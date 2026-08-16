"""Tests for interpretation cache versioning at the application boundary."""

from __future__ import annotations

from datetime import UTC, date, datetime

from src.application.interpret_search import SourceBackedInterpretationVersion
from src.domain.source_reference import SourceReference


def _reference(
    dataset_id: str,
    *,
    synchronised_at: datetime | None = None,
    published_at: date | None = None,
) -> SourceReference:
    return SourceReference(
        dataset_id=dataset_id,
        url=f"https://example.invalid/{dataset_id}",
        last_synchronised_at=synchronised_at or datetime(2026, 8, 15, 12, tzinfo=UTC),
        source_published_at=published_at,
    )


class MutableSourceReader:
    def __init__(self, references: dict[str, SourceReference]) -> None:
        self.references = references

    def all_by_dataset_id(self) -> dict[str, SourceReference]:
        return self.references


def test_version_token_is_stable_across_source_mapping_order() -> None:
    directory = _reference("directory")
    communes = _reference("communes")
    reader = MutableSourceReader({"directory": directory, "communes": communes})
    provider = SourceBackedInterpretationVersion(reader, "editorial-v1")

    first = provider.current_version()
    reader.references = {"communes": communes, "directory": directory}

    assert provider.current_version() == first


def test_version_token_changes_with_sync_publication_or_content_version() -> None:
    initial = _reference(
        "directory",
        published_at=date(2026, 8, 14),
    )
    reader = MutableSourceReader({"directory": initial})
    provider = SourceBackedInterpretationVersion(reader, "editorial-v1")
    original = provider.current_version()

    reader.references = {
        "directory": _reference(
            "directory",
            synchronised_at=datetime(2026, 8, 16, 12, tzinfo=UTC),
            published_at=date(2026, 8, 14),
        )
    }
    after_sync = provider.current_version()
    reader.references = {
        "directory": _reference(
            "directory",
            synchronised_at=datetime(2026, 8, 16, 12, tzinfo=UTC),
            published_at=date(2026, 8, 15),
        )
    }
    after_publication = provider.current_version()
    after_content = SourceBackedInterpretationVersion(
        reader, "editorial-v2"
    ).current_version()

    assert len({original, after_sync, after_publication, after_content}) == 4
