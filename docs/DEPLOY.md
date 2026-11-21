# HopTrace Production Deployment Guide

This document describes how to build, deploy, verify, and maintain HopTrace in production.

---

## 1. Production Architecture Overview

HopTrace is designed to be served under **one public HTTPS URL** with the React frontend and FastAPI backend hosted same-origin. This guarantees:
- The React frontend calls `/api/v1` same-origin with no CORS restrictions or preflight overhead.
- Live telemetry streams over WebSocket at `/ws/telemetry` on the same host and protocol (`wss://` in production).
- Persistent SQLite storage survives container rebuilds, restarts, and redeployments.
- Container healthchecks monitor system readiness at `/api/v1/health`.

Two deployment layouts are supported:

| Deployment Layout | Target Environments | Container Structure |
| :--- | :--- | :--- |
| **Layout A: Docker Compose** | Linux VPS, AWS EC2, DigitalOcean Droplets, Hetzner, Coolify | `hoptrace-frontend` (Nginx unprivileged reverse proxy) + `hoptrace-backend` (FastAPI) |
| **Layout B: Multi-Stage Root Dockerfile** | Single-container PaaS (Render, Railway, Fly.io, Google Cloud Run) | Single container with pre-built frontend static assets served directly by FastAPI |

---

## 2. Environment Variables & Secret Configuration

Copy `.env.example` to `.env` on your host or set these variables securely in your cloud provider's dashboard. **Never commit `.env` with real credentials to git.**

| Variable | Description | Default / Recommended |
| :--- | :--- | :--- |
| `DATA_MODE` | Telemetry mode: `demo` (simulated streams for evaluation) or `live` (edge agent data) | `demo` |
| `APP_VERSION` | API version string reported in healthchecks | `0.1.0` |
| `SQLITE_DB_PATH` | Path to persistent database file | `/app/data/hoptrace.db` |
| `CORS_ORIGINS` | Allowed browser origins for CORS (fallback for development / external clients) | `http://localhost,http://127.0.0.1` |
| `SEED_DEMO_SUBSCRIBERS` | Automatically seed demo subscriber records on first startup | `true` |
| `SEED_DEMO_INCIDENTS` | Automatically seed demo incident records on first startup | `true` |
| `TOPOLOGY_PROVIDER` | Network graph provider: `engine` (graph engine) or `simulated` | `engine` |
| `DEPENDENCY_ADAPTER` | Dependency mapping: `engine`, `simulated`, or `unavailable` | `engine` |
| `EXPLANATION_PROVIDER` | AI incident explanations: `unavailable` or `sarvam` | `unavailable` |
| `SARVAM_API_KEY` | Sarvam AI API key (required if `EXPLANATION_PROVIDER=sarvam`) | *(leave blank if unused)* |
| `NOTIFICATION_PROVIDER` | Outage alerts: `console` (demo logs), `twilio` (real SMS), or `unavailable` | `console` |
| `REAL_SEND_ALLOWLIST` | Comma-separated phone numbers permitted for real sends | *(leave blank if unused)* |
| `INGEST_API_KEY` | Secret token required in `X-API-Key` for telemetry ingestion | *(set in production)* |
| `AUTH_DISABLED` | Skip JWT auth checks (true for tests/local, false in hardened deployment) | `false` |
| `AUTH_SECRET` | Secret key for signing and verifying JWT tokens | *(generate random 32+ char string)* |
| `OPERATOR_PASSWORD` | Seeded password for operator login | *(set secure password)* |
| `VIEWER_PASSWORD` | Seeded password for read-only viewer login | *(set secure password)* |
| `EVALUATOR_PASSWORD` | Seeded password for evaluator login | *(set secure password)* |
| `NEO4J_URI` | Bolt connection URI for Neo4j graph engine | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | *(leave blank for in-memory fallback)* |

---

## 3. Persistent Storage & Healthcheck Verification

### 3.1 SQLite Persistence (`/app/data`)
The SQLite database stores subscribers, incidents, runs, and baselines. It must reside on a persistent volume:
* **Docker Compose**: Uses named volume `hoptrace_data` mounted to `/app/data`.
* **Single-Container PaaS (Render / Railway / Fly.io)**: Attach a persistent disk mounted to `/app/data`.

To backup or verify the SQLite database:
```bash
# Verify file exists on volume
docker compose exec backend ls -la /app/data/hoptrace.db

# Backup database
docker compose cp backend:/app/data/hoptrace.db ./hoptrace_backup.db
```

### 3.2 Healthcheck (`/api/v1/health`)
Both deployment layouts query `/api/v1/health` using the Python standard library `urllib.request` (no external curl dependencies required).
```bash
# Verify health endpoint from host
curl -s http://localhost:80/api/v1/health
# Response: {"status":"ok","version":"0.1.0","database":"ok"}
```

---

## 4. Deployment Instructions

