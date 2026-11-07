"""Server-side authentication and fail-closed permission checks."""

from fastapi import HTTPException, Request

from .auth_sessions import get_session_user_id
from .config import get_settings
from .db import get_connection

SESSION_COOKIE = "are_erp_session"


def get_current_user(request: Request) -> dict:
    settings = get_settings()
    if len(settings.session_signing_key) < 32:
        raise HTTPException(status_code=503, detail="Authentication security is not configured.")

    token = request.cookies.get(SESSION_COOKIE)
    user_id = get_session_user_id(token, settings.session_signing_key)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Please sign in.", headers={"WWW-Authenticate": "Cookie"})

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, company_id, username, full_name, is_active
                FROM core.users
                WHERE id = %s
                """,
                (user_id,),
            )
            user = cur.fetchone()

    if not user or user["is_active"] is not True:
        raise HTTPException(status_code=401, detail="Session is not valid. Please sign in again.")

    return user


def require_permission_for_user(user: dict, permission_code: str) -> dict:
    """Check one permission for an already authenticated user."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT 1
                FROM core.user_roles ur
                JOIN core.roles r
                  ON r.id = ur.role_id
                 AND r.company_id = %s
                 AND r.is_active IS TRUE
                JOIN core.role_permissions rp ON rp.role_id = r.id
                JOIN core.permissions p
                  ON p.id = rp.permission_id
                 AND p.code = %s
                 AND p.is_active IS TRUE
                WHERE ur.user_id = %s
                LIMIT 1
                """,
                (user["company_id"], permission_code, user["id"]),
            )
            allowed = cur.fetchone()

    if not allowed:
        raise HTTPException(
            status_code=403,
            detail="Access denied: required permission is not assigned.",
        )

    return user


def require_permission(permission_code: str):
    """Require an active permission granted through an active company role."""

    def dependency(request: Request) -> dict:
        user = get_current_user(request)
        return require_permission_for_user(user, permission_code)

    return dependency
