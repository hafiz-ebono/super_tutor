from app.config import get_settings
from app.extraction.jina import fetch_via_jina
from app.extraction.trafilatura_extractor import fetch_via_trafilatura
from app.extraction.playwright_extractor import fetch_via_playwright


class ExtractionError(Exception):
    def __init__(self, kind: str, message: str = ""):
        self.kind = kind
        self.message = message
        super().__init__(message or kind)


PAYWALL_DOMAINS = ["nytimes.com", "wsj.com", "ft.com", "bloomberg.com", "economist.com"]


def _classify_failure(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        return "invalid_url"
    if any(d in url for d in PAYWALL_DOMAINS):
        return "paywall"
    return "empty"


async def extract_content(url: str) -> str:
    """
    Tries Jina → trafilatura → Playwright. Returns text or raises ExtractionError.
    Skips Jina if JINA_API_KEY is not configured.
    """
    settings = get_settings()

    # Layer 1: Jina Reader (skip if no API key)
    if settings.jina_api_key:
        text = await fetch_via_jina(url, settings.jina_api_key)
        if text:
            return text

    # Layer 2: trafilatura (sync)
    text = fetch_via_trafilatura(url)
    if text:
        return text

    # Layer 3: Playwright (async headless browser)
    text = await fetch_via_playwright(url)
    if text:
        return text

    raise ExtractionError(
        kind=_classify_failure(url),
        message="Could not extract readable content from this URL",
    )
