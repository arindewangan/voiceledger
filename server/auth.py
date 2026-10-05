"""Bearer-token authentication middleware for the /mcp endpoint."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class BearerAuthMiddleware(BaseHTTPMiddleware):
    """Rejects unauthenticated requests to protected paths with 401."""

    def __init__(self, app, token: str, protected_prefixes: tuple[str, ...] = ("/mcp",)):
        super().__init__(app)
        self.token = token
        self.protected_prefixes = protected_prefixes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if any(request.url.path.startswith(p) for p in self.protected_prefixes):
            auth = request.headers.get("authorization", "")
            if auth != f"Bearer {self.token}":
                return JSONResponse(
                    {"error": "unauthorized",
                     "message": "Missing or invalid Bearer <redacted>"},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
        return await call_next(request)
