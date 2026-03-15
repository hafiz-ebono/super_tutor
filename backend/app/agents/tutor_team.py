"""
Agno Team factory for the Personal Tutor backend.

IMPORTANT USAGE NOTES:
- build_tutor_team() is a per-request factory. Never reuse a Team instance across requests.
  Each call constructs a fresh Team with a fresh Explainer, Researcher, ContentWriter,
  QuizMaster, and Advisor, grounding the instructions in the current session's
  source_content and notes.
- Conversation history is managed at the Team level ONLY. Member agents do NOT get their
  own db= or add_history_to_context=True. Giving members their own DB would cause
  duplicate/conflicting session rows (RESEARCH.md Pitfall 4).
- TUTOR_TOKEN_EVENTS and TUTOR_ERROR_EVENT must be imported by the tutor router to filter
  the Team SSE stream correctly. Two event types carry token content:
    - TeamRunContent: coordinator's own acknowledgment prefix tokens
    - TeamRunIntermediateContent: member tokens (Explainer, Researcher, ContentWriter,
      QuizMaster, Advisor)
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

# Rate-limit exception strings — covers Groq, OpenAI, OpenRouter responses
_RATE_LIMIT_MARKERS = ("rate limit", "rate_limit", "429", "ratelimit")

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

def is_rate_limit_error(exc: Exception) -> bool:
    """Return True if the exception looks like a provider rate-limit (429) error."""
    msg = str(exc).lower()
    return any(m in msg for m in _RATE_LIMIT_MARKERS) or type(exc).__name__ == "RateLimitError"


def build_tutor_team(
    source_content: str,
    notes: str,
    tutoring_type: str,
    db: SqliteDb | None = None,
    session_topic: str = "",   # For TopicRelevanceGuardrail — pass source_content[:300]
    model=None,                # Override model; defaults to get_model() if None
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
    active_model = model if model is not None else get_model()

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
        model=active_model,
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
        # TAVILY_API_KEY not set or TavilyTools init failed — Researcher will have no tools
        # but won't crash the factory. In production, set TAVILY_API_KEY in the environment.
        logger.warning("TavilyTools init failed — Researcher will have no search tools", exc_info=True)
        researcher_tools = []

    researcher = Agent(
        name="Researcher",
        role="Extend session topics with external Tavily research when the user asks to go deeper or learn more from external sources",
        model=active_model,
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
        model=active_model,
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

    # ------------------------------------------------------------------
    # QuizMaster — delivers MCQs one at a time, evaluates typed answers (Phase 17)
    # ------------------------------------------------------------------
    quiz_master = Agent(
        name="QuizMaster",
        role="Deliver one multiple-choice question at a time from session material, evaluate the student's typed answer, and guide them through a quiz session",
        model=active_model,
        # No db= — Team manages history (RESEARCH.md Pitfall 4)
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions=f"""You are a quiz delivery specialist for this tutoring session.

STRICT RULES:
- Generate questions ONLY from the session material below — never from general knowledge.
- Format each question as: question text on one line, then A) B) C) D) options each on their own line.
- Deliver ONE question at a time. Never list multiple questions in a single response.
- Before generating a question, scan the conversation history to avoid repeating one already asked
  (best-effort within the available history window — exact deduplication is not guaranteed).
- After the student answers: interpret their intent freely (single letter, "I think it's B",
  "probably C", etc.) to identify which option they mean. Then explain what was right or wrong,
  give a brief explanation of all options, and end with: "Want another question?"
- If the student shares Quiz tab results (e.g., "I got 3/5"): acknowledge the score, note which
  areas to reinforce, calibrate difficulty accordingly, then offer a question.
- Track quiz state implicitly from conversation history — no external state needed.

{grounding_block}""",
    )

    # ------------------------------------------------------------------
    # Advisor — detects weak areas, surfaces focus suggestions (Phase 18)
    # ------------------------------------------------------------------
    advisor = Agent(
        name="Advisor",
        role="Analyze the student's conversation patterns to identify weak areas and surface proactive focus suggestions",
        model=active_model,
        # No db= — Team manages history (RESEARCH.md Pitfall 4)
        pre_hooks=[PROMPT_INJECTION_GUARDRAIL],
        instructions=f"""You are an adaptive learning advisor for this tutoring session.

