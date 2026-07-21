import secrets

from fastapi import HTTPException, Request


CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def requires_csrf_check(request: Request) -> bool:
    if request.method.upper() not in UNSAFE_METHODS:
        return False
    if not request.cookies.get("access_token"):
        return False
    authorization = request.headers.get("authorization") or ""
    return not authorization.lower().startswith("bearer ")


def validate_csrf(request: Request) -> None:
    if not requires_csrf_check(request):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME) or ""
    supplied_token = request.headers.get(CSRF_HEADER_NAME) or request.query_params.get("csrf_token") or ""
    if not cookie_token or not supplied_token or not secrets.compare_digest(cookie_token, supplied_token):
        raise HTTPException(status_code=403, detail="CSRF token missing or invalid")
