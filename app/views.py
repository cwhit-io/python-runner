from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login, authenticate
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .services.item_service import items_db
from .models import UserProfile, APIToken
from .forms import UserProfileForm
from .api import api


def index(request):
    """Main page with htmx integration."""
    return render(request, "index.html")


def websocket_demo(request):
    """WebSocket demo page."""
    return render(request, "websocket_demo.html")


def register_view(request):
    """User registration view."""
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Ensure profile exists (signal should create it, but just in case)
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.send_verification_email(request)
            username = form.cleaned_data.get("username")
            messages.success(
                request,
                f"Account created for {username}! Please check your email to verify your account.",
            )
            return redirect("login")
    else:
        form = UserCreationForm()
    return render(request, "registration/register.html", {"form": form})


def verify_email(request, token):
    """Verify user email with token."""
    try:
        profile = UserProfile.objects.get(email_verification_token=token)
        profile.email_verified = True
        profile.email_verification_token = ""
        profile.save()
        messages.success(request, "Your email has been verified! You can now login.")
        return redirect("login")
    except UserProfile.DoesNotExist:
        messages.error(request, "Invalid verification token.")
        return redirect("index")


@login_required
def resend_verification(request):
    """Resend email verification link."""
    # Ensure profile exists
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if profile.email_verified:
        messages.info(request, "Your email is already verified.")
    else:
        profile.send_verification_email(request)
        messages.success(request, "Verification email sent! Check your inbox.")
    return redirect("profile")


@login_required
def profile(request):
    """User profile view."""
    # Ensure profile exists
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    return render(request, "profile.html", {"user": request.user})


@login_required
def profile_edit(request):
    """Edit user profile."""
    # Ensure profile exists
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated!")
            return redirect("profile")
    else:
        form = UserProfileForm(instance=profile)
    return render(request, "profile_edit.html", {"form": form})


@login_required
def api_tokens(request):
    """Manage API tokens."""
    tokens = APIToken.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "api_tokens.html", {"tokens": tokens})


def api_docs(request):
    """API documentation index page with links to different documentation formats."""
    return render(request, "api_docs.html")


def api_docs_swagger(request):
    """Swagger UI documentation."""
    from ninja.openapi.docs import Swagger

    swagger = Swagger()
    return swagger.render_page(request, api)


def api_docs_redoc(request):
    """Redoc documentation."""
    from ninja.openapi.docs import Redoc

    redoc = Redoc()
    return redoc.render_page(request, api)


@login_required
def create_api_token(request):
    """Create a new API token."""
    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        if not name:
            messages.error(request, "Token name is required.")
            return redirect("api_tokens")

        token = APIToken.objects.create(user=request.user, name=name)
        messages.success(request, f"API token created! Copy it now: {token.token}")
        return redirect("api_tokens")
    return redirect("api_tokens")


@login_required
def toggle_api_token(request, token_id):
    """Toggle API token active state."""
    token = get_object_or_404(APIToken, id=token_id, user=request.user)
    token.is_active = not token.is_active
    token.save()
    status = "activated" if token.is_active else "deactivated"
    messages.success(request, f'API token "{token.name}" {status}.')
    return redirect("api_tokens")


@login_required
def delete_api_token(request, token_id):
    """Delete an API token."""
    token = get_object_or_404(APIToken, id=token_id, user=request.user)
    name = token.name
    token.delete()

    messages.success(request, f'API token "{name}" deleted successfully!')
    return redirect("api_tokens")


@login_required
@require_http_methods(["POST"])
def update_theme(request):
    """Update user's theme preference."""
    theme = request.POST.get("theme", "light")
    if theme:
        # Ensure profile exists
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.theme_preference = theme
        profile.save()
    return HttpResponse(status=204)


@require_http_methods(["GET"])
def list_items_htmx(request):
    """Return HTML fragment of items list for htmx."""
    if not items_db:
        return HttpResponse('<div class="alert">No items yet. Add one above!</div>')

    items_html = ""
    for item in items_db:
        items_html += f"""
        <div class="alert alert-info flex justify-between items-center" id="item-{item["id"]}">
            <div>
                <strong>{item["name"]}</strong>
                {f"<span class='text-sm opacity-70'> - {item['description']}</span>" if item.get("description") else ""}
            </div>
            <button class="btn btn-error btn-sm" 
                    hx-delete="/items/{item["id"]}/delete/" 
                    hx-target="#item-{item["id"]}" 
                    hx-swap="outerHTML swap:1s">
                Delete
            </button>
        </div>
        """
    return HttpResponse(items_html)


@require_http_methods(["POST"])
def add_item_htmx(request):
    """Add new item and return HTML fragment for htmx."""
    name = request.POST.get("name", "").strip()
    description = request.POST.get("description", "").strip()

    if not name:
        return HttpResponse(
            '<div class="alert alert-error">Name is required</div>', status=400
        )

    # Create new item
    new_id = max([item["id"] for item in items_db]) + 1 if items_db else 1
    new_item = {
        "id": new_id,
        "name": name,
        "description": description if description else None,
    }
    items_db.append(new_item)

    # Return HTML fragment for the new item
    return HttpResponse(f"""
    <div class="alert alert-info flex justify-between items-center" id="item-{new_item["id"]}">
        <div>
            <strong>{new_item["name"]}</strong>
            {f"<span class='text-sm opacity-70'> - {new_item['description']}</span>" if new_item.get("description") else ""}
        </div>
        <button class="btn btn-error btn-sm" 
                hx-delete="/items/{new_item["id"]}/delete/" 
                hx-target="#item-{new_item["id"]}" 
                hx-swap="outerHTML swap:1s">
            Delete
        </button>
    </div>
    """)


@require_http_methods(["DELETE"])
def delete_item_htmx(request, item_id):
    """Delete item and return empty response for htmx."""
    global items_db
    original_length = len(items_db)
    items_db = [item for item in items_db if item["id"] != item_id]

    if len(items_db) == original_length:
        return HttpResponse(
            '<div class="alert alert-error">Item not found</div>', status=404
        )

    # Return empty response - htmx will swap out the element
    return HttpResponse("")
