# HopTrace Backend Dockerfile
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . /app/

# Sensible default environment variables for judges
ENV TOPOLOGY_PROVIDER=engine \
    DEPENDENCY_ADAPTER=engine \
    EXPLANATION_PROVIDER=simulated \
    NOTIFICATION_PROVIDER=console \
    SQLITE_DB_PATH=/app/data/hoptrace.db \
    INGEST_RETENTION_RUNS=1000 \
    CORS_ORIGINS="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173,http://frontend:5173"

# Create directory for SQLite persistence
RUN mkdir -p /app/data

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
