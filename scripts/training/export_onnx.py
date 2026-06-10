# scripts/training/export_onnx.py
#!/usr/bin/env python3
"""Export PyTorch model to ONNX format"""

import argparse
import torch
from pathlib import Path
import json
import onnx
import onnxruntime as ort
import numpy as np
from typing import Tuple
import logging
import sys

try:
    from model_utils import load_checkpoint_model
except ModuleNotFoundError:
    from scripts.training.model_utils import load_checkpoint_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8")


class ModelExporter:
    """Export PyTorch models to ONNX format"""
    
    def __init__(self, model_path: Path, num_classes: int | None = None):
        self.model_path = model_path
        self.num_classes = num_classes
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.checkpoint = None
        
    def load_model(self):
        """Load PyTorch model"""
        self.model, self.checkpoint = load_checkpoint_model(
            self.model_path,
            num_classes=self.num_classes,
            device=self.device,
        )
        self.num_classes = int(self.checkpoint.get("num_classes", self.num_classes or 15))
        
        logger.info(f"Model loaded from {self.model_path}")
        
    def export_to_onnx(
        self,
        output_path: Path,
        input_size: Tuple[int, int, int] = (3, 224, 224),
        opset_version: int = 18,
        quantize: bool = False,
        exporter: str = "dynamo",
        dynamic_batch: bool = False,
        quantization_exporter: str = "auto",
    ):
        """Export model to ONNX format"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        self._export_model(
            output_path=output_path,
            input_size=input_size,
            opset_version=opset_version,
            exporter=exporter,
            dynamic_batch=dynamic_batch,
        )
        self.validate_onnx_model(output_path)

        quantized_path = None
        quantized_from = None
        if quantize:
            quantized_path, quantized_from = self.quantize_with_fallback(
                primary_path=output_path,
                input_size=input_size,
                opset_version=opset_version,
                primary_exporter=exporter,
                quantization_exporter=quantization_exporter,
                dynamic_batch=dynamic_batch,
            )

        self.write_export_metadata(
            output_path=output_path,
            exporter=exporter,
            opset_version=opset_version,
            dynamic_batch=dynamic_batch,
            quantized_path=quantized_path,
            quantized_from=quantized_from,
        )

    def _export_model(
        self,
        output_path: Path,
        input_size: Tuple[int, int, int],
        opset_version: int,
        exporter: str,
        dynamic_batch: bool,
    ):
        """Export using either the modern dynamo exporter or legacy fallback."""
        if exporter not in {"dynamo", "legacy"}:
            raise ValueError(f"Unsupported exporter: {exporter}")

        dummy_input = torch.randn(1, *input_size).to(self.device)
        export_kwargs = {
            "export_params": True,
            "opset_version": opset_version,
            "do_constant_folding": True,
            "input_names": ["input"],
            "output_names": ["output"],
            "dynamo": exporter == "dynamo",
        }
        if dynamic_batch:
            export_kwargs["dynamic_axes"] = {
                "input": {0: "batch_size"},
                "output": {0: "batch_size"},
            }

        torch.onnx.export(self.model, dummy_input, output_path, **export_kwargs)
        logger.info("Model exported to ONNX with %s exporter: %s", exporter, output_path)

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
        
    def quantize_with_fallback(
        self,
        primary_path: Path,
        input_size: Tuple[int, int, int],
        opset_version: int,
        primary_exporter: str,
        quantization_exporter: str,
        dynamic_batch: bool,
    ) -> tuple[Path, str]:
        """Quantize, falling back to a legacy quantization source if needed."""
        quantized_path = primary_path.with_suffix(".quant.onnx")
        attempts = [primary_exporter]
        if quantization_exporter != "auto":
            attempts = [quantization_exporter]
        elif primary_exporter != "legacy":
            attempts.append("legacy")

        last_error: Exception | None = None
        for attempt in attempts:
            source_path = primary_path
            if attempt != primary_exporter:
                source_path = primary_path.with_suffix(f".{attempt}_quant_source.onnx")
                self._export_model(
                    output_path=source_path,
                    input_size=input_size,
                    opset_version=opset_version,
                    exporter=attempt,
                    dynamic_batch=dynamic_batch,
                )
                self.validate_onnx_model(source_path)

            try:
                self.quantize_onnx_model(source_path, quantized_path)
                self.validate_onnx_model(quantized_path)
                return quantized_path, attempt
            except Exception as exc:
                last_error = exc
                logger.warning("Quantization with %s ONNX source failed: %s", attempt, exc)

        raise RuntimeError("ONNX quantization failed for all exporters") from last_error

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

    def write_export_metadata(
        self,
        output_path: Path,
        exporter: str,
        opset_version: int,
        dynamic_batch: bool,
        quantized_path: Path | None,
        quantized_from: str | None,
    ):
        """Write export metadata beside the ONNX artifact."""
        metadata = {
            "model_path": str(self.model_path),
            "onnx_path": str(output_path),
            "onnx_size_mb": round(output_path.stat().st_size / (1024 * 1024), 2),
            "external_data_path": str(output_path.with_suffix(output_path.suffix + ".data"))
            if output_path.with_suffix(output_path.suffix + ".data").exists()
            else None,
            "external_data_size_mb": round(
                output_path.with_suffix(output_path.suffix + ".data").stat().st_size / (1024 * 1024),
                2,
            )
            if output_path.with_suffix(output_path.suffix + ".data").exists()
            else None,
            "exporter": exporter,
            "opset_version": opset_version,
            "dynamic_batch": dynamic_batch,
            "num_classes": self.num_classes,
            "class_names": self.checkpoint.get("class_names", []) if self.checkpoint else [],
            "quantized_path": str(quantized_path) if quantized_path else None,
            "quantized_size_mb": round(quantized_path.stat().st_size / (1024 * 1024), 2)
            if quantized_path and quantized_path.exists()
            else None,
            "quantized_from_exporter": quantized_from,
        }
        metadata_path = output_path.with_suffix(".export.json")
        with metadata_path.open("w", encoding="utf-8") as file:
            json.dump(metadata, file, indent=2)
        logger.info("Export metadata saved to %s", metadata_path)


def main():
    parser = argparse.ArgumentParser(description="Export PyTorch model to ONNX")
    parser.add_argument("--model_path", type=str, required=True, help="Path to PyTorch model")
    parser.add_argument("--output_path", type=str, default="./model.onnx", help="Output ONNX path")
    parser.add_argument("--num_classes", type=int, default=None, help="Number of classes; defaults to checkpoint metadata")
    parser.add_argument("--quantize", action="store_true", help="Quantize model")
    parser.add_argument("--exporter", choices=["dynamo", "legacy"], default="dynamo", help="Primary ONNX exporter")
    parser.add_argument(
        "--quantization-exporter",
        choices=["auto", "dynamo", "legacy"],
        default="auto",
        help="Exporter source to use for quantization. auto tries the primary exporter, then legacy.",
    )
    parser.add_argument("--opset", type=int, default=18, help="ONNX opset version")
    parser.add_argument("--dynamic-batch", action="store_true", help="Export dynamic batch axes")
    
    args = parser.parse_args()
    
    exporter = ModelExporter(
        model_path=Path(args.model_path),
        num_classes=args.num_classes
    )
    
    exporter.load_model()
    exporter.export_to_onnx(
        output_path=Path(args.output_path),
        opset_version=args.opset,
        quantize=args.quantize,
        exporter=args.exporter,
        dynamic_batch=args.dynamic_batch,
        quantization_exporter=args.quantization_exporter,
    )
    
    logger.info("Export completed successfully!")


if __name__ == "__main__":
    main()
