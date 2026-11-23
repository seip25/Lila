"""Opt-in desktop bug reports and anonymous diagnostics (server + client).

Server side (disabled by default):
    app = App(..., desktop_reports=True)
    # or: desktop_reports={"prefix": "/api/desktop", "retention_days": 90, ...}

- Stores reports in an isolated SQLite WAL database under
  ``app/desktop/database/reports.db`` (never touches the main app DB).
- Enforces streaming body-size limits (256 KB default -> 413), per-IP rate
  limits (10/60s default -> 429), strict Pydantic validation (422), optional
  ``X-Lila-Report-Token`` auth (401), PII redaction, and deduplication on
  ``(kind, app_version, install_id, period_key, content_hash)``.
- Every successful ingestion schedules a background cleanup deleting records
  older than ``retention_days`` (default 90 days = ~3 months).
- All ingestion/query routes are tagged ``desktop=False`` so they exist only on
  the web server and are excluded from desktop executables.

Client side (inside ``lila desktop dev`` / frozen ``.exe``):
- Preferences persisted in ``get_data_path("desktop_preferences.json")`` with
  ``anonymous_telemetry`` **False** (opt-in) by default.
- Manual bug reports (``send_bug_report``) and periodic anonymous telemetry
  (``DesktopTelemetryScheduler``) redact PII and avoid duplicate uploads.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
import hashlib
import hmac
import json
import os
import platform
import re
import sqlite3
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field, ValidationError, field_validator

from lila.core.background import BackgroundTask
from lila.core.cache import Cache
from lila.core.config import ENV_CONFIG, get_data_path
from lila.core.logger import Logger
from lila.core.request import Request
from lila.core.responses import JSONResponse
from lila.core.routing import Router
from lila.core.session import Session
from lila.core.tasks import task

DEFAULT_MAX_BODY_BYTES = 256 * 1024  # 256 KB
DEFAULT_RATE_LIMIT = (10, 60)  # 10 requests per 60 seconds per IP
DEFAULT_RETENTION_DAYS = 90  # ~3 months
MAX_CLIENT_LOG_BYTES = 120_000
DEFAULT_TELEMETRY_INTERVAL = 3600

_SCHEMA = """
CREATE TABLE IF NOT EXISTS desktop_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,
    app_name TEXT NOT NULL DEFAULT '',
    app_version TEXT NOT NULL DEFAULT '1.0.0',
    lila_version TEXT NOT NULL DEFAULT '',
    platform TEXT NOT NULL DEFAULT '',
    os_version TEXT NOT NULL DEFAULT '',
    install_id TEXT NOT NULL,
    period_key TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    log_date TEXT NOT NULL DEFAULT '',
    log_type TEXT NOT NULL DEFAULT '',
    user_note TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_desktop_reports_dedup
    ON desktop_reports (kind, app_version, install_id, period_key, content_hash);
CREATE INDEX IF NOT EXISTS ix_desktop_reports_created_at
    ON desktop_reports (created_at);
CREATE INDEX IF NOT EXISTS ix_desktop_reports_lookup
    ON desktop_reports (kind, app_version, period_key);
