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


def get_settings() -> Settings:
    # pydantic-settings fills every field from the environment, so the
    # required `database_url` is supplied at runtime even though mypy cannot
    # see a matching argument here. A missing value raises ValidationError at
    # startup, which is exactly the loud failure we want.
    return Settings()  # type: ignore[call-arg]
