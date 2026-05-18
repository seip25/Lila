# Lila Framework — Agent Reference

Lila is a high-performance Python web framework built on **Starlette** + **Pydantic** + **SQLAlchemy**.
Designed for rapid full-stack development with async support, ORM, templates, CLI scaffolding, and admin panel.

## Project Structure

```
lila/
├── main.py                  # App entry point (uvicorn, routes, middlewares)
├── core/                    # Framework core
│   ├── app.py               # App class (extends Starlette) + getenvironment helper
│   ├── routing.py           # Router with HTTP decorators, WebSocket, REST CRUD generation, OpenAPI/Swagger
│   ├── database.py          # Database class (SQLAlchemy: MySQL, PostgreSQL, SQLite)
│   ├── templates.py         # Jinja2 render, Markdown, templates utilities
│   ├── session.py           # Signed cookie sessions + async get/set/delete helpers
│   ├── auth.py              # JWT tokens (generate, verify), password hashing
│   ├── security.py          # XSS detection and data sanitization utilities
│   ├── files.py             # File upload and image optimization utilities
│   ├── responses.py         # JSONResponse (auto-serialize) + validation_error helper
│   ├── admin.py             # Admin panel (dashboard, metrics, model CRUD, log viewer)
│   ├── logger.py            # File-based Logger (error, warning, info) + request logging
│   ├── debug.py             # Debug middleware (RAM, CPU, execution time per request)
│   ├── translate.py         # Translate class (i18n loading, language detection, Pydantic error translation)
│   ├── middleware.py        # Re-export of Starlette Middleware
│   ├── controller.py        # RequestParser (body/query validation via Pydantic)
│   ├── request.py           # Re-export of Starlette Request
│   ├── utils.py             # General utilities (date conversion, etc.)
│   └── background.py        # Re-export of Starlette BackgroundTask
├── app/
│   ├── config.py            # Environment config (.env): DEBUG, SECRET_KEY, paths, project meta
│   ├── connections.py       # Database connection instances
│   ├── locales/             # JSON translation files (i18n)
│   ├── middlewares/         # Custom middleware (security, logging, rate-limit)
│   ├── models/              # SQLAlchemy models
│   └── routes/              # Route definitions (routes.py, api.py, admin.py)
├── cli/                     # CLI tools (scaffold, model gen, migrations, auth, admin, React, minify)
│   ├── scaffold.py          # Create a new Lila project structure
│   ├── model.py             # Generate SQLAlchemy models from database tables
│   ├── migrations.py        # Manage database migrations (Alembic-based)
│   ├── auth.py              # Create database admin
│   ├── admin.py             # Create admin panel
│   ├── react.py             # Initialize Vite + Tailwind CSS v4 environment
│   └── minify.py            # Minify CSS/JS using rjsmin/rcssmin + HTML minify
├── resources/               # Frontend resources and Jinja2 templates (Unified)
│   ├── js/                  # JavaScript source files (e.g. main.js)
│   ├── html/                # HTML templates
│   └── markdown/            # Markdown files
└── public/                  # Static files (css, js, img)
```

## Core Concepts

### Routing (`core/routing.py`)

- `Router(prefix)`: Group routes under a prefix.
- Decorators: `@router.get("/")`, `@router.post("/")`, `@router.put("/")`, `@router.delete("/")`, `@router.patch("/")`, `@router.websocket("/ws")`.
- `router.route(path, methods, model)`: Generic route decorator with optional Pydantic model for OpenAPI docs.
- `router.rest_crud_generate(...)`: Auto-generates GET all, GET by id, POST, PUT, DELETE endpoints + HTML CRUD view.
- `router.swagger_ui()` / `router.openapi_json()`: Auto-generated API documentation.
- Path parameters: `/{id}` with type conversion.

### Pydantic (`app/routes/api.py`)
- Example data model using Pydantic. 
- Defines an "api/example" route, using ExampleModel for input validation, with automatic documentation passing the "model" parameter ("model=ExampleModel").
- Get request input in request.state.data
```python
from pydantic import BaseModel, EmailStr
from core.routing import Router
from core.responses import JSONResponse
from core.request import Request

router = Router()

class ExampleModel(BaseModel):
    email: EmailStr   .
    password: str  

 
@router.post(path="/example", model=ExampleModel)
async def login(request: Request):
    """Example function get request json form"""
    input =request.state.data 

    email = input.email
    password = input.password
    response = JSONResponse({"email": email, "password": password, "success": True})
    return response
```

