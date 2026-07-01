"""Double-submit-cookie CSRF protection for authenticated mutations.

The frontend reads the non-HttpOnly ``capitalos_csrf`` cookie and echoes it in
the ``X-CSRF-Token`` header on unsafe requests. We only enforce this when a
session cookie is present (i.e. the request is acting on behalf of a logged-in
user), which is where CSRF actually matters.
"""

from __future__ import annotations

import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings

CSRF_COOKIE_NAME = "capitalos_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
# Session-bootstrap endpoints that establish (rather than act on) a session.
# The CSRF token is issued *by* these responses, so they cannot require it.
EXEMPT_PATHS = {"/api/v1/auth/login", "/api/v1/auth/setup", "/api/v1/auth/pin/login"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS and request.url.path not in EXEMPT_PATHS:
            has_session = settings.session_cookie_name in request.cookies
            if has_session:
                cookie_token = request.cookies.get(CSRF_COOKIE_NAME)
                header_token = request.headers.get(CSRF_HEADER_NAME)
                if not cookie_token or not header_token or not secrets.compare_digest(
                    cookie_token, header_token
                ):
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "CSRF token missing or invalid"},
                    )
        return await call_next(request)
