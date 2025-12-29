"""
Download and export YOLOv8n model to ONNX format

This script:
1. Downloads the YOLOv8n PyTorch model from Ultralytics
2. Exports it to ONNX format for faster inference
3. Saves the ONNX model to classification/models/

Run during Docker build to prepare the model for Lambda deployment.
"""

import os
from pathlib import Path


def download_and_export_yolov8n():
    """
    Download YOLOv8n and export to ONNX format
    """
    print("[ModelDownload] Starting YOLOv8n download and export...")

    try:
        import torch
        from ultralytics import YOLO

        # Create models directory
        models_dir = Path(__file__).parent / "models"
        models_dir.mkdir(exist_ok=True)

        output_path = models_dir / "yolov8n.onnx"

        # Check if model already exists
        if output_path.exists():
            print(f"[ModelDownload] Model already exists at: {output_path}")
            print(f"[ModelDownload] Size: {output_path.stat().st_size / (1024*1024):.2f} MB")
            return str(output_path)

        # Load YOLOv8n model (check /tmp first, then let ultralytics auto-download)
        model_source = '/tmp/yolov8n.pt' if Path('/tmp/yolov8n.pt').exists() else 'yolov8n.pt'
        print(f"[ModelDownload] Loading YOLOv8n model from: {model_source}")

        # Temporarily patch torch.load to disable weights_only for trusted ultralytics model
        # This bypasses PyTorch 2.6+ security for this official model from GitHub
        original_load = torch.load
        def patched_load(*args, **kwargs):
            kwargs['weights_only'] = False
            return original_load(*args, **kwargs)

        torch.load = patched_load
        try:
            model = YOLO(model_source)
        finally:
            torch.load = original_load  # Restore original

        # Export to ONNX format
        print("[ModelDownload] Exporting to ONNX format...")
        model.export(
            format='onnx',
            imgsz=640,  # Input size 640x640
            simplify=True,  # Simplify ONNX graph for faster inference
            opset=12  # ONNX opset version (compatible with onnxruntime 1.16)
        )

        # Move exported model to models directory
        # Ultralytics saves the ONNX file in the same directory as the source .pt file
        exported_path = Path('/tmp/yolov8n.onnx') if Path('/tmp/yolov8n.pt').exists() else Path('yolov8n.onnx')
        if exported_path.exists():
            exported_path.rename(output_path)
            print(f"[ModelDownload] ✓ Model exported successfully!")
            print(f"[ModelDownload] Location: {output_path}")
            print(f"[ModelDownload] Size: {output_path.stat().st_size / (1024*1024):.2f} MB")
        else:
            raise FileNotFoundError(f"Export succeeded but ONNX file not found at {exported_path}")

        return str(output_path)

    except ImportError:
        print("[ModelDownload] ERROR: ultralytics not installed")
        print("[ModelDownload] Run: pip install ultralytics")
        return None
    except Exception as e:
        print(f"[ModelDownload] ERROR: Failed to download/export model: {e}")
        return None


if __name__ == "__main__":
    model_path = download_and_export_yolov8n()
    if model_path:
        print(f"\n[ModelDownload] SUCCESS: Model ready at {model_path}")
        exit(0)
    else:
        print("\n[ModelDownload] FAILED: Could not prepare model")
        exit(1)
