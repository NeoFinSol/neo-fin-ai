@echo off
REM Neo Fin AI - Quick Start Scripts
REM Usage: Run from project root directory

setlocal enabledelayedexpansion

echo ========================================
echo Neo Fin AI - Project Management
echo ========================================
echo.
echo 1. Docker Compose Up (Recommended)
echo 2. Docker Compose Down
echo 3. View Logs
echo 4. Run Backend Only (Local)
echo 5. Run Frontend Only (Local)
echo 6. Install Dependencies
echo 7. Apply Migrations
echo 8. Exit
echo.

set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" (
    echo Starting Docker Compose...
    docker-compose up -d
    timeout /t 5
    echo.
    echo Backend: http://localhost:8000
    echo API Docs: http://localhost:8000/docs
    echo Frontend: http://localhost
    goto :end
)

if "%choice%"=="2" (
    echo Stopping Docker Compose...
    docker-compose down
    goto :end
)

if "%choice%"=="3" (
    echo Showing logs...
    docker-compose logs -f backend
    goto :end
)

if "%choice%"=="4" (
    echo Starting Backend (Local)...
    E:\neo-fin-ai\venv\Scripts\python.exe -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
    goto :end
)

if "%choice%"=="5" (
    echo Starting Frontend (Local)...
    cd frontend
    npm install
    npm run dev
    goto :end
)

if "%choice%"=="6" (
    echo Installing dependencies...
    echo.
    echo Installing Python dependencies...
    E:\neo-fin-ai\venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    echo Installing Frontend dependencies...
    cd frontend
    npm install
    cd ..
    goto :end
)

if "%choice%"=="7" (
    echo Applying migrations...
    E:\neo-fin-ai\venv\Scripts\python.exe -m alembic upgrade head
    goto :end
)

if "%choice%"=="8" (
    goto :end
)

echo Invalid choice!

:end
endlocal
