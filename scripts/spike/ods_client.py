"""Minimal Opendatasoft Explore API v2.1 client for the Phase 0 spike.

Disposable code — see README.md in this directory. The production adapters
(Phase 1, DATA-3/4) must be written independently under
back/src/infrastructure/ingestion/, behind a port defined in the domain.

Design notes worth carrying over to Phase 1:
- /records is capped at 100 rows per page and ~10 000 rows of offset, so it
  cannot page a full dataset. /exports/json has no offset ceiling and is the
  only viable way to pull a whole dataset in one go.
- `select` must be used to restrict columns; the directory dataset has 71
  fields and pulling all of them is wasteful.
"""

from __future__ import annotations

import gzip
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

BASE_URL = "https://data.education.gouv.fr/api/explore/v2.1/catalog/datasets"
OUTPUT_DIR = Path(__file__).parent / "output"

# Dataset identifiers confirmed live against the catalogue on 2026-08-15.
# NOTE: docs/03_Glossaire_Metier.md did not list the IVAC dataset id, and the
# "old version" IVAL ids are needed for SPIKE-2. Recorded here as discovered.
DATASET_DIRECTORY = "fr-en-annuaire-education"
DATASET_IVAC = "fr-en-indicateurs-valeur-ajoutee-colleges"
DATASET_IVAL_GT = "fr-en-indicateurs-de-resultat-des-lycees-gt_v2"
DATASET_IVAL_PRO = "fr-en-indicateurs-de-resultat-des-lycees-pro_v2"
DATASET_IVAL_GT_LEGACY = (
    "fr-en-indicateurs-de-resultat-des-lycees-denseignement-general-et-technologique"
)
DATASET_IVAL_PRO_LEGACY = (
    "fr-en-indicateurs-de-resultat-des-lycees-denseignement-professionnels"
)

USER_AGENT = "etablissements-en-clair-phase0-spike/0.1 (technical spike)"
MAX_RETRIES = 4
TIMEOUT_SECONDS = 180


class SpikeAbort(RuntimeError):
    """Raised when an assumption fails. The spike must fail loudly, never guess."""


def _decode(payload: bytes) -> str:
    """The catalogue metadata endpoint returns gzip even when the request asks
    for `Accept-Encoding: identity`, while /records and /exports honour it.
    Sniff the gzip magic bytes rather than trusting the response headers."""
    if payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    return payload.decode("utf-8")


def _request(url: str) -> Any:
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(_decode(response.read()))
        except urllib.error.HTTPError as error:
            # 429/5xx are worth retrying; a 400 means our query is wrong and
            # retrying it would just hide the mistake.
            if error.code not in (429, 500, 502, 503, 504):
                detail = _decode(error.read())[:400]
                raise SpikeAbort(f"HTTP {error.code} for {url}\n{detail}") from error
            last_error = error
        except (urllib.error.URLError, TimeoutError) as error:
            last_error = error
        backoff = 2 ** attempt
        print(f"  ... retry {attempt + 1}/{MAX_RETRIES} in {backoff}s ({last_error})")
        time.sleep(backoff)
    raise SpikeAbort(f"Giving up on {url} after {MAX_RETRIES} attempts: {last_error}")


def dataset_metadata(dataset_id: str) -> dict[str, Any]:
    return _request(f"{BASE_URL}/{dataset_id}")


def field_names(dataset_id: str) -> list[str]:
    return [f["name"] for f in dataset_metadata(dataset_id).get("fields", [])]


def record_count(dataset_id: str, where: str | None = None) -> int:
    params = {"limit": 0}
    if where:
        params["where"] = where
    url = f"{BASE_URL}/{dataset_id}/records?" + urllib.parse.urlencode(params)
    return _request(url)["total_count"]


def aggregate(
    dataset_id: str, select: str, group_by: str, order_by: str = "", limit: int = 100
) -> list[dict[str, Any]]:
    params = {"select": select, "group_by": group_by, "limit": limit}
    if order_by:
        params["order_by"] = order_by
    url = f"{BASE_URL}/{dataset_id}/records?" + urllib.parse.urlencode(params)
    return _request(url)["results"]


def export_all(
    dataset_id: str, select: str, where: str | None = None, cache: bool = True
) -> list[dict[str, Any]]:
    """Pull a whole dataset via /exports/json (no offset ceiling).

    Results are cached on disk so re-running a spike script does not hammer a
    public government API.
    """
    OUTPUT_DIR.mkdir(exist_ok=True)
    cache_key = f"{dataset_id}__{abs(hash((select, where)))}.json"
    cache_path = OUTPUT_DIR / cache_key
    if cache and cache_path.exists():
        print(f"  (cached) {dataset_id}")
        return json.loads(cache_path.read_text(encoding="utf-8"))

    params = {"select": select}
    if where:
        params["where"] = where
    url = f"{BASE_URL}/{dataset_id}/exports/json?" + urllib.parse.urlencode(params)
    print(f"  fetching {dataset_id} ...")
    started = time.monotonic()
    rows = _request(url)
    elapsed = time.monotonic() - started
    if not isinstance(rows, list):
        raise SpikeAbort(f"Expected a JSON array from {dataset_id}, got {type(rows)}")
    print(f"  -> {len(rows)} rows in {elapsed:.1f}s")
    if cache:
        cache_path.write_text(json.dumps(rows), encoding="utf-8")
    return rows


def check_fields_present(dataset_id: str, expected: list[str]) -> None:
    """Abort if the source schema no longer matches what this spike assumes.

    This is the spike-level equivalent of the schema-mismatch detection that
    Phase 1 (DATA-5) must implement properly with alerting. Here it only has
    to stop a human from reading a number computed on the wrong columns.
    """
    actual = set(field_names(dataset_id))
    missing = [name for name in expected if name not in actual]
    if missing:
        raise SpikeAbort(
            f"Schema mismatch on {dataset_id}: missing field(s) {missing}.\n"
            "The source dataset changed shape. Do not interpret any result "
            "from this run — update the spike and re-read the dataset schema."
        )
    print(f"  schema OK: {dataset_id} ({len(expected)} expected fields present)")


def write_report(name: str, lines: list[str]) -> Path:
    OUTPUT_DIR.mkdir(exist_ok=True)
    path = OUTPUT_DIR / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReport written to {path}")
    return path


def fail(message: str) -> None:
    print(f"\nSPIKE ABORTED: {message}", file=sys.stderr)
    sys.exit(1)
