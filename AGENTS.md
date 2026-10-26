# Lila Framework v2.0.0 — Agent & Developer Reference

Lila is an ultra-lightweight (<40MB RAM), high-performance full-stack Python web framework built on **Starlette** + **Pydantic v2** + **SQLAlchemy 2.0 Async** + **Jinja2**.

Designed for zero-infrastructure out of the box (SQLite WAL mode + In-Memory LRU Cache), an SPA user experience without a Node.js build step via **View Transitions API** (`lila-client.js`), native AI integration (`core/ia.py`) with reversible PII masking, and 1-command desktop builds (`lila desktop`).

---

## 1. Project Directory Structure

```text
Lila/
├── pyproject.toml           # Packaging, dependencies, CLI entry points
├── README.md                # Main repository README
├── AGENTS.md                # Developer & agent guide
├── MANIFEST.in
├── implementation.md        # Master implementation plan
├── lila/                    # Package source and scaffold files
│   ├── main.py              # Clean application entrypoint
│   ├── .env_example         # Environment template
│   ├── core/                # Framework core modules (22 modules)
│   │   ├── app.py           # App ASGI wrapper, dev-reload SSE & OpenAPI 3.0
│   │   ├── routing.py       # Router with auto-responses, Pydantic v2 & dependency injection
│   │   ├── cache.py         # In-Memory LRU+TTL and Redis drivers
│   │   ├── database.py      # Async SQLite WAL mode & optional MySQL/PostgreSQL
│   │   ├── base_model.py    # ActiveRecord CRUD & single-flight deduplication
│   │   ├── ia.py            # AI Helper (OpenAI, DeepSeek, Gemini, PII Masking, Cache Hit)
│   │   ├── oauth.py         # Better Auth OAuth (Google, GitHub, Discord + inline SVGs)
│   │   ├── websocket.py     # Simplified WebSocketHub with rooms and events
│   │   ├── admin.py         # Admin 2.0 CRUD endpoints, CSV export, telemetry
│   │   ├── templates.py     # Jinja2 renderer with X-Lila-Partial and asset helpers
│   │   ├── middleware.py    # Pure ASGI Middlewares & route decorators
│   │   ├── session.py       # Cookie and cache sessions
│   │   ├── auth.py          # JWT and PasswordHasher (Argon2 / scrypt)
│   │   ├── security.py      # XSS sanitization and path traversal protection
│   │   ├── csrf.py          # CSRF tokens with itsdangerous
│   │   ├── translate.py     # O(1) in-memory Pydantic v2 error localization
│   │   ├── files.py         # Async upload and WebP optimization
│   │   ├── mailer.py        # Async & background SMTP
│   │   ├── exporter.py      # Zero-dependency CSV exporter
│   │   ├── background.py    # Memory & Redis tasks
│   │   ├── debug.py         # Memory-only telemetry
│   │   ├── logger.py        # Non-blocking stream-safe logger
│   │   └── config.py        # ConfigLoader & sys._MEIPASS compatibility
│   ├── cli/                 # Unified CLI commands
│   ├── public/              # Static assets (lila-client.js, tailwind.js, ws.js)
│   └── resources/           # Builtin Jinja2 templates (lila/, admin/, index.jinja)
└── docs/                    # GitHub Pages documentation site
```

---

## 2. Core Concepts & Usage

### 2.1. Application Entrypoint (`main.py`)
Middlewares and features are **100% optional** parameters passed directly to `App(...)`:

```python
from app.config import DEBUG, HOST, PORT, JIT, WORKERS
from app.routes.web.index import router as web_router
from app.routes.api.index import router as api_router
from app.routes.admin.index import router as admin_router
from lila.core.app import App

app = App(
    routes=[web_router, api_router, admin_router],
    debug=DEBUG,
    security=True,       # Security headers & path traversal protection
    rate_limit=300,      # Max 300 requests/minute per IP (None to disable)
    logging=False,       # Set True to log HTTP requests in app/logs/
    cors=True,           # Enable CORS (True or dict with configuration)
    openapi=True,        # Mount /openapi.json and /docs (Swagger UI)
)
```

### 2.2. Routing & Controllers (`core/routing.py`)
Automatic return formatting and type casting:
- Returning `dict` or `list` automatically returns `JSONResponse` via `orjson`.
- Returning `str` returns `HTMLResponse`.
- Path and query parameters are automatically cast according to function signature:

```python
from lila.core.routing import Router
from lila.core.request import Request
from pydantic import BaseModel, EmailStr

router = Router(prefix="/api")

class UserCreate(BaseModel):
    email: EmailStr
    name: str

@router.get("/users/{id}")
async def get_user(request: Request, id: int, page: int = 1):
    return {"id": id, "page": page}

@router.post("/users", model=UserCreate, rate_limit=(10, 60))
async def create_user(request: Request, data: UserCreate):
    return {"success": True, "email": data.email}
```

