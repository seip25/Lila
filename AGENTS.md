# Lila Framework v2.0.0 — Agent & Developer Reference

Lila is a lightweight full-stack Python web framework built on **Starlette**,
**Pydantic v2**, **SQLAlchemy 2.0 Async** and **Jinja2**. It targets 1–2 worker
deployments with SQLite WAL + memory cache by default, optional Redis when
reachable, and a file-cache fallback.

Requires **Python 3.10+**.

---

## 1. Project Structure

```text
Lila/
├── pyproject.toml           # Packaging, dependencies, CLI entry points
├── README.md
├── AGENTS.md
├── SECURITY.md
├── CHANGELOG.md
├── .github/workflows/tests.yml
├── lila/
│   ├── main.py              # Scaffold entrypoint
│   ├── core/                # Framework core
│   │   ├── app.py           # App, static mounts, OpenAPI, debug dashboard
│   │   ├── routing.py       # Router, typed params, cache, CSRF, SEO
│   │   ├── cache.py         # memory / redis / file drivers, counters
│   │   ├── database.py      # Async engine, transactions, schema sync
│   │   ├── base_model.py    # ActiveRecord CRUD, single-flight cache
│   │   ├── config.py        # ConfigLoader, typed ENV_CONFIG, secret handling
│   │   ├── session.py       # signed-cookie sessions (never stores credentials)
│   │   ├── csrf.py          # signed double-submit + form/JSON support
│   │   ├── auth.py          # JWT + Argon2id/scrypt
│   │   ├── middleware.py    # Pure ASGI middlewares + decorators
│   │   ├── admin.py         # Admin 2.0 (project DB, sanitized CRUD)
│   │   ├── templates.py     # Jinja render, CSRF meta, partials, assets
│   │   ├── translate.py     # Pydantic error + UI localization (en/es/pt/zh)
│   │   ├── ia.py            # OpenAI/DeepSeek/Gemini + PII masking
│   │   ├── oauth.py         # Google/GitHub/Discord OAuth
│   │   ├── websocket.py     # WebSocketHub + Redis pub/sub
│   │   ├── files.py         # streaming uploads + WebP
│   │   ├── mailer.py        # SMTP/TLS/SSL mailer
│   │   ├── seo.py           # @seo decorator + SEO_CONFIG
│   │   ├── controller.py    # RequestParser (v1 compatibility)
│   │   ├── exporter.py      # CSV (formula-safe, BOM)
│   │   ├── background.py    # Redis JSON tasks / Starlette fallback
│   │   ├── logger.py        # buffered date-based logs
│   │   ├── debug.py         # in-memory request history
│   │   └── ...              # security, responses, request, two_factor
│   ├── cli/                  # Commands + scaffolds
│   └── resources/            # Bundled templates
└── docs/                     # GitHub Pages documentation
```

---

## 2. Application

```python
from app.config import DEBUG, HOST, PORT, WORKERS
from lila.core.app import App

app = App(
    routes=[router],
    debug=DEBUG,          # bool, not a string
    security=True,        # headers + traversal shield
    rate_limit=300,       # global per-IP; static assets excluded
    logging=False,
    cors=True,            # credentials are OFF by default
    gzip=True,
    openapi=True,
    debug_html=DEBUG,     # mounts /debug (GET / DELETE)
    csrf=False,           # global JSON/header CSRF; prefer route csrf=True
)
```

`App` calls `ConfigLoader.load()` itself, so importing `App` directly still reads
`.env`. `include_router(router, prefix=...)` supports prefixes and raw route lists;
list routes also appear in `/openapi.json`.

---

## 3. Routing

```python
from lila.core.routing import Router, seo
from lila.core.request import Request

router = Router(prefix="/api", default_cache_ttl=60)

@router.get("/items/{id:int}")
async def item(request: Request, id: int, page: int = 1, q: str | None = None):
    return {"id": id, "page": page}

@router.get("/legacy")
@seo(title="Legacy", description="...")
async def legacy(request): ...

@router.route("/old-style", methods=["GET", "POST"])   # v1 compatibility
async def old(request): ...
```

- `dict`/`list` → JSON, `str` → HTML, Pydantic → JSON, `None` → `{"success": true}`.
- Path/query values are cast from annotations (`int`, `float`, `bool`, `Enum`,
  `Literal`, lists, `Optional`, `Annotated`). Invalid values return **422**.
- Missing required query params return **422** instead of a 500.
- `model=Model` validates JSON/form bodies; the model is injected into the
  matching parameter and available at `request.state.data`.
- `csrf=True`/`@csrf` accepts `X-CSRF-Token`, JSON `_csrf` or a form `_csrf`.
  Route `csrf=True` is checked before body validation.
