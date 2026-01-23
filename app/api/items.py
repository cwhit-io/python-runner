from ninja import Router
from typing import List
from .schemas import ItemSchema, ItemCreateSchema
from ..services.item_service import ItemService
from ..auth import APITokenAuth

router = Router()
item_service = ItemService()

# Optional: Protected router that requires authentication for all routes
protected_router = Router(auth=APITokenAuth())


@router.get("/", response=List[ItemSchema], tags=["Items"])
def list_items(request):
    """List all items."""
    return item_service.get_all()


@router.get("/{item_id}", response=ItemSchema, tags=["Items"])
def get_item(request, item_id: int):
    """Get a specific item by ID."""
    item = item_service.get_by_id(item_id)
    if not item:
        return router.create_response(request, {"detail": "Item not found"}, status=404)
    return item


@router.post("/", response=ItemSchema, tags=["Items"])
def create_item(request, payload: ItemCreateSchema):
    """Create a new item."""
    return item_service.create(payload.name, payload.description)


@router.delete("/{item_id}", tags=["Items"])
def delete_item(request, item_id: int):
    """Delete an item."""
    success = item_service.delete(item_id)
    if not success:
        return router.create_response(request, {"detail": "Item not found"}, status=404)
    return {"success": True}


# Example protected endpoint - requires API token
@protected_router.get("/my-items", response=List[ItemSchema], tags=["Protected Items"])
def get_my_items(request):
    """
    Get items for the authenticated user.
    Requires: Authorization header with "Bearer <token>"
    """
    user = request.auth.user
    # In a real app, you'd filter items by user
    return item_service.get_all()
