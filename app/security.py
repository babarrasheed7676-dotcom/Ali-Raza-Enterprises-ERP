
"""Read-only ERP security foundation: password hashing and signed sessions."""

import base64
import hashlib
import hmac
import secrets
import time


def hash_password(password: str) -> str:
    """Generate a new scrypt password hash."""
    if not isinstance(password, str) or not password:
        raise ValueError("Password cannot be empty.")
    if len(password) > 1024:
        raise ValueError("Password is too long.")

    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    """Verify only this module's scrypt format; reject unknown formats."""
    if not isinstance(password, str) or not isinstance(stored_hash, str):
        return False
    if not password or len(password) > 1024:
        return False

    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "scrypt":
        return False

    try:
        salt = bytes.fromhex(parts[1])
        expected = bytes.fromhex(parts[2])
        if len(salt) != 16 or len(expected) != 32:
            return False

        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=2**14,
            r=8,
            p=1,
            dklen=32,
        )
    except (ValueError, MemoryError):
        return False

    return hmac.compare_digest(actual, expected)


def create_session_token(
    subject: str,
    signing_key: str,
    ttl_seconds: int = 8 * 60 * 60,
) -> str:
    """Create an HMAC-signed, time-limited session token."""
    if not subject or len(subject) > 200:
        raise ValueError("Invalid session subject.")
    if not isinstance(signing_key, str) or len(signing_key) < 32:
        raise ValueError("Signing key must be at least 32 characters.")
    if not 60 <= ttl_seconds <= 86400:
        raise ValueError("Session lifetime must be 1 minute to 24 hours.")

    issued = int(time.time())
    expires = issued + ttl_seconds
    nonce = secrets.token_urlsafe(16)
    payload = f"{subject}|{issued}|{expires}|{nonce}"
    signature = hmac.new(
        signing_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    encoded = base64.urlsafe_b64encode(
        payload.encode("utf-8")
    ).decode("ascii").rstrip("=")
    return f"{encoded}.{signature}"


def verify_session_token(
    token: str | None,
    signing_key: str,
) -> dict | None:
    """Return verified session claims or None for invalid/expired tokens."""
    if not isinstance(token, str) or not isinstance(signing_key, str):
        return None
    if len(signing_key) < 32:
        return None

    try:
        encoded, supplied_signature = token.split(".", 1)
        encoded += "=" * (-len(encoded) % 4)
        payload = base64.urlsafe_b64decode(encoded).decode("utf-8")
        subject, issued_text, expires_text, nonce = payload.split("|", 3)
        issued = int(issued_text)
        expires = int(expires_text)
    except (ValueError, UnicodeDecodeError):
        return None

    expected_signature = hmac.new(
        signing_key.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_signature, supplied_signature):
        return None

    now = int(time.time())
    if not subject or not nonce or issued > now + 60 or expires <= now:
        return None
    if expires <= issued or expires - issued > 86400:
        return None

    return {"sub": subject, "iat": issued, "exp": expires, "nonce": nonce}