"""

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}\b")
_SECRET_KV_RE = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?token|refresh[_-]?token|csrf)\b\s*([=:])\s*([^\s,;\"']+|\"[^\"]*\"|'[^']*')"
)
_WIN_HOME_RE = re.compile(r"(?i)([A-Z]:\\Users\\)[^\\/\r\n]+")
_UNIX_HOME_RE = re.compile(r"(/(?:Users|home)/)[^/\r\n]+")

_VERSION_RE = re.compile(r"^[A-Za-z0-9._+-]{1,40}$")
_INSTALL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_PERIOD_RE = re.compile(r"^\d{4}-\d{2}(-\d{2})?$")
_PLATFORM_RE = re.compile(r"^[a-z0-9_-]{1,20}$")
_HASH_RE = re.compile(r"^[a-fA-F0-9]{16,64}$")

_db_lock = threading.Lock()
_initialized_dbs: set[str] = set()


def redact_pii(text: Any) -> str:
    """Masks emails, tokens/secrets, and user home directories before storing or sending."""
    if text is None:
        return ""
    value = str(text)
    if not value:
        return ""
    value = _EMAIL_RE.sub("[email]", value)
    value = _BEARER_RE.sub("Bearer [redacted]", value)
    value = _JWT_RE.sub("[jwt]", value)
    value = _SECRET_KV_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted]", value)
    value = _WIN_HOME_RE.sub(r"\1[user]", value)
    value = _UNIX_HOME_RE.sub(r"\1[user]", value)
    return value


def _redact_obj(obj: Any, depth: int = 0) -> Any:
    if depth > 4:
        return "[truncated]"
    if isinstance(obj, str):
        return redact_pii(obj)[:500]
    if isinstance(obj, dict):
        out: Dict[str, Any] = {}
        for idx, (k, v) in enumerate(obj.items()):
            if idx >= 30:
                break
            out[str(k)[:60]] = _redact_obj(v, depth + 1)
        return out
    if isinstance(obj, (list, tuple)):
        return [_redact_obj(item, depth + 1) for item in list(obj)[:30]]
    if isinstance(obj, (int, float, bool)) or obj is None:
        return obj
    return redact_pii(str(obj))[:200]


def resolve_reports_db_path(explicit: Optional[str] = None) -> str:
    configured = explicit or os.environ.get("LILA_DESKTOP_REPORTS_DB") or ""
    if configured:
        return os.path.abspath(configured)
    return get_data_path("app", "desktop", "database", "reports.db")


def _connect_db(db_path: str) -> sqlite3.Connection:
    folder = os.path.dirname(db_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=10000")
    with _db_lock:
        if db_path not in _initialized_dbs:
            conn.executescript(_SCHEMA)
            _initialized_dbs.add(db_path)
    return conn


def prune_old_reports(db_path: Optional[str] = None, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """Deletes desktop reports older than ``retention_days`` (default 90 days)."""
    resolved = resolve_reports_db_path(db_path)
    if not os.path.isfile(resolved):
        return 0
    days = max(1, int(retention_days or DEFAULT_RETENTION_DAYS))
    cutoff = time.time() - (days * 86400)
    conn = _connect_db(resolved)
    try:
        cur = conn.execute("DELETE FROM desktop_reports WHERE created_at < ?", (cutoff,))
        return max(0, int(cur.rowcount or 0))
    finally:
        conn.close()


@task(name="lila.core.desktop_reports:prune_old_reports_task", retries=2, timeout=60)
def prune_old_reports_task(db_path: Optional[str] = None, retention_days: int = DEFAULT_RETENTION_DAYS) -> int:
    """SQLite/Redis task wrapper for pruning old desktop reports."""
    return prune_old_reports(db_path=db_path, retention_days=retention_days)


class _BaseReportPayload(BaseModel):
    app_name: str = Field(default="Lila Desktop", max_length=120)
    app_version: str = Field(default="1.0.0", max_length=40)
    lila_version: str = Field(default="", max_length=40)
    platform: str = Field(default="unknown", max_length=20)
    os_version: str = Field(default="", max_length=80)
    install_id: str = Field(..., min_length=8, max_length=64)
    period_key: str = Field(..., min_length=7, max_length=10)
    log_date: str = Field(default="", max_length=20)
    log_type: str = Field(default="app", max_length=40)
    user_note: str = Field(default="", max_length=2000)
    logs: str = Field(default="", max_length=180_000)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    content_hash: Optional[str] = Field(default=None, max_length=64)

    @field_validator("app_version")
    @classmethod
    def _val_version(cls, value: str) -> str:
        clean = value.strip()
        if not _VERSION_RE.match(clean):
            raise ValueError("Invalid app_version format")
        return clean

    @field_validator("install_id")
    @classmethod
    def _val_install_id(cls, value: str) -> str:
        clean = value.strip()
        if not _INSTALL_ID_RE.match(clean):
            raise ValueError("Invalid install_id format")
        return clean

    @field_validator("period_key")
    @classmethod
    def _val_period(cls, value: str) -> str:
        clean = value.strip()
        if not _PERIOD_RE.match(clean):
            raise ValueError("period_key must be YYYY-MM or YYYY-MM-DD")
        return clean

    @field_validator("platform")
    @classmethod
    def _val_platform(cls, value: str) -> str:
        clean = (value or "unknown").strip().lower()
        if not _PLATFORM_RE.match(clean):
            raise ValueError("Invalid platform")
        return clean

    @field_validator("content_hash")
    @classmethod
    def _val_hash(cls, value: Optional[str]) -> Optional[str]:
        if value is None or value == "":
            return None
        clean = value.strip().lower()
        if not _HASH_RE.match(clean):
            raise ValueError("Invalid content_hash")
        return clean

    @field_validator("metrics")
    @classmethod
    def _val_metrics(cls, value: Dict[str, Any]) -> Dict[str, Any]:
        if len(value) > 30:
            raise ValueError("Too many metric keys (max 30)")
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        if len(encoded.encode("utf-8")) > 16_384:
            raise ValueError("metrics payload too large (max 16 KB)")
        return value


class BugReportPayload(_BaseReportPayload):
    pass


class TelemetryPayload(_BaseReportPayload):
    pass


def _compute_content_hash(kind: str, data: Dict[str, Any]) -> str:
    canonical = json.dumps(
        {
            "kind": kind,
            "app_version": data.get("app_version", ""),
            "period_key": data.get("period_key", ""),
            "log_date": data.get("log_date", ""),
            "log_type": data.get("log_type", ""),
            "user_note": data.get("user_note", ""),
            "logs": data.get("logs", ""),
            "metrics": data.get("metrics", {}),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class _PayloadTooLargeError(Exception):
    pass


async def _read_bounded_json(request: Request, max_bytes: int) -> dict:
    raw_len = request.headers.get("content-length")
    if raw_len:
        try:
            if int(raw_len) > max_bytes:
                raise _PayloadTooLargeError()
        except ValueError:
            pass
    chunks: List[bytes] = []
    total = 0
    async for chunk in request.stream():
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            raise _PayloadTooLargeError()
        chunks.append(chunk)
    raw = b"".join(chunks)
    if not raw:
        return {}
    parsed = json.loads(raw.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("JSON body must be an object")
    return parsed


def _check_report_token(request: Request, expected_token: str) -> bool:
    if not expected_token:
        return True
    provided = request.headers.get("x-lila-report-token", "").strip()
    if not provided:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            provided = auth[7:].strip()
    return bool(provided) and hmac.compare_digest(provided, expected_token)


async def _is_admin_or_token(request: Request, expected_token: str) -> bool:
    if expected_token and _check_report_token(request, expected_token):
        return True
    admin = await Session.get_async(request, cookie_name="admin_session")
    if isinstance(admin, dict) and admin.get("admin_id"):
        return True
    admin_alt = await Session.get_async(request, cookie_name="admin")
    return isinstance(admin_alt, dict) and bool(admin_alt.get("admin_id") or admin_alt.get("is_admin"))


def _store_report_sync(
    db_path: str,
    kind: str,
    validated: _BaseReportPayload,
) -> Tuple[bool, Optional[int], str]:
    redacted_note = redact_pii(validated.user_note)
    redacted_logs = redact_pii(validated.logs)
    redacted_metrics = _redact_obj(validated.metrics)
    normalized = {
        "app_name": validated.app_name.strip(),
        "app_version": validated.app_version,
        "lila_version": validated.lila_version.strip(),
        "platform": validated.platform,
        "os_version": validated.os_version.strip(),
        "install_id": validated.install_id,
        "period_key": validated.period_key,
        "log_date": validated.log_date.strip(),
        "log_type": validated.log_type.strip() or "app",
        "user_note": redacted_note,
        "logs": redacted_logs,
        "metrics": redacted_metrics,
    }
    content_hash = validated.content_hash or _compute_content_hash(kind, normalized)
    payload_json = json.dumps(normalized, ensure_ascii=False)
    now = time.time()

    conn = _connect_db(db_path)
    try:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO desktop_reports (
                kind, app_name, app_version, lila_version, platform, os_version,
                install_id, period_key, content_hash, log_date, log_type,
                user_note, payload, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                kind,
                normalized["app_name"],
                normalized["app_version"],
                normalized["lila_version"],
                normalized["platform"],
                normalized["os_version"],
                normalized["install_id"],
                normalized["period_key"],
                content_hash,
                normalized["log_date"],
                normalized["log_type"],
                redacted_note,
                payload_json,
                now,
            ),
        )
        stored = int(cur.rowcount or 0) > 0
        row_id = int(cur.lastrowid) if stored and cur.lastrowid else None
        return stored, row_id, content_hash
    finally:
        conn.close()


def create_reports_router(config: Any = True) -> Router:
    """Creates the hardened ``desktop=False`` router for desktop bug/telemetry ingestion."""
    opts = dict(config) if isinstance(config, dict) else {}
    prefix = "/" + str(opts.get("prefix", "/api/desktop") or "/api/desktop").strip("/")
    max_body_bytes = max(1024, int(opts.get("max_body_bytes", DEFAULT_MAX_BODY_BYTES) or DEFAULT_MAX_BODY_BYTES))
    rate_limit_cfg = opts.get("rate_limit", DEFAULT_RATE_LIMIT)
    if isinstance(rate_limit_cfg, int):
        rl_max, rl_win = max(1, rate_limit_cfg), 60
    elif isinstance(rate_limit_cfg, (tuple, list)) and len(rate_limit_cfg) >= 2:
        rl_max, rl_win = max(1, int(rate_limit_cfg[0])), max(1, int(rate_limit_cfg[1]))
    else:
        rl_max, rl_win = DEFAULT_RATE_LIMIT
    retention_days = max(1, int(opts.get("retention_days", DEFAULT_RETENTION_DAYS) or DEFAULT_RETENTION_DAYS))
    explicit_token = opts.get("token")
    db_path_cfg = opts.get("db_path")
    admin_auth = bool(opts.get("admin_auth", True))

    router = Router(prefix=prefix, tags=["Desktop Reports"], desktop=False)

    def _expected_token() -> str:
        if explicit_token is not None:
            return str(explicit_token or "")
        return str(os.environ.get("DESKTOP_REPORT_TOKEN") or ENV_CONFIG.get("DESKTOP_REPORT_TOKEN", "") or "")

    def _db_path() -> str:
        return resolve_reports_db_path(db_path_cfg)

    async def _ingest(request: Request, kind: str, model_cls: type[_BaseReportPayload]) -> JSONResponse:
        client_ip = getattr(getattr(request, "client", None), "host", None) or "unknown"
        rl_key = f"rl:desktop_report:{kind}:{client_ip}"
        count = await Cache.incr_async(rl_key, ttl=rl_win)
        if count > rl_max:
            return JSONResponse(
                {"success": False, "error": "rate_limit_exceeded", "message": "Rate limit exceeded."},
                status_code=429,
                headers={"Retry-After": str(rl_win)},
            )

        expected = _expected_token()
        if expected and not _check_report_token(request, expected):
            return JSONResponse({"success": False, "message": "Invalid or missing report token"}, status_code=401)

        try:
            raw_data = await _read_bounded_json(request, max_body_bytes)
        except _PayloadTooLargeError:
            return JSONResponse(
                {"success": False, "message": f"Payload exceeds limit ({max_body_bytes} bytes)"},
                status_code=413,
            )
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
            return JSONResponse({"success": False, "message": "Malformed JSON payload"}, status_code=400)

        try:
            validated = model_cls.model_validate(raw_data)
        except ValidationError as exc:
            return JSONResponse.validation_error(exc)

        resolved_db = _db_path()
        stored, row_id, content_hash = await asyncio.to_thread(_store_report_sync, resolved_db, kind, validated)
        bg = BackgroundTask(prune_old_reports, resolved_db, retention_days)
        if stored:
            return JSONResponse(
                {"success": True, "status": "stored", "stored": True, "id": row_id, "hash": content_hash},
                status_code=201,
                background=bg,
            )
        return JSONResponse(
            {"success": True, "status": "duplicate", "stored": False, "hash": content_hash},
            status_code=200,
            background=bg,
        )

    @router.post("/bug", desktop=False)
    async def submit_bug_report(request: Request):
        return await _ingest(request, "bug", BugReportPayload)

    @router.post("/telemetry", desktop=False)
    async def submit_telemetry(request: Request):
        return await _ingest(request, "telemetry", TelemetryPayload)

    @router.get("/reports", desktop=False)
    async def list_reports(
        request: Request,
        kind: Optional[str] = None,
        app_version: Optional[str] = None,
        period_key: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        if admin_auth and not await _is_admin_or_token(request, _expected_token()):
            return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)

        safe_limit = max(1, min(int(limit or 50), 200))
        safe_offset = max(0, int(offset or 0))
        clauses: List[str] = []
        params: List[Any] = []
        if kind:
            clauses.append("kind = ?")
            params.append(kind.strip())
        if app_version:
            clauses.append("app_version = ?")
            params.append(app_version.strip())
        if period_key:
            clauses.append("period_key = ?")
            params.append(period_key.strip())
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        resolved_db = _db_path()
        if not os.path.isfile(resolved_db):
            return {"items": [], "total": 0, "limit": safe_limit, "offset": safe_offset}

        conn = _connect_db(resolved_db)
        try:
            total = conn.execute(f"SELECT COUNT(*) FROM desktop_reports {where}", params).fetchone()[0]
            rows = conn.execute(
                f"""
                SELECT id, kind, app_name, app_version, lila_version, platform, os_version,
                       install_id, period_key, content_hash, log_date, log_type, user_note,
                       payload, created_at
                FROM desktop_reports
                {where}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                [*params, safe_limit, safe_offset],
            ).fetchall()
            items = []
            for row in rows:
                item = dict(row)
                try:
                    item["payload"] = json.loads(item["payload"])
                except Exception:
                    pass
                items.append(item)
            return {"items": items, "total": int(total), "limit": safe_limit, "offset": safe_offset}
        finally:
            conn.close()

    @router.get("/reports/stats", desktop=False)
    async def report_stats(request: Request):
        if admin_auth and not await _is_admin_or_token(request, _expected_token()):
            return JSONResponse({"success": False, "message": "Unauthorized"}, status_code=401)

        resolved_db = _db_path()
        if not os.path.isfile(resolved_db):
            return {"total": 0, "by_kind": {}, "by_version": {}, "by_platform": {}, "by_period": {}}

        conn = _connect_db(resolved_db)
        try:
            total = conn.execute("SELECT COUNT(*) FROM desktop_reports").fetchone()[0]
            by_kind = {
                r[0]: r[1]
                for r in conn.execute("SELECT kind, COUNT(*) FROM desktop_reports GROUP BY kind").fetchall()
            }
            by_version = {
                r[0]: r[1]
                for r in conn.execute("SELECT app_version, COUNT(*) FROM desktop_reports GROUP BY app_version").fetchall()
            }
            by_platform = {
                r[0]: r[1]
                for r in conn.execute("SELECT platform, COUNT(*) FROM desktop_reports GROUP BY platform").fetchall()
            }
            by_period = {
                r[0]: r[1]
                for r in conn.execute(
                    "SELECT period_key, COUNT(*) FROM desktop_reports GROUP BY period_key ORDER BY period_key DESC LIMIT 30"
                ).fetchall()
            }
            return {
                "total": int(total),
                "by_kind": by_kind,
                "by_version": by_version,
                "by_platform": by_platform,
                "by_period": by_period,
            }
        finally:
            conn.close()

    return router


