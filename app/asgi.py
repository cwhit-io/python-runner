"""
ASGI config for app project.

Mounts the Django app, WebSocket routing, and the MCP Streamable HTTP server.
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# Initialize Django ASGI application early to ensure the AppRegistry
# is populated before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

# ── Import routing after Django ASGI app is initialized ─────────────────
from app.routing import websocket_urlpatterns

# ── Build the MCP ASGI app (import triggers django.setup internally) ────
from app.mcp_server import create_mcp_asgi_app

mcp_asgi_app = create_mcp_asgi_app()

# ── Django + WebSocket router ───────────────────────────────────────────
_django_app = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)

# ── Top-level ASGI router ───────────────────────────────────────────────
# FastMCP's streamable_http_app() is a Starlette instance with routes:
#   /mcp                                  – MCP Streamable HTTP
#   /.well-known/oauth-protected-resource – OAuth metadata (RFC 9728)
#
# ChatGPT hits /mcp first (gets 401), then fetches the well-known metadata.
# Resource metadata URL is {resource_server_url}/.well-known/oauth-protected-resource.
# We route /mcp and /.well-known/oauth-protected-resource to FastMCP.
from starlette.types import Scope, Receive, Send


async def application(scope: Scope, receive: Receive, send: Send) -> None:
    """Route /mcp and OAuth protected-resource paths to FastMCP, rest to Django."""
    path = scope.get("path", "")
    if scope["type"] == "http" and (
        path.startswith("/mcp")
        or path.startswith("/.well-known/oauth-protected-resource")
    ):
        await mcp_asgi_app(scope, receive, send)
    else:
        await _django_app(scope, receive, send)

