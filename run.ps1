# Neo Fin AI - Quick Start Scripts (PowerShell)
# Usage: .\run.ps1

param(
    [string]$Command = ""
)

function Show-Menu {
    Clear-Host
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Neo Fin AI - Project Management" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Usage: .\run.ps1 -Command <command_name>" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Available Commands:" -ForegroundColor Green
    Write-Host ""
    Write-Host "  docker-up           Docker Compose Up (Recommended)" -ForegroundColor White
    Write-Host "  docker-down         Docker Compose Down" -ForegroundColor White
    Write-Host "  logs                View Backend Logs" -ForegroundColor White
    Write-Host "  backend             Run Backend Only (Local)" -ForegroundColor White
    Write-Host "  frontend            Run Frontend Only (Local)" -ForegroundColor White
    Write-Host "  install             Install Dependencies" -ForegroundColor White
    Write-Host "  migrate             Apply Database Migrations" -ForegroundColor White
    Write-Host "  clean               Clean and Reset (Remove volumes)" -ForegroundColor Red
    Write-Host ""
}

function Invoke-DockerUp {
    Write-Host "Starting Docker Compose..." -ForegroundColor Green
    docker-compose up -d
    Start-Sleep -Seconds 5
    Write-Host ""
    Write-Host "Services started!" -ForegroundColor Green
    Write-Host "  Backend:    http://localhost:8000" -ForegroundColor Cyan
    Write-Host "  API Docs:   http://localhost:8000/docs" -ForegroundColor Cyan
    Write-Host "  Frontend:   http://localhost" -ForegroundColor Cyan
}

function Invoke-DockerDown {
    Write-Host "Stopping Docker Compose..." -ForegroundColor Yellow
    docker-compose down
    Write-Host "Done!" -ForegroundColor Green
}

function Invoke-DockerLogs {
    Write-Host "Showing Backend Logs (Press Ctrl+C to exit)..." -ForegroundColor Yellow
    docker-compose logs -f backend
}

function Invoke-Backend {
    Write-Host "Starting Backend (Local)..." -ForegroundColor Green
    Write-Host "Backend running on http://localhost:8000" -ForegroundColor Cyan

    # Use relative path for virtual environment
    $pythonPath = ".\env\Scripts\python.exe"

    if (-not (Test-Path $pythonPath)) {
        Write-Host "ERROR: Virtual environment not found at $pythonPath" -ForegroundColor Red
        Write-Host "Please run: python -m venv env" -ForegroundColor Yellow
        return
    }

    & $pythonPath -m uvicorn src.app:app --reload --host 0.0.0.0 --port 8000
}

function Invoke-Frontend {
    Write-Host "Starting Frontend (Local)..." -ForegroundColor Green
    Set-Location frontend
    npm install
    npm run dev
}

function Invoke-Install {
    Write-Host "Installing Dependencies..." -ForegroundColor Green
    Write-Host ""
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow

    # Use relative path for virtual environment
    $pythonPath = ".\env\Scripts\python.exe"

    if (-not (Test-Path $pythonPath)) {
        Write-Host "ERROR: Virtual environment not found at $pythonPath" -ForegroundColor Red
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv env
    }

    & $pythonPath -m pip install -r requirements.txt -q
    Write-Host ""
    Write-Host "Installing Frontend dependencies..." -ForegroundColor Yellow
    Set-Location frontend
    npm install
    Set-Location ..
    Write-Host "Done!" -ForegroundColor Green
}

function Invoke-Migrate {
    Write-Host "Applying Database Migrations..." -ForegroundColor Green

    # Use relative path for virtual environment
    $pythonPath = ".\env\Scripts\python.exe"

    if (-not (Test-Path $pythonPath)) {
        Write-Host "ERROR: Virtual environment not found at $pythonPath" -ForegroundColor Red
        Write-Host "Please run: python -m venv env" -ForegroundColor Yellow
        return
    }

    & $pythonPath -m alembic upgrade head
}

function Invoke-Clean {
    Write-Host "Cleaning Docker resources..." -ForegroundColor Red
    Write-Host "WARNING: This will delete all containers and volumes!" -ForegroundColor Red
    $confirm = Read-Host "Continue? (yes/no)"
    if ($confirm -eq "yes") {
        docker-compose down -v
        Write-Host "Done!" -ForegroundColor Green
    } else {
        Write-Host "Cancelled." -ForegroundColor Yellow
    }
}

# Execute command
if ([string]::IsNullOrEmpty($Command)) {
    Show-Menu
    Write-Host ""
    $Command = Read-Host "Enter command"
}

switch ($Command.ToLower()) {
    "docker-up" { Invoke-DockerUp; break }
    "docker-down" { Invoke-DockerDown; break }
    "logs" { Invoke-DockerLogs; break }
    "backend" { Invoke-Backend; break }
    "frontend" { Invoke-Frontend; break }
    "install" { Invoke-Install; break }
    "migrate" { Invoke-Migrate; break }
    "clean" { Invoke-Clean; break }
    default { Write-Host "Unknown command: $Command" -ForegroundColor Red; Show-Menu }
}
