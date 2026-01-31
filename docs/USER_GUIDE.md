# User Guide

Complete guide for using ScriptDash.

## Table of Contents

- [Getting Started](#getting-started)
- [Managing Scripts](#managing-scripts)
- [Organizing with Tags](#organizing-with-tags)
- [Running Scripts](#running-scripts)
- [Scheduling Scripts](#scheduling-scripts)
- [Managing Secrets](#managing-secrets)
- [API Usage](#api-usage)
- [Keyboard Shortcuts](#keyboard-shortcuts)

## Getting Started

### First Login

1. Navigate to http://localhost:8000
2. Register a new account or login with your credentials
3. Complete email verification (if configured)

### Creating Your First Script

1. Click **"Create Script"** from the dashboard
2. Enter a name and description
3. Select script language (Python, Bash, or HTTP)
4. Click **"Create"**

## Managing Scripts

### Editing Scripts

The Monaco editor provides a professional coding experience:

1. Open any script to access the editor
2. Write your code with syntax highlighting
3. Add dependencies in the sidebar (Python scripts only)
4. Save your changes with **Ctrl+S** or the Save button

### Adding Dependencies (Python)

Add Python packages one per line in the Requirements section:

```text
requests==2.31.0
pandas>=1.5.0
numpy
beautifulsoup4
```

**Smart Features:**
- Hash-based change detection (only reinstalls when changed)
- Automatic conflict detection
- Isolated virtual environments per script

### Script Types

**Python Scripts:**
- Full Python 3.11 environment
- Custom pip dependencies
- Isolated virtual environments

**Bash Scripts:**
- System bash environment
- Direct shell access
- No dependency management needed

**HTTP Requests:**
- Visual request builder
- Method, URL, headers, and body configuration
- Automatic code generation

### Duplicating Scripts

Clone any script with one click:
- Preserves code and dependencies
- Creates new isolated environment
- Auto-generates unique name

### Import/Export

**Export:**
- Single script: Click "Export" on detail page
- Multiple scripts: Use bulk selection checkboxes

**Import:**
- Click "Import Script" from scripts list
- Upload JSON file
- Script is recreated with new environment

### Bulk Operations

Select multiple scripts using checkboxes:
- **Bulk Delete**: Remove multiple scripts
- **Bulk Export**: Download as JSON files

## Organizing with Tags

### Creating Tags

1. Navigate to **Tags** from the main menu
2. Click **"Create Tag"**
3. Enter name, choose color, add description
4. Save

### Using Tags

**Assign to Scripts:**
- Edit any script
- Select tags from your collection
- Tags appear as colored badges

**Filter by Tags:**
- Click tag buttons in script list
- View all scripts with that tag

**Tag Management:**
- Edit tag properties
- View script counts per tag
- Delete unused tags

## Running Scripts

### Manual Execution

1. Open script detail page
2. Click **"Run Now"**
3. View real-time status updates
4. Check execution logs

### Viewing Execution History

Each execution records:
- **Status** (success/failed/running)
- **Duration** (execution time)
- **Output** (stdout)
- **Errors** (stderr)
- **Exit Code**
- **Performance Metrics** (CPU, memory)

**Copy Output:**
- Click "Copy" button next to output sections
- Easily share logs or debug information

## Scheduling Scripts

### Creating a Schedule

1. Go to script detail page
2. Click **"Add Schedule"**
3. Choose schedule type:
   - **Interval**: Run every N minutes/hours/days
   - **Cron**: Use cron expression for complex schedules

### Schedule Types

**Interval Examples:**
- Every 30 minutes
- Every 6 hours
- Once per day

**Cron Examples:**
```text
0 */6 * * *    # Every 6 hours
0 0 * * *      # Daily at midnight
0 9 * * 1-5    # Weekdays at 9 AM
0 0 * * 0      # Weekly on Sunday
0 0 1 * *      # Monthly on 1st
```

### Managing Schedules

- **Enable/Disable**: Toggle schedules on/off
- **Edit**: Update timing or type
- **Delete**: Remove schedules
- **View Next Run**: See when next execution is scheduled

## Managing Secrets

Store sensitive values securely:

1. Edit your script
2. In the **Secrets** section, add key-value pairs
3. Access in your code:

**Python:**
```python
import os
api_key = os.environ.get('API_KEY')
```

**Bash:**
```bash
echo $API_KEY
```

**Features:**
- Encrypted storage
- Per-script isolation
- Never logged in execution output

## API Usage

### Getting Your API Token

1. Go to **Profile** → **API Tokens**
2. Click **"Create Token"**
3. Name your token
4. Copy immediately (shown only once)

### Example API Calls

**List Scripts:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/scripts
```

**Create Script:**
```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"name":"API Script","code":"print(\"Hello from API\")"}' \
     http://localhost:8000/api/v1/scripts
```

**Execute Script:**
```bash
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/scripts/1/execute
```

**Get Execution Details:**
```bash
curl -H "Authorization: Bearer YOUR_TOKEN" \
     http://localhost:8000/api/v1/executions/1
```

For complete API documentation, visit http://localhost:8000/api/docs

## Keyboard Shortcuts

Speed up your workflow:

- **Ctrl+N** / **Cmd+N**: Create new script
- **Ctrl+E** / **Cmd+E**: Edit current script
- **Ctrl+R** / **Cmd+R**: Run current script
- **Ctrl+D** / **Cmd+D**: Duplicate current script
- **Ctrl+S** / **Cmd+S**: Save script changes

## User Profile

### Customization

- **Avatar**: Upload profile picture
- **Theme**: Choose from 29 themes
- **Timezone**: Set for accurate scheduling
- **Time Format**: 12h or 24h display

### Account Security

- Change password
- Manage API tokens
- View login history (admin)

## Tips & Best Practices

### Script Development

1. **Test Locally**: Use "Run Now" before scheduling
2. **Check Logs**: Always review execution output
3. **Use Tags**: Organize scripts by purpose
4. **Version Control**: Export important scripts regularly

### Dependencies

1. **Pin Versions**: Use `==` for reproducibility
2. **Test First**: Run after dependency changes
3. **Watch Conflicts**: Review conflict warnings

### Scheduling

1. **Start Simple**: Test with longer intervals first
2. **Monitor**: Check execution history regularly
3. **Error Handling**: Add try/catch in your scripts
4. **Notifications**: Consider adding email alerts in your scripts

### Security

1. **Use Secrets**: Never hardcode credentials
2. **Limit Scope**: Only add necessary dependencies
3. **API Tokens**: Create separate tokens per integration
4. **Review Access**: Regularly audit user permissions
