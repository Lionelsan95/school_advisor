"""Application-level ingestion failures.

These belong here rather than in `infrastructure/` because they express
*business* rules — the quality gates defined next to them in
`ingest_public_data.py` — not a transport or storage problem. Keeping them in
the application layer preserves the dependency direction stated in `ports.py`:
application code never imports from infrastructure.
"""

from __future__ import annotations


class SuspiciousIngestionError(Exception):
    """The data arrived intact but does not look like what we know.

    Covers the quality gates that a schema check cannot catch: a collapsed
    record count, or a join match rate well below what the Phase 0 spike
    measured. Raised before anything is written, so a suspicious run never
    reaches users.
    """
