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


def describe_cron_expression(cron_expression: str) -> str:
    """
    Convert a cron expression to a human-readable description.
    
    Args:
        cron_expression: A cron expression (e.g., "0 */6 * * *")
    
    Returns:
        A human-readable description of the cron expression
    
    Examples:
        >>> describe_cron_expression("0 */6 * * *")
        "Every 6 hours"
        >>> describe_cron_expression("0 0 * * 1")
        "Weekly on Monday at midnight"
        >>> describe_cron_expression("invalid")
        "Custom schedule"
    """
    try:
        parts = cron_expression.strip().split()
        
        # Basic cron format: minute hour day_of_month month day_of_week
        if len(parts) != 5:
            return "Custom schedule"
        
        minute, hour, day_of_month, month, day_of_week = parts
        
        # Common patterns
        common_patterns = {
            "* * * * *": "Every minute",
            "*/5 * * * *": "Every 5 minutes",
            "*/10 * * * *": "Every 10 minutes",
            "*/15 * * * *": "Every 15 minutes",
            "*/30 * * * *": "Every 30 minutes",
            "0 * * * *": "Every hour",
            "0 */2 * * *": "Every 2 hours",
            "0 */3 * * *": "Every 3 hours",
            "0 */4 * * *": "Every 4 hours",
            "0 */6 * * *": "Every 6 hours",
            "0 */12 * * *": "Every 12 hours",
            "0 0 * * *": "Daily at midnight",
            "0 12 * * *": "Daily at noon",
            "0 0 * * 0": "Weekly on Sunday at midnight",
            "0 0 * * 1": "Weekly on Monday at midnight",
            "0 0 1 * *": "Monthly on the 1st at midnight",
            "0 0 1 1 *": "Yearly on January 1st at midnight",
        }
        
        if cron_expression in common_patterns:
            return common_patterns[cron_expression]
        
        # Try to describe custom expressions
        description_parts = []
        
        # Minute part
        if minute == "*":
            pass  # Will be covered by hour/day descriptions
        elif "/" in minute:
            interval = minute.split("/")[1]
            description_parts.append(f"every {interval} minutes")
        elif minute.isdigit():
            pass  # Will be added with hour
        else:
            description_parts.append(f"at minutes {minute}")
        
        # Hour part
        if hour == "*":
            if not description_parts:
                description_parts.append("every hour")
        elif "/" in hour:
            interval = hour.split("/")[1]
            description_parts.append(f"every {interval} hours")
        elif hour.isdigit():
            hour_val = int(hour)
            time_str = f"{hour_val:02d}:{minute if minute.isdigit() else '00'}"
            if day_of_month == "*" and month == "*" and day_of_week == "*":
                return f"Daily at {time_str}"
            description_parts.append(f"at {time_str}")
        
        # Day of week
        if day_of_week != "*":
            days = {
                "0": "Sunday", "1": "Monday", "2": "Tuesday",
                "3": "Wednesday", "4": "Thursday", "5": "Friday", "6": "Saturday"
            }
            if day_of_week in days:
                description_parts.append(f"on {days[day_of_week]}")
        
        # Day of month
        if day_of_month != "*":
            if day_of_month.isdigit():
                description_parts.append(f"on day {day_of_month}")
        
        # Month
        if month != "*":
            months = {
                "1": "January", "2": "February", "3": "March", "4": "April",
                "5": "May", "6": "June", "7": "July", "8": "August",
                "9": "September", "10": "October", "11": "November", "12": "December"
            }
            if month in months:
                description_parts.append(f"in {months[month]}")
        
        if description_parts:
            result = " ".join(description_parts)
            return result[0].upper() + result[1:]
        
        return "Custom schedule"
    except Exception:
        return "Custom schedule"
