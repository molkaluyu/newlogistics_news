"""
Tests for processing/cleaner.py -- clean_text() and clean_title().
"""

import pytest

from processing.cleaner import clean_text, clean_title


# ---------------------------------------------------------------------------
# clean_text
# ---------------------------------------------------------------------------


class TestCleanTextStripsHtml:
    """clean_text should remove all HTML tags from the input."""

    def test_simple_tags(self):
        assert clean_text("<p>Hello world</p>") == "Hello world"

    def test_nested_tags(self):
        result = clean_text("<div><p>Hello <strong>world</strong></p></div>")
        assert result == "Hello world"

    def test_self_closing_tags(self):
        result = clean_text("Line one<br/>Line two")
        assert result == "Line oneLine two"

    def test_tags_with_attributes(self):
        result = clean_text('<a href="https://example.com" class="link">Click</a>')
        assert result == "Click"

    def test_mixed_html_and_text(self):
        result = clean_text("Before <b>bold</b> after <i>italic</i> end")
        assert result == "Before bold after italic end"


class TestCleanTextDecodesEntities:
    """clean_text should decode HTML entities into their plain-text form."""

    def test_named_entities(self):
        assert clean_text("&amp; &lt; &gt;") == "& < >"

    def test_numeric_entities(self):
        assert clean_text("&#169; &#8212;") == "\u00a9 \u2014"

    def test_hex_entities(self):
        assert clean_text("&#x00A9;") == "\u00a9"

    def test_entity_inside_html(self):
        result = clean_text("<p>Price &gt; $100</p>")
        assert result == "Price > $100"

    def test_nbsp_entity(self):
        # &nbsp; (non-breaking space, U+00A0) gets NFKC-normalized to regular space
        result = clean_text("hello&nbsp;world")
        assert result == "hello world"


class TestCleanTextNormalizesWhitespace:
    """clean_text should collapse multiple spaces/tabs and limit consecutive newlines."""

    def test_multiple_spaces(self):
        assert clean_text("hello    world") == "hello world"

    def test_tabs_become_single_space(self):
        assert clean_text("hello\t\tworld") == "hello world"

    def test_mixed_spaces_and_tabs(self):
        assert clean_text("a \t  b") == "a b"

    def test_three_plus_newlines_collapsed_to_two(self):
        result = clean_text("paragraph one\n\n\n\nparagraph two")
        assert result == "paragraph one\n\nparagraph two"

    def test_two_newlines_preserved(self):
        result = clean_text("paragraph one\n\nparagraph two")
        assert result == "paragraph one\n\nparagraph two"

    def test_leading_trailing_whitespace_stripped(self):
        assert clean_text("  hello world  ") == "hello world"


class TestCleanTextUnicodeNormalization:
    """clean_text should apply NFKC unicode normalization."""

    def test_fullwidth_chars(self):
        # Fullwidth latin letters -> normal ASCII under NFKC
        result = clean_text("\uff28\uff45\uff4c\uff4c\uff4f")  # "Hello" fullwidth
        assert result == "Hello"

    def test_compatibility_characters(self):
        # fi ligature (U+FB01) decomposes to "fi" under NFKC
        result = clean_text("of\ufb01ce")
        assert result == "office"

    def test_superscript_digits(self):
        # Superscript 2 (U+00B2) -> "2" under NFKC
        result = clean_text("m\u00b2")
        assert result == "m2"


class TestCleanTextEmptyInput:
    """clean_text should return None for empty or whitespace-only input."""

    def test_empty_string(self):
        assert clean_text("") is None

    def test_whitespace_only(self):
        assert clean_text("   ") is None

    def test_only_html_tags(self):
        # After stripping HTML, nothing remains
        assert clean_text("<p></p>") is None

    def test_tabs_and_newlines_only(self):
        assert clean_text("\t\n\n  \t") is None


class TestCleanTextNoneInput:
    """clean_text should return None when given None."""

    def test_none_returns_none(self):
        assert clean_text(None) is None


# ---------------------------------------------------------------------------
# clean_title
# ---------------------------------------------------------------------------


class TestCleanTitleRemovesSourceSuffix:
    """clean_title should strip common ' - SourceName' / ' | SourceName' suffixes."""

    def test_dash_suffix(self):
        result = clean_title("Port congestion update - The Loadstar")
        assert result == "Port congestion update"

    def test_pipe_suffix(self):
        result = clean_title("Air cargo rates surge | FreightWaves")
        assert result == "Air cargo rates surge"

    def test_no_suffix_unchanged(self):
        result = clean_title("Port congestion update")
        assert result == "Port congestion update"

    def test_suffix_with_extra_spaces(self):
        result = clean_title("Tanker market outlook  -  Splash247")
        assert result == "Tanker market outlook"

    def test_multiple_words_source_name(self):
        result = clean_title("Ocean rates drop - The Maritime Executive")
        assert result == "Ocean rates drop"


class TestCleanTitleStripsWhitespace:
    """clean_title should strip leading/trailing whitespace from the result."""

    def test_leading_spaces(self):
        result = clean_title("   Port update")
        assert result == "Port update"

    def test_trailing_spaces(self):
        result = clean_title("Port update   ")
        assert result == "Port update"

    def test_both_sides(self):
        result = clean_title("  Port update  ")
        assert result == "Port update"

    def test_none_input(self):
        assert clean_title(None) is None

    def test_empty_string(self):
        assert clean_title("") is None

    def test_html_in_title(self):
        result = clean_title("<b>Breaking</b> news: port strike")
        assert result == "Breaking news: port strike"
