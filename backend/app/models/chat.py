from pydantic import BaseModel, Field
from typing import Literal


class ChatStreamRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    tutoring_type: Literal["micro_learning", "teaching_a_kid", "advanced"]
    session_id: str  # required; router loads notes from SQLite using this ID
    chat_reset_id: str | None = None  # optional; appended to agno session key so reset starts fresh history

    model_config = {"str_strip_whitespace": True}
