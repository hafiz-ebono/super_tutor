from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # AI provider config
    agent_provider: str = "openai"
    agent_model: str = "gpt-4o"
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    # URL extraction
    jina_api_key: str = ""

    # CORS
    allowed_origins: List[str] = ["http://localhost:3000"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
