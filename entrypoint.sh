#!/bin/sh
set -e

PORT="${PORT:-8000}"

# If running as root (PaaS host volume mount like Render/Fly/Railway with RAILWAY_RUN_UID=0),
# fix permissions of persistent data directory and drop privileges to hoptrace.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data
    chown -R hoptrace:hoptrace /app/data
    chmod 775 /app/data

    if [ "$1" = "uvicorn" ] || [ $# -eq 0 ]; then
        exec gosu hoptrace uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
    fi
    exec gosu hoptrace "$@"
fi

if [ "$1" = "uvicorn" ] || [ $# -eq 0 ]; then
    exec uvicorn app.main:app --host 0.0.0.0 --port "$PORT"
fi

exec "$@"
