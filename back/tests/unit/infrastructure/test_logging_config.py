"""OPS-3 — `configure_logging` and `JsonFormatter`.

`configure_logging` deliberately replaces every handler on the root logger
(see its docstring), which means it also removes pytest's own `caplog`
handler. So these tests read the process's actual stdout/stderr via `capsys`
rather than `caplog` — that is the only way to observe what a deployment
would really see — and each test restores the root logger's prior state
afterwards so it does not leak into any other test in the same session.
"""

from __future__ import annotations

import json
import logging

import pytest

from src.infrastructure.logging_config import configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logger() -> None:
    root = logging.getLogger()
    previous_handlers = list(root.handlers)
    previous_level = root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in previous_handlers:
        root.addHandler(handler)
    root.setLevel(previous_level)


def test_json_format_emits_parseable_json_with_core_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="INFO", log_format="json")

    logging.getLogger("test.logger").info("ingestion complete")

    line = capsys.readouterr().err.strip()
    payload = json.loads(line)  # raises if this is not valid JSON

    assert payload["message"] == "ingestion complete"
    assert payload["logger"] == "test.logger"
    assert payload["level"] == "INFO"
    assert payload["timestamp"]


def test_extra_fields_pass_through_to_the_json_output(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The ingestion paths pass dataset_id/uai/year via `extra=` — this is the
    entire point of structured logging here, so it must survive to output."""
    configure_logging(level="INFO", log_format="json")

    logging.getLogger("test.logger").info(
        "row skipped: no directory match",
        extra={"dataset_id": "ivac", "uai": "0750001A", "year": 2025},
    )

    payload = json.loads(capsys.readouterr().err.strip())

    assert payload["dataset_id"] == "ivac"
    assert payload["uai"] == "0750001A"
    assert payload["year"] == 2025


def test_an_exception_is_rendered_as_one_string_field_not_split_apart(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="ERROR", log_format="json")
    logger = logging.getLogger("test.logger")

    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("ingestion failed")

    payload = json.loads(capsys.readouterr().err.strip())

    assert isinstance(payload["exception"], str)
    assert "Traceback" in payload["exception"]
    assert "ValueError: boom" in payload["exception"]
    # A traceback is read by a human — it must not be split across fields.
    assert "exc_info" not in payload
    assert "exc_text" not in payload


def test_text_format_does_not_emit_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(level="INFO", log_format="text")

    logging.getLogger("test.logger").info("ingestion complete")

    line = capsys.readouterr().err.strip()
    with pytest.raises(json.JSONDecodeError):
        json.loads(line)
    assert "ingestion complete" in line


def test_configuring_twice_does_not_duplicate_log_lines(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Both the API lifespan and the ingestion CLI may call this in one
    process — calling it a second time must replace the handler, not add a
    second one, or every line would be emitted twice."""
    configure_logging(level="INFO", log_format="text")
    configure_logging(level="INFO", log_format="text")

    assert len(logging.getLogger().handlers) == 1

    logging.getLogger("test.logger").info("single line please")

    lines = [line for line in capsys.readouterr().err.splitlines() if line]
    assert len(lines) == 1
