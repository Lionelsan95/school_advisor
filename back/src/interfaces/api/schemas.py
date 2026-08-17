"""The single English -> French serialization boundary.

Domain and application code uses English identifiers; the wire format is
French, per the journal entry "Identifiants de code en anglais, format JSON en
français". That conversion happens here and nowhere else.

No wording in this module is composed at runtime. Every explanatory or
disclaimer string is looked up from `domain.explanatory_content`, which is
static versioned content under human review — see CLAUDE.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from src.application.assistant_search import (
    AssistantSearchClarification,
    AssistantSearchSuccess,
    AssistantSearchUnavailable,
    ClarificationKind,
    UnavailableReason,
)
from src.application.compare_establishments import Comparison, ComparisonCell
from src.application.get_establishment_fact_sheet import FactSheet, Figure, ResultRow
from src.application.get_establishment_history import EstablishmentHistory
from src.application.ports import SearchCriteria
from src.application.search_communes import CommuneSearchResults
from src.application.search_establishments import EstablishmentSearchResponse
from src.domain import assistant_content, glossary_content
from src.domain import explanatory_content as content
from src.domain.establishment import Establishment
from src.domain.methodology_break import MethodologyBreak
from src.domain.source_reference import SourceReference


class SourceOut(BaseModel):
    """Provenance of a figure (F10)."""

    dataset_id: str
    url: str
    derniere_synchronisation: datetime
    date_publication: date | None = None

    @classmethod
    def of(cls, reference: SourceReference) -> SourceOut:
        return cls(
            dataset_id=reference.dataset_id,
            url=reference.url,
            derniere_synchronisation=reference.last_synchronised_at,
            date_publication=reference.source_published_at,
        )


class ExplanationOut(BaseModel):
    """A static explanatory block, in the charter's six-part structure."""

    content_id: str
    version: int
    titre: str
    definition_simple: str
    comment_lire: str
    ce_que_cela_mesure: str
    ce_que_cela_ne_mesure_pas: str
    methode: str | None
    source: str

    @classmethod
    def of(cls, block: content.ExplanatoryContent) -> ExplanationOut:
        return cls(
            content_id=block.content_id,
            version=block.version,
            titre=block.title,
            definition_simple=block.simple_definition,
            comment_lire=block.how_to_read,
            ce_que_cela_mesure=block.what_it_measures,
            ce_que_cela_ne_mesure_pas=block.what_it_does_not_measure,
            methode=block.method,
            source=block.source_note,
        )


class FigureOut(BaseModel):
    """One number, or an explicit, reason-free absence (F6).

    When `valeur` is null, `explication_absence` carries the *content id* of
    the static block explaining what an absence means. The block itself is
    returned once per response under `explications`, not repeated per figure —
    and it never names a cause for this particular row, because no source
    publishes one.
    """

    valeur: float | None
    calcule: bool = False
    note_de_calcul: str | None = None
    explication_absence: str | None = None

    @classmethod
    def of(cls, figure: Figure) -> FigureOut:
        return cls(
            valeur=figure.value,
            calcule=figure.computed,
            note_de_calcul=figure.computation_note,
            explication_absence=(
                None if figure.is_present else content.ABSENT_VALUE.content_id
            ),
        )


class ResultOut(BaseModel):
    annee: int
    type_indicateur: str
    candidats_presents: int | None
    taux_reussite: FigureOut
    taux_reussite_attendu: FigureOut
    valeur_ajoutee_reussite: FigureOut
    taux_acces: FigureOut
    valeur_ajoutee_acces: FigureOut
    taux_mention: FigureOut
    valeur_ajoutee_mention: FigureOut
    source: SourceOut

    @classmethod
    def of(cls, row: ResultRow) -> ResultOut:
        return cls(
            annee=row.year,
            type_indicateur=row.indicator_type.value,
            candidats_presents=row.candidates_present,
            taux_reussite=FigureOut.of(row.success_rate),
            taux_reussite_attendu=FigureOut.of(row.expected_success_rate),
            valeur_ajoutee_reussite=FigureOut.of(row.value_added_success),
            taux_acces=FigureOut.of(row.access_rate),
            valeur_ajoutee_acces=FigureOut.of(row.value_added_access),
            taux_mention=FigureOut.of(row.mention_rate),
            valeur_ajoutee_mention=FigureOut.of(row.value_added_mention),
            source=SourceOut.of(row.source),
        )


