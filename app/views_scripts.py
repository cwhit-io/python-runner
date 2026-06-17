"""
Views for script management.
"""

import json

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from app.models import Script, ScriptExecution, ScriptSchedule, Tag
from app.services.script_runner import ScriptRunner
from app.services.scheduler import schedule_job, remove_schedule
from app.services.secret_store import (
    list_script_secrets,
    get_script_secret,
    set_script_secret,
    delete_script_secret,
)


@login_required
def scripts_list(request):
    """List all scripts for the current user."""
    # Get user's own scripts and public scripts
    scripts = Script.objects.filter(owner=request.user).order_by("-updated_at")

    # Filter by tag if specified
    tag_filter = request.GET.get("tag")
    if tag_filter:
        scripts = scripts.filter(tags__name=tag_filter)

    # Get all user's tags for filter dropdown
    from app.models import Tag

    user_tags = Tag.objects.filter(created_by=request.user).order_by("name")

    # Scripts are already annotated with next_run property
    return render(
        request,
        "scripts/list.html",
        {"scripts": scripts, "user_tags": user_tags, "current_tag": tag_filter},
    )


@login_required
def script_create(request):
    """Create a new script."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        description = request.POST.get("description", "").strip()
        language = request.POST.get("language", "python")  # Default to python

        if not name:
            messages.error(request, "Script name is required.")
            return redirect("scripts_list")

        # Check if name already exists for this user
        if Script.objects.filter(owner=request.user, name=name).exists():
            messages.error(request, "A script with this name already exists.")
            return redirect("scripts_list")

        script = Script.objects.create(
            name=name, description=description, owner=request.user, language=language
        )

        messages.success(request, f'Script "{name}" created successfully!')
        return redirect("script_edit", script_id=script.id)

    return redirect("scripts_list")


@login_required
def script_detail(request, script_id):
    """View script details and execution history."""
    script = get_object_or_404(Script, id=script_id)
    from app.models import Tag, GlobalCredential

    # Check permissions: owner can always view, others can only view if public
    if script.owner != request.user and not script.is_public:
        from django.http import Http404

        raise Http404("Script not found")

    executions = script.executions.all()[:20]  # Last 20 executions
    schedules = list(script.schedules.all())

    # Compute next_run for schedules that don't have it persisted
    from app.services.scheduler import compute_next_run

    for sched in schedules:
        try:
            if not getattr(sched, "next_run", None):
                sched.next_run = compute_next_run(sched)
        except Exception:
            sched.next_run = None

    return render(
        request,
        "scripts/detail.html",
        {
            "script": script,
            "executions": executions,
            "schedules": schedules,
            "user_tags": Tag.objects.filter(created_by=request.user).order_by("name"),
            "user_credentials": GlobalCredential.objects.filter(user=request.user).order_by("name"),
        },
    )


@login_required
@require_http_methods(["POST"])
def script_toggle_public(request, script_id):
    """Toggle the public status of a script via AJAX."""
    from django.http import JsonResponse

    script = get_object_or_404(Script, id=script_id, owner=request.user)

    # Parse JSON data
    import json

    try:
        data = json.loads(request.body)
        is_public = data.get("is_public", False)
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"success": False, "error": "Invalid data"}, status=400)

    # Update the script
    script.is_public = is_public
    script.save()

    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def script_toggle_mcp(request, script_id):
    """Toggle the MCP exposure status of a script via AJAX."""
    from django.http import JsonResponse
    import json

    script = get_object_or_404(Script, id=script_id, owner=request.user)

    try:
        data = json.loads(request.body)
        expose_to_mcp = data.get("expose_to_mcp", False)
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({"success": False, "error": "Invalid data"}, status=400)

    script.expose_to_mcp = expose_to_mcp
    script.save()

    return JsonResponse({"success": True})


@login_required
@require_http_methods(["POST"])
def script_edit_inline(request, script_id):
    """Save inline-edited name/description via AJAX."""
    from django.http import JsonResponse
    import json

    script = get_object_or_404(Script, id=script_id, owner=request.user)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    if "name" in data:
        name = data["name"].strip()
        if not name:
            return JsonResponse({"success": False, "error": "Name is required"}, status=400)
        script.name = name
    if "description" in data:
        script.description = data["description"].strip()

    script.save()
    return JsonResponse({"success": True, "name": script.name, "description": script.description})


@login_required
@require_http_methods(["POST"])
def script_edit_meta(request, script_id):
    """Edit script metadata (language, visibility, tags, credentials) via HTMX."""
    from app.models import Tag, GlobalCredential
    
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    
    # Update fields (name/description edited inline on the detail page)
    script.language = request.POST.get("language", script.language)
    script.is_public = request.POST.get("is_public") == "on"
    script.expose_to_mcp = request.POST.get("expose_to_mcp") == "on"
    
    # Handle tags - only assign existing tags
    tag_names = request.POST.getlist("tags")
    tags = []
    for tag_name in tag_names:
        try:
            tag = Tag.objects.get(name=tag_name, created_by=request.user)
            tags.append(tag)
        except Tag.DoesNotExist:
            pass
    script.tags.set(tags)
    
    # Handle credentials - only assign existing credentials owned by user
    cred_ids = request.POST.getlist("credentials")
    credentials = []
    for cred_id in cred_ids:
        try:
            cred = GlobalCredential.objects.get(id=cred_id, user=request.user)
            credentials.append(cred)
        except GlobalCredential.DoesNotExist:
            pass
    script.credentials.set(credentials)
    
    script.save()
    
    # Build the PUBLIC badge outside the f-string to avoid backslash issues
    public_badge = ''
    if script.is_public:
        public_badge = '<span class=\"badge badge-sm badge-primary font-bold\">PUBLIC</span>'
    
    # Return HTMX response to update badges and close panel
    response_html = f'''
    <script>
    // Update badges
    const headerBadges = document.getElementById('header-badges');
    headerBadges.innerHTML = '{public_badge}';
    {{% for tag in script.tags.all %}}
    headerBadges.innerHTML += '<span class="badge badge-sm badge-outline opacity-80" style="border-color: {{{{ tag.color }}}}; color: {{{{ tag.color }}}};">{{{{ tag.name }}}}</span>';
    {{% endfor %}};
    
    showToast("Metadata updated successfully!", "success");
    // Hide the inline settings panel instead of closing a modal
    const settingsPanel = document.getElementById('inline-settings-panel');
    if (settingsPanel) settingsPanel.classList.add('hidden');
    const metaLabel = document.getElementById('edit-meta-label');
    if (metaLabel) metaLabel.textContent = 'Edit Metadata';
    </script>
    '''
    
    return HttpResponse(response_html)


@login_required
def script_edit(request, script_id):
    """Edit script code, dependencies, language, and credentials."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    if request.method == "POST":
        script.code = request.POST.get("code", script.code)
        script.dependencies = request.POST.get("dependencies", script.dependencies)
        script.language = request.POST.get("language", script.language)

        # Handle credentials - only assign existing credentials owned by user
        from app.models import GlobalCredential
        cred_ids = request.POST.getlist("credentials")
        if cred_ids:
            credentials = []
            for cred_id in cred_ids:
                try:
                    cred = GlobalCredential.objects.get(id=cred_id, user=request.user)
                    credentials.append(cred)
                except GlobalCredential.DoesNotExist:
                    pass
            script.credentials.set(credentials)

        script.save()

        messages.success(request, "Script updated successfully!")
        return redirect("script_detail", script_id=script.id)

    return render(
        request,
        "scripts/edit.html",
        {
            "script": script,
        },
    )


