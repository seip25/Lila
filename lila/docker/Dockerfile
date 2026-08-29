# ─────────────────────────────────────────────────────────────────────────────
# Lila Framework — Production Dockerfile
# Python 3.12-slim for optimal performance, stability, and pre-built binary wheels
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HOST=0.0.0.0 \
    PORT=8000

WORKDIR /app

# Install runtime libraries and curl for healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a non-privileged user and group for production security
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/bash -m appuser

# Copy dependency specifications first to leverage Docker layer caching
COPY requirements.txt* pyproject.toml* ./

# Install dependencies:
# 1. If requirements.txt exists (standard Lila projects), install listed packages
# 2. If pyproject.toml exists (framework development or local repo builds), install package directly
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Copy project source code
COPY . .

# If pyproject.toml is present (local framework repo), install the package locally
RUN if [ -f pyproject.toml ]; then pip install --no-cache-dir .; fi

# Create necessary directories and ensure proper permissions
RUN mkdir -p app/logs app/cache public /tmp/sockets && \
    chown -R appuser:appgroup /app /tmp/sockets && \
    chmod 777 /tmp/sockets

# Switch to non-root user
USER appuser

# Expose app port
EXPOSE 8000

# Container Healthcheck (checks TCP port or root endpoint)
HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/ || python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/')" || exit 1

# Start the Lila application
CMD ["python", "main.py"]