# ─── Desktop Client Helpers ───────────────────────────────────────────────────

def get_preferences_path() -> str:
    return get_data_path("desktop_preferences.json")


def load_preferences() -> Dict[str, Any]:
    path = get_preferences_path()
    prefs: Dict[str, Any] = {}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
            if isinstance(loaded, dict):
                prefs = loaded
        except Exception:
            prefs = {}

    changed = False
    if not isinstance(prefs.get("install_id"), str) or not _INSTALL_ID_RE.match(prefs["install_id"]):
        prefs["install_id"] = uuid.uuid4().hex
        changed = True
    if "anonymous_telemetry" not in prefs:
        prefs["anonymous_telemetry"] = False
        changed = True
    else:
        prefs["anonymous_telemetry"] = bool(prefs["anonymous_telemetry"])
    if not isinstance(prefs.get("sent_hashes"), list):
        prefs["sent_hashes"] = []
        changed = True
    if changed:
        save_preferences(prefs)
    return prefs


def save_preferences(prefs: Dict[str, Any]) -> None:
    path = get_preferences_path()
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(prefs, fh, indent=2)
    except OSError:
        pass


def get_configured_report_url() -> str:
    url = str(os.environ.get("DESKTOP_REPORT_URL") or ENV_CONFIG.get("DESKTOP_REPORT_URL", "") or "").strip()
    return url.rstrip("/")


