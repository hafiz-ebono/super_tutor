"""Tests for Settings: verifies generic agent_api_key replaces provider-specific keys."""


def test_settings_has_agent_api_key():
    from app.config import Settings
    fields = Settings.model_fields
    assert "agent_api_key" in fields


def test_settings_no_provider_specific_keys():
    from app.config import Settings
    fields = Settings.model_fields
    assert "openai_api_key" not in fields
    assert "anthropic_api_key" not in fields
    assert "groq_api_key" not in fields


def test_agent_api_key_defaults_to_empty_string():
    from app.config import Settings
    s = Settings()
    assert s.agent_api_key == ""