### Database (`core/database.py`)

- `Database(config)`: Supports `sqlite`, `mysql`, `postgresql`/`psgr`. Auto-creates database if not exists.
- `db.connect()`: Establish connection.
- `db.query(query, params, return_rows, return_row)`: Raw SQL queries.
- `db.query_orm(model, operation, instance, session, filters, values)`: ORM operations (select, insert, update, delete).
- `db.migrate(use_base)`: Run migrations.
- `Base`: SQLAlchemy declarative base for model definitions.

### Templates (`core/templates.py`)

- `render(request, template, context, files_translate, lang_default)`: Render Jinja2 HTML.
- `renderMarkdown(request, file, css_files, js_files)`: Render Markdown files as HTML pages.
- `hot_reload()`: Development hot reload scripts (Vite WS client). Injects scripts only if `DEBUG=True`.
- Templates auto-inject: `title`, `version`, `lang`, `translate`, `description`, `keywords`, `author`.

### Vite & Asset Pipeline (`resources/`)

- **Unified Frontend Builder**: Source stylesheets reside in `resources/css/` (e.g. `tailwind.css`) and source Javascript files in `resources/js/` (e.g. `utils.js`, `spa.js`).
- **Development Assets Serving**: In development (`DEBUG=True`), asset calls to `js/utils.js` or `css/tailwind.css` serve the source files from Vite's server (e.g. `http://localhost:5173/public/resources/js/utils.js`) with complete Hot Module Replacement (HMR).
- **Production Asset Bundling**: Running `npm run build` compiles, minifies, bundles, and hashes assets under `public/assets/`, generating a standard `manifest.json`. The framework dynamically reads the manifest file to serve hashed assets (e.g. `/assets/utils-CnU24iax.js`), ensuring caching and eliminating manual minification.
- **Dynamic Theme Switcher (Tailwind CSS v4)**: Theme preferences are saved in `localStorage` and set on the document element as `data-theme="dark"`. To support dynamic styling, a custom `@variant dark` is configured in `resources/css/tailwind.css`:
  ```css
  @variant dark (&:where([data-theme="dark"], [data-theme="dark"] *));
  ```
  This applies all `dark:` class utilities whenever `data-theme="dark"` is active, without requiring manual browser preference changes.

### Session (`core/session.py`)

- `Session.setSession(new_val, response, name_cookie, max_age, ...)`: Create signed cookie.
- `Session.unsign(key, request, max_age)`: Read and verify signed cookie.
- `Session.getSessionValue(request, key, max_age)`: Convenience wrapper for unsign.
- `Session.deleteSession(response, name_cookie)`: Remove session cookie.

### Memory Cache (`core/cache.py`)

- `Cache.set(key, value, ttl)`: Store a Python object in memory for `ttl` seconds.
- `Cache.get(key)`: Retrieve a cached object. Returns `None` if expired or not found.
- `Cache.delete(key)`: Remove a specific key from the cache.
- `Cache.clear()`: Clear all cached items.
- **Automatic Route Caching**: By default, `GET` routes are cached for 30 seconds.
- Internally used to optimize OpenAPI docs, Vite asset detection, and translations.

### App (`core/app.py`)

- `App(debug, routes, cors, middleware, compress_type, trusted_hosts, public_folder, on_startup, on_shutdown)`.
- Built-in 404/500 error pages (detailed trace in DEBUG mode).
- Compression: gzip (default) or zstd.
- Debug mode: adds DebugMiddleware + debug panel at `/debug`.

### Responses (`core/responses.py`)

- `JSONResponse(content, status_code, serialize, headers)`: Auto-serializes Decimal, datetime, Pydantic models.
- `HTMLResponse`, `RedirectResponse`, `PlainTextResponse`, `StreamingResponse`.
- **Automatic Headers**: All responses include `Powered-By: Lila Framework`.

### Security (`core/security.py` & `core/auth.py`)

