@echo off
REM Build script for ADB Transfer Tool
REM Creates a standalone .exe file

echo ========================================
echo   ADB Transfer Tool - Build Script
echo ========================================
echo.

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERREUR: Impossible d'installer PyInstaller
        pause
        exit /b 1
    )
)

echo.
echo Building executable...
echo.

REM Build using spec file
pyinstaller --clean adb_transfer.spec

if errorlevel 1 (
    echo.
    echo ERREUR: Build failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo   Build Complete!
echo ========================================
echo.
echo Executable created at: dist\ADB_Transfer_Tool.exe
echo.
echo NOTE: Git auto-update will NOT work with .exe
echo       Users must download new .exe from GitHub Releases
echo.
pause
