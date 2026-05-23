"""
In-memory rate limiting helpers.

Важно: это процессный лимитер (per-instance). Для multi-instance продакшена
лучше вынести состояние в Redis/API gateway.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


class SlidingWindowLimiter:
    """Simple thread-safe sliding-window limiter."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str, *, limit: int, window_seconds: int) -> bool:
        if limit <= 0:
            return True
        now = time.time()
        edge = now - window_seconds
        with self._lock:
            q = self._events[key]
            while q and q[0] < edge:
                q.popleft()
            if len(q) >= limit:
                return False
            q.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


_global_rate_limiter = SlidingWindowLimiter()
_signup_ip_limiter = SlidingWindowLimiter()


def global_rate_limiter() -> SlidingWindowLimiter:
    return _global_rate_limiter


def signup_ip_limiter() -> SlidingWindowLimiter:
    return _signup_ip_limiter


def reset_limiters_for_tests() -> None:
    _global_rate_limiter.reset()
    _signup_ip_limiter.reset()