### 2.3. SPA View Transitions & UI Components (`lila-client.js`)
Lila provides a zero-build-step client runtime loaded in `lila/base.jinja`:
- Elements inside `<div id="lila-outlet" data-lila-outlet>` smoothly transition with native browser **View Transitions API**.
- Elements marked `data-persist="true"` (like audio players or the Admin sidebar) retain their DOM state across navigations.
- Interactive Tailwind UI components:
  - **Toast**: `lila('toast', { title: 'Saved', description: 'Changes saved', type: 'success' })`
  - **Snackbar**: `lila('snackbar', { message: 'Item deleted', type: 'info' })`
  - **ResponsiveDataTable**: `new ResponsiveDataTable('containerId', { data: [...], columns: [...] })`
  - **Command Palette**: Press `Ctrl+K` or call `lila('command', { action: 'toggle' })`
  - **Drawer**: `lila('drawer', { id: 'sidebar', action: 'toggle' })`
  - **HTTP helper**: `await Http(url, method, body)` (automatically attaches CSRF token and invalidates prefetch cache).

### 2.4. Zero-Infrastructure Database & Models (`core/database.py` & `core/base_model.py`)
- SQLite Async with **WAL Mode** enabled by default:
  ```sql
  PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA cache_size=-20000;
  ```
- Easy scaling to PostgreSQL or MySQL via `DB_TYPE="postgresql"` or `DB_TYPE="mysql"` in `.env`.
- `BaseModel` provides async and sync ActiveRecord methods with automatic cache invalidation:
  - `await Model.get_all_async(select="id,name", limit=100)`
  - `await Model.get_by_id_async(id)`
  - `Model.insert(db, params)`
  - `Model.update(db, id, params)`
  - `Model.delete(db, id)` (soft delete if `active` column exists)
  - `item.to_dict()`

### 2.5. Cache with Drivers (`core/cache.py`)
Configurable via `.env` (`CACHE_DRIVER=memory` or `CACHE_DRIVER=redis`) or programmatically:
```python
from lila.core.cache import Cache, cached

# In-Memory LRU + TTL by default
Cache.set("key", {"value": 123}, ttl=300)
data = Cache.get("key")

# Async methods
await Cache.set_async("user:1", profile_data, ttl=600)
user = await Cache.get_async("user:1")

# Route caching
@router.get("/products", cache=120)
async def list_products(request: Request):
    return await Product.get_all_async()
```

### 2.6. AI Integration with PII Masking (`core/ia.py`)
Unified client for **OpenAI**, **DeepSeek**, and **Gemini**:
- Reads API keys automatically from `.env` (`OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `GEMINI_API_KEY`).
- **Sensitive Data (PII) Masking**: Replaces sensitive keys (e.g. email, phone, dni) with `[email_01]` before sending to the LLM, and restores original values upon receiving the response.
- **Prompt Cache Hit**: Repeated queries return in 0ms without hitting the external provider.
- **Rate Limiting**: Throttles abuse per IP or user.

```python
from lila.core.ia import IA

ai = IA(provider="gemini", rate_limit=15, rate_window=60, cache_ttl=3600)

result = await ai.ask(
    prompt="Draft a friendly email response to this customer:",
    data={"name": "Alex Rivera", "email": "alex@example.com", "plan": "Pro"},
    sensitive_keys=["name", "email"],
    request=request
)
# result["text"] -> Restored with original name and email
```

### 2.7. Better Auth OAuth 2.0 (`core/oauth.py`)
Out-of-the-box support for **Google**, **GitHub**, and **Discord**:
- Official inline SVG vector icons included automatically.
- 1-line mounting in router:
  ```python
  from lila.core.oauth import OAuth
  OAuth.mount_routes(router)
  ```
- Jinja template button helper:
  ```html
  {{ oauth_buttons() | safe }}
  ```

### 2.8. Simplified WebSockets (`core/websocket.py`)
Declarative events and room management:
```python
from lila.core.websocket import ws

router.ws_hub("/ws", ws)

@ws.on("chat:send")
async def on_message(websocket, data):
    await ws.broadcast("chat:message", {"user": data["user"], "text": data["text"]}, room=data.get("room"))
```

### 2.9. Desktop Applications (`cli/desktop.py`)
Run and compile any Lila application as a native desktop program consuming <25MB RAM:
```bash
# Run locally in a native desktop window (pywebview or Chromium App Mode)
lila desktop dev

# Build standalone executable (.exe / binary)
lila desktop build
```

---

## 3. CLI Commands Reference

- `lila init` / `lila-init`: Initialize a new project.
- `lila dev` / `lila-dev`: Start local development server with hot-reload.
- `lila desktop dev` / `lila-desktop`: Run as desktop application.
- `lila desktop build`: Compile standalone desktop executable.
- `lila auth` / `lila-auth`: Scaffold Auth 2.0 with Better Auth OAuth buttons.
- `lila admin` / `lila-admin`: Setup Admin 2.0 and create administrator credentials.
- `lila model` / `lila-model`: Scaffold SQLAlchemy models interactively.
- `lila crud` / `lila-crud`: Generate complete CRUD scaffold with ResponsiveDataTable.
- `lila migrate` / `lila-migrations`: Run database migrations.
- `lila optimize` / `lila-optimize`: Minify JS/CSS and convert images to WebP.
- `lila secret-key` / `lila-secret-key`: Rotate SECRET_KEY in `.env`.
- `lila seo` / `lila-seo`: Generate `public/sitemap.xml` and `public/robots.txt`.
- `lila worker` / `lila-worker`: Run Redis background task worker.
