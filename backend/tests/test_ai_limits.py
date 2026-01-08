from __future__ import annotations

import pytest

from app.services.limits import ConcurrencyLimitExceededError, InMemoryConcurrencyLimiter


def test_concurrency_limiter_allows_only_configured_slots():
    limiter = InMemoryConcurrencyLimiter(max_concurrent=1)

    with limiter.acquire(1):
        with pytest.raises(ConcurrencyLimitExceededError):
            with limiter.acquire(1):
                pass

    # Slot released
    with limiter.acquire(1):
        pass

