#!/bin/bash
# Lila Framework — Docker stop script
# Usage:
#   ./docker/stop.sh           → Stop all containers for this project
#   ./docker/stop.sh mysql     → Stop only MySQL
#   ./docker/stop.sh app       → Stop only the Python app container
#
SERVICE=${1:-all}

if [ "$SERVICE" = "all" ]; then
  echo "🛑 Stopping all Lila containers..."
  docker compose --profile prod down
  echo "✅ All containers stopped."
elif [ "$SERVICE" = "mysql" ]; then
  echo "🛑 Stopping MySQL container..."
  docker compose stop mysql
  docker compose rm -f mysql
  echo "✅ MySQL stopped."
elif [ "$SERVICE" = "app" ]; then
  echo "🛑 Stopping Python app container..."
  docker compose --profile prod stop app
  docker compose --profile prod rm -f app
  echo "✅ App container stopped."
elif [ "$SERVICE" = "postgres" ]; then
  echo "🛑 Stopping PostgreSQL container..."
  docker compose stop postgres
  docker compose rm -f postgres
  echo "✅ PostgreSQL stopped."
else
  echo "❌ Error: Unknown service '$SERVICE'."
  echo "   Use: all (default), mysql, app, postgres"
  exit 1
fi
