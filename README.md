# Python Script Runner

A centralized Python script manager with web UI for DevOps automation, ETL jobs, and scheduled tasks. Edit scripts in Monaco editor, run manually or on schedule (APScheduler), each with isolated virtual environments. Captures logs, stdout/stderr, and execution history.

Built on **Django + Django Ninja API + HTMX + DaisyUI + Unfold admin**.

Perfect for DevOps automation, ETL jobs, and scheduled tasks without container overhead.

## Key Features

### 🐍 Script Management

- **Monaco Editor** - Professional code editor with Python syntax highlighting
- **Isolated Virtual Environments** - Each script has its own venv with custom dependencies
- **Dependency Management** - Specify requirements per script (e.g., `requests==2.28.0`)
- **Version Control Ready** - All scripts stored in database with full history

### ⏰ Scheduling & Execution

- **APScheduler Integration** - Cron-based scheduling for automated execution
- **Manual Execution** - Run scripts on-demand with a single click
- **Execution History** - Complete logs of every run with stdout/stderr
- **Real-time Status** - Track running, success, and failed executions
- **Multiple Trigger Types** - Manual, scheduled, or API-triggered

### 📊 Monitoring & Logging

- **Execution Logs** - Full stdout and stderr capture for debugging
- **Performance Metrics** - Track execution duration and exit codes
- **Status Tracking** - Monitor script health and last successful run
- **Error Handling** - Detailed error messages and stack traces

### 🔐 Authentication & Security

- **Role-based Access** - User-owned scripts with optional public sharing
- **API Token Authentication** - Secure token-based API access
- **User Profiles** - Avatar upload and theme preferences
- **Email Verification** - Token-based email confirmation

### 🚀 API Features

- **Django Ninja** - Fast, type-safe API framework
- **Auto-generated API Docs** - Interactive Swagger/OpenAPI documentation
- **Script Management API** - Full CRUD for scripts via REST API
- **Execution Triggers** - Start scripts remotely via API
- **Schedule Management** - Create/update schedules programmatically
- **Token Authentication** - Secure Bearer token authentication

### ⚡ Real-time Features

- **WebSocket Support** - Built-in channels integration
- **Live Log Streaming** - Real-time execution output (coming soon)
- **Status Updates** - WebSocket-based status notifications (coming soon)

### 🎨 Modern UI

- **daisyUI + Tailwind CSS** - Beautiful, responsive components
- **Light/Dark Mode** - 29 themes with localStorage persistence
- **htmx** - Dynamic interactions without page reloads
- **Unfold Admin** - Modern, customizable admin interface

## Quick Start

### Prerequisites

- Python 3.10+
- pip and virtualenv

### Installation

1. **Clone the repository**

```bash
git clone <your-repo>
cd django-starter-template
```

2. **Create and activate virtual environment**

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Run migrations**

```bash
python manage.py migrate
```

5. **Create superuser**

```bash
python manage.py createsuperuser
```

6. **Run development server**

```bash
python manage.py runserver
```

7. **Visit the application**

- **Script Manager**: http://localhost:8000
- **Admin Panel**: http://localhost:8000/admin
- **API Docs**: http://localhost:8000/api/docs

## Usage Guide

### Creating a Script

1. **Login** and navigate to "My Scripts"
2. Click **"Create Script"**
3. Enter a name and description
4. Click **"Create"**

### Editing Scripts

1. Open the script editor
2. Write your Python code in the **Monaco Editor**
3. Add **dependencies** (one per line):
   ```
   requests==2.28.0
   pandas>=1.5.0
   numpy
   ```
4. Click **"Save Changes"**

### Running Scripts

**Manual Execution:**
- Click **"Run Now"** on the script detail page
- View real-time status and logs

**Scheduled Execution:**
1. Add a schedule with a cron expression
2. Examples:
   - `0 */6 * * *` - Every 6 hours
   - `0 0 * * *` - Daily at midnight
   - `0 0 * * 0` - Weekly on Sunday
3. Enable/disable schedules as needed

### Viewing Execution Logs

1. Go to script detail page
2. Click on any execution in the history
3. View:
   - **Status** (success/failed)
   - **Duration**
   - **Standard Output** (stdout)
   - **Standard Error** (stderr)
   - **Exit Code**

## API Usage

### Authentication

Create an API token:
1. Profile → API Tokens → Create Token
2. Copy the token immediately

### API Examples

```bash
# List all scripts
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/scripts

# Create a script
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"My Script","code":"print(\"Hello\")"}' \
     http://localhost:8000/api/v1/scripts

# Execute a script
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/scripts/1/execute

# Get execution details
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/executions/1
```

Full API documentation: http://localhost:8000/api/docs

## Project Structure

