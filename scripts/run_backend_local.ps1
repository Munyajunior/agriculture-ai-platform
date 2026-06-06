$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

& powershell -ExecutionPolicy Bypass -File scripts\setup_infrastructure.ps1
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

uv run python scripts\smoke_backend.py
