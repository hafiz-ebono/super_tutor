import trafilatura


def fetch_via_trafilatura(url: str) -> str | None:
    """Returns extracted markdown text or None."""
    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return None
    text = trafilatura.extract(
        downloaded,
        include_tables=True,
        no_fallback=False,
        output_format="markdown",
    )
    return text if text and len(text) > 200 else None


def extract_from_html(html: str) -> str | None:
    """Used by Playwright layer to extract from already-fetched HTML."""
    text = trafilatura.extract(
        html,
        include_tables=True,
        output_format="markdown",
    )
    return text if text and len(text) > 200 else None
