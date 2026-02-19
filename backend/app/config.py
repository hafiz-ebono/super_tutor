from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )

    # AI provider config — set all three in .env
    agent_provider: str = "openai"     # openai | anthropic | groq | openrouter
    agent_model: str = "gpt-4o"        # model ID valid for chosen provider
    agent_api_key: str = ""            # single key for whichever provider is active

    # URL extraction
    jina_api_key: str = ""

    # CORS
    allowed_origins: List[str] = ["http://localhost:3000"]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
