"""
Views for global credential management.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from app.models import GlobalCredential, CredentialType


@login_required
def credentials_list(request):
    """List all global credentials for the current user."""
    credentials = GlobalCredential.objects.filter(user=request.user).order_by("-updated_at")
    credential_types = [
        {"value": ct.value, "label": ct.label}
        for ct in CredentialType
    ]
    
    return render(
        request,
        "scripts/credentials_list.html",
        {
            "credentials": credentials,
            "credential_types": credential_types,
        },
    )


@login_required
def credential_create(request):
    """Create a new global credential."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        credential_type = request.POST.get("credential_type", CredentialType.GENERIC)
        
        # Build credential data based on type
        credential_data = {}
        
        if credential_type == CredentialType.API_KEY:
            credential_data["api_key"] = request.POST.get("api_key", "")
        elif credential_type == CredentialType.BEARER_TOKEN:
            credential_data["token"] = request.POST.get("token", "")
        elif credential_type == CredentialType.BASIC_AUTH:
            credential_data["username"] = request.POST.get("username", "")
            credential_data["password"] = request.POST.get("password", "")
        elif credential_type == CredentialType.OAUTH_CLIENT_CREDENTIALS:
            credential_data["client_id"] = request.POST.get("client_id", "")
            credential_data["client_secret"] = request.POST.get("client_secret", "")
            credential_data["token_url"] = request.POST.get("token_url", "")
        elif credential_type == CredentialType.GENERIC:
            credential_data["key"] = request.POST.get("key", "")
            credential_data["value"] = request.POST.get("value", "")
        
        if not name:
            messages.error(request, "Credential name is required.")
            return redirect("credentials_list")
        
        if not credential_data:
            messages.error(request, "Credential data is required.")
            return redirect("credentials_list")
        
        # Check if name already exists
        if GlobalCredential.objects.filter(user=request.user, name=name).exists():
            messages.error(request, "A credential with this name already exists.")
            return redirect("credentials_list")
        
        credential = GlobalCredential.objects.create(
            user=request.user,
            name=name,
            credential_type=credential_type,
        )
        credential.set_encrypted_data(credential_data)
        credential.save()
        
        messages.success(request, f'Credential "{name}" created successfully!')
        return redirect("credentials_list")
    
    return redirect("credentials_list")


@login_required
def credential_delete(request, credential_id):
    """Delete a global credential."""
    credential = get_object_or_404(GlobalCredential, id=credential_id, user=request.user)
    
    if request.method == "POST":
        name = credential.name
        credential.delete()
        
        if request.headers.get("HX-Request"):
            return HttpResponse(f'''
            <script>
            showToast("Credential "{name}" deleted successfully!", "success");
            setTimeout(() => {{ window.location.reload(); }}, 500);
            </script>
            ''')
        
        messages.success(request, f'Credential "{name}" deleted successfully!')
    
    return redirect("credentials_list")