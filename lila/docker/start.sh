#!/bin/bash
# Lila Framework — Docker start script
# Usage:
#   ./docker/start.sh          → Start MySQL only (dev)
#   ./docker/start.sh mysql    → Start MySQL only (dev)
#   ./docker/start.sh prod     → Start MySQL + Python app (production)
#
SERVICE=${1:-mysql}

if [ "$SERVICE" = "mysql" ] || [ "$SERVICE" = "dev" ]; then
  echo "🚀 Starting MySQL container (dev mode)..."
  docker compose up -d mysql
  echo "✅ MySQL ready. Run your app with: python main.py"
elif [ "$SERVICE" = "prod" ]; then
  echo "🚀 Starting full production stack (MySQL + App)..."
  docker compose --profile prod up -d
  echo "✅ Production stack started."
elif [ "$SERVICE" = "postgres" ]; then
  echo "🚀 Starting PostgreSQL container..."
  docker compose up -d postgres
  echo "✅ PostgreSQL ready. Run your app with: python main.py"
elif [ "$SERVICE" = "all" ]; then
  echo "🚀 Starting all services (dev mode — app excluded)..."
  docker compose up -d mysql
  echo "✅ Services started. Run your app with: python main.py"
else
  echo "❌ Error: Unknown service '$SERVICE'."
  echo "   Use: mysql (default), prod, postgres"
  exit 1
fi
