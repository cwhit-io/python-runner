"""
Utility functions and helpers for the application.
"""


def sanitize_string(text: str) -> str:
    """Remove leading/trailing whitespace and normalize."""
    return text.strip() if text else ""


def generate_slug(text: str) -> str:
    """Generate URL-friendly slug from text."""
    import re
    text = text.lower()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-')
