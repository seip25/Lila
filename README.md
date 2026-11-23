<p align="center">
  <img src="https://raw.githubusercontent.com/seip25/Lila/main/lila/public/img/lila-256.webp" width="120" height="120" alt="Lila Framework">
</p>

<h1 align="center">Lila Framework v2.2.2</h1>

<p align="center">
  <b>Lightweight full-stack Python web & desktop framework</b><br>
  Starlette + Pydantic v2 + SQLAlchemy 2.0 Async + Jinja2 + a native View Transitions SPA.
</p>

<p align="center">
  <a href="https://pypi.org/project/lila-framework/"><img src="https://img.shields.io/pypi/v/lila-framework?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/lila-framework/"><img src="https://img.shields.io/pypi/dm/lila-framework" alt="Downloads"></a>
  <a href="https://seip25.github.io/Lila"><img src="https://img.shields.io/badge/docs-v2.2-emerald" alt="Documentation"></a>
  <a href="https://github.com/seip25/Lila/blob/main/LICENSE"><img src="https://img.shields.io/github/license/seip25/Lila" alt="License"></a>
</p>

---

## ⚡ What is Lila?

Lila is a small, batteries-included Python web framework for people who want the
speed of Starlette, the validation of Pydantic v2 and an SPA experience **without a
Node.js build step**. It is designed for 1–2 worker deployments on a cheap VPS:
SQLite WAL by default, an in-process LRU cache, optional Redis when it is actually
reachable, and a file cache fallback.

- 🪶 **Light on import**: `import lila` is lazy (~19 MB RSS). A full `App` is around
  42 MB on Python 3.14, and no SQLAlchemy is loaded unless you use models.
- 🚀 **SPA without Node.js**: `lila-client.js` uses the native View Transitions API,
  hover prefetching, persistent islands (`data-persist="true"`) and Tailwind UI
  components (toast, snackbar, command palette, drawer, tabs, carousel, DataTable).
- 🧩 **Templates without boilerplate**: a page is just its HTML. `render()` adds the
  layout, `<title>`, description, Open Graph, JSON-LD, icon, styles and scripts;
  `{{ datatable(...) }}` and `{{ carousel(...) }}` build components from Jinja, and
  `data-lila-form` / `data-action` send forms and buttons without page scripts.
- 💾 **Zero infrastructure by default**: Async SQLite with WAL, an in-memory LRU
  cache, and `CACHE_DRIVER="file"` for a persistent fallback. `CACHE_DRIVER="redis"`
  is used only when the Redis package is installed **and the server answers**;
  otherwise Lila logs once and falls back to memory.
- 🗄️ **Real migrations**: `lila migrate` creates tables, adds and renames columns
  and creates indexes; `--plan` shows the diff first and risky changes are only reported.
- ⏱️ **Background work without Redis**: `@task` queue and `@every`/`@cron` jobs on
  their own SQLite files, Jinja email templates, Server-Sent Events.
- 🔐 **Roles & permissions, API keys and rotating JWT refresh tokens** built in.
- 📈 **Lean in production**: `lila css build` (compiled Tailwind, no Node),
  precompressed static files, ETag/304, cache memory budget, Granian support,
  `lila bench`, protected `/health` and Prometheus `/metrics`.
- 🤖 **AI helper** (`core/ia.py`): OpenAI, DeepSeek and Gemini with explicit PII
  masking/restoration, prompt cache and per-IP rate limits.
- 🔐 **Auth 2.0**: cookie sessions without sensitive fields, Argon2id, CSRF for
  classic HTML forms, Google/GitHub/Discord OAuth, login lockout and email reset
  links (SMTP optional).
- 🛠️ **Admin 2.0**: CRUD, CSV export, cache purge, logs and honest telemetry.
- 🖥️ **Desktop mode**: `lila desktop dev` / `lila desktop build` (PyInstaller
  bundles `main` and the Lila templates/assets).
- 🌍 **Locales**: `en`, `es`, `pt` and `zh` built in, plus project overrides in
  `app/locales/*.json`.

> **Runtime requirement:** Python **3.10+** (Starlette 1.x and Uvicorn 0.54 require it).

---

## 📦 Installation

