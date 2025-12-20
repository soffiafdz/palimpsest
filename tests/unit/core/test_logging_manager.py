"""
Tests for logging_manager module.

Tests the safe_logger function and NullLogger class that provide
null-safe logging throughout the codebase.
"""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from dev.core.logging_manager import (
    NullLogger,
    PalimpsestLogger,
    safe_logger,
)


class TestNullLogger:
    """Tests for NullLogger class."""

    def test_null_logger_log_operation_no_op(self):
        """NullLogger.log_operation should do nothing."""
        logger = NullLogger()
        # Should not raise any exception
        logger.log_operation("test_op", {"key": "value"})

    def test_null_logger_log_error_no_op(self):
        """NullLogger.log_error should do nothing."""
        logger = NullLogger()
        error = ValueError("test error")
        logger.log_error(error, {"context": "test"})

    def test_null_logger_log_debug_no_op(self):
        """NullLogger.log_debug should do nothing."""
        logger = NullLogger()
        logger.log_debug("debug message", {"key": "value"})

    def test_null_logger_log_info_no_op(self):
        """NullLogger.log_info should do nothing."""
        logger = NullLogger()
        logger.log_info("info message", {"key": "value"})

    def test_null_logger_log_warning_no_op(self):
        """NullLogger.log_warning should do nothing."""
        logger = NullLogger()
        logger.log_warning("warning message", {"key": "value"})

    def test_null_logger_log_cli_error_returns_formatted(self):
        """NullLogger.log_cli_error should return formatted error string."""
        logger = NullLogger()
        error = ValueError("test error")
        result = logger.log_cli_error(error, {"context": "test"})
        assert "ValueError" in result
        assert "test error" in result


class TestSafeLogger:
    """Tests for safe_logger function."""

    def test_safe_logger_returns_logger_when_provided(self):
        """safe_logger should return the same logger when not None."""
        mock_logger = MagicMock(spec=PalimpsestLogger)
        result = safe_logger(mock_logger)
        assert result is mock_logger

    def test_safe_logger_returns_null_logger_when_none(self):
        """safe_logger should return NullLogger when logger is None."""
        result = safe_logger(None)
        assert isinstance(result, NullLogger)

    def test_safe_logger_null_logger_is_singleton(self):
        """safe_logger should return the same NullLogger instance."""
        result1 = safe_logger(None)
        result2 = safe_logger(None)
        assert result1 is result2

    def test_safe_logger_can_chain_log_calls(self):
        """safe_logger should allow chaining log calls."""
        # Test with None - should not raise
        safe_logger(None).log_info("test message")
        safe_logger(None).log_debug("debug")
        safe_logger(None).log_warning("warning")
        safe_logger(None).log_operation("op", {"key": "value"})

    def test_safe_logger_with_real_logger(self, tmp_path):
        """safe_logger should work with real PalimpsestLogger."""
        log_dir = tmp_path / "logs"
        log_dir.mkdir()
        logger = PalimpsestLogger(log_dir, "test")

        result = safe_logger(logger)
        assert result is logger

        # Should be able to log
        result.log_info("test message")


class TestSafeLoggerUsagePatterns:
    """Tests for common safe_logger usage patterns."""

    def test_replaces_if_logger_pattern(self):
        """Demonstrate safe_logger replaces if self.logger: pattern."""
        # Old pattern:
        # if self.logger:
        #     self.logger.log_info("message")

        # New pattern using safe_logger:
        logger = None
        safe_logger(logger).log_info("message")  # Should not raise

        # With actual logger
        mock_logger = MagicMock(spec=PalimpsestLogger)
        safe_logger(mock_logger).log_info("message")
        mock_logger.log_info.assert_called_once_with("message")

    def test_works_with_log_details(self):
        """safe_logger should handle log calls with details dict."""
        mock_logger = MagicMock(spec=PalimpsestLogger)
        details = {"file": "test.py", "line": 42}

        safe_logger(mock_logger).log_operation("process", details)
        mock_logger.log_operation.assert_called_once_with("process", details)

        # Also works with None logger
        safe_logger(None).log_operation("process", details)

    def test_works_with_log_error(self):
        """safe_logger should handle log_error calls."""
        mock_logger = MagicMock(spec=PalimpsestLogger)
        error = ValueError("test")
        context = {"operation": "test_op"}

        safe_logger(mock_logger).log_error(error, context)
        mock_logger.log_error.assert_called_once_with(error, context)

        # Also works with None logger
        safe_logger(None).log_error(error, context)
