#!/bin/sh
set -e

# If running as root (PaaS host volume mount like Render/Fly/Railway),
# fix permissions of persistent data directory and drop privileges to hoptrace.
if [ "$(id -u)" = "0" ]; then
    mkdir -p /app/data
    chown -R hoptrace:hoptrace /app/data
    chmod 775 /app/data
    exec su -s /bin/sh hoptrace -c 'exec "$@"' -- "$@"
fi

exec "$@"