@login_required
def script_delete(request, script_id):
    """Delete a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    if request.method == "POST":
        name = script.name

        # Remove any schedules
        for schedule in script.schedules.all():
            remove_schedule(schedule)

        script.delete()

        # Check if this is an HTMX request
        if request.headers.get("HX-Request"):
            # Return HTML response with script for HTMX
            return HttpResponse(f'''
            <script>
            showToast("Script \\"{name}\\" deleted successfully!", "success");
            setTimeout(() => {{ window.location.href = "/scripts/"; }}, 1000);
            </script>
            ''')
        else:
            # Traditional redirect for non-HTMX requests
            messages.success(request, f'Script "{name}" deleted successfully!')
            return redirect("scripts_list")

    return redirect("script_detail", script_id=script_id)


@login_required
@require_http_methods(["POST"])
def script_duplicate(request, script_id):
    """Duplicate a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    # Create a copy with a new name
    base_name = script.name
    counter = 1
    new_name = f"{base_name} (Copy)"

    # Find a unique name
    while Script.objects.filter(owner=request.user, name=new_name).exists():
        counter += 1
        new_name = f"{base_name} (Copy {counter})"

    # Create the duplicate
    duplicated_script = Script.objects.create(
        name=new_name,
        description=script.description,
        language=script.language,
        code=script.code,
        dependencies=script.dependencies,
        owner=request.user,
        is_public=False,  # Duplicates are private by default
    )

    messages.success(request, f'Script "{script.name}" duplicated as "{new_name}"!')
    return redirect("script_detail", script_id=duplicated_script.id)


