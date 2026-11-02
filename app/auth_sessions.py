"""In-memory session registry for local single-process ERP testing."""

from threading import RLock
from time import time

from .security import create_session_token, verify_session_token


_lock = RLock()
_sessions: dict[str, dict] = {}


def issue_session(user_id: int, signing_key: str,
                  ttl_seconds: int = 8 * 60 * 60) -> str:
    # Opportunistically remove expired in-memory sessions before adding a new one.
    clear_expired_sessions()

    if not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Invalid user id.")

    token = create_session_token(str(user_id), signing_key, ttl_seconds)
    claims = verify_session_token(token, signing_key)
    if claims is None:
        raise ValueError("Could not validate newly created session.")

    with _lock:
        _sessions[claims["nonce"]] = {
            "user_id": user_id,
            "expires_at": claims["exp"],
        }
    return token


def get_session_user_id(token: str | None, signing_key: str) -> int | None:
    claims = verify_session_token(token, signing_key)
    if claims is None:
        return None

    try:
        user_id = int(claims["sub"])
    except (KeyError, TypeError, ValueError):
        return None

    with _lock:
        record = _sessions.get(claims["nonce"])
        if not record:
            return None
        if record["user_id"] != user_id or record["expires_at"] <= int(time()):
            _sessions.pop(claims["nonce"], None)
            return None

    return user_id


def revoke_session(token: str | None, signing_key: str) -> bool:
    claims = verify_session_token(token, signing_key)
    if claims is None:
        return False

    with _lock:
        return _sessions.pop(claims["nonce"], None) is not None


def clear_expired_sessions() -> int:
    now = int(time())
    with _lock:
        expired = [
            nonce for nonce, record in _sessions.items()
            if record["expires_at"] <= now
        ]
        for nonce in expired:
            _sessions.pop(nonce, None)
    return len(expired)
