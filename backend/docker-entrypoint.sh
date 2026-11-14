#!/bin/sh
# Apply database migrations, then exec the container command (uvicorn by default).
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "[entrypoint] Running alembic upgrade head..."
    alembic upgrade head
fi

echo "[entrypoint] Starting: $*"
exec "$@"