@login_required
@require_http_methods(["POST"])
def scripts_bulk_delete(request):
    """Bulk delete scripts."""
    script_ids = request.POST.getlist("script_ids")

    if not script_ids:
        messages.error(request, "No scripts selected.")
        return redirect("scripts_list")

    # Filter scripts to only those owned by the user
    scripts = Script.objects.filter(id__in=script_ids, owner=request.user)

    if not scripts:
        messages.error(request, "No valid scripts found.")
        return redirect("scripts_list")

    deleted_count = 0
    for script in scripts:
        # Remove any schedules
        for schedule in script.schedules.all():
            remove_schedule(schedule)
        script.delete()
        deleted_count += 1

    messages.success(request, f"Successfully deleted {deleted_count} script(s).")

    # Check if this is an HTMX request
    if request.headers.get("HX-Request"):
        # Return HTML response with script for HTMX
        return HttpResponse(f"""
        <script>
        showToast("Successfully deleted {deleted_count} script(s).", "success");
        setTimeout(() => {{ window.location.reload(); }}, 1000);
        </script>
        """)
    else:
        # Traditional redirect for non-HTMX requests
        return redirect("scripts_list")


@login_required
def script_export(request, script_id):
    """Export a script as JSON."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    # Create export data
    export_data = {
        "name": script.name,
        "description": script.description,
        "language": script.language,
        "code": script.code,
        "dependencies": script.dependencies,
        "is_public": script.is_public,
        "exported_at": timezone.now().isoformat(),
        "version": "1.0",
    }

    # Return as JSON download
    response = JsonResponse(export_data, json_dumps_params={"indent": 2})
    response["Content-Disposition"] = (
        f'attachment; filename="{script.name.replace(" ", "_")}.json"'
    )
    return response


@login_required
def script_secrets_list(request, script_id):
    """Return JSON list of secret names for this script (owner-only)."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    try:
        names = list_script_secrets(script_id)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"secrets": names})


@login_required
@require_http_methods(["POST"])
def script_secret_set(request, script_id):
    """Set/update a script secret. Params: name, value"""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    name = request.POST.get("name", "").strip()
    value = request.POST.get("value", "")
    if not name:
        return JsonResponse({"error": "Missing name"}, status=400)
    # Basic validation for secret name
    import re

    if not re.match(r"^[A-Z0-9_\-]+$", name, re.I):
        return JsonResponse(
            {"error": "Invalid name (use letters, numbers, - or _)"}, status=400
        )
    try:
        set_script_secret(script_id, name, value)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    return JsonResponse({"ok": True})


