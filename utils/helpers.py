"""
Helper utilities for the Date-Planner Agent system.
"""
import os
import logging
from datetime import datetime
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


def get_env_variable(key: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    """
    Safely retrieve environment variable.

    Args:
        key: Environment variable key
        default: Default value if not found
        required: If True, raises error when not found

    Returns:
        Environment variable value or default

    Raises:
        ValueError: If required=True and variable not found
    """
    value = os.getenv(key, default)

    if required and not value:
        raise ValueError(f"Required environment variable '{key}' is not set")

    return value


def generate_plan_id() -> str:
    """Generate a unique plan ID"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"plan_{timestamp}"


def parse_date_time(date_str: str) -> dict:
    """
    Parse flexible date/time strings into structured format.

    Examples:
        "Saturday 7pm" -> {"day": "Saturday", "time": "19:00"}
        "2024-02-10 19:00" -> {"date": "2024-02-10", "time": "19:00"}

    Args:
        date_str: Date/time string in various formats

    Returns:
        Dictionary with parsed date/time components
    """
    date_str = date_str.lower().strip()

    # Simple keyword extraction (can be enhanced with dateutil.parser)
    result = {
        "original": date_str,
        "day": None,
        "time": None,
        "date": None
    }

    # Extract day of week
    days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for day in days:
        if day in date_str:
            result["day"] = day.capitalize()
            break

    # Extract time (basic pattern matching)
    import re
    time_patterns = [
        r'(\d{1,2})\s*(am|pm)',
        r'(\d{1,2}):(\d{2})\s*(am|pm)?',
        r'(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})'
    ]

    for pattern in time_patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            result["time"] = match.group(0)
            break

    return result


def calculate_price_bracket(budget_per_person: Optional[float]) -> int:
    """
    Convert budget to Google Places price_level (1-4).

    Args:
        budget_per_person: Budget in local currency

    Returns:
        Price level (1=cheap, 2=moderate, 3=expensive, 4=very expensive)
    """
    if not budget_per_person:
        return 2  # Default to moderate

    # Assuming INR (adjust for other currencies)
    if budget_per_person < 500:
        return 1
    elif budget_per_person < 1500:
        return 2
    elif budget_per_person < 3000:
        return 3
    else:
        return 4


def format_budget_display(amount: float, currency: str = "INR") -> str:
    """Format budget amount for display"""
    if currency == "INR":
        return f"₹{amount:,.0f}"
    elif currency == "USD":
        return f"${amount:,.2f}"
    else:
        return f"{currency} {amount:,.2f}"


def extract_city_coordinates(city: str) -> dict:
    """
    Get approximate coordinates for major cities (fallback before geocoding).
    In production, use a geocoding API.

    Args:
        city: City name

    Returns:
        Dictionary with lat/lon
    """
    # Major Indian cities (expand as needed)
    city_coords = {
        "mumbai": {"lat": 19.0760, "lon": 72.8777, "country": "IN"},
        "delhi": {"lat": 28.7041, "lon": 77.1025, "country": "IN"},
        "bangalore": {"lat": 12.9716, "lon": 77.5946, "country": "IN"},
        "bengaluru": {"lat": 12.9716, "lon": 77.5946, "country": "IN"},
        "pune": {"lat": 18.5204, "lon": 73.8567, "country": "IN"},
        "hyderabad": {"lat": 17.3850, "lon": 78.4867, "country": "IN"},
        "chennai": {"lat": 13.0827, "lon": 80.2707, "country": "IN"},
        "kolkata": {"lat": 22.5726, "lon": 88.3639, "country": "IN"},
        "ahmedabad": {"lat": 23.0225, "lon": 72.5714, "country": "IN"},
        "jaipur": {"lat": 26.9124, "lon": 75.7873, "country": "IN"},
        "goa": {"lat": 15.2993, "lon": 74.1240, "country": "IN"},
    }

    city_key = city.lower().strip()
    return city_coords.get(city_key, {"lat": 0.0, "lon": 0.0, "country": "UNKNOWN"})


def is_venue_open(opening_hours: Optional[list], target_day: str, target_time: str) -> bool:
    """
    Check if venue is open at target day/time.

    Args:
        opening_hours: List of opening hours strings
        target_day: Day of week (e.g., "Saturday")
        target_time: Time (e.g., "19:00")

    Returns:
        True if venue is likely open, False otherwise
    """
    if not opening_hours:
        return True  # Assume open if no hours provided

    # Simple heuristic (can be enhanced with proper parsing)
    for hours in opening_hours:
        if target_day.lower() in hours.lower():
            # Basic check if "closed" is mentioned
            if "closed" in hours.lower():
                return False

    return True  # Default to True


def generate_google_maps_url(place_name: str, address: str) -> str:
    """Generate Google Maps URL for a place"""
    import urllib.parse
    query = f"{place_name}, {address}"
    encoded_query = urllib.parse.quote(query)
    return f"https://www.google.com/maps/search/?api=1&query={encoded_query}"


def generate_safety_checklist(venue_name: str, time: str) -> list:
    """Generate safety checklist based on context"""
    checklist = [
        "Share live location with a trusted friend or family member",
        "Choose a public, well-lit venue",
        "Arrange your own transportation",
        "Keep emergency contacts handy",
        "Trust your instincts - leave if uncomfortable"
    ]

    # Add time-specific advice
    if "night" in time.lower() or "pm" in time.lower():
        hour = int(time.split(":")[0]) if ":" in time else 0
        if hour >= 21 or hour <= 4:  # Late night
            checklist.append("Inform someone about your expected return time")
            checklist.append("Book a verified cab service for return journey")

    return checklist


def log_agent_action(agent_name: str, action: str, details: str = ""):
    """Structured logging for agent actions"""
    logger = get_logger(agent_name)
    logger.info(f"{action} | {details}")
