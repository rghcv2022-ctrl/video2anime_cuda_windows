@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "SAFE_TEMP=C:\Temp\conda_tmp"
if not exist "%SAFE_TEMP%" mkdir "%SAFE_TEMP%"
set "TEMP=%SAFE_TEMP%"
set "TMP=%SAFE_TEMP%"
set "PIP_DISABLE_PIP_VERSION_CHECK=1"
set "PYTHONUTF8=1"
set "ENV_NAME=video2anime39"
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

call "%~dp0setup_conda.bat"
if errorlevel 1 (
    echo [ERROR] setup_conda.bat failed.
    pause
    exit /b 1
)

call "%CONDA_BAT%" activate "%ENV_NAME%"
if errorlevel 1 (
    echo [ERROR] Failed to activate conda environment %ENV_NAME%.
    pause
    exit /b 1
)

python -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
    echo Installing PyInstaller...
    python -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pyinstaller pyinstaller-hooks-contrib
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller.
        pause
        exit /b 1
    )
) else (
    echo PyInstaller already available.
)

echo Cleaning old build output...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

echo Building slim packaged app (runtime downloads on first launch)...
python -m PyInstaller --noconfirm video2anime.spec
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo Build complete.
echo App path: %~dp0dist\Video2AnimeCUDA\Video2AnimeCUDA.exe
pause
exit /b 0