@login_required
def script_secret_get(request, script_id):
    """Return the secret value for a given name (owner-only)."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    name = request.GET.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Missing name"}, status=400)
    try:
        val = get_script_secret(script_id, name)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    if val is None:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse({"value": val})


@login_required
@require_http_methods(["POST"])
def script_secret_delete(request, script_id):
    """Delete a script secret. Params: name"""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    name = request.POST.get("name", "").strip()
    if not name:
        return JsonResponse({"error": "Missing name"}, status=400)
    try:
        ok = delete_script_secret(script_id, name)
    except RuntimeError as e:
        return JsonResponse({"error": str(e)}, status=500)
    if not ok:
        return JsonResponse({"error": "Not found"}, status=404)
    return JsonResponse({"ok": True})


@login_required
def script_import(request):
    """Import a script from JSON file."""
    if request.method == "POST":
        if "json_file" not in request.FILES:
            messages.error(request, "No file selected.")
            return redirect("scripts_list")

        json_file = request.FILES["json_file"]

        try:
            # Parse JSON
            data = json.load(json_file)

            # Validate required fields
            required_fields = ["name", "code"]
            for field in required_fields:
                if field not in data:
                    messages.error(
                        request, f"Invalid JSON format: missing '{field}' field."
                    )
                    return redirect("scripts_list")

            # Check if name already exists
            name = data["name"].strip()
            if Script.objects.filter(owner=request.user, name=name).exists():
                # Create a unique name
                base_name = name
                counter = 1
                while Script.objects.filter(owner=request.user, name=name).exists():
                    counter += 1
                    name = f"{base_name} (Import {counter})"

            # Create the script
            script = Script.objects.create(
                name=name,
                description=data.get("description", ""),
                language=data.get("language", "python"),
                code=data.get("code", ""),
                dependencies=data.get("dependencies", ""),
                is_public=data.get("is_public", False),
                owner=request.user,
            )

            messages.success(request, f'Script "{script.name}" imported successfully!')
            return redirect("script_detail", script_id=script.id)

        except json.JSONDecodeError:
            messages.error(request, "Invalid JSON file format.")
        except Exception as e:
            messages.error(request, f"Error importing script: {str(e)}")

        return redirect("scripts_list")

    return redirect("scripts_list")


@login_required
@require_http_methods(["POST"])
def script_execute(request, script_id):
    """Execute a script manually."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    # Get optional timeout from form, default to 10 minutes (600 seconds)
    timeout_seconds = request.POST.get("timeout_seconds", "").strip()
    if timeout_seconds:
        try:
            timeout_seconds = int(timeout_seconds)
            if timeout_seconds <= 0:
                timeout_seconds = 600  # Default to 10 minutes
        except (ValueError, TypeError):
            timeout_seconds = 600  # Default to 10 minutes
    else:
        timeout_seconds = 600  # Default to 10 minutes

    # Execute the script
    runner = ScriptRunner(script)
    execution = runner.execute(
        triggered_by=request.user,
        trigger_type="manual",
        timeout_seconds=timeout_seconds,
    )

    # Check if this is an HTMX request
    if request.headers.get("HX-Request"):
        # Return HTML response with HTMX redirect header
        response = HttpResponse(f'''
        <script>
        showToast("{script.name} execution started!", "success");
        </script>
        ''')
        # Use HX-Redirect header to navigate after request completes
        response["HX-Redirect"] = f"/executions/{execution.id}/"
        return response
    else:
        # Traditional redirect for non-HTMX requests
        messages.success(request, f'Script "{script.name}" execution started!')
        return redirect("execution_detail", execution_id=execution.id)


@login_required
def execution_detail(request, execution_id):
    """View execution details."""
    execution = get_object_or_404(ScriptExecution, id=execution_id)

    # Check if user has permission to view this execution
    if execution.script.owner != request.user:
        messages.error(request, "You do not have permission to view this execution.")
        return redirect("scripts_list")

    return render(request, "scripts/execution_detail.html", {"execution": execution})