- `cache=N` is **per identity** (cookie/Authorization fingerprint) and per
  concrete path + query; use `cache_public=True` only for public content.
- `q: Optional[str]` without a default receives `None` when missing.
- `auth=True` requires a session; API paths get 401, pages get a 303 redirect.

---

## 4. Database & Models

```python
from sqlalchemy import Column, Integer, String, func, TIMESTAMP
from lila.core.base_model import BaseModel

class Product(BaseModel):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    active = Column(Integer, nullable=False, default=1)
    created_at = Column(TIMESTAMP, server_default=func.now())
```

- Async: `insert_async`, `get_all_async(limit, offset, order_by, select=...)`,
  `get_by_id_async`, `update_async`, `delete_async`, `count_async`.
- `to_dict()` returns **only loaded columns** and skips `__private_fields__`.
- Set `__private_fields__ = ("password", "token")` on models with credentials.
- Sync methods work outside an event loop (persistent loop); inside async code use
  the `_async` variants.
- `lila migrate` creates tables **and adds missing columns**; `--refresh` drops
  tables (confirmation required unless `--yes`).
- Cache invalidation is per process and also sent to Redis when configured; the
  model read cache defaults to `MODEL_CACHE_TTL=5`. Cached reads are returned as
  copies (mutating a result never changes the cache).
- Filters, `order_by` and `select` accept only table columns; an unknown filter
  raises `ValueError`. `update_async` skips soft-deleted rows unless the payload
  sets the active field (`update_async(id, active=1)` restores).
- `router.rest_crud_generate(Model, auth=True, max_limit=500)` only writes table
  columns (never the primary key or `__private_fields__`).

---

## 5. Cache

- `CACHE_DRIVER=memory|redis|file`; Redis is used **only if reachable**, otherwise
  Lila logs once and falls back to memory.
- `Cache.stats()`, `incr/incr_async`, `clear(include_sessions=False)`.
- Route caches include the request identity, so authenticated pages do not leak.
- `Session` payloads over ~3 KB are stored server-side (Redis or memory) with a
  signed `sid:` cookie. The memory LRU evicts expired and non-session keys first.
- `Session.get` honours the `max_age` given to `Session.set` (stored in the signed
  cookie); pass `max_age` to `get` only to enforce a shorter lifetime.

---

## 6. Auth, Sessions & CSRF

- `SECRET_KEY` is mandatory. If it is empty/placeholder, Lila generates a
  persistent `.lila_secret` (0600) and warns; it never signs with an empty key.
- Cookies are signed, not encrypted: **never put passwords/tokens in a session**.
  `Session.set_async` strips password-like keys and `User.to_dict` hides
  `__private_fields__`.
- `secure` cookies are enabled automatically when `APP_URL` starts with `https://`.
- `login_required`, `session_active`, `admin_required`, `rate_limit`,
  `csrf_protect`, `validate_token` and `create_decorator` are exported from
  `lila.core.middleware`.
- Login attempts are locked after 5 failures for 5 minutes; login/register/reset
  have per-IP throttles.
- Password reset stores only the SHA-256 hash of the token and sends email when
  SMTP is configured; in debug the URL is printed to the console.
- Admin login uses the project database and an `admins` table created through
  migrations; `/debug` is only mounted with `debug=True, debug_html=True`.

---

## 7. Templates & Client

Page templates contain **only their HTML**. `render()` wraps them in the
default layout (`lila/base.jinja`) and builds the `<head>`:

```python
return render(
    request, "authenticated/dashboard", {"user": user},
    title="dashboard",                 # translation key or text -> "Dashboard - <TITLE_PROJECT>"
    description="Your panel",
    image="img/og.png", canonical=True, robots="noindex",
    jsonld={"@context": "https://schema.org", "@type": "WebPage"},
    meta={"theme-color": "#1a73e8"}, styles=["css/app.css"], scripts=["js/chart.js"],
    head='<link rel="preconnect" href="https://cdn.example">',   # raw, trusted
    layout=None,                       # None = default, "x/layout.jinja", False = fragment
)
```

```jinja
{# resources/html/authenticated/dashboard.jinja — no extends/blocks needed #}
<main class="max-w-7xl mx-auto p-8">
  <h1>{{ translate['welcome'] }}, {{ user.name }}!</h1>
  {{ datatable(rows, ["id", "name", ("email", "E-mail")], edit="onEdit") }}
  {{ carousel(slides, autoplay=5000) }}
</main>
```

- Precedence: `.env` defaults < `SEO_CONFIG`/`@seo` < `context` < `render()` kwargs.
  `TITLE_TEMPLATE="{title} - {project}"` formats `<title>`.
- A page may still declare `{% block head %}`/`{% block scripts %}`; they are moved
  to the layout. Templates with `{% extends %}` or `<html>` are not wrapped (v2.0.0
  templates keep working). Includes/macros are never wrapped.
