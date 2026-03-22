# 🔄 CI/CD РУКОВОДСТВО

**Дата:** 23.03.2026  
**Статус:** Готово к использованию  
**Платформа:** GitHub Actions

---

## 📋 СОДЕРЖАНИЕ

1. [Обзор](#обзор)
2. [Настроенные workflow](#настроенные-workflow)
3. [Как это работает](#как-это-работает)
4. [Запуск вручную](#запуск-вручную)
5. [Мониторинг](#мониторинг)
6. [Troubleshooting](#troubleshooting)

---

## 🎯 ОБЗОР

Проект NeoFin AI использует GitHub Actions для автоматизации:

- ✅ **Continuous Integration (CI)** — автоматическое тестирование при каждом commit
- ✅ **Code Quality** — проверка стиля, покрытия, типов
- ✅ **Security Scanning** — поиск уязвимостей в зависимостях
- ✅ **Docker Build** — сборка и тестирование контейнеров

---

## 📁 НАСТРОЕННЫЕ WORKFLOW

### 1️⃣ `.github/workflows/ci.yml` — Основной CI Pipeline

**Срабатывает при:**
- Push на ветки `main` или `develop`
- Создании Pull Request в `main`

**Включает jobs:**

#### 🔹 Lint
- Проверка синтаксиса Python
- Стиль кода (flake8, black, isort)
- Сложность кода (cyclomatic complexity)

#### 🔹 Test
- Запуск unit тестов
- Запуск integration тестов
- Тестирование API endpoints
- PostgreSQL базы данных (main + test)
- Артефакты: test-results.xml

#### 🔹 Security
- Bandit security scan
- pip-audit проверка уязвимостей
- Safety check зависимостей
- Артефакты: security reports

#### 🔹 Build
- Сборка Docker образов
- Тестирование контейнеров
- Проверка docker-compose

---

### 2️⃣ `.github/workflows/code-quality.yml` — Code Quality

**Срабатывает при:**
- Pull Request в `main` или `develop`

**Включает jobs:**

#### 🔹 Coverage
- Запуск тестов с coverage
- Генерация HTML отчета
- Проверка порога покрытия (≥70%)
- Артефакты: coverage-report

#### 🔹 Type Check
- MyPy статический анализ типов
- Проверка type hints
- Игнорирование missing imports

---

## ⚙️ КАК ЭТО РАБОТАЕТ

### Стандартный workflow:

```
Developer делает commit
         ↓
   GitHub触发 CI
         ↓
   ┌───────────────┐
   │    Lint Job   │ → Проверка стиля кода
   └───────────────┘
         ↓
   ┌───────────────┐
   │   Test Job    │ → Запуск всех тестов
   └───────────────┘
         ↓
   ┌───────────────┐
   │ Security Job  │ → Сканирование уязвимостей
   └───────────────┘
         ↓
   ┌───────────────┐
   │  Build Job    │ → Сборка Docker
   └───────────────┘
         ↓
    ✅ Success / ❌ Failure
```

### Статусы проверок:

- 🟢 **Success** — все проверки пройдены
- 🔴 **Failure** — одна или более проверок не прошли
- 🟡 **In Progress** — проверки выполняются
- ⚪ **Skipped** — проверки пропущены

---

## 🚀 ЗАПУСК ВРУЧНУЮ

### Через GitHub UI:

1. Перейти на вкладку **Actions** репозитория
2. Выбрать нужный workflow (CI/CD Pipeline или Code Quality)
3. Нажать **Run workflow**
4. Выбрать ветку
5. Нажать **Run workflow**

### Через GitHub CLI:

```bash
# Установить GitHub CLI (если не установлен)
# Windows: winget install GitHub.cli
# macOS: brew install gh
# Linux: sudo apt install gh

# Авторизоваться
gh auth login

# Запустить workflow
gh workflow run ci.yml --ref main

# Проверить статус
gh run list
gh run watch <RUN_ID>
```

### Триггеры:

```bash
# Commit message с [skip ci] пропускает CI
git commit -m "Docs: update README [skip ci]"

# Commit message с [ci full] запускает все проверки
git commit -m "Feature: add new endpoint [ci full]"
```

---

## 📊 МОНИТОРИНГ

### GitHub Actions Dashboard:

1. **Repository → Actions tab**
   - Список всех workflow runs
   - Статус выполнения
   - Время выполнения

2. **Workflow Run Details**
   - Логи каждого job
   - Артефакты (test results, coverage reports)
   - Время каждого step

### Бейджи в README:

Добавьте в `README.md`:

```markdown
![CI/CD](https://github.com/NeoFinSol/neo-fin-ai/actions/workflows/ci.yml/badge.svg)
![Code Quality](https://github.com/NeoFinSol/neo-fin-ai/actions/workflows/code-quality.yml/badge.svg)
```

---

## 🔧 TROUBLESHOOTING

### ❌ Workflow не запускается

**Проблема:** Workflow не появляется в Actions

**Решение:**
```bash
# Проверить путь к файлу
ls -la .github/workflows/

# Проверить синтаксис YAML
yamllint .github/workflows/ci.yml

# Проверить права доступа
# Settings → Actions → General → Allow all actions
```

### ❌ Test job fails with database error

**Проблема:** PostgreSQL не запустился

**Решение:**
```yaml
# Увеличить healthcheck timeout в ci.yml
services:
  postgres:
    options: >-
      --health-interval 15s  # Было 10s
      --health-retries 10    # Было 5
```

### ❌ Coverage ниже порога

**Проблема:** Покрытие упало ниже 70%

**Решение:**
1. Посмотреть отчет о покрытии (артефакт coverage-report)
2. Добавить тесты для непокрытого кода
3. Или снизить порог в code-quality.yml (не рекомендуется)

### ❌ Docker build fails

**Проблема:** Ошибка сборки Docker образа

**Решение:**
```bash
# Локальная сборка для отладки
docker-compose build backend

# Проверка Dockerfile
docker build -t neofin-backend .

# Очистка кэша
docker system prune -a
```

### ❌ Security scan нашел уязвимости

**Проблема:** pip-audit или safety нашли уязвимые зависимости

**Решение:**
```bash
# Обновить зависимости
pip install --upgrade package-name

# Или обновить все
pip-review --interactive

# Если уязвимость не критична, добавить игнор
# pip-audit-ignore.txt
package-name==1.2.3  # CVE-2024-XXXXX
```

---

## 📈 BEST PRACTICES

### 1. Оптимизация времени выполнения:

```yaml
# Кэширование зависимостей
- uses: actions/setup-python@v5
  with:
    cache: 'pip'

# Параллельный запуск независимых jobs
jobs:
  lint:
    # ...
  test:
    needs: []  # Не ждать другие jobs
  security:
    needs: []
```

### 2. Управление артефактами:

```yaml
# Сохранять артефакты только при failure
- uses: actions/upload-artifact@v4
  if: failure()
  with:
    name: test-results
    path: test-results.xml
```

### 3. Notification:

```yaml
# Уведомления в Slack/Discord
- name: Notify on failure
  if: failure()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "❌ CI failed for ${{ github.repository }}"
      }
```

---

## 🔐 БЕЗОПАСНОСТЬ

### Required GitHub Secrets:

Настройте следующие секреты в репозитории:

```bash
# Перейти в: Settings → Secrets and variables → Actions
# Нажать: New repository secret

# Обязательно настройте:
DATABASE_PASSWORD          # Пароль PostgreSQL (используется в ci.yml)
QWEN_API_KEY               # API ключ Qwen AI
QWEN_API_URL               # URL Qwen API (например, https://api.qwen.ai/v1)
CORS_ALLOW_ORIGINS         # Разрешенные CORS origin (через запятую)
CORS_ALLOW_METHODS         # Разрешенные HTTP методы
CORS_ALLOW_HEADERS         # Разрешенные заголовки
CORS_ALLOW_CREDENTIALS     # Разрешить credentials (true/false)
```

### Secrets Management:

1. **Не коммитьте секреты в код!**
2. Используйте GitHub Secrets для всех чувствительных данных
3. Workflow автоматически подставляет секреты через environment variables

Пример настройки секретов:

```bash
# Через GitHub UI:
1. Repository Settings → Secrets and variables → Actions
2. New repository secret
3. Name: DATABASE_PASSWORD
4. Value: <your_secure_password>
5. Repeat for all required secrets

# Через GitHub CLI:
gh secret set DATABASE_PASSWORD --body "<your_password>"
gh secret set QWEN_API_KEY --body "<your_api_key>"
gh secret set QWEN_API_URL --body "https://api.qwen.ai/v1"
```

Использование в workflow:
```yaml
env:
  DATABASE_URL: postgresql+asyncpg://postgres:${{ secrets.DB_PASSWORD }}@localhost:5432/neofin
  QWEN_API_KEY: ${{ secrets.QWEN_API_KEY }}
```

### Branch Protection:

```markdown
Settings → Branches → Add rule:
- Branch name pattern: main
- Require pull request reviews before merging: ✅
- Require status checks to pass before merging: ✅
  - Required status checks: lint, test, security
- Require branches to be up to date before merging: ✅
```

---

## 📊 METRICS

### Отслеживаемые метрики:

| Метрика | Порог | Текущее значение |
|---------|-------|------------------|
| **Test Coverage** | ≥70% | ~80% ✅ |
| **Build Time** | <10 min | ~5 min ✅ |
| **Test Duration** | <5 min | ~4 min ✅ |
| **Security Issues** | 0 critical | 0 ✅ |

---

## 🎯 СЛЕДУЮЩИЕ ШАГИ

### Рекомендуется добавить:

1. **CD Pipeline** — автоматический deploy на staging/production
2. **Performance Tests** — нагрузочное тестирование
3. **E2E Tests** — end-to-end тестирование
4. **Dependency Review** — автоматическая проверка PR на уязвимости
5. **Code Climate** — интеграция с code quality platforms

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Workflow Syntax Reference](https://docs.github.com/en/actions/reference/workflow-syntax-for-github-actions)
- [Python for GitHub Actions](https://docs.github.com/en/actions/guides/building-and-testing-python)
- [Docker in GitHub Actions](https://docs.github.com/en/actions/guides/publishing-docker-images)

---

*Руководство актуально для версии проекта NeoFin AI 0.1.0*  
**Последнее обновление:** 23.03.2026
