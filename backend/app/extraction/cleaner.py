"""
Text cleaning utility for extracted content.

Shared by the URL extraction path (trafilatura) and the document extraction
path (pypdf / python-docx). Apply immediately after extraction, before the
text is passed into any workflow or stored in session state.
"""
import re
import unicodedata


def clean_extracted_content(text: str, source_type: str = "document") -> str:
    """
    Normalise extracted text for use as LLM grounding material.

    Args:
        text: Raw extracted text.
        source_type: "document" (pypdf/.docx — strip residual HTML tags) or
                     "url" (trafilatura markdown output — preserve markup).

    Returns:
        Cleaned, stripped text.
    """
    # 1. Unicode normalisation — collapses ligatures (ﬁ→fi), fancy quotes, etc.
    text = unicodedata.normalize("NFKC", text)

    # 2. Strip trailing whitespace from each line (preserve leading indentation)
    text = "\n".join(line.rstrip() for line in text.splitlines())

    # 3. Collapse runs of 3+ blank lines down to a single blank line (two newlines)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 4. Strip residual HTML/XML tags for document source type only
    #    (trafilatura already produces clean markdown — don't alter its structure)
    if source_type == "document":
        text = re.sub(r"<[^>]+>", "", text)

    # 5. Strip leading/trailing whitespace from the whole text
    return text.strip()
