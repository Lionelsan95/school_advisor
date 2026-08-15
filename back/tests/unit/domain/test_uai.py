"""Unit tests for the UAI value object.

The format `^[0-9]{7}[A-Z]$` was verified against all 67 896 directory
records during the Phase 0 spike (see `src/domain/uai.py` docstring); these
tests protect that invariant and the "never repair, only reject" rule.
"""

from __future__ import annotations

import pytest

from src.domain.uai import InvalidUaiError, is_valid_uai, parse_uai


@pytest.mark.parametrize(
    "raw",
    [
        "0750001A",
        "9760001Z",  # Mayotte-prefixed UAI, referenced by the spike (976xxxx)
        "0010001B",
    ],
)
def test_parse_uai_accepts_well_formed_identifiers(raw: str) -> None:
    assert parse_uai(raw) == raw


def test_parse_uai_normalises_lowercase_input() -> None:
    assert parse_uai("0750001a") == "0750001A"


def test_parse_uai_strips_surrounding_whitespace() -> None:
    assert parse_uai("  0750001A  ") == "0750001A"


def test_parse_uai_rejects_none() -> None:
    with pytest.raises(InvalidUaiError):
        parse_uai(None)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "075000A",  # only 6 digits before the letter
        "07500001A",  # 8 digits before the letter
        "0750001AA",  # two trailing letters
        "0750001a1",  # trailing digit instead of a letter
        "A750001A",  # letter where a digit is expected
        "0750001",  # missing the trailing letter entirely
        "075-001A",  # punctuation
    ],
)
def test_parse_uai_rejects_malformed_identifiers(raw: str) -> None:
    with pytest.raises(InvalidUaiError):
        parse_uai(raw)


def test_parse_uai_never_repairs_a_malformed_identifier() -> None:
    # A close-but-wrong UAI must be rejected outright, not "fixed" to the
    # nearest valid shape — ingestion must surface the problem, not paper
    # over it.
    with pytest.raises(InvalidUaiError):
        parse_uai("075001A")  # one digit short of the required seven


def test_is_valid_uai_true_for_a_well_formed_identifier() -> None:
    assert is_valid_uai("0750001A") is True


@pytest.mark.parametrize("raw", [None, "", "not-a-uai", "0750001AA"])
def test_is_valid_uai_false_without_raising(raw: str | None) -> None:
    assert is_valid_uai(raw) is False