```
python-runner/
├── app/
│   ├── api/              # Django Ninja API endpoints
│   │   ├── scripts.py    # Script management API
│   │   └── items.py      # Example API
│   ├── services/         # Business logic
│   │   ├── script_runner.py  # Script execution engine
│   │   └── scheduler.py      # APScheduler integration
│   ├── models.py         # Database models
│   │   ├── Script        # Script definition
│   │   ├── ScriptExecution  # Execution logs
│   │   └── ScriptSchedule   # Scheduled jobs
│   ├── views_scripts.py  # Script UI views
│   ├── admin.py          # Admin interface
│   └── settings.py       # Configuration
├── templates/
│   ├── scripts/          # Script management UI
│   │   ├── list.html     # Script list
│   │   ├── detail.html   # Script details
│   │   ├── edit.html     # Monaco editor
│   │   └── execution_detail.html
│   └── base.html         # Base template
├── media/
│   └── venvs/            # Isolated virtual environments
├── requirements.txt      # Python dependencies
└── manage.py
```

## Configuration

### Virtual Environments

Each script gets an isolated virtual environment:
- **Location**: `media/venvs/{script_id}/`
- **Auto-created**: On first execution
- **Dependencies**: Installed from script's requirements

### Scheduling

APScheduler runs in-process:
- **Timezone**: Configurable per schedule
- **Persistence**: Database-backed (optional)
- **Auto-reload**: On server restart

### Email Settings

For password reset and verification (development uses console):

```python
# app/settings.py
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-app-password'
```

### WebSocket Configuration

For production WebSocket support, configure Redis:

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

#### Running with Daphne (development)

The built-in Django development server does not support WebSockets. To test WebSocket features locally, run an ASGI server such as Daphne:

```bash
# Activate your virtualenv first
source .venv/bin/activate

# Run Daphne (bind to 0.0.0.0:8000)
daphne -b 0.0.0.0 -p 8000 app.asgi:application
```

You can also use the provided helper script:

```bash
# Make it executable once:
chmod +x ./scripts/run_daphne.sh
# Then run:
./scripts/run_daphne.sh
```

For production, run Daphne (or Uvicorn) behind a process manager and/or load balancer and connect to Redis-backed Channels for scaling.

### Media Files

Media files are configured for local development. For production, use cloud storage:

```bash
pip install django-storages boto3
```

```python
# app/settings.py
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
AWS_ACCESS_KEY_ID = 'your-access-key'
AWS_SECRET_ACCESS_KEY = 'your-secret-key'
AWS_STORAGE_BUCKET_NAME = 'your-bucket-name'
```

## Usage

### API Token Authentication

1. **Create a token**
   - Login to your account
   - Go to Profile → API Tokens
   - Click "Create Token" and name it
   - Copy the token immediately (shown only once)

2. **Use the token in API requests**

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/protected/items/my-items
```

3. **In JavaScript**

```javascript
fetch("/api/protected/items/my-items", {
  headers: {
    Authorization: "Bearer YOUR_TOKEN",
  },
});
```

### WebSocket Integration

**Chat Room Example:**

```javascript
const chatSocket = new WebSocket("ws://localhost:8000/ws/chat/lobby/");

chatSocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(`${data.username}: ${data.message}`);
};

chatSocket.send(JSON.stringify({ message: "Hello!" }));
```

**User Notifications (requires authentication):**

```javascript
const notificationSocket = new WebSocket(
  "ws://localhost:8000/ws/notifications/",
);

notificationSocket.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Notification:", data.message);
};
```

### Custom API Endpoints

Add new API endpoints in `app/api/`:

```python
# app/api/your_module.py
from ninja import Router
from app.auth import APITokenAuth

router = Router()

@router.get("/example", auth=APITokenAuth())
def example_endpoint(request):
    return {"user": request.auth.user.username}
```

Register in `app/api/__init__.py`:

```python
from .your_module import router as your_router
api.add_router("/your-path", your_router)
```

## Docker Deployment

**Development:**

```bash
docker-compose up
```

**Production:**

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Admin Interface

Access the admin at `/admin` with your superuser credentials.

**Features:**

- **API Logs** - View all API requests with color-coded status
- **User Profiles** - Manage user profiles and avatars
- **API Tokens** - View and manage user API tokens
- **Custom Theme** - Purple/violet color scheme
- **Dark Mode** - Built-in theme switching

## Models

### UserProfile

- One-to-one with Django User
- Fields: avatar, bio, email_verified, email_verification_token
- Auto-created on user registration

### APIToken

- Secure token generation
- Fields: token, name, user, is_active, created_at, last_used
- Used for API authentication

### APILog

- Automatic logging via middleware
- Fields: endpoint, method, status_code, user, ip_address, timestamp, etc.
- Color-coded display in admin

## Testing

```bash
# Run tests
python manage.py test

# Check for issues
python manage.py check
```

## Security Notes

- Change `SECRET_KEY` in production
- Set `DEBUG = False` in production
- Configure `ALLOWED_HOSTS` for your domain
- Use HTTPS in production
- Store API tokens securely (never in code)
- Use environment variables for sensitive settings

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

MIT License - feel free to use this template for any project!

## Support

For issues or questions, please open an issue on GitHub.

---

Built with ❤️ using Django, Django Ninja, htmx, and daisyUI
