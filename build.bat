@echo off
REM ============================================================================
REM  build.bat - Compile MI DES Fire EV1 Card Manager into a Windows .exe
REM
REM  Output: dist\MIDESFireEV1CardManager.exe  (single-file executable)
REM
REM  Uses the Python already on PATH (with PySide6 / pyscard / pycryptodome
REM  already installed). PyInstaller is installed automatically only if missing.
REM
REM  Usage: double-click build.bat, or run "build.bat" from a command prompt.
REM ============================================================================

setlocal enabledelayedexpansion
cd /d "%~dp0"

set APP_NAME=MIDESFireEV1CardManager
set ENTRY=main.py

echo.
echo [1/3] Checking build tools...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found on PATH.
    exit /b 1
)

python -c "import PyInstaller" >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found - installing...
    python -m pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: could not install PyInstaller. Install it manually with:
        echo         python -m pip install pyinstaller
        exit /b 1
    )
)

echo.
echo [2/3] Cleaning previous build artifacts...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
if exist "%APP_NAME%.spec" del /q "%APP_NAME%.spec"

echo.
echo [3/3] Building executable with PyInstaller...
python -m PyInstaller ^
    --name "%APP_NAME%" ^
    --onefile ^
    --windowed ^
    --noconfirm ^
    --clean ^
    --distpath "dist" ^
    --workpath "build" ^
    --collect-submodules smartcard ^
    --hidden-import Crypto ^
    "%ENTRY%"

if errorlevel 1 (
    echo.
    echo ERROR: build failed.
    exit /b 1
)

echo.
echo ============================================================================
echo  Build complete:  dist\%APP_NAME%.exe
echo ============================================================================
endlocal
