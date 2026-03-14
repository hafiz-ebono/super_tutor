"""
Shared FastAPI dependencies.

traces_db is created once at app startup (main.py lifespan) and stored on
app.state. All routers retrieve the same instance via Depends(get_traces_db)
instead of each maintaining their own lazy singleton.

ACTIVE_TASKS is a process-wide set of all running background asyncio tasks.
Both sessions.py and upload.py register tasks here so the lifespan shutdown
hook can await all of them in one place.

limiter is imported here so routers have a single import location for both.
"""
import asyncio
from fastapi import Request
from agno.db.sqlite import SqliteDb
from slowapi import Limiter
from slowapi.util import get_remote_address

# Process-wide registry of in-flight background tasks.
# Routers add tasks here; lifespan shutdown drains them.
ACTIVE_TASKS: set[asyncio.Task] = set()

limiter = Limiter(key_func=get_remote_address)


def get_traces_db(request: Request) -> SqliteDb:
    """Return the single shared SqliteDb instance for this process."""
    return request.app.state.traces_db
