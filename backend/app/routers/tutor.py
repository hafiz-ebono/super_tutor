import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request, Path
from sse_starlette.sse import EventSourceResponse
from agno.db.sqlite import SqliteDb
from agno.exceptions import InputCheckError

from app.models.tutor import TutorStreamRequest
from app.agents.tutor_team import build_tutor_team, is_rate_limit_error, TUTOR_TOKEN_EVENTS, TUTOR_ERROR_EVENT
from app.agents.model_factory import get_fallback_model
from app.dependencies import get_traces_db, limiter, ACTIVE_TASKS
from app.config import get_settings
from app.workflows.session_workflow import build_session_workflow

logger = logging.getLogger("super_tutor.tutor")

_QUIZ_SCORE_RE = re.compile(r"scored?\s+(\d+)\s+out\s+of\s+(\d+)", re.IGNORECASE)
_PROGRESS_QUERY_RE = re.compile(
    r"how\s+am\s+i\s+doing|where\s+am\s+i\s+weak|what\s+(?:are\s+my\s+)?(?:weak\s+areas?|gaps?|struggles?)"
    r"|my\s+progress|how\s+(?:well|good)\s+am\s+i|what\s+should\s+i\s+(?:focus|study|review)",
    re.IGNORECASE,
)
_FOCUS_AREA_RE = re.compile(
    r"(?:flashcards?|notes?|content|material|concepts?|topics?)\s+on\s+['\"]?([A-Za-z][^'\"?\.\n]{2,59})['\"]?"
    r"|(?:focus(?:ing)?\s+on|review(?:ing)?\s+|study(?:ing)?\s+)([A-Za-z][^'\"?\.\n]{2,59})",
    re.IGNORECASE,
)


def _build_progress_response(
    session_state: dict,
    source_content: str,
) -> str | None:
    """
    Return a pre-formed progress summary if the session state has adaptive data,
    or a prompt to get quizzed if there's no data yet. Returns None only if we
    should fall through to the LLM (currently never, always returns a string).

    Bypasses the LLM for this deterministic query so small models can't produce
    "I don't have the necessary tools" responses.
    """
    quiz_score = session_state.get("quiz_score")
    focus_areas = session_state.get("focus_areas", [])
    topic = source_content.split("\n")[0].strip().lstrip("#").strip() or "this material"

    if not quiz_score and not focus_areas:
        return (
            f"You haven't been quizzed yet — want me to test you on {topic} "
            f"so I can track your progress?"
        )

    parts = []
    if quiz_score:
        correct = quiz_score.get("correct", "?")
        total = quiz_score.get("total", "?")
        pct = round(correct / total * 100) if total else 0
        parts.append(f"Your last quiz score was {correct}/{total} ({pct}%).")
    if focus_areas:
        areas_str = ", ".join(focus_areas[:3])
        parts.append(f"Based on your answers, focus on: {areas_str}.")
        parts.append("Want me to generate extra flashcards on any of these?")
    elif quiz_score:
        parts.append("Keep it up — want another quiz question?")

    return " ".join(parts)


