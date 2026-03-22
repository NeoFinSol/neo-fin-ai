#!/usr/bin/env sh
set -e

MAX_RETRIES=${DB_WAIT_RETRIES:-30}
SLEEP_SECONDS=${DB_WAIT_SECONDS:-2}

echo "Waiting for database to be ready..."
MIGRATED=false
for i in $(seq 1 "$MAX_RETRIES"); do
  if alembic upgrade head; then
    MIGRATED=true
    echo "Database migrations applied."
    break
  fi
  echo "Database not ready (attempt $i/$MAX_RETRIES). Waiting ${SLEEP_SECONDS}s..."
  sleep "$SLEEP_SECONDS"
done

if [ "$MIGRATED" != true ]; then
  echo "Failed to apply database migrations after $MAX_RETRIES attempts"
  exit 1
fi

exec uvicorn src.app:app --host 0.0.0.0 --port 8000
