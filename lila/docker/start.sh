#!/bin/bash
# Lila Framework — Docker start script
# Usage:
#   ./docker/start.sh          → Start MySQL and Redis (dev mode)
#   ./docker/start.sh dev      → Start MySQL and Redis (dev mode)
#   ./docker/start.sh mysql    → Start MySQL only
#   ./docker/start.sh redis    → Start Redis only
#   ./docker/start.sh prod     → Start full production stack (MySQL + Redis + App + Nginx)
#   ./docker/start.sh postgres → Start PostgreSQL container
#
SERVICE=${1:-dev}

if [ "$SERVICE" = "dev" ]; then
  echo "🚀 Starting MySQL and Redis containers (dev mode)..."
  docker compose up -d mysql redis
  echo "✅ MySQL and Redis ready. Run your app locally with: lila-dev or python main.py"
elif [ "$SERVICE" = "mysql" ]; then
  echo "🚀 Starting MySQL container (low-memory mode)..."
  docker compose up -d mysql
  echo "✅ MySQL ready. Memory capped (~70MB RAM)."
elif [ "$SERVICE" = "redis" ]; then
  echo "🚀 Starting Redis container..."
  docker compose up -d redis
  echo "✅ Redis ready."
elif [ "$SERVICE" = "prod" ]; then
  echo "🚀 Starting full production stack (MySQL + Redis + App + Nginx)..."
  docker compose --profile prod up -d
  echo "✅ Production stack started. View status with: lila-docker ps"
elif [ "$SERVICE" = "postgres" ]; then
  echo "🚀 Starting PostgreSQL container..."
  docker compose up -d postgres
  echo "✅ PostgreSQL ready."
else
  echo "❌ Error: Unknown service '$SERVICE'."
  echo "   Use: dev (default), mysql, redis, prod, postgres"
  exit 1
fi
