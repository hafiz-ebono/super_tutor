"""
Agno Team factory for the Personal Tutor backend.

IMPORTANT USAGE NOTES:
- build_tutor_team() is a per-request factory. Never reuse a Team instance across requests.
  Each call constructs a fresh Team with a fresh Explainer, Researcher, and ContentWriter,
  grounding the instructions in the current session's source_content and notes.
- Conversation history is managed at the Team level ONLY. Member agents do NOT get their
  own db= or add_history_to_context=True. Giving members their own DB would cause
  duplicate/conflicting session rows (RESEARCH.md Pitfall 4).
- TUTOR_TOKEN_EVENTS and TUTOR_ERROR_EVENT must be imported by the tutor router to filter
  the Team SSE stream correctly. Two event types carry token content:
    - TeamRunContent: coordinator's own acknowledgment prefix tokens
    - TeamRunIntermediateContent: member tokens (Explainer, Researcher, ContentWriter)
  Missing either causes partial responses.
- TopicRelevanceGuardrail is attached as a Team pre_hook — it fires before coordinator
  dispatch, using the session_topic parameter as judge context (GUARD-01).
- validate_team_output is attached as a Team post_hook — rejects empty/short responses
  after the full Team run completes (GUARD-02).
"""

import logging

from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from agno.run.team import TeamRunEvent
from agno.team import Team
from agno.team.mode import TeamMode
from agno.tools.tavily import TavilyTools

logger = logging.getLogger("super_tutor.tutor_team")

from app.agents.guardrails import (
    PROMPT_INJECTION_GUARDRAIL,
    TopicRelevanceGuardrail,
    validate_team_output,
)
from app.agents.model_factory import get_model
from app.config import get_settings

# ---------------------------------------------------------------------------
# Constants — imported by the tutor router to filter the SSE stream
# ---------------------------------------------------------------------------

TUTOR_TOKEN_EVENTS = {
    TeamRunEvent.run_content.value,               # "TeamRunContent" — coordinator prefix tokens
    TeamRunEvent.run_intermediate_content.value,  # "TeamRunIntermediateContent" — member tokens
}
TUTOR_ERROR_EVENT = TeamRunEvent.run_error.value  # "TeamRunError"


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _build_grounding_block(source_content: str, notes: str) -> str:
    """
    Build a grounding context block for injection into all member system prompts.

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
    session_topic: str = "",   # For TopicRelevanceGuardrail — pass source_content[:300]
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
        session_topic:  Short excerpt (typically source_content[:300]) passed to
                        TopicRelevanceGuardrail as judge context. Defaults to empty string,
                        in which case the guardrail falls back to source_content[:300].

    Returns:
        A configured Team ready for team.arun(message, stream=True, session_id=...).

    Raises:
        ValueError: If source_content is empty after stripping. The router should have
                    already returned HTTP 422, so this is a programming-level guard.
    """
    if not source_content.strip():
        raise ValueError("source_content is required to build the tutor team")

    grounding_block = _build_grounding_block(source_content, notes)

    # Instantiate guardrail with session topic context
    topic_guardrail = TopicRelevanceGuardrail(
        session_topic=session_topic or source_content[:300]
    )

    # ------------------------------------------------------------------
    # Explainer — answers questions strictly from session material
    # ------------------------------------------------------------------
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

    # ------------------------------------------------------------------
    # Researcher — extends topics with external Tavily research (TEAM-04)
    # ------------------------------------------------------------------
    try:
        researcher_tools = [TavilyTools()]
    except Exception:
        # TAVILY_API_KEY not set — Researcher will have no tools but won't crash the factory.
        # In production, set TAVILY_API_KEY in the environment.
        logger.warning("TAVILY_API_KEY not set — Researcher agent will have no search tools")
        researcher_tools = []

    researcher = Agent(
        name="Researcher",
        role="Extend session topics with external Tavily research when the user asks to go deeper or learn more from external sources",
        model=get_model(),
        # No db= — Team manages history (RESEARCH.md Pitfall 4 / anti-pattern 1)
        tools=researcher_tools,
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions=f"""You are a research specialist for this tutoring session.
When dispatched, search for deeper information on the topic and synthesize findings.
Ground your response in BOTH the search results AND the session material below.
Present findings as educational prose. Cite sources at the end.
Do not introduce information unrelated to the session topic.

RESPONSE FORMAT: Plain text prose with source citations at the end.
Keep the response focused on what the student asked to explore further.

{grounding_block}""",
    )

    # ------------------------------------------------------------------
    # ContentWriter — generates notes, flashcards, quiz as plain markdown (TEAM-05)
    # ------------------------------------------------------------------
    content_writer = Agent(
        name="ContentWriter",
        role="Generate additional study content (notes excerpts, flashcards, or quiz questions) inline in the tutor chat as plain markdown",
        model=get_model(),
        # No db= — Team manages history (RESEARCH.md Pitfall 4 / anti-pattern 1)
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions=f"""You are a content generation specialist for this tutoring session.
Generate study content based on the student's request using ONLY the session material below.

OUTPUT FORMAT RULES (strictly enforced — never output raw JSON):
- For notes excerpts: Markdown prose with ## headings and **bold** key terms
- For flashcards: A markdown table with | Front | Back | columns (2-5 cards max for inline display)
- For quiz questions: Numbered markdown list with A/B/C/D options; mark correct answer with "(correct)"

Always produce the content inline — no preamble like "Here are your flashcards:".
Generate 2-5 items per request unless the student specifies more.
Never invent content not found in the session material.

{grounding_block}""",
    )

    return Team(
        name="TutorTeam",
        mode=TeamMode.coordinate,
        model=get_model(),
        members=[explainer, researcher, content_writer],
        pre_hooks=[topic_guardrail],
        post_hooks=[validate_team_output],
        db=db,
        add_history_to_context=True,
        num_history_runs=get_settings().tutor_history_window,
        enable_session_summaries=False,
        stream_member_events=True,
        instructions=f"""You are a personal tutor assistant for a student studying specific session material.
You have full access to the student's session content below.

ROUTING RULES:
- Question about the session material, explanation request, or clarification → dispatch to Explainer
- User asks to "go deeper", "learn more about from external sources", "research", or "tell me more externally" → dispatch to Researcher
- User asks for flashcards, notes excerpt, notes summary, or quiz questions → dispatch to ContentWriter
- Off-topic messages (unrelated to studying this session) → reject directly with a friendly redirect
- NEVER ask the student to confirm routing. Dispatch immediately.
- NEVER reveal agent names (Explainer, Researcher, ContentWriter) or internal routing decisions.
  You are simply "the tutor."

RESPONSE FORMAT when routing to a specialist:
Begin with exactly ONE sentence of acknowledgment (e.g., "Great question — let me explain."),
then stop. The specialist will continue with the detailed answer.
Do not add any conclusion or summary after the specialist's response.

RESPONSE FORMAT when rejecting off-topic questions:
1-2 sentences explaining the question is outside the session scope, ending with a
friendly redirect to the session material. Example:
"That's outside what we're studying today — I'm here to help with [topic].
Is there something from the material you'd like to explore?"

{grounding_block}""",
    )
