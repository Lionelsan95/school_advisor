"""API-10 / F9 — the glossary.

**This module is editorial content**, under the same human-review gate as
`explanatory_content.py`. Its text is shown to readers verbatim.

Two kinds of entry, and the distinction is deliberate:

- **Derived.** The five indicator concepts that already have an
  `ExplanatoryContent` block are converted from it, not retyped. There is
  exactly one authored copy of "what value added is", so the glossary and the
  fact sheet cannot drift into disagreeing about it — the same
  single-source-of-truth reasoning applied to the home-page scope reminder.
- **Authored.** Terms with no indicator block of their own (UAI, IVAC, DEPP,
  ULIS…). The source material is `docs/03_Glossaire_Metier.md`, but rewritten:
  that document is written for developers and carries meta-commentary
  ("Corrigé le 15/08/2026 (API-4)", match rates, ticket numbers) that has no
  place in front of a parent.

Voice per the charter §2: factual, calm, transparent about limits. A definition
here explains what a word means — it never says whether the thing it names is
desirable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .explanatory_content import (
    ACCESS_RATE,
    EXPECTED_RATE,
    MENTION_RATE,
    SUCCESS_RATE,
    VALUE_ADDED,
    ExplanatoryContent,
)

GLOSSARY_CONTENT_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class GlossaryTerm:
    """One entry. `related_term_ids` may name entries defined further down."""

    term_id: str
    term: str
    definition: str
    source_note: str
    example: str | None = None
    related_term_ids: tuple[str, ...] = ()


def _from_explanation(
    block: ExplanatoryContent, related: tuple[str, ...] = ()
) -> GlossaryTerm:
    """Reuse an indicator's reviewed definition rather than writing a second one."""
    return GlossaryTerm(
        term_id=block.content_id,
        term=block.title,
        definition=block.simple_definition,
        source_note=block.source_note,
        example=block.how_to_read,
        related_term_ids=related,
    )


_DERIVED: Final = (
    _from_explanation(VALUE_ADDED, ("taux_attendu", "taux_reussite", "ivac", "ival")),
    _from_explanation(SUCCESS_RATE, ("valeur_ajoutee", "taux_attendu")),
    _from_explanation(EXPECTED_RATE, ("valeur_ajoutee", "depp")),
    _from_explanation(ACCESS_RATE, ("ivac", "ival")),
    _from_explanation(MENTION_RATE, ("taux_reussite",)),
)


