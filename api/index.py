"""Vercel ASGI entry point for the Elite MatchMaster API.

The request-serving deployment deliberately disables the original app lifespan:
the upstream lifespan launches long-running polling/learning loops that do not
belong inside serverless request workers. Run those workers on a persistent
worker host and use durable external storage before relying on cross-request
state in production.
"""
from contextlib import asynccontextmanager
from pathlib import Path
import sys

REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import app as emm_app  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402


@asynccontextmanager
async def serverless_lifespan(_application):
    """Do not start persistent background loops in a serverless worker."""
    yield


app = emm_app.app
app.router.lifespan_context = serverless_lifespan


@app.get("/", include_in_schema=False)
async def api_root():
    """Return a lightweight discovery document instead of a misleading 404."""
    return JSONResponse({
        "service": "Elite MatchMaster API",
        "status_endpoint": "/status",
        "health_endpoint": "/health",
        "openapi_endpoint": "/openapi.json",
        "docs_endpoint": "/docs",
        "fixtures_endpoint": "/events/today",
        "analysis_endpoint": "/analyze/match",
        "note": "Health freshness depends on the separate persistent polling worker."
    })


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Browsers request a favicon automatically; no icon asset is required."""
    return Response(status_code=204)


# Vercel rewrites to one Python function. Carry the original request path in
# __path so FastAPI can dispatch /openapi.json, /events/today, and other routes
# instead of receiving only the internal /api/index function path.
from urllib.parse import parse_qsl, urlencode


class VercelOriginalPathMiddleware:
    def __init__(self, application):
        self.application = application

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            query = parse_qsl(
                scope.get("query_string", b"").decode("latin-1"),
                keep_blank_values=True,
            )
            original_path = next(
                (value for key, value in query if key == "__path"), None
            )

            # Some Vercel routing paths omit rewritten query parameters. Recover
            # the public path from platform routing headers before falling back
            # to the ASGI path.
            headers = {
                key.decode("latin-1").lower(): value.decode("latin-1")
                for key, value in scope.get("headers", [])
            }
            if not original_path:
                original_path = headers.get("x-invoke-path") or headers.get("x-now-route-matches")
                if original_path and "=" in original_path and "path=" in original_path:
                    original_path = next(
                        (part.split("=", 1)[1] for part in original_path.split("&") if part.startswith("path=")),
                        original_path,
                    )
            if original_path:
                original_path = original_path.split("?", 1)[0]
                # Normalize both "openapi.json" and "//openapi.json" to
                # the canonical "/openapi.json" path after rewrite expansion.
                original_path = "/" + original_path.lstrip("/")
                scope = dict(scope)
                scope["path"] = original_path
                scope["raw_path"] = original_path.encode("utf-8")
                remaining = [(key, value) for key, value in query if key != "__path"]
                scope["query_string"] = urlencode(remaining, doseq=True).encode("latin-1")
        await self.application(scope, receive, send)


app = VercelOriginalPathMiddleware(app)