@login_required
@require_http_methods(["POST"])
def execution_kill(request, execution_id):
    """Kill a running execution."""
    execution = get_object_or_404(ScriptExecution, id=execution_id)

    # Check if user has permission
    if execution.script.owner != request.user:
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>showToast("You do not have permission to kill this execution.", "error");</script>'
            )
        messages.error(request, "You do not have permission to kill this execution.")
        return redirect("scripts_list")

    # Try to kill the execution
    from app.services.script_runner import kill_execution

    if kill_execution(execution_id):
        if request.headers.get("HX-Request"):
            return HttpResponse(f"""
            <script>
            showToast("Execution #{execution_id} cancelled successfully!", "success");
            // Update the status after a short delay
            setTimeout(() => {{ location.reload(); }}, 1000);
            </script>
            """)
        messages.success(request, "Execution cancelled successfully!")
    else:
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<script>showToast("Failed to cancel execution. It may have already completed.", "error");</script>'
            )
        messages.error(
            request, "Failed to cancel execution. It may have already completed."
        )

    return redirect("execution_detail", execution_id=execution_id)


@login_required
@require_http_methods(["POST"])
def schedule_create(request, script_id):
    """Create a new schedule for a script or update an existing one."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    schedule_id = request.POST.get("schedule_id", "").strip()

    # Check if this is an update
    if schedule_id:
        try:
            schedule = get_object_or_404(
                ScriptSchedule, id=schedule_id, script__owner=request.user
            )
            is_update = True
        except (ValueError, ScriptSchedule.DoesNotExist):
            messages.error(request, "Schedule not found.")
            return redirect("script_detail", script_id=script_id)
    else:
        is_update = False

    name = request.POST.get("name", "").strip()
    interval_unit = request.POST.get("interval_unit", "").strip()
    start_datetime = request.POST.get("start_datetime", "").strip()

    if not name:
        messages.error(request, "Schedule name is required.")
        return redirect("script_detail", script_id=script_id)

    # Determine schedule type based on whether interval_unit is provided
    if interval_unit:
        schedule_type = "interval"
    else:
        schedule_type = "single"

    # Validate required fields
    if not start_datetime:
        messages.error(request, "Start date/time is required.")
        return redirect("script_detail", script_id=script_id)

    try:
        # Parse the datetime string (user's local time)
        from dateutil.parser import parse as parse_dt
        from django.utils import timezone as django_tz
        import pytz

        # Get user's timezone preference
        user_tz_str = (
            getattr(request.user.profile, "timezone", "UTC")
            if hasattr(request.user, "profile")
            else "UTC"
        )
        try:
            user_tz = pytz.timezone(user_tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.UTC

        # Parse the datetime as if it's in user's timezone
        dt = parse_dt(start_datetime)
        if dt.tzinfo is None:
            # Assume the input is in user's timezone
            dt = user_tz.localize(dt)

        # Convert to UTC for storage
        dt_utc = dt.astimezone(pytz.UTC)

        if is_update:
            # Update existing schedule
            schedule.name = name
            schedule.timezone = user_tz_str
            schedule.schedule_type = schedule_type
            schedule.start_datetime = dt_utc
            schedule.interval_unit = interval_unit if interval_unit else ""
            schedule.interval_value = 1
            schedule.save()

            # Remove old job and add new one
            remove_schedule(schedule)
            schedule_job(schedule)

            messages.success(request, f'Schedule "{name}" updated successfully!')
        else:
            # Create new schedule
            schedule = ScriptSchedule.objects.create(
                script=script,
                name=name,
                timezone=user_tz_str,  # Store user's timezone for reference
                schedule_type=schedule_type,
                start_datetime=dt_utc,
                interval_unit=interval_unit if interval_unit else "",
                interval_value=1,
                created_by=request.user,
            )

            # Add to scheduler
            schedule_job(schedule)

            messages.success(request, f'Schedule "{name}" created successfully!')
    except Exception as e:
        messages.error(request, f"Failed to create schedule: {str(e)}")

    return redirect("script_detail", script_id=script_id)


@login_required
@require_http_methods(["POST"])
def schedule_toggle(request, schedule_id):
    """Toggle a schedule active/inactive."""
    schedule = get_object_or_404(ScriptSchedule, id=schedule_id)

    # Check permission
    if schedule.script.owner != request.user:
        messages.error(request, "You do not have permission to modify this schedule.")
        return redirect("scripts_list")

    schedule.is_active = not schedule.is_active
    schedule.save()

    if schedule.is_active:
        schedule_job(schedule)
        messages.success(request, f'Schedule "{schedule.name}" activated.')
    else:
        remove_schedule(schedule)
        messages.success(request, f'Schedule "{schedule.name}" deactivated.')

    # Redirect back to the referring page or script detail
    referer = request.META.get("HTTP_REFERER", "")
    if "schedules" in referer and "schedules/create" not in referer:
        return redirect("schedules_list")
    return redirect("script_detail", script_id=schedule.script.id)


@login_required
@require_http_methods(["POST"])
def schedule_delete(request, schedule_id):
    """Delete a schedule."""
    schedule = get_object_or_404(ScriptSchedule, id=schedule_id)

    # Check permission
    if schedule.script.owner != request.user:
        messages.error(request, "You do not have permission to delete this schedule.")
        return redirect("scripts_list")

    script_id = schedule.script.id
    name = schedule.name

    remove_schedule(schedule)
    schedule.delete()

    # Check if this is an HTMX request
    if request.headers.get("HX-Request"):
        # Return HTML response with script for HTMX
        return HttpResponse(f'''
        <script>
        showToast("Schedule \\"{name}\\" deleted.", "success");
        setTimeout(() => {{ window.location.reload(); }}, 500);
        </script>
        ''')
    else:
        # Traditional redirect for non-HTMX requests
        messages.success(request, f'Schedule "{name}" deleted.')
        # Redirect back to the referring page or script detail
        referer = request.META.get("HTTP_REFERER", "")
        if "schedules" in referer and "schedules/create" not in referer:
            return redirect("schedules_list")
        return redirect("script_detail", script_id=script_id)


@login_required
def schedules_list(request):
    """List all schedules for all user's scripts with filtering, sorting, and pagination."""
    from django.core.paginator import Paginator
    from django.db.models import Q

    # Get query parameters
    search_query = request.GET.get("q", "").strip()
    tag_filter = request.GET.get("tag", "").strip()
    sort_by = request.GET.get("sort", "created_at")
    sort_order = request.GET.get("order", "desc")
    page_number = request.GET.get("page", 1)

    # Base queryset
    schedules = (
        ScriptSchedule.objects.filter(script__owner=request.user)
        .select_related("script", "created_by")
        .prefetch_related("script__tags")
    )

    # Apply filters
    if search_query:
        schedules = schedules.filter(
            Q(name__icontains=search_query) | Q(script__name__icontains=search_query)
        )

    if tag_filter:
        schedules = schedules.filter(script__tags__name__iexact=tag_filter)

    # Apply sorting
    sort_field = sort_by
    if sort_order == "desc":
        sort_field = f"-{sort_field}"

    # Handle special sort fields
    if sort_by == "script_name":
        sort_field = "script__name" if sort_order == "asc" else "-script__name"
    elif sort_by == "status":
        # Sort by is_active first, then by next_run
        schedules = schedules.order_by(
            "-is_active" if sort_order == "desc" else "is_active",
            "-next_run" if sort_order == "desc" else "next_run",
        )
        sort_field = None  # Already sorted
    elif sort_by == "type":
        sort_field = "schedule_type" if sort_order == "asc" else "-schedule_type"
    elif sort_by == "next_run":
        # Handle null values - put nulls at the end
        schedules = schedules.order_by(f"{'-' if sort_order == 'desc' else ''}next_run")
        sort_field = None
    elif sort_by == "last_run":
        # Handle null values - put nulls at the end
        schedules = schedules.order_by(f"{'-' if sort_order == 'desc' else ''}last_run")
        sort_field = None

    if sort_field:
        schedules = schedules.order_by(sort_field)

    # Get all user's scripts for the create schedule dropdown
    scripts = Script.objects.filter(owner=request.user).order_by("name")

    # Get all tags for filter dropdown
    tags = Tag.objects.filter(scripts__owner=request.user).distinct().order_by("name")

    # Compute next_run for schedules that don't have it persisted
    from app.services.scheduler import compute_next_run

    for sched in schedules:
        try:
            if not getattr(sched, "next_run", None):
                sched.next_run = compute_next_run(sched)
        except Exception:
            sched.next_run = None

    # Pagination
    paginator = Paginator(schedules, 25)  # 25 items per page
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    # Count active schedules from filtered results
    active_count = schedules.filter(is_active=True).count()

    # Find next scheduled run from filtered results
    next_schedule = None
    active_schedules = schedules.filter(
        is_active=True, next_run__isnull=False
    ).order_by("next_run")
    if active_schedules.exists():
        next_schedule = active_schedules.first()

    return render(
        request,
        "scripts/schedules_list.html",
        {
            "schedules": page_obj,
            "scripts": scripts,
            "tags": tags,
            "active_count": active_count,
            "next_schedule": next_schedule,
            "now": timezone.now(),
            "search_query": search_query,
            "tag_filter": tag_filter,
            "sort_by": sort_by,
            "sort_order": sort_order,
            "page_obj": page_obj,
        },
    )


