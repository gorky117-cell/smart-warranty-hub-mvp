import json
import logging
import time
from uuid import uuid4

from fastapi import Request


REQUEST_ID_HEADER = "X-Request-ID"
_LOGGER = logging.getLogger("swh.request")


def request_id_from(request: Request) -> str:
    supplied = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
    if supplied and len(supplied) <= 128:
        return supplied
    return f"req_{uuid4().hex[:16]}"


def _client_host(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _safe_user(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


def request_log_record(
    request: Request,
    *,
    request_id: str,
    status_code: int,
    elapsed_ms: float,
    error: str | None = None,
) -> dict:
    record = {
        "event": "http_request",
        "request_id": request_id,
        "method": request.method,
        "path": request.url.path,
        "status_code": status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "client": _client_host(request),
        "user_id": _safe_user(request),
    }
    if error:
        record["error"] = error[:160]
    return record


def log_request(record: dict, *, exc_info=None) -> None:
    status_code = int(record.get("status_code") or 0)
    message = json.dumps(record, sort_keys=True, default=str)
    if exc_info is not None or status_code >= 500:
        _LOGGER.error(message, exc_info=exc_info)
    elif status_code >= 400:
        _LOGGER.warning(message)
    else:
        _LOGGER.info(message)


def elapsed_ms_since(start: float) -> float:
    return (time.perf_counter() - start) * 1000.0
