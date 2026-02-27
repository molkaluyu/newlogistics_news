"""
Tests for monitoring/logging_config.py -- JSON formatter and logging setup.

No external dependencies to mock; tests inspect Python logging internals.
"""

import json
import logging

import pytest

from monitoring.logging_config import JSONFormatter, setup_logging


# ---------------------------------------------------------------------------
# JSONFormatter
# ---------------------------------------------------------------------------


class TestJSONFormatter:
    """JSONFormatter should produce valid JSON with required fields."""

    def _make_record(
        self,
        msg: str = "test message",
        level: int = logging.INFO,
        name: str = "test.logger",
        exc_info=None,
        extra: dict | None = None,
    ) -> logging.LogRecord:
        """Create a LogRecord for testing."""
        record = logging.LogRecord(
            name=name,
            level=level,
            pathname="test.py",
            lineno=1,
            msg=msg,
            args=(),
            exc_info=exc_info,
        )
        if extra:
            for key, value in extra.items():
                setattr(record, key, value)
        return record

    def test_output_is_valid_json(self):
        """Formatted output should be parseable as JSON."""
        formatter = JSONFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_required_fields(self):
        """Output should contain timestamp, level, logger, and message."""
        formatter = JSONFormatter()
        record = self._make_record(
            msg="hello world", level=logging.WARNING, name="my.logger"
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert parsed["timestamp"].endswith("Z")
        assert parsed["level"] == "WARNING"
        assert parsed["logger"] == "my.logger"
        assert parsed["message"] == "hello world"

    def test_includes_exception_info(self):
        """When exc_info is present, output should contain exception field."""
        formatter = JSONFormatter()
        try:
            raise ValueError("test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()

        record = self._make_record(msg="error occurred", exc_info=exc_info)
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]
        assert "test error" in parsed["exception"]

    def test_no_exception_field_when_no_exc_info(self):
        """Output should not contain exception field when there is no exception."""
        formatter = JSONFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" not in parsed

    def test_includes_source_id(self):
        """Custom source_id field should appear in output when set."""
        formatter = JSONFormatter()
        record = self._make_record(extra={"source_id": "loadstar_rss"})
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["source_id"] == "loadstar_rss"

    def test_includes_article_id(self):
        """Custom article_id field should appear in output when set."""
        formatter = JSONFormatter()
        record = self._make_record(extra={"article_id": "abc-123"})
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["article_id"] == "abc-123"

    def test_includes_both_custom_fields(self):
        """Both source_id and article_id should appear when both are set."""
        formatter = JSONFormatter()
        record = self._make_record(
            extra={"source_id": "splash247", "article_id": "xyz-789"}
        )
        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["source_id"] == "splash247"
        assert parsed["article_id"] == "xyz-789"

    def test_omits_custom_fields_when_absent(self):
        """Custom fields should not appear when not set on the record."""
        formatter = JSONFormatter()
        record = self._make_record()
        output = formatter.format(record)
        parsed = json.loads(output)

        assert "source_id" not in parsed
        assert "article_id" not in parsed


# ---------------------------------------------------------------------------
# setup_logging
# ---------------------------------------------------------------------------


class TestSetupLogging:
    """setup_logging should configure root logger level, formatter, and noisy libs."""

    def _cleanup_root_logger(self):
        """Remove all handlers from root logger after test."""
        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

    def test_sets_correct_log_level_info(self):
        """Root logger should be set to the specified level."""
        try:
            setup_logging(level="INFO", json_format=False)
            root = logging.getLogger()
            assert root.level == logging.INFO
        finally:
            self._cleanup_root_logger()

    def test_sets_correct_log_level_debug(self):
        """Root logger should accept DEBUG level."""
        try:
            setup_logging(level="DEBUG", json_format=False)
            root = logging.getLogger()
            assert root.level == logging.DEBUG
        finally:
            self._cleanup_root_logger()

    def test_sets_correct_log_level_case_insensitive(self):
        """Level string should be case-insensitive."""
        try:
            setup_logging(level="warning", json_format=False)
            root = logging.getLogger()
            assert root.level == logging.WARNING
        finally:
            self._cleanup_root_logger()

    def test_uses_json_formatter(self):
        """When json_format=True, handler should use JSONFormatter."""
        try:
            setup_logging(level="INFO", json_format=True)
            root = logging.getLogger()
            assert len(root.handlers) == 1
            assert isinstance(root.handlers[0].formatter, JSONFormatter)
        finally:
            self._cleanup_root_logger()

    def test_uses_standard_formatter(self):
        """When json_format=False, handler should use standard Formatter."""
        try:
            setup_logging(level="INFO", json_format=False)
            root = logging.getLogger()
            assert len(root.handlers) == 1
            formatter = root.handlers[0].formatter
            assert not isinstance(formatter, JSONFormatter)
            assert isinstance(formatter, logging.Formatter)
        finally:
            self._cleanup_root_logger()

    def test_quiets_noisy_libraries(self):
        """httpx, httpcore, and asyncio loggers should be set to WARNING."""
        try:
            setup_logging(level="DEBUG", json_format=False)
            assert logging.getLogger("httpx").level == logging.WARNING
            assert logging.getLogger("httpcore").level == logging.WARNING
            assert logging.getLogger("asyncio").level == logging.WARNING
        finally:
            self._cleanup_root_logger()

    def test_removes_existing_handlers(self):
        """Existing root handlers should be removed before adding new one."""
        root = logging.getLogger()
        dummy_handler = logging.StreamHandler()
        root.addHandler(dummy_handler)

        try:
            setup_logging(level="INFO", json_format=False)
            # Only the newly added handler should remain
            assert len(root.handlers) == 1
            assert root.handlers[0] is not dummy_handler
        finally:
            self._cleanup_root_logger()
