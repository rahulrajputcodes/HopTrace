"""
Application configuration.

Settings are read from environment variables (and from a .env file when
python-dotenv is present).  Defaults are safe for local development.
Never put real credentials here; use a .env file that is git-ignored.
"""
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- API ---
    app_version: str = "0.1.0"

    # --- CORS ---
    # Comma-separated list of allowed origins for CORS.
    # Default: only the local Vite dev server used by Member 3 (frontend).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # --- Topology provider ---
    # "simulated"  – use the built-in SimulatedTopologyProvider (no Neo4j needed)
    # "engine"     – use the EngineTopologyProvider (HopTrace graph engine)
    topology_provider: str = "engine"

    # --- Dependency analysis adapter ---
    # "unavailable" – default honest behavior when engine is not connected (returns 503)
    # "simulated"   – simulated dependency mapping for demos/testbed
    # "engine"      – engine dependency adapter (when implemented)
    dependency_adapter: str = "engine"

    # --- Explanation provider ---
    # "unavailable" – default honest behavior when no explanation provider is connected (returns 503)
    # "sarvam"      – Sarvam AI chat-completions endpoint (requires SARVAM_API_KEY)
    explanation_provider: str = "unavailable"

    # --- Sarvam AI (used when EXPLANATION_PROVIDER=sarvam) ---
    # Set SARVAM_API_KEY in your local .env file (never commit a real key).
    sarvam_api_key: str = ""
    sarvam_model: str = "sarvam-105b"
    sarvam_timeout_seconds: float = 30.0

    # --- Telemetry Ingestion ---
    # Optional API key for POST /api/v1/measurements/ingest (header X-API-Key)
    ingest_api_key: str = ""

    # --- Run Telemetry Retention (SQLite) ---
    # Maximum number of past test runs and their measurements to retain in SQLite
    runs_retention_limit: int = 1000

    # --- Business Impact & SLA Credits ---
    # Fraction of monthly plan price credited per hour of outage (e.g. 0.02 = 2% per hour)
    sla_credit_rate_per_hour: float = 0.02

    # --- Notification Provider ---
    # "unavailable" – default honest behavior (returns 503)
    # "console"     – demo provider logging notifications
    # "twilio"      – Twilio SMS / WhatsApp delivery
    notification_provider: str = "unavailable"

    # --- Twilio (used when NOTIFICATION_PROVIDER=twilio) ---
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    twilio_whatsapp_from_number: str = ""

    @field_validator("sarvam_model", mode="before")
    @classmethod
    def _validate_sarvam_model(cls, v: object) -> str:
        """Reject blank or whitespace-only model identifiers; strip surrounding whitespace."""
        if not isinstance(v, str) or not v.strip():
            raise ValueError(
                "SARVAM_MODEL must be a non-blank string (e.g. 'sarvam-105b')."
            )
        return v.strip()

    @field_validator("sarvam_timeout_seconds", mode="before")
    @classmethod
    def _validate_sarvam_timeout(cls, v: object) -> float:
        """Reject non-positive timeout values."""
        try:
            value = float(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(
                f"SARVAM_TIMEOUT_SECONDS must be a positive number; got {v!r}."
            )
        if value <= 0:
            raise ValueError(
                f"SARVAM_TIMEOUT_SECONDS must be greater than zero; got {value!r}."
            )
        return value

    @field_validator("runs_retention_limit", mode="before")
    @classmethod
    def _validate_runs_retention_limit(cls, v: object) -> int:
        """Reject non-positive retention limit values."""
        try:
            value = int(v)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValueError(
                f"RUNS_RETENTION_LIMIT must be an integer; got {v!r}."
            )
        if value <= 0:
            raise ValueError("RUNS_RETENTION_LIMIT must be greater than zero.")
        return value

    @field_validator("sla_credit_rate_per_hour", mode="before")
    @classmethod
    def _validate_sla_credit_rate(cls, v: object) -> float:
        """Ensure sla_credit_rate_per_hour is non-negative."""
        try:
            val = float(v)
            if val < 0.0:
                raise ValueError
            return val
        except (TypeError, ValueError):
            raise ValueError(
                f"SLA_CREDIT_RATE_PER_HOUR must be a non-negative number; got {v!r}."
            )

    # Neo4j connection (used by the graph engine when configured)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # --- SQLite Database ---
    sqlite_db_path: str = "hoptrace.db"
    seed_demo_subscribers: bool = True
    seed_demo_incidents: bool = True


settings = Settings()
