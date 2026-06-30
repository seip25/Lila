#!/bin/bash
SERVICE=${1:-all}

if [ "$SERVICE" = "mysql" ]; then
  echo "Stopping MySQL database container..."
  docker compose stop mysql
  docker compose rm -f mysql
elif [ "$SERVICE" = "postgres" ]; then
  echo "Stopping PostgreSQL database container..."
  docker compose stop postgres
  docker compose rm -f postgres
elif [ "$SERVICE" = "all" ]; then
  echo "Stopping and removing all database containers..."
  docker compose down
else
  echo "❌ Error: Unknown service '$SERVICE'. Use 'mysql', 'postgres', or 'all'."
  exit 1
fi
