# Plant Camera Demo

This is the first local desktop/terminal interface for showing the trained model before mobile and admin dashboard work.

## What It Does

- Opens a desktop camera preview.
- Captures a plant image from the webcam.
- Runs local ONNX inference.
- Prints disease prediction, confidence, top predictions, and recommendations.
- Saves captured images and JSON diagnosis reports.

The current demo uses the trained v1 quantized model:

```text
models/plant-disease-v2/plant_disease_mobilenetv3.quant.onnx
models/plant-disease-v2/plant_disease_mobilenetv3.export.json
```

After v2 is trained/exported, pass the v2 model and metadata paths with `--model` and `--metadata`.

## Camera Demo

```powershell
uv run --package ai-service python scripts/demo/plant_camera_demo.py
```

Controls:

```text
c or space: capture and diagnose
q or esc: quit
```

Outputs are saved under:

```text
demo-output/
```

## Image Mode

Use this when no camera is attached, or to test with a known image:

```powershell
uv run --package ai-service python scripts\demo\plant_camera_demo.py `
  --image data\processed\plant-disease-v1\test\tomato_late_blight\<image-file>.jpg
```

## SDK Usage

```python
from pathlib import Path
from scripts.demo.plant_disease_sdk import PlantDiseaseSDK

sdk = PlantDiseaseSDK(
    Path("models/plant-disease-v1/plant_disease_mobilenetv3.quant.onnx"),
    Path("models/plant-disease-v1/plant_disease_mobilenetv3.export.json"),
)

result = sdk.predict_file(Path("leaf.jpg"))
print(result.label, result.confidence)
print(result.recommendations)
```

## Recommendation Scope

Recommendations are rule-based and meant for demo/support guidance. They should not replace local agronomist or extension officer confirmation, especially before pesticide use or crop removal.
