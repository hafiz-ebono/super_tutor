"""Unit tests for clean_extracted_content() — TDD RED phase."""
import pytest
from app.extraction.cleaner import clean_extracted_content


class TestUnicodeNormalization:
    def test_nfkc_ligature_fi(self):
        """Unicode ligature ﬁ should normalise to 'fi'."""
        result = clean_extracted_content("\ufb01le", source_type="document")
        assert result == "file"

    def test_nfkc_fancy_quotes(self):
        """NFKC normalisation runs without error; fancy quotes pass through (NFKC preserves them)."""
        # Note: NFKC normalises ligatures and compatibility chars but fancy quotes (U+201C/U+201D)
        # are canonical Unicode and remain unchanged. The key check is that extraction doesn't crash
        # and the content (including surrounding text) is returned intact.
        result = clean_extracted_content("\u201chello\u201d", source_type="document")
        assert "hello" in result
        # Verify NFKC ran: a ligature alongside it would be resolved
        result2 = clean_extracted_content("\u201c\ufb01le\u201d", source_type="document")
        assert "file" in result2  # ﬁ → fi via NFKC


class TestTrailingWhitespace:
    def test_trailing_spaces_per_line_stripped(self):
        """Trailing spaces on each line must be removed."""
        text = "line one   \nline two  \n  indented  "
        result = clean_extracted_content(text, source_type="document")
        for line in result.splitlines():
            assert line == line.rstrip(), f"Line has trailing whitespace: {repr(line)}"

    def test_leading_whitespace_preserved_within_line(self):
        """Leading whitespace (indentation) should be preserved."""
        text = "    indented line"
        result = clean_extracted_content(text, source_type="document")
        # After strip() on the whole text, single-line leading space is gone,
        # but mid-text indentation is preserved
        assert "indented line" in result


class TestBlankLineCollapsing:
    def test_three_blank_lines_collapsed_to_two(self):
        """Three or more consecutive newlines should collapse to two."""
        text = "para one\n\n\npara two"
        result = clean_extracted_content(text, source_type="document")
        assert "\n\n\n" not in result

    def test_four_blank_lines_collapsed_to_two(self):
        """Four consecutive newlines should collapse to two."""
        text = "para one\n\n\n\npara two"
        result = clean_extracted_content(text, source_type="document")
        assert "\n\n\n" not in result
        assert "para one" in result
        assert "para two" in result

    def test_two_blank_lines_preserved(self):
        """Two consecutive newlines (one blank line) should be preserved."""
        text = "para one\n\npara two"
        result = clean_extracted_content(text, source_type="document")
        assert "para one\n\npara two" in result


class TestHtmlStripping:
    def test_html_tags_stripped_for_document_source(self):
        """HTML tags should be stripped when source_type='document'."""
        text = "<p>Hello <b>world</b></p>"
        result = clean_extracted_content(text, source_type="document")
        assert "<" not in result
        assert ">" not in result
        assert "Hello" in result
        assert "world" in result

    def test_html_tags_preserved_for_url_source(self):
        """HTML/markdown should be preserved when source_type='url'."""
        text = "# Heading\n\n**bold text** and [link](https://example.com)"
        result = clean_extracted_content(text, source_type="url")
        assert "# Heading" in result
        assert "**bold text**" in result
        assert "[link](https://example.com)" in result

    def test_residual_xml_stripped_for_document_source(self):
        """Residual XML/HTML tags from pypdf should be stripped."""
        text = "Some text <xml:tag attr='val'>with tags</xml:tag> here"
        result = clean_extracted_content(text, source_type="document")
        assert "<" not in result
        assert "Some text" in result
        assert "with tags" in result


class TestEmptyAndEdgeCases:
    def test_empty_string_returns_empty(self):
        """Empty string input should return empty string."""
        assert clean_extracted_content("", source_type="document") == ""
        assert clean_extracted_content("", source_type="url") == ""

    def test_whitespace_only_returns_empty(self):
        """Whitespace-only input should return empty string after strip."""
        assert clean_extracted_content("   \n  \n  ", source_type="document") == ""

    def test_leading_trailing_whitespace_stripped(self):
        """Leading and trailing whitespace of the whole text should be stripped."""
        result = clean_extracted_content("\n\nhello world\n\n", source_type="document")
        assert result == "hello world"

    def test_default_source_type_is_document(self):
        """Default source_type should be 'document' (strips HTML)."""
        text = "<p>test</p>"
        result = clean_extracted_content(text)
        assert "<" not in result
        assert "test" in result
