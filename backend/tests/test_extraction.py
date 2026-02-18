"""
TDD tests for the URL content extraction chain.
Tests cover: Jina success, Jina fallback, trafilatura fallback, Playwright fallback,
all-layers-fail, error kind classification, and Jina-skip when api_key is empty.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

LONG_TEXT = "x" * 201   # > 200 chars — counts as valid content
SHORT_TEXT = "short"    # < 200 chars — not usable content


# ──────────────────────────────────────────────────────────────
# Test 1: Jina returns usable content → returns Jina text, no fallback
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jina_success_returns_jina_text():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=LONG_TEXT)) as mock_jina,
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=LONG_TEXT) as mock_traf,
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=LONG_TEXT)) as mock_pw,
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = "test-key"
        from app.extraction.chain import extract_content
        result = await extract_content("https://example.com")
        assert result == LONG_TEXT
        mock_jina.assert_called_once()
        mock_traf.assert_not_called()
        mock_pw.assert_not_called()


# ──────────────────────────────────────────────────────────────
# Test 2: Jina returns short text → falls back to trafilatura
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jina_short_falls_back_to_trafilatura():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=None)) as mock_jina,
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=LONG_TEXT) as mock_traf,
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=None)) as mock_pw,
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = "test-key"
        from app.extraction.chain import extract_content
        result = await extract_content("https://example.com")
        assert result == LONG_TEXT
        mock_jina.assert_called_once()
        mock_traf.assert_called_once()
        mock_pw.assert_not_called()


# ──────────────────────────────────────────────────────────────
# Test 3: Jina raises exception + trafilatura returns None → falls back to Playwright
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jina_exception_traf_none_falls_back_to_playwright():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=None)) as mock_jina,
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=None) as mock_traf,
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=LONG_TEXT)) as mock_pw,
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = "test-key"
        from app.extraction.chain import extract_content
        result = await extract_content("https://example.com")
        assert result == LONG_TEXT
        mock_jina.assert_called_once()
        mock_traf.assert_called_once()
        mock_pw.assert_called_once()


# ──────────────────────────────────────────────────────────────
# Test 4: All three layers fail → raises ExtractionError
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_all_layers_fail_raises_extraction_error():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=None),
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = "test-key"
        from app.extraction.chain import extract_content, ExtractionError
        with pytest.raises(ExtractionError):
            await extract_content("https://unknown-domain-xyz.com")


# ──────────────────────────────────────────────────────────────
# Test 5: ExtractionError.kind == "invalid_url" when URL has no scheme
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_error_kind_invalid_url_no_scheme():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=None),
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = ""
        from app.extraction.chain import extract_content, ExtractionError
        with pytest.raises(ExtractionError) as exc_info:
            await extract_content("not-a-url")
        assert exc_info.value.kind == "invalid_url"


# ──────────────────────────────────────────────────────────────
# Test 6: ExtractionError.kind == "paywall" for nytimes.com
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_error_kind_paywall_for_nytimes():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=None),
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = "test-key"
        from app.extraction.chain import extract_content, ExtractionError
        with pytest.raises(ExtractionError) as exc_info:
            await extract_content("https://nytimes.com/article/test")
        assert exc_info.value.kind == "paywall"


# ──────────────────────────────────────────────────────────────
# Test 7: ExtractionError.kind == "empty" for unknown domain
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_error_kind_empty_for_unknown_domain():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=None),
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = "test-key"
        from app.extraction.chain import extract_content, ExtractionError
        with pytest.raises(ExtractionError) as exc_info:
            await extract_content("https://some-obscure-site.com/article")
        assert exc_info.value.kind == "empty"


# ──────────────────────────────────────────────────────────────
# Test 8: Jina API key empty → Jina layer is NEVER called
# ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_jina_skipped_when_api_key_empty():
    with (
        patch("app.extraction.chain.fetch_via_jina", new=AsyncMock(return_value=LONG_TEXT)) as mock_jina,
        patch("app.extraction.chain.fetch_via_trafilatura", return_value=LONG_TEXT),
        patch("app.extraction.chain.fetch_via_playwright", new=AsyncMock(return_value=None)),
        patch("app.extraction.chain.get_settings") as mock_settings,
    ):
        mock_settings.return_value.jina_api_key = ""  # empty → skip Jina
        from app.extraction.chain import extract_content
        result = await extract_content("https://example.com")
        mock_jina.assert_not_called()
        assert result == LONG_TEXT  # came from trafilatura