class SiteOut(BaseModel):
    nom: str
    adresse: str | None
    code_postal: str | None
    commune: str | None
    code_commune: str | None
    latitude: float | None
    longitude: float | None


class IdentityOut(BaseModel):
    nom: str
    type: str
    statut_public_prive: str | None
    adresse: str | None
    code_postal: str | None
    commune: str | None
    code_departement: str | None
    filieres: list[str]
    sections: list[str]
    # A multi-site establishment publishes one UAI for several addresses. The
    # list is returned in full: dropping a site would hide a real location
    # from someone who might be assigned to it.
    sites: list[SiteOut]


def _identity_of(establishment: Establishment) -> IdentityOut:
    canonical = establishment.canonical_site
    return IdentityOut(
        nom=establishment.name,
        type=establishment.type.value,
        statut_public_prive=(
            establishment.sector.value if establishment.sector else None
        ),
        adresse=canonical.address,
        code_postal=canonical.postal_code,
        commune=canonical.city,
        code_departement=establishment.department_code,
        filieres=[filiere.value for filiere in establishment.filieres],
        sections=[section.value for section in establishment.sections],
        sites=[
            SiteOut(
                nom=site.name,
                adresse=site.address,
                code_postal=site.postal_code,
                commune=site.city,
                code_commune=site.city_code,
                latitude=site.latitude,
                longitude=site.longitude,
            )
            for site in establishment.sites
        ],
    )


# Which explanatory blocks a fact sheet carries. Always the same set, so a
# reader never sees an indicator explained on one page and bare on another.
_FACT_SHEET_EXPLANATIONS = (
    content.VALUE_ADDED,
    content.SUCCESS_RATE,
    content.EXPECTED_RATE,
    content.ACCESS_RATE,
    content.MENTION_RATE,
    content.ABSENT_VALUE,
)


class ComparisonCellOut(BaseModel):
    """One establishment's data for one year of a comparison.

    `annee_publiee: false` means this establishment has no published row for
    the year at all — not that its figures were withheld. `explication_absence`
    then points at the static block saying so, which is a different block from
    the one used for a missing figure inside a published row.
    """

    uai: str
    annee_publiee: bool
    resultat: ResultOut | None
    explication_absence: str | None

    @classmethod
    def of(cls, cell: ComparisonCell) -> ComparisonCellOut:
        return cls(
            uai=cell.uai,
            annee_publiee=cell.has_published_year,
            resultat=ResultOut.of(cell.row) if cell.row is not None else None,
            explication_absence=(
                None
                if cell.has_published_year
                else content.YEAR_NOT_PUBLISHED.content_id
            ),
        )


class ComparisonRowOut(BaseModel):
    annee: int
    cellules: list[ComparisonCellOut]


class ComparisonIdentityOut(BaseModel):
    uai: str
    nom: str
    type: str
    statut_public_prive: str | None
    commune: str | None


class CompareOut(BaseModel):
    """Two establishments' published records, aligned by year.

    Note what this response does NOT contain, by construction: no difference,
    no winner, no count of criteria, no aggregate of any kind. The charter
    (§11) forbids computing them, and the shape gives a client nothing to
    compute them from — each cell is rendered independently, and the two
    values for a year are never handed over as a pair.
    """

    etablissements: list[ComparisonIdentityOut]
    lignes: list[ComparisonRowOut]
    explications: dict[str, ExplanationOut]
    rappel_de_portee: str = Field(default=content.SCOPE_DISCLAIMER)

    @classmethod
    def of(cls, comparison: Comparison) -> CompareOut:
        return cls(
            etablissements=[
                ComparisonIdentityOut(
                    uai=establishment.uai,
                    nom=establishment.name,
                    type=establishment.type.value,
                    statut_public_prive=(
                        establishment.sector.value if establishment.sector else None
                    ),
                    commune=establishment.canonical_site.city,
                )
                for establishment in comparison.establishments
            ],
            lignes=[
                ComparisonRowOut(
                    annee=row.year,
                    cellules=[ComparisonCellOut.of(cell) for cell in row.cells],
                )
                for row in comparison.rows
            ],
            explications={
                block.content_id: ExplanationOut.of(block)
                for block in (*_FACT_SHEET_EXPLANATIONS, content.YEAR_NOT_PUBLISHED)
            },
            rappel_de_portee=content.SCOPE_DISCLAIMER,
        )


