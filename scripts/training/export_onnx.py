# scripts/training/export_onnx.py
#!/usr/bin/env python3
"""Export PyTorch model to ONNX format"""

import argparse
import torch
import torch.nn as nn
from pathlib import Path
import onnx
import onnxruntime as ort
import numpy as np
from typing import Tuple
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelExporter:
    """Export PyTorch models to ONNX format"""
    
    def __init__(self, model_path: Path, num_classes: int = 15):
        self.model_path = model_path
        self.num_classes = num_classes
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
    def load_model(self):
        """Load PyTorch model"""
        import torchvision.models as models
        
        # Create model architecture
        self.model = models.mobilenet_v3_large(pretrained=False)
        in_features = self.model.classifier[-1].in_features
        self.model.classifier = nn.Sequential(
            nn.Linear(in_features, 1024),
            nn.Hardswish(),
            nn.Dropout(0.2),
            nn.Linear(1024, self.num_classes)
        )
        
        # Load weights
        checkpoint = torch.load(self.model_path, map_location=self.device)
        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.model.eval()
        self.model.to(self.device)
        
        logger.info(f"Model loaded from {self.model_path}")
        
    def export_to_onnx(
        self,
        output_path: Path,
        input_size: Tuple[int, int, int] = (3, 224, 224),
        opset_version: int = 11,
        quantize: bool = False
    ):
        """Export model to ONNX format"""
        
        # Create dummy input
        dummy_input = torch.randn(1, *input_size).to(self.device)
        
        # Export to ONNX
        torch.onnx.export(
            self.model,
            dummy_input,
            output_path,
            export_params=True,
            opset_version=opset_version,
            do_constant_folding=True,
            input_names=['input'],
            output_names=['output'],
            dynamic_axes={
                'input': {0: 'batch_size'},
                'output': {0: 'batch_size'}
            }
        )
        
        logger.info(f"Model exported to ONNX: {output_path}")
        
        # Validate ONNX model
        self.validate_onnx_model(output_path)
        
        # Quantize if requested
        if quantize:
            self.quantize_onnx_model(output_path, output_path.with_suffix('.quant.onnx'))
        
    def validate_onnx_model(self, onnx_path: Path):
        """Validate exported ONNX model"""
        
        # Load ONNX model
        onnx_model = onnx.load(onnx_path)
        onnx.checker.check_model(onnx_model)
        
        # Test inference
        ort_session = ort.InferenceSession(onnx_path)
        
        # Create test input
        dummy_input = np.random.randn(1, 3, 224, 224).astype(np.float32)
        
        # Run inference
        outputs = ort_session.run(['output'], {'input': dummy_input})
        
        logger.info(f"ONNX model validated. Output shape: {outputs[0].shape}")
        
    def quantize_onnx_model(self, input_path: Path, output_path: Path):
        """Quantize ONNX model to int8"""
        
        from onnxruntime.quantization import quantize_dynamic, QuantType
        
        quantize_dynamic(
            input_path,
            output_path,
            weight_type=QuantType.QInt8
        )
        
        logger.info(f"Quantized model saved to {output_path}")
        
        # Compare sizes
        orig_size = input_path.stat().st_size / (1024 * 1024)
        quant_size = output_path.stat().st_size / (1024 * 1024)
        
        logger.info(f"Original size: {orig_size:.2f} MB")
        logger.info(f"Quantized size: {quant_size:.2f} MB")
        logger.info(f"Reduction: {(1 - quant_size/orig_size) * 100:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Export PyTorch model to ONNX")
    parser.add_argument("--model_path", type=str, required=True, help="Path to PyTorch model")
    parser.add_argument("--output_path", type=str, default="./model.onnx", help="Output ONNX path")
    parser.add_argument("--num_classes", type=int, default=15, help="Number of classes")
    parser.add_argument("--quantize", action="store_true", help="Quantize model")
    
    args = parser.parse_args()
    
    exporter = ModelExporter(
        model_path=Path(args.model_path),
        num_classes=args.num_classes
    )
    
    exporter.load_model()
    exporter.export_to_onnx(
        output_path=Path(args.output_path),
        quantize=args.quantize
    )
    
    logger.info("Export completed successfully!")


if __name__ == "__main__":
    main()