"""Official commune lookup endpoint for deterministic locality resolution."""

from __future__ import annotations

import logging
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from src.application.search_communes import (
    DEFAULT_COMMUNE_LIMIT,
    MAX_COMMUNE_LIMIT,
    InvalidCommuneSearchError,
    MissingCommuneSourceError,
    SearchCommunes,
)
from src.infrastructure.persistence.queries import (
    PostgresCommuneReader,
    PostgresSourceReferenceReader,
)
from src.interfaces.api.establishments import get_connection
from src.interfaces.api.schemas import CommuneSearchResponseOut

router = APIRouter(prefix="/communes", tags=["communes"])
logger = logging.getLogger(__name__)

_MISSING_COMMUNE_SOURCE_MESSAGE = (
    "Une référence de source nécessaire à cette recherche est indisponible. "
    "Les résultats ne sont pas publiés afin de ne pas présenter de données "
    "sans origine."
)


def get_commune_search_use_case(
    connection: Annotated[psycopg.Connection, Depends(get_connection)],
) -> SearchCommunes:
    return SearchCommunes(
        communes=PostgresCommuneReader(connection),
        sources=PostgresSourceReferenceReader(connection),
    )


@router.get("/search", response_model=CommuneSearchResponseOut)
def search_communes(
    use_case: Annotated[SearchCommunes, Depends(get_commune_search_use_case)],
    q: Annotated[str, Query(min_length=2, max_length=120)],
    limit: Annotated[int, Query(ge=1, le=MAX_COMMUNE_LIMIT)] = DEFAULT_COMMUNE_LIMIT,
) -> CommuneSearchResponseOut:
    try:
        results = use_case.run(q, limit)
    except InvalidCommuneSearchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except MissingCommuneSourceError as error:
        logger.error("Commune search withheld because provenance is missing")
        raise HTTPException(
            status_code=503, detail=_MISSING_COMMUNE_SOURCE_MESSAGE
        ) from error
    return CommuneSearchResponseOut.of(results)
