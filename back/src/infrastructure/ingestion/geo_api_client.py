"""Synchronous client for the official geo.api.gouv.fr commune reference."""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from .errors import SourceUnavailableError

logger = logging.getLogger(__name__)

DEFAULT_GEO_API_BASE_URL = "https://geo.api.gouv.fr"


class GeoApiClient:
    def __init__(
        self,
        base_url: str = DEFAULT_GEO_API_BASE_URL,
        timeout: float = 180.0,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": "etablissements-en-clair/0.1"},
            follow_redirects=True,
        )

    @property
    def source_page_url(self) -> str:
        return f"{self._base_url}/decoupage-administratif/communes"

    def fetch_communes(self) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                response = self._client.get(
                    f"{self._base_url}/communes",
                    params={
                        "fields": "nom,code,codesPostaux,codeDepartement,centre",
                        "format": "json",
                    },
                )
                response.raise_for_status()
                try:
                    payload: Any = response.json()
                except ValueError as error:
                    raise SourceUnavailableError(
                        "The commune API response is not a JSON array "
                        "because it is not valid JSON"
                    ) from error
                if not isinstance(payload, list):
                    raise SourceUnavailableError(
                        "The commune API response is not a JSON array"
                    )
                return payload
            except (httpx.HTTPError, ValueError, SourceUnavailableError) as error:
                last_error = error
                logger.warning(
                    "Commune source request failed (attempt %d/%d): %s",
                    attempt + 1,
                    self._max_retries,
                    error,
                )
                if attempt < self._max_retries - 1:
                    time.sleep(self._backoff_seconds * (2**attempt))
        raise SourceUnavailableError(
            f"Commune source failed after {self._max_retries} attempts: {last_error}"
        )

    def close(self) -> None:
        self._client.close()