@login_required
@require_http_methods(["POST"])
def schedule_create_from_list(request):
    """Create a new schedule or update an existing one from the schedules list page."""
    script_id = request.POST.get("script_id", "").strip()
    schedule_id = request.POST.get("schedule_id", "").strip()

    # Check if this is an update
    if schedule_id:
        try:
            schedule = get_object_or_404(
                ScriptSchedule, id=schedule_id, script__owner=request.user
            )
            is_update = True
        except (ValueError, ScriptSchedule.DoesNotExist):
            messages.error(request, "Schedule not found.")
            return redirect("schedules_list")
    else:
        is_update = False
        if not script_id:
            messages.error(request, "Script is required.")
            return redirect("schedules_list")

        try:
            script = get_object_or_404(Script, id=script_id, owner=request.user)
        except (ValueError, Script.DoesNotExist):
            messages.error(request, "Invalid script selected.")
            return redirect("schedules_list")

    name = request.POST.get("name", "").strip()
    interval_unit = request.POST.get("interval_unit", "").strip()
    start_datetime = request.POST.get("start_datetime", "").strip()

    if not name:
        messages.error(request, "Schedule name is required.")
        return redirect("schedules_list")

    # Determine schedule type based on whether interval_unit is provided
    if interval_unit:
        schedule_type = "interval"
    else:
        schedule_type = "single"

    # Validate required fields
    if not start_datetime:
        messages.error(request, "Start date/time is required.")
        return redirect("schedules_list")

    try:
        # Parse the datetime string (user's local time)
        from dateutil.parser import parse as parse_dt
        from django.utils import timezone as django_tz
        import pytz

        # Get user's timezone preference
        user_tz_str = (
            getattr(request.user.profile, "timezone", "UTC")
            if hasattr(request.user, "profile")
            else "UTC"
        )
        try:
            user_tz = pytz.timezone(user_tz_str)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.UTC

        # Parse the datetime as if it's in user's timezone
        dt = parse_dt(start_datetime)
        if dt.tzinfo is None:
            # Assume the input is in user's timezone
            dt = user_tz.localize(dt)

        # Convert to UTC for storage
        dt_utc = dt.astimezone(pytz.UTC)

        if is_update:
            # Update existing schedule
            schedule.name = name
            schedule.schedule_type = schedule_type
            schedule.start_datetime = dt_utc
            schedule.interval_unit = interval_unit if interval_unit else ""
            schedule.interval_value = 1
            schedule.save()

            # Remove and re-add to scheduler to update the job
            from app.services.scheduler import remove_schedule, schedule_job

            remove_schedule(schedule)
            schedule_job(schedule)

            messages.success(request, f'Schedule "{name}" updated successfully!')
        else:
            # Create new schedule
            schedule = ScriptSchedule.objects.create(
                script=script,
                name=name,
                timezone=user_tz_str,  # Store user's timezone for reference
                schedule_type=schedule_type,
                start_datetime=dt_utc,
                interval_unit=interval_unit if interval_unit else "",
                interval_value=1,
                created_by=request.user,
            )

            # Add to scheduler
            from app.services.scheduler import schedule_job

            schedule_job(schedule)

            messages.success(
                request, f'Schedule "{name}" created successfully for "{script.name}"!'
            )
    except Exception as e:
        messages.error(
            request,
            f"Failed to {'update' if is_update else 'create'} schedule: {str(e)}",
        )

    return redirect("schedules_list")


