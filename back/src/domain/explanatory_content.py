"""API-3 / F3, F6, F7 — static, versioned explanatory content.

**This module is editorial content, not code that may be freely edited.**
Per CLAUDE.md ("Explanatory content change"), any change to the French strings
below requires explicit human review and sign-off before commit. No LLM may
rewrite them at request time, and no caller may interpolate a value into them:
what a reader sees for a given `content_id` is byte-identical for every
establishment, every year, and every request.

Structure follows docs/14_Charte_Neutralite_Editoriale.md §4, which mandates
six parts for each indicator explanation: simple definition, how to read the
value, what it measures, what it does not measure, method, and source note.

`version` exists so a change is detectable. Bump it whenever the text of an
entry changes; the content-consistency tests assert the pair (content_id,
version) still maps to the exact expected string.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True, slots=True)
class ExplanatoryContent:
    """One versioned editorial block, in the charter's six-part structure."""

    content_id: str
    version: int
    title: str
    simple_definition: str
    how_to_read: str
    what_it_measures: str
    what_it_does_not_measure: str
    source_note: str
    method: str | None = None


# --------------------------------------------------------------------------
# F7 — scope disclaimer. Single source of truth; imported by every response
# that carries establishment results. Wording from Charte §7 ("version
# courte"), reproduced verbatim.
# --------------------------------------------------------------------------

SCOPE_DISCLAIMER: Final = (
    "Ces indicateurs décrivent certains résultats scolaires. Ils ne mesurent "
    "pas l'ambiance, l'accompagnement quotidien, le bien-être des élèves ni "
    "l'adéquation avec un enfant."
)


# --------------------------------------------------------------------------
# F6 — absence of a published value.
#
# The wording below is constrained by a fact established twice: by the Phase 0
# spike, and by the DEPP's own methodology (Guide méthodologique IVAC 2025,
# "Conditions de publication des indicateurs"; DEPP catalogue entry for the
# IVAL). The methodology lists *three* distinct reasons a value-added figure
# may be absent — too few candidates, too little retrieved pupil information
# (<75% of 6e evaluation scores or of parental occupations), and Mayotte,
# where expected rates are not computed at all. The published open data marks
# none of them: every one of those cases arrives as a plain null, verified
# against the live API on rows with 143 and 655 candidates.
#
# So the reason is knowable in general and unknowable per row. The text
# therefore states the absence, lists the documented possibilities as
# possibilities, and attributes none of them. Anything narrower would assert a
# cause the source does not give — forbidden by Charte §14 question 3 — and
# the spike measured 457 rows a threshold-based message would mislabel.
# --------------------------------------------------------------------------

ABSENT_VALUE: Final = ExplanatoryContent(
    content_id="valeur_non_disponible",
    version=1,
    title="Valeur non disponible",
    simple_definition=(
        "Cette valeur n'est pas publiée dans les données officielles pour cette année."
    ),
    how_to_read=(
        "L'absence de valeur n'est pas un résultat. Elle ne signifie ni un "
        "résultat élevé, ni un résultat faible : elle signifie que la donnée "
        "n'a pas été diffusée."
    ),
    what_it_measures=(
        "La source publie l'absence sans en indiquer le motif. Sa "
        "documentation méthodologique prévoit plusieurs situations dans "
        "lesquelles une valeur ajoutée n'est pas diffusée : un nombre de "
        "candidats inférieur au seuil de diffusion, des informations "
        "disponibles pour moins de 75 % des élèves, ou le cas de Mayotte, où "
        "les taux attendus ne sont pas calculés."
    ),
    what_it_does_not_measure=(
        "Il n'est pas possible de savoir laquelle de ces situations "
        "s'applique à cet établissement pour cette année : le fichier publié "
        "ne le précise pas. Nous ne l'estimons pas et ne le devinons pas."
    ),
    method=(
        "Aucun calcul n'est effectué pour remplacer une valeur absente. "
        "Aucune estimation, aucun report d'une autre année, aucune "
        "substitution par zéro."
    ),
    source_note=(
        "Conditions de publication décrites par la direction de l'évaluation, "
        "de la prospective et de la performance (DEPP) dans ses guides "
        "méthodologiques IVAC et IVAL."
    ),
)


# --------------------------------------------------------------------------
# F3 — one entry per indicator concept the fact sheet can return.
# --------------------------------------------------------------------------

