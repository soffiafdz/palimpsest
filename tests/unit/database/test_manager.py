import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.exc import OperationalError, IntegrityError

from dev.database.manager import PalimpsestDB, DatabaseError
from dev.database.managers import TagManager # Example manager
from dev.core.logging_manager import PalimpsestLogger # For __init__

# Mock object that satisfies SQLAlchemy's checks for session.add()
class MockSQLAObject:
    def __init__(self, id=None, name="test"):
        self.id = id
        self.name = name
        # Mock specific SQLAlchemy attributes often accessed
        self._sa_instance_state = MagicMock()
        self._sa_instance_state.class_ = self.__class__
        self._sa_instance_state.key = None # Not persisted yet
        self._sa_instance_state.deleted = False
    
    # Required for the _get_or_create_lookup_item test (filter_by requires __tablename__)
    __tablename__ = "mock_table"

class TestPalimpsestDBTransactionsAndRetries:
    """Tests for transaction management and retry logic in PalimpsestDB."""

    @pytest.fixture
    def mock_db_path(self, tmp_path):
        """Mock database path."""
        return tmp_path / "test.db"

    @pytest.fixture
    def mock_alembic_dir(self, tmp_path):
        """Mock alembic directory."""
        return tmp_path / "alembic"

    @pytest.fixture
    def mock_logger(self):
        """Mock logger instance."""
        return MagicMock(spec=PalimpsestLogger)

    @pytest.fixture
    def db_instance(self, mock_db_path, mock_alembic_dir, mock_logger):
        """PalimpsestDB instance with mocked SQLAlchemy components."""
        with patch("sqlalchemy.create_engine"), \
             patch.object(PalimpsestDB, "_setup_alembic", autospec=True), \
             patch.object(PalimpsestDB, "initialize_schema", autospec=True), \
             patch("dev.core.backup_manager.BackupManager", autospec=True): # PATCH THE CLASS

            db = PalimpsestDB(
                db_path=mock_db_path,
                alembic_dir=mock_alembic_dir,
                log_dir=mock_db_path.parent / "logs",
                backup_dir=mock_db_path.parent / "backups",
                enable_auto_backup=False,
            )
            # Ensure managers are initialized for session_scope to work
            db._tag_manager = MagicMock(autospec=TagManager)
            db._person_manager = MagicMock(autospec=True)
            db._event_manager = MagicMock(autospec=True)
            db._moment_manager = MagicMock(autospec=True)
            db._location_manager = MagicMock(autospec=True)
            db._reference_manager = MagicMock(autospec=True)
            db._poem_manager = MagicMock(autospec=True)
            db._manuscript_manager = MagicMock(autospec=True)
            db._entry_manager = MagicMock(autospec=True)
            return db

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_session_scope_commit_on_success(self, mock_sleep, db_instance):
        """Verify session commits on successful execution within session_scope."""
        # Mock the session returned by SessionLocal
        mock_session = MagicMock()
        db_instance.SessionLocal = MagicMock(return_value=mock_session)
        
        with db_instance.session_scope() as session:
            session.add(MockSQLAObject()) 
        
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_session_scope_rollback_on_exception(self, mock_sleep, db_instance):
        """Verify session rolls back on exception within session_scope."""
        # Mock the session returned by SessionLocal
        mock_session = MagicMock()
        db_instance.SessionLocal = MagicMock(return_value=mock_session)

        with pytest.raises(ValueError, match="Test error"):
            with db_instance.session_scope() as session:
                session.add(MockSQLAObject())
                raise ValueError("Test error")
        
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_transaction_context_manager(self, mock_sleep, db_instance):
        """Verify transaction context manager delegates to session_scope."""
        # Mock the session returned by SessionLocal
        mock_session = MagicMock()
        db_instance.SessionLocal = MagicMock(return_value=mock_session)

        with db_instance.transaction() as session:
            session.add(MockSQLAObject())
            
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called_once()

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_execute_with_retry_success_first_attempt(self, mock_sleep, db_instance):
        """Verify _execute_with_retry succeeds on the first attempt."""
        mock_operation = MagicMock(autospec=True, return_value="Success")
        result = db_instance._execute_with_retry(mock_operation)
        assert result == "Success"
        mock_operation.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_execute_with_retry_succeeds_after_retries(self, mock_sleep, db_instance):
        """Verify _execute_with_retry retries on OperationalError (locked/busy) and succeeds."""
        mock_operation = MagicMock(autospec=True, side_effect=[
            OperationalError("mock conn", "mock cursor", "database is locked", "statement"),
            OperationalError("mock conn", "mock cursor", "database is busy", "statement"),
            "Success"
        ])
        result = db_instance._execute_with_retry(mock_operation, max_retries=3)
        assert result == "Success"
        assert mock_operation.call_count == 3
        assert mock_sleep.call_count == 2 # Called after first two failures

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_execute_with_retry_exhausted_retries_raises_database_error(self, mock_sleep, db_instance):
        """Verify _execute_with_retry raises DatabaseError after exhausting retries."""
        mock_operation = MagicMock(autospec=True, side_effect=[
            OperationalError("mock conn", "mock cursor", "database is locked", "statement"),
            OperationalError("mock conn", "mock cursor", "database is locked", "statement"),
            OperationalError("mock conn", "mock cursor", "database is locked", "statement")
        ])
        with pytest.raises(DatabaseError, match="Operation failed after 3 attempts due to database lock/busy conditions."):
            db_instance._execute_with_retry(mock_operation, max_retries=3)
        assert mock_operation.call_count == 3
        assert mock_sleep.call_count == 2

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_execute_with_retry_non_lock_operational_error_no_retry(self, mock_sleep, db_instance):
        """Verify _execute_with_retry raises non-lock OperationalError immediately."""
        mock_operation = MagicMock(autospec=True, side_effect=OperationalError("mock conn", "mock cursor", "disk I/O error", "statement"))
        with pytest.raises(OperationalError, match="disk I/O error"):
            db_instance._execute_with_retry(mock_operation)
        mock_operation.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_execute_with_retry_other_exception_no_retry(self, mock_sleep, db_instance):
        """Verify _execute_with_retry raises other exceptions immediately."""
        mock_operation = MagicMock(autospec=True, side_effect=ValueError("Some other error"))
        with pytest.raises(ValueError, match="Some other error"):
            db_instance._execute_with_retry(mock_operation)
        mock_operation.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("sqlalchemy.orm.sessionmaker")
    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_get_or_create_lookup_item_returns_existing(self, mock_sleep, mock_sessionmaker, db_instance):
        """Test _get_or_create_lookup_item returns existing item."""
        mock_session_instance = MagicMock()
        mock_sessionmaker.return_value = MagicMock(return_value=mock_session_instance)
        mock_session_instance.query.return_value.filter_by.return_value.first.return_value = MagicMock(id=1, name="Existing")
        
        mock_model_class = MagicMock(name="MockModel", autospec=True)
        result = db_instance._get_or_create_lookup_item(mock_session_instance, mock_model_class, {"name": "Existing"})
        assert result.id == 1
        mock_session_instance.query.assert_called_once_with(mock_model_class)
        mock_session_instance.add.assert_not_called()
        mock_session_instance.flush.assert_not_called()

    @patch("sqlalchemy.orm.sessionmaker")
    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_get_or_create_lookup_item_creates_new(self, mock_sleep, mock_sessionmaker, db_instance):
        """Test _get_or_create_lookup_item creates new item if not found."""
        mock_session_instance = MagicMock()
        mock_sessionmaker.return_value = MagicMock(return_value=mock_session_instance)
        mock_session_instance.query.return_value.filter_by.return_value.first.return_value = None # No existing
        
        mock_model_class = MagicMock(name="MockModel", autospec=True)
        # Mocking the constructor call to MockModel()
        mock_model_instance = MockSQLAObject(name="New")
        mock_model_class.return_value = mock_model_instance 
        
        result = db_instance._get_or_create_lookup_item(mock_session_instance, mock_model_class, {"name": "New"})
        assert result.name == "New"
        mock_session_instance.query.assert_called_once_with(mock_model_class)
        mock_session_instance.add.assert_called_once_with(mock_model_instance)
        mock_session_instance.flush.assert_called_once()

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_get_or_create_lookup_item_handles_integrity_error_on_race(self, mock_sleep, db_instance):
        """Test _get_or_create_lookup_item handles IntegrityError (race condition)."""
        mock_session = MagicMock()
        
        mock_model_class = MagicMock(name="MockModel", autospec=True)
        mock_existing_obj = MagicMock(id=1, name="Existing")
        
        # Simulate: first check finds nothing, creation fails with IntegrityError, second check finds it.
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            None, # First check
            mock_existing_obj # Second check after rollback
        ]
        mock_session.add.side_effect = IntegrityError("msg", {}, "orig")
        
        result = db_instance._get_or_create_lookup_item(mock_session, mock_model_class, {"name": "Race"})
        assert result == mock_existing_obj
        assert mock_session.query.call_count == 2
        mock_session.rollback.assert_called_once()

    @patch("dev.database.manager.time.sleep", autospec=True)
    def test_get_or_create_lookup_item_raises_if_integrity_error_and_not_found(self, mock_sleep, db_instance):
        """Test _get_or_create_lookup_item re-raises if IntegrityError occurs and item still not found."""
        mock_session = MagicMock()
        
        mock_model_class = MagicMock(name="MockModel", autospec=True)
        
        mock_session.query.return_value.filter_by.return_value.first.side_effect = [
            None, # First check
            None # Second check after rollback still finds nothing
        ]
        mock_session.add.side_effect = IntegrityError("msg", {}, "orig")
        
        with pytest.raises(DatabaseError, match="Data integrity violation"):
            db_instance._get_or_create_lookup_item(mock_session, mock_model_class, {"name": "FailedRace"})
        mock_session.rollback.assert_called_once()
