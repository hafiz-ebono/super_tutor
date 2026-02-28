import logging

from app.config import get_settings

logger = logging.getLogger("super_tutor.model_factory")


def get_model():
    settings = get_settings()
    provider = settings.agent_provider.lower()
    model_id = settings.agent_model
    api_key = settings.agent_api_key

    if provider == "anthropic":
        from agno.models.anthropic import Claude
        logger.debug("Model resolved: provider=%s model=%s", provider, model_id)
        return Claude(id=model_id, api_key=api_key)
    elif provider == "groq":
        from agno.models.groq import Groq
        logger.debug("Model resolved: provider=%s model=%s", provider, model_id)
        return Groq(id=model_id, api_key=api_key)
    elif provider == "openrouter":
        from agno.models.openai import OpenAIChat
        logger.debug("Model resolved: provider=%s model=%s", provider, model_id)
        return OpenAIChat(
            id=model_id,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
    else:
        # Default: OpenAI
        from agno.models.openai import OpenAIChat
        logger.debug("Model resolved: provider=%s model=%s", provider, model_id)
        return OpenAIChat(id=model_id, api_key=api_key)


def get_fallback_model():
    """Return a model object for the configured fallback model, or None if unset."""
    settings = get_settings()
    if not settings.agent_fallback_model:
        return None

    provider = settings.agent_provider.lower()
    model_id = settings.agent_fallback_model
    api_key = settings.agent_api_key

    if provider == "anthropic":
        from agno.models.anthropic import Claude
        logger.debug("Fallback model resolved: provider=%s model=%s", provider, model_id)
        return Claude(id=model_id, api_key=api_key)
    elif provider == "groq":
        from agno.models.groq import Groq
        logger.debug("Fallback model resolved: provider=%s model=%s", provider, model_id)
        return Groq(id=model_id, api_key=api_key)
    elif provider == "openrouter":
        from agno.models.openai import OpenAIChat
        logger.debug("Fallback model resolved: provider=%s model=%s", provider, model_id)
        return OpenAIChat(
            id=model_id,
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )
    else:
        # Default: OpenAI
        from agno.models.openai import OpenAIChat
        logger.debug("Fallback model resolved: provider=%s model=%s", provider, model_id)
        return OpenAIChat(id=model_id, api_key=api_key)
