"""
Views for global credential management.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db.models import Count
from django.views.decorators.http import require_POST
from app.models import GlobalCredential, CredentialType


def _normalize_field_key(key: str) -> str:
    return key.strip().upper().replace(" ", "_")


def _build_credential_payload(field_key: str, value: str) -> dict:
    return {_normalize_field_key(field_key): value}


@login_required
def credentials_list(request):
    """List all global credentials for the current user."""
    credentials = (
        GlobalCredential.objects.filter(user=request.user)
        .annotate(script_count=Count("scripts"))
        .prefetch_related("scripts")
        .order_by("-updated_at")
    )

    return render(
        request,
        "scripts/credentials_list.html",
        {"credentials": credentials},
    )


@login_required
def credential_create(request):
    """Create a new global credential."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        key = request.POST.get("key", "").strip()
        value = request.POST.get("value", "").strip()

        is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"

        def _fail(error: str, status: int = 400):
            if is_ajax:
                return JsonResponse({"success": False, "error": error}, status=status)
            messages.error(request, error)
            return redirect("credentials_list")

        if not name:
            return _fail("Credential name is required.")

        if not key or not value:
            return _fail("Both key and value are required.")

        if GlobalCredential.objects.filter(user=request.user, name=name).exists():
            return _fail("A credential with this name already exists.")

        credential = GlobalCredential.objects.create(
            user=request.user,
            name=name,
            credential_type=CredentialType.GENERIC,
        )
        credential.set_encrypted_data(_build_credential_payload(key, value))
        credential.save()

        if is_ajax:
            return JsonResponse(
                {
                    "success": True,
                    "credential": {
                        "id": credential.id,
                        "name": credential.name,
                        "primary_key": credential.get_credential_keys()[0],
                        "env_var": credential.get_env_var_names()[0],
                    },
                }
            )

        messages.success(request, f'Credential "{name}" created successfully!')
        return redirect("credentials_list")

    return redirect("credentials_list")


@login_required
@require_POST
def credential_edit(request, credential_id):
    """Update an existing credential (AJAX or form POST)."""
    credential = get_object_or_404(
        GlobalCredential, id=credential_id, user=request.user
    )

    name = request.POST.get("name", "").strip()
    key = request.POST.get("key", "").strip()
    value = request.POST.get("value", "").strip()

    if not name:
        error = "Credential name is required."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect("credentials_list")

    if (
        GlobalCredential.objects.filter(user=request.user, name=name)
        .exclude(id=credential.id)
        .exists()
    ):
        error = "A credential with this name already exists."
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": error}, status=400)
        messages.error(request, error)
        return redirect("credentials_list")

    credential.name = name

    existing = credential.get_credential_data()
    if credential.credential_type == CredentialType.GENERIC:
        if not key and existing:
            key = next(iter(existing.keys()))
        if not key:
            error = "Key is required."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error}, status=400)
            messages.error(request, error)
            return redirect("credentials_list")

        secret = value
        if not secret and existing:
            if len(existing) == 1:
                secret = next(iter(existing.values()))
            else:
                old_secret = existing.get(_normalize_field_key(key))
                if old_secret is None and existing:
                    secret = next(iter(existing.values()))
                else:
                    secret = old_secret or ""

        if not secret:
            error = "Value is required when creating a new key mapping."
            if request.headers.get("X-Requested-With") == "XMLHttpRequest":
                return JsonResponse({"success": False, "error": error}, status=400)
            messages.error(request, error)
            return redirect("credentials_list")

        credential.set_encrypted_data(_build_credential_payload(key, secret))

    credential.save()

    primary_key = credential.get_credential_keys()[0]
    env_var = credential.get_env_var_names()[0]

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse(
            {
                "success": True,
                "credential": {
                    "id": credential.id,
                    "name": credential.name,
                    "primary_key": primary_key,
                    "env_var": env_var,
                    "script_count": credential.scripts.count(),
                    "updated_at": credential.updated_at.strftime("%b %d, %Y"),
                },
            }
        )

    messages.success(request, f'Credential "{name}" updated successfully!')
    return redirect("credentials_list")


@login_required
def credential_delete(request, credential_id):
    """Delete a global credential."""
    credential = get_object_or_404(
        GlobalCredential, id=credential_id, user=request.user
    )

    if request.method == "POST":
        name = credential.name
        credential.delete()

        if request.headers.get("HX-Request"):
            return HttpResponse(
                f'''
            <script>
            showToast("Credential "{name}" deleted successfully!", "success");
            setTimeout(() => {{ window.location.reload(); }}, 500);
            </script>
            '''
            )

        messages.success(request, f'Credential "{name}" deleted successfully!')

    return redirect("credentials_list")