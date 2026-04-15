# Lila Framework — Agent Reference

Lila is a high-performance Python web framework built on **Starlette** + **Pydantic** + **SQLAlchemy**. 
It is designed for rapid full-stack development, providing a library-based core (`lila.core`) and specialized CLI tools for project management.

## Project Structure (Standard)

When working on a Lila project, the local structure focuses on application logic, as the core is installed as a package:

```
project_root/
├── main.py                  # Entry point (uvicorn, app initialization)
├── .env                     # Configuration (DEBUG, SECRET_KEY, DB_CONFIG)
├── app/
│   ├── config.py            # Loads .env and defines project constants
│   ├── connections.py       # Database connection instances (from lila.core.database)
│   ├── helpers/             # Security, translations, file handling
│   ├── locales/             # i18n JSON files
│   ├── models/              # SQLAlchemy models (extending lila.core.database.Base)
│   └── routes/              # Route definitions and API endpoints
├── templates/               # Jinja2 HTML templates
└── public/                  # Static assets (css, js, images)
```

> **Note:** The framework engine (`lila.core`) and CLI logic (`lila.cli`) are installed in the virtual environment.

## Core Components (`lila.core`)

### Routing & Validation
- **`lila.core.routing.Router`**: Extends Starlette routing with Pydantic integration.
- **Auto-Validation**: When a `model` (Pydantic) is passed to a route, data is automatically validated and stored in `request.state.data`.
- **REST CRUD**: `router.rest_crud_generate()` automates full API + HTML view generation for any SQLAlchemy model.
- **Documentation**: Built-in `swagger_ui()` and `openapi_json()` support.

### Database Engine
- **`lila.core.database.Database`**: Unified interface for SQLite, MySQL, and PostgreSQL.
- **Hybrid Querying**: Supports both raw SQL (`db.query`) and ORM patterns (`db.query_orm`).
- **Auto-Provisioning**: Automatically creates the database if it doesn't exist (MySQL/PostgreSQL).

### Template Engine
- **`lila.core.templates.render`**: Standard Jinja2 rendering with auto-injected context (translations, meta tags).
- **React Islands**: `renderReact()` and `react()` helpers for embedding React components within HTML templates.
- **Markdown Support**: `renderMarkdown()` for converting `.md` files into themed documentation or pages.

### Security & Sessions
- **Sessions**: Signed cookie-based sessions using `itsdangerous` via `lila.core.session.Session`.
- **Admin Panel**: `lila.core.admin` provides a dashboard with system metrics (CPU/RAM via `psutil`), log viewing, and automatic model management.
- **Password Hashing**: Automatic `argon2` hashing for "password" fields in CRUD operations.

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
