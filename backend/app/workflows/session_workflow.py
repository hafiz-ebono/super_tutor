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

from agno.exceptions import InputCheckError
from agno.workflow import Workflow, Step
from agno.workflow.types import StepInput, StepOutput
from agno.db.sqlite import SqliteDb
from agno.agent import Agent

from app.agents.flashcard_agent import build_flashcard_agent
from app.agents.quiz_agent import build_quiz_agent
from app.agents.model_factory import get_model
from app.agents.notes_agent import build_notes_agent
from app.agents.personas import CHAT_INTROS
from app.agents.research_agent import build_research_agent
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
# research_step executor
# ---------------------------------------------------------------------------

def research_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Runs ResearchAgent for topic-mode sessions.
    Writes source_content and sources to session_state.
    Fatal: raises RuntimeError on any failure.

    IMPORTANT: This function runs inside asyncio.to_thread — do NOT use await here.
    """
    settings = get_settings()

    topic_description = step_input.additional_data.get("topic_description", "")
    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("db") or step_input.additional_data.get("traces_db")

    agent = build_research_agent(db=traces_db)

    logger.info("Workflow step start — step=research topic=%r", topic_description[:80])
    _t = time.perf_counter()
    try:
        result = run_with_retry(
            agent.run,
            topic_description,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,
        )
    except InputCheckError as e:
        logger.warning("Prompt injection blocked in research_step — trigger=%s", e.check_trigger)
        raise RuntimeError(
            "Research topic rejected by input guardrail. If this is unexpected, try rephrasing your topic."
        ) from e
    logger.info("Workflow step done — step=research elapsed=%.2fs", time.perf_counter() - _t)

    if not result or not result.content:
        raise RuntimeError("ResearchAgent returned empty content")

    # The ResearchAgent instructs the model to return JSON {content, sources}.
    # Strip markdown fences and attempt to parse; fall back to treating the
    # entire output as prose with no sources (matches research_agent._parse_json_safe).
    raw = result.content
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip()
    cleaned = re.sub(r"```\s*$", "", cleaned).strip()
    try:
        parsed = json.loads(cleaned)
        source_content = parsed.get("content", "")
        sources = parsed.get("sources", [])
        if not isinstance(sources, list):
            sources = []
        sources = [s for s in sources if isinstance(s, str)]
    except (json.JSONDecodeError, ValueError, AttributeError):
        source_content = raw
        sources = []

    if len(source_content) < 100:
        raise RuntimeError(
            f"ResearchAgent returned insufficient content — got {len(source_content)} chars. Please try again."
        )

    # Write to session_state — agno persists to SQLite in finally block
    session_state["source_content"] = source_content
    session_state["sources"] = sources
    session_state["session_type"] = "topic"  # mark so notes_step/flashcards/quiz read from state

    return StepOutput(content=source_content)


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

    tutoring_type = step_input.additional_data.get("tutoring_type", "advanced")
    focus_prompt = step_input.additional_data.get("focus_prompt", "")
    session_id = step_input.additional_data.get("session_id", "")

    traces_db = step_input.additional_data.get("traces_db")

    # Determine source_content based on session_type.
    # Prefer session_state (set by research_step for topic sessions), fall back to additional_data.
    session_type = session_state.get("session_type") or step_input.additional_data.get("session_type", "")
    if session_type == "topic":
        source_content = session_state.get("source_content", "")
    else:
        # url or paste path — read from additional_data and persist for downstream steps
        source_content = step_input.additional_data.get("source_content", "")
        session_state["source_content"] = source_content

    # 50-char minimum (lower than research_step's 100) — user-supplied content can be
    # shorter prose; we only reject clearly empty or trivially short inputs.
    if not source_content or len(source_content) < 50:
        raise RuntimeError(
            f"source_content is too short to generate notes — got {len(source_content)} chars. "
            "Please provide more content."
        )

    input_text = (
        f"Content:\n{source_content}\n\nFocus on: {focus_prompt}"
        if focus_prompt
        else f"Content:\n{source_content}"
    )

    notes_agent = build_notes_agent(tutoring_type, db=traces_db)
    logger.info("Workflow step start — step=notes tutoring_type=%s", tutoring_type)
    _t = time.perf_counter()
    try:
        notes_result = run_with_retry(
            notes_agent.run,
            input_text,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,
        )
    except InputCheckError as e:
        logger.warning("Prompt injection blocked in notes_step — trigger=%s", e.check_trigger)
        raise RuntimeError(
            "Content rejected by input guardrail. If this is unexpected, try rephrasing your input."
        ) from e
    logger.info("Workflow step done — step=notes elapsed=%.2fs", time.perf_counter() - _t)

    notes = notes_result.content or ""
    if len(notes.strip()) < 100:
        raise RuntimeError(
            f"Notes generation failed — model returned: {notes.strip()!r}. Please try again."
        )

    # Write to session_state — agno persists to SQLite in finally block
    session_state["notes"] = notes
    session_state["tutoring_type"] = tutoring_type
    # sources: only set for non-topic sessions — topic sessions have sources set by research_step
    if session_type != "topic":
        session_state["sources"] = []
    session_state["chat_intro"] = CHAT_INTROS.get(tutoring_type, CHAT_INTROS["advanced"])

    return StepOutput(content=notes)


# ---------------------------------------------------------------------------
# flashcards_step executor
# ---------------------------------------------------------------------------

def flashcards_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates flashcards from source_content in session_state.
    Non-fatal: failures write to session_state["errors"]["flashcards"] and return empty list.
    Agno injects session_state by parameter name.

    IMPORTANT: This function runs inside asyncio.to_thread — do NOT use await here.
    """
    settings = get_settings()

    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("db") or step_input.additional_data.get("traces_db")
    tutoring_type = step_input.additional_data.get("tutoring_type", "advanced")
    source_content = session_state.get("source_content", "")

    logger.info("[flashcards_step] start session_id=%s", session_id)

    try:
        if not source_content:
            raise RuntimeError("No source_content in session_state for flashcards_step")

        agent = build_flashcard_agent(tutoring_type=tutoring_type, db=traces_db)
        result = run_with_retry(
            agent.run,
            source_content,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,
        )

        if not result or not result.content:
            raise RuntimeError("FlashcardAgent returned empty output")

        # Parse JSON — strip markdown fences first
        raw = result.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        flashcards = json.loads(raw)

        if not isinstance(flashcards, list):
            raise ValueError("FlashcardAgent output is not a JSON array")

        session_state["flashcards"] = flashcards
        logger.info("[flashcards_step] done session_id=%s count=%d", session_id, len(flashcards))
        return StepOutput(content=json.dumps(flashcards))

    except InputCheckError as e:
        msg = f"Flashcard generation rejected by input guardrail: {e.check_trigger}"
        logger.warning("[flashcards_step] InputCheckError session_id=%s: %s", session_id, msg)
        session_state.setdefault("errors", {})["flashcards"] = msg
        session_state["flashcards"] = []
        return StepOutput(content="[]")
    except Exception as e:
        msg = str(e)
        logger.warning("[flashcards_step] non-fatal error session_id=%s: %s", session_id, msg)
        session_state.setdefault("errors", {})["flashcards"] = msg
        session_state["flashcards"] = []
        return StepOutput(content="[]")