class GlossaryTermOut(BaseModel):
    """One glossary entry.

    `termes_associes` carries ids, not prose, so the frontend links terms
    without any of them having to embed markup in reviewed text.
    """

    term_id: str
    terme: str
    definition: str
    exemple: str | None
    source: str
    termes_associes: list[str]

    @classmethod
    def of(cls, term: glossary_content.GlossaryTerm) -> GlossaryTermOut:
        return cls(
            term_id=term.term_id,
            terme=term.term,
            definition=term.definition,
            exemple=term.example,
            source=term.source_note,
            termes_associes=list(term.related_term_ids),
        )


class GlossaryOut(BaseModel):
    """The whole glossary, alphabetical. Static content — no query parameters.

    Returned in full rather than paginated or searchable server-side: it is a
    few dozen short entries, and shipping it whole lets the frontend link a
    term inline without a request per term.
    """

    version: int
    termes: list[GlossaryTermOut]
    rappel_de_portee: str = Field(default=content.SCOPE_DISCLAIMER)

    @classmethod
    def of(cls) -> GlossaryOut:
        return cls(
            version=glossary_content.GLOSSARY_CONTENT_VERSION,
            termes=[GlossaryTermOut.of(term) for term in glossary_content.ALL_TERMS],
            rappel_de_portee=content.SCOPE_DISCLAIMER,
        )


class MethodologyBreakOut(BaseModel):
    """A year from which the series stops being strictly comparable.

    Present only when this establishment's own history spans the break. The
    note is static, human-reviewed content: the chart must be able to say why
    the reader should not read across the year, and that sentence cannot be
    composed at request time.
    """

    annee: int
    content_id: str
    version: int
    titre: str
    note: str

    @classmethod
    def of(cls, item: MethodologyBreak) -> MethodologyBreakOut:
        return cls(
            annee=item.year,
            content_id=item.content_id,
            version=item.version,
            titre=item.title,
            note=item.note,
        )


class HistoryOut(BaseModel):
    """Every published year for one establishment, oldest first.

    Carries the same figure objects as the fact sheet — a history point is not
    a reduced or rounded version of a result, it is the same result read in a
    different order. `annees_couvertes` states the span explicitly so a reader
    can tell a short history (IVAC starts in 2022) from a gap in a long one.
    """

    uai: str
    nom: str
    points: list[ResultOut]
    ruptures_methodologiques: list[MethodologyBreakOut]
    annees_couvertes: list[int]
    explications: dict[str, ExplanationOut]
    rappel_de_portee: str = Field(default=content.SCOPE_DISCLAIMER)

    @classmethod
    def of(cls, history: EstablishmentHistory) -> HistoryOut:
        return cls(
            uai=history.establishment.uai,
            nom=history.establishment.name,
            points=[ResultOut.of(row) for row in history.points],
            ruptures_methodologiques=[
                MethodologyBreakOut.of(item) for item in history.methodology_breaks
            ],
            annees_couvertes=list(history.covered_years),
            explications={
                block.content_id: ExplanationOut.of(block)
                for block in _FACT_SHEET_EXPLANATIONS
            },
            rappel_de_portee=content.SCOPE_DISCLAIMER,
        )


class FactSheetOut(BaseModel):
    uai: str
    identite: IdentityOut
    resultats: list[ResultOut]
    explications: dict[str, ExplanationOut]
    rappel_de_portee: str = Field(default=content.SCOPE_DISCLAIMER)
    derniere_synchronisation: datetime | None

    @classmethod
    def of(cls, sheet: FactSheet) -> FactSheetOut:
        return cls(
            uai=sheet.establishment.uai,
            identite=_identity_of(sheet.establishment),
            resultats=[ResultOut.of(row) for row in sheet.results],
            explications={
                block.content_id: ExplanationOut.of(block)
                for block in _FACT_SHEET_EXPLANATIONS
            },
            rappel_de_portee=content.SCOPE_DISCLAIMER,
            derniere_synchronisation=sheet.last_synchronised_at,
        )


