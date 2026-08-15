"""Provenance of a published figure (feature F10).

Every number the product shows must be traceable to where it came from. This
is a direct consequence of the neutrality principle: an output that cannot be
traced to raw official data, a documented deterministic calculation, or
versioned editorial content has no place in a response.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Where a set of values came from, and when it was last synchronised."""

    dataset_id: str
    url: str
    last_synchronised_at: datetime
    source_published_at: date | None = None

    # Note: a SourceReference always designates an official dataset. Values
    # computed by this product are flagged separately at the serialization
    # boundary (`computed: true` in the API contract), so a reader can always
    # tell an official figure from a derived one. There is deliberately no
    # `is_official` flag here — it could only ever be True, and a field that
    # never varies invites a future reader to trust it as if it did.
