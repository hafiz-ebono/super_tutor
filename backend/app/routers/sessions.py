import asyncio
import logging
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from agno.db.sqlite import SqliteDb

from app.models.session import SessionRequest
from app.extraction.chain import extract_content, ExtractionError
from app.workflows.session_workflow import (
    run_workflow_background,
    build_session_workflow,
    _parse_json_safe,
)
from app.agents.flashcard_agent import build_flashcard_agent
from app.agents.quiz_agent import build_quiz_agent
from app.config import get_settings
from app.utils.session_status import (
    create_session_status,
    update_session_status,
    get_session_status,
)

logger = logging.getLogger("super_tutor.sessions")

router = APIRouter()

# Keep strong references to running tasks so the GC cannot collect them
# before they complete. Tasks remove themselves via add_done_callback.
_ACTIVE_TASKS: set[asyncio.Task] = set()


# ---------------------------------------------------------------------------
# Traces DB singleton
# ---------------------------------------------------------------------------

def _get_traces_db() -> SqliteDb:
    """Lazy singleton for the shared trace db — avoids circular import from main.py."""
    if not hasattr(_get_traces_db, "_instance"):
        settings = get_settings()
        _get_traces_db._instance = SqliteDb(
            db_file=settings.trace_db_path,
            id="super_tutor_traces",
        )
    return _get_traces_db._instance


# ---------------------------------------------------------------------------
# Session guard (used by regenerate endpoint)
# ---------------------------------------------------------------------------

def _guard_session(session_id: str) -> None:
    """
    Raise HTTP 404 if session_id is unknown.
    Raise HTTP 409 if session is still processing (not yet complete).
    """
    status_row = get_session_status(session_id)
    if status_row is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found.",
        )
    if status_row["status"] != "complete":
        raise HTTPException(
            status_code=409,
            detail="Session is still processing. Please wait for it to complete.",
        )


# ---------------------------------------------------------------------------
# Background pipeline (fire-and-forget asyncio task)
# ---------------------------------------------------------------------------

async def _run_session_pipeline(
    session_id: str,
    params: dict,
    traces_db: SqliteDb,
) -> None:
    """
    Full background pipeline: content extraction → agno workflow → status update.

    Dispatched via asyncio.create_task() from POST /sessions.
    Never raises — all outcomes are written to session_status.db so the
    polling endpoint can surface them to the client.
    """
    url = params.get("url") or ""
    paste_text = params.get("paste_text") or ""
    topic_description = params.get("topic_description") or ""
    tutoring_type = params.get("tutoring_type", "advanced")
    focus_prompt = params.get("focus_prompt") or ""
    generate_flashcards = bool(params.get("generate_flashcards", False))
    generate_quiz = bool(params.get("generate_quiz", False))

    input_type = "topic" if topic_description else ("paste" if paste_text else "url")
    logger.debug(
        "Pipeline start — session_id=%s input_type=%s tutoring_type=%s"
        " flashcards=%s quiz=%s",
        session_id, input_type, tutoring_type, generate_flashcards, generate_quiz,
    )

    try:
        if topic_description:
            session_type = "topic"
            content = ""

        elif paste_text:
            session_type = "paste"
            content = paste_text
            logger.debug(
                "Paste input — session_id=%s chars=%d", session_id, len(content)
            )

        elif url:
            session_type = "url"
            logger.debug("Extracting URL — session_id=%s url=%.120s", session_id, url)
            try:
                content = await extract_content(str(url))
                logger.debug(
                    "URL extraction complete — session_id=%s chars=%d",
                    session_id, len(content),
                )
            except ExtractionError as e:
                logger.warning(
                    "Extraction failed — session_id=%s kind=%s message=%s",
                    session_id, e.kind, e.message,
                )
                update_session_status(session_id, "failed", e.kind, e.message)
                return

        else:
            update_session_status(
                session_id, "failed", "invalid_input",
                "No URL, text, or topic provided.",
            )
            return

        await run_workflow_background(
            session_id=session_id,
            session_type=session_type,
            source_content=content,
            topic_description=topic_description,
            tutoring_type=tutoring_type,
            focus_prompt=focus_prompt,
            generate_flashcards=generate_flashcards,
            generate_quiz=generate_quiz,
            traces_db=traces_db,
        )

    except Exception:
        logger.error(
            "Pipeline unhandled error — session_id=%s", session_id, exc_info=True
        )
        update_session_status(
            session_id, "failed", "workflow_error",
            "An unexpected error occurred. Please try again.",
        )


# ---------------------------------------------------------------------------
# POST /sessions — create session and start background workflow
# ---------------------------------------------------------------------------

