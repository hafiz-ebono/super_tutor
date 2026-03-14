"""
upload.py: POST /sessions/upload SSE endpoint for PDF/DOCX file uploads.

Accepts a file via multipart/form-data, validates it synchronously (before
opening the SSE stream), extracts text via extract_document(), then runs
the existing session workflow — emitting SSE progress events throughout.

Phase 2 of Phase 12 (backend upload endpoint).
"""
import asyncio
import json
import logging
import uuid
from typing import AsyncGenerator, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from sse_starlette.sse import EventSourceResponse

from app.extraction.document_extractor import DocumentExtractionError, extract_document
from app.utils.session_status import create_session_status
from app.workflows.session_workflow import _get_traces_db, run_workflow_background

logger = logging.getLogger("super_tutor.upload")

router = APIRouter()

# Keep strong references to running tasks so the GC cannot collect them
# before they complete. Tasks remove themselves via add_done_callback.
_ACTIVE_TASKS: set[asyncio.Task] = set()

MAX_BYTES = 20 * 1024 * 1024  # 20 MB
ALLOWED_EXTENSIONS = (".pdf", ".docx")


# ---------------------------------------------------------------------------
# POST /upload — mounted at /sessions/upload via main.py
# ---------------------------------------------------------------------------


@router.post("/upload")
async def create_upload_session(
    file: UploadFile = File(...),
    tutoring_type: str = Form(...),
    focus_prompt: Optional[str] = Form(default=None),
    generate_flashcards: bool = Form(default=False),
    generate_quiz: bool = Form(default=False),
):
    """
    Accept a PDF (or DOCX) file upload, validate it, extract text, then stream
    session-creation progress events via Server-Sent Events.

    Pre-stream validation:
      - Extension check: must end with .pdf or .docx (HTTP 400 for others)
      - Size guard: max 20 MB (HTTP 413)
      - Extraction: scanned/image PDFs raise HTTP 422 with error_kind='scanned_pdf'

    SSE events emitted after validation passes:
      {"event": "progress", "data": {"message": "Reading your file..."}}
      ...workflow events...
      {"event": "complete", "data": {"session_id": "<uuid>"}}
    or on error:
      {"event": "error", "data": {"error_kind": "...", "message": "..."}}
    """

    # ------------------------------------------------------------------
    # PHASE 1: Pre-stream validation (errors here return plain HTTP, not SSE)
    # ------------------------------------------------------------------

    # Step 1: Read bytes and capture filename
    filename = file.filename or "upload.pdf"
    file_bytes: bytes = await file.read()

    logger.info(
        "File received — filename=%s size_bytes=%d tutoring_type=%s",
        filename, len(file_bytes), tutoring_type,
    )

    # Step 2: Extension / MIME validation — only PDF and DOCX supported via this endpoint
    if not filename.lower().endswith(ALLOWED_EXTENSIONS):
        raise HTTPException(
            status_code=400,
            detail={
                "error_kind": "unsupported_format",
                "message": "Only PDF and Word (.docx) files are supported.",
            },
        )

    # Step 3: File size guard
    if len(file_bytes) > MAX_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error_kind": "file_too_large",
                "message": "File exceeds the 20 MB limit. Please upload a smaller file.",
            },
        )

    # Step 4: Extract document (blocking — runs in thread; raises HTTP 422 for scanned PDFs)
    try:
        extracted: str = await asyncio.to_thread(extract_document, file_bytes, filename)
    except DocumentExtractionError as e:
        logger.warning(
            "Document extraction failed before SSE open — filename=%s error_kind=%s message=%s",
            filename, e.error_kind, e.message,
        )
        raise HTTPException(
            status_code=422,
            detail={"error_kind": e.error_kind, "message": e.message},
        )

    logger.info(
        "Document extracted — filename=%s chars=%d tutoring_type=%s",
        filename, len(extracted), tutoring_type,
    )

    # ------------------------------------------------------------------
    # PHASE 2: SSE stream (extraction succeeded — open stream and run workflow)
    # ------------------------------------------------------------------

    session_id = str(uuid.uuid4())
    create_session_status(session_id)
    queue: asyncio.Queue[dict | None] = asyncio.Queue()

    async def background_pipeline() -> None:
        """Fire-and-forget coroutine: runs workflow, posts events to queue."""
        try:
            await queue.put(
                {"event": "progress", "data": json.dumps({"message": "Reading your file..."})}
            )
            logger.debug("Workflow start — session_id=%s filename=%s", session_id, filename)

            await run_workflow_background(
                session_id=session_id,
                session_type="upload",
                source_content=extracted,
                topic_description="",
                tutoring_type=tutoring_type,
                focus_prompt=focus_prompt or "",
                source=filename,
                generate_flashcards=generate_flashcards,
                generate_quiz=generate_quiz,
                traces_db=_get_traces_db(),
            )

            logger.info("Session stored — session_id=%s", session_id)
            await queue.put(
                {"event": "complete", "data": json.dumps({"session_id": session_id})}
            )
        except Exception:
            logger.error(
                "Upload pipeline error — session_id=%s", session_id, exc_info=True
            )
            await queue.put(
                {
                    "event": "error",
                    "data": json.dumps(
                        {
                            "error_kind": "workflow_error",
                            "message": "An unexpected error occurred. Please try again.",
                        }
                    ),
                }
            )
        finally:
            await queue.put(None)  # sentinel — signals event_generator to stop

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Dequeue events from background_pipeline and yield them as SSE."""
        task = asyncio.create_task(background_pipeline())
        _ACTIVE_TASKS.add(task)
        task.add_done_callback(_ACTIVE_TASKS.discard)
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            task.cancel()

    return EventSourceResponse(event_generator())