# Tag Management Views


@login_required
def tags_list(request):
    """List all tags for the current user."""
    from app.models import Tag

    tags = Tag.objects.filter(created_by=request.user).order_by("name")
    return render(request, "scripts/tags_list.html", {"tags": tags})


@login_required
def tag_create(request):
    """Create a new tag."""
    from app.models import Tag

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        color = request.POST.get("color", "#3B82F6").strip()
        description = request.POST.get("description", "").strip()

        if not name:
            messages.error(request, "Tag name is required.")
            return redirect("tags_list")

        # Check if name already exists for this user
        if Tag.objects.filter(created_by=request.user, name=name).exists():
            messages.error(request, "A tag with this name already exists.")
            return redirect("tags_list")

        Tag.objects.create(
            name=name,
            color=color,
            description=description,
            created_by=request.user,
        )

        messages.success(request, f'Tag "{name}" created successfully!')
        return redirect("tags_list")

    return redirect("tags_list")


@login_required
def tag_edit(request, tag_id):
    """Edit a tag."""
    from app.models import Tag

    tag = get_object_or_404(Tag, id=tag_id, created_by=request.user)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        color = request.POST.get("color", tag.color).strip()
        description = request.POST.get("description", tag.description).strip()

        if not name:
            messages.error(request, "Tag name is required.")
            return redirect("tag_edit", tag_id=tag.id)

        # Check if name already exists for this user (excluding current tag)
        if (
            Tag.objects.filter(created_by=request.user, name=name)
            .exclude(id=tag.id)
            .exists()
        ):
            messages.error(request, "A tag with this name already exists.")
            return redirect("tag_edit", tag_id=tag.id)

        tag.name = name
        tag.color = color
        tag.description = description
        tag.save()

        messages.success(request, f'Tag "{name}" updated successfully!')
        return redirect("tags_list")

    return render(request, "scripts/tag_edit.html", {"tag": tag})


