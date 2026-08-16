"""HTTP client for the Opendatasoft Explore API v2.1.

Behaviour here encodes what the Phase 0 spike established about this API.
See CLAUDE.md "Non-obvious gotchas" — each of these was observed, not assumed:

- `/records` caps at 100 rows per page and has an offset ceiling, so it cannot
  page a full dataset. `/exports/json` has no such ceiling and is the only
  viable full-pull endpoint.
- `select=` must be used to restrict columns; the directory has 71 fields.
- The catalogue metadata endpoint returns gzip even when the request asks for
  identity encoding, unlike `/records` and `/exports`.
"""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

import httpx

from src.domain.dataset_ids import (
    DATASET_DIRECTORY,
    DATASET_IVAC,
    DATASET_IVAL_GT,
    DATASET_IVAL_PRO,
)

from .errors import SourceSchemaMismatchError, SourceUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://data.education.gouv.fr/api/explore/v2.1"

# Re-exported from the domain so both the fetching code here and the
# provenance mapping in the application layer name the same strings. Do not
# redefine them locally — see src/domain/dataset_ids.py.
__all__ = [
    "DATASET_DIRECTORY",
    "DATASET_IVAC",
    "DATASET_IVAL_GT",
    "DATASET_IVAL_PRO",
    "OdsClient",
]


class OdsClient:
    """Thin, synchronous client. The ingestion job is a background batch;
    concurrency would add failure modes without shortening a 10-second pull."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 180.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._catalog_cache: dict[str, dict[str, Any]] = {}
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "etablissements-en-clair/0.1"},
            follow_redirects=True,
        )

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.get(url, params=params)
            except httpx.HTTPError as error:
                last_error = error
            else:
                if response.status_code < 400:
                    return response
                # A 4xx other than 429 means our request is wrong; retrying
                # would only hide the mistake.
                if response.status_code != 429 and response.status_code < 500:
                    raise SourceUnavailableError(
                        f"{url} returned HTTP {response.status_code}: "
                        f"{response.text[:300]}"
                    )
                last_error = SourceUnavailableError(f"HTTP {response.status_code}")
            logger.warning(
                "Source request failed (attempt %d/%d): %s",
                attempt + 1,
                self._max_retries,
                last_error,
            )
            # Back off before retrying. Hammering a public government API
            # immediately after a 429 would make the throttling worse, not
            # better. Skipped after the final attempt.
            if attempt < self._max_retries - 1:
                time.sleep(self._backoff_seconds * (2**attempt))
        raise SourceUnavailableError(
            f"{url} failed after {self._max_retries} attempts: {last_error}"
        )

    def _catalog_entry(self, dataset_id: str) -> dict[str, Any]:
        """Fetch a dataset's catalogue entry, once per client instance.

        Both the schema check and the provenance lookup need this document, so
        without the cache a run made two identical requests per dataset — eight
        avoidable round trips against a public API this client already backs
        off from on 429s. A client lives for one ingestion run, so the cache
        cannot serve stale metadata across runs.
        """
        cached = self._catalog_cache.get(dataset_id)
        if cached is not None:
            return cached
        response = self._get(f"{self._base_url}/catalog/datasets/{dataset_id}")
        payload: dict[str, Any] = response.json()
        self._catalog_cache[dataset_id] = payload
        return payload

    def field_names(self, dataset_id: str) -> list[str]:
        return [
            field["name"] for field in self._catalog_entry(dataset_id).get("fields", [])
        ]

    def dataset_page_url(self, dataset_id: str) -> str:
        """The human-readable portal page for a dataset (F10 source link).

        Derived from the configured API base URL so a different deployment or
        a test double does not silently link back to the production portal.
        """
        portal = self._base_url.split("/api/explore/")[0]
        return f"{portal}/explore/dataset/{dataset_id}/information/"

    def data_published_at(self, dataset_id: str) -> date | None:
        """When the source last *processed the data* for this dataset.

        `data_processed` is preferred over `modified`: the catalogue's own
        metadata says `modified` also moves on a pure metadata edit, which
        would make us report a new publication date for a dataset whose
        figures did not change. Returns None rather than guessing when the
        field is absent or unparseable.
        """
        metas = self._catalog_entry(dataset_id).get("metas", {}).get("default", {})
        raw = metas.get("data_processed")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(str(raw)).date()
        except ValueError:
            logger.warning(
                "Unparseable data_processed for %s: %r — leaving the publication "
                "date unset rather than inventing one",
                dataset_id,
                raw,
            )
            return None

    def assert_schema(self, dataset_id: str, expected_fields: list[str]) -> None:
        """Abort ingestion if the dataset no longer exposes what we read.

        This is the guard that makes a silent upstream schema change
        impossible to miss — the project's most critical known blind spot.
        """
        present = self.field_names(dataset_id)
        missing = [name for name in expected_fields if name not in present]
        if missing:
            raise SourceSchemaMismatchError(dataset_id, missing, present)
        logger.info(
            "Schema check passed for %s (%d expected fields present)",
            dataset_id,
            len(expected_fields),
        )

    def export_all(self, dataset_id: str, select: list[str]) -> list[dict[str, Any]]:
        """Pull an entire dataset. See the module docstring on why /exports."""
        response = self._get(
            f"{self._base_url}/catalog/datasets/{dataset_id}/exports/json",
            params={"select": ",".join(select)},
        )
        rows = response.json()
        if not isinstance(rows, list):
            raise SourceUnavailableError(
                f"Expected a JSON array from {dataset_id}, got {type(rows).__name__}"
            )
        logger.info("Fetched %d rows from %s", len(rows), dataset_id)
        return rows

    def close(self) -> None:
        self._client.close()
