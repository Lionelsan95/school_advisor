"""The UAI — the official identifier of a French school establishment.

The format `^[0-9]{7}[A-Z]$` was verified against all 67 896 directory records
during the Phase 0 spike, with zero exceptions. It is therefore a genuine
domain invariant and is enforced here.

Note what is deliberately NOT enforced: the UAI is *not* unique in the source
directory. 74 identifiers designate multi-site establishments. That multiplicity
is modelled by `Establishment.sites`, not by relaxing this value object.
"""

from __future__ import annotations

import re
from typing import Final

UAI_PATTERN: Final = re.compile(r"^[0-9]{7}[A-Z]$")


class InvalidUaiError(ValueError):
    """Raised when a string cannot be a UAI. Never silently coerced."""


def parse_uai(raw: str | None) -> str:
    """Validate and normalise a UAI, or raise.

    Ingestion must not invent or repair identifiers: a malformed UAI is a
    source problem to surface, not to paper over.
    """
    if raw is None:
        raise InvalidUaiError("UAI is missing")
    candidate = raw.strip().upper()
    if not UAI_PATTERN.match(candidate):
        raise InvalidUaiError(f"Not a valid UAI: {raw!r}")
    return candidate


def is_valid_uai(raw: str | None) -> bool:
    try:
        parse_uai(raw)
    except InvalidUaiError:
        return False
    return True
