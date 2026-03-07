"""
SessionWorkflow: orchestrates notes agent only (flashcards/quiz are on-demand).
Yields progress RunResponse objects (with .content str) before the notes step,
then a final RunResponse (with .content dict) when notes + title complete.

Note on agno 2.1.1 deviation: agno.run.workflow in version 2.1.1 has a substantially
different API (event-based streaming with WorkflowStartedEvent etc.) from what the plan
assumed. To avoid the API mismatch, SessionWorkflow is a plain Python class that does NOT
inherit from agno.workflow.Workflow. The run() generator interface is preserved exactly as
the SSE endpoint (01-05) expects: yields objects with .content and .event attributes.
"""
import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import AsyncIterator, Any

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from app.agents.model_factory import get_model
from app.config import get_settings
from app.utils.retry import run_with_retry

logger = logging.getLogger("super_tutor.workflow")
from app.agents.notes_agent import build_notes_agent


@dataclass
class RunResponse:
    """Minimal response object compatible with the SSE endpoint's event loop."""
    content: Any = None
    event: str = "workflow_running"


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


class SessionWorkflow:
    """
    Orchestrates the notes agent only. Flashcards and quiz are generated on demand.
    run() is an async generator — each blocking agent.run() call is offloaded to the
    thread pool via asyncio.to_thread so the event loop stays unblocked between SSE yields.
    """

    def __init__(self, tutoring_type: str, db: SqliteDb | None = None):
        self.tutoring_type = tutoring_type
        self.db = db
        self.notes_agent = build_notes_agent(tutoring_type, db=self.db)

    async def run(
        self,
        content: str,
        tutoring_type: str,
        focus_prompt: str = "",
        url: str = "",
        session_type: str = "url",
        sources: list | None = None,
        title_input: str = "",
        session_id: str = "",
    ) -> AsyncIterator[RunResponse]:
        input_text = (
            f"Content:\n{content}\n\nFocus on: {focus_prompt}"
            if focus_prompt
            else f"Content:\n{content}"
        )

        # Step 1: Generate notes — critical. Agno returns provider error messages as content
        # strings rather than raising, so we check length (real notes are always >100 chars).
        yield RunResponse(content="Crafting your notes...")
        logger.info("Workflow step start — step=notes tutoring_type=%s", tutoring_type)
        _t = time.perf_counter()
        settings = get_settings()
        notes_result = await asyncio.to_thread(
            run_with_retry, self.notes_agent.run, input_text,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,  # TRAC-04: scope notes agent trace to this session
        )
        logger.info("Workflow step done — step=notes elapsed=%.2fs", time.perf_counter() - _t)
        notes = notes_result.content or ""
        if len(notes.strip()) < 100:
            raise RuntimeError(
                f"Notes generation failed — model returned: {notes.strip()!r}. Please try again."
            )

        # Final: AI-generated title from the most focused signal available.
        # _generate_title is synchronous and runs safely inside the thread pool thread.
        source_title = await asyncio.to_thread(_generate_title, title_input if title_input else content, title_input or url, self.db, session_id)
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


def build_workflow(tutoring_type: str, db: SqliteDb | None = None) -> SessionWorkflow:
    """Factory: creates SessionWorkflow for the given tutoring type."""
    return SessionWorkflow(tutoring_type=tutoring_type, db=db)
