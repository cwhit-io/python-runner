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
from app.models import Script, ScriptExecution, ScriptSchedule
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

        if not name:
            messages.error(request, "Script name is required.")
            return redirect("scripts_list")

        # Check if name already exists for this user
        if Script.objects.filter(owner=request.user, name=name).exists():
            messages.error(request, "A script with this name already exists.")
            return redirect("scripts_list")

        script = Script.objects.create(
            name=name, description=description, owner=request.user
        )

        messages.success(request, f'Script "{name}" created successfully!')
        return redirect("script_edit", script_id=script.id)

    return redirect("scripts_list")


@login_required
def script_detail(request, script_id):
    """View script details and execution history."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)
    executions = script.executions.all()[:20]  # Last 20 executions
    schedules = script.schedules.all()

    return render(
        request,
        "scripts/detail.html",
        {
            "script": script,
            "executions": executions,
            "schedules": schedules,
        },
    )


@login_required
def script_edit(request, script_id):
    """Edit script code and settings."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    if request.method == "POST":
        script.name = request.POST.get("name", script.name)
        script.description = request.POST.get("description", script.description)
        script.code = request.POST.get("code", script.code)
        script.dependencies = request.POST.get("dependencies", script.dependencies)
        script.is_public = request.POST.get("is_public") == "on"

        # Handle tags - only assign existing tags
        tag_names = request.POST.getlist("tags")
        from app.models import Tag

        tags = []
        for tag_name in tag_names:
            try:
                tag = Tag.objects.get(name=tag_name, created_by=request.user)
                tags.append(tag)
            except Tag.DoesNotExist:
                # Skip tags that don't exist or don't belong to the user
                pass
        script.tags.set(tags)

        script.save()

        messages.success(request, "Script updated successfully!")
        return redirect("script_detail", script_id=script.id)

    # Get all user's tags for the form
    from app.models import Tag

    user_tags = Tag.objects.filter(created_by=request.user).order_by("name")

    return render(
        request, "scripts/edit.html", {"script": script, "user_tags": user_tags}
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
    return redirect("scripts_list")


@login_required
def script_export(request, script_id):
    """Export a script as JSON."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    # Create export data
    export_data = {
        "name": script.name,
        "description": script.description,
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

    # Execute the script
    runner = ScriptRunner(script)
    execution = runner.execute(triggered_by=request.user, trigger_type="manual")

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
def schedule_create(request, script_id):
    """Create a new schedule for a script."""
    script = get_object_or_404(Script, id=script_id, owner=request.user)

    name = request.POST.get("name", "").strip()
    cron_expression = request.POST.get("cron_expression", "").strip()
    timezone = request.POST.get("timezone", "UTC").strip()

    if not name or not cron_expression:
        messages.error(request, "Schedule name and cron expression are required.")
        return redirect("script_detail", script_id=script_id)

    try:
        schedule = ScriptSchedule.objects.create(
            script=script,
            name=name,
            cron_expression=cron_expression,
            timezone=timezone,
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

    messages.success(request, f'Schedule "{name}" deleted.')
    return redirect("script_detail", script_id=script_id)


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
        messages.success(request, f'Tag "{name}" deleted successfully!')
        return redirect("tags_list")

    return redirect("tags_list")
