"""Static, versioned user-facing content for the bounded search assistant.

No provider output is displayed to users. Changes to these strings require the
same explicit human-review workflow as other editorial content.
"""

ASSISTANT_CONTENT_VERSION = 1

SUBJECTIVE_REQUEST_REFRAME = (
    "Ce service ne classe pas et ne recommande pas les établissements. "
    "La demande est limitée à des critères factuels sans ordre fondé sur "
    "les résultats."
)

LOCATION_REQUIRED = "Autour de quelle commune souhaitez-vous effectuer la recherche ?"
LOCATION_UNKNOWN = (
    "Quelle commune officielle souhaitez-vous utiliser pour cette recherche ?"
)
LOCATION_AMBIGUOUS = (
    "Plusieurs communes correspondent. Laquelle souhaitez-vous utiliser ?"
)
LOCATION_HAS_NO_CENTRE = (
    "Le référentiel officiel ne publie pas de centre pour cette commune. "
    "Souhaitez-vous préciser une autre commune ?"
)

INTERPRETER_UNAVAILABLE = (
    "L'interprétation en langage naturel n'est pas disponible. "
    "La recherche structurée reste accessible."
)