def get_configured_report_token() -> str:
    return str(os.environ.get("DESKTOP_REPORT_TOKEN") or ENV_CONFIG.get("DESKTOP_REPORT_TOKEN", "") or "").strip()


def is_valid_report_url(url: str) -> bool:
    clean = (url or "").strip()
    return clean.startswith("https://") or clean.startswith("http://127.0.0.1") or clean.startswith("http://localhost")


def get_report_settings() -> Dict[str, Any]:
    prefs = load_preferences()
    url = get_configured_report_url()
    try:
        interval = max(60, int(os.environ.get("DESKTOP_TELEMETRY_INTERVAL") or ENV_CONFIG.get("DESKTOP_TELEMETRY_INTERVAL", DEFAULT_TELEMETRY_INTERVAL) or DEFAULT_TELEMETRY_INTERVAL))
    except (TypeError, ValueError):
        interval = DEFAULT_TELEMETRY_INTERVAL
    return {
        "configured": bool(url and is_valid_report_url(url)),
        "report_url": url,
        "anonymous_telemetry": bool(prefs.get("anonymous_telemetry", False)),
        "install_id": prefs.get("install_id", ""),
        "last_telemetry_at": prefs.get("last_telemetry_at"),
        "interval_seconds": interval,
    }


def set_telemetry_opt_in(enabled: bool) -> Dict[str, Any]:
    prefs = load_preferences()
    prefs["anonymous_telemetry"] = bool(enabled)
    save_preferences(prefs)
    return get_report_settings()


