from .db import get_user_for_auth
from .security import verify_password


# Valid-format dummy hash: used only to perform equivalent Scrypt work.
_DUMMY_PASSWORD_HASH = (
    "scrypt$" + ("00" * 16) + "$" + ("00" * 32)
)


def _has_supported_hash_format(stored_hash: object) -> bool:
    if not isinstance(stored_hash, str):
        return False
    parts = stored_hash.split("$")
    if len(parts) != 3 or parts[0] != "scrypt":
        return False
    try:
        return len(bytes.fromhex(parts[1])) == 16 and len(
            bytes.fromhex(parts[2])
        ) == 32
    except ValueError:
        return False


def authenticate_user(username: str, password: str) -> dict | None:
    """Authenticate active users without exposing username timing differences."""
    if not isinstance(username, str) or not isinstance(password, str):
        return None

    if not username.strip() or not password or len(password) > 1024:
        return None

    user = get_user_for_auth(username.strip())

    if not user or user.get("is_active") is not True:
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    stored_hash = user.get("password_hash")

    if not _has_supported_hash_format(stored_hash):
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None

    if not verify_password(password, stored_hash):
        return None

    # Never return the stored password hash to the caller.
    return {
        "id": user["id"],
        "company_id": user["company_id"],
        "username": user["username"],
        "full_name": user["full_name"],
    }