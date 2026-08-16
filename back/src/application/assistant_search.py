"""Bounded search orchestration: interpret criteria, then call factual ports."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256

from src.application.interpret_search import (
    InterpretationCache,
    InterpretationVersionProvider,
    InterpretedSearch,
    InterpreterUnavailableError,
    LocationMode,
    QueryInterpreter,
)
from src.application.ports import SearchCriteria
from src.application.search_communes import CommuneSearchResults, SearchCommunes
from src.application.search_establishments import (
    EstablishmentSearchResponse,
    SearchEstablishments,
)

DEFAULT_RADIUS_KM = 10.0
MAX_QUERY_LENGTH = 500

_UAI_RE = re.compile(r"^[0-9]{7}[A-Za-z]$")
_POSTAL_RE = re.compile(r"^[0-9]{5}$")
_COMPLEX_MARKERS = (
    " autour ",
    " pres de ",
    " proche de ",
    " proches ",
    " near ",
    " within ",
    " public ",
    " prive ",
    " private ",
    " generale ",
    " technologique ",
    " professionnelle ",
)
_SUBJECTIVE_MARKERS = (
    " meilleur",
    " meilleure",
    " best ",
    " top ",
    " recommande",
    " recommandation",
    " recommend ",
    " recommendation",
    " choisir",
    " should i choose",
    " better ",
    " mieux classe",
    " plus performant",
    " higher performing",
    " classe ",
    " classer ",
    " classement ",
    " ranking ",
    " pire ",
    " worst ",
    " eviter ",
    " avoid ",
    " conseille",
    " ideal ",
    " highest ",
    " lowest ",
    " plus eleve",
    " plus faible",
    " taux de reussite",
    " valeur ajoutee",
    " performance",
)
_FILTERED_PLACE_RE = re.compile(
    r"\b(colleges?|lycees?|ecoles?|erea)\b.*\b(a|dans|autour|pres|proches?)\b"
)
_PLURAL_PLACE_RE = re.compile(r"\b(colleges|lycees|ecoles)\b.*\b(de|of)\b")

_ESTABLISHMENT_WORD = r"(?:colleges?|lycees?|ecoles?|erea|etablissements?)"
_TYPE_SUPPORT_PATTERNS = {
    "college": (r"\bcolleges?\b",),
    "lycee": (r"\blycees?\b",),
    "ecole": (r"\becoles?\b",),
    "erea": (r"\berea\b",),
    "autre": (r"\b(?:autres?|other)\s+etablissements?\b",),
}
_NAMED_ESTABLISHMENT_START_PATTERNS = tuple(
    patterns[0] for patterns in _TYPE_SUPPORT_PATTERNS.values()
)
_SECTOR_SUPPORT_PATTERNS = {
    "public": (
        rf"\b{_ESTABLISHMENT_WORD}\s+(?:publics?|publiques?)\b",
        rf"\b(?:publics?|publiques?)\s+{_ESTABLISHMENT_WORD}\b",
        r"\b(?:secteur|statut)\s+(?:publics?|publiques?)\b",
    ),
    "prive": (
        rf"\b{_ESTABLISHMENT_WORD}\s+(?:prive(?:s|e|es)?|private)\b",
        rf"\b(?:prive(?:s|e|es)?|private)\s+{_ESTABLISHMENT_WORD}\b",
        r"\b(?:secteur|statut)\s+(?:prive(?:s|e|es)?|private)\b",
    ),
}
_FILIERE_SUPPORT_PATTERNS = {
    "generale": (
        r"\b(?:filiere|voie)(?:\s+[a-z0-9'-]+){0,2}\s+generales?\b",
        r"\b(?:bacs?|baccalaureats?)(?:\s+[a-z0-9'-]+){0,2}\s+general(?:e|es|aux)?\b",
        r"\blycees?\s+generaux\b",
    ),
    "technologique": (
        r"\b(?:filiere|voie)(?:\s+[a-z0-9'-]+){0,2}\s+technologique?s?\b",
        r"\b(?:lycees?|bacs?|baccalaureats?)(?:\s+[a-z0-9'-]+){0,2}\s+technologique?s?\b",
    ),
    "professionnelle": (
        r"\b(?:filiere|voie)(?:\s+[a-z0-9'-]+){0,2}\s+(?:professionnelle?s?|vocational)\b",
        r"\b(?:lycees?|bacs?|baccalaureats?)(?:\s+[a-z0-9'-]+){0,2}\s+(?:professionnelle?s?|vocational)\b",
    ),
}
_UNSAFE_TEXT_QUERY_WORDS = {
    "best",
    "meilleur",
    "meilleure",
    "pire",
    "worst",
    "top",
    "recommande",
    "recommandation",
    "conseille",
    "choisir",
    "ideal",
    "performance",
    "performant",
    "resultat",
    "resultats",
    "highest",
    "lowest",
    "avoid",
    "eviter",
    "classement",
    "ranking",
}


class InvalidAssistantQueryError(ValueError):
    pass


class ClarificationKind(StrEnum):
    LOCATION_REQUIRED = "lieu_requis"
    LOCATION_UNKNOWN = "lieu_inconnu"
    LOCATION_AMBIGUOUS = "lieu_ambigu"
    LOCATION_HAS_NO_CENTRE = "centre_indisponible"


@dataclass(frozen=True, slots=True)
class AssistantSearchSuccess:
    search: EstablishmentSearchResponse
    criteria: SearchCriteria
    subjective_request_reframed: bool
    resolved_place: CommuneSearchResults | None = None


@dataclass(frozen=True, slots=True)
class AssistantSearchClarification:
    kind: ClarificationKind
    options: CommuneSearchResults | None = None
    subjective_request_reframed: bool = False


@dataclass(frozen=True, slots=True)
class AssistantSearchUnavailable:
    """Only the optional interpretation path is unavailable."""


AssistantSearchOutcome = (
    AssistantSearchSuccess | AssistantSearchClarification | AssistantSearchUnavailable
)


def _normalized(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(ascii_text.lower().split())


def _is_subjective(query: str) -> bool:
    padded = f" {_normalized(query)} "
    return any(marker in padded for marker in _SUBJECTIVE_MARKERS)


def _matches_any(value: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, value) is not None for pattern in patterns)


def _supports_text_query(text_query: str, normalized_query: str) -> bool:
    normalized_text = _normalized(text_query)
    words = normalized_text.split()
    if _is_subjective(text_query) or any(
        word in _UNSAFE_TEXT_QUERY_WORDS for word in words
    ):
        return False
    # Simple names and UAIs bypass the provider. On the interpreted path, only
    # accept an explicit establishment label plus a distinguishing name; this
    # deliberately rejects generic or evaluative fragments that merely happen
    # to occur in the request.
    return (
        len(words) >= 2
        and _matches_any(words[0], _NAMED_ESTABLISHMENT_START_PATTERNS)
        and normalized_text in normalized_query
    )


def _supports_place_query(place_query: str, normalized_query: str) -> bool:
    place = re.escape(_normalized(place_query))
    return (
        re.search(
            rf"\b(?:a|dans|in|of|de|autour\s+de|pres\s+de|near)\s+"
            rf"(?:la\s+commune\s+de\s+)?{place}\b",
            normalized_query,
        )
        is not None
    )


def _deterministic_intent(query: str) -> InterpretedSearch | None:
    cleaned = query.strip()
    if _UAI_RE.fullmatch(cleaned):
        return InterpretedSearch(text_query=cleaned.upper())
    if _POSTAL_RE.fullmatch(cleaned):
        return InterpretedSearch(postal_code=cleaned)
    padded = f" {_normalized(cleaned)} "
    if _is_subjective(cleaned):
        return None
    if not any(marker in padded for marker in _COMPLEX_MARKERS) and not (
        _FILTERED_PLACE_RE.search(padded) or _PLURAL_PLACE_RE.search(padded)
    ):
        return InterpretedSearch(text_query=cleaned)
    return None


class AssistantSearch:
    def __init__(
        self,
        interpreter: QueryInterpreter,
        communes: SearchCommunes,
        establishments: SearchEstablishments,
        interpretation_cache: InterpretationCache | None = None,
        version_provider: InterpretationVersionProvider | None = None,
    ) -> None:
        self._interpreter = interpreter
        self._communes = communes
        self._establishments = establishments
        self._interpretation_cache = interpretation_cache
        self._version_provider = version_provider
        if (interpretation_cache is None) != (version_provider is None):
            raise ValueError("cache and version_provider must be configured together")

    def run(self, query: str) -> AssistantSearchOutcome:
        cleaned = query.strip()
        if not cleaned or len(cleaned) > MAX_QUERY_LENGTH:
            raise InvalidAssistantQueryError(
                f"query must contain between 1 and {MAX_QUERY_LENGTH} characters"
            )

        subjective = _is_subjective(cleaned)
        intent = _deterministic_intent(cleaned)
        interpreted_by_provider = intent is None
        cache_key: str | None = None
        cache_hit = False
        if (
            intent is None
            and self._interpretation_cache is not None
            and self._version_provider is not None
        ):
            cache_key = self._cache_key(
                cleaned,
                self._interpreter.cache_identity,
                self._version_provider.current_version(),
            )
            intent = self._interpretation_cache.get(cache_key)
            cache_hit = intent is not None
        if intent is None:
            try:
                intent = self._interpreter.interpret(cleaned)
            except InterpreterUnavailableError:
                return AssistantSearchUnavailable()

        try:
            self._validate_intent(
                intent,
                cleaned,
                require_lexical_support=interpreted_by_provider,
            )
        except ValueError:
            return AssistantSearchUnavailable()
        if (
            interpreted_by_provider
            and not cache_hit
            and cache_key is not None
            and self._interpretation_cache is not None
        ):
            self._interpretation_cache.put(cache_key, intent)

        latitude: float | None = None
        longitude: float | None = None
        radius_km: float | None = None
        resolved_place: CommuneSearchResults | None = None
        if intent.needs_location and intent.place_query is None:
            return AssistantSearchClarification(
                ClarificationKind.LOCATION_REQUIRED,
                subjective_request_reframed=subjective,
            )
        if intent.place_query is not None:
            place_results = self._communes.run(intent.place_query)
            if not place_results.hits:
                return AssistantSearchClarification(
                    ClarificationKind.LOCATION_UNKNOWN,
                    place_results,
                    subjective_request_reframed=subjective,
                )
            best_tier = place_results.hits[0].match_tier
            best = tuple(
                hit for hit in place_results.hits if hit.match_tier == best_tier
            )
            if len(best) != 1:
                return AssistantSearchClarification(
                    ClarificationKind.LOCATION_AMBIGUOUS,
                    CommuneSearchResults(hits=best, source=place_results.source),
                    subjective_request_reframed=subjective,
                )
            commune = best[0].commune
            if intent.location_mode is LocationMode.AROUND and (
                commune.latitude is None or commune.longitude is None
            ):
                return AssistantSearchClarification(
                    ClarificationKind.LOCATION_HAS_NO_CENTRE,
                    CommuneSearchResults(hits=best, source=place_results.source),
                    subjective_request_reframed=subjective,
                )
            if intent.location_mode is LocationMode.AROUND:
                latitude = commune.latitude
                longitude = commune.longitude
                radius_km = intent.radius_km or DEFAULT_RADIUS_KM
            resolved_place = CommuneSearchResults(
                hits=(best[0],), source=place_results.source
            )

        criteria = SearchCriteria(
            text_query=intent.text_query,
            commune_code=(
                resolved_place.hits[0].commune.code
                if resolved_place is not None
                and intent.location_mode is LocationMode.EXACT_COMMUNE
                else None
            ),
            postal_code=intent.postal_code,
            establishment_type=intent.establishment_type,
            sector=intent.sector,
            filiere=intent.filiere,
            latitude=latitude,
            longitude=longitude,
            radius_km=radius_km,
        )
        return AssistantSearchSuccess(
            search=self._establishments.run(criteria),
            criteria=criteria,
            subjective_request_reframed=subjective,
            resolved_place=resolved_place,
        )

    @staticmethod
    def _cache_key(query: str, interpreter_identity: str, version: str) -> str:
        payload = "\0".join((interpreter_identity, version, _normalized(query)))
        return sha256(payload.encode()).hexdigest()

    @staticmethod
    def _validate_intent(
        intent: InterpretedSearch,
        original_query: str,
        *,
        require_lexical_support: bool,
    ) -> None:
        normalized_query = _normalized(original_query)
        for name, value in (
            ("text_query", intent.text_query),
            ("place_query", intent.place_query),
        ):
            if value is not None and (
                len(value.strip()) < 2
                or len(value.strip()) > 120
                or not any(char.isalnum() for char in value)
            ):
                raise ValueError(f"{name} is outside the search contract")
        if (
            require_lexical_support
            and intent.text_query is not None
            and not _supports_text_query(intent.text_query, normalized_query)
        ):
            raise ValueError("text_query is not supported by the request")
        if (
            require_lexical_support
            and intent.place_query is not None
            and not _supports_place_query(intent.place_query, normalized_query)
        ):
            raise ValueError("place_query is not supported by the request")
        if intent.postal_code is not None and not _POSTAL_RE.fullmatch(
            intent.postal_code
        ):
            raise ValueError("postal_code is outside the search contract")
        if intent.postal_code is not None and intent.postal_code not in original_query:
            raise ValueError("postal_code is not supported by the request")
        if intent.place_query is None and intent.location_mode is not None:
            raise ValueError("location_mode requires place_query")
        if intent.place_query is not None and intent.location_mode is None:
            raise ValueError("place_query requires location_mode")
        if (
            intent.radius_km is not None
            and intent.location_mode is not LocationMode.AROUND
        ):
            raise ValueError("radius_km requires around mode")
        if intent.radius_km is not None and not 0 < intent.radius_km <= 100:
            raise ValueError("radius_km is outside the search contract")
        if not require_lexical_support:
            return

        supported_patterns = (
            (
                "establishment_type",
                intent.establishment_type,
                _TYPE_SUPPORT_PATTERNS,
            ),
            ("sector", intent.sector, _SECTOR_SUPPORT_PATTERNS),
            ("filiere", intent.filiere, _FILIERE_SUPPORT_PATTERNS),
        )
        for field_name, field_value, patterns_by_value in supported_patterns:
            if field_value is None:
                continue
            if not _matches_any(normalized_query, patterns_by_value[field_value.value]):
                raise ValueError(f"{field_name} is not supported by the request")

        around_words = ("autour", "pres", "proche", "near", "within", "rayon")
        exact_words = (" a ", " de ", " dans ", " in ", " of ")
        padded_query = f" {normalized_query} "
        if intent.location_mode is LocationMode.AROUND and not any(
            word in normalized_query for word in around_words
        ):
            raise ValueError("around mode is not supported by the request")
        if intent.location_mode is LocationMode.EXACT_COMMUNE and not any(
            word in padded_query for word in exact_words
        ):
            raise ValueError("exact commune mode is not supported by the request")
        if intent.needs_location and not any(
            word in normalized_query for word in around_words
        ):
            raise ValueError("needs_location is not supported by the request")
        if intent.radius_km is not None:
            radius_spellings = {
                str(intent.radius_km),
                str(int(intent.radius_km))
                if intent.radius_km.is_integer()
                else str(intent.radius_km).replace(".", ","),
            }
            if not any(spelling in original_query for spelling in radius_spellings):
                raise ValueError("radius_km is not supported by the request")
        if not any(
            (
                intent.text_query,
                intent.place_query,
                intent.postal_code,
                intent.establishment_type,
                intent.sector,
                intent.filiere,
                intent.needs_location,
            )
        ):
            raise ValueError("interpretation contains no factual criterion")
