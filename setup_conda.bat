@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "ENV_NAME=video2anime39"
set "SAFE_TEMP=C:\Temp\conda_tmp"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONUTF8=1"
set "ORT_WHEEL=downloads\onnxruntime_gpu-1.18.1-cp39-cp39-win_amd64.whl"
set "ORT_URL=https://files.pythonhosted.org/packages/3a/2e/1e254840ceda53e75a69f05d5e0f7937652f3b59346a1f0b19dd44c3b9c7/onnxruntime_gpu-1.18.1-cp39-cp39-win_amd64.whl"

if not exist "%SAFE_TEMP%" mkdir "%SAFE_TEMP%"
if not exist downloads mkdir downloads
set "TEMP=%SAFE_TEMP%"
set "TMP=%SAFE_TEMP%"

set "CONDA_BAT="
if exist "C:\ProgramData\Anaconda3\Library\bin\conda.bat" set "CONDA_BAT=C:\ProgramData\Anaconda3\Library\bin\conda.bat"
if not defined CONDA_BAT (
    for /f "delims=" %%I in ('where.exe conda.bat 2^>nul') do (
        set "CONDA_BAT=%%I"
        goto :conda_found
    )
)

:conda_found
if not defined CONDA_BAT (
    echo [ERROR] conda.bat not found.
    echo Please make sure Anaconda is installed.
    exit /b 1
)

echo [1/4] Checking conda...
call "%CONDA_BAT%" --version >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Conda is unavailable.
    exit /b 1
)

echo [2/4] Checking environment "%ENV_NAME%"...
call "%CONDA_BAT%" env list | findstr /b /c:"%ENV_NAME% " >nul
if errorlevel 1 (
    echo     Environment not found. Creating it now...
    call "%CONDA_BAT%" create -y -n "%ENV_NAME%" python=3.9
    if errorlevel 1 (
        echo     Online creation failed. Falling back to cloning base...
        call "%CONDA_BAT%" create -y -n "%ENV_NAME%" --clone base
        if errorlevel 1 (
            echo [ERROR] Failed to create conda environment.
            exit /b 1
        )
    )
) else (
    echo     Environment already exists.
)

echo [3/4] Activating environment...
call "%CONDA_BAT%" activate "%ENV_NAME%"
if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment.
    exit /b 1
)

echo [4/4] Checking Python dependencies...
python -c "import numpy" >nul 2>nul
if errorlevel 1 (
    echo     Installing numpy...
    python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org numpy>=1.26.0
    if errorlevel 1 exit /b 1
)

python -c "import requests" >nul 2>nul
if errorlevel 1 (
    echo     Installing requests...
    python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org requests>=2.32.0
    if errorlevel 1 exit /b 1
)

python -c "import imageio_ffmpeg" >nul 2>nul
if errorlevel 1 (
    echo     Installing imageio-ffmpeg...
    python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org imageio-ffmpeg>=0.5.1
    if errorlevel 1 exit /b 1
)

python -c "import cv2" >nul 2>nul
if errorlevel 1 (
    echo     Installing opencv-python...
    python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org opencv-python>=4.10.0
    if errorlevel 1 exit /b 1
)

python -c "import onnxruntime" >nul 2>nul
if errorlevel 1 (
    echo     Installing onnxruntime-gpu from local wheel / direct download...
    if not exist "%ORT_WHEEL%" (
        echo     Downloading GPU runtime wheel...
        curl.exe -L --fail --output "%ORT_WHEEL%" "%ORT_URL%"
        if errorlevel 1 (
            echo [ERROR] Failed to download onnxruntime-gpu wheel.
            exit /b 1
        )
    )
    python -m pip install --no-index --no-deps "%ORT_WHEEL%"
    if errorlevel 1 (
        echo [ERROR] Failed to install local onnxruntime-gpu wheel.
        exit /b 1
    )
)

echo Setup complete.
exit /b 0
