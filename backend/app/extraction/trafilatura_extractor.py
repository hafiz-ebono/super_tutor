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

if __name__ == "__main__":
    print(fetch_via_trafilatura("https://en.wikipedia.org/wiki/Cryptocurrency"))
