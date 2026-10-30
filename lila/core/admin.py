"""Lila Framework v2.0.x Admin 2.0 Engine.

- Uses the project's database connection (not the global default DB).
- Creates the ``admins`` table through the normal model/migration flow.
- No SQL errors are exposed to the browser.
- Server-side sanitized JSON for the CRUD table (no script breakout/XSS).
"""

import os
import re
import glob
import json
from typing import List, Optional, Any, Dict

from sqlalchemy import Column, Integer, String, TIMESTAMP, func, select
from starlette.requests import Request
from starlette.responses import RedirectResponse

from lila.core.responses import JSONResponse, orjson_dumps, orjson_loads
from lila.core.session import Session
from lila.core.templates import render
from lila.core.logger import Logger, DEFAULT_LOG_DIR, clear_logs
from lila.core.cache import Cache
from lila.core.auth import PasswordHasher
from lila.core.exporter import Exporter
from lila.core.middleware import admin_required
from lila.core.base_model import BaseModel
from lila.core.config import ENV_CONFIG
from lila.core.request import Request as LilaRequest

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    psutil = None
    HAS_PSUTIL = False


_ADMIN_TABLE_READY = False


class Admin(BaseModel):
    """Administrator account stored in the project database."""

    __tablename__ = "admins"
    _delete_logic = True
    _active_field = "active"
    __private_fields__ = ("password",)

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    username = Column(String(length=100), unique=True, nullable=False, index=True)
    password = Column(String(length=255), nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, nullable=False, server_default=func.now())

    @classmethod
    async def get_by_username_async(cls, username: str):
        conn = cls.get_connection()
        async with conn.transaction() as session:
            stmt = (
                select(cls)
                .where(func.lower(cls.username) == str(username).strip().lower(), cls.active == 1)
                .limit(1)
            )
            result = await session.execute(stmt)
            return result.scalars().first()


async def ensure_admin_table_async(connection=None) -> None:
    """Creates the admins table (and any missing columns) using the project DB."""
    global _ADMIN_TABLE_READY
    if _ADMIN_TABLE_READY:
        return
    conn = connection or Admin.get_connection()
    await conn.migrate_async(use_base=True, add_columns=False)
    _ADMIN_TABLE_READY = True


def pluralize(name: str) -> str:
    """Small English pluralizer used by the admin navigation."""
    lower = name.lower()
    if lower.endswith(("s", "x", "z", "ch", "sh")):
        return f"{lower}es"
    if lower.endswith("y") and len(lower) > 1 and lower[-2] not in "aeiou":
        return f"{lower[:-1]}ies"
    return f"{lower}s"


def get_admin_metrics() -> dict:
    """Returns real process/system metrics. Missing psutil is reported honestly."""
    cache_stats = Cache.stats()
    if HAS_PSUTIL and psutil is not None:
        try:
            proc = psutil.Process(os.getpid())
            mem_rss = round(proc.memory_info().rss / (1024 * 1024), 2)
            cpu_proc = round(proc.cpu_percent(interval=0), 1)
            vmem = psutil.virtual_memory()
            return {
                "process_memory_mb": mem_rss,
                "process_cpu": cpu_proc,
                "system_used_mb": round((vmem.total - vmem.available) / (1024 * 1024), 2),
                "system_total_mb": round(vmem.total / (1024 * 1024), 2),
                "system_cpu": round(psutil.cpu_percent(interval=0), 1),
                "cache": cache_stats,
                "psutil_available": True,
            }
        except Exception:
            pass

    return {
        "process_memory_mb": None,
        "process_cpu": None,
        "system_used_mb": None,
        "system_total_mb": None,
        "system_cpu": None,
        "cache": cache_stats,
        "psutil_available": False,
    }


