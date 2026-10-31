<p align="center">
  <img src="https://raw.githubusercontent.com/seip25/Lila/main/lila/public/img/lila-256.webp" width="120" height="120" alt="Lila Framework">
</p>

<h1 align="center">Lila Framework v2.0.0</h1>

<p align="center">
  <b>Lightweight full-stack Python web & desktop framework</b><br>
  Starlette + Pydantic v2 + SQLAlchemy 2.0 Async + Jinja2 + a native View Transitions SPA.
</p>

<p align="center">
  <a href="https://pypi.org/project/lila-framework/"><img src="https://img.shields.io/pypi/v/lila-framework?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/lila-framework/"><img src="https://img.shields.io/pypi/dm/lila-framework" alt="Downloads"></a>
  <a href="https://seip25.github.io/Lila"><img src="https://img.shields.io/badge/docs-v2.0-emerald" alt="Documentation"></a>
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
- 💾 **Zero infrastructure by default**: Async SQLite with WAL, an in-memory LRU
  cache, and `CACHE_DRIVER="file"` for a persistent fallback. `CACHE_DRIVER="redis"`
  is used only when the Redis package is installed **and the server answers**;
  otherwise Lila logs once and falls back to memory.
- 🗄️ **Real migrations**: `lila migrate` creates missing tables **and adds missing
  columns**. `--refresh` now really drops tables and asks for confirmation.
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
```

---

## 🚀 Quick Start

```bash
lila init        # scaffold main.py, app/, public/, resources/ and .env
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
)
```

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
```

Admin lives at `/admin`; OAuth callbacks at `/auth/{provider}/callback`. Set
`APP_URL` and the provider credentials in `.env`. Password reset requires SMTP
(`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`) — in development the
reset URL is printed to the console instead.

### Desktop

```bash
pip install "lila-framework[desktop]"
lila desktop dev
lila desktop build --name MyApp --onefile --windowed
```

The generated executable bundles `main`, `app`, Lila templates and `public/`.
Lila binds the desktop server to `127.0.0.1`, enforces a per-run local token,
prevents a second instance and stores its SQLite/cache/logs in the OS
application-data directory.

---

## 🛠️ CLI Reference

| Command | Description |
| :--- | :--- |
| `lila init` | Scaffold a project without overwriting existing files. |
| `lila dev` | Uvicorn reload + Jinja/static SSE auto-reload (reads `.env` HOST/PORT). |
| `lila run -w 2` | Production server; warns when using memory cache with >1 worker. |
| `lila doctor` | Health check: Python, `.env`, SECRET_KEY, DB, templates, public/. |
| `lila routes` | List every route registered in `main:app`. |
| `lila auth` | Auth 2.0 scaffold (backups for overwritten files). |
| `lila admin` | Create/update admin user + link routes safely. |
| `lila model create` | Generate an ActiveRecord model. |
| `lila crud --model X` | CRUD API + HTML DataTable with CSRF. |
| `lila migrate` | Create tables and add missing columns. |
| `lila migrate --refresh --yes` | Drop and recreate (asks without `--yes`). |
| `lila optimize` | Minify JS/CSS (needs the optimize extra) + WebP images. |
| `lila secret-key` | Rotate `SECRET_KEY`. |
| `lila seo` | `public/sitemap.xml` + `robots.txt` (served at `/sitemap.xml`). |
| `lila worker` | Redis JSON task worker (`pip install lila-framework[redis]`). |
| `lila deploy` | Generate systemd + Nginx + Windows Server files in `deploy/`. |
| `lila backup` | Online, zero-downtime SQLite backup with retention. |
| `lila desktop dev/build` | Native window / PyInstaller executable. |

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
