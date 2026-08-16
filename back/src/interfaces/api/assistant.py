"""Bounded, stateless natural-language search endpoint."""

from __future__ import annotations

from typing import Annotated

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Request

from src.application.assistant_search import (
    AssistantSearch,
    AssistantSearchClarification,
    AssistantSearchSuccess,
    InvalidAssistantQueryError,
)
from src.application.interpret_search import (
    InterpretationCache,
    QueryInterpreter,
    SourceBackedInterpretationVersion,
)
from src.application.search_communes import MissingCommuneSourceError, SearchCommunes
from src.application.search_establishments import (
    MissingSearchSourceError,
    SearchEstablishments,
)
from src.domain.content_version import editorial_content_version
from src.infrastructure.persistence.queries import (
    PostgresCommuneReader,
    PostgresEstablishmentReader,
    PostgresSourceReferenceReader,
)
from src.interfaces.api.establishments import get_connection
from src.interfaces.api.schemas import (
    AssistantSearchClarificationOut,
    AssistantSearchIn,
    AssistantSearchSuccessOut,
    AssistantSearchUnavailableOut,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])

_MISSING_ASSISTANT_SOURCE_MESSAGE = (
    "Une référence de source nécessaire à cette recherche est indisponible. "
    "Les résultats ne sont pas publiés afin de ne pas présenter de données "
    "sans origine."
)


def get_interpreter(request: Request) -> QueryInterpreter:
    interpreter: QueryInterpreter = request.app.state.query_interpreter
    return interpreter


def get_interpretation_cache(request: Request) -> InterpretationCache:
    cache: InterpretationCache = request.app.state.interpretation_cache
    return cache


def get_assistant_search_use_case(
    connection: Annotated[psycopg.Connection, Depends(get_connection)],
    interpreter: Annotated[QueryInterpreter, Depends(get_interpreter)],
    interpretation_cache: Annotated[
        InterpretationCache, Depends(get_interpretation_cache)
    ],
) -> AssistantSearch:
    sources = PostgresSourceReferenceReader(connection)
    return AssistantSearch(
        interpreter=interpreter,
        communes=SearchCommunes(
            communes=PostgresCommuneReader(connection), sources=sources
        ),
        establishments=SearchEstablishments(
            establishments=PostgresEstablishmentReader(connection), sources=sources
        ),
        interpretation_cache=interpretation_cache,
        version_provider=SourceBackedInterpretationVersion(
            sources=sources,
            content_version=editorial_content_version(),
        ),
    )


AssistantSearchOut = (
    AssistantSearchSuccessOut
    | AssistantSearchClarificationOut
    | AssistantSearchUnavailableOut
)


@router.post("/search", response_model=AssistantSearchOut)
def assistant_search(
    payload: AssistantSearchIn,
    use_case: Annotated[AssistantSearch, Depends(get_assistant_search_use_case)],
) -> AssistantSearchOut:
    try:
        outcome = use_case.run(payload.requete)
    except InvalidAssistantQueryError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except (MissingCommuneSourceError, MissingSearchSourceError) as error:
        raise HTTPException(
            status_code=503, detail=_MISSING_ASSISTANT_SOURCE_MESSAGE
        ) from error
    if isinstance(outcome, AssistantSearchSuccess):
        return AssistantSearchSuccessOut.of(outcome)
    if isinstance(outcome, AssistantSearchClarification):
        return AssistantSearchClarificationOut.of(outcome)
    return AssistantSearchUnavailableOut.of(outcome)
