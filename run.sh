#!/usr/bin/env bash
# Helper entrypoint for development Docker container
# - Runs migrations
# - Collects static files
# - Starts Daphne ASGI server to support WebSockets

set -euo pipefail

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-app.settings}

# Run database migrations (ignore failures if DB not ready)
python manage.py migrate --noinput || true

# Collect static files so container has /app/staticfiles
python manage.py collectstatic --noinput || true

# Start Daphne to serve ASGI (supports WebSockets)
exec daphne -b 0.0.0.0 -p 8000 app.asgi:application