class SearchHitOut(BaseModel):
    """A search result carries identity only — never a result indicator.

    Returning a figure here would let a client sort or colour the list by it,
    which is the ranking this product exists not to produce. Results live on
    the fact sheet, one establishment at a time.
    """

    uai: str
    nom: str
    type: str
    statut_public_prive: str | None
    commune: str | None
    code_postal: str | None
    code_departement: str | None
    filieres: list[str]
    latitude: float | None
    longitude: float | None
    distance_km: float | None


class FiltersAppliedOut(BaseModel):
    q: str | None
    code_commune: str | None
    code_postal: str | None
    type: str | None
    secteur: str | None
    filiere: str | None
    latitude: float | None
    longitude: float | None
    rayon_km: float | None
    limit: int
    offset: int


class SearchResponseOut(BaseModel):
    resultats: list[SearchHitOut]
    nombre_total: int
    tri: str
    filtres_appliques: FiltersAppliedOut
    source: SourceOut
    rappel_de_portee: str = Field(default=content.SCOPE_DISCLAIMER)

    @classmethod
    def of(
        cls, response: EstablishmentSearchResponse, criteria: SearchCriteria
    ) -> SearchResponseOut:
        results = response.results
        return cls(
            resultats=[
                SearchHitOut(
                    uai=hit.establishment.uai,
                    nom=hit.establishment.name,
                    type=hit.establishment.type.value,
                    statut_public_prive=(
                        hit.establishment.sector.value
                        if hit.establishment.sector
                        else None
                    ),
                    commune=hit.establishment.canonical_site.city,
                    code_postal=hit.establishment.canonical_site.postal_code,
                    code_departement=hit.establishment.department_code,
                    filieres=[f.value for f in hit.establishment.filieres],
                    latitude=hit.establishment.canonical_site.latitude,
                    longitude=hit.establishment.canonical_site.longitude,
                    distance_km=hit.distance_km,
                )
                for hit in results.hits
            ],
            nombre_total=results.total_count,
            # Stated explicitly so a consumer never has to infer the ordering,
            # and so it is visible that neither option involves a result.
            tri=(
                "correspondance_puis_proximite"
                if criteria.text_query is not None and criteria.has_location
                else "correspondance"
                if criteria.text_query is not None
                else "proximite"
                if criteria.has_location
                else "alphabetique"
            ),
            filtres_appliques=FiltersAppliedOut(
                q=criteria.text_query,
                code_commune=criteria.commune_code,
                code_postal=criteria.postal_code,
                type=(
                    criteria.establishment_type.value
                    if criteria.establishment_type
                    else None
                ),
                secteur=criteria.sector.value if criteria.sector else None,
                filiere=criteria.filiere.value if criteria.filiere else None,
                latitude=criteria.latitude,
                longitude=criteria.longitude,
                rayon_km=criteria.radius_km,
                limit=criteria.limit,
                offset=criteria.offset,
            ),
            source=SourceOut.of(response.source),
            rappel_de_portee=content.SCOPE_DISCLAIMER,
        )


class CommuneHitOut(BaseModel):
    code: str
    nom: str
    codes_postaux: list[str]
    code_departement: str
    latitude: float | None
    longitude: float | None


class CommuneSearchResponseOut(BaseModel):
    resultats: list[CommuneHitOut]
    source: SourceOut

    @classmethod
    def of(cls, results: CommuneSearchResults) -> CommuneSearchResponseOut:
        return cls(
            resultats=[
                CommuneHitOut(
                    code=hit.commune.code,
                    nom=hit.commune.name,
                    codes_postaux=list(hit.commune.postal_codes),
                    code_departement=hit.commune.department_code,
                    latitude=hit.commune.latitude,
                    longitude=hit.commune.longitude,
                )
                for hit in results.hits
            ],
            source=SourceOut.of(results.source),
        )


class AssistantSearchIn(BaseModel):
    requete: str = Field(min_length=1, max_length=500)


