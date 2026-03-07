from agno.agent import Agent
from agno.db.sqlite import SqliteDb
from app.agents.model_factory import get_model
from app.agents.personas import PERSONAS


def build_notes_agent(tutoring_type: str, db: SqliteDb | None = None) -> Agent:
    persona = PERSONAS[tutoring_type]
    return Agent(
        name="NotesAgent",
        model=get_model(),
        db=db,
        enable_session_summaries=True,
        instructions=f"""{persona}

You are producing comprehensive study notes from the provided content.

**Coverage rule — this is your primary constraint:**
Work through the content from beginning to end.
Every section, concept, definition, example, argument, and nuance present in the source MUST appear in your notes.
Do NOT skip sections because they seem minor. Do NOT summarise multiple distinct points into one vague bullet.
If the source is long, your notes should be long. If the source is short, your notes should still capture every point it makes.

**Format:**
- Use markdown headings (##, ###) that mirror the structure of the source
- Bold every key term on first use: **term**
- Use bullet points for lists of facts, steps, or examples
- Write prose sentences where the source makes an argument or explains a process
- Adapt depth, vocabulary, and tone to match your role above

**Do not** include any preamble such as "Here are your notes:" — output the notes directly.""",
    )
