"""
Custom template tags and filters for the application.
"""

from django import template
from django.utils import timezone
import pytz
from datetime import datetime

register = template.Library()


@register.filter
def user_datetime(value, user):
    """
    Format a datetime according to the user's timezone and time format preferences.

    Usage: {{ datetime_obj|user_datetime:request.user }}
    """
    if not value or not user:
        return value

    # Get user's timezone preference, default to UTC
    user_tz_str = (
        getattr(user.profile, "timezone", "UTC") if hasattr(user, "profile") else "UTC"
    )
    try:
        user_tz = pytz.timezone(user_tz_str)
    except pytz.exceptions.UnknownTimeZoneError:
        user_tz = pytz.UTC

    # Convert to user's timezone
    if timezone.is_naive(value):
        # Assume UTC if naive
        value = timezone.make_aware(value, timezone=pytz.UTC)

    localized_time = value.astimezone(user_tz)

    # Get user's time format preference
    time_format = (
        getattr(user.profile, "time_format", "24") if hasattr(user, "profile") else "24"
    )

    if time_format == "12":
        # 12-hour format with AM/PM
        return localized_time.strftime("%b %d, %Y %I:%M %p")
    else:
        # 24-hour format
        return localized_time.strftime("%b %d, %Y %H:%M")


@register.filter
def user_timesince(value, user):
    """
    Format a timesince according to the user's timezone.

    Usage: {{ datetime_obj|user_timesince:request.user }}
    """
    if not value or not user:
        return value

    # Get user's timezone preference, default to UTC
    user_tz_str = (
        getattr(user.profile, "timezone", "UTC") if hasattr(user, "profile") else "UTC"
    )
    try:
        user_tz = pytz.timezone(user_tz_str)
    except pytz.exceptions.UnknownTimeZoneError:
        user_tz = pytz.UTC

    # Convert to user's timezone for timesince calculation
    if timezone.is_naive(value):
        value = timezone.make_aware(value, timezone=pytz.UTC)

    localized_time = value.astimezone(user_tz)

    # Use Django's timesince but with localized time
    from django.utils.timesince import timesince

    now = timezone.now().astimezone(user_tz)

    return timesince(localized_time, now)
