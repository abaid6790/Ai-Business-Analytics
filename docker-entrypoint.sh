#!/bin/sh
set -e

# Give a containerized Postgres a moment to be ready to accept connections
# on first `docker compose up` — Postgres itself starts fast, but the
# initial "accepting connections" state can lag a few seconds behind the
# container reporting as running.
if [ -n "$DATABASE_URL" ]; then
    echo "Waiting for the database to be ready..."
    python3 -c "
import time
import sys
from sqlalchemy import create_engine, text

url = '$DATABASE_URL'
for attempt in range(30):
    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        print('Database is ready.')
        sys.exit(0)
    except Exception as exc:
        print('  ...not ready yet (attempt ' + str(attempt + 1) + '/30): ' + str(exc))
        time.sleep(2)
sys.exit(1)
"
fi

echo "Running database migrations..."
flask db upgrade

if [ -n "$ADMIN_EMAIL" ] && [ -n "$ADMIN_PASSWORD" ]; then
    echo "Ensuring admin account exists..."
    flask create-admin || true
fi

echo "Starting: $@"
exec "$@"
