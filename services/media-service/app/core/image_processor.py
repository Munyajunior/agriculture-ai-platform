# services/media-service/app/core/image_processor.py
"""Advanced image processing for plant disease detection"""

import io
import asyncio
from typing import Tuple, Optional, List, Dict, Any
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
import numpy as np
import cv2
from blurhash import encode as blurhash_encode
import colorsys
import logging

from ..config import settings

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Image processing utilities for optimization and analysis"""
    
    def __init__(self):
        self.thumbnail_sizes = settings.THUMBNAIL_SIZES
        self.image_quality = settings.IMAGE_QUALITY
        
    async def process_upload(
        self,
        image_data: bytes,
        filename: str,
        generate_thumbnails: bool = True
    ) -> Dict[str, Any]:
        """Process uploaded image - resize, optimize, extract metadata"""
        
        try:
            # Open image
            img = Image.open(io.BytesIO(image_data))
            
            # Convert to RGB if needed
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            
            # Extract EXIF data
            exif_data = self._extract_exif(img)
            
            # Auto-orient based on EXIF
            img = ImageOps.exif_transpose(img)
            
            # Get image dimensions
            width, height = img.size
            
            # Generate blurhash for progressive loading
            blurhash = self._generate_blurhash(img)
            
            # Get dominant color
            dominant_color = await self._get_dominant_color(img)
            
            # Optimize original image
            optimized_data = await self._optimize_image(img)
            
            # Generate thumbnails
            thumbnails = {}
            if generate_thumbnails:
                thumbnails = await self._generate_thumbnails(img)
            
            # Analyze image quality
            quality_analysis = await self._analyze_quality(img)
            
            return {
                "width": width,
                "height": height,
                "exif_data": exif_data,
                "blurhash": blurhash,
                "dominant_color": dominant_color,
                "optimized_data": optimized_data,
                "thumbnails": thumbnails,
                "quality_analysis": quality_analysis,
                "original_size": len(image_data),
                "optimized_size": len(optimized_data),
                "compression_ratio": len(optimized_data) / len(image_data)
            }
            
        except Exception as e:
            logger.error(f"Image processing failed: {e}")
            raise
    
    async def _optimize_image(self, img: Image.Image) -> bytes:
        """Optimize image for web/mobile delivery"""
        
        # Resize if too large (max dimension 2048px)
        max_dimension = 2048
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = tuple(int(dim * ratio) for dim in img.size)
            img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Apply slight sharpening for better detail
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.2)
        
        # Save optimized image
        output = io.BytesIO()
        
        # Determine format
        format = 'JPEG' if img.mode == 'RGB' else 'PNG'
        
        img.save(
            output,
            format=format,
            quality=self.image_quality,
            optimize=True,
            progressive=True
        )
        
        return output.getvalue()
    
    async def _generate_thumbnails(self, img: Image.Image) -> Dict[str, bytes]:
        """Generate multiple thumbnail sizes"""
        
        thumbnails = {}
        
        for size in self.thumbnail_sizes:
            # Create thumbnail
            thumb = img.copy()
            thumb.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            output = io.BytesIO()
            thumb.save(output, format='JPEG', quality=75, optimize=True)
            thumbnails[f"{size[0]}x{size[1]}"] = output.getvalue()
        
        return thumbnails
    
    def _extract_exif(self, img: Image.Image) -> Dict[str, Any]:
        """Extract EXIF data from image"""
        
        exif_data = {}
        
        if hasattr(img, '_getexif') and img._getexif():
            exif = img._getexif()
            
            # Map common EXIF tags
            exif_tags = {
                271: 'make',
                272: 'model',
                306: 'datetime',
                33434: 'exposure_time',
                33437: 'fnumber',
                34855: 'iso',
                37386: 'focal_length',
                36867: 'datetime_original',
                42034: 'lens_model'
            }
            
            for tag_id, tag_name in exif_tags.items():
                if tag_id in exif:
                    exif_data[tag_name] = str(exif[tag_id])
        
        return exif_data
    
    def _generate_blurhash(self, img: Image.Image) -> str:
        """Generate blurhash for progressive image loading"""
        
        # Resize to reasonable size for blurhash (max 100px)
        img_small = img.copy()
        img_small.thumbnail((100, 100), Image.Resampling.LANCZOS)
        
        # Convert to RGB and get pixels
        img_small = img_small.convert('RGB')
        pixels = np.array(img_small)
        
        # Generate blurhash (components x=4, y=3)
        try:
            blurhash = blurhash_encode(pixels, x_components=4, y_components=3)
            return blurhash
        except Exception as e:
            logger.warning(f"Blurhash generation failed: {e}")
            return ""
    
    async def _get_dominant_color(self, img: Image.Image) -> str:
        """Extract dominant color from image"""
        
        # Resize for faster processing
        img_small = img.copy()
        img_small.thumbnail((100, 100), Image.Resampling.LANCZOS)
        
        # Convert to RGB array
        pixels = np.array(img_small.convert('RGB'))
        pixels = pixels.reshape(-1, 3)
        
        # Use k-means to find dominant color
        from sklearn.cluster import KMeans
        
        kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
        kmeans.fit(pixels)
        
        # Get dominant cluster center
        dominant_rgb = kmeans.cluster_centers_[kmeans.labels_.argmax()]
        dominant_rgb = dominant_rgb.astype(int)
        
        # Convert to hex
        hex_color = '#{:02x}{:02x}{:02x}'.format(*dominant_rgb)
        
        return hex_color
    
    async def _analyze_quality(self, img: Image.Image) -> Dict[str, Any]:
        """Analyze image quality for plant disease detection suitability"""
        
        # Convert to numpy array for OpenCV processing
        img_array = np.array(img.convert('RGB'))
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Calculate brightness
        hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
        brightness = np.mean(hsv[:, :, 2])
        brightness_score = min(100, int(brightness / 255 * 100))
        
        # Calculate contrast (standard deviation)
        gray = cv2.cvtColor(img_array, cv2.COLOR_BGR2GRAY)
        contrast = np.std(gray)
        contrast_score = min(100, int(contrast / 50 * 100))
        
        # Calculate sharpness using Laplacian variance
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        sharpness = np.var(laplacian)
        sharpness_score = min(100, int(sharpness / 500 * 100))
        
        # Calculate noise level
        noise = self._estimate_noise(gray)
        noise_score = max(0, 100 - int(noise * 10))
        
        # Overall quality score
        quality_score = int((
            brightness_score * 0.2 +
            contrast_score * 0.3 +
            sharpness_score * 0.3 +
            noise_score * 0.2
        ))
        
        # Determine if suitable for disease detection
        is_suitable = (
            quality_score > 60 and
            brightness_score > 30 and
            sharpness_score > 40
        )
        
        return {
            "brightness": brightness_score,
            "contrast": contrast_score,
            "sharpness": sharpness_score,
            "noise_level": noise_score,
            "quality_score": quality_score,
            "is_suitable_for_detection": is_suitable,
            "suggestions": self._get_improvement_suggestions(
                brightness_score, contrast_score, sharpness_score
            )
        }
    
    def _estimate_noise(self, gray_image: np.ndarray) -> float:
        """Estimate noise level in image"""
        
        # Use median filter to estimate noise
        median = cv2.medianBlur(gray_image, 5)
        noise = np.mean(np.abs(gray_image.astype(float) - median.astype(float)))
        
        # Normalize
        noise_normalized = noise / 255.0
        
        return noise_normalized
    
    def _get_improvement_suggestions(
        self,
        brightness: int,
        contrast: int,
        sharpness: int
    ) -> List[str]:
        """Get suggestions for image quality improvement"""
        
        suggestions = []
        
        if brightness < 40:
            suggestions.append("Image is too dark. Ensure good lighting when capturing.")
        elif brightness > 90:
            suggestions.append("Image is too bright. Avoid direct sunlight on leaves.")
        
        if contrast < 30:
            suggestions.append("Low contrast detected. Capture with better lighting conditions.")
        
        if sharpness < 40:
            suggestions.append("Image is blurry. Hold camera steady or use autofocus.")
        
        if not suggestions:
            suggestions.append("Good image quality for disease detection.")
        
        return suggestions
    
    async def detect_disease_regions(
        self,
        img: Image.Image
    ) -> List[Dict[str, Any]]:
        """Detect potential disease regions in plant image"""
        
        # Convert to OpenCV format
        img_array = np.array(img.convert('RGB'))
        img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Convert to HSV for color-based segmentation
        hsv = cv2.cvtColor(img_array, cv2.COLOR_BGR2HSV)
        
        # Define color ranges for disease symptoms
        # Brown spots (early blight, late blight)
        lower_brown = np.array([10, 50, 50])
        upper_brown = np.array([30, 255, 200])
        
        # Yellow spots (mosaic virus, nutrient deficiency)
        lower_yellow = np.array([20, 100, 100])
        upper_yellow = np.array([30, 255, 255])
        
        # White/powdery mildew
        lower_white = np.array([0, 0, 200])
        upper_white = np.array([180, 30, 255])
        
        # Create masks
        brown_mask = cv2.inRange(hsv, lower_brown, upper_brown)
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        white_mask = cv2.inRange(hsv, lower_white, upper_white)
        
        # Combine masks
        disease_mask = cv2.bitwise_or(brown_mask, yellow_mask)
        disease_mask = cv2.bitwise_or(disease_mask, white_mask)
        
        # Apply morphological operations
        kernel = np.ones((5, 5), np.uint8)
        disease_mask = cv2.morphologyEx(disease_mask, cv2.MORPH_OPEN, kernel)
        disease_mask = cv2.morphologyEx(disease_mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(
            disease_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Extract disease regions
        regions = []
        total_area = img_array.shape[0] * img_array.shape[1]
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area > total_area * 0.01:  # Filter small regions (>1% of image)
                x, y, w, h = cv2.boundingRect(contour)
                
                # Calculate severity based on area coverage
                severity = min(1.0, (area / total_area) * 3)  # Up to 30% coverage = severe
                
                # Determine likely disease type based on color
                roi = hsv[y:y+h, x:x+w]
                avg_hue = np.mean(roi[:, :, 0])
                
                if 10 <= avg_hue <= 30:  # Brown range
                    disease_type = "brown_spot"
                elif 20 <= avg_hue <= 40:  # Yellow range
                    disease_type = "yellowing"
                else:
                    disease_type = "unknown"
                
                regions.append({
                    "bbox": [int(x), int(y), int(w), int(h)],
                    "area": float(area),
                    "severity": float(severity),
                    "disease_type": disease_type,
                    "confidence": float(min(1.0, area / (total_area * 0.1)))  # Confidence based on area
                })
        
        return sorted(regions, key=lambda x: x['severity'], reverse=True)