- Custom layouts: `{% include "lila/head.jinja" %}` in `<head>`, `data-layout` on
  `<body>`, `[data-lila-outlet]` around `{% block content %}`.
- Head tags from `styles=`/`scripts=`/`jsonld=` carry `data-lila-head`; the SPA
  router swaps them (and `<html lang>`) on navigation and runs scripts in order.
- Every render sets a CSRF cookie and `<meta name="csrf-token">`; `Http()` reads it.
- `datatable(data | url=..., columns, id=None, rows_per_page, search, pagination,
  edit="fnName", delete="fnName", exclude=("password","token","hash"))` — unique
  id, rows embedded as escaped JSON (or loaded with `Http(url)`), auto-initialized.
- `carousel(slides, autoplay=0, loop=True, arrows=True, indicators=True,
  item_class="basis-full")` — scroll-snap, swipe, keyboard, pauses on hover.
- `lila-client.js`: View Transitions, prefetch, `data-persist`, toast/snackbar,
  command palette, drawer, tabs, carousel and `ResponsiveDataTable`. Page scripts
  re-run on SPA navigation: use `var`/functions (not top-level `let`/`const`) and
  call init code directly instead of `DOMContentLoaded`.
- `ws.js`: `lilaWS("/ws")` (relative URLs ok), auto reconnect with backoff, rooms,
  bounded offline queue; closed automatically when the SPA leaves the page unless
  `{ persist: true }`. Server side: `@hub.can_join` authorizes room joins.
- `/js/lila-client.js` and `/js/ws.js` are always served from the installed package.
- `data-partial-target` extracts the `[data-lila-outlet]` fragment.
- `Http(url, method, body, bodyForm, headers)` attaches CSRF, parses JSON/text and
  exposes `error.status`/`error.data`.
- Assets: `public()` maps `lila optimize` output and appends `?v=mtime`.

---

## 8. CLI

- `lila init` — scaffold; **never overwrites existing files/.env**.
- `lila dev` / `lila run` — read `.env` HOST/PORT; `run` supports `-w`.
  `lila dev` forces development mode and enables Jinja auto-reload plus an SSE
  watcher for templates/static/locales (works without `watchfiles`).
- `lila doctor`, `lila routes` — health and route introspection.
- `lila auth`, `lila admin`, `lila model`, `lila crud` — safe `main.py` patching
  (`lila/cli/_patch.py`) with backups for overwritten scaffold files.
- `lila migrate` — tables + columns; `--refresh --yes` to drop.
- `lila optimize` — manifest consumed by `public()`; requires `rjsmin`/`rcssmin`
  for JS/CSS (otherwise it skips instead of corrupting assets).
- `lila seo` — discovers public GET routes, writes `public/sitemap.xml` and
  `public/robots.txt`; served at the site root.
- `lila worker` — Redis JSON tasks (`LILA_TASK_MODULES` allowlist, retries,
  dead-letter queue).
- `lila deploy` — generates systemd app/worker units, Nginx static+proxy config
  and Windows Server starter scripts in `deploy/` (`SERVICE_NAME` from `.env`).
- `sudo "$(which lila)" deploy setup` — interactive Linux install: asks (S/N)
  to set `DEBUG=False`, `HOST=127.0.0.1`, a new `SECRET_KEY`, `APP_URL`; installs
  the systemd service, the Nginx site (rolled back if `nginx -t` fails) and
  Certbot HTTPS; health-checks the port. `--dry-run`, `--yes`.
- `lila backup` — online SQLite backup with retention; refuses non-SQLite DBs.
- `lila desktop dev/build` — bundles `main`, `app`, Lila templates/assets;
  binds to `127.0.0.1`, enforces `LILA_DESKTOP_TOKEN`, and stores data under the
  OS app-data directory when frozen.

---

## 9. Testing

```bash
python -m unittest discover -s tests -v
```

Tests cover routing/422, cache isolation, CSRF forms, sessions, seed secrets,
schema column additions, admin coercion, deploy/backup generation, the deploy
setup wizard, auto-layout templates and component helpers, WebSocketHub,
REST CRUD, locale parity, native metrics, desktop locking/bridge and safe
`main.py` patching.

---

## 10. Conventions

- Never use `bool(os.getenv("X"))`; use `ENV_CONFIG.get_bool` or `is_debug()`.
- Never search `main.py` with `find(")")`; use `lila.cli._patch.patch_main`.
- Never cache authenticated responses without an identity fingerprint.
- Never return `str(exc)` from database/admin endpoints to clients; log it.
- Never expose `password`, `token` or absolute upload paths in JSON.
- Docs must match code: examples are expected to run against the current API.
