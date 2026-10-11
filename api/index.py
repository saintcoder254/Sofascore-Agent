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


@asynccontextmanager
async def serverless_lifespan(_application):
    """Do not start persistent background loops in a serverless worker."""
    yield


app = emm_app.app
app.router.lifespan_context = serverless_lifespan
