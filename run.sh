#!/usr/bin/env bash
# Helper entrypoint for development Docker container
# - Runs migrations
# - Collects static files
# - Starts Daphne ASGI server to support WebSockets

set -euo pipefail

# Activate virtual environment first
source .venv/bin/activate

export DJANGO_SETTINGS_MODULE=${DJANGO_SETTINGS_MODULE:-app.settings}

# Check if port 8000 is in use
PORT=8000
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "Port $PORT is already in use."
    echo "Process details:"
    lsof -Pi :$PORT -sTCP:LISTEN

    # Ask user if they want to kill the process
    read -p "Do you want to kill the process using port $PORT? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "Killing process on port $PORT..."
        kill -9 $(lsof -ti :$PORT) 2>/dev/null || true
        echo "Process killed. Waiting a moment..."
        sleep 2
    else
        echo "Exiting without killing the process."
        exit 1
    fi
fi

# Run database migrations (ignore failures if DB not ready)
python manage.py migrate --noinput || true

# Collect static files so container has /app/staticfiles
python manage.py collectstatic --noinput || true

# Start Daphne to serve ASGI (supports WebSockets)
exec daphne -b 0.0.0.0 -p 8000 app.asgi:application
