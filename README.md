<p align="center">
  <img src="https://raw.githubusercontent.com/seip25/Lila/main/lila/public/img/lila.png" width="120" height="120" alt="Lila Framework">
</p>

<h1 align="center">Lila Framework v2.0.0</h1>

<p align="center">
  <b>Ultra-Lightweight (<40MB RAM) Full-Stack Python Web & Desktop Framework</b><br>
  Built with Starlette + Pydantic v2 + SQLAlchemy 2.0 Async + Jinja2 + Native View Transitions SPA.
</p>

<p align="center">
  <a href="https://pypi.org/project/lila-framework/"><img src="https://img.shields.io/pypi/v/lila-framework?color=blue" alt="PyPI"></a>
  <a href="https://pypi.org/project/lila-framework/"><img src="https://img.shields.io/pypi/dm/lila-framework" alt="Downloads"></a>
  <a href="https://seip25.github.io/Lila"><img src="https://img.shields.io/badge/docs-v2.0.0-emerald" alt="Documentation"></a>
  <a href="https://github.com/seip25/Lila/blob/main/LICENSE"><img src="https://img.shields.io/github/license/seip25/Lila" alt="License"></a>
</p>

---

## ⚡ What is Lila v2.0?

Lila v2.0 is re-architected from the ground up for modern Python developers. It bridges the gap between pure API frameworks (FastAPI) and heavy monolithic frameworks (Django, Next.js):

- 🪶 **Ultra-Lightweight (<40MB RAM)**: Pure ASGI pipeline built on top of Starlette and Uvicorn.
- 🚀 **SPA Experience without Node.js (`lila-client.js`)**: Real client-side navigation powered by the native browser **View Transitions API**, prefetching on hover, persistent islands (`data-persist="true"`), and reactive Tailwind UI components (`toast`, `snackbar`, `ResponsiveDataTable`, `command`, `drawer`, `tabs`, `carousel`).
- 💾 **Zero-Infrastructure by Default**: Out-of-the-box **SQLite Async (WAL mode)** + **In-Memory LRU Cache**. Run 95% of real-world apps with zero external database or caching servers, with seamless scaling to **Redis, PostgreSQL, or MySQL** via `.env` configuration.
- 🤖 **AI-First Integration (`core/ia.py`)**: Unified helper for **OpenAI**, **DeepSeek**, and **Gemini** featuring **Automatic PII Masking** (anonymizing emails, phones, and IDs to `[email_01]` and restoring them on response), **Prompt Cache Hits**, and configurable **Rate Limiting**.
- 🖥️ **Web to Desktop in 1 Command (`lila desktop`)**: Run your application inside a native OS window via `pywebview` or standalone App Mode consuming <25MB RAM, and compile single-file `.exe` binaries with PyInstaller.
- 🔐 **Better Auth OAuth 2.0 (`core/oauth.py`)**: Instant login with Google, GitHub, and Discord including official inline SVG buttons, 1-line router mounting, and Argon2 password hashing.
- 🔌 **Simplified WebSockets (`core/websocket.py`)**: Declarative event listeners (`@ws.on(...)`), room management, and broadcasting in 3 lines of code.
- 🛠️ **Unified Admin 2.0 (`core/admin.py`)**: Interactive CRUD management, live memory/CPU telemetry, cache clearing, and CSV export.

---

## 📦 Quick Installation

Install Lila Framework v2.0 with pip:

```bash
pip install lila-framework
```

Optional extras:
```bash
# Redis cache & task queue
pip install "lila-framework[redis]"

# Desktop mode (pywebview & PyInstaller)
pip install "lila-framework[desktop]"

# PostgreSQL / MySQL drivers
pip install "lila-framework[postgres]"
pip install "lila-framework[mysql]"

# Image WebP optimization
pip install "lila-framework[images]"
```

---

## 🚀 Getting Started

### 1. Initialize a new project:
```bash
lila init
```

### 2. Start the development server with hot-reload:
```bash
lila dev
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) to see your application running with instant SPA transitions.

---

## 💡 Code Examples

### 1. Minimal Application (`main.py`)
Middlewares are pure ASGI and 100% optional:

```python
from app.config import DEBUG, HOST, PORT
from app.routes.web.index import router as web_router
from app.routes.api.index import router as api_router
from lila.core.app import App

app = App(
    routes=[web_router, api_router],
    debug=DEBUG,
    security=True,       # Security headers & path shield
    rate_limit=300,      # 300 requests/min per IP (None to disable)
    cors=True,           # Enable CORS
)
```

### 2. Modern Route with Pydantic v2 & Auto-Casting
```python
from lila.core.routing import Router
from lila.core.request import Request
from pydantic import BaseModel, EmailStr

router = Router(prefix="/api")

class RegisterSchema(BaseModel):
    name: str
    email: EmailStr

@router.post("/register")
async def register(request: Request, data: RegisterSchema):
    # Dicts are automatically returned as JSONResponse with orjson
    return {"success": True, "email": data.email}

@router.get("/users/{id}", cache=60) # Caches response for 60 seconds
async def get_user(request: Request, id: int):
    # Path parameter 'id' is automatically cast to integer
    return {"user_id": id}
```

### 3. AI Helper with Sensitive Data (PII) Masking
```python
from lila.core.ia import IA

ai = IA(provider="gemini", rate_limit=20, rate_window=60, cache_ttl=3600)

result = await ai.ask(
    prompt="Generate a polite support reply for this customer issue:",
    data={
        "name": "Maria Garcia",
        "email": "maria@example.com",
        "ticket": "Cannot access invoice #402"
    },
    sensitive_keys=["name", "email"], # Replaced by [name_01] and [email_01] before sending
    request=request
)
# result["text"] -> Automatically restored with original name and email!
```

### 4. Native Desktop Application
```bash
# Run locally in a native desktop window
lila desktop dev

# Compile standalone executable (.exe)
lila desktop build --name "MyDesktopApp"
```

---

## 🛠️ Unified CLI Reference

Lila v2.0 includes a comprehensive CLI:

| Command | Description |
| :--- | :--- |
| `lila init` | Scaffolds a new project without external infrastructure. |
| `lila dev` | Starts Uvicorn server with hot-reload and dev SSE sync. |
| `lila desktop dev` | Runs web application inside an ultra-lightweight native window. |
| `lila desktop build` | Compiles standalone executable using PyInstaller. |
| `lila auth` | Scaffolds Auth 2.0 with Better Auth OAuth buttons and dashboard. |
| `lila admin` | Sets up Admin 2.0 panel and administrator credentials. |
| `lila model` | Generates ActiveRecord models with CRUD boilerplate. |
| `lila crud` | Scaffolds complete CRUD routes, schemas, and DataTable view. |
| `lila migrate` | Synchronizes SQLAlchemy models with the database. |
| `lila optimize` | Minifies JS/CSS and optimizes images to WebP. |
| `lila secret-key` | Rotates cryptographic SECRET_KEY in `.env`. |
| `lila seo` | Generates `sitemap.xml` and `robots.txt`. |
| `lila worker` | Runs background Redis task worker. |

---

## 📖 Documentation

Comprehensive guides, tutorials, and API reference:  
👉 **[https://seip25.github.io/Lila](https://seip25.github.io/Lila)**

---

## 📄 License

Lila Framework is open-source software licensed under the [MIT License](LICENSE).
