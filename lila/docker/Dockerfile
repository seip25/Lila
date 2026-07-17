# ─────────────────────────────────────────────────────────────────────────────
# Lila Framework — Production Dockerfile
# Python 3.14-slim for maximum compatibility and performance
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.14-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHON_JIT=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install system dependencies for mysql-connector-python and Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies first (layer cache optimization)
COPY requirements.txt* pyproject.toml* ./
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    elif [ -f pyproject.toml ]; then \
        pip install --no-cache-dir .; \
    else \
        pip install --no-cache-dir starlette jinja2 uvicorn[standard] pydantic pydantic[email] python-dotenv itsdangerous mysql-connector-python argon2-cffi markdown SQLAlchemy PyJWT psutil python-multipart typer rjsmin rcssmin jinja2-htmlmin starlette-compress pillow orjson redis psycopg uvloop httptools; \
    fi

# Copy project source
COPY . .

# Create necessary directories
RUN mkdir -p app/logs app/cache public

# Expose the app port (read from .env at runtime via docker-compose)
EXPOSE 8000

# Start the Lila application
CMD ["python", "main.py"]
