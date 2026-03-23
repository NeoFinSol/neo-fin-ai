# NeoFin AI - Инициализация проекта (PowerShell версия)
# Выполняет все необходимые шаги для подготовки проекта к разработке

param(
    [switch]$Force = $false,
    [switch]$DevOnly = $false
)

$ErrorActionPreference = "Stop"

function Write-Header {
    param([string]$Text)
    Write-Host "`n" + ("="*60) -ForegroundColor Cyan
    Write-Host "📋 $Text" -ForegroundColor Cyan
    Write-Host ("="*60) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "✅ $Text" -ForegroundColor Green
}

function Write-Error-Custom {
    param([string]$Text)
    Write-Host "❌ $Text" -ForegroundColor Red
}

function Write-Info {
    param([string]$Text)
    Write-Host "ℹ️  $Text" -ForegroundColor Blue
}

# Проверка Python
Write-Header "Проверка Python"
try {
    $pythonVersion = python --version 2>&1
    Write-Success "$pythonVersion"
} catch {
    Write-Error-Custom "Python не установлен или не в PATH"
    exit 1
}

# Создание виртуального окружения
Write-Header "Виртуальное окружение"
if ((Test-Path "env") -and -not $Force) {
    Write-Success "Окружение уже существует (используйте -Force для переустановки)"
} else {
    Write-Info "Создание виртуального окружения..."
    python -m venv env
    Write-Success "Окружение создано"
}

# Активация окружения в PowerShell
Write-Header "Активация окружения"
$activateScript = ".\env\Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    & $activateScript
    Write-Success "Окружение активировано"
} else {
    Write-Error-Custom "Скрипт активации не найден"
    exit 1
}

# Обновление pip
Write-Header "Обновление pip"
python -m pip install --upgrade pip
Write-Success "pip обновлен"

# Установка production зависимостей
Write-Header "Installation production зависимостей"
python -m pip install -r requirements.txt --no-cache-dir
Write-Success "Production зависимости установлены"

# Установка development зависимостей
if (-not $DevOnly -or $DevOnly) {
    Write-Header "Установка development зависимостей"
    python -m pip install -r requirements-dev.txt --no-cache-dir
    Write-Success "Development зависимости установлены"
}

# Проверка установки
Write-Header "Проверка установки"

$packages = @(
    @{Name = "pytest"; Check = "python -m pytest --version"},
    @{Name = "fastapi"; Check = "python -c 'import fastapi; print(fastapi.__version__)'"},
    @{Name = "sqlalchemy"; Check = "python -c 'import sqlalchemy; print(sqlalchemy.__version__)'"},
    @{Name = "pydantic"; Check = "python -c 'import pydantic; print(pydantic.__version__)'"}
)

foreach ($pkg in $packages) {
    try {
        $output = & $pkg.Check 2>&1
        Write-Success "$($pkg.Name): $output"
    } catch {
        Write-Error-Custom "$($pkg.Name): не установлен или ошибка"
    }
}

# Финальное сообщение
Write-Header "🎉 Инициализация завершена!"
Write-Host "`n📝 Следующие шаги:`n" -ForegroundColor Cyan
Write-Info "1. Приложение уже активировано в этом терминале"
Write-Info "2. Запустите приложение: python src/app.py"
Write-Info "3. Или запустите тесты: python -m pytest tests/ -v"
Write-Info "4. Подробнее в BUILD_GUIDE.md"
Write-Host ""
