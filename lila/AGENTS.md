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
│   ├── base_model.py        # BaseModel class (ORM CRUD boilerplate, soft delete, relation helpers)
│   ├── templates.py         # Jinja2 render, Markdown, templates utilities
│   ├── session.py           # Signed cookie sessions + async get/set/delete helpers
│   ├── auth.py              # JWT tokens (generate, verify), password hashing
│   ├── security.py          # XSS detection and data sanitization utilities
│   ├── csrf.py              # CSRF token generation and verification
│   ├── files.py             # File upload and image optimization utilities
│   ├── responses.py         # JSONResponse (auto-serialize) + validation_error helper
│   ├── admin.py             # Admin panel (dashboard, metrics, model CRUD, log viewer)
│   ├── logger.py            # File-based Logger (error, warning, info) + request logging
│   ├── debug.py             # Debug middleware (RAM, CPU, execution time per request)
│   ├── translate.py         # Translate class (i18n loading, language detection, Pydantic error translation)
│   ├── middleware.py        # Route decorators and global HTTP middlewares
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
from lila.core.routing import Router
from lila.core.responses import JSONResponse
from lila.core.request import Request

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

### Base Model (`core/base_model.py`)

- `BaseModel`: Class inheriting from `Base`. Models should inherit from `BaseModel` for automatic ActiveRecord CRUD methods, soft-delete configuration, and relationship helpers.
- Configuration variables on `BaseModel` subclasses:
  - `_delete_logic` (bool, default `True`): Soft delete instead of hard delete.
  - `_active_field` (str, default `"active"`): Field name for indicating active status (value 1).
  - `_primary_key` (str, default `"id"`): Primary key column name.
- Class Methods:
  - `BaseModel.get_all(select=None, limit=1000, **filters)`: Returns active list of dicts.
  - `BaseModel.get_by_id(db, id)`: Returns record by ID.
  - `BaseModel.insert(db, params)`: Inserts a record.
  - `BaseModel.update(db, id, data)`: Updates record by ID.
  - `BaseModel.delete(db, id)`: Deletes (or soft-deletes) record by ID.
  - `BaseModel.get_all_without_orm(select=None, limit=1000, **filters)`: Performance raw SQL fetch.
  - `BaseModel.get_by_id_without_orm(id, select=None)`: Raw SQL fetch single record.
- Instance Methods:
  - `instance.get_related(model_class, foreign_key_field=None)`: Safely fetches related one-to-one/many-to-one record.
  - `instance.get_related_many(model_class, foreign_key_field=None, limit=1000)`: Safely fetches related one-to-many list.

### Templates (`core/templates.py`)

- `render(request, template, context, files_translate, lang_default, csrf)`: Render Jinja2 HTML. When `csrf=True`, generates a CSRF token, injects it as `csrf_token` in context, and sets the signed `_csrf` cookie on the response.
- `renderMarkdown(request, file, css_files, js_files)`: Render Markdown files as HTML pages.
- `csrf_input`: Jinja2 global helper. Returns `<input type="hidden" name="csrf" id="csrf" value="TOKEN" />`.
- Templates auto-inject: `title`, `version`, `lang`, `translate`, `description`, `keywords`, `author`.

### CDN & Style Delivery
- **CDN Styles Delivery**: By default, `asset('css/tailwind.css')` injects Outfit & Inter Google Fonts, Tailwind Play CDN browser-side compiler, theme config colors, and the Lila design system components stylesheet layer.
- **Dynamic Theme Switcher**: Dark and light themes are toggleable out-of-the-box using the custom styling component class layer which handles browser local storage preference state mapping.

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
- Internally used to optimize OpenAPI docs, templates, asset definitions, and translations.

### App (`core/app.py`)

- `App(debug, routes, cors, middleware, compress_type, trusted_hosts, public_folder, on_startup, on_shutdown)`.
- Built-in 404/500 error pages (detailed trace in DEBUG mode).
- Compression: gzip (default) or zstd.
- Debug mode: adds DebugMiddleware + debug panel at `/debug`.

### Responses (`core/responses.py`)

