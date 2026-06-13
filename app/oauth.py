"""
OAuth2 authorization server for ChatGPT MCP integration.

Provides:
  GET  /oauth/authorize/  – User-facing authorization page (login required)
  POST /oauth/token/      – Token exchange endpoint (authorization_code → access_token)
"""

import secrets
import json
import time
from urllib.parse import urlencode, urlparse, parse_qs

import json
from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseBadRequest
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.cache import cache
from django.conf import settings

from .models import APIToken

# ── helpers ──────────────────────────────────────────────────────────────

AUTH_CODE_EXPIRY = 300  # 5 minutes


def _generate_auth_code(client_id: str, user_id: int, redirect_uri: str) -> str:
    """Create and store a short-lived authorization code."""
    code = secrets.token_urlsafe(32)
    cache.set(
        f"oauth_code:{code}",
        {"client_id": client_id, "user_id": user_id, "redirect_uri": redirect_uri},
        timeout=AUTH_CODE_EXPIRY,
    )
    return code


def _consume_auth_code(code: str) -> dict | None:
    """Retrieve and delete an authorization code (one-time use)."""
    key = f"oauth_code:{code}"
    data = cache.get(key)
    if data is not None:
        cache.delete(key)
    return data


# ── views ────────────────────────────────────────────────────────────────


@login_required
@require_http_methods(["GET", "POST"])
def authorize(request):
    """OAuth2 authorization endpoint.

    ChatGPT redirects the user here.  The user must be logged in already
    (Django session).  They see a consent page and click "Allow".

    Query parameters (from ChatGPT):
        client_id      – OAuth client identifier from registration
        redirect_uri   – where ChatGPT expects us to send the auth code
        response_type  – must be "code"
        state          – CSRF token from ChatGPT (echoed back)
    """
    client_id = request.GET.get("client_id", "") or request.POST.get("client_id", "")
    redirect_uri = request.GET.get("redirect_uri", "") or request.POST.get("redirect_uri", "")

    if request.method == "GET":
        # Validate client_id if provided
        if client_id:
            client_data = cache.get(f"oauth_client:{client_id}")
            if client_data is None:
                return HttpResponseBadRequest("Invalid client_id")
        return _render_consent(request)

    # POST → user clicked "Allow"
    if request.POST.get("action") != "allow":
        sep = "&" if "?" in redirect_uri else "?"
        return redirect(f"{redirect_uri}{sep}error=access_denied")

    state = request.POST.get("state") or request.GET.get("state", "")

    if not redirect_uri:
        return HttpResponseBadRequest("Missing redirect_uri")

    # Generate a short-lived auth code
    code = _generate_auth_code(client_id, request.user.id, redirect_uri)

    # Redirect back to ChatGPT
    sep = "&" if "?" in redirect_uri else "?"
    params = urlencode({"code": code, "state": state})
    return redirect(f"{redirect_uri}{sep}{params}")


def _render_consent(request):
    """Render a simple consent page."""
    scopes = [
        ("script:read", "View your scripts and executions"),
        ("script:write", "Create, edit, and delete your scripts"),
        ("script:execute", "Run your scripts"),
    ]
    ctx = {
        "app_name": "ChatGPT / MCP Client",
        "scopes": scopes,
        "redirect_uri": request.GET.get("redirect_uri", ""),
        "client_id": request.GET.get("client_id", ""),
        "state": request.GET.get("state", ""),
    }
    return render(request, "oauth/authorize.html", ctx)


