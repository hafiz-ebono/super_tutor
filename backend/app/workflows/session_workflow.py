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
import re
from dataclasses import dataclass, field
from typing import Iterator, Any

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
    ) -> Iterator[RunResponse]:
        input_text = (
            f"Content:\n{content}\n\nFocus on: {focus_prompt}"
            if focus_prompt
            else f"Content:\n{content}"
        )

        # Step 1: Generate notes
        yield RunResponse(content="Crafting your notes...")
        notes_result = self.notes_agent.run(input_text)
        notes = notes_result.content or ""

        # Step 2: Generate flashcards
        yield RunResponse(content="Making your flashcards...")
        flashcard_result = self.flashcard_agent.run(input_text)
        flashcards_raw = flashcard_result.content or "[]"
        flashcards = _parse_json_safe(flashcards_raw, [])

        # Step 3: Generate quiz
        yield RunResponse(content="Building your quiz...")
        quiz_result = self.quiz_agent.run(input_text)
        quiz_raw = quiz_result.content or "[]"
        quiz = _parse_json_safe(quiz_raw, [])

        # Final: complete event with all data
        yield RunResponse(
            event="workflow_completed",
            content={
                "source_title": _extract_title(content, url),
                "tutoring_type": tutoring_type,
                "notes": notes,
                "flashcards": flashcards,
                "quiz": quiz,
            },
        )


def build_workflow(tutoring_type: str) -> SessionWorkflow:
    """Factory: creates SessionWorkflow for the given tutoring type."""
    return SessionWorkflow(tutoring_type=tutoring_type)
