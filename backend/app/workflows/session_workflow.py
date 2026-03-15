"""
session_workflow.py: agno Workflow composition for the notes pipeline.

Uses agno.workflow.Workflow + Step (composition, not subclassing).
The notes_step executor writes to session_state so agno's finally-block
save_session() automatically persists session data to SQLite.

Background execution is handled by run_workflow_background(), called from
the async pipeline task in sessions.py after content extraction.
"""
import json
import logging
import re
import time

from agno.exceptions import InputCheckError
from agno.workflow import Workflow, Step
from agno.workflow.condition import Condition
from agno.workflow.parallel import Parallel
from agno.workflow.types import StepInput, StepOutput
from agno.db.sqlite import SqliteDb
from agno.agent import Agent

from app.extraction.cleaner import clean_extracted_content
from app.agents.flashcard_agent import build_flashcard_agent
from app.agents.quiz_agent import build_quiz_agent
from app.agents.model_factory import get_model
from app.agents.notes_agent import build_notes_agent
from app.agents.personas import CHAT_INTROS
from app.agents.research_agent import build_research_agent
from app.config import get_settings

logger = logging.getLogger("super_tutor.workflow")

# Maximum items returned from agent JSON output — prevents runaway generation.
_MAX_FLASHCARDS = 50
_MAX_QUIZ = 20


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
    "unknown",
    "provider",
    "i cannot",
    "i'm sorry",
    "i apologize",
    "sorry",
)
_TITLE_ERROR_SUBSTRINGS = ("returned error", "error occurred", "model error")


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


async def _generate_title(text: str, fallback: str = "", db: SqliteDb | None = None) -> str:
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
        result = await agent.arun(text[:800])
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

async def research_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Runs ResearchAgent for topic-mode sessions.
    Writes source_content and sources to session_state.
    Fatal: raises RuntimeError on any failure.
    """
    data = step_input.additional_data or {}

    topic_description = data.get("topic_description", "") or (step_input.get_input_as_string() or "")
    session_id = data.get("session_id", "")
    traces_db = data.get("db") or data.get("traces_db")

    agent = build_research_agent(db=traces_db)

    logger.info("research step start — topic=%.80s", topic_description, extra={"session_id": session_id, "step": "research"})
    _t = time.perf_counter()
    try:
        result = await agent.arun(topic_description)
    except InputCheckError as e:
        logger.warning("Prompt injection blocked in research_step — trigger=%s", e.check_trigger)
        raise RuntimeError(
            "Research topic rejected by input guardrail. If this is unexpected, try rephrasing your topic."
        ) from e
    logger.info("research step done — elapsed=%.3fs", time.perf_counter() - _t, extra={"session_id": session_id, "step": "research"})

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

    # Clean before storing — normalise unicode, collapse blank lines, strip trailing whitespace
    source_content = clean_extracted_content(source_content, source_type="url")

    # Write to session_state — agno persists to SQLite in finally block
    session_state["source_content"] = source_content
    session_state["sources"] = sources
    session_state["session_type"] = "topic"  # mark so notes_step/flashcards/quiz read from state

    return StepOutput(content=source_content)


# ---------------------------------------------------------------------------
# notes_step executor
# ---------------------------------------------------------------------------

async def notes_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Async step executor called by agno inside Workflow._execute().
    The parameter name 'session_state' is detected by agno via inspection
    (agno/workflow/step.py _function_has_session_state_param). Mutations to
    this dict are persisted to SQLite by save_session() in the finally block.
    """
    data = step_input.additional_data or {}

    tutoring_type = data.get("tutoring_type", "advanced")
    focus_prompt = data.get("focus_prompt", "")
    session_id = data.get("session_id", "")

    traces_db = data.get("traces_db")

    # Determine source_content based on session_type.
    # Prefer session_state (set by research_step for topic sessions), fall back to additional_data.
    session_type = session_state.get("session_type") or data.get("session_type", "")
    if session_type == "topic":
        source_content = session_state.get("source_content", "")
    else:
        # url or paste path — read from additional_data and persist for downstream steps
        source_content = data.get("source_content", "") or (step_input.get_input_as_string() or "")
        source_content = clean_extracted_content(source_content, source_type="document")
        session_state["source_content"] = source_content
        session_state["session_type"] = session_type  # persist url/paste so GET endpoint returns correct type

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
    logger.info("notes step start — tutoring_type=%s", tutoring_type, extra={"session_id": session_id, "step": "notes"})
    _t = time.perf_counter()
    try:
        notes_result = await notes_agent.arun(input_text)
    except InputCheckError as e:
        logger.warning("Prompt injection blocked in notes_step — trigger=%s", e.check_trigger)
        raise RuntimeError(
            "Content rejected by input guardrail. If this is unexpected, try rephrasing your input."
        ) from e
    logger.info("notes step done — elapsed=%.3fs", time.perf_counter() - _t, extra={"session_id": session_id, "step": "notes"})

    notes = notes_result.content or ""
    # Detect provider error JSON stored as content (agno may swallow 429s and return error JSON)
    if '"rate_limit_exceeded"' in notes or (notes.strip().startswith('{"error":') and '"message"' in notes):
        raise RuntimeError(f"rate_limit_exceeded: {notes[:500]}")
    if len(notes.strip()) < 100:
        raise RuntimeError(
            f"Notes generation failed — model returned: {notes.strip()!r}. Please try again."
        )

    # Ensure truncation notice is always present in notes when the document was cut.
    # Models may omit or rephrase the inline marker — append deterministically if missing.
    was_truncated = bool(data.get("was_truncated", False))
    if was_truncated and "truncated" not in notes.lower():
        notes = (
            notes
            + "\n\n---\n\n**Note:** This document was truncated due to length. "
            "Upload a specific chapter or section for complete coverage."
        )

    # Write to session_state — agno persists to SQLite in finally block
    session_state["notes"] = notes
    session_state["tutoring_type"] = tutoring_type
    session_state["was_truncated"] = was_truncated
    # sources: only set for non-topic sessions — topic sessions have sources set by research_step
    if session_type != "topic":
        session_state["sources"] = []
    session_state["chat_intro"] = CHAT_INTROS.get(tutoring_type, CHAT_INTROS["advanced"])

    # Persist upload filename as source — used by GET /sessions/{id} response
    source = data.get("source", "")
    if source:
        session_state["source"] = source

    return StepOutput(content=notes)


