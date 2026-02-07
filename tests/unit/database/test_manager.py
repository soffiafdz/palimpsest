#!/usr/bin/env python3
"""
test_manager.py
---------------
Tests for dev/database/manager.py - PalimpsestDB main database manager.

Tests cover:
- Transaction management (session_scope, transaction context manager)
- Manager initialization and cleanup within session scope
- Database cleanup operations with Scene model
- Error handling and rollback behavior
"""
import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from dev.database.manager import PalimpsestDB
from dev.database.managers import (
    PersonManager,
    LocationManager,
    ReferenceManager,
    PoemManager,
    EntryManager,
    SimpleManager,
)
from dev.database.models import Tag, Location, Scene, Theme, Entry
from dev.core.logging_manager import PalimpsestLogger


# Mock object that satisfies SQLAlchemy's checks for session.add()
class MockSQLAObject:
    """Mock SQLAlchemy object for transaction tests."""

    def __init__(self, id=None, name="test"):
        """
        Initialize mock object.

        Args:
            id: Optional entity ID
            name: Entity name
        """
        self.id = id
        self.name = name
        # Mock specific SQLAlchemy attributes often accessed
        self._sa_instance_state = MagicMock()
        self._sa_instance_state.class_ = self.__class__
        self._sa_instance_state.key = None  # Not persisted yet
        self._sa_instance_state.deleted = False

    __tablename__ = "mock_table"


class TestPalimpsestDBTransactions:
    """
    Tests for transaction management in PalimpsestDB.

    These tests use mocking to verify transaction behavior without
    requiring a real database connection. They verify commit, rollback,
    and cleanup behavior.
    """

    @pytest.fixture
    def mock_db_path(self, tmp_path):
        """Create temporary database path."""
        return tmp_path / "test.db"

    @pytest.fixture
    def mock_alembic_dir(self, tmp_path):
        """Create mock alembic directory."""
        return tmp_path / "alembic"

    @pytest.fixture
    def mock_logger(self):
        """Create mock logger instance."""
        return MagicMock(spec=PalimpsestLogger)

    @pytest.fixture
    def db_instance(self, mock_db_path, mock_alembic_dir):
        """Create PalimpsestDB instance with mocked SQLAlchemy components."""
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
            yield db

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


class TestPalimpsestDBManagerInitialization:
    """Tests for manager initialization and cleanup in session_scope."""

    @pytest.fixture
    def test_db(self, test_db_path, test_alembic_dir):
        """Create test database instance."""
        db = PalimpsestDB(
            db_path=test_db_path,
            alembic_dir=test_alembic_dir,
            enable_auto_backup=False,
        )
        yield db
        if test_db_path.exists():
            test_db_path.unlink()

    def test_session_scope_initializes_all_managers(self, test_db):
        """Verify session_scope initializes all required managers."""
        with test_db.session_scope() as _:
            # Check that all managers are initialized
            assert test_db._tag_manager is not None
            assert isinstance(test_db._tag_manager, SimpleManager)

            assert test_db._person_manager is not None
            assert isinstance(test_db._person_manager, PersonManager)

            assert test_db._location_manager is not None
            assert isinstance(test_db._location_manager, LocationManager)

            assert test_db._reference_manager is not None
            assert isinstance(test_db._reference_manager, ReferenceManager)

            assert test_db._poem_manager is not None
            assert isinstance(test_db._poem_manager, PoemManager)

            assert test_db._entry_manager is not None
            assert isinstance(test_db._entry_manager, EntryManager)

            assert test_db._event_manager is not None
            assert isinstance(test_db._event_manager, SimpleManager)

        # After exiting context, managers should be cleaned up
        assert test_db._tag_manager is None
        assert test_db._event_manager is None
        assert test_db._person_manager is None
        assert test_db._location_manager is None
        assert test_db._reference_manager is None
        assert test_db._poem_manager is None
        assert test_db._entry_manager is None

    def test_session_scope_no_moment_manager(self, test_db):
        """Verify session_scope does NOT initialize MomentManager (deprecated)."""
        with test_db.session_scope() as _:
            # Phase 13: MomentManager no longer exists
            assert not hasattr(test_db, "_moment_manager")

    def test_manager_properties_accessible_in_session(self, test_db):
        """Verify manager properties are accessible within session_scope."""
        with test_db.session_scope() as _:
            # All manager properties should work
            assert test_db.tags is not None
            assert test_db.events is not None
            assert test_db.people is not None
            assert test_db.locations is not None
            assert test_db.references is not None
            assert test_db.poems is not None
            assert test_db.entries is not None

    def test_manager_properties_raise_outside_session(self, test_db):
        """Verify manager properties raise errors outside session_scope."""
        from dev.core.exceptions import DatabaseError

        # Outside session context, accessing managers should raise DatabaseError
        with pytest.raises(DatabaseError, match="requires active session"):
            _ = test_db.tags

        with pytest.raises(DatabaseError, match="requires active session"):
            _ = test_db.people

        with pytest.raises(DatabaseError, match="requires active session"):
            _ = test_db.entries

    def test_managers_share_session(self, test_db):
        """Verify all managers share the same session instance."""
        with test_db.session_scope() as session:
            # All managers should share the same session
            assert test_db._tag_manager.session is session
            assert test_db._event_manager.session is session
            assert test_db._person_manager.session is session
            assert test_db._location_manager.session is session
            assert test_db._reference_manager.session is session
            assert test_db._poem_manager.session is session
            assert test_db._entry_manager.session is session


