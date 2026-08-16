"""FastAPI entrypoint.

Thin wiring only — no business logic here (CLAUDE.md). This module is the
composition root for the read API: it opens the connection pool, builds the
Postgres readers, injects them into the use cases, and mounts the routers.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import psycopg
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from psycopg import IsolationLevel
from psycopg_pool import ConnectionPool

from src.infrastructure.ingestion.job import start_scheduler
from src.infrastructure.llm.anthropic_interpreter import AnthropicQueryInterpreter
from src.infrastructure.llm.interpretation_cache import InMemoryInterpretationCache
from src.infrastructure.settings import get_cors_origins, get_settings
from src.interfaces.api import assistant, communes, establishments

logger = logging.getLogger(__name__)


def _configure_read_connection(connection: psycopg.Connection) -> None:
    """Make every pooled connection read-only and repeatable-read.

    REPEATABLE READ so that the several queries behind one response all see
    the same snapshot: under the default READ COMMITTED each statement takes a
    fresh one, and an ingestion committing mid-request could produce a total
    that disagrees with its own page, or a fact sheet half from before the
    load and half from after.

    Read-only because nothing serving an HTTP request has any business
    writing. It costs nothing and turns a whole class of mistake into an
    immediate error from Postgres rather than a silent modification.
    """
    connection.isolation_level = IsolationLevel.REPEATABLE_READ
    connection.read_only = True


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level)
    interpretation_cache = InMemoryInterpretationCache(
        max_entries=settings.assistant_cache_max_entries,
        ttl_seconds=settings.assistant_cache_ttl_seconds,
    )

    # One connection per request, borrowed by the router's dependencies and
    # shared by every reader serving that request — so a fact sheet cannot mix
    # an establishment read before an ingestion commit with indicator rows
    # read after it. See `interfaces/api/establishments.py`.
    pool = ConnectionPool(
        settings.database_url,
        min_size=1,
        max_size=10,
        open=True,
        configure=_configure_read_connection,
    )
    app.state.pool = pool
    app.state.interpretation_cache = interpretation_cache
    interpreter: AnthropicQueryInterpreter | None = None
    scheduler = None
    try:
        interpreter = AnthropicQueryInterpreter(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            base_url=settings.anthropic_base_url,
            timeout_seconds=settings.anthropic_timeout_seconds,
        )
        app.state.query_interpreter = interpreter
        scheduler = start_scheduler(settings)
        yield
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        if interpreter is not None:
            interpreter.close()
        pool.close()


app = FastAPI(
    title="Établissements en clair — API",
    description=(
        "Public-data explainer for French school establishments. "
        "This service describes official data; it does not rank or recommend."
    ),
    lifespan=lifespan,
)

# The frontend is served from a different origin than the API (Vite on :5173,
# API on :8000), so without this the browser refuses every call. Origins come
# from settings rather than the code: a deployment must name its own domain,
# and the Definition of Done (§5) forbids environment-specific values here.
#
# Only GET and POST are allowed, and no credentials: this API is read-only
# public data with no cookies or auth, so allowing more would widen the surface
# for nothing. The read-only pool already refuses writes at the database level.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(establishments.router)
app.include_router(communes.router)
app.include_router(assistant.router)
