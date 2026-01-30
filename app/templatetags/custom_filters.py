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

    # Handle string inputs from {% now %} tag
    if isinstance(value, str):
        from dateutil.parser import parse as parse_dt

        try:
            value = parse_dt(value)
        except (ValueError, TypeError):
            return value  # Return original string if parsing fails

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

    # Handle string inputs from {% now %} tag
    if isinstance(value, str):
        from dateutil.parser import parse as parse_dt

        try:
            value = parse_dt(value)
        except (ValueError, TypeError):
            return value  # Return original string if parsing fails

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
    now = timezone.now().astimezone(user_tz)

    # Calculate time difference manually for better precision
    if localized_time > now:
        # Future time - calculate time until
        diff = localized_time - now
        total_seconds = int(diff.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds} seconds"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            if minutes == 0:
                return f"{hours} hour{'s' if hours != 1 else ''}"
            else:
                return f"{hours} hour{'s' if hours != 1 else ''} {minutes} minute{'s' if minutes != 1 else ''}"
        else:
            days = total_seconds // 86400
            hours = (total_seconds % 86400) // 3600
            if hours == 0:
                return f"{days} day{'s' if days != 1 else ''}"
            else:
                return f"{days} day{'s' if days != 1 else ''} {hours} hour{'s' if hours != 1 else ''}"
    else:
        # Past time - use Django's timesince
        from django.utils.timesince import timesince

        return timesince(localized_time, now)


@register.filter
def user_datetime_iso(value, user):
    """
    Format a datetime as ISO string in the user's timezone for HTML datetime-local inputs.

    Usage: {{ datetime_obj|user_datetime_iso:request.user }}
    """
    if not value or not user:
        return value

    # Handle string inputs
    if isinstance(value, str):
        from dateutil.parser import parse as parse_dt

        try:
            value = parse_dt(value)
        except (ValueError, TypeError):
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
        value = timezone.make_aware(value, timezone=pytz.UTC)

    localized_time = value.astimezone(user_tz)

    # Return ISO format for datetime-local input
    return localized_time.strftime("%Y-%m-%dT%H:%M")
