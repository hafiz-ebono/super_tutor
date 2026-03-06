from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import List, Any


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
    agent_fallback_model: str = ""     # optional fallback model ID (same provider/key)
    agent_max_retries: int = 3         # max attempts before giving up

    # Trace storage — SQLite db for AgentOS run traces
    trace_db_path: str = "tmp/super_tutor_traces.db"  # override with TRACE_DB_PATH env var

    # Agno Control Plane — remote telemetry at app.agno.com (Phase 7)
    agno_api_key: str = ""            # set AGNO_API_KEY env var; get from app.agno.com
    agno_telemetry: bool = True       # set AGNO_TELEMETRY=false to disable; SDK reads this env var

    # URL extraction
    jina_api_key: str = ""

    # CORS
    allowed_origins: List[str] | str = ["http://localhost:3000"]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",")]
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()
