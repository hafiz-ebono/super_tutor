import logging
import trafilatura

logger = logging.getLogger("super_tutor.extraction")


def fetch_via_trafilatura(url: str) -> str | None:
    """Returns extracted markdown text or None."""
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        logger.debug("trafilatura fetch returned nothing — url=%s", url)
        return None
    text = trafilatura.extract(
        downloaded,
        include_tables=True,
        no_fallback=False,
        output_format="markdown",
    )
    if text and len(text) > 200:
        return text
    logger.debug("trafilatura content too short — url=%s chars=%d", url, len(text) if text else 0)
    return None

if __name__ == "__main__":
    print(fetch_via_trafilatura("https://en.wikipedia.org/wiki/Cryptocurrency"))
