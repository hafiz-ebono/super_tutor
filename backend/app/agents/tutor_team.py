"""
Agno Team factory for the Personal Tutor backend.

IMPORTANT USAGE NOTES:
- build_tutor_team() is a per-request factory. Never reuse a Team instance across requests.
  Each call constructs a fresh Team with a fresh Explainer, grounding the instructions in
  the current session's source_content and notes.
- Conversation history is managed at the Team level ONLY. The Explainer agent does NOT
  get its own db= or add_history_to_context=True. Giving the Explainer its own DB would
  cause duplicate/conflicting session rows (RESEARCH.md Pitfall 4).
- TUTOR_TOKEN_EVENTS and TUTOR_ERROR_EVENT must be imported by the tutor router to filter
  the Team SSE stream correctly. Two event types carry token content:
    - TeamRunContent: coordinator's own acknowledgment prefix tokens
    - TeamRunIntermediateContent: Explainer member tokens (the substantive answer)
  Missing either causes partial responses.
"""

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.run.team import TeamRunEvent
from agno.team import Team
from agno.team.mode import TeamMode

from app.agents.guardrails import PROMPT_INJECTION_GUARDRAIL
from app.agents.model_factory import get_model
from app.config import get_settings

# ---------------------------------------------------------------------------
# Constants — imported by the tutor router to filter the SSE stream
# ---------------------------------------------------------------------------

TUTOR_TOKEN_EVENTS = {
    TeamRunEvent.run_content.value,               # "TeamRunContent" — coordinator prefix tokens
    TeamRunEvent.run_intermediate_content.value,  # "TeamRunIntermediateContent" — Explainer tokens
}
TUTOR_ERROR_EVENT = TeamRunEvent.run_error.value  # "TeamRunError"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_grounding_block(source_content: str, notes: str) -> str:
    """
    Build a grounding context block for injection into both the coordinator and
    Explainer system prompts.

    source_content is the authoritative grounding (full raw text from the session).
    notes are the distilled AI-generated derivative — useful for concise reference.
    Both are included when available for maximum grounding fidelity.
    """
    block = f"--- SESSION MATERIAL ---\n{source_content}\n--- END MATERIAL ---"
    if notes.strip():
        block += f"\n\n--- SESSION NOTES (summary) ---\n{notes}\n--- END NOTES ---"
    return block


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_tutor_team(
    source_content: str,
    notes: str,
    tutoring_type: str,
    db: SqliteDb | None = None,
) -> Team:
    """
    Build a fresh Agno Team for a single tutor request.

    Args:
        source_content: The session's full source text. Required — raises ValueError if empty.
        notes:          AI-generated notes for the session (may be empty string).
        tutoring_type:  One of "micro_learning", "teaching_a_kid", "advanced". Passed through
                        for future persona differentiation (not used in this phase).
        db:             Shared SqliteDb instance (traces_db from dependency injection).
                        Pass None only in tests without persistence.

    Returns:
        A configured Team ready for team.arun(message, stream=True, session_id=...).

    Raises:
        ValueError: If source_content is empty after stripping. The router should have
                    already returned HTTP 422, so this is a programming-level guard.
    """
    if not source_content.strip():
        raise ValueError("source_content is required to build the tutor team")

    grounding_block = _build_grounding_block(source_content, notes)

    explainer = Agent(
        name="Explainer",
        role="Answer student questions strictly grounded in the session material",
        model=get_model(),
        # No db= on the Explainer — history is managed at the Team level only (RESEARCH.md Pitfall 4)
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions=f"""You are a tutoring specialist.
Answer ONLY from the session material below. Do not use outside knowledge.
If the student's question is not covered in the material, say exactly:
"I can only answer about this session's material."

RESPONSE FORMAT: Plain text only. No markdown, no bullet points, no bold text,
no headers. Write in clear prose. Keep answers focused and concise.
Only elaborate if the student explicitly asks for more detail.

{grounding_block}""",
    )

    return Team(
        name="TutorTeam",
        mode=TeamMode.coordinate,
        model=get_model(),
        members=[explainer],
        db=db,
        add_history_to_context=True,
        num_history_runs=get_settings().tutor_history_window,
        enable_session_summaries=False,
        stream_member_events=True,
        instructions=f"""You are a personal tutor assistant for a student studying specific session material.
You have full access to the student's session content below.

ROUTING RULES:
- If the student's question relates to the session material → dispatch to the Explainer immediately
- If the question is off-topic (not related to the session material) → reject it directly
- NEVER ask the student to confirm routing. Dispatch immediately without explanation.
- NEVER reveal agent names, internal routing decisions, or team structure.
  You are simply "the tutor."

RESPONSE FORMAT when routing to Explainer:
Begin with exactly ONE sentence of acknowledgment (e.g., "Great question — let me explain."),
then stop. The Explainer will continue with the detailed answer.
Do not add any conclusion or summary after the Explainer's response.

RESPONSE FORMAT when rejecting off-topic questions:
1-2 sentences explaining the question is outside the session scope, ending with a
friendly redirect to the session material. Example:
"That's outside what we're studying today — I'm here to help with [topic].
Is there something from the material you'd like to explore?"

{grounding_block}""",
    )
