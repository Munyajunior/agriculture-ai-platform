# shared/inference-sdk/agriculture_inference/preprocessing.py
"""Image preprocessing for plant disease detection"""

from pathlib import Path

import cv2
import numpy as np
import torch
from PIL import Image
from torchvision import transforms
from typing import Tuple, Optional, List, Union


class ImagePreprocessor:
    """Advanced image preprocessing pipeline"""
    
    def __init__(
        self,
        target_size: Tuple[int, int] = (224, 224),
        normalize: bool = True,
        mean: List[float] = [0.485, 0.456, 0.406],
        std: List[float] = [0.229, 0.224, 0.225]
    ):
        self.target_size = target_size
        self.normalize = normalize
        self.mean = mean
        self.std = std
        
    async def process_image(
        self,
        image: Union[str, Path, np.ndarray, Image.Image],
        augment: bool = False
    ) -> np.ndarray:
        """Process image for model input"""
        
        # Load image based on input type
        if isinstance(image, (str, Path)):
            image = Image.open(image).convert('RGB')
        elif isinstance(image, np.ndarray):
            if len(image.shape) == 2:  # Grayscale
                image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
            elif image.shape[2] == 4:  # RGBA
                image = cv2.cvtColor(image, cv2.COLOR_RGBA2RGB)
            image = Image.fromarray(image)
        elif isinstance(image, Image.Image):
            if image.mode != 'RGB':
                image = image.convert('RGB')
        
        # Build transform pipeline
        transforms_list = [
            transforms.Resize(self.target_size),
            transforms.CenterCrop(self.target_size),
            transforms.ToTensor()
        ]
        
        if self.normalize:
            transforms_list.append(
                transforms.Normalize(mean=self.mean, std=self.std)
            )
        
        if augment:
            transforms_list.extend([
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomRotation(degrees=15),
                transforms.ColorJitter(brightness=0.2, contrast=0.2)
            ])
        
        transform = transforms.Compose(transforms_list)
        tensor = transform(image)
        
        # Add batch dimension
        if len(tensor.shape) == 3:
            tensor = tensor.unsqueeze(0)
        
        # Convert to numpy for ONNX
        return tensor.numpy()
    
    async def batch_process(
        self,
        images: List[Union[str, Path, np.ndarray, Image.Image]],
        augment: bool = False
    ) -> np.ndarray:
        """Process batch of images"""
        
        batch = []
        for image in images:
            processed = await self.process_image(image, augment)
            batch.append(processed)
        
        return np.vstack(batch)
    
    def enhance_image(
        self,
        image: np.ndarray,
        techniques: List[str] = ['contrast', 'sharpening']
    ) -> np.ndarray:
        """Enhance image quality"""
        
        enhanced = image.copy()
        
        for technique in techniques:
            if technique == 'contrast':
                # Apply CLAHE
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
                enhanced = cv2.fastNlMeansDenoisingColored(
                    enhanced, None, 10, 10, 7, 21
                )
        
        return enhanced
    
    def detect_leaf_region(self, image: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Detect leaf region in image"""
        
        # Convert to HSV for better segmentation
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # Define range for green color (leaves)
        lower_green = np.array([35, 40, 40])
        upper_green = np.array([85, 255, 255])
        
        # Create mask
        mask = cv2.inRange(hsv, lower_green, upper_green)
        
        # Morphological operations
        kernel = np.ones((5,5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if contours:
            # Get largest contour
            largest = max(contours, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(largest)
            return (x, y, w, h)
        
        return None