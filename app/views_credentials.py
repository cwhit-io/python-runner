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
        
        if not name:
            messages.error(request, "Credential name is required.")
            return redirect("credentials_list")
        
        if not key or not value:
            messages.error(request, "Both key and value are required.")
            return redirect("credentials_list")
        
        # Check if name already exists
        if GlobalCredential.objects.filter(user=request.user, name=name).exists():
            messages.error(request, "A credential with this name already exists.")
            return redirect("credentials_list")
        
        credential = GlobalCredential.objects.create(
            user=request.user,
            name=name,
            credential_type=CredentialType.GENERIC,
        )
        credential.set_encrypted_data({"key": key, "value": value})
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