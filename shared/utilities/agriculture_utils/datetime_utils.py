# shared/utilities/agriculture_utils/datetime_utils.py
"""Date and time utilities for agriculture applications"""

from datetime import datetime, timedelta, date, time
from typing import Optional, Union, Tuple, Dict, Any, List
import pytz
import re


def format_timestamp(
    dt: Optional[datetime] = None,
    format_str: str = "%Y-%m-%d %H:%M:%S",
    timezone: str = "UTC"
) -> str:
    """
    Format datetime to string
    
    Args:
        dt: Datetime object (defaults to current UTC time)
        format_str: Format string
        timezone: Target timezone
        
    Returns:
        Formatted timestamp string
    """
    
    if dt is None:
        dt = datetime.utcnow()
    
    # Convert to specified timezone if not UTC
    if timezone != "UTC":
        tz = pytz.timezone(timezone)
        dt = dt.replace(tzinfo=pytz.UTC).astimezone(tz)
    
    return dt.strftime(format_str)


def parse_iso_date(date_string: str) -> Optional[datetime]:
    """
    Parse ISO format date string
    
    Args:
        date_string: ISO format date string
        
    Returns:
        Datetime object or None
    """
    
    # Try different ISO formats
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
    ]
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_string, fmt)
            if fmt == "%Y-%m-%d":
                dt = dt.replace(hour=0, minute=0, second=0)
            return dt
        except ValueError:
            continue
    
    return None


def get_season_for_date(dt: datetime, hemisphere: str = "northern") -> str:
    """
    Determine growing season based on date and hemisphere
    
    Args:
        dt: Date to check
        hemisphere: "northern" or "southern"
        
    Returns:
        Season name
    """
    
    month = dt.month
    
    if hemisphere == "northern":
        if month in [12, 1, 2]:
            return "winter"
        elif month in [3, 4, 5]:
            return "spring"
        elif month in [6, 7, 8]:
            return "summer"
        else:
            return "autumn"
    else:
        if month in [12, 1, 2]:
            return "summer"
        elif month in [3, 4, 5]:
            return "autumn"
        elif month in [6, 7, 8]:
            return "winter"
        else:
            return "spring"


def calculate_growing_degree_days(
    daily_temps: List[float],
    base_temp: float = 10,
    upper_threshold: Optional[float] = 30
) -> float:
    """
    Calculate growing degree days (GDD)
    
    Args:
        daily_temps: List of daily average temperatures
        base_temp: Base temperature for crop growth
        upper_threshold: Upper temperature threshold
        
    Returns:
        Total GDD
    """
    
    gdd = 0.0
    
    for temp in daily_temps:
        # Apply upper threshold if set
        if upper_threshold and temp > upper_threshold:
            temp = upper_threshold
        
        # Calculate daily GDD
        daily_gdd = max(0, temp - base_temp)
        gdd += daily_gdd
    
    return gdd


def estimate_harvest_date(
    planting_date: date,
    days_to_maturity: int,
    gdd_required: Optional[float] = None,
    daily_temps: Optional[List[float]] = None
) -> date:
    """
    Estimate harvest date based on planting date
    
    Args:
        planting_date: Date of planting
        days_to_maturity: Average days to maturity
        gdd_required: Required GDD (alternative to days)
        daily_temps: Daily temperatures for GDD calculation
        
    Returns:
        Estimated harvest date
    """
    
    if gdd_required and daily_temps:
        # Use GDD method
        accumulated_gdd = 0
        current_date = planting_date
        days_passed = 0
        
        while accumulated_gdd < gdd_required and days_passed < 365:
            # Get temperature for this day (simplified - would need forecast)
            temp = daily_temps[days_passed] if days_passed < len(daily_temps) else 15
            daily_gdd = max(0, temp - 10)  # Base temp of 10°C
            accumulated_gdd += daily_gdd
            current_date += timedelta(days=1)
            days_passed += 1
        
        return current_date
    else:
        # Use days to maturity
        return planting_date + timedelta(days=days_to_maturity)


