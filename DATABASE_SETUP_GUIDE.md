# 🗄️ ИНСТРУКЦИЯ ПО НАСТРОЙКЕ БАЗЫ ДАННЫХ

**Дата:** 23.03.2026  
**Статус:** Готово к использованию

---

## 📋 СОДЕРЖАНИЕ

1. [Быстрый старт с Docker](#быстрый-старт-с-docker)
2. [Локальная установка PostgreSQL](#локальная-установка-postgresql)
3. [Запуск миграций](#запуск-миграций)
4. [Запуск DB integration тестов](#запуск-db-integration-тестов)
5. [Troubleshooting](#troubleshooting)

---

## 🚀 БЫСТРЫЙ СТАРТ С DOCKER

### Требования:
- Docker Desktop (Windows/Mac/Linux)
- docker-compose v2+

### Шаг 1: Запуск баз данных

```bash
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

```bash
# Проверка main БД
docker-compose exec db psql -U postgres -d neofin -c "SELECT 1"

# Проверка test БД
docker-compose exec db_test psql -U postgres -d neofin_test -c "SELECT 1"
```

### Шаг 3: Запуск миграций

```bash
# Применить все миграции
alembic upgrade head

# Проверить статус миграций
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

3. **Создать тестовую БД:**
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

## 🔧 ЗАПУСК МИГРАЦИЙ

### Предварительные требования:

1. Убедитесь что `.env` файл настроен:
```bash
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/neofin
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5433/neofin_test
```

2. Установлены зависимости:
```bash
pip install -r requirements.txt
```

### Применение миграций:

```bash
# Перейти в директорию проекта
cd e:\neo-fin-ai

# Применить все миграции
alembic upgrade head

# Проверить текущую ревизию
alembic current

# Показать историю миграций
alembic history
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
export DATABASE_URL=postgresql+asyncpg://<user>:<password>@localhost:5432/neofin
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
- [ ] Порты 5432 и 5433 открыты
- [ ] Миграции применены (`alembic current` показывает `0001_create_analyses`)
- [ ] DB integration тест проходит

### Команды для проверки:

```bash
# 1. Проверка Docker
docker-compose ps

# 2. Проверка подключения к БД
docker-compose exec db psql -U postgres -d neofin -c "SELECT version()"

# 3. Проверка миграций
alembic current

# 4. Запуск тестов
pytest tests/test_db_integration.py -v
```

---

## 🔐 БЕЗОПАСНОСТЬ

### Рекомендации для production:

1. **Не используйте пароли по умолчанию:**
   ```bash
   # Измените в docker-compose.yml
   POSTGRES_PASSWORD=<secure_password>
   ```

2. **Не публикуйте порты наружу:**
   ```yaml
   # Уберите ports из production docker-compose
   # ports:
   #   - "5432:5432"
   ```

3. **Используйте secrets:**
   ```yaml
   # Для Docker Swarm/Kubernetes
   secrets:
     - db_password
   ```

4. **Регулярные бэкапы:**
   ```bash
   docker-compose exec db pg_dump -U postgres neofin > backup.sql
   ```

---

## 📚 ДОПОЛНИТЕЛЬНЫЕ РЕСУРСЫ

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Docker Compose Reference](https://docs.docker.com/compose/)
- [SQLAlchemy Async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)

---

*Инструкция актуальна для версии проекта NeoFin AI 0.1.0*
