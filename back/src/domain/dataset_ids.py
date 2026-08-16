"""Identifiers of the published datasets this product reads.

These live in the domain because they are pure identifiers with no framework
or transport dependency, and because two layers need them for different
reasons: infrastructure to fetch a dataset, and the application layer to
attach the right provenance to a figure (F10).

Keeping a single definition matters more than it looks. When these were
duplicated, a dataset id changing upstream would have been corrected in the
fetching code while the read side kept the old string — and the only symptom
would have been every result row quietly losing its source attribution, with
no error and no log. `INDICATOR_DATASET_IDS` exists so that mismatch is a
type-level impossibility rather than something a test has to notice.
"""

from __future__ import annotations

from typing import Final

from .enums import IndicatorType

DATASET_DIRECTORY: Final = "fr-en-annuaire-education"
DATASET_IVAC: Final = "fr-en-indicateurs-valeur-ajoutee-colleges"
DATASET_IVAL_GT: Final = "fr-en-indicateurs-de-resultat-des-lycees-gt_v2"
DATASET_IVAL_PRO: Final = "fr-en-indicateurs-de-resultat-des-lycees-pro_v2"
DATASET_COMMUNES: Final = "geo-api-gouv-communes"

INDICATOR_DATASET_IDS: Final[dict[IndicatorType, str]] = {
    IndicatorType.IVAC: DATASET_IVAC,
    IndicatorType.IVAL_GT: DATASET_IVAL_GT,
    IndicatorType.IVAL_PRO: DATASET_IVAL_PRO,
}
