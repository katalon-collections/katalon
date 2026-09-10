#!/bin/sh
set -e

echo "Waiting for database..."
# Extract host and port from DATABASE_URL for the wait loop.
# Fallback to db:5432 if not set.
DB_HOST=$(echo "$DATABASE_URL" | sed -n 's/.*@\([^:/]*\).*/\1/p')
DB_PORT=$(echo "$DATABASE_URL" | sed -n 's/.*:\([0-9]*\)\/.*/\1/p')
DB_HOST=${DB_HOST:-db}
DB_PORT=${DB_PORT:-5432}

for i in $(seq 1 30); do
    if python -c "import socket; socket.create_connection(('${DB_HOST}', ${DB_PORT}), timeout=1)" 2>/dev/null; then
        echo "Database is ready."
        break
    fi
    echo "Database not ready yet, retrying in 1s... (${i}/30)"
    sleep 1
done

echo "Running database migrations..."
alembic -c migrations/alembic.ini upgrade head

echo "Starting application..."
exec "$@"