- `JSONResponse(content, status_code, serialize, headers)`: Auto-serializes Decimal, datetime, Pydantic models.
- `HTMLResponse`, `RedirectResponse`, `PlainTextResponse`, `StreamingResponse`.
- **Automatic Headers**: All responses include `Powered-By: Lila Framework`.

### Security (`core/security.py` & `core/auth.py` & `core/csrf.py`)

- **Data Sanitization**: `Security.sanitize_data(data)` recursively cleans strings, dicts, and lists from XSS patterns.
- **XSS Detection**: `Security.check_xss(text)` identifies potential malicious scripts.
- **JWT Tokens**: `generate_token(name, value, minutes)`, `get_token(token)`, `get_user_id_by_token(request, key)`.
- **Password Hashing**: argon2 via `PasswordHasher`.
- **Automatic Protection**: `@router.route` automatically sanitizes incoming JSON bodies and checks query parameters for XSS.
- **CSRF Protection**: `CSRF.generate(request)` creates a random signed token stored in cookie `_csrf`. `CSRF.verify(request)` reads the token from `X-CSRF-Token` header or body field `csrf` and compares against the signed cookie. `@csrf` route decorator enforces verification on POST/PUT/PATCH/DELETE.

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
- `lila-seo`: Generate sitemap.xml and robots.txt.

### SEO Optimization (`core/routing.py` & `cli/seo.py`)

- `@seo(title="...", description="...")`: Route decorator for injecting SEO metadata into `request.state.seo` and template context.
- **Multilingual support**: Pass dictionaries (e.g., `{"en": "Title", "es": "Título"}`) or use translation keys (`"translate:key"`).
- **Centralized configuration**: Map route paths to metadata in `app/seo.py`.
- **Auto-generate** `sitemap.xml` and `robots.txt` using the CLI.

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

### ORM & BaseModel operations

Using the built-in ActiveRecord-style methods on `BaseModel` subclasses:
```python
# Assuming Item inherits from BaseModel
session = connection.get_session()

# Select all active records
items = Item.get_all()

# Select active records with specific field filter
items_filtered = Item.get_all(active=1, category_id=5)

# Select only specific columns (returns list of dicts)
items_dict = Item.get_all(select="id,name")

# Find record by primary key (ID)
item = Item.get_by_id(session, 1)

# Create a record
new_item = Item.insert(session, {"name": "Item Name", "price": 9.99})
session.commit()

# Update a record
Item.update(session, 1, {"name": "Updated Name"})

# Delete a record (soft delete active=0 if _delete_logic=True)
Item.delete(session, 1)

# Safely fetch relationship data (expunged from session to avoid DetachedInstanceError)
user = User.get_by_id(session, 1)
profile = user.get_related(Profile)  # One-to-One / Many-to-One
posts = user.get_related_many(Post)   # One-to-Many
```

Direct database connection ORM queries:
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

## Programmatic Configuration in App
Lila allows configuring these parameters directly when initializing the `App` class:
- `translate` (bool, default `True`): If `False`, validation translations and defaults are loaded, but the user's local `locales/translations.json` is ignored.
- `debug_html` (bool, default `False`): If `True`, registers the `/debug` dashboard panel at runtime.
- Overrides for settings (can bypass `.env` / `app/config.py` definitions):
  - `secret_key`, `title`, `version`, `description`, `lang_default`, `minify_html`
  - `path_log_base_dir`, `path_template_not_found`, `path_templates_html`, `path_templates_markdown`, `path_locales`, `path_uploads`

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

