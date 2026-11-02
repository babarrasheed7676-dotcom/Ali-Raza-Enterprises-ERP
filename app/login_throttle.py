"""Process-local login throttling. No database access."""
from collections import deque
from hashlib import sha256
from threading import RLock
from time import monotonic

_WINDOW = 15 * 60
_PAIR_LIMIT = 5
_IP_LIMIT = 30
_MAX_BUCKETS = 10000

_lock = RLock()
_events: dict[tuple[str, str], deque[float]] = {}


def _keys(ip: str, username: str):
    identity = sha256(username.strip().casefold().encode("utf-8")).hexdigest()
    return (("ip", ip), ("pair", f"{ip}:{identity}"))


def _prune(now: float) -> None:
    expired = [
        key for key, events in _events.items()
        if not events or now - events[0] >= _WINDOW
    ]
    for key in expired:
        _events.pop(key, None)

    while len(_events) > _MAX_BUCKETS:
        _events.pop(next(iter(_events)))


def get_retry_after(ip: str, username: str) -> int:
    now = monotonic()
    limits = ((_keys(ip, username)[0], _IP_LIMIT),
              (_keys(ip, username)[1], _PAIR_LIMIT))

    with _lock:
        _prune(now)
        retry = 0
        for key, limit in limits:
            events = _events.get(key)
            if events and len(events) >= limit:
                retry = max(retry, int(_WINDOW - (now - events[0])) + 1)
        return max(0, retry)


def record_login_failure(ip: str, username: str) -> None:
    now = monotonic()
    with _lock:
        _prune(now)
        for key in _keys(ip, username):
            events = _events.setdefault(key, deque())
            events.append(now)
        _prune(now)


def record_login_success(ip: str, username: str) -> None:
    pair_key = _keys(ip, username)[1]
    with _lock:
        _events.pop(pair_key, None)
