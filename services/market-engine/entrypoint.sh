#!/bin/sh
set -e

# Run database migrations before starting the server.
# Uses psql to execute the SQL migration file against the DATABASE_URL.
if [ -n "$DATABASE_URL" ] && [ -f /migrations/001_initial.sql ]; then
  echo "Running market-engine database migrations..."
  # Convert Go-style postgres:// URL to psql-compatible format.
  psql "$DATABASE_URL" -f /migrations/001_initial.sql
  echo "Migrations complete."
fi

exec /market-engine "$@"
