"""Login and logout routes for local ERP authentication."""

import hmac
import secrets
from urllib.parse import parse_qs

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from .auth_service import authenticate_user
from .auth_sessions import issue_session, get_session_user_id, revoke_session
from .config import get_settings
from .login_throttle import (
    get_retry_after,
    record_login_failure,
    record_login_success,
)


router = APIRouter()
settings = get_settings()
templates = Jinja2Templates(directory=str(__import__("pathlib").Path(__file__).resolve().parent / "templates"))

SESSION_COOKIE = "are_erp_session"
CSRF_COOKIE = "are_erp_csrf"
COOKIE_SECURE = settings.app_environment.lower() != "development"


def _csrf_token() -> str:
    return secrets.token_urlsafe(32)


def _render_login(request: Request, csrf: str, error: str | None = None,
                  status_code: int = 200) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"csrf_token": csrf, "error": error},
        status_code=status_code,
    )
    response.set_cookie(
        CSRF_COOKIE, csrf, httponly=True, secure=COOKIE_SECURE,
        samesite="lax", path="/", max_age=600,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


async def _read_form(request: Request) -> dict[str, str] | None:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/x-www-form-urlencoded":
        return None
    body = await request.body()
    if len(body) > 16384:
        return None
    try:
        parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=10)
    except (UnicodeDecodeError, ValueError):
        return None
    return {key: values[0] for key, values in parsed.items() if values}


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    csrf = _csrf_token()
    return _render_login(request, csrf)


@router.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request):
    form = await _read_form(request)
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    csrf_form = form.get("csrf_token", "") if form else ""

    if not csrf_cookie or not csrf_form or not hmac.compare_digest(csrf_cookie, csrf_form):
        response = _render_login(
            request, _csrf_token(),
            "Session check failed. Please try again.", 400,
        )
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    signing_key = settings.session_signing_key
    if len(signing_key) < 32:
        return _render_login(
            request, _csrf_token(),
            "Login is unavailable because session security is not configured.", 503,
        )

    username = form.get("username", "") if form else ""
    password = form.get("password", "") if form else ""
    client_ip = request.client.host if request.client else "unknown"

    retry_after = get_retry_after(client_ip, username)
    if retry_after:
        response = _render_login(
            request, _csrf_token(),
            "Too many sign-in attempts. Please wait before trying again.",
            429,
        )
        response.headers["Retry-After"] = str(retry_after)
        return response

    user = authenticate_user(username, password)

    if not user:
        record_login_failure(client_ip, username)
        return _render_login(
            request, _csrf_token(),
            "Sign-in failed. Check your credentials or contact the system administrator.",
            401,
        )

    record_login_success(client_ip, username)

    # Replace any previous browser session only after successful authentication.
    previous_token = request.cookies.get(SESSION_COOKIE)
    if previous_token:
        revoke_session(previous_token, signing_key)

    token = issue_session(user["id"], signing_key)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE, token, httponly=True, secure=COOKIE_SECURE,
        samesite="lax", path="/", max_age=28800,
    )
    logout_csrf = _csrf_token()
    response.set_cookie(
        CSRF_COOKIE, logout_csrf, httponly=True, secure=COOKIE_SECURE,
        samesite="lax", path="/", max_age=28800,
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@router.post("/logout")
async def logout_submit(request: Request):
    form = await _read_form(request)
    csrf_cookie = request.cookies.get(CSRF_COOKIE, "")
    csrf_form = form.get("csrf_token", "") if form else ""

    if not csrf_cookie or not csrf_form or not hmac.compare_digest(csrf_cookie, csrf_form):
        return HTMLResponse("CSRF validation failed.", status_code=400)

    token = request.cookies.get(SESSION_COOKIE)
    if token:
        revoke_session(token, settings.session_signing_key)

    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    logout_csrf = _csrf_token()
    response.set_cookie(
        CSRF_COOKIE, logout_csrf, httponly=True, secure=COOKIE_SECURE,
        samesite="lax", path="/", max_age=28800,
    )
    response.headers["Cache-Control"] = "no-store"
    return response

