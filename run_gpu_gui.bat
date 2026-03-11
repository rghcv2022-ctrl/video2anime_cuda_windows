@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "SAFE_TEMP=C:\Temp\conda_tmp"
if not exist "%SAFE_TEMP%" mkdir "%SAFE_TEMP%"
set "TEMP=%SAFE_TEMP%"
set "TMP=%SAFE_TEMP%"
set "PYTHONUTF8=1"
set "CONDA_BAT=C:\ProgramData\Anaconda3\Library\bin\conda.bat"

if not exist "%CONDA_BAT%" (
    for /f "delims=" %%I in ('where.exe conda.bat 2^>nul') do (
        set "CONDA_BAT=%%I"
        goto :conda_found
    )
)

:conda_found
if not exist "%CONDA_BAT%" (
    echo [ERROR] conda.bat not found.
    pause
    exit /b 1
)

call "%CONDA_BAT%" activate video2anime39
if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment video2anime39.
    pause
    exit /b 1
)

echo Starting GPU-ready GUI from conda environment...
python app.py
set "APP_EXIT=%ERRORLEVEL%"
if not "%APP_EXIT%"=="0" (
    echo.
    echo [ERROR] App exited with code %APP_EXIT%.
    pause
)
exit /b %APP_EXIT%
