# HopTrace Unified Production Dockerfile (Single-Container PaaS)
# Stage 1: Build static frontend assets
FROM node:20.18.0-alpine AS frontend-builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm install --no-audit --no-fund

COPY frontend/ ./
RUN npm run build

# Stage 2: Python backend with bundled SPA assets
FROM python:3.11.10-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SQLITE_DB_PATH=/app/data/hoptrace.db \
    FRONTEND_DIST_DIR=/app/static

# Install gosu for secure privilege drop in entrypoint
RUN apt-get update && apt-get install -y --no-install-recommends gosu && rm -rf /var/lib/apt/lists/*

# Create non-root system user and group
RUN groupadd -g 10001 hoptrace && \
    useradd -u 10001 -g hoptrace -s /bin/bash -m hoptrace

# Install Python backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY backend/ /app/

# Copy compiled frontend from Stage 1 into /app/static
COPY --from=frontend-builder /build/dist /app/static

# Copy entrypoint script for handling volume permissions on PaaS
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Create persistent data directory and grant permissions to non-root user
RUN mkdir -p /app/data && \
    chown -R hoptrace:hoptrace /app /app/data

USER hoptrace

EXPOSE 8000

# Healthcheck using Python standard library (dynamic port support)
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os, sys; port = os.environ.get('PORT', '8000'); sys.exit(0 if urllib.request.urlopen(f'http://127.0.0.1:{port}/api/v1/health', timeout=5).getcode() == 200 else 1)"

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