@csrf_exempt
@require_http_methods(["POST"])
def token(request):
    """OAuth2 token endpoint.

    ChatGPT POSTs here to exchange an authorization code for an access token.
    Also supports client_credentials grant for server-to-server flows.

    POST data (form-encoded):
        grant_type    – "authorization_code" or "client_credentials"
        code          – auth code (required for authorization_code)
        client_id     – ignored (we use existing token infra)
        client_secret – ignored
    """
    body = request.POST.dict()

    # Support client_secret_basic auth (Authorization: Basic base64(client_id:client_secret))
    client_id = body.get("client_id", "")
    client_secret = body.get("client_secret", "")
    import base64 as _b64
    auth_header = request.META.get("HTTP_AUTHORIZATION", "")
    if auth_header.startswith("Basic "):
        try:
            decoded = _b64.b64decode(auth_header[6:]).decode("utf-8")
            cid, csec = decoded.split(":", 1)
            if not client_id:
                client_id = cid
            if not client_secret:
                client_secret = csec
        except Exception:
            pass

    grant_type = body.get("grant_type", "authorization_code")

    if grant_type == "authorization_code":
        code = body.get("code", "")

        data = _consume_auth_code(code)
        if data is None:
            return JsonResponse(
                {"error": "invalid_grant", "error_description": "Invalid or expired authorization code"},
                status=400,
            )

        # Validate client credentials if a client_id was used
        if client_id:
            client_data = cache.get(f"oauth_client:{client_id}")
            if client_data is None:
                return JsonResponse(
                    {"error": "invalid_client", "error_description": "Unknown client"},
                    status=401,
                )
            if client_secret != client_data["client_secret"]:
                return JsonResponse(
                    {"error": "invalid_client", "error_description": "Invalid client secret"},
                    status=401,
                )

        # Create an API token for this user
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=data["user_id"])
        api_token = APIToken.objects.create(
            user=user,
            name=f"ChatGPT MCP ({time.strftime('%Y-%m-%d %H:%M')})",
        )

        return JsonResponse(
            {
                "access_token": api_token.token,
                "token_type": "Bearer",
                "expires_in": 86400 * 365,  # long-lived; user can revoke via UI
                "scope": "script:read script:write script:execute",
            }
        )

    elif grant_type == "client_credentials":
        # For direct API token-based auth
        from django.contrib.auth import get_user_model
        User = get_user_model()
        # Try to get user from basic auth
        import base64
        auth_header = request.META.get("HTTP_AUTHORIZATION", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                username, password = decoded.split(":", 1)
                user = authenticate(username=username, password=password)
                if user is None:
                    return JsonResponse({"error": "invalid_client"}, status=401)
                api_token = APIToken.objects.create(
                    user=user,
                    name=f"ChatGPT MCP Client ({time.strftime('%Y-%m-%d %H:%M')})",
                )
                return JsonResponse(
                    {
                        "access_token": api_token.token,
                        "token_type": "Bearer",
                        "expires_in": 86400 * 365,
                        "scope": "script:read script:write script:execute",
                    }
                )
            except Exception:
                pass

        return JsonResponse({"error": "unsupported_grant_type"}, status=400)

    return JsonResponse({"error": "unsupported_grant_type"}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def register_client(request):
    """Dynamic OAuth client registration endpoint.

    ChatGPT POSTs its client metadata here to obtain a client_id and client_secret.
    """
    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        body = request.POST.dict()

    client_name = body.get("client_name", "ChatGPT MCP Client")
    redirect_uris = body.get("redirect_uris", [])
    grant_types = body.get("grant_types", ["authorization_code"])

    # Generate a client_id and client_secret
    import secrets
    client_id = secrets.token_urlsafe(24)
    client_secret = secrets.token_urlsafe(48)

    # Store in cache (persist across requests; for production use the DB)
    cache.set(
        f"oauth_client:{client_id}",
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "grant_types": grant_types,
        },
        timeout=None,  # no expiry
    )

    now_ts = int(time.time())
    return JsonResponse(
        {
            "client_id": client_id,
            "client_secret": client_secret,
            "client_id_issued_at": now_ts,
            "client_secret_expires_at": 0,  # never expires
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "grant_types": grant_types,
            "token_endpoint_auth_method": "client_secret_basic",
            "scopes": ["script:read", "script:write", "script:execute"],
        },
        status=201,
    )
