# NeoFin AI - Production Deployment Script (PowerShell)
# Usage: .\scripts\deploy-prod.ps1
#
# This script:
#   1. Validates .env file exists
#   2. Builds all Docker images
#   3. Runs database migrations
#   4. Starts all services
#   5. Shows service status

$ErrorActionPreference = "Stop"

# Configuration
$ComposeFile = "docker-compose.prod.yml"
$EnvFile = ".env"

Write-Host "========================================" -ForegroundColor Green
Write-Host "NeoFin AI - Production Deployment" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Step 1: Validate .env file
Write-Host "[1/5] Validating environment..." -ForegroundColor Yellow
if (-not (Test-Path $EnvFile)) {
    Write-Host "ERROR: $EnvFile not found!" -ForegroundColor Red
    Write-Host "Please copy .env.example to .env and fill in required values."
    exit 1
}

# Check required variables
$requiredVars = @("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "API_KEY")
foreach ($var in $requiredVars) {
    $content = Get-Content $EnvFile -Raw
    if (-not ($content -match "^$var=.+")) {
        Write-Host "ERROR: Required variable $var is not set in $EnvFile" -ForegroundColor Red
        exit 1
    }
}

Write-Host "Environment validated" -ForegroundColor Green
Write-Host ""

# Step 2: Build all images
Write-Host "[2/5] Building Docker images..." -ForegroundColor Yellow
docker-compose -f $ComposeFile build --no-cache
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host "Images built" -ForegroundColor Green
Write-Host ""

# Step 3: Run database migrations
Write-Host "[3/5] Running database migrations..." -ForegroundColor Yellow
docker-compose -f $ComposeFile run --rm backend-migrate
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host "Migrations completed" -ForegroundColor Green
Write-Host ""

# Step 4: Start all services
Write-Host "[4/5] Starting services..." -ForegroundColor Yellow
docker-compose -f $ComposeFile up -d
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Host "Services started" -ForegroundColor Green
Write-Host ""

# Step 5: Show status
Write-Host "[5/5] Service status:" -ForegroundColor Yellow
docker-compose -f $ComposeFile ps

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Deployment complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Frontend: http://localhost" -ForegroundColor Cyan
Write-Host "Backend API: http://localhost/api/" -ForegroundColor Cyan
Write-Host "Health check: http://localhost/system/health" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs:" -ForegroundColor Yellow
Write-Host "  docker-compose -f $ComposeFile logs -f"
Write-Host ""
Write-Host "To stop services:" -ForegroundColor Yellow
Write-Host "  docker-compose -f $ComposeFile down"
Write-Host ""
Write-Host "To restart services:" -ForegroundColor Yellow
Write-Host "  docker-compose -f $ComposeFile restart"
Write-Host ""