# ---------------------------------------------------------------------------
# quiz_step executor
# ---------------------------------------------------------------------------

def quiz_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates quiz questions from source_content in session_state.
    Non-fatal: failures write to session_state["errors"]["quiz"] and return empty list.
    Agno injects session_state by parameter name.

    IMPORTANT: This function runs inside asyncio.to_thread — do NOT use await here.
    """
    settings = get_settings()

    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("db") or step_input.additional_data.get("traces_db")
    tutoring_type = step_input.additional_data.get("tutoring_type", "advanced")
    source_content = session_state.get("source_content", "")

    logger.info("[quiz_step] start session_id=%s", session_id)

    try:
        if not source_content:
            raise RuntimeError("No source_content in session_state for quiz_step")

        agent = build_quiz_agent(tutoring_type=tutoring_type, db=traces_db)
        result = run_with_retry(
            agent.run,
            source_content,
            max_attempts=settings.agent_max_retries,
            session_id=session_id,
        )

        if not result or not result.content:
            raise RuntimeError("QuizAgent returned empty output")

        # Parse JSON — strip markdown fences first
        raw = result.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        quiz = json.loads(raw)

        if not isinstance(quiz, list):
            raise ValueError("QuizAgent output is not a JSON array")

        session_state["quiz"] = quiz
        logger.info("[quiz_step] done session_id=%s count=%d", session_id, len(quiz))
        return StepOutput(content=json.dumps(quiz))

    except InputCheckError as e:
        msg = f"Quiz generation rejected by input guardrail: {e.check_trigger}"
        logger.warning("[quiz_step] InputCheckError session_id=%s: %s", session_id, msg)
        session_state.setdefault("errors", {})["quiz"] = msg
        session_state["quiz"] = []
        return StepOutput(content="[]")
    except Exception as e:
        msg = str(e)
        logger.warning("[quiz_step] non-fatal error session_id=%s: %s", session_id, msg)
        session_state.setdefault("errors", {})["quiz"] = msg
        session_state["quiz"] = []
        return StepOutput(content="[]")


# ---------------------------------------------------------------------------
# title_step executor
# ---------------------------------------------------------------------------

def title_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates a short session title (3-5 words).
    Non-fatal: falls back to _extract_title(notes) on AI failure, then to a generic string.
    Agno injects session_state by parameter name.

    IMPORTANT: This function runs inside asyncio.to_thread — do NOT use await here.
    """
    session_id = step_input.additional_data.get("session_id", "")
    traces_db = step_input.additional_data.get("db") or step_input.additional_data.get("traces_db")
    notes = session_state.get("notes", "")
    source_content = session_state.get("source_content", "")

    logger.info("[title_step] start session_id=%s", session_id)

    try:
        title = _generate_title(source_content or notes, db=traces_db, session_id=session_id)
        if not title or len(title.strip()) < 3:
            raise RuntimeError("Title too short")
    except Exception as e:
        logger.warning("[title_step] AI title failed, falling back: %s", e)
        try:
            title = _extract_title(notes) or "Study Session"
        except Exception:
            title = "Study Session"

    title = title.strip() or "Study Session"
    session_state["title"] = title
    logger.info("[title_step] done session_id=%s title=%r", session_id, title)
    return StepOutput(content=title)