def collect_recent_logs(
    max_days: int = 7,
    max_bytes: int = MAX_CLIENT_LOG_BYTES,
    log_types: Optional[Tuple[str, ...]] = None,
) -> Dict[str, Any]:
    """Reads recent log tails from ``get_data_path('app', 'logs')`` and redacts PII."""
    base_dir = os.environ.get("LILA_LOG_DIR") or get_data_path("app", "logs")
    if not os.path.isabs(base_dir):
        base_dir = os.path.join(os.getcwd(), base_dir)
    if not os.path.isdir(base_dir):
        return {"logs": "", "log_date": _dt.date.today().isoformat(), "log_type": "none", "files": []}

    date_dirs: List[str] = []
    try:
        for entry in os.listdir(base_dir):
            full = os.path.join(base_dir, entry)
            if os.path.isdir(full) and re.match(r"^\d{4}-\d{2}-\d{2}$", entry):
                date_dirs.append(entry)
    except OSError:
        date_dirs = []

    date_dirs.sort(reverse=True)
    selected_dates = date_dirs[: max(1, int(max_days))]
    sections: List[str] = []
    files: List[str] = []
    remaining = max(1024, int(max_bytes))
    latest_date = selected_dates[0] if selected_dates else _dt.date.today().isoformat()
    found_types: List[str] = []

    for date_name in selected_dates:
        if remaining <= 0:
            break
        folder = os.path.join(base_dir, date_name)
        try:
            names = sorted(os.listdir(folder))
        except OSError:
            continue
        for fname in names:
            if not fname.endswith(".log"):
                continue
            stem = fname[:-4]
            if log_types and stem not in log_types:
                continue
            fpath = os.path.join(folder, fname)
            if not os.path.isfile(fpath):
                continue
            try:
                size = os.path.getsize(fpath)
                with open(fpath, "r", encoding="utf-8", errors="replace") as fh:
                    if size > remaining:
                        fh.seek(max(0, size - remaining))
                        fh.readline()  # avoid cutting mid-line
                    content = fh.read(remaining)
            except OSError:
                continue
            clean = redact_pii(content).strip()
            if not clean:
                continue
            header = f"=== {date_name}/{fname} ==="
            block = f"{header}\n{clean}"
            if len(block.encode("utf-8")) > remaining:
                block = block[-remaining:]
            sections.append(block)
            files.append(f"{date_name}/{fname}")
            if stem not in found_types:
                found_types.append(stem)
            remaining -= len(block.encode("utf-8"))
            if remaining <= 256:
                break

    return {
        "logs": "\n\n".join(sections),
        "log_date": latest_date,
        "log_type": ",".join(found_types) if found_types else "none",
        "files": files,
    }