_AUTHORED: Final = (
    GlossaryTerm(
        term_id="uai",
        term="UAI",
        definition=(
            "L'unité administrative immatriculée est l'identifiant officiel "
            "d'un établissement scolaire : sept chiffres suivis d'une lettre, "
            "par exemple 0750001A."
        ),
        example=(
            "Un même UAI peut couvrir plusieurs sites : l'identifiant désigne "
            "l'établissement administratif, pas le bâtiment."
        ),
        source_note="Annuaire de l'éducation, ministère de l'Éducation nationale.",
        related_term_ids=("annuaire",),
    ),
    GlossaryTerm(
        term_id="depp",
        term="DEPP",
        definition=(
            "La direction de l'évaluation, de la prospective et de la "
            "performance est le service statistique du ministère de "
            "l'Éducation nationale. C'est elle qui calcule et publie les "
            "indicateurs présentés ici."
        ),
        source_note="Ministère de l'Éducation nationale.",
        related_term_ids=("ivac", "ival", "valeur_ajoutee"),
    ),
    GlossaryTerm(
        term_id="ivac",
        term="IVAC",
        definition=(
            "Les indicateurs de valeur ajoutée des collèges portent sur le "
            "diplôme national du brevet. Ils sont publiés depuis la session "
            "2022."
        ),
        example=(
            "Un collège dispose donc d'un historique plus court qu'un lycée. "
            "C'est une propriété de la publication, pas une donnée manquante."
        ),
        source_note="Indicateurs de valeur ajoutée des collèges, DEPP.",
        related_term_ids=("ival", "valeur_ajoutee", "depp"),
    ),
    GlossaryTerm(
        term_id="ival",
        term="IVAL",
        definition=(
            "Les indicateurs de valeur ajoutée des lycées portent sur le "
            "baccalauréat et sur le parcours au lycée. Ils sont publiés depuis "
            "la session 2012, en deux séries : générale et technologique d'une "
            "part, professionnelle d'autre part."
        ),
        example=(
            "La réforme du baccalauréat s'applique à partir de 2021 : les "
            "valeurs publiées avant et après cette date ne portent pas sur "
            "exactement le même examen."
        ),
        source_note="Indicateurs de valeur ajoutée des lycées, DEPP.",
        related_term_ids=("ivac", "valeur_ajoutee", "depp"),
    ),
    GlossaryTerm(
        term_id="annuaire",
        term="Annuaire de l'éducation",
        definition=(
            "Le répertoire officiel des établissements scolaires : nom, "
            "adresse, statut, filières et sections proposées. Il fournit "
            "l'identité des établissements présentés ici."
        ),
        source_note="Annuaire de l'éducation, data.education.gouv.fr.",
        related_term_ids=("uai",),
    ),
    GlossaryTerm(
        term_id="secteur",
        term="Public, privé",
        definition=(
            "Le statut administratif de l'établissement, tel que l'annuaire le "
            "publie : public ou privé."
        ),
        example=(
            "La source ne distingue pas le privé sous contrat du privé hors "
            "contrat, et laisse ce champ vide pour une petite part des "
            "établissements. Ce service ne complète pas cette information."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("annuaire",),
    ),
    GlossaryTerm(
        term_id="filiere",
        term="Filière",
        definition=(
            "Les voies d'enseignement proposées par l'établissement : "
            "générale, technologique, professionnelle. Un établissement peut "
            "en proposer plusieurs."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("annuaire", "ival"),
    ),
    GlossaryTerm(
        term_id="europeenne",
        term="Section européenne",
        definition=(
            "Une section européenne ou de langue orientale propose un "
            "enseignement linguistique renforcé et l'étude d'une discipline "
            "non linguistique dans cette langue."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("internationale",),
    ),
    GlossaryTerm(
        term_id="internationale",
        term="Section internationale",
        definition=(
            "Une section internationale accueille des élèves français et "
            "étrangers et propose un enseignement partagé avec un système "
            "éducatif partenaire."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("europeenne",),
    ),
    GlossaryTerm(
        term_id="sport",
        term="Section sportive",
        definition=(
            "Une section sportive scolaire permet de pratiquer une discipline "
            "sportive de façon approfondie dans le cadre de la scolarité."
        ),
        source_note="Annuaire de l'éducation.",
    ),
    GlossaryTerm(
        term_id="arts",
        term="Section arts",
        definition=(
            "Un enseignement artistique renforcé proposé dans le cadre de la "
            "scolarité, en complément du programme commun."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("cinema", "theatre"),
    ),
    GlossaryTerm(
        term_id="cinema",
        term="Section cinéma",
        definition=(
            "Un enseignement de cinéma et audiovisuel proposé dans le cadre "
            "de la scolarité."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("arts",),
    ),
    GlossaryTerm(
        term_id="theatre",
        term="Section théâtre",
        definition=(
            "Un enseignement de théâtre proposé dans le cadre de la scolarité."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("arts",),
    ),
    GlossaryTerm(
        term_id="ulis",
        term="ULIS",
        definition=(
            "Une unité localisée pour l'inclusion scolaire accueille, au sein "
            "de l'établissement, des élèves en situation de handicap avec un "
            "accompagnement adapté."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("segpa",),
    ),
    GlossaryTerm(
        term_id="segpa",
        term="SEGPA",
        definition=(
            "Une section d'enseignement général et professionnel adapté "
            "accueille, au collège, des élèves rencontrant des difficultés "
            "scolaires durables, avec des enseignements adaptés."
        ),
        source_note="Annuaire de l'éducation.",
        related_term_ids=("ulis",),
    ),
    GlossaryTerm(
        term_id="seuil_de_diffusion",
        term="Seuil de diffusion",
        definition=(
            "En dessous d'un certain nombre de candidats, la DEPP ne publie "
            "pas certains résultats, afin de ne pas diffuser de valeur peu "
            "fiable statistiquement."
        ),
        example=(
            "Ce seuil n'est pas le seul motif d'absence, et la source "
            "n'indique jamais lequel s'applique à une valeur donnée : voir "
            "« Valeur non disponible »."
        ),
        source_note=(
            "Conditions de publication décrites par la DEPP dans ses guides "
            "méthodologiques IVAC et IVAL."
        ),
        related_term_ids=("valeur_non_disponible", "depp"),
    ),
    GlossaryTerm(
        term_id="valeur_non_disponible",
        term="Valeur non disponible",
        definition=(
            "Une valeur que la source n'a pas publiée pour cette année. "
            "L'absence n'est pas un résultat et ne permet aucune conclusion "
            "sur l'établissement."
        ),
        example=(
            "Plusieurs situations peuvent l'expliquer, et le fichier publié "
            "n'indique pas laquelle s'applique. Ce service ne la devine pas."
        ),
        source_note="Guides méthodologiques IVAC et IVAL, DEPP.",
        related_term_ids=("seuil_de_diffusion",),
    ),
)


ALL_TERMS: Final[tuple[GlossaryTerm, ...]] = tuple(
    sorted((*_DERIVED, *_AUTHORED), key=lambda term: term.term.lower())
)

TERMS_BY_ID: Final[dict[str, GlossaryTerm]] = {term.term_id: term for term in ALL_TERMS}


def get_term(term_id: str) -> GlossaryTerm:
    """Raises `KeyError` rather than returning a placeholder.

    A glossary link pointing at a term that does not exist is a bug to surface,
    not something to paper over with generic text.
    """
    return TERMS_BY_ID[term_id]
