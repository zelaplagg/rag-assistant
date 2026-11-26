"""HTTP limits that run before FastAPI parses a request."""
import asyncio
import time

from starlette.datastructures import Headers, MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from .web_sessions import Window

_JSON_LIMIT = 12 * 1024
_ACTIONS = {"/api/ask", "/api/summary", "/api/flashcards", "/api/sample", "/api/upload"}
_CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
    "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


class HttpGuard:
    def __init__(self, app, *, public: bool, origins: set[str], upload_limit: int, origin: str | None):
        self.app = app
        self.public = public
        self.origins = origins
        self.upload_limit = upload_limit
        self.origin = origin
        self.actions = asyncio.Semaphore(1 if public else 2)
        self.requests = Window(120)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope["path"]
        method = scope["method"]
        is_api = path == "/api" or path.startswith("/api/")
        headers = Headers(scope=scope)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                out = MutableHeaders(scope=message)
                out["X-Content-Type-Options"] = "nosniff"
                out["X-Frame-Options"] = "DENY"
                out["Referrer-Policy"] = "no-referrer"
                if self.public:
                    out["Strict-Transport-Security"] = "max-age=31536000"
                    out["Content-Security-Policy"] = _CSP
                if is_api:
                    out["Cache-Control"] = "no-store"
            await send(message)

        async def reject(status, detail, extra=None):
            await JSONResponse({"detail": detail}, status, headers=extra)(scope, receive, send_with_headers)

        if self.public and is_api and path != "/api/health":
            try:
                self.requests.take(time.monotonic())
            except HTTPException as exc:
                await reject(exc.status_code, exc.detail, exc.headers)
                return

        if is_api and method in {"POST", "DELETE", "PUT", "PATCH"}:
            scheme = "https" if self.public else scope["scheme"]
            same_origin = self.origin or f"{scheme}://{headers.get('host', '')}"
            origin = headers.get("origin")
            if (
                (origin is not None and origin != same_origin and origin not in self.origins)
                or (origin is None and headers.get("sec-fetch-site") == "cross-site")
            ):
                await reject(403, "This request must come from the StudyMate site.")
                return

        if method != "POST" or path not in _ACTIONS:
            await self.app(scope, receive, send_with_headers)
            return

        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        expected = "multipart/form-data" if path == "/api/upload" else "application/json"
        if content_type != expected and not (path == "/api/sample" and not content_type):
            await reject(415, f"Send this request as {expected}.")
            return

        limit = self.upload_limit if path == "/api/upload" else _JSON_LIMIT
        length = headers.get("content-length")
        if length is not None and (not length.isascii() or not length.isdecimal() or len(length) > 12):
            await reject(400, "Invalid request size.")
            return
        if length is not None and int(length) > limit:
            await reject(413, "The request is too large.")
            return
        if self.actions.locked():
            await reject(429, "StudyMate is processing another request. Try again shortly.", {"Retry-After": "3"})
            return

        async with self.actions:
            body = bytearray()
            try:
                async with asyncio.timeout(15):
                    more = True
                    while more:
                        message = await receive()
                        if message["type"] == "http.disconnect":
                            return
                        chunk = message.get("body", b"")
                        if len(body) + len(chunk) > limit:
                            await reject(413, "The request is too large.")
                            return
                        body.extend(chunk)
                        more = message.get("more_body", False)
            except TimeoutError:
                await reject(408, "The request body took too long.")
                return

            async def bounded_receive():
                if body is not None:
                    return replay_body()
                return await receive()

            def replay_body():
                nonlocal body
                data = bytes(body)
                body = None
                return {"type": "http.request", "body": data, "more_body": False}

            await self.app(scope, bounded_receive, send_with_headers)
