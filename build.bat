@echo off
setlocal

echo ============================================
echo   Audio dB Tweaker - Build Script
echo ============================================
echo.

REM --- Check that the icon file exists ---
if not exist "icon.ico" (
    echo [ERROR] icon.ico not found in this folder.
    echo Place your icon.ico next to this build.bat before running it.
    echo.
    pause
    exit /b 1
)

REM --- Check that the script exists ---
if not exist "audio_db_tweaker.py" (
    echo [ERROR] audio_db_tweaker.py not found in this folder.
    echo Place the script next to this build.bat before running it.
    echo.
    pause
    exit /b 1
)

REM --- Make sure PyInstaller is installed ---
echo Checking for PyInstaller...
python -m pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found. Installing it now...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo [ERROR] Failed to install PyInstaller. Check your Python/pip setup.
        pause
        exit /b 1
    )
)

echo.
echo Cleaning up previous build artifacts...
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"

echo.
echo Building the executable...
echo.
python -m PyInstaller --onefile --windowed --icon=icon.ico --add-data "icon.ico;." --name "Audio dB Tweaker" audio_db_tweaker.py

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. Check the messages above for details.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Build complete!
echo   Your executable is in the "dist" folder:
echo   dist\Audio dB Tweaker.exe
echo ============================================
echo.
pause
