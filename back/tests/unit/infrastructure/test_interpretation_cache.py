"""Unit tests for the bounded process-local interpretation cache."""

from __future__ import annotations

from math import inf, nan
from threading import Event, Thread

import pytest

from src.application.interpret_search import InterpretedSearch
from src.infrastructure.llm.interpretation_cache import InMemoryInterpretationCache


class ControlledClock:
    def __init__(self, value: float = 0.0) -> None:
        self.value = value
        self.calls = 0

    def __call__(self) -> float:
        self.calls += 1
        return self.value


def test_entry_is_live_before_ttl_and_expired_at_the_exact_boundary() -> None:
    clock = ControlledClock(10.0)
    cache = InMemoryInterpretationCache(2, 5.0, clock)
    value = InterpretedSearch(text_query="Lycée Jean Moulin")

    cache.put("key", value)
    clock.value = 14.999999
    assert cache.get("key") is value
    clock.value = 15.0
    assert cache.get("key") is None


def test_get_promotes_lru_and_put_evicts_the_least_recent_entry() -> None:
    cache = InMemoryInterpretationCache(2, 60)
    first = InterpretedSearch(text_query="first")
    second = InterpretedSearch(text_query="second")
    third = InterpretedSearch(text_query="third")

    cache.put("first", first)
    cache.put("second", second)
    assert cache.get("first") is first
    cache.put("third", third)

    assert cache.get("second") is None
    assert cache.get("first") is first
    assert cache.get("third") is third


def test_replacement_promotes_entry_and_refreshes_its_ttl() -> None:
    clock = ControlledClock()
    cache = InMemoryInterpretationCache(2, 5, clock)
    old = InterpretedSearch(text_query="old")
    replacement = InterpretedSearch(text_query="replacement")

    cache.put("same", old)
    cache.put("other", InterpretedSearch(text_query="other"))
    clock.value = 4.0
    cache.put("same", replacement)
    cache.put("new", InterpretedSearch(text_query="new"))

    assert cache.get("other") is None
    clock.value = 5.0
    assert cache.get("same") is replacement
    clock.value = 9.0
    assert cache.get("same") is None


@pytest.mark.parametrize("max_entries", [0, -1, -100])
def test_non_positive_capacity_is_rejected(max_entries: int) -> None:
    with pytest.raises(ValueError, match="max_entries must be positive"):
        InMemoryInterpretationCache(max_entries, 1)


@pytest.mark.parametrize("ttl_seconds", [0.0, -1.0, nan, inf, -inf])
def test_non_positive_or_non_finite_ttl_is_rejected(ttl_seconds: float) -> None:
    with pytest.raises(ValueError, match="ttl_seconds must be finite and positive"):
        InMemoryInterpretationCache(1, ttl_seconds)


def test_clock_is_sampled_while_the_cache_lock_excludes_another_operation() -> None:
    clock_entered = Event()
    release_clock = Event()
    second_started = Event()
    second_finished = Event()
    calls = 0

    def blocking_clock() -> float:
        nonlocal calls
        calls += 1
        if calls == 1:
            clock_entered.set()
            assert release_clock.wait(timeout=1)
        return 0.0

    cache = InMemoryInterpretationCache(2, 60, blocking_clock)

    first = Thread(target=lambda: cache.get("missing"))

    def write_second() -> None:
        second_started.set()
        cache.put("second", InterpretedSearch(text_query="second"))
        second_finished.set()

    second = Thread(target=write_second)
    first.start()
    assert clock_entered.wait(timeout=1)
    second.start()
    assert second_started.wait(timeout=1)
    assert not second_finished.wait(timeout=0.05)
    release_clock.set()
    first.join(timeout=1)
    second.join(timeout=1)

    assert not first.is_alive()
    assert not second.is_alive()
    assert second_finished.is_set()
