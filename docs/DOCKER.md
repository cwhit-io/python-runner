# Django Starter Template - Docker Setup

## Quick Start with Docker

### Development (with hot reload)

```bash
docker-compose up
```

Access at http://localhost:8000

### Production Build

```bash
docker build -f Dockerfile.prod -t django-starter:prod .
docker run -p 8000:8000 django-starter:prod
```

### With Nginx (full stack)

```bash
docker-compose up -d
```

Access at http://localhost

## Commands

### Build

```bash
docker-compose build
```

### Run migrations

```bash
docker-compose exec web python manage.py migrate
```

### Create superuser

```bash
docker-compose exec web python manage.py createsuperuser
```

### View logs

```bash
docker-compose logs -f web
```

### Stop containers

```bash
docker-compose down
```

### Remove volumes (clean database)

```bash
docker-compose down -v
```

## GitHub Container Registry

Images are automatically built and pushed to GitHub Container Registry on:

- Push to `main` branch
- Pull requests (build only, no push)
- Version tags (e.g., `v1.0.0`)

### Pull from registry

```bash
docker pull ghcr.io/cwhit-io/django-starter-template:latest
docker pull ghcr.io/cwhit-io/django-starter-template:prod-latest
```

### Run from registry

```bash
docker run -p 8000:8000 ghcr.io/cwhit-io/django-starter-template:latest
```

## Environment Variables

Create a `.env` file for local development:

```env
DEBUG=1
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgresql://django_user:django_password@db:5432/django_db
```