#### Generate SQLAlchemy models (scaffold & list)
```bash
# Start interactive BaseModel wizard (prompts for table, primary keys, soft delete, custom columns)
lila-model create

# Generate a skeleton model directly
lila-model create --name Product --table products

# List all generated models in app/models/
lila-model list-models
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

#### Run database containers with Docker (MySQL/PostgreSQL)
```bash
lila-docker start [mysql|postgres|all]
lila-docker stop [mysql|postgres|all]
lila-docker ps   # Shows status of database containers (also runs by default on "lila-docker")
lila-docker mysql # Connect to MySQL shell using .env credentials
lila-docker db    # Alias for lila-docker mysql
```

#### Run development server (starts local uvicorn on main.py)
```bash
lila-dev
```

#### Generate SEO Sitemap & Robots
```bash
lila-seo sitemap --domain https://yourdomain.com
lila-seo robots --domain https://yourdomain.com
```

### Core Enhancements Reference

#### 1. Flash Messages
- Queue a flash message in views:
  ```python
  from lila.core.session import flash
  flash(request, "Task completed!", category="success")
  ```
- Render flashes in templates:
  ```html
  {% for item in get_flashes() %}
    <div class="alert alert-{{ item.category }}">{{ item.message }}</div>
  {% endfor %}
  ```

#### 2. CSRF Protection
- Enable CSRF on a form route:
  ```python
  from lila.core.templates import render
  from lila.core.middleware import csrf

  @router.get('/contact')
  async def contact_page(request: Request):
      return render(request, 'contact', csrf=True)

  @router.post('/contact')
  @csrf
  async def contact_submit(request: Request):
      return JSONResponse({"success": True})
  ```
- Render the hidden input in your Jinja2 template:
  ```html
  <form method="POST" action="/contact">
    {{ csrf_input | safe }}
    <input type="text" name="name" />
    <button type="submit">Send</button>
  </form>
  ```
- `Http()` in `public/js/utils.js` automatically detects `document.getElementById('csrf')` and sends `X-CSRF-Token` on every request. No additional client-side code required.

#### 2. DB Transactions Context Manager
- Safely run queries/updates using automatic commits and rollbacks:
  ```python
  with connection.transaction() as db:
      db.add(new_instance)
  ```

#### 3. Automatic Pydantic Validation on API Routes
- Type-annotate Pydantic model directly on your route handler function:
  ```python
  @router.post("/items")
  async def create_item(request: Request, body: ItemCreateSchema):
      # body is already parsed and validated!
      print(body.name)
  ```

#### 4. Extended @seo Decorator
- Passes canonical links, robots controls, author fields, or any custom meta:
  ```python
  @seo(title="Title", author="Me", canonical="https://...", custom_field="val")
  ```

---

## Performance Best Practices

### Async Database Queries (non-blocking)

Lila routes are `async def` (ASGI). Calling synchronous ORM methods from an async route **blocks the event loop** while the DB query runs, degrading throughput under concurrent load.

`BaseModel` provides async variants with **query deduplication**: when N concurrent requests trigger the exact same SELECT, only one DB round-trip happens. All other callers await the same `asyncio.Future` and receive the result automatically.

```python
# ✅ Non-blocking (use in async routes for SELECT operations)
@router.get("/products")
async def list_products(request: Request):
    items = await Product.get_all_async(limit=100)
    return JSONResponse(items)

@router.get("/products/{id}")
async def get_product(request: Request):
    product = await Product.get_by_id_async(request.path_params["id"])
    return JSONResponse(product or {})

# ✅ Synchronous (use in CLI, migrations, background tasks, write-after-read)
@router.post("/products")
async def create_product(request: Request):
    db = connection.get_session()
    Product.insert(db, request.state.data.dict())
    db.commit()
    db.close()
    return JSONResponse({"success": True})
```

**Query deduplication only applies to SELECT** — writes (`insert`, `update`, `delete`) always execute immediately.

### Connection Pool Configuration

`Database` defaults to `pool_size=20, max_overflow=40` for MySQL/PostgreSQL. These values align with `run_in_executor`'s thread pool to prevent threads queuing for a DB connection.

Adjust in `app/connections.py`:
```python
config = {
    "type": "mysql",
    ...
    "pool_size": 30,      # Max open connections at once
    "max_overflow": 60,   # Extra connections allowed under peak load
}
```

> **Rule of thumb**: `pool_size` should match or exceed `ThreadPoolExecutor` workers (default: `os.cpu_count() * 5`).

### Memory Optimization with `__slots__`

For custom helper classes (DTOs, service objects, data containers) that create **many instances**, use `__slots__` to eliminate the per-instance `__dict__`, reducing RAM by up to 60-70%.

```python
# Without __slots__: each instance allocates a __dict__ (~200+ bytes)
class Producto:
    __slots__ = ['id', 'nombre', 'precio']  # Evita __dict__ dinámico
    def __init__(self, id, nombre, precio):
        self.id = id
        self.nombre = nombre
        self.precio = precio
