# Architecture & Technical Details

Technical documentation for developers working with Python Runner.

## Technology Stack

### Backend
- **Django 4.2+** - Web framework
- **Django Ninja** - Fast, type-safe API framework
- **APScheduler** - Task scheduling
- **Django Channels** - WebSocket support

### Frontend
- **HTMX** - Dynamic interactions without JavaScript
- **Alpine.js** - Lightweight reactivity
- **Tailwind CSS** - Utility-first styling
- **DaisyUI** - Component library
- **Monaco Editor** - Code editing

### Admin
- **Django Unfold** - Modern admin interface

## Project Structure

```
python-runner/
├── app/
│   ├── api/                    # API endpoints
│   │   ├── __init__.py        # API router registration
│   │   ├── items.py           # Example endpoints
│   │   ├── scripts.py         # Script management API
│   │   └── schemas.py         # Pydantic schemas
│   ├── management/
│   │   └── commands/
│   │       └── check_schedules.py  # Scheduler daemon
│   ├── services/               # Business logic
│   │   ├── script_runner.py   # Execution engine
│   │   ├── scheduler.py       # APScheduler integration
│   │   ├── secret_store.py    # Secrets management
│   │   └── item_service.py    # Example service
│   ├── templatetags/
│   │   └── custom_filters.py  # Template helpers
│   ├── utils/
│   │   └── helpers.py         # Utility functions
│   ├── admin.py               # Admin configuration
│   ├── auth.py                # Authentication backends
│   ├── consumers.py           # WebSocket consumers
│   ├── forms.py               # Django forms
│   ├── middleware.py          # Custom middleware
│   ├── models.py              # Database models
│   ├── routing.py             # WebSocket routing
│   ├── settings.py            # Django settings
│   ├── urls.py                # URL configuration
│   ├── views.py               # Main views
│   ├── views_scripts.py       # Script views
│   └── wsgi.py / asgi.py      # Server entry points
├── templates/                  # Django templates
│   ├── scripts/               # Script UI
│   ├── registration/          # Auth pages
│   └── base.html              # Base template
├── static/                     # Static assets
│   └── css/                   # Custom styles
├── staticfiles/               # Collected static files
├── media/                     # User uploads
│   ├── avatars/               # Profile pictures
│   └── venvs/                 # Script virtual environments
├── docker/                    # Docker configuration
├── docs/                      # Documentation
└── requirements.txt           # Python dependencies
```

## Core Models

### UserProfile
Extended user model with additional fields:
- `avatar` - Profile picture
- `theme_preference` - UI theme selection
- `timezone` - User timezone
- `time_format` - 12h/24h preference
- `email_verified` - Verification status
- `email_verification_token` - Verification token

### APIToken
Secure API authentication:
- `token` - Hashed token value
- `name` - Token identifier
- `user` - Owner
- `is_active` - Enable/disable
- `last_used` - Track usage

### Script
Core script model:
- `name`, `description` - Metadata
- `code` - Script source code
- `language` - python/bash/http
- `dependencies` - Requirements text
- `dependency_hash` - Change detection
- `has_conflicts` - Conflict flag
- `conflict_details` - JSON conflict info
- `tags` - Many-to-many with Tag
- `is_public` - Visibility
- `user` - Owner

### Tag
Organization and categorization:
- `name` - Tag name
- `color` - Hex color code
- `description` - Optional description
- `created_by` - Owner

### ScriptExecution
Execution history and logs:
- `script` - Related script
- `status` - running/success/failed
- `stdout`, `stderr` - Output capture
- `exit_code` - Process exit code
- `duration` - Execution time
- `peak_cpu_percent` - CPU usage
- `peak_memory_mb` - Memory usage
- `started_at`, `finished_at` - Timestamps

### ScriptSchedule
Automated scheduling:
- `script` - Related script
- `schedule_type` - interval/cron
- `cron_expression` - Cron timing (if cron)
- `interval_value`, `interval_unit` - Interval timing
- `is_active` - Enable/disable
- `next_run`, `last_run` - Schedule tracking

## Services

### ScriptRunner (`services/script_runner.py`)

Handles script execution with isolated environments.

**Key Methods:**
- `run_script(script)` - Execute a script
- `_ensure_venv(script)` - Create/verify virtual environment
- `_install_dependencies(script)` - Install pip packages
- `_check_dependency_conflicts(script)` - Detect version conflicts
- `_execute_in_venv(script)` - Run code in isolated environment

**Features:**
- Isolated virtual environments per script
- Hash-based dependency caching
- Automatic conflict detection
- Resource monitoring (CPU, memory)
- Output capture (stdout/stderr)
- Timeout handling

### Scheduler (`services/scheduler.py`)

APScheduler integration for automated execution.

**Key Methods:**
- `start()` - Initialize scheduler
- `add_schedule(schedule)` - Add scheduled job
- `remove_schedule(schedule)` - Remove job
- `update_schedule(schedule)` - Update timing

**Features:**
- Cron and interval schedules
- Persistent job storage
- Automatic recovery on restart
- Timezone support

### SecretStore (`services/secret_store.py`)

Encrypted secrets management.

