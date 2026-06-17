# 🚀 ScriptDash

<div align="center">

**A beautiful web-based platform for managing, scheduling, and executing Python & Bash scripts**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Django 4.2+](https://img.shields.io/badge/django-4.2+-green.svg)](https://www.djangoproject.com/)

[Documentation](docs/) • [API Reference](docs/API_REFERENCE.md) • [Report Bug](https://github.com/cwhit-io/python-runner/issues)

</div>

---

## ✨ Why ScriptDash?

Stop juggling cron jobs, virtual environments, and scattered scripts. **ScriptDash** gives you a centralized platform to manage all your automation scripts with a beautiful, modern interface.

Perfect for:
- 🔄 **DevOps Engineers** - Automate deployments and infrastructure tasks
- 📊 **Data Engineers** - Schedule ETL jobs and data pipelines  
- 🤖 **Automation Enthusiasts** - Manage all your scripts in one place
- 🏢 **Small Teams** - Share and collaborate on automation scripts

## 🎯 Key Features

### 💻 Professional Code Editor
- **Monaco Editor** with syntax highlighting
- Dark/light themes with 29 options
- Auto-save and keyboard shortcuts
- Support for Python, Bash, and HTTP requests

### 🔒 Isolated Environments
- Each script runs in its own virtual environment
- Custom pip dependencies per script
- Smart dependency caching (only reinstalls on changes)
- Automatic conflict detection

### ⏰ Flexible Scheduling
- **Cron expressions** for complex schedules
- **Interval scheduling** for simple repeating tasks
- Enable/disable schedules on the fly
- View next run times at a glance

### 📈 Complete Execution History
- Full stdout/stderr capture
- Performance metrics (CPU, memory usage)
- Searchable execution logs
- One-click log copying

### 🎨 Beautiful Interface
- Modern, responsive design with DaisyUI
- 29 themes including dark mode
- Real-time status updates with HTMX
- Mobile-friendly

### 🔐 Secure & Shareable
- User authentication and authorization
- Encrypted secrets management
- API token authentication
- Optional public script sharing

### 🚀 Powerful API
- RESTful API with Django Ninja
- Auto-generated OpenAPI/Swagger docs
- Execute scripts remotely
- Integrate with any platform

## 📸 Screenshots

<div align="center">

### Script List
![Script List](docs/screenshots/screenshot-1769819883529.png)

### Script Editor
![Script Editor](docs/screenshots/screenshot-1769819973463.png)

### Execution Details
![Execution Details](docs/screenshots/screenshot-1769819956597.png)

### Schedule Management
![Schedule Management](docs/screenshots/screenshot-1769819916892.png)

</div>

## 🚀 Quick Start

Get up and running in under 5 minutes:

```bash
# Clone the repository
git clone https://github.com/cwhit-io/python-runner.git
cd python-runner

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup database
python manage.py migrate

# Create admin user
python manage.py createsuperuser

# Start the server
python manage.py runserver
```

Visit **http://localhost:8000** and start creating scripts! 🎉

📚 For detailed installation instructions, see [Installation Guide](docs/INSTALLATION.md)

## 📖 Documentation

| Document | Description |
|----------|-------------|
| [Installation Guide](docs/INSTALLATION.md) | Detailed setup instructions |
| [User Guide](docs/USER_GUIDE.md) | How to use ScriptDash |
| [API Reference](docs/API_REFERENCE.md) | Complete API documentation |
| [Architecture](docs/ARCHITECTURE.md) | Technical details for developers |
| [Docker Guide](docs/DOCKER.md) | Docker deployment |
| [Theming](docs/THEMING.md) | UI customization |

## 🎓 Usage Examples

### Create a Simple Script

1. Click **"Create Script"**
2. Add your Python code:
```python
import requests

response = requests.get('https://api.github.com')
print(f"GitHub API Status: {response.status_code}")
```
3. Add dependencies:
```
requests==2.31.0
```
4. Click **"Save"** and **"Run Now"**

### Schedule a Daily Task

1. Open your script
2. Click **"Add Schedule"**
3. Choose **Cron** and enter: `0 9 * * *` (runs at 9 AM daily)
4. Enable the schedule ✅

### Use the API

```bash
# Get your API token from Profile → API Tokens

# Execute a script remotely
curl -X POST \
  -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/v1/scripts/1/execute
```

## 🔧 Tech Stack

- **Backend:** Django 4.2, Django Ninja, APScheduler
- **Frontend:** HTMX, Alpine.js, Tailwind CSS, DaisyUI
- **Editor:** Monaco Editor (VS Code's editor)
- **Admin:** Django Unfold
- **Database:** SQLite (dev), PostgreSQL (prod)

## 🐳 Docker Deployment

```bash
# Development
docker-compose up

# Production
docker-compose -f docker-compose.prod.yml up -d
```

See [Docker Guide](docs/DOCKER.md) for details.

## � AI-Callable API Wrappers

The `ai_scripts/` directory contains standalone Python wrapper scripts designed to be called by AI agents (including ScriptDash's MCP tools). Each wrapper:

- Accepts a single JSON object via `argv[1]` or stdin
- Requires an `action` field
- Returns consistent JSON with `success`, `data`, `warnings`, and `meta`
- Supports `dry_run` for write actions
- Uses environment variables for credentials

### Services

| Service | Description | Credentials |
|---------|-------------|-------------|
| `planning_center_people` | People, households, workflows, lists | `PLANNING_CENTER_ACCESS_TOKEN` or `PLANNING_CENTER_CLIENT_ID` + `PLANNING_CENTER_CLIENT_SECRET` |
| `planning_center_calendar` | Events, resources, rooms, tags | Same as above |
| `planning_center_services` | Service types, plans, songs, teams | Same as above |
| `planning_center_publishing` | Episodes, series, speakers | Same as above |
| `planning_center_giving` | Donations, funds, batches (read-only) | Same as above |
| `planning_center_groups` | Groups, memberships, events | Same as above |
| `planning_center_registrations` | Events, attendees (read-only) | Same as above |
| `planning_center_checkins` | Check-ins, locations (read-only) | Same as above |
| `vimeo` | Videos, livestreams, uploads | `VIMEO_ACCESS_TOKEN` |
| `emailoctopus` | Lists, contacts, campaigns | `EMAILOCTOPUS_API_KEY` |
| `bitfocus_companion` | Buttons, variables, surfaces | `COMPANION_BASE_URL` (optional `COMPANION_API_KEY`) |
| `sermonshots` | Videos, clips, transcripts, AI content | `SERMONSHOTS_API_KEY` |

### CLI Usage

```bash
# List Planning Center people
python ai_scripts/planning_center_people/wrapper.py '{"action":"list_people","per_page":5}'

# Dry-run a contact creation
python ai_scripts/emailoctopus/wrapper.py '{"action":"create_contact","list_id":"abc123","email":"user@example.com","dry_run":true}'

# Press a Companion button
python ai_scripts/bitfocus_companion/wrapper.py '{"action":"press_button","page":0,"bank":0,"x":1,"y":2}'
```

See each subfolder's `README.md` for full action lists and examples.

## �🤝 Contributing

We love contributions! Whether it's:

- 🐛 Bug reports
- 💡 Feature requests  
- 📝 Documentation improvements
- 🔧 Code contributions

Please open an issue or submit a pull request!

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

Built with amazing open-source tools:
- [Django](https://www.djangoproject.com/)
- [Django Ninja](https://django-ninja.rest-framework.com/)
- [Monaco Editor](https://microsoft.github.io/monaco-editor/)
- [HTMX](https://htmx.org/)
- [Tailwind CSS](https://tailwindcss.com/)
- [DaisyUI](https://daisyui.com/)

## 📮 Support

- 💬 GitHub Issues: [Report a bug](https://github.com/cwhit-io/python-runner/issues)
- 📖 Documentation: [Read the docs](docs/)

---

<div align="center">

**Made with ❤️ for the automation community**

[⭐ Star this repo](https://github.com/cwhit-io/python-runner) if you find it useful!

</div>
