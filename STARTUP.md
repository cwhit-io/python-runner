# Startup Guide - Python Script Runner

## Before Running - Complete Setup Checklist

### 1. Required System Dependencies

```bash
# Python 3.10 or higher required
python3 --version

# Ensure pip is up to date
python3 -m pip install --upgrade pip
```

### 2. Install Python Dependencies

```bash
# Navigate to project directory
cd /home/runner/work/python-runner/python-runner

# Install all required packages
pip install -r requirements.txt
```

**Required packages (from requirements.txt):**
- Django>=5.0,<6.1
- django-ninja>=1.1.0
- django-cors-headers>=4.3.0
- daphne>=4.0.0
- channels>=4.0.0
- channels-redis>=4.0.0
- Pillow>=10.0.0
- whitenoise>=6.0.0
- django-unfold
- APScheduler>=3.10.0
- croniter>=2.0.0

### 3. Database Setup

```bash
# Create database tables (SQLite by default)
python manage.py migrate

# Expected output:
# Operations to perform:
#   Apply all migrations: admin, app, auth, contenttypes, sessions
# Running migrations:
#   Applying contenttypes.0001_initial... OK
#   Applying auth.0001_initial... OK
#   ...
#   Applying app.0004_script_scriptexecution_scriptschedule_and_more... OK
```

### 4. Create Superuser (Admin Access)

```bash
python manage.py createsuperuser

# Follow prompts:
# Username: admin
# Email: admin@example.com
# Password: (choose a secure password)
```

### 5. Create Media Directory for Virtual Environments

```bash
# Create directory for script virtual environments
mkdir -p media/venvs
```

### 6. Verify Settings (app/settings.py)

**Required settings are already configured:**

✅ **Database** (SQLite):
```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

✅ **Media files** (for venvs and uploads):
```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

✅ **Static files**:
```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
```

✅ **Installed apps** (includes all required):
- unfold (admin theme)
- channels (WebSocket)
- app (our application)

### 7. Start Development Server

```bash
# Run the development server
python manage.py runserver 0.0.0.0:8000

# Expected output:
# Watching for file changes with StatReloader
# Performing system checks...
# System check identified no issues (0 silenced).
# January 23, 2026 - 05:35:00
# Django version 6.0.1, using settings 'app.settings'
# Starting development server at http://0.0.0.0:8000/
# Quit the server with CONTROL-C.
```

### 8. Access the Application

**Web Interface:**
- **Script Manager**: http://localhost:8000/
- **Admin Panel**: http://localhost:8000/admin/
- **API Documentation**: http://localhost:8000/api/docs

**Default Credentials:**
- Username: (created in step 4)
- Password: (created in step 4)

---

## Quick Start - First Script

### 1. Create Your First Script

1. Login at http://localhost:8000/
2. Click **"Create Script"**
3. Enter:
   - Name: `Hello World`
   - Description: `My first script`
4. Click **"Create"**

### 2. Edit the Script

1. Click **"Edit"** on the script
2. In the Monaco editor, write:
   ```python
   import sys
   print("Hello from Python Script Runner!")
   print(f"Python version: {sys.version}")
   ```
3. Click **"Save Changes"**

### 3. Run the Script

1. Go back to script details
2. Click **"Run Now"**
3. View the execution details
4. Check stdout for output

### 4. Add a Schedule (Optional)

1. On script details page, click **"Add Schedule"**
2. Enter:
   - Name: `Hourly run`
   - Cron Expression: `0 * * * *` (every hour)
   - Timezone: `UTC`
3. Click **"Create"**

### 5. Add Dependencies

For scripts that need external packages:

1. Edit your script
2. In the **Dependencies** field, add:
   ```
   requests==2.31.0
   pandas>=2.0.0
   ```
3. Save changes
4. On next execution, dependencies will be installed in isolated venv

---

## API Usage Examples

### 1. Create an API Token

```bash
# Via Web UI:
# 1. Login → Profile → API Tokens → Create Token
# 2. Name it: "My API Token"
# 3. Copy the token immediately (shown only once)
```

### 2. Use the API

```bash
# Set your token
export TOKEN="your-token-here"

# List all scripts
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/scripts

# Create a new script
curl -X POST \
     -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{
       "name": "API Script",
       "description": "Created via API",
       "code": "print(\"Hello from API!\")"
     }' \
     http://localhost:8000/api/v1/scripts

# Execute a script (replace 1 with actual script ID)
curl -X POST \
     -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/scripts/1/execute

# Get execution details (replace 1 with actual execution ID)
curl -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/api/v1/executions/1
```