```bash
pip install lila-framework

# Optional:
pip install "lila-framework[redis]"       # Redis cache/worker
pip install "lila-framework[images]"      # WebP uploads
pip install "lila-framework[markdown]"    # render_markdown
pip install "lila-framework[metrics]"     # truthful admin telemetry
pip install "lila-framework[optimize]"    # rjsmin/rcssmin + Pillow
pip install "lila-framework[desktop]"     # pywebview + PyInstaller
pip install "lila-framework[s3]"          # S3 / R2 / MinIO uploads (boto3)
pip install "lila-framework[otel]"        # OpenTelemetry tracing
```

---

## 🚀 Quick Start

```bash
lila init        # scaffold main.py, app/, public/, resources/ and .env
lila init -t full -y   # or a template: web | react | auth | react-auth | full | desktop
lila dev         # http://127.0.0.1:8000 with reload + dev SSE
lila doctor      # check .env, SECRET_KEY, database, templates, public/
lila routes      # list registered routes of main:app
```

```python
# main.py
from app.config import DEBUG, HOST, PORT, WORKERS
from app.routes.web.index import router as web_router
from lila.core.app import App

app = App(
    routes=[web_router],
    debug=DEBUG,
    security=True,
    rate_limit=300,
    gzip=True,
    openapi=True,
    debug_html=DEBUG,   # mount /debug in debug mode
    csp=True,           # Content-Security-Policy with per-response nonces
)
```

With `csp=True` inline scripts need the nonce (`<script{{ nonce_attr }}>`) and
inline handlers become `data-onclick="fn"`; framework templates already comply.

### Routes with typed params

```python
from lila.core.routing import Router
from lila.core.request import Request
from pydantic import BaseModel, EmailStr

router = Router(prefix="/api")

class UserCreate(BaseModel):
    email: EmailStr
    name: str

@router.get("/users")
async def users(request: Request, page: int = 1, q: str | None = None):
    # page is a real int; invalid values return HTTP 422
    return {"page": page, "q": q}

@router.get("/users/{id:int}", cache=60, cache_public=True)
async def get_user(request: Request, id: int):
    return {"id": id}

@router.post("/users", model=UserCreate, csrf=True)
async def create_user(request: Request, data: UserCreate):
    return {"success": True, "email": data.email}
```

### Pages: just HTML, the layout is automatic

```python
from lila.core.templates import render

@router.get("/dashboard", auth=True)
async def dashboard(request: Request):
    user = request.state.user
    return render(
        request, "authenticated/dashboard", {"user": user, "orders": await Order.get_all_async()},
        title="dashboard",               # translation key -> "Dashboard - My App"
        description="Your orders",
        robots="noindex",
        jsonld={"@context": "https://schema.org", "@type": "WebPage", "name": "Dashboard"},
        scripts=["js/chart.js"],
    )
```

```jinja
{# resources/html/authenticated/dashboard.jinja — no extends, no blocks #}
<main class="max-w-7xl mx-auto px-4 py-8 space-y-6">
  <h1 class="text-3xl font-black">{{ translate['welcome'] }}, {{ user.name }}!</h1>
  {{ datatable(orders, ["id", ("total", "Total"), "status"], rows_per_page=10) }}
  {{ carousel([{"image": "img/promo.webp", "title": "Sale"}], autoplay=5000) }}
</main>
```

Templates written for 2.0.0 with `{% extends %}` keep working unchanged.

### Forms without JavaScript

```html
<form action="/api/contact" method="post" data-lila-form data-snackbar data-reset>
  <input name="email" type="email" required>
  <textarea name="text" required minlength="10"></textarea>
  <div data-message hidden></div>
  <button type="submit" data-loading-text="Sending...">Send</button>
</form>

<button data-action="/api/items/3" data-method="DELETE" data-confirm="Delete?" data-refresh="#items">Delete</button>
```

HTML5 validation, CSRF, disabled buttons with a spinner, messages from the API
(`success`, `message`/`msg`, 422 `errors` per field), redirects and table refreshes
are handled by `lila-client.js`.

