"""Request ids and optional Sentry. Tokens and payment secrets are not sent."""

from __future__ import annotations

import os
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_SECRET_HEADERS = {"authorization", "cookie", "x-razorpay-signature"}


def init_sentry() -> None:
    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
    except ImportError:
        return

    def _scrub(event, hint):
        request = event.get("request") or {}
        headers = {
            key: value
            for key, value in (request.get("headers") or {}).items()
            if key.lower() not in _SECRET_HEADERS
        }
        request["headers"] = headers
        request.pop("cookies", None)
        request.pop("data", None)
        event["request"] = request
        return event

    sentry_sdk.init(dsn=dsn, send_default_pii=False, before_send=_scrub)


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        request.state.request_id = request_id
        try:
            import sentry_sdk

            sentry_sdk.set_tag("request_id", request_id)
            facility_id = request.headers.get("x-facility-id")
            if facility_id:
                sentry_sdk.set_tag("facility_id", facility_id)
        except ImportError:
            pass
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
