# Lila Framework — Agent Reference

Lila is a high-performance, lightweight Python web framework built on **Starlette** + **Pydantic** + **SQLAlchemy** + **orjson**.
Designed for rapid development, low RAM consumption, and seamless Docker/VPS deployment.

## Project Structure

```
lila/
├── main.py                  # App entry point (Uvicorn, routing, ASGI middlewares)
├── core/                    # Framework core
│   ├── app.py               # App class (extends Starlette) with pure ASGI middlewares
│   ├── routing.py           # Router with HTTP decorators, WebSocket, REST CRUD, OpenAPI/Swagger
│   ├── database.py          # Database engine (SQLAlchemy: SQLite, MySQL, PostgreSQL)
│   ├── base_model.py        # BaseModel class (ORM CRUD boilerplate, soft delete, relation helpers)
│   ├── templates.py         # Lazy-loaded Jinja2 and Markdown template utilities
│   ├── session.py           # Signed cookie and Redis session management
│   ├── auth.py              # JWT tokens (generate, verify) and password hashing
│   ├── security.py          # HTML sanitization utilities
│   ├── csrf.py              # CSRF token generation and validation
│   ├── files.py             # File upload utilities
│   ├── responses.py         # JSONResponse (orjson), HTMLResponse, FileResponse, RedirectResponse
│   ├── websocket.py         # WebSocketManager (rooms, broadcast, Redis pub/sub)
│   ├── oauth.py             # GoogleAuth and GitHubAuth helpers
│   ├── mailer.py            # Mailer engine (async SMTP, HTML email templates)
│   ├── admin.py             # Admin panel (dashboard, metrics, model CRUD)
│   ├── logger.py            # File-based Logger + request logger
│   ├── debug.py             # Diagnostic performance monitoring
│   ├── translate.py         # Precedence-based language detection (?lang=, body, header, cookies)
│   ├── middleware.py        # Pure ASGI middlewares (SecurityHeaders, RateLimit, Logging, Flash)
│   ├── controller.py        # RequestParser (body/query validation via Pydantic)
│   ├── request.py           # Starlette Request wrapper
│   ├── utils.py             # Helper utilities
│   └── background.py        # Hybrid BackgroundTask (Starlette + Redis Queue)
├── app/
│   ├── config.py            # Environment configuration (.env)
│   ├── connections.py       # Database connection instance
│   ├── middlewares/         # Custom user middlewares
│   ├── models/              # SQLAlchemy models
│   └── routes/              # Route modules (web, api, admin)
├── cli/                     # CLI tools
│   ├── scaffold.py          # Create a new Lila project (lila-init)
│   ├── model.py             # Generate SQLAlchemy models from database tables (lila-model)
│   ├── migrations.py        # Database migrations (lila-migrations)
│   ├── auth.py              # Create database admin (lila-auth)
│   ├── create_admin.py      # Admin creation helper
│   ├── create_panel_admin.py# Admin panel generator
│   ├── scaffold_crud.py     # Generate REST CRUD endpoints
│   ├── secret_key.py        # Generate secure secret keys (lila-secret-key)
│   ├── seo.py               # SEO tools (lila-seo)
│   ├── docker.py            # Docker management (lila-docker)
│   ├── dev.py               # Development server runner (lila-dev)
│   └── worker.py            # Background task worker (lila-worker)
├── resources/               # Frontend templates (HTML/Jinja2)
└── public/                  # Static assets served by Nginx or Starlette
```

## Core Architecture Principles

1. **KISS & Minimal Footprint**: Lean core with zero bloated dependencies. Consumes <40MB RAM per worker.
2. **Pure ASGI Middlewares**: All core middlewares implement `async def __call__(self, scope, receive, send)` without `BaseHTTPMiddleware` / AnyIO task group overhead.
3. **No Regex XSS False Positives**: Incoming query parameters and URLs (such as Instagram or Google referral links) pass through cleanly without false alarms.
4. **API-First & Static Edge**: Nginx serves `/public/` static files in 0.1ms directly from disk with gzip/brotli compression, leaving Python focused solely on dynamic endpoints.
5. **Low-Memory Database**: MySQL connection pool default is `pool_size: 5, max_overflow: 10`, paired with low-memory `my.cnf` (`performance_schema = OFF`) to fit comfortably within 512MB/1GB VPS droplets.
