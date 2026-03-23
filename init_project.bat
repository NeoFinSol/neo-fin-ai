@echo off
REM Initialize Neo-Fin AI Project
REM This script is called during Visual Studio Build

echo.
echo ========================================
echo NeoFin AI - Project Initialization
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    exit /b 1
)

REM Check if virtual environment exists
if not exist "env" (
    echo Creating virtual environment...
    python -m venv env
    if errorlevel 1 (
        echo ERROR: Failed to create virtual environment
        exit /b 1
    )
)

REM Activate virtual environment and install dependencies
echo.
echo Installing dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install requirements
    exit /b 1
)

echo.
echo Checking pytest...
python -m pytest --version
if errorlevel 1 (
    echo ERROR: pytest not installed
    exit /b 1
)

echo.
echo ========================================
echo Project initialized successfully!
echo ========================================
echo.

exit /b 0