# ---------------------------------------------------------------------------
# flashcards_step executor
# ---------------------------------------------------------------------------

async def flashcards_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates flashcards from source_content in session_state.
    Non-fatal: failures write to session_state["errors"]["flashcards"] and return empty list.
    Agno injects session_state by parameter name.
    """
    data = step_input.additional_data or {}
    session_id = data.get("session_id", "")
    traces_db = data.get("db") or data.get("traces_db")
    tutoring_type = data.get("tutoring_type", "advanced")
    # Prefer session_state (set by research_step for topic sessions); fall back to
    # additional_data for url/paste sessions where notes_step may run in parallel.
    source_content = session_state.get("source_content", "") or data.get("source_content", "")

    logger.info("flashcards step start", extra={"session_id": session_id, "step": "flashcards"})

    try:
        if not source_content:
            raise RuntimeError("No source_content in session_state for flashcards_step")

        agent = build_flashcard_agent(tutoring_type=tutoring_type, db=traces_db)
        result = await agent.arun(source_content)

        if not result or not result.content:
            raise RuntimeError("FlashcardAgent returned empty output")

        # Parse JSON — strip markdown fences first
        raw = result.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        flashcards = json.loads(raw)

        if not isinstance(flashcards, list):
            raise ValueError("FlashcardAgent output is not a JSON array")

        flashcards = flashcards[:_MAX_FLASHCARDS]
        session_state["flashcards"] = flashcards
        logger.info("flashcards step done — count=%d", len(flashcards), extra={"session_id": session_id, "step": "flashcards"})
        return StepOutput(content=json.dumps(flashcards))

    except InputCheckError as e:
        msg = f"Flashcard generation rejected by input guardrail: {e.check_trigger}"
        logger.warning("flashcards step error — %s", msg, extra={"session_id": session_id, "step": "flashcards"})
        session_state.setdefault("errors", {})["flashcards"] = msg
        session_state["flashcards"] = []
        return StepOutput(content="[]")
    except Exception as e:
        msg = str(e)
        logger.warning("flashcards step error — %s", msg, extra={"session_id": session_id, "step": "flashcards"})
        session_state.setdefault("errors", {})["flashcards"] = msg
        session_state["flashcards"] = []
        return StepOutput(content="[]")


# ---------------------------------------------------------------------------
# quiz_step executor
# ---------------------------------------------------------------------------

async def quiz_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates quiz questions from source_content in session_state.
    Non-fatal: failures write to session_state["errors"]["quiz"] and return empty list.
    Agno injects session_state by parameter name.
    """
    data = step_input.additional_data or {}
    session_id = data.get("session_id", "")
    traces_db = data.get("db") or data.get("traces_db")
    tutoring_type = data.get("tutoring_type", "advanced")
    # Prefer session_state (set by research_step for topic sessions); fall back to
    # additional_data for url/paste sessions where notes_step may run in parallel.
    source_content = session_state.get("source_content", "") or data.get("source_content", "")

    logger.info("quiz step start", extra={"session_id": session_id, "step": "quiz"})

    try:
        if not source_content:
            raise RuntimeError("No source_content in session_state for quiz_step")

        agent = build_quiz_agent(tutoring_type=tutoring_type, db=traces_db)
        result = await agent.arun(source_content)

        if not result or not result.content:
            raise RuntimeError("QuizAgent returned empty output")

        # Parse JSON — strip markdown fences first
        raw = result.content.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        quiz = json.loads(raw)

        if not isinstance(quiz, list):
            raise ValueError("QuizAgent output is not a JSON array")

        quiz = quiz[:_MAX_QUIZ]
        session_state["quiz"] = quiz
        logger.info("quiz step done — count=%d", len(quiz), extra={"session_id": session_id, "step": "quiz"})
        return StepOutput(content=json.dumps(quiz))

    except InputCheckError as e:
        msg = f"Quiz generation rejected by input guardrail: {e.check_trigger}"
        logger.warning("quiz step error — %s", msg, extra={"session_id": session_id, "step": "quiz"})
        session_state.setdefault("errors", {})["quiz"] = msg
        session_state["quiz"] = []
        return StepOutput(content="[]")
    except Exception as e:
        msg = str(e)
        logger.warning("quiz step error — %s", msg, extra={"session_id": session_id, "step": "quiz"})
        session_state.setdefault("errors", {})["quiz"] = msg
        session_state["quiz"] = []
        return StepOutput(content="[]")


