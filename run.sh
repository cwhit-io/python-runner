#!/usr/bin/env bash
# Helper entrypoint for development Docker container
# - Runs migrations
# - Collects static files
# - Starts Daphne ASGI server to support WebSockets

set -euo pipefail

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-app.settings}

# Run database migrations (ignore failures if DB not ready)
python manage.py migrate --noinput || true

# Create superuser if environment variables are set
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_EMAIL:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
    python manage.py createsuperuser --noinput --username "$DJANGO_SUPERUSER_USERNAME" --email "$DJANGO_SUPERUSER_EMAIL" || true
fi

# Collect static files so container has /app/staticfiles
python manage.py collectstatic --noinput || true

# Start Daphne to serve ASGI (supports WebSockets)
exec daphne -b 0.0.0.0 -p 8000 app.asgi:application
