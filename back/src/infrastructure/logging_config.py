"""OPS-3 — one place that decides how this service logs.

Two entry points configure logging (the API lifespan and the ingestion CLI), and
they previously each called `logging.basicConfig` with their own arguments. That
is how a deployment ends up with structured logs from one path and bare text
from the other, which is worse than either alone: a log search that works for
requests silently misses ingestion.

JSON in production because a log line nobody can query is not observability.
Text in development because JSON is unpleasant to read in a terminal, and the
format is a deployment concern rather than a property of the code.
"""

from __future__ import annotations

import json
import logging
from typing import Any

# Attributes `logging.LogRecord` sets itself. Anything else on a record came
# from `extra=` at the call site and is worth carrying into the output — the
# ingestion paths already pass dataset ids, UAIs and years that way.
_STANDARD_ATTRIBUTES = frozenset(
    logging.LogRecord("", 0, "", 0, "", None, None).__dict__
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    """Minimal JSON formatter — no dependency for a dozen lines of work."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRIBUTES:
                payload[key] = value

        if record.exc_info:
            # Kept as one string rather than a nested object: a traceback is
            # read by a human, and splitting it across JSON fields helps nobody.
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)


def configure_logging(level: str = "INFO", log_format: str = "text") -> None:
    """Install a single handler on the root logger.

    Replaces existing handlers rather than adding to them, so calling this
    twice — the API and a CLI invocation in one process, say — cannot produce
    every line twice.
    """
    handler = logging.StreamHandler()
    if log_format == "json":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level.upper())
