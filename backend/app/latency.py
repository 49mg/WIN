"""Response times of the recommend endpoints (WIN-40): the last 500 per kind, in memory.

A kind is mode (titles / vibe) x source (engine / ai: the AI re-ranking actually ran).
Memory only, like the rate limiter: enough for one server; a restart resets it.
"""

import threading
from collections import deque

KEEP = 500
_times: dict[str, deque[float]] = {}
_lock = threading.Lock()


def record(kind: str, ms: float) -> None:
    with _lock:
        _times.setdefault(kind, deque(maxlen=KEEP)).append(ms)


def _pct(sorted_ms: list[float], p: float) -> float:
    return sorted_ms[min(len(sorted_ms) - 1, int(p * len(sorted_ms)))]


def summary() -> list[dict]:
    with _lock:
        snap = {k: sorted(v) for k, v in _times.items() if v}
    return [{"kind": k, "count": len(v), "p50_ms": round(_pct(v, 0.5)),
             "p95_ms": round(_pct(v, 0.95))} for k, v in sorted(snap.items())]
