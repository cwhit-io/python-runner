# Enhanced Execution Monitoring

## Overview
This implementation adds comprehensive execution monitoring capabilities with real-time updates, resource tracking, timeout controls, and the ability to kill running executions.

## Features Implemented

### 1. Real-time Execution Progress (WebSocket Updates)
- **WebSocket Consumer**: `ExecutionMonitorConsumer` in `app/consumers.py`
- **WebSocket Route**: `/ws/execution/<execution_id>/`
- **Frontend**: Live monitoring card on execution detail page
- **Updates Include**:
  - CPU usage percentage
  - Memory usage in MB
  - Elapsed execution time
  - Execution status changes
  - Completion notifications

### 2. Resource Usage Monitoring
- **CPU Monitoring**: Tracks current and peak CPU usage
- **Memory Monitoring**: Tracks current and peak memory usage in MB
- **Database Fields** (ScriptExecution model):
  - `peak_cpu_percent`: Peak CPU usage during execution
  - `peak_memory_mb`: Peak memory usage during execution
- **Implementation**: Uses `psutil` library for cross-platform process monitoring
- **Update Frequency**: Resource stats updated every 0.5 seconds

### 3. Execution Timeout Controls
- **Timeout Setting**: Optional timeout can be set when executing a script
- **Enforcement**: Script is automatically terminated if timeout is exceeded
- **Database Fields**:
  - `timeout_seconds`: Configured timeout in seconds
  - `timed_out`: Boolean flag indicating if execution was terminated due to timeout
- **UI**: Timeout input field in the "Run Script" modal

### 4. Kill Running Executions
- **Endpoint**: `POST /executions/<execution_id>/kill/`
- **View**: `execution_kill` in `app/views_scripts.py`
- **Function**: `kill_execution()` in `app/services/script_runner.py`
- **Process**:
  1. Attempts graceful termination (SIGTERM)
  2. Waits 0.5 seconds
  3. Force kills if still running (SIGKILL)
  4. Updates execution status to "cancelled"
  5. Sends WebSocket notification
- **UI**: "Kill" button appears on execution detail page for running executions

## Technical Implementation

### Database Schema Changes
Migration: `0009_scriptexecution_peak_cpu_percent_and_more.py`

```python
# New fields added to ScriptExecution model
peak_cpu_percent = FloatField(null=True, blank=True)
peak_memory_mb = FloatField(null=True, blank=True)
timeout_seconds = IntegerField(null=True, blank=True)
timed_out = BooleanField(default=False)
```

### Script Runner Enhancements

#### Resource Monitoring Thread
```python
def _monitor_process(self, process, start_time):
    # Monitors CPU/memory every 0.5 seconds
    # Checks for timeout
    # Sends WebSocket updates
    # Returns peak stats
```

#### WebSocket Updates
```python
def _send_websocket_update(self, message_type, data):
    # Sends updates to execution_{id} channel group
    # Message types: started, resource_update, completed, cancelled, timeout, error
```

### WebSocket Consumer
```python
class ExecutionMonitorConsumer(AsyncWebsocketConsumer):
    # Handles real-time monitoring connections
    # Group name: execution_{execution_id}
    # Broadcasts execution progress updates
```

### Frontend Integration

#### Execution Detail Page
- Live monitoring card (visible only for running executions)
- Real-time CPU, memory, and time displays
- Auto-refresh when execution completes
- Kill button for running executions

#### Script Detail Page
- Run modal with optional timeout input
- Redirects to execution detail after starting

## Usage Examples

### 1. Execute with Timeout
```python
from app.services.script_runner import execute_script

execution = execute_script(
    script_id=1,
    triggered_by=user,
    trigger_type='manual',
    timeout_seconds=300  # 5 minute timeout
)
```

### 2. Kill Running Execution
```python
from app.services.script_runner import kill_execution

success = kill_execution(execution_id=123)
# Returns True if killed, False if already completed or not found
```

### 3. WebSocket Monitoring (JavaScript)
```javascript
const socket = new WebSocket(`ws://localhost:8000/ws/execution/${executionId}/`);

socket.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'resource_update') {
        console.log(`CPU: ${data.cpu_percent}%`);
        console.log(`Memory: ${data.memory_mb} MB`);
        console.log(`Elapsed: ${data.elapsed_seconds}s`);
    } else if (data.type === 'completed') {
        console.log(`Finished with status: ${data.status}`);
    }
};
```

## Dependencies
- **psutil** (>=5.9.0): Cross-platform process and system utilities
- **channels**: WebSocket support
- **channels-redis**: Channel layer backend for broadcasting

## Testing

### Manual Testing Steps
1. **Test Timeout**:
   - Create a script with long-running operation (e.g., `import time; time.sleep(600)`)
   - Execute with 10 second timeout
   - Verify it gets cancelled after 10 seconds
   - Check `timed_out` flag is True

2. **Test Resource Monitoring**:
   - Create a script that uses CPU/memory
   - Execute and watch execution detail page
   - Verify real-time updates of CPU and memory
   - Check peak values are stored after completion

3. **Test Kill Execution**:
   - Start a long-running script
   - Click "Kill" button on execution detail page
   - Verify execution is cancelled
   - Check status changes to "cancelled"

4. **Test WebSocket Reconnection**:
   - Start an execution
   - Refresh the execution detail page
   - Verify WebSocket reconnects and shows updates

## Security Considerations
1. **Permission Checks**: Only script owners can kill executions
2. **WebSocket Auth**: Only authenticated users can connect
3. **Process Isolation**: Each execution runs in isolated process
4. **Resource Limits**: Timeout prevents runaway executions

## Performance Considerations
1. **Monitoring Overhead**: ~0.5s polling interval balances responsiveness and CPU usage
2. **WebSocket Scaling**: Use channels-redis for multi-server deployments
3. **Database Updates**: Resource stats only written on completion, not during monitoring

## Future Enhancements
- [ ] Execution queue with priority
- [ ] Concurrent execution limits per user
- [ ] Disk I/O monitoring
- [ ] Network usage tracking
- [ ] Historical resource usage charts
- [ ] Email notifications on completion/failure
- [ ] Execution log streaming (real-time stdout/stderr)
