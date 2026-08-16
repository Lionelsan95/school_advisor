"""Read endpoints for establishments (API-1, API-2).

Thin wiring, per CLAUDE.md: parse and validate query parameters, call a use
case, serialize. The only rule enforced *here* rather than deeper down is the
refusal of a results-based sort — it has to be caught at the edge, because the
point is to answer the caller rather than silently drop what they asked for.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query, Request

from src.application.errors import MissingSourceReferenceError
from src.application.get_establishment_fact_sheet import GetEstablishmentFactSheet
from src.application.get_establishment_history import GetEstablishmentHistory
from src.application.ports import SearchCriteria
from src.application.search_establishments import (
    DEFAULT_LIMIT,
    MAX_LIMIT,
    InvalidSearchError,
    MissingSearchSourceError,
    SearchEstablishments,
)
from src.domain.enums import EstablishmentType, Filiere, Sector
from src.domain.uai import InvalidUaiError, parse_uai
from src.infrastructure.persistence.queries import (
    PostgresEstablishmentReader,
    PostgresIndicatorReader,
    PostgresSourceReferenceReader,
)
from src.interfaces.api.schemas import (
    FactSheetOut,
    HistoryOut,
    SearchResponseOut,
)

router = APIRouter(prefix="/establishments", tags=["establishments"])
logger = logging.getLogger(__name__)

# Any of these in a query string is a request for a ranked list. The contract
# says such a request gets a 400 rather than being ignored, so that a consumer
# building on this API learns the ordering is not negotiable instead of
# quietly receiving a list they may present as a ranking.
_SORT_PARAMETERS = frozenset(
    {"sort", "sort_by", "sortby", "order", "order_by", "orderby", "tri"}
)

_NO_RANKING_MESSAGE = (
    "Ce service ne classe pas les établissements. Le paramètre {name!r} n'est "
    "pas accepté : l'ordre repose uniquement sur la correspondance factuelle "
    "avec la recherche, la proximité lorsqu'une position est fournie, puis "
    "l'ordre alphabétique."
)

_MISSING_PROVENANCE_MESSAGE = (
    "Une référence de source nécessaire à cette fiche est indisponible. "
    "La fiche n'est pas publiée afin de ne pas présenter de donnée sans origine."
)

_MISSING_SEARCH_SOURCE_MESSAGE = (
    "Une référence de source nécessaire à cette recherche est indisponible. "
    "Les résultats ne sont pas publiés afin de ne pas présenter de données "
    "sans origine."
)


def _reject_sort_parameters(request: Request) -> None:
    for name in request.query_params:
        if name.lower() in _SORT_PARAMETERS:
            raise HTTPException(
                status_code=400, detail=_NO_RANKING_MESSAGE.format(name=name)
            )


def get_connection(request: Request) -> Iterator[psycopg.Connection]:
    """Borrow one pooled connection for the whole request.

    Every reader serving this request shares it, and the surrounding
    transaction is REPEATABLE READ (configured on the pool), so a fact sheet
    assembled from three queries cannot straddle an ingestion commit and
    report an establishment and its indicators from two different states of
    the world.
    """
    with request.app.state.pool.connection() as connection, connection.transaction():
        yield connection


def get_fact_sheet_use_case(
    connection: Annotated[psycopg.Connection, Depends(get_connection)],
) -> GetEstablishmentFactSheet:
    return GetEstablishmentFactSheet(
        establishments=PostgresEstablishmentReader(connection),
        indicators=PostgresIndicatorReader(connection),
        sources=PostgresSourceReferenceReader(connection),
    )


def get_history_use_case(
    connection: Annotated[psycopg.Connection, Depends(get_connection)],
) -> GetEstablishmentHistory:
    return GetEstablishmentHistory(
        establishments=PostgresEstablishmentReader(connection),
        indicators=PostgresIndicatorReader(connection),
        sources=PostgresSourceReferenceReader(connection),
    )


def get_search_use_case(
    connection: Annotated[psycopg.Connection, Depends(get_connection)],
) -> SearchEstablishments:
    return SearchEstablishments(
        establishments=PostgresEstablishmentReader(connection),
        sources=PostgresSourceReferenceReader(connection),
    )


@router.get("/search", response_model=SearchResponseOut)
def search_establishments(
    request: Request,
    use_case: Annotated[SearchEstablishments, Depends(get_search_use_case)],
    type: Annotated[EstablishmentType | None, Query()] = None,
    secteur: Annotated[Sector | None, Query()] = None,
    filiere: Annotated[Filiere | None, Query()] = None,
    q: Annotated[str | None, Query(min_length=2, max_length=120)] = None,
    code_commune: Annotated[str | None, Query(min_length=1, max_length=10)] = None,
    code_postal: Annotated[str | None, Query(min_length=1, max_length=10)] = None,
    lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    lng: Annotated[float | None, Query(ge=-180, le=180)] = None,
    rayon_km: Annotated[float | None, Query(gt=0, le=100)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SearchResponseOut:
    _reject_sort_parameters(request)
    criteria = SearchCriteria(
        text_query=q.strip() if q is not None else None,
        commune_code=(
            code_commune.strip().upper() if code_commune is not None else None
        ),
        postal_code=(code_postal.strip() if code_postal is not None else None),
        establishment_type=type,
        sector=secteur,
        filiere=filiere,
        latitude=lat,
        longitude=lng,
        radius_km=rayon_km,
        limit=limit,
        offset=offset,
    )
    try:
        results = use_case.run(criteria)
    except InvalidSearchError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except MissingSearchSourceError as error:
        logger.error("Establishment search withheld because provenance is missing")
        raise HTTPException(
            status_code=503, detail=_MISSING_SEARCH_SOURCE_MESSAGE
        ) from error
    return SearchResponseOut.of(results, criteria)


@router.get("/{uai}", response_model=FactSheetOut)
def get_establishment(
    uai: str,
    use_case: Annotated[GetEstablishmentFactSheet, Depends(get_fact_sheet_use_case)],
) -> FactSheetOut:
    # A malformed UAI is a 400: the client sent something that cannot identify
    # an establishment. A well-formed UAI that is simply absent is a 404. The
    # distinction matters — "we have no record of this" and "that is not an
    # identifier" are different answers.
    try:
        normalised = parse_uai(uai)
    except InvalidUaiError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        sheet = use_case.run(normalised)
    except MissingSourceReferenceError as error:
        logger.error(
            "Fact sheet withheld because source provenance is missing",
            extra={
                "dataset_id": error.dataset_id,
                "uai": error.uai,
                "year": error.year,
            },
        )
        raise HTTPException(
            status_code=503, detail=_MISSING_PROVENANCE_MESSAGE
        ) from error
    if sheet is None:
        raise HTTPException(
            status_code=404, detail=f"Aucun établissement connu pour l'UAI {normalised}"
        )
    return FactSheetOut.of(sheet)


@router.get("/{uai}/history", response_model=HistoryOut)
def get_establishment_history(
    uai: str,
    use_case: Annotated[GetEstablishmentHistory, Depends(get_history_use_case)],
) -> HistoryOut:
    """Every published year for one establishment, oldest first (F5).

    Same error semantics as the fact sheet, deliberately: a malformed UAI is a
    400, an unknown one a 404, and missing provenance withholds the answer with
    a 503 rather than showing figures whose origin cannot be stated.
    """
    try:
        normalised = parse_uai(uai)
    except InvalidUaiError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    try:
        history = use_case.run(normalised)
    except MissingSourceReferenceError as error:
        logger.error(
            "History withheld because source provenance is missing",
            extra={
                "dataset_id": error.dataset_id,
                "uai": error.uai,
                "year": error.year,
            },
        )
        raise HTTPException(
            status_code=503, detail=_MISSING_PROVENANCE_MESSAGE
        ) from error
    if history is None:
        raise HTTPException(
            status_code=404, detail=f"Aucun établissement connu pour l'UAI {normalised}"
        )
    return HistoryOut.of(history)
