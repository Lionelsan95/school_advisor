"""FastAPI entrypoint.

Thin wiring only — no business logic here (CLAUDE.md). Phase 1 exposes just a
health check; the read API arrives in Phase 2.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.infrastructure.ingestion.job import start_scheduler
from src.infrastructure.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    scheduler = start_scheduler(settings)
    try:
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)


app = FastAPI(
    title="Établissements en clair — API",
    description=(
        "Public-data explainer for French school establishments. "
        "This service describes official data; it does not rank or recommend."
    ),
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