### Layout A: Deploying on a Linux VPS / Cloud VM (Docker Compose)
Target hosts: AWS EC2, DigitalOcean Droplet, Hetzner, Linode, Coolify.

#### Step 1: Provision Host
Ensure Docker (v24+) and Docker Compose (v2+) are installed:
```bash
sudo apt-get update && sudo apt-get install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

#### Step 2: Clone Repository & Configure Environment
```bash
git clone https://github.com/<org>/HopTrace.git /opt/hoptrace
cd /opt/hoptrace
cp .env.example .env
# Edit .env with your production secrets (e.g., AUTH_SECRET, passwords, API keys)
nano .env
```

#### Step 3: Build & Launch Containers
```bash
docker compose up -d --build
```

#### Step 4: Verify Running Services
```bash
docker compose ps
# Expected output:
# hoptrace-backend    running (healthy)
# hoptrace-frontend   running (healthy)   0.0.0.0:80->8080/tcp
```

#### Step 5: Configure Reverse Proxy / TLS (HTTPS)
Use Caddy or Nginx on the host to terminate HTTPS with automated Let's Encrypt certificates:
```caddy
# /etc/caddy/Caddyfile
hoptrace.yourdomain.com {
    reverse_proxy localhost:80
}
```
Reload Caddy: `sudo systemctl reload caddy`.

---

### Layout B: Deploying on Single-Container PaaS (Render / Railway / Fly.io)

Target hosts: Render Web Service, Railway, Fly.io, Google Cloud Run.

#### Option 1: Render
1. Go to **Dashboard** -> **New** -> **Web Service**.
2. Connect your Git repository.
3. Select **Docker** as the Environment.
4. Set Dockerfile Path: `./Dockerfile` (root multi-stage Dockerfile).
5. Add **Persistent Disk**:
   - Name: `hoptrace-data`
   - Mount Path: `/app/data`
   - Size: 1 GB (or as required)
6. Under **Environment Variables**, add the variables listed in Section 2 (e.g. `DATA_MODE=demo`, `SQLITE_DB_PATH=/app/data/hoptrace.db`, `AUTH_SECRET=...`).
7. Set Health Check Path: `/api/v1/health`.
8. Click **Create Web Service**. Render automatically builds and launches the container under HTTPS.

#### Option 2: Railway
1. Click **New Project** -> **Deploy from GitHub repo**.
2. Railway detects the root `Dockerfile`.
3. In service settings:
   - Add a **Volume** mounted at `/app/data`.
   - In **Variables**, enter environment variables from `.env.example`.
4. Click **Deploy**.

#### Option 3: Fly.io
1. Install `flyctl` and run `fly launch`.
2. Create persistent volume:
   ```bash
   fly volumes create hoptrace_data --size 1
   ```
3. Configure `fly.toml`:
   ```toml
   [mounts]
     source = "hoptrace_data"
     destination = "/app/data"

   [[services.http_checks]]
     interval = 10000
     grace_period = "10s"
     method = "get"
     path = "/api/v1/health"
     protocol = "http"
     timeout = 2000
   ```
4. Deploy: `fly deploy`.

---

## 5. Redeploying on Merge

### PaaS (Render, Railway, Fly.io)
* **Native Auto-Deploy**: Both Render and Railway connect directly to GitHub. When a pull request is merged into `main`, the host automatically triggers a build and zero-downtime rolling deployment.
* Ensure **Auto-Deploy** is set to **Yes** in service settings.

### Linux VPS / Self-Hosted Docker Compose
If hosting on a VPS, use a lightweight CD webhook or GitHub Actions runner:

#### Simple Auto-Redeploy Script (`/opt/hoptrace/deploy.sh`):
```bash
#!/usr/bin/env bash
set -e
cd /opt/hoptrace
git fetch origin main
git reset --hard origin/main
docker compose up -d --build
docker image prune -f
echo "[HopTrace] Successfully deployed commit $(git rev-parse --short HEAD)"
```

#### GitHub Actions Workflow (`.github/workflows/deploy.yml`):
```yaml
name: Production CD
on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Remote Deployment via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USER }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: /opt/hoptrace/deploy.sh
```

---

## 6. Security & Container Hardening (ArgosX Baseline)

The container configuration adheres to security best practices:
1. **Non-Root Execution**:
   - Backend runs as `hoptrace` (UID/GID 10001).
   - Frontend runs as `nginx` (unprivileged UID 101, listening on non-privileged port 8080).
2. **Pinned Base Images**:
   - `python:3.11.10-slim`
   - `node:20.18.0-alpine`
   - `nginx:1.27.2-alpine`
3. **No Embedded Secrets or Phone Numbers**:
   - `.dockerignore` excludes `.env*`, `.git`, databases, and build caches from the build context.
   - Credentials are injected at runtime via environment variables only.
4. **Isolated Same-Origin Traffic**:
   - Backend port 8000 is internal and not exposed to the public internet in the Docker Compose layout.
   - Frontend proxies `/api/` and `/ws/` internally to `backend:8000`.
