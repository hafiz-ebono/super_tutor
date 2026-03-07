"""
session_workflow.py: agno Workflow composition for the notes pipeline.

Uses agno.workflow.Workflow + Step (composition, not subclassing).
The notes_step executor writes to session_state so agno's finally-block
save_session() automatically persists session data to SQLite.

SSE stream behavior is preserved end-to-end via run_session_workflow().
"""
import asyncio
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import AsyncGenerator, Any

from agno.workflow import Workflow, Step
from agno.workflow.types import StepInput, StepOutput
from agno.db.sqlite import SqliteDb
from agno.agent import Agent

from app.agents.model_factory import get_model
from app.agents.notes_agent import build_notes_agent
from app.config import get_settings
from app.utils.retry import run_with_retry

logger = logging.getLogger("super_tutor.workflow")


# ---------------------------------------------------------------------------
# RunResponse — minimal SSE-compatible response object (unchanged)
# ---------------------------------------------------------------------------

@dataclass
class RunResponse:
    """Minimal response object compatible with the SSE endpoint's event loop."""
    content: Any = None
    event: str = "workflow_running"


# ---------------------------------------------------------------------------
# Session DB singleton
# ---------------------------------------------------------------------------

def _get_session_db() -> SqliteDb:
    """Lazy singleton for the session SQLite db — separate file from traces."""
    if not hasattr(_get_session_db, "_instance"):
        settings = get_settings()
        db_dir = os.path.dirname(settings.session_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        _get_session_db._instance = SqliteDb(
            db_file=settings.session_db_path,
            id="super_tutor_sessions",  # different id from traces (super_tutor_traces)
        )
    return _get_session_db._instance


# ---------------------------------------------------------------------------
# Title helpers (verbatim — tested)
# ---------------------------------------------------------------------------

def _extract_title(content: str, url: str = "") -> str:
    """Extract a title from the first markdown heading or first line of content."""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
        if line and not line.startswith("#"):
            return line[:80]
    return url[:80] if url else "Untitled"


_TITLE_ERROR_PREFIXES = (
    "error",
    "provider",
    "i cannot",
    "i'm sorry",
    "i apologize",
    "sorry",
)
_TITLE_ERROR_SUBSTRINGS = ("returned error", "error occurred")


def _is_valid_title(title: str) -> bool:
    """Return True if title looks like a genuine short title, not a provider error string."""
    lower = title.lower()
    # Must not start with known error prefixes
    if any(lower.startswith(p) for p in _TITLE_ERROR_PREFIXES):
        return False
    # Must not contain known error substrings
    if any(s in lower for s in _TITLE_ERROR_SUBSTRINGS):
        return False
    # Must not span multiple lines (real titles are single-line)
    if "\n" in title:
        return False
    # Must be at least 2 words (single-word responses are suspicious)
    if len(title.split()) < 2:
        return False
    return True


def _generate_title(text: str, fallback: str = "", db: SqliteDb | None = None, session_id: str = "") -> str:
    """Ask the AI for a concise 3-5 word title. Falls back to fallback (truncated) or _extract_title on failure."""
    agent = Agent(
        model=get_model(),
        db=db,
        instructions=(
            "Generate a concise 3-5 word title that captures the main subject of the content provided. "
            "Return ONLY the title — no punctuation at the end, no quotes, no explanation."
        ),
    )
    try:
        logger.debug("Title generation start")
        result = run_with_retry(agent.run, text[:800], session_id=session_id)
        title = (result.content or "").strip().strip('"').strip("'")
        if title and _is_valid_title(title):
            logger.debug("Title generation done — title=%r", title)
            return title[:80]
        elif title:
            logger.warning("Title generation returned error-like string, falling back — title=%r", title)
    except Exception:
        logger.warning("Title generation failed, falling back to user input or extract_title")
    if fallback:
        return fallback[:80]
    return _extract_title(text)


def _parse_json_safe(raw: str, fallback: list) -> list:
    """Parse JSON from agent output, stripping markdown fences if present."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return fallback


# ---------------------------------------------------------------------------
# notes_step executor
# ---------------------------------------------------------------------------

def notes_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Synchronous step executor called by agno inside Workflow._execute().
    The parameter name 'session_state' is detected by agno via inspection
    (agno/workflow/step.py _function_has_session_state_param). Mutations to
    this dict are persisted to SQLite by save_session() in the finally block.

    IMPORTANT: This function runs inside asyncio.to_thread — do NOT use await here.
    """
    settings = get_settings()

    content = step_input.additional_data.get("content", "")
    tutoring_type = step_input.additional_data.get("tutoring_type", "micro_learning")
    session_type = step_input.additional_data.get("session_type", "url")
    sources = step_input.additional_data.get("sources", [])
    focus_prompt = step_input.additional_data.get("focus_prompt", "")
    session_id = step_input.additional_data.get("session_id", "")

    traces_db = step_input.additional_data.get("traces_db")

    input_text = (
        f"Content:\n{content}\n\nFocus on: {focus_prompt}"
        if focus_prompt
        else f"Content:\n{content}"
    )

    notes_agent = build_notes_agent(tutoring_type, db=traces_db)
    logger.info("Workflow step start — step=notes tutoring_type=%s", tutoring_type)
    _t = time.perf_counter()
    notes_result = run_with_retry(
        notes_agent.run,
        input_text,
        max_attempts=settings.agent_max_retries,
        session_id=session_id,
    )
    logger.info("Workflow step done — step=notes elapsed=%.2fs", time.perf_counter() - _t)

    notes = notes_result.content or ""
    if len(notes.strip()) < 100:
        raise RuntimeError(
            f"Notes generation failed — model returned: {notes.strip()!r}. Please try again."
        )

    # Write to session_state — agno persists to SQLite in finally block
    session_state["notes"] = notes
    session_state["tutoring_type"] = tutoring_type
    session_state["session_type"] = session_type
    session_state["sources"] = sources

    return StepOutput(content=notes)


# ---------------------------------------------------------------------------
# Workflow factory
# ---------------------------------------------------------------------------

def build_session_workflow(session_id: str, session_db: SqliteDb) -> Workflow:
    """
    Per-request factory. Never reuse across requests (CVE-2025-64168).
    Uses Steps-list path (not callable path) so agno injects session_state correctly.
    """
    return Workflow(
        id="session-workflow",        # stable id — becomes workflow_id in DB rows
        name="Session Workflow",
        steps=[Step(name="notes", executor=notes_step)],
        db=session_db,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Async generator for SSE (called from router)
# ---------------------------------------------------------------------------

async def run_session_workflow(
    session_id: str,
    content: str,
    tutoring_type: str,
    focus_prompt: str = "",
    url: str = "",
    session_type: str = "url",
    sources: list | None = None,
    title_input: str = "",
    traces_db: SqliteDb | None = None,
) -> AsyncGenerator[RunResponse, None]:
    """
    Async generator yielding RunResponse-compatible objects for the SSE router.
    Wraps the sync Workflow.run() via asyncio.to_thread (STATE.md locked decision).
    """
    yield RunResponse(content="Crafting your notes...")

    workflow = build_session_workflow(session_id=session_id, session_db=_get_session_db())

    result = await asyncio.to_thread(
        workflow.run,
        additional_data={
            "content": content,
            "tutoring_type": tutoring_type,
            "focus_prompt": focus_prompt,
            "session_type": session_type,
            "sources": sources or [],
            "session_id": session_id,
            "traces_db": traces_db,
        },
        session_id=session_id,
    )

    notes = result.content if result else ""

    source_title = await asyncio.to_thread(
        _generate_title,
        title_input if title_input else content,
        title_input or url,
        traces_db,
        session_id,
    )

    yield RunResponse(
        event="workflow_completed",
        content={
            "source_title": source_title,
            "tutoring_type": tutoring_type,
            "session_type": session_type,
            "sources": sources,
            "notes": notes,
            "flashcards": [],
            "quiz": [],
            "errors": None,
        },
    )
