# 🗄️ ИНСТРУКЦИЯ ПО НАСТРОЙКЕ БАЗЫ ДАННЫХ

**Дата:** 23.03.2026  
**Статус:** Готово к использованию  
**Уровень безопасности:** ⚠️ Требует настройки переменных окружения для production

---

## 📋 СОДЕРЖАНИЕ

1. [Быстрый старт с Docker](#быстрый-старт-с-docker)
2. [Локальная установка PostgreSQL](#локальная-установка-postgresql)
3. [Настройка переменных окружения](#настройка-переменных-окружения)
4. [Запуск миграций](#запуск-миграций)
5. [Запуск DB integration тестов](#запуск-db-integration-тестов)
6. [Troubleshooting](#troubleshooting)

---

## 🚀 БЫСТРЫЙ СТАРТ С DOCKER

### Требования:
- Docker Desktop (Windows/Mac/Linux)
- docker-compose v2+

### Шаг 1: Запуск баз данных

```bash
# Перейти в директорию проекта
cd <project-root>  # Например: cd e:\neo-fin-ai (Windows) или cd ~/neo-fin-ai (Linux/Mac)

# Запустить только PostgreSQL (main + test)
docker-compose up -d db db_test

# Проверить статус
docker-compose ps
```

**Ожидаемый результат:**
```
NAME                STATUS                   PORTS
db                  Up (healthy)             0.0.0.0:5432->5432
db_test             Up (healthy)             0.0.0.0:5433->5432
```

### Шаг 2: Проверка подключения

**Вариант A: Через docker-compose (рекомендуется):**
```bash
# Проверка main БД (через internal network)
docker-compose exec db psql -U postgres -d neofin -c "SELECT 1"

# Проверка test БД
docker-compose exec db_test psql -U postgres -d neofin_test -c "SELECT 1"
```

**Вариант B: Через опубликованные порты:**
```bash
# Main БД (порт 5432)
psql -h localhost -p 5432 -U postgres -d neofin -c "SELECT 1"

# Test БД (порт 5433)
psql -h localhost -p 5433 -U postgres -d neofin_test -c "SELECT 1"
```

⚠️ **Важно:** Пароль по умолчанию `postgres` используется ТОЛЬКО для локальной разработки!

### Шаг 3: Настройка переменных окружения

Создайте файл `.env` в корне проекта (не коммитьте в git!):

```bash
# .env файл (НЕ для production!)
# ⚠️ ЗАМЕНИТЕ ПАРОЛИ НА БЕЗОПАСНЫЕ ЗНАЧЕНИЯ!

DATABASE_URL=postgresql+asyncpg://postgres:<YOUR_PASSWORD>@localhost:5432/neofin
TEST_DATABASE_URL=postgresql+asyncpg://postgres:<YOUR_PASSWORD>@localhost:5433/neofin_test

# Qwen AI API configuration (опционально)
# QWEN_API_KEY=<your_api_key>
# QWEN_API_URL=https://api.qwen.ai/v1
```

🔐 **Для production используйте secrets:**

```yaml
# docker-compose.prod.yml
services:
  db:
    environment:
      POSTGRES_PASSWORD_FILE: /run/secrets/db_password
    secrets:
      - db_password

secrets:
  db_password:
    external: true
```

### Шаг 4: Запуск миграций

**Вариант A: С использованием .env файла:**
```bash
# Alembic автоматически загрузит DATABASE_URL из .env
alembic upgrade head
```

**Вариант B: Явная передача DATABASE_URL:**

Bash (Linux/Mac):
```bash
export DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/neofin"
alembic upgrade head
```

PowerShell (Windows):
```powershell
$env:DATABASE_URL="postgresql+asyncpg://postgres:password@localhost:5432/neofin"
alembic upgrade head
```

**Вариант C: С указанием конфигурационного файла:**
```bash
alembic -c alembic.ini upgrade head
```

**Проверка статуса:**
```bash
alembic current
```

**Ожидаемый результат:**
```
0001_create_analyses (head)
```

---

## 💻 ЛОКАЛЬНАЯ УСТАНОВКА POSTGRESQL

### Windows

1. **Скачать PostgreSQL:**
   - Посетите https://www.postgresql.org/download/windows/
   - Или используйте Chocolatey: `choco install postgresql`

2. **Установить:**
   ```bash
   # Запомните пароль для пользователя postgres
   # Порт по умолчанию: 5432
   ```

3. **Создать базы данных:**
   ```bash
   psql -U postgres
   CREATE DATABASE neofin;
   CREATE DATABASE neofin_test;
   \q
   ```

### macOS

```bash
# Через Homebrew
brew install postgresql@16
brew services start postgresql@16

# Создать БД
createdb neofin
createdb neofin_test
```

### Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install postgresql postgresql-contrib

# Запустить сервис
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Создать БД
sudo -u postgres createdb neofin
sudo -u postgres createdb neofin_test
```

---

## 🔧 ЗАПУСК МИГРАЦИЙ (ПОДРОБНО)

### Предварительные требования:

1. Убедитесь что `.env` файл настроен (см. выше)
2. Установлены зависимости:
   ```bash
   pip install -r requirements.txt
   ```

### Применение миграций:

```bash
# Перейти в директорию проекта
cd <project-root>

# Применить все миграции
alembic upgrade head

# Проверить текущую ревизию
alembic current

# Показать историю миграций
alembic history --verbose
```

### Откат миграций:

```bash
# Откатить одну миграцию
alembic downgrade -1

# Откатить все миграции
alembic downgrade base

# Откатить к конкретной ревизии
alembic downgrade <revision_id>
```

---

## 🧪 ЗАПУСК DB INTEGRATION ТЕСТОВ

### Шаг 1: Подготовить окружение

```bash
# Установить dev зависимости
pip install -r requirements-dev.txt

# Убедиться что БД запущены
docker-compose ps
```

### Шаг 2: Запустить тесты

```bash
# Запустить все тесты включая DB integration
python -m pytest tests/test_db_integration.py -v

# Запустить с покрытием
python -m pytest tests/test_db_integration.py -v --cov=src/db
```

### Ожидаемый результат:

```
tests/test_db_integration.py::test_analysis_crud_roundtrip PASSED [100%]

============================== 1 passed in 0.5s ==============================
```

---

## 🔧 TROUBLESHOOTING

### ❌ Ошибка: "connection refused"

**Проблема:** PostgreSQL не запущен или недоступен

**Решение:**
```bash
# Проверить статус Docker контейнеров
docker-compose ps

# Перезапустить БД
docker-compose restart db db_test

# Проверить логи
docker-compose logs db
```

### ❌ Ошибка: "database does not exist"

**Проблема:** Базы данных не созданы

**Решение:**
```bash
# Подключиться к PostgreSQL
docker-compose exec db psql -U postgres

# Создать БД вручную
CREATE DATABASE neofin;

# Выйти
\q
```

### ❌ Ошибка: "role postgres does not exist"

**Проблема:** Пользователь не найден

**Решение:**
```bash
# Использовать текущего пользователя
# Bash/Linux:
export DATABASE_URL="postgresql+asyncpg://<user>:<password>@localhost:5432/neofin"

# PowerShell/Windows:
$env:DATABASE_URL="postgresql+asyncpg://<user>:<password>@localhost:5432/neofin"
```

### ❌ Ошибка: "migration already applied"

**Проблема:** Миграции уже применены

**Решение:**
```bash
# Проверить текущее состояние
alembic current

# Если нужно, откатить и применить заново
alembic downgrade base
alembic upgrade head
```

### ❌ Docker Desktop error 500

**Проблема:** Docker Desktop не работает корректно

**Решение:**
1. Перезапустить Docker Desktop
2. Проверить настройки WSL2 (для Windows)
3. Очистить кэш Docker:
   ```bash
   docker system prune -a
   ```

---

## 📊 ПРОВЕРКА УСТАНОВКИ

### Чек-лист успешной настройки:

- [ ] Docker запущен и доступен
- [ ] Контейнеры `db` и `db_test` в статусе `Up (healthy)`
- [ ] Порты 5432 и 5433 открыты (только для development!)
- [ ] `.env` файл настроен с безопасными паролями
- [ ] Миграции применены (`alembic current` показывает `0001_create_analyses`)
- [ ] DB integration тест проходит

### Команды для проверки:

```bash
# 1. Проверка Docker
docker-compose ps

# 2. Проверка подключения к БД (internal network)
docker-compose exec db psql -U postgres -d neofin -c "SELECT version()"

# 3. Проверка миграций
alembic current

# 4. Запуск тестов
pytest tests/test_db_integration.py -v
```

---

## 🔐 БЕЗОПАСНОСТЬ

### ⚠️ КРИТИЧЕСКИ ВАЖНО ДЛЯ PRODUCTION:

1. **НИКОГДА не используйте пароли по умолчанию:**
   ```bash
   # ПЛОХО:
   POSTGRES_PASSWORD=postgres
   
   # ХОРОШО:
   POSTGRES_PASSWORD=<secure_random_password_32_chars>
   ```

2. **Не публикуйте порты наружу в production:**
   ```yaml
   # docker-compose.prod.yml
   db:
     # Уберите публикацию портов!
     # ports:
     #   - "5432:5432"
     
     # Используйте internal network
     networks:
       - backend-network
   ```

3. **Используйте secrets для управления паролями:**
   ```yaml
   # Docker Swarm example
   services:
     db:
       environment:
         POSTGRES_PASSWORD_FILE: /run/secrets/db_password
       secrets:
         - db_password
   
   secrets:
     db_password:
       external: true  #或使用 file:/path/to/secret
   ```

4. **Изолируйте базы данных:**
   ```yaml
   networks:
     backend-network:
       driver: bridge
       internal: true  # Нет доступа извне
   ```

5. **Регулярные бэкапы:**
   ```bash
   # Создать бэкап
   docker-compose exec db pg_dump -U postgres neofin > backup_$(date +%Y%m%d).sql
   
   # Восстановить из бэкапа
   cat backup_20260323.sql | docker-compose exec -T db psql -U postgres neofin
   ```

6. **.env файл НЕ должен попадать в git:**
   ```bash
   # Проверьте .gitignore
   echo ".env" >> .gitignore
   
   # Удалите из git если уже добавлен
   git rm --cached .env
   ```

### Рекомендации по генерации паролей:

```bash
# Linux/Mac
openssl rand -base64 32

# Python
python -c "import secrets; print(secrets.token_urlsafe(32))"

# PowerShell
[System.Web.Security.Membership]::GeneratePassword(32, 4)
```

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
- [Docker Secrets](https://docs.docker.com/engine/swarm/secrets/)

---

*Инструкция актуальна для версии проекта NeoFin AI 0.1.0*  
**Последнее обновление:** 23.03.2026  
**Уровень безопасности:** Требуется настройка production переменных окружения
