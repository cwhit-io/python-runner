# Installation Guide

## Prerequisites

- Python 3.10 or higher
- pip and virtualenv
- Git

## Standard Installation

### 1. Clone the Repository

```bash
git clone https://github.com/cwhit-io/python-runner.git
cd python-runner
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Migrations

```bash
python manage.py migrate
```

### 5. Create Superuser

```bash
python manage.py createsuperuser
```

### 6. Start the Server

```bash
python manage.py runserver
```

### 7. Access the Application

- **Web Interface**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **API Documentation**: http://localhost:8000/api/docs

## Docker Installation

### Development

```bash
docker-compose up
```

### Production

```bash
docker-compose -f docker-compose.prod.yml up -d
```

For more details, see [DOCKER.md](DOCKER.md).

## Configuration

### Email Settings (Optional)

For password reset and email verification:

```python
# app/settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

### WebSocket Configuration (Optional)

For real-time features, configure Redis:

```python
# app/settings.py
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [('127.0.0.1', 6379)],
        },
    },
}
```

Run with Daphne for WebSocket support:

```bash
daphne -b 0.0.0.0 -p 8000 app.asgi:application
```

### Security Settings (Production)

⚠️ **Important**: Before deploying to production:

1. Change `SECRET_KEY` in settings
2. Set `DEBUG = False`
3. Configure `ALLOWED_HOSTS` for your domain
4. Use HTTPS
5. Use environment variables for sensitive settings

## Troubleshooting

### Common Issues

**Port already in use:**
```bash
# Use a different port
python manage.py runserver 8080
```

**Database migrations fail:**
```bash
# Reset migrations (development only)
python manage.py migrate --run-syncdb
```

**Dependencies conflict:**
```bash
# Recreate virtual environment
deactivate
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

For more help, see [GitHub Issues](https://github.com/cwhit-io/python-runner/issues).
