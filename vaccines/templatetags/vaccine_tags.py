from django import template
import math

register = template.Library()

@register.filter
def humanize_days(days):
    """Converts days into a human-readable string (weeks, months, or years)."""
    if days is None or days == '':
        return ''
    
    try:
        days = int(days)
    except (ValueError, TypeError):
        return days

    if days == 0:
        return "Birth"
    
    if days < 0:
        return f"{days} days"

    # Conversion logic
    if days < 30:
        if days % 7 == 0:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks > 1 else ''}"
        return f"{days} day{'s' if days > 1 else ''}"
    
    if days < 365:
        # Months (approximate)
        months = round(days / 30.44, 1)
        if months.is_integer():
            months = int(months)
        
        # Check if it matches typical week milestones (6, 10, 14 weeks)
        if days in [42, 70, 98]:
            return f"{days // 7} weeks ({months} months)"
            
        return f"{months} month{'s' if months > 1 else ''}"
    
    # Years
    years = round(days / 365.25, 1)
    if years.is_integer():
        years = int(years)
    
    # Also show months if > 1 year but < 2 years for precision
    if 1 < years < 2:
        months = round(days / 30.44, 1)
        if months.is_integer():
            months = int(months)
        return f"{years} year{'s' if years > 1 else ''} ({months} months)"

    return f"{years} year{'s' if years > 1 else ''}"