def _extract_quiz_score(message: str) -> dict | None:
    """Extract quiz score from quiz-results sharing message. Returns None if not a score message."""
    m = _QUIZ_SCORE_RE.search(message)
    if m:
        return {
            "correct": int(m.group(1)),
            "total": int(m.group(2)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    return None


def _extract_focus_areas(response_text: str) -> list[str]:
    """Extract named focus areas from Advisor response text. Returns [] if none found."""
    areas = []
    for m in _FOCUS_AREA_RE.finditer(response_text):
        concept = (m.group(1) or m.group(2) or "").strip()
        if concept:
            areas.append(concept)
    return areas


async def _persist_tutor_adaptive_data(
    session_id: str,
    traces_db: SqliteDb,
    quiz_score: dict | None,
    focus_areas: list[str],
) -> None:
    """Write quiz_score and/or focus_areas to workflow session_state in SQLite.

    Uses the BARE session_id (not the tutor namespace) — adaptive data belongs
    in the workflow session row, not the tutor conversation history row.
    Non-fatal: logs on failure, never raises.
    """
    if not quiz_score and not focus_areas:
        return
    try:
        wf = build_session_workflow(session_id=session_id, session_db=traces_db)
        existing = await asyncio.to_thread(wf.get_session, session_id=session_id)
        if existing is None:
            logger.warning("_persist_tutor_adaptive_data: session not found — session_id=%s", session_id)
            return
        session_data = existing.session_data or {}
        state = session_data.get("session_state", {})
        if quiz_score:
            state["quiz_score"] = quiz_score
        if focus_areas:
            existing_areas = state.get("focus_areas", [])
            merged = list(dict.fromkeys(existing_areas + focus_areas))  # deduplicate, preserve order
            state["focus_areas"] = merged
        session_data["session_state"] = state
        existing.session_data = session_data
        await wf.asave_session(session=existing)
        logger.info(
            "Persisted adaptive data — session_id=%s quiz_score=%s focus_areas=%s",
            session_id,
            quiz_score,
            focus_areas,
        )
    except Exception:
        logger.warning("Failed to persist adaptive data — session_id=%s", session_id, exc_info=True)


router = APIRouter()


@router.post("/{session_id}/stream")
@limiter.limit(get_settings().rate_limit_tutor)
async def tutor_stream(
    session_id: str = Path(max_length=128, pattern=r'^[a-zA-Z0-9_-]+$'),
    request: Request = ...,
    body: TutorStreamRequest = ...,
    traces_db: SqliteDb = Depends(get_traces_db),
):
    """
    Accept: JSON body with message, tutoring_type, session_id.
    source_content and notes are loaded from SQLite session state via session_id.
    Return: SSE stream of stream_start, token events, and a final done event.

    Conversation history is stored in SQLite under the `tutor:{session_id}` namespace
    and replayed on every request (TUTOR-03 persistence requirement).

    CRITICAL: Uses team.arun(stream=True) — a native async generator in agno 2.5.8.
    Do NOT use asyncio.to_thread here (RESEARCH.md Pitfall 1: breaks streaming).
    """
    # Load session from SQLite session state — authoritative source.
    try:
        wf = build_session_workflow(session_id=session_id, session_db=traces_db)
        session = await asyncio.to_thread(wf.get_session, session_id=session_id)
    except Exception as e:
        logger.error("Failed to load session for tutor — session_id=%s error=%s", session_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to load session data. Please try again.")

    # session_data is the top-level dict; session_state is nested inside it
    session_state = (session.session_data or {}).get("session_state", {}) if session else {}
    if not session or not session_state:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Please create a new session.",
        )

    # Extract content fields from session state
    source_content = session_state.get("source_content", "")
    notes = session_state.get("notes", "")

    # Guard: source_content is required — the tutor cannot function without session material.
    # Returns HTTP 422 per CONTEXT.md locked decision (client error: session is incomplete).
    if not source_content.strip():
        raise HTTPException(
            status_code=422,
            detail="Session has no source content. The tutor requires source material to function.",
        )

    # Namespace the session_id to avoid collision with the workflow session row.
    # agno_sessions uses session_id as primary key — sharing the same id would cause
    # the team to overwrite the workflow's session_data (which holds source_content and notes).
    # See RESEARCH.md Pitfall 3.
    tutor_session_id = f"tutor:{session_id}:{body.tutor_reset_id}"

    # Build team — per-request factory, never reuse across requests.
    team_kwargs = dict(
        source_content=source_content,
        notes=notes,
        tutoring_type=body.tutoring_type,
        db=traces_db,
        session_topic=source_content[:300],
        quiz_score=session_state.get("quiz_score"),
        focus_areas=session_state.get("focus_areas", []),
    )
    team = build_tutor_team(**team_kwargs)

    # Fallback model wrapper is built upfront (cheap — no network I/O).
    # The full fallback team is built lazily inside the rate-limit exception handler.
    fallback_model = get_fallback_model()

    logger.info(
        "Tutor stream start",
        extra={"session_id": session_id, "tutoring_type": body.tutoring_type},
    )

    async def _stream_team(active_team, message: str) -> AsyncGenerator[dict, None]:
        """Inner generator — yields SSE dicts from one team.arun() call.

        When InputCheckError is raised in a pre-hook, agno does NOT propagate it
        as an exception — it emits a TeamRunError event instead. We inspect the
        chunk to distinguish off-topic rejections from real errors and re-raise
        InputCheckError so the outer handler sends the correct SSE event.

        Also yields a final {"event": "_accumulated", "data": <full_text>} sentinel
        for post-stream focus area extraction. Callers must consume and discard this event.
        """
        error_chunk = None
        accumulated: list[str] = []
        async for chunk in active_team.arun(message, stream=True, session_id=tutor_session_id):
            if chunk.event == TUTOR_ERROR_EVENT:
                error_chunk = chunk
                break
            if chunk.event in TUTOR_TOKEN_EVENTS and chunk.content:
                accumulated.append(chunk.content)
                yield {"event": "token", "data": json.dumps({"token": chunk.content})}
        if error_chunk is not None:
            err_str = (
                str(getattr(error_chunk, "error", "") or "")
                + str(getattr(error_chunk, "content", "") or "")
            ).lower()
            if "not related" in err_str or "off_topic" in err_str or "off-topic" in err_str:
                raise InputCheckError("Message is not related to the session topic.")
            if any(m in err_str for m in ("rate limit", "rate_limit", "1300", "429", "too many request", "unknown model error")):
                raise RuntimeError("rate_limit_error")
            raise RuntimeError("team_run_error")
        # Sentinel: yield accumulated text for caller to capture — never forwarded to SSE client.
        yield {"event": "_accumulated", "data": "".join(accumulated)}

    async def event_generator() -> AsyncGenerator[dict, None]:
        yield {"event": "stream_start", "data": json.dumps({})}

        # Pre-stream: extract quiz score from message if it matches the share-results pattern.
        # This runs before team.arun() so it captures the score even if the Advisor fires later.
        quiz_score = _extract_quiz_score(body.message)

        async def _stream_and_persist(active_team, message: str) -> AsyncGenerator[dict, None]:
            """Consume _stream_team, strip the _accumulated sentinel, and schedule persistence."""
            accumulated_text = ""
            async for event in _stream_team(active_team, message):
                if event["event"] == "_accumulated":
                    accumulated_text = event["data"]
                    continue
                yield event
            # Post-stream: fire-and-forget persistence — create_task is non-blocking so
            # the done event (yielded by the caller after us) is never delayed by DB I/O.
            focus_areas = _extract_focus_areas(accumulated_text)
            task = asyncio.create_task(
                _persist_tutor_adaptive_data(
                    session_id=session_id,
                    traces_db=traces_db,
                    quiz_score=quiz_score,
                    focus_areas=focus_areas,
                )
            )
            ACTIVE_TASKS.add(task)
            task.add_done_callback(ACTIVE_TASKS.discard)

        # Progress queries ("how am I doing?", "where am I weak?") are answered
        # deterministically from session state — bypasses the LLM so small models
        # can't produce "I don't have the necessary tools" responses.
        if _PROGRESS_QUERY_RE.search(body.message):
            progress_text = _build_progress_response(session_state, source_content)
            if progress_text:
                logger.info("Progress query intercepted — responding deterministically")
                yield {"event": "token", "data": json.dumps({"token": progress_text})}
                yield {"event": "done", "data": json.dumps({})}
                return

        try:
            async for event in _stream_and_persist(team, body.message):
                yield event
            logger.info("Tutor stream done", extra={"session_id": session_id})
            yield {"event": "done", "data": json.dumps({})}

        except InputCheckError:
            logger.info("Topic guardrail triggered — session_id=%s user_message=%s", session_id, body.message[:100])
            yield {
                "event": "rejected",
                "data": json.dumps({
                    "reason": "That's outside what we're studying today. Let's stay focused on the session material."
                }),
            }
        except RuntimeError as e:
            if str(e) == "team_run_error":
                logger.warning("Tutor run error event received — session_id=%s", session_id)
                yield {"event": "error", "data": json.dumps({"error": "Something went wrong. Please try again."})}
            elif str(e) == "rate_limit_error" and fallback_model is not None:
                logger.warning(
                    "Primary model rate-limited (Team event), switching to fallback — session_id=%s", session_id
                )
                fallback_team = build_tutor_team(**team_kwargs, model=fallback_model)
                yield {"event": "token", "data": json.dumps({"token": "\n*(Switching to backup model…)*\n\n"})}
                try:
                    async for event in _stream_and_persist(fallback_team, body.message):
                        yield event
                    logger.info("Tutor stream done (fallback) — session_id=%s", session_id)
                    yield {"event": "done", "data": json.dumps({})}
                except Exception as e2:
                    logger.error("Fallback tutor stream error: %s", e2, exc_info=True)
                    yield {"event": "error", "data": json.dumps({"error": "Both primary and backup models failed. Please try again later."})}
            else:
                raise
        except Exception as e:
            if is_rate_limit_error(e) and fallback_model is not None:
                logger.warning(
                    "Primary model rate-limited, switching to fallback — session_id=%s", session_id
                )
                fallback_team = build_tutor_team(**team_kwargs, model=fallback_model)
                yield {"event": "token", "data": json.dumps({"token": "\n*(Switching to backup model…)*\n\n"})}
                try:
                    async for event in _stream_and_persist(fallback_team, body.message):
                        yield event
                    logger.info("Tutor stream done (fallback) — session_id=%s", session_id)
                    yield {"event": "done", "data": json.dumps({})}
                except Exception as e2:
                    logger.error("Fallback tutor stream error: %s", e2, exc_info=True)
                    yield {"event": "error", "data": json.dumps({"error": "Both primary and backup models failed. Please try again later."})}
            else:
                logger.error("Tutor stream error: %s", e, exc_info=True, extra={"session_id": session_id})
                yield {"event": "error", "data": json.dumps({"error": "Something went wrong. Please try again."})}

    return EventSourceResponse(event_generator())
