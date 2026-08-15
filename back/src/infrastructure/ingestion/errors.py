"""Ingestion failures that must never be swallowed.

docs/02_Architecture_Decisions.md names silent ingestion failure as the single
most critical blind spot of this project: the government APIs can change shape
without warning, and a partial import that looks successful would quietly
corrupt what the product tells people. Every failure mode here is therefore a
loud exception, not a logged warning and a shrug.
"""

from __future__ import annotations


class IngestionError(Exception):
    """Base class for every ingestion failure."""


class SourceUnavailableError(IngestionError):
    """The upstream API could not be reached or kept failing."""


class SourceSchemaMismatchError(IngestionError):
    """The upstream dataset no longer has the shape the adapters rely on.

    Raised *before* any parsing, so a renamed or removed column can never be
    read as a null value and stored as if the source had published nothing.
    """

    def __init__(self, dataset_id: str, missing: list[str], present: list[str]):
        self.dataset_id = dataset_id
        self.missing = missing
        self.present = present
        super().__init__(
            f"Schema mismatch on {dataset_id}: expected field(s) {sorted(missing)} "
            f"are absent. The dataset now exposes {len(present)} fields. "
            f"Ingestion aborted — no partial import was performed."
        )