```

> **Do NOT use `__slots__` on SQLAlchemy models** — it is incompatible with SQLAlchemy's descriptor system. Only use it on plain Python helper classes.

### ASGI Server (uvicorn + uvloop + httptools)

Lila uses `uvicorn[standard]` which automatically activates `uvloop` (faster event loop) and `httptools` (faster HTTP parser) on Linux/macOS. No configuration needed — performance is improved automatically.

For even higher throughput, **Granian** is a Rust-based ASGI server compatible with Starlette. It offers ~30-50% more throughput and lower memory overhead than uvicorn in benchmarks. It is a drop-in replacement:
```bash
pip install granian
granian --interface asgi main:app --port 8000
```
Granian does not support Windows. Evaluate it for production VPS deployments where maximum performance is required.

---

## Docker Workflow

### Architecture

Each Lila project gets its own isolated Docker environment:
- **MySQL container**: always running, named `{LILA_PROJECT_NAME}-mysql`
- **Python app container** (prod only): named `{LILA_PROJECT_NAME}-app`
- **Private network**: named `{LILA_PROJECT_NAME}_network` — containers on different projects cannot communicate

This allows multiple Lila projects to coexist on one VPS without port or name conflicts.

### Setup (lila-init)

When running `lila-init`, the CLI asks for a project name and optional MySQL setup. The project name is sanitized (spaces → underscores, lowercase) and written to `.env` as `LILA_PROJECT_NAME`. This name is used by `docker-compose.yml` to namespace all resources.

### Development Workflow

```bash
# Start only MySQL (run your Python app locally)
lila-docker start
# or: lila-docker start mysql

# Run app normally
python main.py
# or: lila-dev
```

### Production Workflow

```bash
# 1. Build the Docker image (first time, or after requirements change)
lila-docker build

# 2. Start full stack (MySQL + Python app)
lila-docker start prod

# 3. View app logs
lila-docker logs
lila-docker logs --no-follow  # print last 100 lines

# 4. Stop everything
lila-docker stop
```

### Connecting to MySQL Terminal

```bash
# Conectar a MySQL usando las credenciales y BD del .env del proyecto
lila-docker mysql

# o usando el alias corto:
lila-docker db

# Conectar como usuario root usando el password root del .env
lila-docker mysql --root

# Especificar/sobrescribir usuario, contraseña o BD si es necesario
lila-docker mysql -u root -p mi_password -d mi_base_de_datos
```

### Running CLI Commands in Production Containers

When the app is running inside Docker, use `lila-docker exec` to run commands inside the container:

```bash
lila-docker exec app bash
# Inside container:
lila-migrations migrate
lila-model create Product
```

### Multi-Project VPS with Nginx

Each project configures its own `PORT` and `DB_PORT` in `.env`. Nginx routes traffic by domain to each container's port.

**Project A `.env`**: `PORT=8001`, `DB_PORT=3307`, `LILA_PROJECT_NAME=shop`
**Project B `.env`**: `PORT=8002`, `DB_PORT=3308`, `LILA_PROJECT_NAME=blog`

```nginx
# /etc/nginx/sites-available/shop.com
server {
    listen 443 ssl;
    server_name shop.com;
    location / {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### .env Docker Variables Reference

| Variable | Default | Description |
|---|---|---|
| `LILA_PROJECT_NAME` | `lila` | Unique project name — used for container and network naming |
| `PORT` | `8000` | Port exposed by the Python app container |
| `DB_NAME` | `lila_db` | MySQL database name |
| `DB_USER` | `root` | MySQL user |
| `DB_PASSWORD` | `root` | MySQL root password |
| `DB_PORT` | `3306` | Host port mapped to MySQL container |

> **Security note**: Change `DB_PASSWORD` in `.env` before deploying to production. The `.env` file is already in `.gitignore`.

### PostgreSQL (Optional)

PostgreSQL support requires the psycopg driver, installed separately:
```bash
pip install lila-framework[psycopg]
# or: pip install psycopg==3.2.10
```

Uncomment the `postgres` service in `docker-compose.yml` and update `app/connections.py`:
```python
config = {
    "type": "postgresql",
    "host": "127.0.0.1",
    "port": 5432,
    "user": "postgres",
    "password": "root",
    "database": "lila_db",
}
```