def _platform_key() -> str:
    return {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")


def _app_meta() -> Dict[str, str]:
    import lila

    return {
        "app_name": str(os.environ.get("TITLE_PROJECT") or ENV_CONFIG.get("TITLE_PROJECT", "Lila Desktop") or "Lila Desktop")[:120],
        "app_version": str(os.environ.get("LILA_APP_VERSION") or ENV_CONFIG.get("VERSION_PROJECT", "1.0.0") or "1.0.0")[:40],
        "lila_version": str(getattr(lila, "__version__", "") or "")[:40],
        "platform": _platform_key(),
        "os_version": f"{platform.system()} {platform.release()}"[:80],
    }


def _open_url(request: urllib.request.Request, timeout: float):
    if request.full_url.startswith(("http://127.0.0.1", "http://localhost")):
        return urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout)  # nosec - https/loopback enforced by caller


def _post_report(endpoint_url: str, payload: Dict[str, Any], token: str = "", timeout: float = 8.0) -> Dict[str, Any]:
    headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "lila-desktop-reporter"}
    if token:
        headers["X-Lila-Report-Token"] = token
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(endpoint_url, data=body, headers=headers, method="POST")
    try:
        with _open_url(req, timeout=timeout) as resp:
            raw = resp.read(64_000).decode("utf-8", "replace")
            data = json.loads(raw) if raw.startswith("{") else {}
            return {
                "ok": True,
                "status": data.get("status", "stored"),
                "stored": bool(data.get("stored", True)),
                "duplicate": data.get("status") == "duplicate",
                "id": data.get("id"),
            }
    except urllib.error.HTTPError as exc:
        try:
            detail = exc.read(16_000).decode("utf-8", "replace")
        except Exception:
            detail = str(exc)
        return {"ok": False, "status": "http_error", "code": exc.code, "reason": detail}
    except Exception as exc:
        return {"ok": False, "status": "network_error", "reason": exc.__class__.__name__}


