"""
SessionWorkflow: orchestrates notes, flashcard, and quiz agents in sequence.
Yields progress RunResponse objects (with .content str) between each agent step,
then a final RunResponse (with .content dict) when all three complete.

Note on agno 2.1.1 deviation: agno.run.workflow in version 2.1.1 has a substantially
different API (event-based streaming with WorkflowStartedEvent etc.) from what the plan
assumed. To avoid the API mismatch, SessionWorkflow is a plain Python class that does NOT
inherit from agno.workflow.Workflow. The run() generator interface is preserved exactly as
the SSE endpoint (01-05) expects: yields objects with .content and .event attributes.
"""
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Iterator, Any

from agno.agent import Agent
from app.agents.model_factory import get_model

logger = logging.getLogger("super_tutor.workflow")
from app.agents.notes_agent import build_notes_agent
from app.agents.flashcard_agent import build_flashcard_agent
from app.agents.quiz_agent import build_quiz_agent


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


def _generate_title(text: str) -> str:
    """Ask the AI for a concise 3-5 word title. Falls back to _extract_title on failure."""
    agent = Agent(
        model=get_model(),
        instructions=(
            "Generate a concise 3-5 word title that captures the main subject of the content provided. "
            "Return ONLY the title — no punctuation at the end, no quotes, no explanation."
        ),
    )
    try:
        logger.debug("Title generation start")
        result = agent.run(text[:800])
        title = (result.content or "").strip().strip('"').strip("'")
        if title:
            logger.debug("Title generation done — title=%r", title)
            return title[:80]
    except Exception:
        logger.warning("Title generation failed, falling back to extract_title")
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
    Orchestrates notes, flashcard, and quiz agents.
    run() is a synchronous generator — the SSE endpoint wraps it in async with asyncio.sleep(0).
    """

    def __init__(self, tutoring_type: str):
        self.tutoring_type = tutoring_type
        self.notes_agent = build_notes_agent(tutoring_type)
        self.flashcard_agent = build_flashcard_agent(tutoring_type)
        self.quiz_agent = build_quiz_agent(tutoring_type)

    def run(
        self,
        content: str,
        tutoring_type: str,
        focus_prompt: str = "",
        url: str = "",
        session_type: str = "url",
        sources: list | None = None,
        title_input: str = "",
    ) -> Iterator[RunResponse]:
        input_text = (
            f"Content:\n{content}\n\nFocus on: {focus_prompt}"
            if focus_prompt
            else f"Content:\n{content}"
        )

        errors: dict[str, str] = {}

        # Step 1: Generate notes — critical. Agno returns provider error messages as content
        # strings rather than raising, so we check length (real notes are always >100 chars).
        yield RunResponse(content="Crafting your notes...")
        logger.info("Workflow step start — step=notes tutoring_type=%s", tutoring_type)
        _t = time.perf_counter()
        notes_result = self.notes_agent.run(input_text)
        logger.info("Workflow step done — step=notes elapsed=%.2fs", time.perf_counter() - _t)
        notes = notes_result.content or ""
        if len(notes.strip()) < 100:
            raise RuntimeError(
                f"Notes generation failed — model returned: {notes.strip()!r}. Please try again."
            )

        # Step 2: Generate flashcards — non-critical. Show notes + error in flashcards tab.
        yield RunResponse(content="Making your flashcards...")
        logger.info("Workflow step start — step=flashcards")
        _t = time.perf_counter()
        try:
            flashcard_result = self.flashcard_agent.run(input_text)
            logger.info("Workflow step done — step=flashcards elapsed=%.2fs", time.perf_counter() - _t)
            flashcards_raw = flashcard_result.content or "[]"
            flashcards = _parse_json_safe(flashcards_raw, [])
            if not flashcards:
                errors["flashcards"] = "Flashcard generation returned an empty response."
        except Exception as e:
            logger.error("Workflow step error — step=flashcards error=%s", e, exc_info=True)
            flashcards = []
            errors["flashcards"] = f"Flashcard generation failed: {e}"

        # Step 3: Generate quiz — non-critical. Show notes (+ flashcards if ok) + error in quiz tab.
        yield RunResponse(content="Building your quiz...")
        logger.info("Workflow step start — step=quiz")
        _t = time.perf_counter()
        try:
            quiz_result = self.quiz_agent.run(input_text)
            logger.info("Workflow step done — step=quiz elapsed=%.2fs", time.perf_counter() - _t)
            quiz_raw = quiz_result.content or "[]"
            quiz = _parse_json_safe(quiz_raw, [])
            if not quiz:
                errors["quiz"] = "Quiz generation returned an empty response."
        except Exception as e:
            logger.error("Workflow step error — step=quiz error=%s", e, exc_info=True)
            quiz = []
            errors["quiz"] = f"Quiz generation failed: {e}"

        # Final: AI-generated title from the most focused signal available
        source_title = _generate_title(title_input if title_input else content)
        yield RunResponse(
            event="workflow_completed",
            content={
                "source_title": source_title,
                "tutoring_type": tutoring_type,
                "session_type": session_type,
                "sources": sources,
                "notes": notes,
                "flashcards": flashcards,
                "quiz": quiz,
                "errors": errors if errors else None,
            },
        )


def build_workflow(tutoring_type: str) -> SessionWorkflow:
    """Factory: creates SessionWorkflow for the given tutoring type."""
    return SessionWorkflow(tutoring_type=tutoring_type)
