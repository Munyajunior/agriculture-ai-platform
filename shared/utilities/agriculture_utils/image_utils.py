# shared/utilities/agriculture_utils/image_utils.py
"""Image processing utilities"""

from PIL import Image
import base64
import io
from typing import Tuple, Optional
import numpy as np


def resize_image(
    image: Image.Image,
    target_size: Tuple[int, int],
    keep_aspect: bool = True
) -> Image.Image:
    """Resize image to target size"""
    
    if keep_aspect:
        image.thumbnail(target_size, Image.Resampling.LANCZOS)
        
        # Create new image with padding
        new_image = Image.new('RGB', target_size, (0, 0, 0))
        new_image.paste(
            image,
            ((target_size[0] - image.size[0]) // 2,
             (target_size[1] - image.size[1]) // 2)
        )
        return new_image
    else:
        return image.resize(target_size, Image.Resampling.LANCZOS)


def encode_image(image: Image.Image, format: str = 'JPEG') -> str:
    """Encode image to base64 string"""
    
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode('utf-8')


def decode_image(base64_string: str) -> Image.Image:
    """Decode base64 string to image"""
    
    # Remove data URL prefix if present
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]
    
    image_bytes = base64.b64decode(base64_string)
    return Image.open(io.BytesIO(image_bytes))


def check_image_dimensions(image: Image.Image) -> bool:
    """Check that image meets minimum dimension and aspect-ratio requirements for processing."""

    if image.width < 100 or image.height < 100:
        return False

    aspect_ratio = image.width / image.height
    if aspect_ratio < 0.25 or aspect_ratio > 4:
        return False

    return True


def extract_image_metadata(image: Image.Image) -> dict:
    """Extract metadata from image"""
    
    return {
        "width": image.width,
        "height": image.height,
        "format": image.format,
        "mode": image.mode,
        "has_exif": bool(image.info.get('exif'))
    }