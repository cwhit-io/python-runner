from ninja import NinjaAPI
from .items import router as items_router, protected_router as protected_items_router
from .schemas import MessageSchema
from datetime import datetime

# Create main API instance
api = NinjaAPI(
    title="Django Starter API",
    version="1.0.0",
    description="A modern Django API built with Django Ninja, htmx, and daisyUI"
)


@api.get("/", response=MessageSchema, tags=["Root"])
def api_root(request):
    """API root endpoint - health check."""
    return {
        "message": "Django Ninja API is running!",
        "timestamp": datetime.now().isoformat()
    }


# Register routers
api.add_router("/items", items_router)
api.add_router("/protected/items", protected_items_router)
