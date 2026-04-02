# Lila Framework — Agent Reference

Lila is a high-performance Python web framework built on **Starlette** + **Pydantic** + **SQLAlchemy**.
Designed for rapid full-stack development with async support, ORM, templates, CLI scaffolding, and admin panel.

## Project Structure

```
lila/
├── main.py                  # App entry point (uvicorn, routes, middlewares)
├── core/                    # Framework core
│   ├── app.py               # App class (extends Starlette) with error handling, CORS, compression
│   ├── routing.py           # Router with HTTP decorators, WebSocket, REST CRUD generation, OpenAPI/Swagger
│   ├── database.py          # Database class (SQLAlchemy: MySQL, PostgreSQL, SQLite)
│   ├── templates.py         # Jinja2 render, React Islands (renderReact), Markdown, Vite assets
│   ├── session.py           # Signed cookie sessions via itsdangerous
│   ├── responses.py         # JSONResponse (auto-serialize), HTMLResponse, RedirectResponse, StreamingResponse
│   ├── admin.py             # Admin panel (dashboard, metrics, model CRUD, log viewer)
│   ├── logger.py            # File-based Logger (error, warning, info) + request logging
│   ├── debug.py             # Debug middleware (RAM, CPU, execution time per request)
│   ├── translate.py         # Translate class (set/get language via session)
│   ├── middleware.py         # Re-export of Starlette Middleware
│   ├── controller.py        # RequestParser (body/query validation via Pydantic)
│   ├── request.py           # Re-export of Starlette Request
│   └── background.py        # Re-export of Starlette BackgroundTask
├── app/
│   ├── config.py            # Environment config (.env): DEBUG, SECRET_KEY, paths, project meta
│   ├── connections.py       # Database connection instances
│   ├── helpers/
│   │   ├── security.py      # JWT tokens (generate, verify), password hashing (argon2)
│   │   ├── translate.py     # Translation loading from JSON, language detection
│   │   ├── files.py         # File upload utilities
│   │   ├── validate.py      # Validation helpers
│   │   └── env.py           # Environment helpers
│   ├── locales/             # JSON translation files (i18n)
│   ├── middlewares/         # Custom middleware (security, logging, rate-limit)
│   ├── models/              # SQLAlchemy models
│   └── routes/              # Route definitions (routes.py, api.py, admin.py)
├── cli/                     # CLI tools (scaffold, model gen, migrations, auth, admin, React, minify)
├── templates/               # Jinja2 HTML templates
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

### Database (`core/database.py`)

- `Database(config)`: Supports `sqlite`, `mysql`, `postgresql`/`psgr`. Auto-creates database if not exists.
- `db.connect()`: Establish connection.
- `db.query(query, params, return_rows, return_row)`: Raw SQL queries.
- `db.query_orm(model, operation, instance, session, filters, values)`: ORM operations (select, insert, update, delete).
- `db.migrate(use_base)`: Run migrations.
- `Base`: SQLAlchemy declarative base for model definitions.

### Templates (`core/templates.py`)

- `render(request, template, context, files_translate, lang_default)`: Render Jinja2 HTML.
- `renderReact(request, component, props, options)`: Render React component as island with SSR-friendly output.
- `renderMarkdown(request, file, css_files, js_files)`: Render Markdown files as HTML pages.
- `react(component, props)`: Generate React mount point div.
- `vite_assets()`: Dev (hot reload) or production (manifest) Vite asset tags.
- Templates auto-inject: `title`, `version`, `lang`, `translate`, `description`, `keywords`, `author`.

### Session (`core/session.py`)

- `Session.setSession(new_val, response, name_cookie, max_age, ...)`: Create signed cookie.
- `Session.unsign(key, request, max_age)`: Read and verify signed cookie.
- `Session.getSessionValue(request, key, max_age)`: Convenience wrapper for unsign.
- `Session.deleteSession(response, name_cookie)`: Remove session cookie.

### App (`core/app.py`)

- `App(debug, routes, cors, middleware, compress_type, trusted_hosts, public_folder, on_startup, on_shutdown)`.
- Built-in 404/500 error pages (detailed trace in DEBUG mode).
- Compression: gzip (default) or zstd.
- Debug mode: adds DebugMiddleware + debug panel at `/debug`.

### Responses (`core/responses.py`)

- `JSONResponse(content, status_code, serialize, headers)`: Auto-serializes Decimal, datetime, Pydantic models.
- `HTMLResponse`, `RedirectResponse`, `PlainTextResponse`, `StreamingResponse`.

### Security (`app/helpers/security.py`)

- `generate_token(name, value, minutes)`: JWT token generation.
- `get_token(token)`: Decode JWT from Authorization header.
- `get_user_by_token(request, key)`: Extract user ID from authorization token.
- Password hashing: argon2 via `PasswordHasher`.

### i18n (`app/helpers/translate.py`)

- Translation files: `app/locales/*.json` with `{"key": {"en": "...", "es": "..."}` format.
- `translate(file_name, request)`: Returns translated dict for current language.
- Language set via session cookie (`lang`).

### CLI Commands

- `lila-init`: Initialize project structure.
- `lila-model`: Generate SQLAlchemy model.
- `lila-scaffold_crud`: Generate full REST CRUD + HTML interface.
- `lila-auth`: Scaffold authentication system.
- `lila-admin`: Generate admin panel.
- `lila-migrations`: Run database migrations.
- `lila-minify`: Minify CSS/JS for production.
- `lila-react`: Set up React + Vite integration.

## Key Patterns

### Adding a new route

```python
from lila.core.routing import Router
from lila.core.request import Request
from lila.core.responses import JSONResponse

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
from lila.core.templates import render
return render(request=request, template="pages/home", context={"items": items})
```

### Session usage

```python
from lila.core.session import Session
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
