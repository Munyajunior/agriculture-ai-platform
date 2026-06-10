param(
    [ValidateSet("cu118", "cu126", "cu128")]
    [string]$Variant = "cu128",
    [switch]$RequireCuda
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    uv venv
}

$IndexUrl = switch ($Variant) {
    "cu118" { "https://download.pytorch.org/whl/cu118" }
    "cu126" { "https://download.pytorch.org/whl/cu126" }
    "cu128" { "https://download.pytorch.org/whl/cu128" }
}

Write-Host "Installing PyTorch variant: $Variant"
Write-Host "Index URL: $IndexUrl"

uv pip install --reinstall torch torchvision --index-url $IndexUrl

Write-Host ""
Write-Host "PyTorch device check:"
uv run --package ai-service python scripts\training\check_torch.py

if ($RequireCuda) {
    uv run --package ai-service python -c "import torch; raise SystemExit(0 if torch.cuda.is_available() else 'CUDA was required but is not available to PyTorch')"
}
