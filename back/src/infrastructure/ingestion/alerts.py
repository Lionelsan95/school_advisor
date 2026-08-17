"""OPS-3 — announcing an ingestion failure somewhere a human will see it.

`docs/02_Architecture_Decisions.md` names silent ingestion failure the project's
most critical blind spot, and until now the only channel was a CRITICAL log line
in a file nobody watches.

A webhook rather than email or a log-based alert: `httpx` is already a
dependency and `respx` already mocks it in tests, so this adds no infrastructure
and no new package, and — the deciding factor — it is provable offline. An
alerting path that can only be tested against a live service is an alerting path
nobody verifies.

**The rule this module exists to respect: it must never make things worse.**
Notification is best-effort and strictly secondary to the failure it reports.
A dead webhook must not mask the underlying error, must not turn a failure into
a different failure, and must not abort a run that otherwise succeeded. Every
call site therefore swallows its exceptions and logs them, which is the one
place in this codebase where swallowing is the correct behaviour — because the
thing that would otherwise be lost is already being reported by the caller.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Short on purpose. A slow notification endpoint must not hold up the report of
# a failure that has already happened.
ALERT_TIMEOUT_SECONDS = 5.0


def send_ingestion_failure_alert(
    webhook_url: str | None,
    *,
    reason: str,
    started_at: str,
    client: httpx.Client | None = None,
) -> bool:
    """Post a failure notice. Returns whether it was delivered.

    The return value exists for tests and for logging, never for control flow:
    no caller should behave differently because an alert failed to send.
    """
    if not webhook_url:
        # Not an error. Alerting is optional configuration, and a deployment
        # without a webhook still has the CRITICAL log and the `ingestion_run`
        # row. Logged at debug so it does not look like a problem.
        logger.debug("No ALERT_WEBHOOK_URL configured; skipping failure alert")
        return False

    payload: dict[str, Any] = {
        # Kept deliberately plain so it can be posted to Slack, Mattermost, a
        # small relay, or anything else, without this module knowing which.
        "text": (
            f"Ingestion failed for Établissements en clair.\n"
            f"Started: {started_at}\n"
            f"Reason: {reason}\n"
            f"No data was published; the previous snapshot is still live."
        ),
        "service": "etablissements-en-clair",
        "event": "ingestion_failed",
        "started_at": started_at,
        "reason": reason,
    }

    owns_client = client is None
    http = client or httpx.Client(timeout=ALERT_TIMEOUT_SECONDS)
    try:
        response = http.post(webhook_url, json=payload)
        if response.status_code >= 400:
            logger.error(
                "Ingestion failure alert rejected by the webhook (HTTP %s). "
                "The ingestion failure itself is unaffected and is logged above.",
                response.status_code,
            )
            return False
        logger.info("Ingestion failure alert delivered")
        return True
    except Exception as error:
        # Deliberate catch-all. See the module docstring: an unreachable
        # notification channel must never become the error a reader sees
        # instead of the ingestion failure that prompted it.
        logger.error(
            "Could not deliver the ingestion failure alert (%s). The ingestion "
            "failure itself is unaffected and is logged above.",
            error,
        )
        return False
    finally:
        if owns_client:
            http.close()