# ---------------------------------------------------------------------------
# Workflow factory
# ---------------------------------------------------------------------------

def build_session_workflow(
    session_id: str,
    session_db: SqliteDb,
    session_type: str = "url",
    generate_flashcards: bool = False,
    generate_quiz: bool = False,
) -> Workflow:
    """
    Per-request factory. Never reuse across requests.
    Builds a conditional step list based on session_type and opt-in flags.
    Calling with only session_id + session_db (e.g. from _guard_session) creates a
    minimal workflow suitable for get_session() lookups.
    """
    steps = []
    if session_type == "topic":
        steps.append(Step(name="research", executor=research_step))
    steps.append(Step(name="notes", executor=notes_step))
    if generate_flashcards:
        steps.append(Step(name="flashcards", executor=flashcards_step))
    if generate_quiz:
        steps.append(Step(name="quiz", executor=quiz_step))
    steps.append(Step(name="title", executor=title_step))

    return Workflow(
        id="session-workflow",   # stable id — becomes workflow_id in DB rows
        name="Session Workflow",
        steps=steps,
        db=session_db,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Async generator for SSE (called from router)
# ---------------------------------------------------------------------------

async def run_session_workflow(
    session_id: str,
    session_type: str,            # "topic" | "url" | "paste"
    source_content: str,          # pre-extracted content (url/paste paths); "" for topic
    topic_description: str,       # raw topic string (topic path); "" for url/paste
    tutoring_type: str,
    focus_prompt: str = "",
    generate_flashcards: bool = False,
    generate_quiz: bool = False,
    traces_db: SqliteDb | None = None,
) -> AsyncGenerator[RunResponse, None]:
    """
    Async generator yielding RunResponse objects for the SSE router.
    Yields upfront progress messages, then runs the workflow in a thread,
    then yields a workflow_completed RunResponse with full session data.
    """
    # Emit predicted progress messages before the thread starts (asyncio.to_thread
    # is blocking — we can't yield from inside it).
    if session_type == "topic":
        yield RunResponse(content="Researching your topic...")
    yield RunResponse(content="Crafting your notes...")
    if generate_flashcards:
        yield RunResponse(content="Creating flashcards...")
    if generate_quiz:
        yield RunResponse(content="Building quiz questions...")
    yield RunResponse(content="Generating title...")

    workflow = build_session_workflow(
        session_id=session_id,
        session_db=_get_session_db(),
        session_type=session_type,
        generate_flashcards=generate_flashcards,
        generate_quiz=generate_quiz,
    )

    await asyncio.to_thread(
        workflow.run,
        additional_data={
            "session_id": session_id,
            "session_type": session_type,
            "source_content": source_content,
            "topic_description": topic_description,
            "tutoring_type": tutoring_type,
            "focus_prompt": focus_prompt,
            "generate_flashcards": generate_flashcards,
            "generate_quiz": generate_quiz,
            "traces_db": traces_db,
        },
        session_id=session_id,
    )

    # Read final state from in-memory workflow.session_state (already persisted to SQLite)
    state = workflow.session_state or {}
    notes = state.get("notes", "")
    flashcards = state.get("flashcards", [])
    quiz = state.get("quiz", [])
    title = state.get("title", "Study Session")
    sources = state.get("sources", [])
    chat_intro = state.get("chat_intro", "")
    errors = state.get("errors") or {}

    # Emit non-fatal step errors as warnings so the frontend can surface them
    for key, msg in errors.items():
        yield RunResponse(event="warning", content=f"{key}: {msg}")

    yield RunResponse(
        event="workflow_completed",
        content={
            "source_title": title,
            "tutoring_type": tutoring_type,
            "session_type": session_type,
            "sources": sources,
            "notes": notes,
            "flashcards": flashcards,
            "quiz": quiz,
            "chat_intro": chat_intro,
            "errors": errors or None,
        },
    )