- **Data Sanitization**: `Security.sanitize_data(data)` recursively cleans strings, dicts, and lists from XSS patterns.
- **XSS Detection**: `Security.check_xss(text)` identifies potential malicious scripts.
- **JWT Tokens**: `generate_token(name, value, minutes)`, `get_token(token)`, `get_user_id_by_token(request, key)`.
- **Password Hashing**: argon2 via `PasswordHasher`.
- **Automatic Protection**: `@router.route` automatically sanitizes incoming JSON bodies and checks query parameters for XSS.

### i18n (`lila/core/translate.py`)

- Translation files: `app/locales/*.json` with `{"key": {"en": "...", "es": "..."}` format.
- `Translate.t(key, request)`: Returns translated string for current language.
- Language set via session cookie (`lang`).

### CLI Commands

- `lila-init`: Initialize project structure.
- `lila-model`: Generate SQLAlchemy model.
- `lila-scaffold_crud`: Generate full REST CRUD + HTML interface.
- `lila-auth`: Scaffold authentication system.
- `lila-admin`: Generate admin panel.
- `lila-migrations`: Run database migrations.
- `lila-minify`: Minify CSS/JS for production.
- `lila-react`: Set up Vite + Tailwind CSS v4 environment.
- `lila-seo`: Generate sitemap.xml and robots.txt.

### SEO Optimization (`core/routing.py` & `cli/seo.py`)

- `@seo(title="...", description="...")`: Route decorator for injecting SEO metadata into `request.state.seo` and template context.
- **Multilingual support**: Pass dictionaries (e.g., `{"en": "Title", "es": "Título"}`) or use translation keys (`"translate:key"`).
- **Centralized configuration**: Map route paths to metadata in `app/seo.py`.
- **Auto-generate** `sitemap.xml` and `robots.txt` using the CLI.

## Key Patterns

### Adding a new route

```python
from core.routing import Router
from core.request import Request
from core.responses import JSONResponse

router = Router("api")

@router.get("/items")
async def get_items(request: Request):
    return JSONResponse({"items": []})
```

### Database query

```python
from app.connections import connection

items = connection.query("SELECT * FROM items WHERE active = 1", return_rows=True)
item = connection.query("SELECT * FROM items WHERE id = :id", params={"id": 1}, return_row=True)
```

### ORM operations

```python
session = connection.get_session()
new_id = connection.query_orm(model=Item, operation="insert", instance=Item(name="x"), session=session)
items = connection.query_orm(model=Item, operation="select", filters={"active": 1})
connection.query_orm(model=Item, operation="update", filters={"id": 1}, values={"name": "y"})
connection.query_orm(model=Item, operation="delete", filters={"id": 1})
```

### Template rendering

```python
from core.templates import render
return render(request=request, template="pages/home", context={"items": items})
```

### Session usage

```python
from core.session import Session
# New simplified async helpers:
await Session.set(request, response, data={"user_id": 1}, key="auth")
data = await Session.get(request, key="auth")
await Session.delete(response, key="auth")

# Or using the classic static methods:
Session.setSession(new_val={"user_id": 1}, response=response, name_cookie="auth")
data = Session.unsign(key="auth", request=request, max_age=3600)
```

## Configuration (`.env`)

```
SECRET_KEY=your-secret-key
DEBUG=True
PORT=8001
HOST=127.0.0.1
TITLE_PROJECT=My App
LANG_DEFAULT=en
```

## Important Notes

- All route handlers are `async` functions receiving a Starlette `Request` object.
- Pydantic models are used for validation in `rest_crud_generate` and `RequestParser`.
- Passwords are auto-hashed with argon2 when `password` field is present in CRUD operations.
- `delete_old_logs(days=30)` runs on startup via `on_startup` lifecycle event.
- Production: set `DEBUG=False`, enable `trusted_hosts`, configure CORS properly.


---

### CLI commands (newly added)

#### Initialize project structure
```bash
lila-init
```

#### Generate SQLAlchemy models from database
```bash
lila-model
```

#### Generate CRUD REST API + HTML interface
```bash
lila-scaffold_crud
```

#### Create authentication system
```bash
lila-auth
```

#### Create admin panel
```bash
lila-admin
```

#### Run database migrations
```bash
lila-migrations
```

#### Minify CSS/JS and HTML
```bash
lila-minify
```

#### Set up Vite + Tailwind CSS v4 environment
```bash
lila-react
```

#### Generate SEO Sitemap & Robots
```bash
lila-seo sitemap --domain https://yourdomain.com
lila-seo robots --domain https://yourdomain.com
```