---

## Common Issues and Solutions

### Issue: Port 8000 already in use

```bash
# Find and kill the process
lsof -ti:8000 | xargs kill -9
# Or use a different port
python manage.py runserver 0.0.0.0:8001
```

### Issue: Database locked

```bash
# SQLite only allows one writer at a time
# Stop all Django processes and restart
```

### Issue: Virtual environment creation fails

```bash
# Ensure python3-venv is installed (Ubuntu/Debian)
sudo apt-get install python3-venv

# Or on other systems, ensure venv module is available
python3 -m venv test_env
```

### Issue: Dependencies won't install in script venv

```bash
# Check script dependencies syntax
# Each line should be: package==version or package>=version
# Example:
requests==2.31.0
pandas>=2.0.0
numpy
```

### Issue: Scheduler not running scripts

```bash
# Check cron expression is valid
# Test at: https://crontab.guru/
# Examples:
# 0 * * * *     - Every hour
# */15 * * * *  - Every 15 minutes
# 0 0 * * *     - Daily at midnight
```

---

## Production Deployment Notes

### 1. Update Settings

```python
# app/settings.py

# Security
DEBUG = False
SECRET_KEY = os.environ.get('SECRET_KEY')  # Use environment variable
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']

# Database (switch to PostgreSQL)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME'),
        'USER': os.environ.get('DB_USER'),
        'PASSWORD': os.environ.get('DB_PASSWORD'),
        'HOST': os.environ.get('DB_HOST'),
        'PORT': '5432',
    }
}

# Email (for password reset)
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST')
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get('EMAIL_USER')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_PASSWORD')

# Security Headers
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

### 2. Collect Static Files

```bash
python manage.py collectstatic --noinput
```

### 3. Use Production Server

```bash
# Install gunicorn
pip install gunicorn

# Run with gunicorn
gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

### 4. Setup Process Manager

```bash
# Use systemd, supervisor, or similar
# Example systemd service:

# /etc/systemd/system/python-runner.service
[Unit]
Description=Python Script Runner
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/python-runner
ExecStart=/path/to/venv/bin/gunicorn app.wsgi:application --bind 0.0.0.0:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## File Structure Reference

```
python-runner/
├── app/
│   ├── migrations/           # Database migrations
│   ├── api/                  # API endpoints
│   │   ├── __init__.py      # Main API setup
│   │   ├── scripts.py       # Script management API
│   │   └── items.py         # Example API
│   ├── services/            # Business logic
│   │   ├── script_runner.py # Script execution
│   │   └── scheduler.py     # APScheduler
│   ├── models.py            # Database models
│   ├── views.py             # Auth views
│   ├── views_scripts.py     # Script management views
│   ├── admin.py             # Admin configuration
│   ├── settings.py          # Django settings
│   ├── urls.py              # URL routing
│   └── apps.py              # App configuration
├── templates/
│   ├── scripts/             # Script UI templates
│   │   ├── list.html
│   │   ├── detail.html
│   │   ├── edit.html
│   │   └── execution_detail.html
│   ├── registration/        # Auth templates
│   └── base.html            # Base template
├── static/
│   └── css/
│       └── site.css
├── media/
│   └── venvs/              # Script virtual environments
│       └── {script_id}/    # Each script has its own venv
├── requirements.txt        # Python dependencies
├── manage.py              # Django CLI
└── db.sqlite3            # SQLite database (created on migrate)
```

---

## Environment Variables (Production)

```bash
# Create .env file
cat > .env << EOF
SECRET_KEY=your-secret-key-here
DEBUG=False
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_NAME=python_runner
DB_USER=db_user
DB_PASSWORD=secure_password
DB_HOST=localhost

# Email
EMAIL_HOST=smtp.gmail.com
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password

# Optional: Redis for Channels (WebSocket)
REDIS_URL=redis://localhost:6379
EOF
```

Load environment variables:
```bash
# Install python-dotenv
pip install python-dotenv

# In settings.py, add at top:
from dotenv import load_dotenv
load_dotenv()
```

---

## Troubleshooting Checklist

- [ ] Python 3.10+ installed
- [ ] All requirements.txt packages installed
- [ ] Migrations applied (`python manage.py migrate`)
- [ ] Superuser created
- [ ] Media directory exists (`mkdir -p media/venvs`)
- [ ] Port 8000 is available
- [ ] Database file is writable (for SQLite)
- [ ] Server started successfully
- [ ] Can access http://localhost:8000
- [ ] Can login to admin panel
- [ ] API docs accessible at /api/docs
