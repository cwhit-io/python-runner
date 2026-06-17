"""
View for AI-friendly instructions page.
"""

from django.shortcuts import render
from django.http import HttpResponse


def ai_instructions(request):
    """Return the AI instructions markdown file as plain text."""
    from django.template.loader import render_to_string
    
    content = render_to_string("ai_instructions.md")
    return HttpResponse(content, content_type="text/plain; charset=utf-8")
