import logging

from app.config import get_settings

logger = logging.getLogger("super_tutor.model_factory")

# SDK retries: handled by the OpenAI http client inside each agent.run() call.
# Step retries: handled by agno's Step(max_retries=) for whole-step failures.
_SDK_RETRIES = 2


def _build_model(provider: str, model_id: str, api_key: str):
    if provider == "anthropic":
        from agno.models.anthropic import Claude
        return Claude(id=model_id, api_key=api_key)
    elif provider == "groq":
        from agno.models.groq import Groq
        try:
            return Groq(id=model_id, api_key=api_key, max_retries=_SDK_RETRIES)
        except TypeError:
            return Groq(id=model_id, api_key=api_key)
    elif provider == "openai":
        from agno.models.openai import OpenAIChat
        return OpenAIChat(id=model_id, api_key=api_key, max_retries=_SDK_RETRIES)
    elif provider == "mistral":
        # Use native MistralChat instead of OpenAIChat-compat: the native class
        # explicitly sets "type": "function" on every tool call dict (streaming and
        # non-streaming).  OpenAIChat passes through raw SDK objects, and Mistral's
        # streaming deltas omit the type field, causing agno's get_function_call_for_tool_call
        # to silently drop every tool call (type == None != "function").
        from agno.models.mistral import MistralChat
        return MistralChat(id=model_id, api_key=api_key)
    else:
        from agno.models.openai import OpenAIChat
        kwargs = dict(id=model_id, api_key=api_key, max_retries=_SDK_RETRIES)
        if provider == "openrouter":
            kwargs["base_url"] = "https://openrouter.ai/api/v1"
        return OpenAIChat(**kwargs)


def get_model():
    settings = get_settings()
    provider = settings.agent_provider.lower()
    model_id = settings.agent_model
    api_key = settings.agent_api_key
    logger.debug("Model resolved: provider=%s model=%s", provider, model_id)
    return _build_model(provider, model_id, api_key)


def get_fallback_model():
    """Return fallback model if configured, else None."""
    settings = get_settings()
    if not settings.agent_fallback_provider or not settings.agent_fallback_model:
        return None
    provider = settings.agent_fallback_provider.lower()
    model_id = settings.agent_fallback_model
    api_key = settings.agent_fallback_api_key or settings.agent_api_key
    logger.debug("Fallback model resolved: provider=%s model=%s", provider, model_id)
    return _build_model(provider, model_id, api_key)