VALUE_ADDED: Final = ExplanatoryContent(
    content_id="valeur_ajoutee",
    version=1,
    title="Valeur ajoutée",
    simple_definition=(
        "La valeur ajoutée est l'écart, en points, entre le résultat observé "
        "dans l'établissement et le résultat statistiquement attendu pour les "
        "élèves qu'il accueille."
    ),
    how_to_read=(
        "Le signe fait partie de la donnée. Un écart de +4 points signifie "
        "que le résultat observé est supérieur de 4 points au résultat "
        "attendu ; un écart de −3 points, qu'il lui est inférieur de "
        "3 points. Un écart faible se lit comme un résultat proche de "
        "l'attendu."
    ),
    what_it_measures=(
        "Le résultat attendu tient compte de l'âge, de l'origine sociale, du "
        "sexe et du niveau scolaire des élèves à l'entrée dans "
        "l'établissement, ainsi que des caractéristiques de la population "
        "qu'il accueille."
    ),
    what_it_does_not_measure=(
        "Cet écart ne mesure pas à lui seul la qualité globale de "
        "l'établissement. Il porte sur un examen et une année donnés. Il ne "
        "dit rien de l'enseignement reçu dans les autres matières, du climat "
        "scolaire, ni du parcours d'un élève en particulier."
    ),
    method=(
        "Valeur ajoutée = taux constaté − taux attendu. Le taux attendu est "
        "produit par un modèle statistique de la DEPP ; il constitue une "
        "simulation, non un objectif assigné à l'établissement."
    ),
    source_note=(
        "Indicateurs de valeur ajoutée publiés par la DEPP (IVAC pour les "
        "collèges, IVAL pour les lycées)."
    ),
)

SUCCESS_RATE: Final = ExplanatoryContent(
    content_id="taux_reussite",
    version=1,
    title="Taux de réussite",
    simple_definition=(
        "Le taux de réussite est la part des élèves présents à l'examen qui "
        "l'ont obtenu."
    ),
    how_to_read=(
        "La valeur est exprimée en pourcentage des candidats présents. Elle "
        "dépend fortement du profil des élèves accueillis, ce que la valeur "
        "ajoutée permet de replacer en contexte."
    ),
    what_it_measures=(
        "Le rapport entre le nombre d'élèves ayant obtenu le diplôme et le "
        "nombre d'élèves de l'établissement inscrits et présents à l'examen."
    ),
    what_it_does_not_measure=(
        "Ce taux ne tient pas compte du profil des élèves accueillis. Il ne "
        "renseigne pas sur les élèves qui n'ont pas été présentés à l'examen, "
        "ni sur ce que les élèves ont appris."
    ),
    method=(
        "Taux constaté = diplômés ÷ présents. Les candidats déjà titulaires "
        "du diplôme l'année précédente sont retirés du calcul."
    ),
    source_note=("Taux de réussite publiés par la DEPP dans les séries IVAC et IVAL."),
)

ACCESS_RATE: Final = ExplanatoryContent(
    content_id="taux_acces",
    version=1,
    title="Taux d'accès",
    simple_definition=(
        "Le taux d'accès est la probabilité qu'un élève poursuive sa "
        "scolarité dans l'établissement jusqu'à la classe visée."
    ),
    how_to_read=(
        "La valeur est exprimée en pourcentage. Elle prend en compte "
        "l'ensemble de la scolarité dans l'établissement, y compris les "
        "redoublements."
    ),
    what_it_measures=(
        "La part des élèves qui accèdent au niveau visé en restant dans le "
        "même établissement, quel que soit le nombre d'années nécessaire."
    ),
    what_it_does_not_measure=(
        "Un élève qui change d'établissement n'est plus suivi par cet "
        "indicateur. Celui-ci ne distingue pas les motifs d'un départ et ne "
        "dit pas ce que sont devenus les élèves partis."
    ),
    method=(
        "Le taux est le produit des taux d'accès d'un niveau au suivant, "
        "observés sur deux années scolaires consécutives (cohorte fictive)."
    ),
    source_note=("Taux d'accès publiés par la DEPP dans les séries IVAC et IVAL."),
)

