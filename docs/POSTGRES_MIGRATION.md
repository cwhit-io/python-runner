# PostgreSQL Migration Guide

This guide covers migrating ScriptDash from SQLite to PostgreSQL for production use.

## Why PostgreSQL?

PostgreSQL offers several advantages over SQLite for production:
- **Concurrent connections**: Better handling of multiple simultaneous users
- **Reliability**: ACID transactions with better crash recovery
- **Performance**: Indexes, query optimization, and connection pooling
- **Scalability**: Handles larger datasets efficiently
- **Features**: JSON fields, full-text search, better timezone support

## Quick Start: Run with Docker Compose (Recommended)

The easiest way to run ScriptDash with PostgreSQL is using Docker Compose:

```bash
# From the docker directory
cd docker

# Copy environment template
cp .env.example .env

# Edit .env with your values
# vim .env

# Start services
docker compose up -d

# The app will be available at http://localhost:8003
```

### Docker Environment Variables

Configure these in `docker/.env`:

```bash
# Required for production
DEBUG=0
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1,yoursite.com

# Admin user (created on first run)
DJANGO_SUPERUSER_USERNAME=admin
DJANGO_SUPERUSER_EMAIL=admin@example.com
DJANGO_SUPERUSER_PASSWORD=your-secure-password

# PostgreSQL is auto-configured via docker-compose.yml
# DATABASE_URL=postgresql://scriptdash:scriptdash@db:5432/scriptdash
```

## Manual Installation

### 1. Install PostgreSQL (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl start postgresql
```

### 2. Create Database and User

```bash
sudo -u postgres psql
```

```sql
CREATE DATABASE scriptdash;
CREATE USER scriptdash WITH PASSWORD 'your-secure-password';
GRANT ALL PRIVILEGES ON DATABASE scriptdash TO scriptdash;
\q
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
export DATABASE_URL=postgresql://scriptdash:your-secure-password@localhost:5432/scriptdash
export SECRET_KEY="your-secret-key-here"
export DEBUG=0
export ALLOWED_HOSTS="localhost,yoursite.com"
```

### 5. Run Migrations

```bash
python manage.py migrate
python manage.py createsuperuser --username admin --email admin@example.com
python manage.py collectstatic --noinput
```

## Migrating Existing Data from SQLite

If you have existing data in SQLite, follow these steps:

### 1. Backup Your SQLite Database

```bash
# Ensure the app is not running
cp db/db.sqlite3 db/db.sqlite3.backup
```

### 2. Export Data from SQLite

```bash
python manage.py dumpdata --natural-foreign --natural-primary \
    --exclude=contenttypes --exclude=admin.logentry \
    --indent=2 > sqlite_backup.json
```

### 3. Set Up PostgreSQL

Follow the steps above to configure PostgreSQL.

### 4. Run Migrations on New Database

```bash
python manage.py migrate
```

### 5. Load Data into PostgreSQL

```bash
python manage.py loaddata sqlite_backup.json
```

### 6. Verify Migration

```bash
# Check that your scripts are present
python manage.py shell -c "from app.models import Script; print(f'Scripts: {Script.objects.count()}')"

# Check users
python manage.py shell -c "from django.contrib.auth.models import User; print(f'Users: {User.objects.count()}')"

# Check execution history
python manage.py shell -c "from app.models import ScriptExecution; print(f'Executions: {ScriptExecution.objects.count()}')"
```

## Log Retention Recommendations

To prevent database bloat and potential file handle issues, configure regular log cleanup:

### Recommended Retention

| Data Type | Retention Period | Notes |
|-----------|-----------------|-------|
| API logs | 30 days | Debugging and auditing |
| Execution stdout/stderr | 90 days | Keep recent output for debugging |
| Execution records | Indefinite | Metadata and status only |
| Script virtual environments | Until script deletion | Stored in `media/venvs/` |

### Set Up Log Cleanup Cron Job

Add to your crontab (`crontab -e`):

```cron
# Run cleanup daily at 2 AM
0 2 * * * cd /app && /usr/bin/python manage.py cleanup_logs --api-days=30 --execution-output-days=90 >> /var/log/scriptdash-cleanup.log 2>&1
```

## System Limits (Preventing "Too Many Open Files")

If you encounter "Too many open files" errors, increase system limits:

### Linux (systemd)

Add to `/etc/systemd/system.conf`:
```
DefaultLimitNOFILE=65536
```

Then reload:
```bash
sudo systemctl daemon-reload
```

### Linux (ulimit)

Add to `/etc/security/limits.conf`:
```
* soft nofile 65536
* hard nofile 65536
```

### Check Current Limits

```bash
ulimit -n  # Current limit
cat /proc/sys/fs/file-max  # System max
```

## PostgreSQL Production Settings

For production, add these to your PostgreSQL configuration (`postgresql.conf`):

```conf
# Connection settings
max_connections = 100
shared_buffers = 256MB
effective_cache_size = 1GB

# Query optimization
work_mem = 4MB
maintenance_work_mem = 64MB

# Logging (helpful for debugging)
log_min_duration_statement = 1000  # Log slow queries > 1s
log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h '
```

## Verification Checklist

After migration, verify:

- [ ] Scripts list loads correctly
- [ ] Can view script details
- [ ] Can run scripts and see output
- [ ] Executions are recorded properly
- [ ] MCP tools are accessible (if exposed)
- [ ] Schedules work correctly
- [ ] Secrets can be set/get
- [ ] API endpoints respond correctly
- [ ] Admin interface works

## Troubleshooting

### Connection Errors

If you see connection errors, check:
1. PostgreSQL is running: `sudo systemctl status postgresql`
2. Database credentials in `DATABASE_URL` are correct
3. Network connectivity (if remote DB)
4. SSL requirements - set `sslmode=disable` in DATABASE_URL if needed

### Migration Issues

If `loaddata` fails:
1. Ensure all migrations are applied first
2. Check for encoding issues in `sqlite_backup.json`
3. Consider splitting the JSON file into smaller chunks

### "Too Many Open Files" Still Occurs

1. Check for stale processes: `ps aux | grep python`
2. Review subprocess cleanup in `script_runner.py`
3. Consider using a process manager (systemd, supervisor)
4. Add explicit file handle cleanup in long-running processes