# ---------------------------------------------------------------------------
# title_step executor
# ---------------------------------------------------------------------------

async def title_step(step_input: StepInput, session_state: dict) -> StepOutput:
    """
    Generates a short session title (3-5 words).
    Non-fatal: falls back to _extract_title(notes) on AI failure, then to a generic string.
    Agno injects session_state by parameter name.
    """
    data = step_input.additional_data or {}
    session_id = data.get("session_id", "")
    traces_db = data.get("db") or data.get("traces_db")
    notes = session_state.get("notes", "")
    source_content = session_state.get("source_content", "")

    logger.info("title step start", extra={"session_id": session_id, "step": "title"})

    # Always compute a programmatic title first — guaranteed to succeed.
    # LLM is an optional enhancement: if it returns a better title, use it.
    programmatic_title = _extract_title(source_content or notes) or "Study Session"
    try:
        title = await _generate_title(source_content or notes, fallback=programmatic_title, db=traces_db)
        if not title or len(title.strip()) < 3:
            title = programmatic_title
    except Exception as e:
        logger.warning("title step error — %s", e, extra={"session_id": session_id, "step": "title"})
        title = programmatic_title

    title = title.strip() or "Study Session"
    session_state["title"] = title
    logger.info("title step done — title=%r", title, extra={"session_id": session_id, "step": "title"})
    return StepOutput(content=title)


# ---------------------------------------------------------------------------
# Condition evaluators
# ---------------------------------------------------------------------------

def _is_topic_session(step_input: StepInput) -> bool:
    """Return True for topic-type sessions that need the research step."""
    data = step_input.additional_data or {}
    return data.get("session_type") == "topic"


def _wants_flashcards(step_input: StepInput) -> bool:
    """Return True if flashcard generation was opted in."""
    data = step_input.additional_data or {}
    return bool(data.get("generate_flashcards", False))