def get_optimal_planting_window(
    location_lat: float,
    crop_type: str,
    year: int
) -> Tuple[date, date]:
    """
    Get optimal planting window based on location and crop
    
    Args:
        location_lat: Latitude
        crop_type: Type of crop
        year: Year
        
    Returns:
        Tuple of (start_date, end_date) for planting window
    """
    
    # Default windows (simplified)
    windows = {
        "maize": ((3, 1), (5, 15)),      # March 1 - May 15
        "tomato": ((3, 15), (6, 1)),     # March 15 - June 1
        "cassava": ((4, 1), (7, 1)),     # April 1 - July 1
        "wheat": ((9, 1), (10, 15)),     # September 1 - October 15
    }
    
    # Adjust for southern hemisphere
    if location_lat < 0:  # Southern hemisphere
        adjusted_windows = {
            "maize": ((9, 1), (11, 15)),
            "tomato": ((9, 15), (12, 1)),
            "cassava": ((10, 1), (1, 1)),
            "wheat": ((3, 1), (4, 15)),
        }
        windows = adjusted_windows
    
    start_month, start_day = windows.get(crop_type.lower(), ((1, 1), (12, 31)))[0]
    end_month, end_day = windows.get(crop_type.lower(), ((1, 1), (12, 31)))[1]
    
    start_date = date(year, start_month, start_day)
    end_date = date(year if end_month >= start_month else year + 1, end_month, end_day)
    
    return (start_date, end_date)


def format_duration_ago(dt: datetime) -> str:
    """
    Format datetime as human-readable duration ago
    
    Args:
        dt: Past datetime
        
    Returns:
        String like "2 hours ago"
    """
    
    now = datetime.utcnow()
    diff = now - dt
    
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    elif seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"
    else:
        return dt.strftime("%B %d, %Y")


def is_within_season(
    dt: datetime,
    start_month: int,
    end_month: int,
    include_edge_months: bool = True
) -> bool:
    """
    Check if date falls within growing season
    
    Args:
        dt: Date to check
        start_month: Starting month (1-12)
        end_month: Ending month (1-12)
        include_edge_months: Include start/end months
        
    Returns:
        True if within season
    """
    
    month = dt.month
    
    if start_month <= end_month:
        if include_edge_months:
            return start_month <= month <= end_month
        else:
            return start_month < month < end_month
    else:
        # Season spans year boundary
        if include_edge_months:
            return month >= start_month or month <= end_month
        else:
            return month > start_month or month < end_month


def get_next_irrigation_date(
    last_irrigation: date,
    crop_type: str,
    soil_type: str,
    recent_rainfall_mm: float = 0
) -> date:
    """
    Estimate next irrigation date based on crop and soil
    
    Args:
        last_irrigation: Last irrigation date
        crop_type: Type of crop
        soil_type: Soil type (clay, loam, sandy)
        recent_rainfall_mm: Recent rainfall in mm
        
    Returns:
        Recommended next irrigation date
    """
    
    # Water requirements by crop (days between irrigation)
    irrigation_intervals = {
        "maize": 7,
        "tomato": 5,
        "cassava": 14,
        "wheat": 10,
    }
    
    # Adjust for soil type
    soil_factors = {
        "clay": 1.5,    # Holds water longer
        "loam": 1.0,    # Normal
        "sandy": 0.5,   # Drains quickly
    }
    
    base_interval = irrigation_intervals.get(crop_type.lower(), 7)
    soil_factor = soil_factors.get(soil_type.lower(), 1.0)
    
    # Calculate adjusted interval
    adjusted_interval = base_interval * soil_factor
    
    # Reduce interval based on rainfall (rainfall > 10mm counts as irrigation)
    if recent_rainfall_mm > 10:
        adjusted_interval += 2  # Delay irrigation due to rain
    
    next_irrigation = last_irrigation + timedelta(days=int(adjusted_interval))
    
    return next_irrigation


def parse_agricultural_date(date_string: str) -> Optional[date]:
    """
    Parse agricultural date formats (e.g., "2024-SPRING", "2024-Q1")
    
    Args:
        date_string: Date string in agricultural format
        
    Returns:
        Date object or None
    """
    
    patterns = {
        r'(\d{4})-SPRING': lambda m: date(int(m[1]), 3, 20),
        r'(\d{4})-SUMMER': lambda m: date(int(m[1]), 6, 20),
        r'(\d{4})-FALL': lambda m: date(int(m[1]), 9, 20),
        r'(\d{4})-WINTER': lambda m: date(int(m[1]), 12, 20),
        r'(\d{4})-Q(\d)': lambda m: date(int(m[1]), {1: 3, 2: 6, 3: 9, 4: 12}[int(m[2])], 1),
        r'(\d{4})-(\d{2})-(\d{2})': lambda m: date(int(m[1]), int(m[2]), int(m[3])),
    }
    
    for pattern, converter in patterns.items():
        match = re.match(pattern, date_string.upper())
        if match:
            return converter(match.groups())
    
    return None