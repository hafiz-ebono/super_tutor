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
        telemetry=True,
        instructions=f"""{persona}

Generate structured study notes from the provided content.
Format as clean markdown: use headings (##), bullet points, and **bold key terms**.
Write a comprehensive study guide that covers all major concepts.
Adapt the depth, vocabulary, and tone to match your role above.
Do not include any preamble like "Here are your notes:" — output the notes directly.""",
    )