@login_required
def tag_delete(request, tag_id):
    """Delete a tag."""
    from app.models import Tag

    tag = get_object_or_404(Tag, id=tag_id, created_by=request.user)

    if request.method == "POST":
        name = tag.name
        tag.delete()

        # Check if this is an HTMX request
        if request.headers.get("HX-Request"):
            # Return HTML response with script for HTMX
            return HttpResponse(f'''
            <script>
            showToast("Tag \\"{name}\\" deleted successfully!", "success");
            setTimeout(() => {{ window.location.reload(); }}, 500);
            </script>
            ''')
        else:
            # Traditional redirect for non-HTMX requests
            messages.success(request, f'Tag "{name}" deleted successfully!')
            return redirect("tags_list")

    return redirect("tags_list")


@login_required
def script_test(request, script_id):
    """Save code/dependencies then run the script."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    if request.method == "POST":
        # Only save code and dependencies (metadata is edited on the detail page)
        script.code = request.POST.get("code", script.code)
        script.dependencies = request.POST.get("dependencies", script.dependencies)
        script.save()

        # Run the test
        try:
            runner = ScriptRunner(script)
            execution = runner.execute(triggered_by=request.user, trigger_type="test")
            messages.success(request, f'Script saved and test execution started (ID: {execution.id})')
            success = True
        except Exception as e:
            messages.error(request, f'Script saved but test execution failed: {str(e)}')
            success = False

        # If AJAX request, return JSON response
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            from django.http import JsonResponse
            return JsonResponse({'status': 'success' if success else 'error'})
        
        # Regular request - redirect to detail page
        return redirect("script_detail", script_id=script.id)

    return HttpResponse("Method not allowed", status=405)
