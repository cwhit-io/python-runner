from ninja import NinjaAPI
from .items import router as items_router, protected_router as protected_items_router
from .scripts import router as scripts_router
from .mcp import router as mcp_router
from .schemas import MessageSchema
from django.utils import timezone

# Create main API instance
api = NinjaAPI(
    title="Python Script Runner API",
    version="1.0.0",
    description="Centralized Python script manager with web UI, scheduling, and isolated venvs",
)


@api.get("/", response=MessageSchema, tags=["Root"])
def api_root(request):
    """API root endpoint - health check."""
    return {
        "message": "Python Script Runner API is running!",
        "timestamp": timezone.now().isoformat(),
    }


@api.get("/server-time/", tags=["Debug"])
def server_time(request):
    """Get current server time in the configured timezone (America/New_York)."""
    now = timezone.now()
    return {"server_time": now.strftime("%Y-%m-%d %H:%M:%S"), "timezone": "America/New_York"}


# Register routers
api.add_router("/items", items_router)
api.add_router("/protected/items", protected_items_router)
api.add_router("/v1", scripts_router)
api.add_router("/v1/mcp", mcp_router)