MENTION_RATE: Final = ExplanatoryContent(
    content_id="taux_mention",
    version=1,
    title="Taux de mention",
    simple_definition=(
        "Le taux de mention est la part des élèves présents à l'examen ayant "
        "obtenu une mention."
    ),
    how_to_read=(
        "La valeur est exprimée en pourcentage des candidats présents, toutes "
        "mentions confondues."
    ),
    what_it_measures=(
        "Le rapport entre le nombre de mentions attribuées et le nombre "
        "d'élèves présents à l'examen."
    ),
    what_it_does_not_measure=(
        "Ce taux ne distingue pas les niveaux de mention et dépend, comme le "
        "taux de réussite, du profil des élèves accueillis."
    ),
    method=None,
    source_note="Taux de mention publiés par la DEPP dans la série IVAL.",
)

EXPECTED_RATE: Final = ExplanatoryContent(
    content_id="taux_attendu",
    version=1,
    title="Taux attendu",
    simple_definition=(
        "Le taux attendu est le résultat qu'un modèle statistique estime pour "
        "les élèves accueillis par l'établissement."
    ),
    how_to_read=(
        "Ce taux sert de point de repère pour lire la valeur ajoutée : il "
        "n'est ni un objectif, ni une note. Il décrit ce qu'auraient obtenu "
        "des élèves comparables scolarisés dans un établissement contribuant "
        "à la réussite ni plus ni moins que la moyenne."
    ),
    what_it_measures=(
        "Une simulation fondée sur l'âge, l'origine sociale, le sexe et le "
        "niveau scolaire des élèves à l'entrée, ainsi que sur les "
        "caractéristiques de la population accueillie."
    ),
    what_it_does_not_measure=(
        "Le taux attendu ne constitue pas un objectif fixé à l'établissement "
        "et ne décrit aucun élève réel."
    ),
    method=(
        "Cette valeur n'est pas publiée telle quelle par la source. Elle est "
        "calculée par ce service à partir de deux données officielles : "
        "taux attendu = taux constaté − valeur ajoutée, conformément à la "
        "définition de la valeur ajoutée retenue par la DEPP."
    ),
    source_note=(
        "Calculé par ce service à partir des taux constatés et des valeurs "
        "ajoutées publiés par la DEPP."
    ),
)


# --------------------------------------------------------------------------
# F4 — a year one establishment published and another did not.
#
# Distinct from ABSENT_VALUE, and the distinction is load-bearing. ABSENT_VALUE
# covers a published row whose figure is empty. This covers an establishment
# that has no row for the year at all — which is the normal case when a collège
# (IVAC, from 2022) is placed beside a lycée (IVAL, from 2012), and says
# nothing whatever about either establishment.
#
# Without its own wording, a comparison table would render this as the same
# blank as a withheld figure, and a reader would take the two for the same
# thing. One means "not measured for this establishment that year"; the other
# means "measured, not published".
# --------------------------------------------------------------------------

YEAR_NOT_PUBLISHED: Final = ExplanatoryContent(
    content_id="annee_non_publiee",
    version=1,
    title="Année non publiée pour cet établissement",
    simple_definition=(
        "Aucun résultat n'est publié pour cet établissement pour cette année."
    ),
    how_to_read=(
        "Cette absence ne se compare pas. Elle indique seulement que l'année "
        "ne figure pas dans la série publiée pour cet établissement."
    ),
    what_it_measures=(
        "Les séries n'ont pas la même profondeur selon le type "
        "d'établissement : les indicateurs des collèges commencent en 2022, "
        "ceux des lycées en 2012. Un établissement peut aussi n'avoir pas "
        "existé, ou ne pas avoir présenté de candidats, cette année-là."
    ),
    what_it_does_not_measure=(
        "Cette absence ne dit rien des résultats de l'établissement, ni de "
        "ceux de l'établissement placé à côté."
    ),
    method=None,
    source_note=(
        "Profondeur des séries publiées par la DEPP : IVAC à partir de 2022, "
        "IVAL à partir de 2012."
    ),
)


_ALL: Final = (
    ABSENT_VALUE,
    YEAR_NOT_PUBLISHED,
    VALUE_ADDED,
    SUCCESS_RATE,
    ACCESS_RATE,
    MENTION_RATE,
    EXPECTED_RATE,
)

CONTENT_BY_ID: Final[dict[str, ExplanatoryContent]] = {
    entry.content_id: entry for entry in _ALL
}


def get_content(content_id: str) -> ExplanatoryContent:
    """Return the versioned block for `content_id`.

    Raises `KeyError` rather than returning a default: a response referring to
    an explanation that does not exist is a bug to surface, not to paper over
    with generic text.
    """
    return CONTENT_BY_ID[content_id]
