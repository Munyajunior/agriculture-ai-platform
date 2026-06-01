# services/ai-service/app/preprocessing/image_processor.py
"""Image preprocessing pipeline"""

import numpy as np
from PIL import Image
import cv2
import torch
from torchvision import transforms
from typing import Tuple, Optional, List
import asyncio


class ImageProcessor:
    """Advanced image preprocessing for plant disease detection"""
    
    def __init__(self):
        self.default_mean = [0.485, 0.456, 0.406]
        self.default_std = [0.229, 0.224, 0.225]
        
    async def process(
        self,
        image: np.ndarray,
        target_size: Tuple[int, int] = (224, 224),
        normalize: bool = True,
        augment: bool = False
    ) -> torch.Tensor:
        """Process image for model input"""
        # Convert to PIL Image
        if isinstance(image, np.ndarray):
            if len(image.shape) == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:  # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            image = Image.fromarray(image)
        
        # Build transform pipeline
        transform_list = [
            transforms.Resize(target_size),
            transforms.CenterCrop(target_size),
            transforms.ToTensor()
        ]
        
        if normalize:
            transform_list.append(
                transforms.Normalize(mean=self.default_mean, std=self.default_std)
            )
        
        if augment:
            transform_list.extend(self._get_augmentations())
        
        transform = transforms.Compose(transform_list)
        
        # Apply transforms
        tensor = transform(image)
        
        # Add batch dimension
        if len(tensor.shape) == 3:
            tensor = tensor.unsqueeze(0)
        
        return tensor
    
    def _get_augmentations(self) -> List:
        """Get data augmentations for training"""
        return [
            transforms.RandomHorizontalFlip(p=0.5),
            transforms.RandomRotation(degrees=15),
            transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        ]
    
    async def enhance_image(
        self,
        image: np.ndarray,
        techniques: List[str] = ['contrast', 'sharpening']
    ) -> np.ndarray:
        """Enhance image quality for better detection"""
        enhanced = image.copy()
        
        for technique in techniques:
            if technique == 'contrast':
                # CLAHE (Contrast Limited Adaptive Histogram Equalization)
                lab = cv2.cvtColor(enhanced, cv2.COLOR_RGB2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                l = clahe.apply(l)
                enhanced = cv2.merge([l, a, b])
                enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2RGB)
                
            elif technique == 'sharpening':
                # Unsharp masking
                gaussian = cv2.GaussianBlur(enhanced, (0, 0), 2.0)
                enhanced = cv2.addWeighted(enhanced, 1.5, gaussian, -0.5, 0)
                
            elif technique == 'denoise':
                # Non-local means denoising
                enhanced = cv2.fastNlMeansDenoisingColored(enhanced, None, 10, 10, 7, 21)
                
            elif technique == 'white_balance':
                # Simple white balance
                result = cv2.cvtColor(enhanced, cv2.COLOR_RGB2LAB)
                avg_a = np.average(result[:, :, 1])
                avg_b = np.average(result[:, :, 2])
                result[:, :, 1] = result[:, :, 1] - ((avg_a - 128) * (result[:, :, 0] / 255.0) * 0.5)
                result[:, :, 2] = result[:, :, 2] - ((avg_b - 128) * (result[:, :, 0] / 255.0) * 0.5)
                enhanced = cv2.cvtColor(result, cv2.COLOR_LAB2RGB)
        
        return enhanced
    
    async def detect_disease_region(
        self,
        image: np.ndarray
    ) -> Tuple[Optional[Tuple[int, int, int, int]], float]:
        """Detect regions of interest (disease spots)"""
        # Convert to HSV for better color segmentation
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # Define ranges for disease symptoms (brown/yellow spots)
        lower_brown = np.array([10, 50, 50])
        upper_brown = np.array([30, 255, 200])
        
        # Create mask for potential disease regions
        mask = cv2.inRange(hsv, lower_brown, upper_brown)
        
        # Morphological operations to clean mask
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Get largest contour
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            
            # Calculate confidence based on area ratio
            area_ratio = (w * h) / (image.shape[0] * image.shape[1])
            confidence = min(area_ratio * 5, 1.0)  # Scale up, max 1.0
            
            return (x, y, w, h), confidence
        
        return None, 0.0