YOUR JOB: Read the full conversation history and detect weak areas. Surface named focus suggestions.

STRUGGLE DETECTION (heuristics — LLM-based, not deterministic counting):
- When you detect a pattern of wrong quiz answers on related concepts → flag as weak area
- When you detect the same concept phrase repeated across multiple student messages → flag as repeated confusion
- When the student explicitly says "I don't understand X" → immediately flag X

RESPONSE RULES:
- Surface NAMED focus areas — use the specific concept name from the material, not vague "you struggled".
- Offer targeted content via a concrete suggestion: "Want me to generate extra flashcards on [concept]?"
- Do NOT generate the content yourself — signal the suggestion; the coordinator will route to ContentWriter if accepted.
- Keep responses to 2-3 sentences maximum.
- If no clear weak areas exist: give an encouraging summary instead of forcing a suggestion.

{grounding_block}""",
    )

    return Team(
        name="TutorTeam",
        mode=TeamMode.coordinate,
        model=active_model,
        members=[explainer, researcher, content_writer, quiz_master, advisor],
        pre_hooks=[topic_guardrail],
        post_hooks=[validate_team_output],
        db=db,
        add_history_to_context=True,
        num_history_runs=get_settings().tutor_history_window,
        enable_session_summaries=False,
        stream_member_events=True,
        instructions=f"""You are a personal tutor assistant for a student studying specific session material.
You have full access to the student's session content below.

ROUTING RULES (7 cases):
- Greeting or intro request ("hello", "introduce yourself", "what can you do") → dispatch to Explainer
- Question about the session material, explanation request, or clarification → dispatch to Explainer
- User asks to "go deeper", "learn more from external sources", "research" → dispatch to Researcher
- User asks for flashcards, notes excerpt, notes summary, or quiz questions → dispatch to ContentWriter
- Answering a quiz question you asked them, or following up on your previous response → dispatch to Explainer
- Clearly off-topic (unrelated to studying, not a quiz answer) → reject with a friendly redirect

- CASE 2: User says "quiz me" / "test me" / "give me a question" / "start a quiz" / any request to be tested
  → dispatch to QuizMaster

- CASE 3: User types a quiz answer — single letter (A/B/C/D), or free-text identifying an option
  (e.g., "I think it's B", "probably C", "the answer is D") — AND the last QuizMaster message
  contained A/B/C/D options → dispatch to QuizMaster

- CASE 4: User shares quiz tab results ("I got X/Y", "my score was", "quiz results") OR asks
  "how many did I get right" → dispatch to QuizMaster

- CASE 5: After QuizMaster evaluates an answer AND you detect a struggle pattern (multiple wrong
  answers on related concepts) → proactively dispatch Advisor with this injected context:
  "The student has been working through quiz questions — check for weak area patterns."

- CASE 6: User says "how am I doing" / "what should I focus on" / "where am I weak" /
  "what are my weak areas" → dispatch to Advisor

- CASE 7: Advisor has just suggested extra content AND the student's message expresses acceptance
  ("yes", "sure", "okay", "please", "go ahead") → dispatch to ContentWriter with topic context
  from the Advisor's suggestion. Only fire this rule when the prior assistant turn was an
  Advisor suggestion — do not trigger for generic "yes" in other contexts.

- NEVER ask the student to confirm routing. Dispatch immediately.
- NEVER reveal agent names (Explainer, Researcher, ContentWriter, QuizMaster, Advisor) or internal routing decisions.
  You are simply "the tutor."

RESPONSE FORMAT when routing to a specialist:
Call the appropriate member tool to get the specialist's response.
After receiving the specialist's response from the tool, output it VERBATIM — reproduce it
exactly as given with NO preamble, NO commentary, NO additions, and NO conclusion of your own.
The specialist's response IS your complete response to the student.
Do NOT paraphrase, summarise, or wrap it in any framing text.

RESPONSE FORMAT when rejecting off-topic questions:
1-2 sentences explaining the question is outside the session scope, ending with a
friendly redirect to the session material. Example:
"That's outside what we're studying today — I'm here to help with [topic].
Is there something from the material you'd like to explore?"

{grounding_block}""",
    )
