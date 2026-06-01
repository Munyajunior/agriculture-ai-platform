# shared/utilities/agriculture_utils/validators.py
"""Validation utilities for agriculture platform"""

import re
from typing import Optional, Tuple, List, Dict, Any, Union
from pathlib import Path
import imghdr
import magic
from PIL import Image


def validate_image(
    image_data: Union[bytes, Path, str],
    max_size_mb: int = 10,
    allowed_formats: List[str] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate image file
    
    Args:
        image_data: Image bytes, file path, or URL
        max_size_mb: Maximum file size in MB
        allowed_formats: List of allowed formats (jpg, png, etc.)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    
    allowed_formats = allowed_formats or ['jpeg', 'jpg', 'png', 'webp']
    
    try:
        # Handle different input types
        if isinstance(image_data, (str, Path)):
            # Check if file exists
            if not Path(image_data).exists():
                return False, "Image file does not exist"
            
            # Check file size
            size_bytes = Path(image_data).stat().st_size
            size_mb = size_bytes / (1024 * 1024)
            if size_mb > max_size_mb:
                return False, f"Image too large: {size_mb:.1f}MB (max {max_size_mb}MB)"
            
            # Check format
            file_format = imghdr.what(image_data)
            if file_format not in allowed_formats:
                return False, f"Unsupported format: {file_format}"
            
            # Try to open with PIL to verify integrity
            try:
                with Image.open(image_data) as img:
                    img.verify()
            except Exception as e:
                return False, f"Corrupted image: {str(e)}"
            
        elif isinstance(image_data, bytes):
            # Check size
            size_mb = len(image_data) / (1024 * 1024)
            if size_mb > max_size_mb:
                return False, f"Image too large: {size_mb:.1f}MB"
            
            # Check format using magic bytes
            mime = magic.from_buffer(image_data[:1024], mime=True)
            if not any(fmt in mime for fmt in allowed_formats):
                return False, f"Unsupported format: {mime}"
        
        return True, None
        
    except Exception as e:
        return False, f"Image validation failed: {str(e)}"


def validate_coordinates(
    lat: float,
    lon: float,
    allow_invalid: bool = False
) -> Tuple[bool, Optional[str]]:
    """
    Validate geographic coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        allow_invalid: Allow out-of-range values
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    
    if allow_invalid and (lat == 0 and lon == 0):
        return True, None
    
    if not isinstance(lat, (int, float)):
        return False, "Latitude must be a number"
    
    if not isinstance(lon, (int, float)):
        return False, "Longitude must be a number"
    
    if lat < -90 or lat > 90:
        return False, f"Invalid latitude: {lat} (must be between -90 and 90)"
    
    if lon < -180 or lon > 180:
        return False, f"Invalid longitude: {lon} (must be between -180 and 180)"
    
    return True, None


def validate_crop_type(crop_type: str, allowed_crops: List[str] = None) -> bool:
    """
    Validate crop type
    
    Args:
        crop_type: Crop type string
        allowed_crops: List of allowed crops
        
    Returns:
        True if valid
    """
    
    allowed_crops = allowed_crops or ['tomato', 'cassava', 'maize', 'wheat', 'rice', 'soybean']
    
    return crop_type.lower() in allowed_crops


def validate_disease_type(
    disease_type: str,
    allowed_diseases: List[str] = None
) -> bool:
    """
    Validate disease type
    
    Args:
        disease_type: Disease type string
        allowed_diseases: List of allowed diseases
        
    Returns:
        True if valid
    """
    
    allowed_diseases = allowed_diseases or [
        'tomato_early_blight', 'tomato_late_blight', 'tomato_leaf_mold',
        'cassava_mosaic', 'cassava_brown_streak', 'maize_rust',
        'maize_northern_leaf_blight', 'healthy'
    ]
    
    return disease_type.lower() in allowed_diseases


def validate_phone_number(phone: str, country_code: str = None) -> bool:
    """
    Validate phone number format
    
    Args:
        phone: Phone number string
        country_code: Optional country code for validation
        
    Returns:
        True if valid
    """
    
    # Remove spaces, dashes, parentheses
    cleaned = re.sub(r'[\s\-\(\)]+', '', phone)
    
    # Check if it starts with +
    if cleaned.startswith('+'):
        # International format
        pattern = r'^\+[1-9]\d{6,14}$'
    elif country_code:
        # With country code but no +
        pattern = rf'^{country_code}\d{{6,12}}$'
    else:
        # Local format
        pattern = r'^\d{7,12}$'
    
    return bool(re.match(pattern, cleaned))


def validate_email(email: str) -> bool:
    """
    Validate email address format
    
    Args:
        email: Email address
        
    Returns:
        True if valid
    """
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(
    password: str,
    min_length: int = 8,
    require_uppercase: bool = True,
    require_lowercase: bool = True,
    require_digits: bool = True,
    require_special: bool = False
) -> Tuple[bool, List[str]]:
    """
    Validate password strength
    
    Args:
        password: Password string
        min_length: Minimum length
        require_uppercase: Require uppercase letters
        require_lowercase: Require lowercase letters
        require_digits: Require digits
        require_special: Require special characters
        
    Returns:
        Tuple of (is_valid, list_of_issues)
    """
    
    issues = []
    
    if len(password) < min_length:
        issues.append(f"Password must be at least {min_length} characters long")
    
    if require_uppercase and not re.search(r'[A-Z]', password):
        issues.append("Password must contain at least one uppercase letter")
    
    if require_lowercase and not re.search(r'[a-z]', password):
        issues.append("Password must contain at least one lowercase letter")
    
    if require_digits and not re.search(r'\d', password):
        issues.append("Password must contain at least one digit")
    
    if require_special and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        issues.append("Password must contain at least one special character")
    
    return len(issues) == 0, issues


def validate_field_id(field_id: str) -> bool:
    """
    Validate field/crop ID format
    
    Args:
        field_id: Field identifier
        
    Returns:
        True if valid
    """
    
    # UUID format or custom format like F-12345
    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
    custom_pattern = r'^[A-Z]{1,3}-\d{3,6}$'
    
    return bool(re.match(uuid_pattern, field_id)) or bool(re.match(custom_pattern, field_id))


def validate_confidence_score(confidence: float) -> bool:
    """
    Validate confidence score
    
    Args:
        confidence: Confidence score (0-1)
        
    Returns:
        True if valid
    """
    
    return isinstance(confidence, (int, float)) and 0 <= confidence <= 1


def validate_model_version(version: str) -> bool:
    """
    Validate model version format (e.g., 1.2.3)
    
    Args:
        version: Version string
        
    Returns:
        True if valid
    """
    
    pattern = r'^\d+(\.\d+)*$'
    return bool(re.match(pattern, version))


def validate_device_id(device_id: str) -> bool:
    """
    Validate device identifier
    
    Args:
        device_id: Device ID
        
    Returns:
        True if valid
    """
    
    # Allow alphanumeric, dash, underscore
    pattern = r'^[a-zA-Z0-9\-_]{8,64}$'
    return bool(re.match(pattern, device_id))


def validate_json_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate JSON data against schema
    
    Args:
        data: Data to validate
        schema: JSON schema
        
    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    
    errors = []
    
    for field, rules in schema.items():
        # Check required
        if rules.get('required', False) and field not in data:
            errors.append(f"Missing required field: {field}")
            continue
        
        if field in data:
            value = data[field]
            field_type = rules.get('type')
            
            # Type checking
            if field_type == 'str' and not isinstance(value, str):
                errors.append(f"Field {field} must be string")
            elif field_type == 'int' and not isinstance(value, int):
                errors.append(f"Field {field} must be integer")
            elif field_type == 'float' and not isinstance(value, (int, float)):
                errors.append(f"Field {field} must be number")
            elif field_type == 'bool' and not isinstance(value, bool):
                errors.append(f"Field {field} must be boolean")
            elif field_type == 'list' and not isinstance(value, list):
                errors.append(f"Field {field} must be list")
            elif field_type == 'dict' and not isinstance(value, dict):
                errors.append(f"Field {field} must be object")
            
            # Min/max for numbers
            if field_type in ['int', 'float']:
                if 'min' in rules and value < rules['min']:
                    errors.append(f"Field {field} must be >= {rules['min']}")
                if 'max' in rules and value > rules['max']:
                    errors.append(f"Field {field} must be <= {rules['max']}")
            
            # String constraints
            if field_type == 'str':
                if 'min_length' in rules and len(value) < rules['min_length']:
                    errors.append(f"Field {field} must be at least {rules['min_length']} characters")
                if 'max_length' in rules and len(value) > rules['max_length']:
                    errors.append(f"Field {field} must be at most {rules['max_length']} characters")
                if 'pattern' in rules and not re.match(rules['pattern'], value):
                    errors.append(f"Field {field} has invalid format")
    
    return len(errors) == 0, errors