class TestPalimpsestDBCleanup:
    """Tests for cleanup_all_metadata with Scene model."""

    @pytest.fixture
    def test_db(self, test_db_path, test_alembic_dir):
        """Create test database instance."""
        db = PalimpsestDB(
            db_path=test_db_path,
            alembic_dir=test_alembic_dir,
            enable_auto_backup=False,
        )
        yield db
        if test_db_path.exists():
            test_db_path.unlink()

    def test_cleanup_all_metadata_removes_orphaned_tags(self, test_db):
        """Verify cleanup removes tags not linked to any entries."""
        with test_db.session_scope() as session:
            # Create tag without entry
            orphan_tag = Tag(name="orphan")
            session.add(orphan_tag)
            session.commit()

        # Run cleanup
        result = test_db.cleanup_all_metadata()

        # Verify orphan was removed
        assert result["tags"] == 1

        # Verify tag is gone
        with test_db.session_scope() as session:
            assert session.query(Tag).filter_by(name="orphan").first() is None

    def test_cleanup_all_metadata_removes_orphaned_locations(self, test_db):
        """Verify cleanup removes locations not linked to any entries."""
        with test_db.session_scope() as session:
            # Create city (required for location)
            from dev.database.models import City
            city = City(name="Test City")
            session.add(city)
            session.flush()

            # Create location with city but no entry links
            orphan_loc = Location(name="Nowhere Cafe", city_id=city.id)
            session.add(orphan_loc)
            session.commit()

        # Run cleanup
        result = test_db.cleanup_all_metadata()

        # Verify orphan was removed
        assert result["locations"] == 1

        # Verify location is gone
        with test_db.session_scope() as session:
            assert session.query(Location).filter_by(name="Nowhere Cafe").first() is None

    @pytest.mark.skip(
        reason="Scene has NOT NULL constraint on entry_id with CASCADE delete - no orphan scenario exists"
    )
    def test_cleanup_all_metadata_removes_orphaned_scenes(self, test_db):
        """Verify cleanup removes scenes not linked to any entry."""
        # Note: This test is invalid - Scene cannot exist without Entry due to NOT NULL FK
        # with CASCADE delete. When Entry is deleted, Scene is automatically cascade-deleted.
        pass

    def test_cleanup_all_metadata_preserves_linked_entities(self, test_db):
        """Verify cleanup preserves entities linked to entries."""
        with test_db.session_scope() as session:
            # Create entry with linked entities
            entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
            session.add(entry)
            session.flush()

            tag = Tag(name="preserved")
            tag.entries.append(entry)
            session.add(tag)

            # Create city (required for location)
            from dev.database.models import City
            city = City(name="Test City")
            session.add(city)
            session.flush()

            location = Location(name="Preserved Cafe", city_id=city.id)
            location.entries.append(entry)
            session.add(location)

            scene = Scene(
                name="Preserved Scene",
                description="This scene has an entry",
                entry_id=entry.id,
            )
            session.add(scene)
            session.commit()

        # Run cleanup
        result = test_db.cleanup_all_metadata()

        # Verify nothing was removed
        assert result["tags"] == 0
        assert result["locations"] == 0
        assert result["scenes"] == 0

        # Verify entities still exist
        with test_db.session_scope() as session:
            assert session.query(Tag).filter_by(name="preserved").first() is not None
            assert session.query(Location).filter_by(name="Preserved Cafe").first() is not None
            assert session.query(Scene).filter_by(name="Preserved Scene").first() is not None

    def test_cleanup_all_metadata_removes_orphaned_themes(self, test_db):
        """Verify cleanup removes themes not linked to any entries."""
        with test_db.session_scope() as session:
            orphan_theme = Theme(name="orphan-theme")
            session.add(orphan_theme)
            session.commit()

        result = test_db.cleanup_all_metadata()

        assert result["themes"] == 1

        with test_db.session_scope() as session:
            assert session.query(Theme).filter_by(name="orphan-theme").first() is None

    @pytest.mark.skip(
        reason="Reference has NOT NULL constraints on entry_id and source_id with CASCADE delete - no orphan scenario exists"
    )
    def test_cleanup_all_metadata_removes_orphaned_references(self, test_db):
        """Verify cleanup removes references not linked to any entry."""
        # Note: This test is invalid - Reference cannot exist without Entry and ReferenceSource
        # due to NOT NULL FKs with CASCADE delete. When Entry or ReferenceSource is deleted,
        # Reference is automatically cascade-deleted.
        pass

    @pytest.mark.skip(
        reason="PoemVersion has NOT NULL constraints on both poem_id and entry_id with CASCADE delete - no orphan scenario exists"
    )
    def test_cleanup_all_metadata_removes_orphaned_poem_versions(self, test_db):
        """Verify cleanup removes poem versions not linked to any entry."""
        # Note: This test is invalid - PoemVersion cannot be orphaned due to NOT NULL FKs
        # with CASCADE delete. When Entry or Poem is deleted, PoemVersion is automatically
        # cascade-deleted by the database.
        pass

    def test_cleanup_all_metadata_combined(self, test_db):
        """Verify cleanup handles multiple entity types simultaneously."""
        with test_db.session_scope() as session:
            # Create entry with some linked entities
            entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
            session.add(entry)
            session.flush()

            # Linked tag (preserved)
            linked_tag = Tag(name="linked")
            linked_tag.entries.append(entry)
            session.add(linked_tag)

            # Orphan tag (removed)
            orphan_tag = Tag(name="orphan")
            session.add(orphan_tag)

            # Linked scene (preserved) - Scene cannot be orphaned due to NOT NULL FK
            linked_scene = Scene(
                name="Linked Scene",
                description="Has entry",
                entry_id=entry.id,
            )
            session.add(linked_scene)

            session.commit()

        # Run cleanup
        result = test_db.cleanup_all_metadata()

        # Verify correct counts (only orphan tag should be removed)
        assert result["tags"] == 1
        assert result["scenes"] == 0  # No orphan scenes possible

        # Verify correct entities remain
        with test_db.session_scope() as session:
            assert session.query(Tag).filter_by(name="linked").first() is not None
            assert session.query(Tag).filter_by(name="orphan").first() is None
            assert session.query(Scene).filter_by(name="Linked Scene").first() is not None

    def test_cleanup_all_metadata_no_orphans(self, test_db):
        """Verify cleanup returns zero counts when no orphans exist."""
        with test_db.session_scope() as session:
            entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
            session.add(entry)
            session.flush()

            tag = Tag(name="used")
            tag.entries.append(entry)
            session.add(tag)
            session.commit()

        result = test_db.cleanup_all_metadata()

        # All counts should be zero
        assert result["tags"] == 0
        assert result["locations"] == 0
        assert result["scenes"] == 0
        assert result["themes"] == 0
        assert result["references"] == 0
        assert result["poem_versions"] == 0

    def test_cleanup_all_metadata_error_handling(self, test_db):
        """Verify cleanup handles errors gracefully."""
        from dev.core.exceptions import DatabaseError

        # Mock health_monitor to raise an error
        with patch.object(test_db.health_monitor, "bulk_cleanup_unused") as mock_cleanup:
            mock_cleanup.side_effect = Exception("Database error")

            with pytest.raises(DatabaseError, match="Cleanup operation failed"):
                test_db.cleanup_all_metadata()