def render_admin_menu(models: Optional[list] = None, request: Optional[Request] = None) -> str:
    """Renders the persistent Admin sidebar."""
    models = models or []
    current_path = request.url.path if request else "/admin"

    def _link(path: str, label: str, icon: str) -> str:
        active = current_path == path or (path != "/admin" and current_path.startswith(path))
        cls_name = (
            "flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-sm font-semibold transition-all "
            + ("bg-blue-600 text-white shadow-sm" if active
               else "text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 hover:text-slate-900 dark:hover:text-slate-100")
        )
        return f'<a href="{path}" class="{cls_name}"><span>{icon}</span> <span>{label}</span></a>'

    nav_links = [_link("/admin", "Dashboard", "📊")]
    if models:
        nav_links.append('<div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-3 pt-4 pb-1">Data Models</div>')
        for model in models:
            name = model.__name__
            nav_links.append(_link(f"/admin/{pluralize(name)}", name, "📁"))

    nav_links.append('<div class="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-3 pt-4 pb-1">System</div>')
    nav_links.append('<a href="/admin/logout" data-no-router class="flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-sm font-semibold text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/20 transition-all"><span>🚪</span> <span>Sign Out</span></a>')
    return (
        '<aside id="admin-sidebar" data-persist="true" class="w-64 flex-shrink-0 p-4 border-r border-slate-200 dark:border-slate-800 bg-white dark:bg-slate-900 min-h-screen flex flex-col justify-between">'
        '<div>'
        '<div class="flex items-center gap-3 px-3 py-3 mb-6 border-b border-slate-100 dark:border-slate-800">'
        '<img src="/img/lila-128.webp" alt="Lila" class="w-8 h-8 rounded-lg shadow-sm">'
        '<div><h4 class="font-extrabold text-slate-800 dark:text-slate-100 text-sm m-0">Lila Admin</h4>'
        '<span class="text-[10px] text-slate-400 font-bold uppercase tracking-wider">v2.0</span></div>'
        '</div>'
        f'<nav class="flex flex-col gap-1">{"".join(nav_links)}</nav>'
        '</div>'
        '</aside>'
    )


def _collect_logs(limit_files: int = 5, max_lines: int = 120) -> List[dict]:
    log_dir = os.environ.get("LILA_LOG_DIR") or DEFAULT_LOG_DIR
    entries: List[dict] = []
    if not os.path.isdir(log_dir):
        return entries
    folders = sorted(glob.glob(os.path.join(log_dir, "*")), reverse=True)[:limit_files]
    for folder in folders:
        if not os.path.isdir(folder):
            continue
        for log_file in sorted(glob.glob(os.path.join(folder, "*.log")))[:4]:
            try:
                with open(log_file, "r", encoding="utf-8", errors="replace") as fh:
                    lines = fh.readlines()[-max_lines:]
                entries.append({
                    "date": os.path.basename(folder),
                    "file": os.path.basename(log_file),
                    "lines": [line.rstrip("\n") for line in lines],
                })
            except Exception:
                continue
    return entries


def _jsonable(items: List[dict]) -> Any:
    """Converts datetimes/Decimals to JSON-native values for Jinja's tojson."""
    try:
        return orjson_loads(orjson_dumps(items))
    except Exception:
        clean = []
        for item in items:
            clean.append({k: str(v) if not isinstance(v, (str, int, float, bool, type(None))) else v for k, v in item.items()})
        return clean


def _model_fields(model) -> List[str]:
    private = set(getattr(model, "__private_fields__", ()))
    return [col.name for col in model.__table__.columns if col.name not in private]


def _sanitize_record(model, record: dict) -> dict:
    """Never exposes password/hash fields through the admin API."""
    private = set(getattr(model, "__private_fields__", ())) | {"password", "password_hash", "hashed_password"}
    return {k: v for k, v in (record or {}).items() if k not in private}


