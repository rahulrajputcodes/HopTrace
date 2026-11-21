"""
Tests for deployment assets: .env.example, docker-compose.yml, Dockerfiles.
Validates M2-5 deploy contract.
"""
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_env_example_has_names_only():
    """Verify .env.example documents all required variables with names only (no values/secrets)."""
    env_example = REPO_ROOT / ".env.example"
    assert env_example.is_file(), ".env.example must exist"

    required_vars = [
        "DATA_MODE",
        "AUTH_DISABLED",
        "AUTH_SECRET",
        "OPERATOR_PASSWORD",
        "VIEWER_PASSWORD",
        "EVALUATOR_PASSWORD",
        "INGEST_API_KEY",
        "NOTIFICATION_PROVIDER",
        "EXPLANATION_PROVIDER",
        "SARVAM_API_KEY",
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "SQLITE_DB_PATH",
        "CORS_ORIGINS",
    ]

    var_definitions = {}
    for line in env_example.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, val = line.split("=", 1)
            var_definitions[key.strip()] = val.strip()

    for var in required_vars:
        assert var in var_definitions, f"Missing required env var in .env.example: {var}"

    for key, val in var_definitions.items():
        assert val == "", f".env.example must have names only without values; found {key}={val}"


def test_docker_compose_volume_and_healthcheck():
    """Verify docker-compose.yml configures SQLite persistent volume and /api/v1/health healthcheck."""
    compose_file = REPO_ROOT / "docker-compose.yml"
    assert compose_file.is_file(), "docker-compose.yml must exist"

    content = compose_file.read_text(encoding="utf-8")
    assert "hoptrace_data:" in content, "docker-compose.yml must define persistent volume hoptrace_data"
    assert "/app/data" in content, "docker-compose.yml must mount volume to /app/data"
    assert "/api/v1/health" in content, "backend healthcheck must query /api/v1/health"
    assert "service_healthy" in content, "frontend must wait for backend healthcheck"


def test_dockerfiles_exist_and_non_root():
    """Verify Dockerfiles exist for both layouts and enforce non-root user."""
    root_dockerfile = REPO_ROOT / "Dockerfile"
    backend_dockerfile = REPO_ROOT / "backend" / "Dockerfile"
    frontend_dockerfile = REPO_ROOT / "frontend" / "Dockerfile"

    assert root_dockerfile.is_file(), "Root multi-stage Dockerfile must exist for PaaS"
    assert backend_dockerfile.is_file(), "Backend Dockerfile must exist for compose"
    assert frontend_dockerfile.is_file(), "Frontend Dockerfile must exist for compose"

    assert "USER hoptrace" in root_dockerfile.read_text(encoding="utf-8")
    assert "USER hoptrace" in backend_dockerfile.read_text(encoding="utf-8")
    assert "USER nginx" in frontend_dockerfile.read_text(encoding="utf-8")


def test_api_healthcheck_endpoint():
    """Verify backend health endpoint returns status ok and version."""
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("status") == "ok"
    assert "version" in data

