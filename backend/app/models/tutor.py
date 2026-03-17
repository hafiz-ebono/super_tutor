from pydantic import BaseModel, Field
from typing import Literal


class TutorStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    tutoring_type: Literal["micro_learning", "teaching_a_kid", "advanced"]
    session_id: str  # required; router loads source_content + notes from SQLite using this ID
    tutor_reset_id: str = Field(default="v0", max_length=64, pattern=r'^[a-zA-Z0-9_-]+$')
    # tutor_reset_id namespaces the agno Team session: `tutor:{session_id}:{tutor_reset_id}`.
    # Changing it starts a fresh conversation in SQLite without deleting any rows.

    model_config = {"str_strip_whitespace": True}