def _coerce_payload(model, data: dict) -> dict:
    """Whitelists model columns and coerces common scalar types."""
    columns = {col.name: col for col in model.__table__.columns}
    private = set(getattr(model, "__private_fields__", ()))
    payload: dict = {}
    for key, value in (data or {}).items():
        if key not in columns or key in ("id",):
            continue
        if key in private and key != "password":
            continue
        if key in ("created_at", "updated_at"):
            continue
        column = columns[key]
        py_type = getattr(column.type, "python_type", None)
        if value == "" and py_type in (int, float):
            value = None
        elif value not in (None, "") and py_type is int:
            try:
                value = int(value)
            except (TypeError, ValueError):
                continue
        elif value not in (None, "") and py_type is float:
            try:
                value = float(value)
            except (TypeError, ValueError):
                continue
        elif value not in (None, "") and py_type is bool:
            value = str(value).lower() in ("1", "true", "yes", "on")
        # Let DB defaults apply for empty optional/defaulted numeric fields.
        if value is None and (column.default is not None or column.server_default is not None):
            continue
        payload[key] = value
    return payload


def admin_routes(models: list, router: Any, default_route: str = "admin") -> Any:
    """Mounts Admin 2.0 routes on the given router."""
    prefix = f"/{default_route.strip('/')}"
    router.openapi = False

    @router.get(f"{prefix}/login")
    async def admin_login_view(request: Request):
        return render(request, "admin/login", csrf=True)

    @router.post(f"{prefix}/login", csrf=True)
    async def admin_login_action(request: Request):
        client_ip = getattr(request.client, "host", "unknown")
        attempts = await Cache.incr_async(f"rl:admin-login:{client_ip}", ttl=60)
        if attempts > 10:
            return JSONResponse(
                {"success": False, "message": "Too many attempts. Try again later."},
                status_code=429,
                headers={"Retry-After": "60"},
            )
        try:
            body = await request.json()
        except Exception:
            return JSONResponse({"success": False, "message": "Invalid request"}, status_code=400)

        username = str((body or {}).get("username") or (body or {}).get("user") or "").strip()
        password = str((body or {}).get("password") or "")
        if not username or not password:
            return JSONResponse({"success": False, "message": "Invalid credentials"}, status_code=401)

        try:
            await ensure_admin_table_async()
            admin_record = await Admin.get_by_username_async(username)
            valid = bool(admin_record) and await PasswordHasher.verify_async(admin_record.password, password)
        except Exception as exc:
            Logger.error(f"[Lila Admin] Login failed: {exc}", exception=exc)
            return JSONResponse({"success": False, "message": "Admin login unavailable"}, status_code=503)

        if not valid:
            return JSONResponse({"success": False, "message": "Invalid credentials"}, status_code=401)

        response = JSONResponse({"success": True, "redirect": prefix})
        await Session.set_async(
            {"id": admin_record.id, "username": admin_record.username},
            response,
            cookie_name="admin_session",
            max_age=43200,
        )
        return response

    @router.get(f"{prefix}/logout")
    async def admin_logout_view(request: Request):
        response = RedirectResponse(f"{prefix}/login", status_code=303)
        await Session.delete_async(request, response, cookie_name="admin_session")
        return response

    @router.get(prefix)
    @admin_required(redirect_to=f"{prefix}/login")
    async def admin_dashboard_view(request: Request):
        metrics = get_admin_metrics()
        menu_html = render_admin_menu(models, request)
        context = {
            "metrics": metrics,
            "cache_stats": metrics.get("cache", {}),
            "menu": menu_html,
            "logs": _collect_logs(),
        }
        return render(request, "admin/dashboard", context=context)

    @router.post(f"{prefix}/cache/clear", csrf=True)
    @admin_required(redirect_to=f"{prefix}/login")
    async def admin_clear_cache(request: Request):
        await Cache.clear_async(include_sessions=False)
        return {"success": True, "message": "Cache cleared (sessions preserved)."}

    @router.delete(f"{prefix}/logs", csrf=True)
    @admin_required(redirect_to=f"{prefix}/login")
    async def admin_delete_logs(request: Request):
        deleted = clear_logs()
        return {"success": True, "message": f"Cleared {deleted} log directories."}

    # ──────────────────────────────────────────────────────────────────────────
    # Dynamic model CRUD
    # ──────────────────────────────────────────────────────────────────────────
    def _mount_model_crud(current_model: Any):
        current_name = current_model.__name__
        current_plural = pluralize(current_name)
        private = set(getattr(current_model, "__private_fields__", ()))

        @router.get(f"{prefix}/{current_plural}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def model_view(request: Request):
            raw_items = await current_model.get_all_async(limit=500)
            items = [_sanitize_record(current_model, item) for item in raw_items]
            headers = [
                col.name for col in current_model.__table__.columns
                if col.name not in private and col.name != "password"
            ]
            context = {
                "model_name": current_name,
                "model_plural": current_plural,
                "headers": headers,
                "items_json": _jsonable(items),
                "menu": render_admin_menu(models, request),
            }
            return render(request, "admin/model_table", context=context)

        @router.get(f"{prefix}/api/{current_plural}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_list(request: Request):
            raw_items = await current_model.get_all_async(limit=1000)
            return [_sanitize_record(current_model, item) for item in raw_items]

        @router.get(f"{prefix}/api/{current_plural}/{{id:int}}")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_get(request: Request, id: int):
            rec = await current_model.get_by_id_async(id)
            if not rec:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return _sanitize_record(current_model, rec)

        @router.post(f"{prefix}/api/{current_plural}", csrf=True)
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_create(request: Request):
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({"success": False, "message": "Invalid JSON body"}, status_code=400)
            payload = _coerce_payload(current_model, data)
            if "password" in payload and payload["password"]:
                payload["password"] = await PasswordHasher.hash_async(str(payload["password"]))
            try:
                created = await current_model.insert_async(**payload)
            except Exception as exc:
                return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
            return JSONResponse({"success": True, "data": _sanitize_record(current_model, created)}, status_code=201)

        @router.put(f"{prefix}/api/{current_plural}/{{id:int}}", csrf=True)
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_update(request: Request, id: int):
            try:
                data = await request.json()
            except Exception:
                return JSONResponse({"success": False, "message": "Invalid JSON body"}, status_code=400)
            payload = _coerce_payload(current_model, data)
            if "password" in payload:
                if payload["password"]:
                    payload["password"] = await PasswordHasher.hash_async(str(payload["password"]))
                else:
                    payload.pop("password", None)
            if not payload:
                return JSONResponse({"success": False, "message": "No editable fields provided"}, status_code=400)
            try:
                ok = await current_model.update_async(id, **payload)
            except Exception as exc:
                return JSONResponse({"success": False, "message": str(exc)}, status_code=400)
            if not ok:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return {"success": True, "id": id}

        @router.delete(f"{prefix}/api/{current_plural}/{{id:int}}", csrf=True)
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_delete(request: Request, id: int):
            ok = await current_model.delete_async(id)
            if not ok:
                return JSONResponse({"success": False, "message": "Record not found"}, status_code=404)
            return {"success": True, "deleted": True}

        @router.get(f"{prefix}/api/{current_plural}/export")
        @admin_required(redirect_to=f"{prefix}/login")
        async def api_export(request: Request):
            limit = 10000
            raw_items = await current_model.get_all_async(limit=limit)
            items = [_sanitize_record(current_model, item) for item in raw_items]
            response = Exporter.to_csv_response(items, filename=f"{current_plural}.csv")
            try:
                total = await current_model.count_async()
                if total > limit:
                    response.headers["X-Lila-Truncated"] = "true"
                    response.headers["X-Lila-Total-Rows"] = str(total)
            except Exception:
                pass
            return response

    for model in models:
        _mount_model_crud(model)

    return router