Everyday UI without page scripts: `data-drawer` (left/right/top/bottom),
`data-dropdown`, `data-copy`, `data-confirm`, `data-toggle-class`, `data-remove`,
`data-password-toggle`, `data-filter`, `data-char-count`, `data-autosubmit`,
`data-tab-target`, `data-carousel`, `<time data-local-time>` — see the
[client docs](https://seip25.github.io/Lila/docs/client.html).

### Models and migrations

```python
from sqlalchemy import Column, Integer, String
from lila.core.base_model import BaseModel

class Product(BaseModel):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=False)
    active = Column(Integer, nullable=False, default=1)

# Async API
await Product.insert_async(name="Chair")
await Product.get_all_async(limit=50, order_by="name")
await Product.get_by_id_async(1, select="id,name")
await Product.update_async(1, name="Desk")
await Product.delete_async(1)  # soft delete when `active` exists
```

Run `lila migrate` after changing models; it adds missing columns. For destructive
changes use `lila migrate --refresh --yes` (asks for confirmation otherwise).

### Cache

```python
from lila.core.cache import Cache

await Cache.set_async("key", {"a": 1}, ttl=300)
data = await Cache.get_async("key")
await Cache.delete_async("key")
await Cache.clear_async(include_sessions=False)
```

`CACHE_DRIVER` accepts `memory` (default), `redis` or `file`. Redis is probed
lazily; if it is down Lila continues with the in-memory cache and logs once.

### AI with PII masking

```python
from lila.core.ia import IA

ai = IA(provider="gemini", rate_limit=20, rate_window=60, cache_ttl=3600)
result = await ai.ask(
    prompt="Draft a support reply for this customer:",
    data={"name": "Maria", "email": "maria@example.com", "ticket": "Cannot access invoice #402"},
    sensitive_keys=["name", "email"],
    request=request,
)
```

Set `OPENAI_API_KEY`, `DEEPSEEK_API_KEY` or `GEMINI_API_KEY`; override the model
with `OPENAI_MODEL`, `DEEPSEEK_MODEL` or `GEMINI_MODEL`.

### Auth + Admin

```bash
lila auth                 # login/register/reset/profile/dashboard + OAuth
lila admin -u admin -p ... # create/update the admin user
lila migrate
lila crud -m Product --react --auth   # React CRUD page (DataTable + form) + paginated API
lila admin --react                    # React admin panel
```

Admin lives at `/admin`; OAuth callbacks at `/auth/{provider}/callback`. Set
`APP_URL` and the provider credentials in `.env`. Password reset requires SMTP
(`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`) — in development the
reset URL is printed to the console instead.

### React (Vite)

```bash
lila react init --install   # TypeScript by default (--js for .jsx): package.json, vite.config.ts, resources/react/*
lila react dev              # Vite (HMR + React Fast Refresh) + Lila together
lila react build            # public/build + manifest — Node is NOT needed on the server
```

Pages per route with server props and full SEO (same keywords as `render()`):

```python
from lila.core.react import react_render

@router.get("/users/{id:int}")
async def user(request: Request, id: int):
    user = await User.get_by_id_async(id)
    return react_render(request, "Users/Show", {"user": user},
                        title=user["name"], description="Profile", canonical=True,
                        jsonld={"@context": "https://schema.org", "@type": "Person", "name": user["name"]})
```

`resources/react/pages/Users/Show.tsx` receives `user` as a prop
(`lila react types` writes TypeScript interfaces for your Pydantic schemas and
models; `useForm` handles CSRF and Lila's 422 errors per field); `<Link href>`
from `@lila` navigates without reloads (JSON page + `<head>` swap, back/forward,
asset-version reload). A React Router SPA with per-route meta:

```python
router.spa("/app", meta={
    "*": {"title": "App"},
    "users/:id": lambda request, params: {"title": f"User {params['id']}", "robots": "noindex"},
})
```

React auth (login, register, forgot/reset password, dashboard, profile) on the
same secure JSON endpoints as the Jinja version: `lila auth --react`.

A UI kit is copied into `resources/react/components/ui` (your code, Lila's
palette and `.btn-*`/`.card`/`.form-control` classes, dark mode shared with
Jinja): `Button`, `Form` + `Input`/`Select`/`Textarea`/`Checkbox`/`SubmitButton`
(422 errors per field), `Card`, `Badge`, `Modal`, `Drawer`, `Carousel`,
`Toaster`/`toast`, `ThemeToggle`, `Skeleton`, `ProgressBar` and `DataTable`
(local rows or `paginate_async` URLs). SPAs get `@lila/router`
(`createRouter`, lazy `page()`, `LilaHead`) and `@lila/auth` (`AuthProvider`,
`useAuth`, `RequireAuth roles=[...]`, `GuestOnly`) backed by `/api/auth/me`.

### Desktop

```bash
pip install "lila-framework[desktop]"
lila desktop dev
lila desktop build --name MyApp --onefile --windowed
lila desktop build --installer auto     # + dist/MyApp.dmg (macOS) or dist/MyApp.msi (Windows, WiX)
```

One codebase, two targets. Keep web-only features out of the desktop build:

```python
@router.post("/checkout", desktop=False)          # web only (payments, uploads, webhooks...)
billing = Router(prefix="/billing", desktop=False)
@router.get("/local-files", desktop="only")       # desktop app only
```

```bash
# .env: DESKTOP_EXCLUDE=/payments*,/upload*,name:stripe_webhook
lila desktop routes                       # preview + suggestions
lila desktop build --exclude "/payments*" --auto-exclude
```

Removed routes return 404, disappear from `/openapi.json`, and React `<Link>`
hides them (`<WebOnly>`, `<DesktopOnly>`, `useLila().isAvailable(href)`; Jinja:
`is_desktop()`, `route_available(path)`). `lila desktop build` runs
`lila react build` first when the project uses Vite.

The generated executable bundles `main`, `app`, Lila templates and `public/`.
Lila binds the desktop server to `127.0.0.1`, enforces a per-run local token,
prevents a second instance, stores its SQLite/cache/logs in the OS
application-data directory and automatically runs safe additive migrations
(`LILA_AUTO_MIGRATE=1`) on startup so new tables are ready on first launch.

Sign and auto-update desktop apps: `--sign-identity` (macOS, + notarization
with `--notary-profile`), `--sign-cert` (Windows, password in
`WINDOWS_SIGN_PASSWORD`), `--update-url https://…/latest.json` and
`lila desktop release`; in React `useDesktopUpdate()` and `desktop.notify(...)`
from `@lila/desktop`.

#### Desktop Bug Reports & Opt-in Anonymous Telemetry

Collect bug logs and opt-in diagnostics from desktop users without bloating your
app database (`desktop_reports` is **OFF** by default and mounts `desktop=False`
web-only endpoints):

```python
# Web server (main.py)
app = App(
    routes=[web_router],
    desktop_reports=True,  # or {"prefix": "/api/desktop", "retention_days": 90, "rate_limit": (10, 60), "max_body_bytes": 262144}
)
```

```bash
# Desktop build / dev pointing at your server (.env: DESKTOP_REPORT_URL, DESKTOP_REPORT_TOKEN, DESKTOP_TELEMETRY_INTERVAL)
lila desktop build --name MyApp --onefile --windowed \
  --report-url "https://example.com/api/desktop" \
  --report-token "$DESKTOP_REPORT_TOKEN" \
  --telemetry-interval 3600
```

- **Isolated storage & deduplication**: stored in `app/desktop/database/reports.db`
  (SQLite WAL) with unique deduplication on `(kind, app_version, install_id, period_key, content_hash)`
  and automatic 90-day background retention pruning (`BackgroundTask`) on every upload.
- **Hardened & PII-safe**: enforces 256 KB streaming body caps (`413`), per-IP rate
  limits (`429`), optional `X-Lila-Report-Token` (`401`), Pydantic v2 validation (`422`),
  and automatic redaction of emails, tokens/secrets, and user home paths.
- **Native UI & React helpers**: configuring `--report-url` enables
  `Help → Report Bug / Issue...` (uploads recent AppData `logs/`) and the opt-in
  **Anonymous diagnostics** toggle in `File → Preferences...` (off by default in
  `desktop_preferences.json`), plus `@lila/desktop` helpers (`desktop.openBugReport()`,
  `desktop.sendBugReport()`, `desktop.setTelemetryOptIn()`, `desktop.getReportSettings()`).

### Real-time, storage and tracing

```tsx
import { useSSE, useWebSocket } from "@lila/realtime";
const orders = useSSE("/events/orders", { events: { "order:new": (o) => toast.success(`#${o.id}`) } });
const chat = useWebSocket("/ws/chat", { rooms: ["general"], events: { "chat:message": addMessage } });
```

```bash
# .env
STORAGE_DRIVER=s3          # upload() goes to S3 / R2 / MinIO (presigned or S3_PUBLIC_URL)
S3_BUCKET=my-bucket
OTEL_ENABLED=true          # OpenTelemetry spans: GET /items/{id}, SQL, tasks
```

---

## 🛠️ CLI Reference

| Command | Description |
| :--- | :--- |
| `lila init` | Scaffold a project without overwriting existing files. |
| `lila dev` | Uvicorn reload + Jinja/static SSE auto-reload (reads `.env` HOST/PORT). |
| `lila run -w 2` | Production server (`DEBUG=False` silences access logs unless `--access-log` / `--log-level` is passed); warns with memory cache and >1 worker. |
| `lila doctor` | Health check: Python, `.env`, SECRET_KEY, DB, templates, public/. |
| `lila routes` | List every route registered in `main:app`. |
| `lila auth` | Auth 2.0 scaffold (backups for overwritten files). |
| `lila admin` | Create/update admin user + link routes safely. |
| `lila model create` | Generate an ActiveRecord model. |
| `lila crud --model X [--react] [--auth]` | Paginated/searchable CRUD API + Jinja or React page. |
| `lila migrate` | Create tables and add missing columns. |
| `lila migrate rollback` | Undo the last migration batch (`--steps`, `--dry-run`). |
| `lila migrate --refresh --yes` | Drop and recreate (asks without `--yes`). |
| `lila optimize` | Minify JS/CSS (needs the optimize extra) + WebP images. |
| `lila secret-key` | Rotate `SECRET_KEY`. |
| `lila seo` | `public/sitemap.xml` + `robots.txt` (served at `/sitemap.xml`). |
| `lila worker` | Redis JSON task worker (`pip install lila-framework[redis]`). |
| `lila deploy` | Generate systemd + Nginx + Windows Server files in `deploy/`. |
| `lila css build` | Compiled, minified Tailwind CSS for production (no Node.js). |
| `lila bench URL` | Requests/s, latency percentiles and server RSS. |
| `lila tasks` / `lila schedule` | SQLite task queue and `@every`/`@cron` jobs. |
| `lila i18n check` | Translation keys missing per language. |
| `sudo "$(which lila)" deploy setup` | Interactive Linux install: `.env` for production, systemd, Nginx, Certbot HTTPS. |
| `lila backup` | Online, zero-downtime SQLite backup with retention. |
| `lila desktop dev/build` | Native window / PyInstaller executable (`--exclude`, `--auto-exclude`, `--installer dmg\|msi`, signing, `--update-url`, `--report-url`, `--report-token`, `--telemetry-interval`, auto-migrations on startup). |
| `lila desktop routes` | Which routes ship in the desktop app + web-only suggestions. |
| `lila react init/dev/build/types/status` | React + Vite (TypeScript): scaffold, HMR dev server, production build, TS types from models. |
| `lila auth --react` | Auth pages in React (TypeScript) instead of Jinja. |
| `lila react ui [--force]` | Add/update the React UI kit in an existing project. |
| `lila admin --react` | React admin panel (dashboard + CRUD of every model). |
| `lila desktop release` | `latest.json` (version, URLs, SHA-256) for in-app updates. |

`lila desktop` binds to `127.0.0.1`, enforces a generated local session token and
allows only one instance. The frozen build stores SQLite/cache/logs in the OS
application-data directory.

---

## 🧪 Tests

```bash
python -m unittest discover -s tests -v
```

---

## 📖 Documentation

Full guides and API reference: **https://seip25.github.io/Lila**

---

## 📄 License

MIT. See [LICENSE](LICENSE).

Security policy: [SECURITY.md](SECURITY.md) · Changelog: [CHANGELOG.md](CHANGELOG.md)
