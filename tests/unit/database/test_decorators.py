"""Tests for database decorators and context managers."""
import pytest
from unittest.mock import MagicMock

from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from dev.database.decorators import DatabaseOperation
from dev.core.exceptions import DatabaseError
from dev.core.logging_manager import PalimpsestLogger


class TestDatabaseOperation:
    """Tests for DatabaseOperation context manager."""

    def test_successful_operation(self):
        """DatabaseOperation should log completion on success."""
        mock_logger = MagicMock(spec=PalimpsestLogger)

        with DatabaseOperation(mock_logger, "test_operation"):
            result = 1 + 1  # Simple operation

        assert result == 2
        mock_logger.log_operation.assert_called_once()
        call_args = mock_logger.log_operation.call_args
        assert call_args[0][0] == "test_operation_completed"
        assert call_args[0][1]["success"] is True

    def test_successful_operation_with_none_logger(self):
        """DatabaseOperation should work with None logger (uses NullLogger)."""
        # Should not raise any exception
        with DatabaseOperation(None, "test_operation"):
            result = 1 + 1

        assert result == 2

    def test_integrity_error_raises_database_error(self):
        """DatabaseOperation should convert IntegrityError to DatabaseError."""
        mock_logger = MagicMock(spec=PalimpsestLogger)

        with pytest.raises(DatabaseError) as exc_info:
            with DatabaseOperation(mock_logger, "test_operation"):
                raise IntegrityError("statement", {}, Exception("duplicate"))

        assert "Data integrity violation" in str(exc_info.value)
        mock_logger.log_error.assert_called_once()

    def test_sqlalchemy_error_raises_database_error(self):
        """DatabaseOperation should convert SQLAlchemyError to DatabaseError."""
        mock_logger = MagicMock(spec=PalimpsestLogger)

        with pytest.raises(DatabaseError) as exc_info:
            with DatabaseOperation(mock_logger, "test_operation"):
                raise SQLAlchemyError("connection failed")

        assert "Database operation failed" in str(exc_info.value)
        mock_logger.log_error.assert_called_once()

    def test_other_exceptions_propagate(self):
        """DatabaseOperation should propagate non-SQLAlchemy exceptions."""
        mock_logger = MagicMock(spec=PalimpsestLogger)

        with pytest.raises(ValueError):
            with DatabaseOperation(mock_logger, "test_operation"):
                raise ValueError("invalid value")

        mock_logger.log_error.assert_called_once()

    def test_log_start_option(self):
        """DatabaseOperation should log start when log_start=True."""
        mock_logger = MagicMock(spec=PalimpsestLogger)

        with DatabaseOperation(mock_logger, "test_operation", log_start=True):
            pass

        mock_logger.log_debug.assert_called_once()
        assert "Starting test_operation" in mock_logger.log_debug.call_args[0][0]

    def test_no_log_start_by_default(self):
        """DatabaseOperation should not log start by default."""
        mock_logger = MagicMock(spec=PalimpsestLogger)

        with DatabaseOperation(mock_logger, "test_operation"):
            pass

        mock_logger.log_debug.assert_not_called()

    def test_duration_is_logged(self):
        """DatabaseOperation should log duration on completion."""
        mock_logger = MagicMock(spec=PalimpsestLogger)

        with DatabaseOperation(mock_logger, "test_operation"):
            pass

        call_args = mock_logger.log_operation.call_args
        assert "duration_seconds" in call_args[0][1]
        assert isinstance(call_args[0][1]["duration_seconds"], float)
