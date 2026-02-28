"""
Tests for processing/language.py -- language detection.

langdetect is mocked for deterministic results.
"""

from unittest.mock import patch

import pytest
from langdetect.lang_detect_exception import LangDetectException

from processing.language import detect_language


# ---------------------------------------------------------------------------
# English detection
# ---------------------------------------------------------------------------


class TestDetectLanguageEnglish:
    """detect_language should identify English text."""

    def test_english_text_detected(self):
        """Standard English text should be detected as 'en'."""
        with patch("processing.language.detect", return_value="en"):
            result = detect_language(
                "Global supply chains continue to face unprecedented challenges "
                "as container shipping rates remain volatile."
            )
        assert result == "en"


# ---------------------------------------------------------------------------
# Chinese detection
# ---------------------------------------------------------------------------


class TestDetectLanguageChinese:
    """detect_language should identify Chinese text."""

    def test_chinese_text_detected(self):
        """Chinese text should be detected as 'zh-cn' (or similar)."""
        with patch("processing.language.detect", return_value="zh-cn"):
            result = detect_language(
                "\u5168\u7403\u4f9b\u5e94\u94fe\u7ee7\u7eed\u9762\u4e34\u524d\u6240\u672a\u6709\u7684\u6311\u6218"
                "\uff0c\u96c6\u88c5\u7bb1\u822a\u8fd0\u8d39\u7387\u4ecd\u7136\u6ce2\u52a8\u4e0d\u5b9a\u3002"
            )
        assert result == "zh-cn"


# ---------------------------------------------------------------------------
# Short text fallback
# ---------------------------------------------------------------------------


class TestDetectLanguageShortText:
    """detect_language should return 'en' for text shorter than 20 chars."""

    def test_short_text_returns_en(self):
        """Text under 20 characters should default to 'en' without calling detect."""
        with patch("processing.language.detect") as mock_detect:
            result = detect_language("Short text")
            mock_detect.assert_not_called()
        assert result == "en"

    def test_exactly_19_chars_returns_en(self):
        """Text with exactly 19 characters should default to 'en'."""
        text = "a" * 19
        with patch("processing.language.detect") as mock_detect:
            result = detect_language(text)
            mock_detect.assert_not_called()
        assert result == "en"


# ---------------------------------------------------------------------------
# Empty and None input
# ---------------------------------------------------------------------------


class TestDetectLanguageEmptyInput:
    """detect_language should return 'en' for empty or None input."""

    def test_empty_string_returns_en(self):
        """An empty string should default to 'en'."""
        result = detect_language("")
        assert result == "en"

    def test_none_input_returns_en(self):
        """None input should default to 'en'."""
        result = detect_language(None)
        assert result == "en"

    def test_whitespace_only_returns_en(self):
        """Whitespace-only text (stripped length < 20) should default to 'en'."""
        result = detect_language("          ")
        assert result == "en"


# ---------------------------------------------------------------------------
# Detection failure fallback
# ---------------------------------------------------------------------------


class TestDetectLanguageFailureFallback:
    """detect_language should return 'en' when detection raises an exception."""

    def test_langdetect_exception_returns_en(self):
        """A LangDetectException should result in 'en' fallback."""
        with patch(
            "processing.language.detect",
            side_effect=LangDetectException(0, "No features in text"),
        ):
            result = detect_language(
                "This is a sufficiently long text for detection to be attempted."
            )
        assert result == "en"

    def test_unexpected_exception_returns_en(self):
        """An unexpected exception should also result in 'en' fallback."""
        with patch(
            "processing.language.detect",
            side_effect=RuntimeError("unexpected error"),
        ):
            result = detect_language(
                "This is a sufficiently long text for detection to be attempted."
            )
        assert result == "en"
