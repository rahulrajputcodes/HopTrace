# HopTrace Backend Production Dockerfile
FROM python:3.11.10-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    SQLITE_DB_PATH=/app/data/hoptrace.db

# Create non-root system user and group
RUN groupadd -g 10001 hoptrace && \
    useradd -u 10001 -g hoptrace -s /bin/bash -m hoptrace

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . /app/

# Create directory for SQLite persistence and grant ownership to non-root user
RUN mkdir -p /app/data && \
    chown -R hoptrace:hoptrace /app /app/data

USER hoptrace

EXPOSE 8000

# Healthcheck using Python standard library (no curl needed in slim image)
HEALTHCHECK --interval=10s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5).getcode() == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
