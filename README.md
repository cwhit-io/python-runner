# Django Starter Template

A modern, production-ready Django starter template with built-in authentication, API support, real-time features, and a beautiful admin interface.

## Features

### 🎨 Modern UI

- **daisyUI + Tailwind CSS** - Beautiful, responsive components
- **Light/Dark Mode** - Theme switching with localStorage persistence
- **htmx** - Dynamic interactions without page reloads
- **Unfold Admin** - Modern, customizable admin interface with custom purple theme

### 🔐 Authentication & User Management

- **User Registration** - With email verification
- **Password Reset** - Complete forgot password flow
- **Email Verification** - Token-based email confirmation
- **User Profiles** - With avatar upload support
- **API Token Authentication** - Secure token-based API access

### 🚀 API Features

- **Django Ninja** - Fast, type-safe API framework
- **Auto-generated API Docs** - Interactive Swagger/OpenAPI documentation
- **API Logging** - Automatic request/response logging with admin visibility
- **Token Authentication** - Secure Bearer token authentication
- **Protected Endpoints** - Example authenticated API routes

### ⚡ Real-time Features

- **WebSocket Support** - Built-in channels integration
- **Chat Rooms** - Public chat room example
- **User Notifications** - Private user-specific notifications
- **Live Demo Page** - Interactive WebSocket demonstration

### 📁 File Management

- **Media Files** - Configured for user uploads (avatars, etc.)
- **Avatar Upload** - Profile picture support with Pillow
- **Static Files** - Organized CSS, JS, and asset management

### 🛠 Developer Experience

- **Docker Support** - Development and production configurations
- **API Logging** - Color-coded status/method display in admin
- **Custom Middleware** - Request logging middleware
- **Type Safety** - Django Ninja schemas for API validation

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

- Frontend: http://localhost:8000
- Admin: http://localhost:8000/admin
- API Docs: http://localhost:8000/api/docs
- WebSocket Demo: http://localhost:8000/websocket-demo

## Project Structure

```
django-starter-template/
├── app/
│   ├── api/              # Django Ninja API endpoints
│   │   ├── items.py      # Item API routes
│   │   └── schemas.py    # Pydantic schemas
│   ├── services/         # Business logic layer
│   │   └── item_service.py
│   ├── utils/            # Helper functions
│   ├── admin.py          # Admin interface configuration
│   ├── auth.py           # API token authentication
│   ├── consumers.py      # WebSocket consumers
│   ├── forms.py          # Django forms
│   ├── middleware.py     # Custom middleware
│   ├── models.py         # Database models
│   ├── routing.py        # WebSocket routing
│   ├── settings.py       # Django settings
│   ├── urls.py           # URL configuration
│   └── views.py          # View functions
├── templates/
│   ├── registration/     # Auth templates
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── profile.html      # User profile
│   ├── profile_edit.html # Profile editing
│   ├── api_tokens.html   # API token management
│   └── websocket_demo.html # WebSocket demo
├── static/
│   └── css/
│       ├── site.css      # Main styles
│       └── admin-custom.css # Admin overrides
├── media/                # User uploaded files
├── requirements.txt      # Python dependencies
└── manage.py            # Django CLI
```

## Configuration

### Email Settings

The template uses console email backend for development. To use real email in production:

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
