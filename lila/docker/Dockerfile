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

# Install runtime libraries and curl for diagnostics
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
COPY requirements.txt* pyproject.toml* setup.py* ./

# Install dependencies:
# 1. If requirements.txt exists, install it
# 2. Guarantee lila-framework is installed in Python environment
RUN if [ -f requirements.txt ]; then \
        pip install --no-cache-dir -r requirements.txt; \
    fi && \
    (python -c "import lila" 2>/dev/null || pip install --no-cache-dir lila-framework)

# Copy project source code
COPY . .

# If pyproject.toml is present (local framework repo build), install local version
RUN if [ -f pyproject.toml ]; then pip install --no-cache-dir .; fi

# Create necessary directories and ensure proper permissions
RUN mkdir -p app/logs app/cache public /tmp/sockets && \
    chown -R appuser:appgroup /app /tmp/sockets && \
    chmod -R 777 app/logs app/cache /tmp/sockets

# Switch to non-root user
USER appuser

# Expose app port
EXPOSE 8000

# Container Healthcheck (supports both UDS Unix socket and TCP mode)
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, sys, socket, urllib.request; uds = os.getenv('UDS_PATH'); (sys.exit(0) if (uds and os.path.exists(uds)) else None); urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/')" || exit 1

# Start the Lila application
CMD ["python", "main.py"]
