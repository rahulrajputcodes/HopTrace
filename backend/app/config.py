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

    # Neo4j connection (used by the graph engine when configured)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""

    # --- SQLite Database ---
    sqlite_db_path: str = "hoptrace.db"
    seed_demo_subscribers: bool = True
    seed_demo_incidents: bool = True


settings = Settings()
