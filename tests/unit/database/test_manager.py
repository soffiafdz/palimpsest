import pytest
from unittest.mock import MagicMock, patch

from dev.database.manager import PalimpsestDB
from dev.database.managers import TagManager
from dev.core.logging_manager import PalimpsestLogger


# Mock object that satisfies SQLAlchemy's checks for session.add()
class MockSQLAObject:
    def __init__(self, id=None, name="test"):
        self.id = id
        self.name = name
        # Mock specific SQLAlchemy attributes often accessed
        self._sa_instance_state = MagicMock()
        self._sa_instance_state.class_ = self.__class__
        self._sa_instance_state.key = None  # Not persisted yet
        self._sa_instance_state.deleted = False

    __tablename__ = "mock_table"


class TestPalimpsestDBTransactions:
    """Tests for transaction management in PalimpsestDB."""

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
             patch("dev.core.backup_manager.BackupManager", autospec=True):

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

    def test_session_scope_commit_on_success(self, db_instance):
        """Verify session commits on successful execution within session_scope."""
        mock_session = MagicMock()
        db_instance.SessionLocal = MagicMock(return_value=mock_session)

        with db_instance.session_scope() as session:
            session.add(MockSQLAObject())

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called_once()

    def test_session_scope_rollback_on_exception(self, db_instance):
        """Verify session rolls back on exception within session_scope."""
        mock_session = MagicMock()
        db_instance.SessionLocal = MagicMock(return_value=mock_session)

        with pytest.raises(ValueError, match="Test error"):
            with db_instance.session_scope() as session:
                session.add(MockSQLAObject())
                raise ValueError("Test error")

        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()

    def test_transaction_context_manager(self, db_instance):
        """Verify transaction context manager delegates to session_scope."""
        mock_session = MagicMock()
        db_instance.SessionLocal = MagicMock(return_value=mock_session)

        with db_instance.transaction() as session:
            session.add(MockSQLAObject())

        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()
        mock_session.close.assert_called_once()
