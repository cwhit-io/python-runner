# In-memory storage (replace with database models in production)
items_db = [
    {"id": 1, "name": "Sample Item 1", "description": "First example item"},
    {"id": 2, "name": "Sample Item 2", "description": "Second example item"},
]


class ItemService:
    """Service layer for item operations."""
    
    def get_all(self):
        """Get all items."""
        return items_db
    
    def get_by_id(self, item_id: int):
        """Get item by ID."""
        for item in items_db:
            if item["id"] == item_id:
                return item
        return None
    
    def create(self, name: str, description: str = None):
        """Create a new item."""
        new_id = max([item["id"] for item in items_db]) + 1 if items_db else 1
        new_item = {
            "id": new_id,
            "name": name,
            "description": description
        }
        items_db.append(new_item)
        return new_item
    
    def update(self, item_id: int, name: str = None, description: str = None):
        """Update an existing item."""
        for item in items_db:
            if item["id"] == item_id:
                if name is not None:
                    item["name"] = name
                if description is not None:
                    item["description"] = description
                return item
        return None
    
    def delete(self, item_id: int):
        """Delete an item by ID."""
        global items_db
        original_length = len(items_db)
        items_db = [item for item in items_db if item["id"] != item_id]
        return len(items_db) < original_length