def _wants_quiz(step_input: StepInput) -> bool:
    """Return True if quiz generation was opted in."""
    data = step_input.additional_data or {}
    return bool(data.get("generate_quiz", False))


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

    Pipeline:
        research (Condition: topic sessions only)
        → Parallel(
            notes (always, fatal on error),
            flashcards (Condition: if opted in, non-fatal),
            quiz (Condition: if opted in, non-fatal),
          )
        → title (non-fatal, falls back internally)

    The session_type / generate_flashcards / generate_quiz params are retained
    for API compatibility — runtime branching is handled by Condition evaluators
    that read the same values from additional_data at execution time.
    Calling with only session_id + session_db creates a workflow suitable for
    session lookups (conditions simply won't fire without additional_data).
    """
    settings = get_settings()
    step_retries = settings.agent_max_retries

    return Workflow(
        id="session-workflow",   # stable id — becomes workflow_id in DB rows
        name="Session Workflow",
        steps=[
            Condition(
                name="research",
                description="Run research agent only for topic-type sessions",
                evaluator=_is_topic_session,
                steps=[Step(name="research", executor=research_step, on_error="fail", max_retries=step_retries)],
            ),
            Parallel(
                Step(name="notes", executor=notes_step, on_error="fail", max_retries=step_retries),
                Condition(
                    name="flashcards",
                    description="Generate flashcards if opted in",
                    evaluator=_wants_flashcards,
                    steps=[Step(name="flashcards", executor=flashcards_step, max_retries=step_retries)],
                ),
                Condition(
                    name="quiz",
                    description="Generate quiz if opted in",
                    evaluator=_wants_quiz,
                    steps=[Step(name="quiz", executor=quiz_step, max_retries=step_retries)],
                ),
                name="content_generation",
                description="Generate notes, flashcards, and quiz concurrently",
            ),
            Step(name="title", executor=title_step),
        ],
        db=session_db,
        session_id=session_id,
    )


# ---------------------------------------------------------------------------
# Background workflow runner (called from sessions.py pipeline task)
# ---------------------------------------------------------------------------

async def run_workflow_background(
    session_id: str,
    session_type: str,       # "topic" | "url" | "paste" | "upload"
    source_content: str,     # pre-extracted content; "" for topic sessions
    topic_description: str,  # raw topic string; "" for url/paste/upload
    tutoring_type: str,
    traces_db: SqliteDb,
    focus_prompt: str = "",
    source: str = "",        # original filename for upload sessions; "" for others
    generate_flashcards: bool = False,
    generate_quiz: bool = False,
    was_truncated: bool = False,  # True when upload document exceeded the char limit
) -> None:
    """
    Runs the agno workflow and updates session_status on completion.
    Called from the background pipeline task in sessions.py after content extraction.

    IMPORTANT: This is called from asyncio.create_task() — never re-raise here.
    All outcomes (success and failure) are written to session_status.db.
    """
    from app.utils.session_status import update_session_status

    logger.debug(
        "Workflow start — session_id=%s session_type=%s tutoring_type=%s"
        " flashcards=%s quiz=%s content_chars=%d",
        session_id, session_type, tutoring_type,
        generate_flashcards, generate_quiz, len(source_content),
    )

    workflow = build_session_workflow(
        session_id=session_id,
        session_db=traces_db,
        session_type=session_type,
        generate_flashcards=generate_flashcards,
        generate_quiz=generate_quiz,
    )

    try:
        await workflow.arun(
            additional_data={
                "session_id": session_id,
                "session_type": session_type,
                "source_content": source_content,
                "source": source,
                "topic_description": topic_description,
                "tutoring_type": tutoring_type,
                "focus_prompt": focus_prompt,
                "generate_flashcards": generate_flashcards,
                "generate_quiz": generate_quiz,
                "was_truncated": was_truncated,
                "traces_db": traces_db,
            },
            session_id=session_id,
        )

        state = workflow.get_session_state(session_id=session_id)
        notes = state.get("notes", "")
        if not notes:
            logger.error(
                "Workflow completed but notes empty — session_id=%s state_keys=%s",
                session_id, list(state.keys()),
            )
            update_session_status(
                session_id, "failed", "empty",
                "Workflow completed but produced no notes. Please try again.",
            )
            return

        title = state.get("title") or session_id
        try:
            workflow.set_session_name(session_id=session_id, session_name=title)
        except Exception as e:
            logger.warning("Could not set workflow session name: %s", e)

        logger.info(
            "Workflow complete — session_id=%s title=%r notes_chars=%d",
            session_id, title, len(notes),
        )
        update_session_status(session_id, "complete")

    except Exception as e:
        logger.error("Workflow failed — session_id=%s", session_id, exc_info=True)
        update_session_status(session_id, "failed", "workflow_error", str(e))
    except BaseException:
        # CancelledError (e.g. server shutdown) is a BaseException, not Exception.
        # Update status before re-raising so the session doesn't stay stuck in 'pending'.
        update_session_status(session_id, "failed", "workflow_error", "Task was cancelled")
        raise
