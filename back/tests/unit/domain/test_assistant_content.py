"""Exact locks for the human-approved bounded-assistant editorial copy."""

from src.domain import assistant_content


def test_assistant_content_version_is_locked() -> None:
    assert assistant_content.ASSISTANT_CONTENT_VERSION == 1


def test_subjective_request_reframe_is_the_approved_version() -> None:
    assert assistant_content.SUBJECTIVE_REQUEST_REFRAME == (
        "Ce service ne classe pas et ne recommande pas les établissements. "
        "La demande est limitée à des critères factuels sans ordre fondé sur "
        "les résultats."
    )


def test_location_required_question_is_the_approved_version() -> None:
    assert assistant_content.LOCATION_REQUIRED == (
        "Autour de quelle commune souhaitez-vous effectuer la recherche ?"
    )


def test_location_unknown_question_is_the_approved_version() -> None:
    assert assistant_content.LOCATION_UNKNOWN == (
        "Quelle commune officielle souhaitez-vous utiliser pour cette recherche ?"
    )


def test_location_ambiguity_question_is_the_approved_version() -> None:
    assert assistant_content.LOCATION_AMBIGUOUS == (
        "Plusieurs communes correspondent. Laquelle souhaitez-vous utiliser ?"
    )


def test_missing_commune_centre_question_is_the_approved_version() -> None:
    assert assistant_content.LOCATION_HAS_NO_CENTRE == (
        "Le référentiel officiel ne publie pas de centre pour cette commune. "
        "Souhaitez-vous préciser une autre commune ?"
    )


def test_interpreter_unavailable_message_is_the_approved_version() -> None:
    assert assistant_content.INTERPRETER_UNAVAILABLE == (
        "L'interprétation en langage naturel n'est pas disponible. "
        "La recherche structurée reste accessible."
    )
