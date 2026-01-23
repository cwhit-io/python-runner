# This file is kept for backward compatibility
# The actual API is now in app/api/__init__.py
from .api import api
from .services.item_service import items_db

__all__ = ['api', 'items_db']
