from pydantic import field_validator, model_validator
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
    agent_base_url: str = ""           # optional base URL override for OpenAI-compatible providers
    agent_fallback_provider: str = "" # fallback provider (if different from primary, e.g. "openrouter")
    agent_fallback_model: str = ""     # optional fallback model ID
    agent_fallback_api_key: str = ""  # fallback API key (if different provider; defaults to agent_api_key)
    agent_max_retries: int = 3         # max attempts before giving up

    # Storage paths — override via env vars
    trace_db_path: str = "tmp/super_tutor_traces.db"  # AgentOS traces + workflow session state
    status_db_path: str = "tmp/session_status.db"     # session lifecycle status (pending/complete/failed)

    # Concurrency limits
    max_concurrent_sessions: int = 20   # max background AI tasks running at once (returns 429 when exceeded)
    rate_limit_sessions: str = "20/minute"   # per-IP limit for POST /sessions
    rate_limit_chat: str = "60/minute"       # per-IP limit for POST /chat/stream
    rate_limit_upload: str = "10/minute"     # per-IP limit for POST /sessions/upload

    # Upload
    upload_max_bytes: int = 20 * 1024 * 1024    # 20 MB; override with UPLOAD_MAX_BYTES

    # Document extraction
    document_truncation_limit: int = 50_000      # chars; override with DOCUMENT_TRUNCATION_LIMIT
    scanned_pdf_threshold: int = 200             # min chars to treat a PDF as text-based

    # Chat
    chat_history_window: int = 20                # past turns included in context; override with CHAT_HISTORY_WINDOW

    # Tutor
    tutor_history_window: int = 10               # past Team runs included in tutor context; override with TUTOR_HISTORY_WINDOW
    rate_limit_tutor: str = "60/minute"          # per-IP limit for POST /tutor/{session_id}/stream
    debug: bool = False                          # enable agno Team debug_mode; override with DEBUG=true

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

    @model_validator(mode="after")
    def warn_if_api_key_missing(self) -> "Settings":
        local_providers = {"local", "ollama", "llamacpp"}
        if self.agent_provider not in local_providers and not self.agent_api_key:
            import logging
            logging.getLogger("super_tutor.config").warning(
                "agent_api_key is not set for provider '%s' — LLM calls will fail at runtime",
                self.agent_provider,
            )
        return self


@lru_cache()
def get_settings() -> Settings:
    return Settings()