@router.post("")
async def create_session(request: SessionRequest):
    """
    Creates a session and starts the AI workflow as a background task.
    Returns session_id immediately. Client polls GET /sessions/{session_id}.
    """
    logger.debug(
        "create_session called — tutoring_type=%s has_url=%s has_paste=%s has_topic=%s",
        request.tutoring_type,
        bool(request.url),
        bool(request.paste_text),
        bool(request.topic_description),
    )

    if request.topic_description and len(request.topic_description.strip()) < 10:
        raise HTTPException(
            status_code=422,
            detail="Topic description is too short. Please describe what you want to learn.",
        )

    session_id = str(uuid.uuid4())
    params = request.model_dump(mode="json")
    input_type = "topic" if request.topic_description else ("paste" if request.paste_text else "url")

    logger.info(
        "Session created — session_id=%s input_type=%s tutoring_type=%s",
        session_id, input_type, request.tutoring_type,
    )

    create_session_status(session_id)

    task = asyncio.create_task(
        _run_session_pipeline(session_id, params, _get_traces_db())
    )
    _ACTIVE_TASKS.add(task)
    task.add_done_callback(_ACTIVE_TASKS.discard)

    logger.debug("Background task dispatched — session_id=%s", session_id)
    return {"session_id": session_id}


# ---------------------------------------------------------------------------
# GET /sessions/{session_id} — poll for status and data
# ---------------------------------------------------------------------------

@router.get("/{session_id}")
async def get_session(session_id: str):
    """
    Poll endpoint. Returns one of:
      { "status": "pending" }
      { "status": "failed", "error_kind": str, "error_message": str }
      { "status": "complete", "session_id": str, ...session_data }
    """
    logger.debug("get_session — session_id=%s", session_id)

    status_row = get_session_status(session_id)
    if status_row is None:
        raise HTTPException(status_code=404, detail="Session not found")

    status = status_row["status"]
    logger.debug("get_session — session_id=%s status=%s", session_id, status)

    if status == "pending":
        return {"status": "pending"}

    if status == "failed":
        return JSONResponse(
            status_code=200,
            content={
                "status": "failed",
                "error_kind": status_row["error_kind"] or "workflow_error",
                "error_message": status_row["error_message"] or "Something went wrong. Please try again.",
            },
        )

    # status == "complete" — read session data from agno's SQLite (traces db)
    wf = build_session_workflow(session_id=session_id, session_db=_get_traces_db())
    existing = wf.get_session(session_id=session_id)
    if existing is None:
        logger.error(
            "Session status=complete but agno data missing — session_id=%s", session_id
        )
        raise HTTPException(
            status_code=500, detail="Session data unavailable. Please try again."
        )

    state = (existing.session_data or {}).get("session_state", {})
    logger.info("get_session complete — session_id=%s", session_id)
    return {
        "status": "complete",
        "session_id": session_id,
        "source_title": state.get("title", "Study Session"),
        "tutoring_type": state.get("tutoring_type", ""),
        "session_type": state.get("session_type", "url"),
        "source": state.get("source", ""),
        "sources": state.get("sources", []),
        "notes": state.get("notes"),
        "flashcards": state.get("flashcards", []),
        "quiz": state.get("quiz", []),
        "chat_intro": state.get("chat_intro", ""),
    }


# ---------------------------------------------------------------------------
# POST /sessions/{session_id}/regenerate/{section}
# ---------------------------------------------------------------------------

class RegenerateRequest(BaseModel):
    tutoring_type: str


@router.post("/{session_id}/regenerate/{section}")
async def regenerate_section(session_id: str, section: str, body: RegenerateRequest):
    """Generates flashcards or quiz on demand using source_content loaded from SQLite session state."""
    if section not in ("flashcards", "quiz"):
        raise HTTPException(status_code=400, detail="section must be 'flashcards' or 'quiz'")

    _guard_session(session_id)

    wf = build_session_workflow(session_id=session_id, session_db=_get_traces_db())
    existing = wf.get_session(session_id=session_id)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")
    state = (existing.session_data or {}).get("session_state", {})
    source_content = state.get("source_content", "")
    if not source_content:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' has no source content. Cannot regenerate.",
        )

    input_text = source_content
    logger.info(
        "Generating %s — session_id=%s tutoring_type=%s",
        section, session_id, body.tutoring_type,
    )

    if section == "flashcards":
        agent = build_flashcard_agent(body.tutoring_type, db=_get_traces_db())
        result = await asyncio.to_thread(agent.run, input_text)
        new_items = _parse_json_safe(result.content or "[]", [])
        if not new_items:
            raise HTTPException(status_code=500, detail="Generation returned empty response")
        logger.info(
            "Generation complete — session_id=%s section=flashcards count=%d",
            session_id, len(new_items),
        )
        return {"flashcards": new_items}

    else:
        agent = build_quiz_agent(body.tutoring_type, db=_get_traces_db())
        result = await asyncio.to_thread(agent.run, input_text)
        new_items = _parse_json_safe(result.content or "[]", [])
        if not new_items:
            raise HTTPException(status_code=500, detail="Generation returned empty response")
        logger.info(
            "Generation complete — session_id=%s section=quiz count=%d",
            session_id, len(new_items),
        )
        return {"quiz": new_items}
