"""
Views for script management.
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from app.models import Script, ScriptExecution, ScriptSchedule
from app.services.script_runner import ScriptRunner
from app.services.scheduler import schedule_job, remove_schedule


@login_required
def scripts_list(request):
    """List all scripts for the current user."""
    # Get user's own scripts and public scripts
    scripts = Script.objects.filter(
        owner=request.user
    ).order_by('-updated_at')
    
    return render(request, 'scripts/list.html', {'scripts': scripts})


@login_required
def script_create(request):
    """Create a new script."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        if not name:
            messages.error(request, 'Script name is required.')
            return redirect('scripts_list')
        
        # Check if name already exists for this user
        if Script.objects.filter(owner=request.user, name=name).exists():
            messages.error(request, 'A script with this name already exists.')
            return redirect('scripts_list')
        
        script = Script.objects.create(
            name=name,
            description=description,
            owner=request.user
        )
        
        messages.success(request, f'Script "{name}" created successfully!')
        return redirect('script_edit', script_id=script.id)
    
    return redirect('scripts_list')


@login_required
def script_detail(request, script_id):
    """View script details and execution history."""
    from app.utils.helpers import describe_cron_expression
    
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    executions = script.executions.all()[:20]  # Last 20 executions
    schedules = script.schedules.all()
    
    # Add human-readable descriptions to schedules
    for schedule in schedules:
        schedule.human_description = describe_cron_expression(schedule.cron_expression)
    
    # Generate API call examples for the script
    # Get the request's host for building the full URL
    protocol = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    api_base_url = f"{protocol}://{host}/api/v1"
    
    api_examples = {
        'curl': f'''curl -X POST "{api_base_url}/scripts/{script.id}/execute" \\
  -H "Authorization: Bearer YOUR_API_TOKEN" \\
  -H "Content-Type: application/json"''',
        'javascript': f'''fetch("{api_base_url}/scripts/{script.id}/execute", {{
  method: "POST",
  headers: {{
    "Authorization": "Bearer YOUR_API_TOKEN",
    "Content-Type": "application/json"
  }}
}})
.then(response => response.json())
.then(data => console.log(data));''',
        'python': f'''import requests

url = "{api_base_url}/scripts/{script.id}/execute"
headers = {{
    "Authorization": "Bearer YOUR_API_TOKEN",
    "Content-Type": "application/json"
}}

response = requests.post(url, headers=headers)
print(response.json())''',
        'n8n': f'''// In n8n HTTP Request node:
// Method: POST
// URL: {api_base_url}/scripts/{script.id}/execute
// Authentication: Generic Credential Type
//   Header Auth:
//     Name: Authorization
//     Value: Bearer YOUR_API_TOKEN''',
    }
    
    return render(request, 'scripts/detail.html', {
        'script': script,
        'executions': executions,
        'schedules': schedules,
        'api_examples': api_examples,
    })


@login_required
def script_edit(request, script_id):
    """Edit script code and settings."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    
    if request.method == 'POST':
        script.name = request.POST.get('name', script.name)
        script.description = request.POST.get('description', script.description)
        script.code = request.POST.get('code', script.code)
        script.dependencies = request.POST.get('dependencies', script.dependencies)
        script.is_public = request.POST.get('is_public') == 'on'
        script.save()
        
        messages.success(request, 'Script updated successfully!')
        return redirect('script_detail', script_id=script.id)
    
    return render(request, 'scripts/edit.html', {'script': script})


@login_required
def script_delete(request, script_id):
    """Delete a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    
    if request.method == 'POST':
        name = script.name
        
        # Remove any schedules
        for schedule in script.schedules.all():
            remove_schedule(schedule)
        
        script.delete()
        messages.success(request, f'Script "{name}" deleted successfully!')
        return redirect('scripts_list')
    
    return redirect('script_detail', script_id=script_id)


@login_required
@require_http_methods(['POST'])
def script_execute(request, script_id):
    """Execute a script manually."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    
    # Execute the script
    runner = ScriptRunner(script)
    execution = runner.execute(triggered_by=request.user, trigger_type='manual')
    
    messages.success(request, f'Script "{script.name}" execution started!')
    return redirect('execution_detail', execution_id=execution.id)


@login_required
def execution_detail(request, execution_id):
    """View execution details."""
    execution = get_object_or_404(ScriptExecution, id=execution_id)
    
    # Check if user has permission to view this execution
    if execution.script.owner != request.user:
        messages.error(request, 'You do not have permission to view this execution.')
        return redirect('scripts_list')
    
    return render(request, 'scripts/execution_detail.html', {'execution': execution})


@login_required
@require_http_methods(['POST'])
def schedule_create(request, script_id):
    """Create a new schedule for a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    
    name = request.POST.get('name', '').strip()
    cron_expression = request.POST.get('cron_expression', '').strip()
    timezone = request.POST.get('timezone', 'UTC').strip()
    
    if not name or not cron_expression:
        messages.error(request, 'Schedule name and cron expression are required.')
        return redirect('script_detail', script_id=script_id)
    
    try:
        schedule = ScriptSchedule.objects.create(
            script=script,
            name=name,
            cron_expression=cron_expression,
            timezone=timezone,
            created_by=request.user
        )
        
        # Add to scheduler
        schedule_job(schedule)
        
        messages.success(request, f'Schedule "{name}" created successfully!')
    except Exception as e:
        messages.error(request, f'Failed to create schedule: {str(e)}')
    
    return redirect('script_detail', script_id=script_id)


@login_required
@require_http_methods(['POST'])
def schedule_toggle(request, schedule_id):
    """Toggle a schedule active/inactive."""
    schedule = get_object_or_404(ScriptSchedule, id=schedule_id)
    
    # Check permission
    if schedule.script.owner != request.user:
        messages.error(request, 'You do not have permission to modify this schedule.')
        return redirect('scripts_list')
    
    schedule.is_active = not schedule.is_active
    schedule.save()
    
    if schedule.is_active:
        schedule_job(schedule)
        messages.success(request, f'Schedule "{schedule.name}" activated.')
    else:
        remove_schedule(schedule)
        messages.success(request, f'Schedule "{schedule.name}" deactivated.')
    
    return redirect('script_detail', script_id=schedule.script.id)


@login_required
@require_http_methods(['POST'])
def schedule_delete(request, schedule_id):
    """Delete a schedule."""
    schedule = get_object_or_404(ScriptSchedule, id=schedule_id)
    
    # Check permission
    if schedule.script.owner != request.user:
        messages.error(request, 'You do not have permission to delete this schedule.')
        return redirect('scripts_list')
    
    script_id = schedule.script.id
    name = schedule.name
    
    remove_schedule(schedule)
    schedule.delete()
    
    messages.success(request, f'Schedule "{name}" deleted.')
    return redirect('script_detail', script_id=script_id)
