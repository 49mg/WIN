"""A small in-memory rate limiter: at most N requests per key in a sliding 60-second window.

Keys are a user id or, for anonymous callers, an IP address. Memory only, per API process:
enough for one server; a restart resets the windows.
"""

import threading
import time
from collections import deque

WINDOW = 60.0


class RateLimiter:
    def __init__(self):
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int) -> tuple[bool, int]:
        """Record a request; returns (allowed, seconds until a slot frees up)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] > WINDOW:
                hits.popleft()
            if len(hits) >= limit:
                return False, int(WINDOW - (now - hits[0])) + 1
            hits.append(now)
            if len(self._hits) > 10_000:  # forget idle keys so memory stays small
                for k in [k for k, h in self._hits.items() if not h or now - h[-1] > WINDOW]:
                    del self._hits[k]
            return True, 0


limiter = RateLimiter()
