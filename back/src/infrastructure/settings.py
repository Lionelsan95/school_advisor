"""Configuration, read from the environment only.

No value here may be hardcoded to an environment-specific default beyond what
is safe for local development — see the Definition of Done, section 5.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # No default. A missing DATABASE_URL must fail loudly at startup rather
    # than silently connecting to whatever happens to be on localhost — the
    # same rule alembic/env.py enforces for migrations.
    database_url: str
    ods_base_url: str = "https://data.education.gouv.fr/api/explore/v2.1"
    geo_api_base_url: str = "https://geo.api.gouv.fr"

    # Optional bounded interpretation layer. Structured deterministic endpoints
    # remain available when no key is configured or the provider is down.
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    anthropic_base_url: str = "https://api.anthropic.com"
    anthropic_timeout_seconds: float = 15.0
    assistant_cache_max_entries: int = 256
    assistant_cache_ttl_seconds: float = 900.0

    # Ingestion schedule. Sources refresh annually (indicators) and weekly
    # (directory), so a daily run is already generous; there is no case for
    # anything more frequent.
    ingestion_enabled: bool = False
    ingestion_hour_utc: int = 3

    log_level: str = "INFO"
    # "json" in production so lines are queryable; "text" locally so they are
    # readable. A format is a deployment concern, not a property of the code.
    log_format: str = "text"

    # Where an ingestion failure is announced (OPS-3). Optional: without it the
    # CRITICAL log and the `ingestion_run` row remain, so a deployment with no
    # webhook is degraded, not broken.
    alert_webhook_url: str | None = None


class CorsSettings(BaseSettings):
    """CORS configuration, deliberately separate from `Settings`.

    CORS middleware has to be installed when the app object is constructed, at
    import time — but `Settings` requires `DATABASE_URL`, and importing the app
    module must not require a database to be configured. Tests import it to
    check routing and headers, and a missing database should fail when the
    application tries to use one, not when Python reads the file.

    Same sources as `Settings` (environment, then `.env`), so it is configured
    the same way despite being a separate class.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # The Vite dev server and nothing else. A deployment serving the frontend
    # from a real domain must name it explicitly rather than inherit a
    # permissive default, and never "*": these responses are public data today,
    # but a wildcard would be silently inherited by anything added later.
    cors_allowed_origins: str = "http://localhost:5173"


def get_cors_origins() -> list[str]:
    """The configured origins, split into the list Starlette expects.

    Blank entries are dropped so a trailing comma in an env file cannot become
    an empty origin — which matches nothing and is tedious to diagnose from a
    browser console.
    """
    raw = CorsSettings().cors_allowed_origins
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_settings() -> Settings:
    # pydantic-settings fills every field from the environment, so the
    # required `database_url` is supplied at runtime even though mypy cannot
    # see a matching argument here. A missing value raises ValidationError at
    # startup, which is exactly the loud failure we want.
    return Settings()  # type: ignore[call-arg]
