"""Bounded process-local cache for validated search interpretations."""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from math import isfinite
from threading import Lock
from time import monotonic

from src.application.interpret_search import InterpretedSearch


@dataclass(frozen=True, slots=True)
class _Entry:
    expires_at: float
    value: InterpretedSearch


class InMemoryInterpretationCache:
    """Thread-safe TTL/LRU cache; it never contains factual search results."""

    def __init__(
        self,
        max_entries: int,
        ttl_seconds: float,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if max_entries < 1:
            raise ValueError("max_entries must be positive")
        if not isfinite(ttl_seconds) or ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be finite and positive")
        self._max_entries = max_entries
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: OrderedDict[str, _Entry] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> InterpretedSearch | None:
        with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return entry.value

    def put(self, key: str, value: InterpretedSearch) -> None:
        with self._lock:
            entry = _Entry(
                expires_at=self._clock() + self._ttl_seconds,
                value=value,
            )
            self._entries[key] = entry
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
