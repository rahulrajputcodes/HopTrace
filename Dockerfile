# HopTrace Unified Production Dockerfile (Single-Container PaaS)
# Stage 1: Build static frontend assets
FROM node:20.18.0-alpine AS frontend-builder

WORKDIR /build

COPY frontend/package*.json ./
RUN npm ci

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

# Create persistent data directory and grant permissions to non-root user
RUN mkdir -p /app/data && \
    chown -R hoptrace:hoptrace /app /app/data

USER hoptrace

EXPOSE 8000

# Healthcheck using Python standard library
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5).getcode() == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
