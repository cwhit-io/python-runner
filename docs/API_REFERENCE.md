# API Reference

Complete reference for Python Runner REST API.

## Authentication

All API endpoints require Bearer token authentication.

### Getting a Token

1. Login to your account
2. Navigate to **Profile** → **API Tokens**
3. Click **"Create Token"**
4. Copy the token (shown only once)

### Using the Token

Include in the `Authorization` header:

```bash
Authorization: Bearer YOUR_TOKEN_HERE
```

## Base URL

```
http://localhost:8000/api/v1
```

## Endpoints

### Scripts

#### List Scripts

```http
GET /scripts
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "Data Processor",
    "description": "Processes daily data",
    "language": "python",
    "code": "print('Hello')",
    "dependencies": "requests==2.31.0\npandas",
    "created_at": "2026-01-30T10:00:00Z",
    "updated_at": "2026-01-30T10:00:00Z"
  }
]
```

#### Get Script

```http
GET /scripts/{id}
```

#### Create Script

```http
POST /scripts
```

**Request Body:**
```json
{
  "name": "My Script",
  "description": "Optional description",
  "language": "python",
  "code": "print('Hello World')",
  "dependencies": "requests==2.31.0"
}
```

#### Update Script

```http
PUT /scripts/{id}
```

**Request Body:** Same as Create Script

#### Delete Script

```http
DELETE /scripts/{id}
```

#### Execute Script

```http
POST /scripts/{id}/execute
```

**Response:**
```json
{
  "execution_id": 123,
  "status": "running",
  "started_at": "2026-01-30T10:00:00Z"
}
```

#### Export Script

```http
GET /scripts/{id}/export/
```

Returns JSON file for download.

#### Import Script

```http
POST /scripts/import/
Content-Type: multipart/form-data
```

**Form Data:**
- `json_file`: Script JSON file

### Executions

#### List Executions

```http
GET /executions
```

**Query Parameters:**
- `script_id`: Filter by script
- `status`: Filter by status (running, success, failed)

#### Get Execution

```http
GET /executions/{id}
```

**Response:**
```json
{
  "id": 123,
  "script_id": 1,
  "status": "success",
  "stdout": "Hello World\n",
  "stderr": "",
  "exit_code": 0,
  "duration": 1.23,
  "peak_cpu_percent": 15.5,
  "peak_memory_mb": 45.2,
  "started_at": "2026-01-30T10:00:00Z",
  "finished_at": "2026-01-30T10:00:01Z"
}
```

### Schedules

#### List Schedules

```http
GET /schedules
```

**Query Parameters:**
- `script_id`: Filter by script

#### Create Schedule

```http
POST /schedules
```

**Request Body:**
```json
{
  "script_id": 1,
  "schedule_type": "cron",
  "cron_expression": "0 */6 * * *",
  "is_active": true
}
```

Or for interval:

```json
{
  "script_id": 1,
  "schedule_type": "interval",
  "interval_value": 30,
  "interval_unit": "minutes",
  "is_active": true
}
```

#### Update Schedule

```http
PUT /schedules/{id}
```

#### Delete Schedule

```http
DELETE /schedules/{id}
```

### Tags

#### List Tags

```http
GET /tags
```

**Response:**
```json
[
  {
    "id": 1,
    "name": "ETL",
    "color": "#3b82f6",
    "description": "Data extraction scripts",
    "script_count": 5
  }
]
```

#### Create Tag

```http
POST /tags
```

**Request Body:**
```json
{
  "name": "Production",
  "color": "#ef4444",
  "description": "Production scripts"
}
```

#### Update Tag

```http
PUT /tags/{id}
```

#### Delete Tag

```http
DELETE /tags/{id}
```

## Error Responses

### 400 Bad Request

```json
{
  "detail": "Invalid request data",
  "errors": {
    "name": ["This field is required"]
  }
}
```

### 401 Unauthorized

```json
{
  "detail": "Invalid or missing authentication token"
}
```

### 403 Forbidden

```json
{
  "detail": "You do not have permission to access this resource"
}
```

### 404 Not Found

```json
{
  "detail": "Resource not found"
}
```

### 500 Internal Server Error

```json
{
  "detail": "An unexpected error occurred"
}
```

## Rate Limiting

Currently no rate limiting is implemented. For production use, consider implementing rate limiting middleware.

## Pagination

List endpoints support pagination:

**Query Parameters:**
- `page`: Page number (default: 1)
- `page_size`: Items per page (default: 20, max: 100)

**Response Format:**
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/v1/scripts?page=2",
  "previous": null,
  "results": [...]
}
```

## Interactive Documentation

Visit http://localhost:8000/api/docs for:
- Interactive API explorer
- Try API calls in browser
- Full request/response examples
- Schema definitions

## Code Examples

### Python

```python
import requests

API_TOKEN = "your_token_here"
BASE_URL = "http://localhost:8000/api/v1"

headers = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

# Create script
response = requests.post(
    f"{BASE_URL}/scripts",
    headers=headers,
    json={
        "name": "My Script",
        "code": "print('Hello')",
        "language": "python"
    }
)
script = response.json()

# Execute script
response = requests.post(
    f"{BASE_URL}/scripts/{script['id']}/execute",
    headers=headers
)
execution = response.json()
```

### JavaScript

```javascript
const API_TOKEN = 'your_token_here';
const BASE_URL = 'http://localhost:8000/api/v1';

const headers = {
  'Authorization': `Bearer ${API_TOKEN}`,
  'Content-Type': 'application/json'
};

// Create script
const response = await fetch(`${BASE_URL}/scripts`, {
  method: 'POST',
  headers: headers,
  body: JSON.stringify({
    name: 'My Script',
    code: 'print("Hello")',
    language: 'python'
  })
});
const script = await response.json();

// Execute script
const execResponse = await fetch(
  `${BASE_URL}/scripts/${script.id}/execute`,
  { method: 'POST', headers: headers }
);
const execution = await execResponse.json();
```

### cURL

```bash
# Store token
TOKEN="your_token_here"
BASE_URL="http://localhost:8000/api/v1"

# Create script
curl -X POST "$BASE_URL/scripts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Script",
    "code": "print(\"Hello\")",
    "language": "python"
  }'

# Execute script (replace 1 with actual script ID)
curl -X POST "$BASE_URL/scripts/1/execute" \
  -H "Authorization: Bearer $TOKEN"
```

## WebSocket API

For real-time features (requires WebSocket support):

### Notifications

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/notifications/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Notification:', data);
};
```

### Live Execution Logs

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/execution/123/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Log:', data.line);
};
```

## Best Practices

1. **Store tokens securely**: Use environment variables or secret managers
2. **Handle errors**: Always check response status codes
3. **Rate limiting**: Implement client-side rate limiting for bulk operations
4. **Pagination**: Use pagination for large result sets
5. **Webhooks**: Consider implementing webhooks for execution notifications
6. **Versioning**: API is versioned (/v1/), check for updates
