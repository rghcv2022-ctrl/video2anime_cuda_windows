param(
    [string]$PythonCmd = "py -3.11"
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

Write-Host "==> Using Python command: $PythonCmd"

$pythonCheck = "$PythonCmd --version"
Invoke-Expression $pythonCheck

if (-not (Test-Path ".venv")) {
    Write-Host "==> Creating virtual environment"
    Invoke-Expression "$PythonCmd -m venv .venv"
}

$pythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

Write-Host "==> Upgrading pip/setuptools/wheel"
& $pythonExe -m pip install --upgrade pip setuptools wheel

Write-Host "==> Installing requirements"
& $pythonExe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Setup complete."
Write-Host "Run the GUI with: .\\run_gui.bat"
Write-Host ""
Write-Host "NOTE: onnxruntime-gpu is usually happiest on Python 3.11/3.12 on Windows."