**Key Methods:**
- `set_secret(script, key, value)` - Store secret
- `get_secret(script, key)` - Retrieve secret
- `delete_secret(script, key)` - Remove secret
- `get_all_secrets(script)` - List all secrets

**Features:**
- Encrypted storage
- Per-script isolation
- Environment variable injection

## API Architecture

### Django Ninja

Type-safe API framework with automatic OpenAPI documentation.

**Router Structure:**
```python
# app/api/__init__.py
from ninja import NinjaAPI
from .scripts import router as scripts_router

api = NinjaAPI()
api.add_router("/scripts", scripts_router)
```

**Authentication:**
```python
from app.auth import APITokenAuth

@router.get("/protected", auth=APITokenAuth())
def protected_endpoint(request):
    return {"user": request.auth.user.username}
```

### Schemas (Pydantic)

Type validation and serialization:

```python
from ninja import Schema

class ScriptCreate(Schema):
    name: str
    code: str
    language: str = "python"
    dependencies: str = ""

class ScriptOut(Schema):
    id: int
    name: str
    code: str
    created_at: datetime
```

## Virtual Environment Management

### Directory Structure

```
media/venvs/
├── 1/                  # Script ID 1
│   ├── bin/
│   ├── lib/
│   └── pyvenv.cfg
├── 2/                  # Script ID 2
│   └── ...
└── 10/                 # Script ID 10
    └── ...
```

### Dependency Optimization

**Hash Calculation:**
```python
import hashlib

def calculate_dependency_hash(dependencies):
    return hashlib.sha256(
        dependencies.encode('utf-8')
    ).hexdigest()
```

**Change Detection:**
- Compare current hash with stored hash
- Only reinstall if hash differs
- Significant performance improvement

**Conflict Detection:**
```python
def check_conflicts(dependencies):
    # Parse version specifications
    # Detect incompatible ranges
    # Return conflict details
```

## Frontend Architecture

### HTMX Patterns

Dynamic updates without full page reloads:

```html
<button 
    hx-post="/scripts/1/execute/" 
    hx-target="#execution-status"
    hx-swap="innerHTML">
    Run Script
</button>

<div id="execution-status">
    <!-- Updated via HTMX -->
</div>
```

### Alpine.js Reactivity

Lightweight component state:

```html
<div x-data="{ open: false }">
    <button @click="open = !open">Toggle</button>
    <div x-show="open">Content</div>
</div>
```

### Monaco Editor Integration

Professional code editing:

```javascript
require.config({ 
    paths: { 'vs': 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } 
});

require(['vs/editor/editor.main'], function() {
    const editor = monaco.editor.create(container, {
        value: code,
        language: 'python',
        theme: 'vs-dark'
    });
});
```

## WebSocket Architecture

### Channels Configuration

```python
# app/routing.py
from django.urls import path
from . import consumers

websocket_urlpatterns = [
    path('ws/notifications/', consumers.NotificationConsumer.as_asgi()),
    path('ws/execution/<int:execution_id>/', consumers.ExecutionConsumer.as_asgi()),
]
```

### Consumers

```python
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        
    async def receive(self, text_data):
        # Handle incoming messages
        pass
        
    async def send_notification(self, event):
        # Send to client
        await self.send(text_data=json.dumps(event))
```

## Security

### Authentication
- Session-based for web UI
- Token-based for API
- CSRF protection enabled

### Authorization
- User-owned resources
- Optional public sharing
- Admin-only access controls

### Secrets Management
- Encrypted storage
- Never logged
- Environment variable injection

### Input Validation
- Pydantic schemas for API
- Django forms for UI
- SQL injection protection (ORM)
- XSS protection (template escaping)

## Performance Optimizations

### Database
- Indexed foreign keys
- Query optimization with `select_related`, `prefetch_related`
- Connection pooling

### Caching
- Static file caching
- Template fragment caching (optional)
- Redis for sessions (optional)

### Virtual Environments
- Hash-based dependency caching
- Lazy venv creation
- Shared system packages

## Testing

### Unit Tests
```python
from django.test import TestCase

class ScriptTestCase(TestCase):
    def test_script_creation(self):
        script = Script.objects.create(
            name="Test",
            code="print('test')"
        )
        self.assertEqual(script.name, "Test")
```

### API Tests
```python
from ninja.testing import TestClient

def test_list_scripts():
    client = TestClient(api)
    response = client.get("/scripts", headers=auth_headers)
    assert response.status_code == 200
```

## Deployment Considerations

### Production Settings
- `DEBUG = False`
- Secure `SECRET_KEY`
- Database: PostgreSQL recommended
- Static files: Use CDN or cloud storage
- Media files: Cloud storage (S3, etc.)

### Process Management
- Use Gunicorn/Uvicorn for WSGI/ASGI
- Daphne for WebSocket support
- Supervisor/systemd for process management
- Nginx for reverse proxy

### Monitoring
- Application logging
- Error tracking (Sentry recommended)
- Performance monitoring
- Resource usage tracking

## Contributing

### Code Style
- PEP 8 for Python
- Black for formatting
- isort for imports
- Type hints encouraged

### Git Workflow
- Feature branches
- Pull requests
- Code review required
- CI/CD integration

For more information, see the [Contributing Guide](../CONTRIBUTING.md).
