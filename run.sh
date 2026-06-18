#!/usr/bin/env bash
# Helper entrypoint for development Docker container
# - Runs migrations
# - Collects static files
# - Starts Daphne ASGI server to support WebSockets

set -euo pipefail

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-app.settings}

# Wait for database to be ready (for PostgreSQL)
if [ -n "${DATABASE_URL:-}" ]; then
    echo "Waiting for PostgreSQL to be ready..."
    # Extract host from DATABASE_URL (format: postgresql://user:pass@host:port/db)
    DB_HOST=$(python -c "
import os
url = os.environ.get('DATABASE_URL', '')
if '@' in url:
    host_part = url.split('@')[1]
    host = host_part.split(':')[0].split('/')[0]
    print(host)
else:
    print('db')
" 2>/dev/null || echo "db")
    
    for i in {1..30}; do
        if pg_isready -h "${DB_HOST}" -p 5432 -q 2>/dev/null || \
           python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('${DB_HOST}', 5432)); s.close()" 2>/dev/null; then
            echo "PostgreSQL is ready!"
            break
        fi
        echo "Waiting for PostgreSQL... ($i/30)"
        sleep 1
    done
fi

# Run database migrations
python manage.py migrate --noinput || true

# Create superuser if environment variables are set
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py createsuperuser --noinput --username "$DJANGO_SUPERUSER_USERNAME" --email "$DJANGO_SUPERUSER_EMAIL" || true
fi

# Collect static files so container has /app/staticfiles
python manage.py collectstatic --noinput || true

# Start Daphne to serve ASGI (supports WebSockets)
exec daphne -b 0.0.0.0 -p 8000 app.asgi:application