class AssistantSearchSuccessOut(BaseModel):
    etat: Literal["resultats"] = "resultats"
    recherche: SearchResponseOut
    lieu_resolu: CommuneHitOut | None = None
    source_lieu: SourceOut | None = None
    reformulation_neutre: str | None = None

    @classmethod
    def of(cls, outcome: AssistantSearchSuccess) -> AssistantSearchSuccessOut:
        note = (
            assistant_content.SUBJECTIVE_REQUEST_REFRAME
            if outcome.subjective_request_reframed
            else None
        )
        return cls(
            recherche=SearchResponseOut.of(outcome.search, outcome.criteria),
            lieu_resolu=(
                CommuneHitOut(
                    code=outcome.resolved_place.hits[0].commune.code,
                    nom=outcome.resolved_place.hits[0].commune.name,
                    codes_postaux=list(
                        outcome.resolved_place.hits[0].commune.postal_codes
                    ),
                    code_departement=(
                        outcome.resolved_place.hits[0].commune.department_code
                    ),
                    latitude=outcome.resolved_place.hits[0].commune.latitude,
                    longitude=outcome.resolved_place.hits[0].commune.longitude,
                )
                if outcome.resolved_place is not None
                else None
            ),
            source_lieu=(
                SourceOut.of(outcome.resolved_place.source)
                if outcome.resolved_place is not None
                else None
            ),
            reformulation_neutre=note,
        )


_CLARIFICATION_MESSAGES = {
    ClarificationKind.LOCATION_REQUIRED: assistant_content.LOCATION_REQUIRED,
    ClarificationKind.LOCATION_UNKNOWN: assistant_content.LOCATION_UNKNOWN,
    ClarificationKind.LOCATION_AMBIGUOUS: assistant_content.LOCATION_AMBIGUOUS,
    ClarificationKind.LOCATION_HAS_NO_CENTRE: (
        assistant_content.LOCATION_HAS_NO_CENTRE
    ),
}


class AssistantSearchClarificationOut(BaseModel):
    etat: Literal["clarification"] = "clarification"
    type_clarification: str
    question: str
    options: list[CommuneHitOut]
    source: SourceOut | None = None
    reformulation_neutre: str | None = None

    @classmethod
    def of(
        cls, outcome: AssistantSearchClarification
    ) -> AssistantSearchClarificationOut:
        options = outcome.options
        return cls(
            type_clarification=outcome.kind.value,
            question=_CLARIFICATION_MESSAGES[outcome.kind],
            options=(
                [
                    CommuneHitOut(
                        code=hit.commune.code,
                        nom=hit.commune.name,
                        codes_postaux=list(hit.commune.postal_codes),
                        code_departement=hit.commune.department_code,
                        latitude=hit.commune.latitude,
                        longitude=hit.commune.longitude,
                    )
                    for hit in options.hits
                ]
                if options is not None
                else []
            ),
            source=SourceOut.of(options.source) if options is not None else None,
            reformulation_neutre=(
                assistant_content.SUBJECTIVE_REQUEST_REFRAME
                if outcome.subjective_request_reframed
                else None
            ),
        )


class AssistantSearchUnavailableOut(BaseModel):
    """No search was run.

    Which of the two approved messages leads depends on what actually
    happened. A rejected interpretation of a subjective request is a refusal to
    rank, and says so; anything else reports the interpretation as
    unavailable, which is what it was. No wording is composed here — both
    strings come from the versioned, human-approved assistant content.

    When a ranking request fails for a genuinely technical reason, the refusal
    to rank still travels alongside in `reformulation_neutre` rather than being
    dropped, so the service's position is never hidden behind an outage.
    """

    etat: Literal["indisponible"] = "indisponible"
    message: str = assistant_content.INTERPRETER_UNAVAILABLE
    reformulation_neutre: str | None = None

    @classmethod
    def of(cls, outcome: AssistantSearchUnavailable) -> AssistantSearchUnavailableOut:
        refused_a_ranking_request = (
            outcome.reason is UnavailableReason.INTERPRETATION_REJECTED
            and outcome.subjective_request_reframed
        )
        if refused_a_ranking_request:
            return cls(
                message=assistant_content.SUBJECTIVE_REQUEST_REFRAME,
                reformulation_neutre=None,
            )
        return cls(
            message=assistant_content.INTERPRETER_UNAVAILABLE,
            reformulation_neutre=(
                assistant_content.SUBJECTIVE_REQUEST_REFRAME
                if outcome.subjective_request_reframed
                else None
            ),
        )
