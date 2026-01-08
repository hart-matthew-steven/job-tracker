from __future__ import annotations

import uuid
from collections import defaultdict
from contextlib import contextmanager
from threading import Lock


class ConcurrencyLimitExceededError(Exception):
    pass


class InMemoryConcurrencyLimiter:
    def __init__(self, max_concurrent: int) -> None:
        self.max_concurrent = max_concurrent
        self._inflight: defaultdict[int, int] = defaultdict(int)
        self._lock = Lock()

    @contextmanager
    def acquire(self, user_id: int):
        with self._lock:
            current = self._inflight[user_id]
            if current >= self.max_concurrent:
                raise ConcurrencyLimitExceededError("Too many concurrent AI requests.")
            self._inflight[user_id] = current + 1
        try:
            yield
        finally:
            with self._lock:
                self._inflight[user_id] = max(0, self._inflight[user_id] - 1)
                if self._inflight[user_id] == 0:
                    del self._inflight[user_id]


def generate_correlation_id(existing: str | None = None) -> str:
    if existing:
        return existing.strip()
    return uuid.uuid4().hex


