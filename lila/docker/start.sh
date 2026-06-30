#!/bin/bash
SERVICE=${1:-all}

if [ "$SERVICE" = "mysql" ]; then
  echo "Starting MySQL database container..."
  docker compose up -d mysql
elif [ "$SERVICE" = "postgres" ]; then
  echo "Starting PostgreSQL database container..."
  docker compose up -d postgres
elif [ "$SERVICE" = "all" ]; then
  echo "Starting all database containers..."
  docker compose up -d
else
  echo "❌ Error: Unknown service '$SERVICE'. Use 'mysql', 'postgres', or 'all'."
  exit 1
fi
