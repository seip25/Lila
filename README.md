# Lila Framework

Lila is a high-performance, lean Python web and API framework built on **Starlette**, **Pydantic**, and **SQLAlchemy**. Designed for developers who value speed, simplicity (KISS), and minimal resource consumption, Lila enables rapid API and full-stack development with a footprint under 40MB RAM per worker.

## Key Features

- **Blazing Fast**: Built on Starlette and Uvicorn (`uvloop` + `httptools`) with pure ASGI middlewares for zero-overhead routing and sub-millisecond responses.
- **Fast Serialization**: 100% powered by `orjson` for high-throughput JSON serialization and deserialization.
- **Robust Validation**: Schema validation using Pydantic models with automatic OpenAPI/Swagger documentation generation.
- **Async Database Engine**: First-class async support for SQLite (`aiosqlite`), MySQL (`aiomysql`/`pymysql`), and PostgreSQL (`asyncpg`/`psycopg`) with connection pooling tuned for low-memory VPS environments.
- **Distributed Cache & Sessions**: Asynchronous Redis integration for session management, caching, and rate limiting with local memory fallback.
- **Docker & VPS Optimized**: Out-of-the-box Docker Compose stack (App + Nginx + Redis + MySQL) running the entire production stack in under 350MB of RAM.
- **API-First Architecture**: Seamless separation of frontend and backend. Nginx serves static assets directly from disk while Python handles dynamic API endpoints.
- **Optional SSR**: Jinja2 and Markdown support are lazy-loaded on demand (`pip install 'lila-framework[ssr]'`), keeping core API deployments ultra lightweight.
- **Background Tasks & WebSockets**: Distributed WebSockets via Redis Pub/Sub and asynchronous background worker queues.
- **JWT & Security**: Stateless JWT authentication helpers and pure ASGI security headers without false-positive URL blocking.

---

## Installation

1. Install Lila Framework using pip:

```bash
pip install lila-framework
```

2. Initialize a new project in your directory:

```bash
lila-init
```

3. Run your development server:

```bash
python main.py
```

---

## Production Deployment with Docker

Lila includes a hardened production Docker stack with MySQL tuned for low-memory VPS deployment:

```bash
# Verify port availability and daemon readiness
lila-docker check

# Start the full production stack (App + Nginx + MySQL + Redis)
lila-docker start prod

# Monitor live CPU and RAM consumption across containers
lila-docker stats

# Zero-downtime VPS deploy helper
lila-docker deploy
```

---

## Documentation

Comprehensive guides and API references:
https://seip25.github.io/Lila