def send_bug_report(
    note: str = "",
    include_logs: bool = True,
    url: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Sends a manual bug report (optionally with redacted recent logs) to ``DESKTOP_REPORT_URL/bug``."""
    base_url = (url or get_configured_report_url()).rstrip("/")
    if not base_url:
        return {"ok": False, "status": "unconfigured", "reason": "DESKTOP_REPORT_URL is not configured"}
    if not is_valid_report_url(base_url):
        return {"ok": False, "status": "invalid_url", "reason": "Report URL must use https"}

    prefs = load_preferences()
    meta = _app_meta()
    log_bundle = collect_recent_logs(max_days=7, max_bytes=MAX_CLIENT_LOG_BYTES) if include_logs else {
        "logs": "",
        "log_date": _dt.date.today().isoformat(),
        "log_type": "none",
    }
    period_key = _dt.date.today().isoformat()
    payload: Dict[str, Any] = {
        **meta,
        "install_id": prefs["install_id"],
        "period_key": period_key,
        "log_date": log_bundle["log_date"],
        "log_type": log_bundle["log_type"],
        "user_note": redact_pii(note)[:2000],
        "logs": log_bundle["logs"],
        "metrics": {"frozen": bool(getattr(sys, "frozen", False))},
    }
    payload["content_hash"] = _compute_content_hash("bug", payload)
    target = base_url if base_url.endswith("/bug") else f"{base_url}/bug"
    return _post_report(target, payload, token=(token if token is not None else get_configured_report_token()))


def send_anonymous_telemetry(
    force: bool = False,
    url: Optional[str] = None,
    token: Optional[str] = None,
) -> Dict[str, Any]:
    """Sends opt-in anonymous diagnostics & redacted error log tail to ``DESKTOP_REPORT_URL/telemetry``."""
    prefs = load_preferences()
    if not force and not prefs.get("anonymous_telemetry", False):
        return {"ok": False, "status": "disabled"}

    base_url = (url or get_configured_report_url()).rstrip("/")
    if not base_url:
        return {"ok": False, "status": "unconfigured"}
    if not is_valid_report_url(base_url):
        return {"ok": False, "status": "invalid_url", "reason": "Report URL must use https"}

    meta = _app_meta()
    log_bundle = collect_recent_logs(max_days=3, max_bytes=64_000, log_types=("error", "warning"))
    period_key = _dt.date.today().isoformat()
    payload: Dict[str, Any] = {
        **meta,
        "install_id": prefs["install_id"],
        "period_key": period_key,
        "log_date": log_bundle["log_date"],
        "log_type": log_bundle["log_type"],
        "user_note": "",
        "logs": log_bundle["logs"],
        "metrics": {"frozen": bool(getattr(sys, "frozen", False))},
    }
    content_hash = _compute_content_hash("telemetry", payload)
    payload["content_hash"] = content_hash

    dedup_token = f"{meta['app_version']}:{period_key}:{content_hash}"
    sent_hashes = list(prefs.get("sent_hashes") or [])
    if not force and dedup_token in sent_hashes:
        return {"ok": True, "status": "duplicate", "stored": False, "duplicate": True}

    target = base_url if base_url.endswith("/telemetry") else f"{base_url}/telemetry"
    res = _post_report(target, payload, token=(token if token is not None else get_configured_report_token()))
    if res.get("ok"):
        if dedup_token not in sent_hashes:
            sent_hashes.append(dedup_token)
        prefs["sent_hashes"] = sent_hashes[-60:]
        prefs["last_telemetry_at"] = _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")
        save_preferences(prefs)
    return res


class DesktopTelemetryScheduler:
    """Periodic daemon thread sending opt-in anonymous telemetry every ``interval_seconds``."""

    def __init__(self, interval_seconds: Optional[int] = None):
        if interval_seconds is None:
            try:
                interval_seconds = int(
                    os.environ.get("DESKTOP_TELEMETRY_INTERVAL")
                    or ENV_CONFIG.get("DESKTOP_TELEMETRY_INTERVAL", DEFAULT_TELEMETRY_INTERVAL)
                    or DEFAULT_TELEMETRY_INTERVAL
                )
            except (TypeError, ValueError):
                interval_seconds = DEFAULT_TELEMETRY_INTERVAL
        self.interval_seconds = max(60, int(interval_seconds))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        url = get_configured_report_url()
        if not url or not is_valid_report_url(url):
            return
        if self._thread is not None and self._thread.is_alive():
            return

        def _loop():
            # Small initial delay so startup stays instant, then repeat every interval.
            if self._stop.wait(15.0):
                return
            while not self._stop.is_set():
                try:
                    send_anonymous_telemetry()
                except Exception:
                    pass
                if self._stop.wait(float(self.interval_seconds)):
                    break

        self._thread = threading.Thread(target=_loop, daemon=True, name="lila-desktop-telemetry")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
