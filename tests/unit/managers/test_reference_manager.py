"""
test_reference_manager.py
--------------------------
Unit tests for ReferenceManager CRUD operations.

Tests reference source and reference management, including the parent-child
relationship between ReferenceSource and Reference entities.

Target Coverage: 90%+
"""
import pytest
from dev.database.models import ReferenceSource, Reference, ReferenceType, ReferenceMode
from dev.core.exceptions import ValidationError, DatabaseError


class TestReferenceManagerSourceExists:
    """Test ReferenceManager.source_exists() method."""

    def test_source_exists_returns_false_when_not_found(self, reference_manager):
        """Test source_exists returns False for non-existent source."""
        assert reference_manager.source_exists("Nonexistent Book") is False

    def test_source_exists_returns_true_when_found(self, reference_manager, db_session):
        """Test source_exists returns True when source exists."""
        reference_manager.create_source({
            "type": "book",
            "title": "The Great Gatsby"
        })
        db_session.commit()

        assert reference_manager.source_exists("The Great Gatsby") is True

    def test_source_exists_normalizes_input(self, reference_manager, db_session):
        """Test source_exists normalizes whitespace."""
        reference_manager.create_source({
            "type": "book",
            "title": "The Great Gatsby"
        })
        db_session.commit()

        assert reference_manager.source_exists("  The Great Gatsby  ") is True


class TestReferenceManagerGetSource:
    """Test ReferenceManager.get_source() method."""

    def test_get_source_returns_none_when_not_found(self, reference_manager):
        """Test get_source returns None for non-existent source."""
        result = reference_manager.get_source(title="Nonexistent")
        assert result is None

    def test_get_source_by_title(self, reference_manager, db_session):
        """Test get source by title."""
        created = reference_manager.create_source({
            "type": "book",
            "title": "1984"
        })
        db_session.commit()

        result = reference_manager.get_source(title="1984")
        assert result is not None
        assert result.id == created.id
        assert result.title == "1984"

    def test_get_source_by_id(self, reference_manager, db_session):
        """Test get source by ID."""
        created = reference_manager.create_source({
            "type": "article",
            "title": "Research Paper"
        })
        db_session.commit()

        result = reference_manager.get_source(source_id=created.id)
        assert result is not None
        assert result.id == created.id


class TestReferenceManagerGetAllSources:
    """Test ReferenceManager.get_all_sources() method."""

    def test_get_all_sources_empty(self, reference_manager):
        """Test get_all_sources returns empty when no sources."""
        result = reference_manager.get_all_sources()
        assert result == []

    def test_get_all_sources_returns_all(self, reference_manager, db_session):
        """Test get_all_sources returns all sources."""
        reference_manager.create_source({"type": "book", "title": "Book A"})
        reference_manager.create_source({"type": "article", "title": "Article B"})
        reference_manager.create_source({"type": "film", "title": "Film C"})
        db_session.commit()

        result = reference_manager.get_all_sources()
        assert len(result) == 3

    def test_get_all_sources_ordered_by_title(self, reference_manager, db_session):
        """Test get_all_sources returns sources ordered by title."""
        reference_manager.create_source({"type": "book", "title": "Zebra"})
        reference_manager.create_source({"type": "book", "title": "Apple"})
        reference_manager.create_source({"type": "book", "title": "Banana"})
        db_session.commit()

        result = reference_manager.get_all_sources()
        titles = [s.title for s in result]
        assert titles == ["Apple", "Banana", "Zebra"]

    def test_get_all_sources_filtered_by_type(self, reference_manager, db_session):
        """Test get_all_sources with type filter."""
        reference_manager.create_source({"type": "book", "title": "Book 1"})
        reference_manager.create_source({"type": "book", "title": "Book 2"})
        reference_manager.create_source({"type": "film", "title": "Film 1"})
        db_session.commit()

        result = reference_manager.get_all_sources(source_type=ReferenceType.BOOK)
        assert len(result) == 2
        assert all(s.type == ReferenceType.BOOK for s in result)


class TestReferenceManagerCreateSource:
    """Test ReferenceManager.create_source() method."""

    def test_create_source_minimal(self, reference_manager, db_session):
        """Test creating source with minimal fields."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "Simple Book"
        })

        assert source is not None
        assert source.id is not None
        assert source.title == "Simple Book"
        assert source.type == ReferenceType.BOOK

    def test_create_source_with_author(self, reference_manager, db_session):
        """Test creating source with author."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "The Hobbit",
            "author": "J.R.R. Tolkien"
        })

        assert source.author == "J.R.R. Tolkien"

    def test_create_source_missing_type_raises_error(self, reference_manager):
        """Test creating source without type raises error."""
        with pytest.raises(ValidationError):
            reference_manager.create_source({"title": "No Type"})

    def test_create_source_missing_title_raises_error(self, reference_manager):
        """Test creating source without title raises error."""
        with pytest.raises(ValidationError):
            reference_manager.create_source({"type": "book"})

    def test_create_source_duplicate_title_raises_error(self, reference_manager, db_session):
        """Test creating source with duplicate title raises error."""
        reference_manager.create_source({
            "type": "book",
            "title": "Duplicate"
        })
        db_session.commit()

        with pytest.raises(DatabaseError) as exc_info:
            reference_manager.create_source({
                "type": "book",
                "title": "Duplicate"
            })
        assert "already exists" in str(exc_info.value).lower()

    def test_create_source_string_type_converted(self, reference_manager, db_session):
        """Test creating source with string type converts to enum."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "String Type Test"
        })

        assert source.type == ReferenceType.BOOK


class TestReferenceManagerUpdateSource:
    """Test ReferenceManager.update_source() method."""

    def test_update_source_title(self, reference_manager, db_session):
        """Test updating source title."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "Old Title"
        })
        db_session.commit()

        reference_manager.update_source(source, {"title": "New Title"})
        db_session.commit()
        db_session.refresh(source)

        assert source.title == "New Title"

    def test_update_source_author(self, reference_manager, db_session):
        """Test updating source author."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "Test Book"
        })
        db_session.commit()

        reference_manager.update_source(source, {"author": "New Author"})
        db_session.commit()
        db_session.refresh(source)

        assert source.author == "New Author"

    def test_update_source_type(self, reference_manager, db_session):
        """Test updating source type."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "Test Source"
        })
        db_session.commit()

        reference_manager.update_source(source, {"type": "article"})
        db_session.commit()
        db_session.refresh(source)

        assert source.type == ReferenceType.ARTICLE

    def test_update_nonexistent_source_raises_error(self, reference_manager):
        """Test updating non-existent source raises error."""
        fake_source = ReferenceSource()
        fake_source.id = 99999

        with pytest.raises(DatabaseError):
            reference_manager.update_source(fake_source, {"title": "Test"})


class TestReferenceManagerDeleteSource:
    """Test ReferenceManager.delete_source() method."""

    def test_delete_source(self, reference_manager, db_session):
        """Test deleting a source."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "To Delete"
        })
        db_session.commit()
        source_id = source.id

        reference_manager.delete_source(source)
        db_session.commit()

        result = reference_manager.get_source(source_id=source_id)
        assert result is None


class TestReferenceManagerGetOrCreateSource:
    """Test ReferenceManager.get_or_create_source() method."""

    def test_get_or_create_returns_existing(self, reference_manager, db_session):
        """Test get_or_create returns existing source."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "Existing"
        })
        db_session.commit()
        original_id = source.id

        result = reference_manager.get_or_create_source("Existing", "book")
        assert result.id == original_id

    def test_get_or_create_creates_new(self, reference_manager, db_session):
        """Test get_or_create creates new source when not exists."""
        result = reference_manager.get_or_create_source("New Source", "book", "Author")

        assert result is not None
        assert result.title == "New Source"
        assert result.type == ReferenceType.BOOK
        assert result.author == "Author"

    def test_get_or_create_empty_title_raises_error(self, reference_manager):
        """Test get_or_create with empty title raises error."""
        with pytest.raises(ValidationError):
            reference_manager.get_or_create_source("", "book")


class TestReferenceManagerCreateReference:
    """Test ReferenceManager.create_reference() method."""

    def test_create_reference_with_source(self, reference_manager, entry_manager, tmp_dir, db_session):
        """Test creating reference linked to source."""
        # Create entry
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        # Create source
        source = reference_manager.create_source({
            "type": "book",
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald"
        })
        db_session.commit()

        reference = reference_manager.create_reference({
            "content": "So we beat on...",
            "entry": entry,
            "source": source
        })

        assert reference.source is not None
        assert reference.source.id == source.id

    # Note: test_create_reference_with_speaker removed - speaker attribute
    # no longer exists on Reference model

    def test_create_reference_missing_content_and_description_raises_error(self, reference_manager, entry_manager, tmp_dir, db_session):
        """Test creating reference without content or description raises error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        with pytest.raises(ValidationError) as exc_info:
            reference_manager.create_reference({"entry": entry})
        assert "content" in str(exc_info.value).lower() or "description" in str(exc_info.value).lower()

    def test_create_reference_missing_entry_raises_error(self, reference_manager):
        """Test creating reference without entry raises error."""
        with pytest.raises(ValidationError) as exc_info:
            reference_manager.create_reference({"content": "Test content"})
        assert "entry" in str(exc_info.value).lower()


class TestReferenceManagerUpdateReference:
    """Test ReferenceManager.update_reference() method."""

    def test_update_nonexistent_reference_raises_error(self, reference_manager):
        """Test updating non-existent reference raises error."""
        fake_reference = Reference()
        fake_reference.id = 99999

        with pytest.raises(DatabaseError):
            reference_manager.update_reference(fake_reference, {"content": "Test"})


class TestReferenceManagerDeleteReference:
    """Test ReferenceManager.delete_reference() method."""

class TestReferenceManagerGetReference:
    """Test ReferenceManager.get_reference() method."""

    def test_get_reference_returns_none_when_not_found(self, reference_manager):
        """Test get_reference returns None for non-existent reference."""
        result = reference_manager.get_reference(99999)
        assert result is None


class TestReferenceManagerGetAllReferences:
    """Test ReferenceManager.get_all_references() method."""

    def test_get_all_references_empty(self, reference_manager):
        """Test get_all_references returns empty when no references."""
        result = reference_manager.get_all_references()
        assert result == []

class TestReferenceManagerQueryMethods:
    """Test ReferenceManager query methods."""

    def test_get_references_for_source(self, reference_manager, entry_manager, tmp_dir, db_session):
        """Test get_references_for_source returns references from specific source."""
        # Create entry
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })

        # Create source
        source = reference_manager.create_source({
            "type": "book",
            "title": "Test Book"
        })
        db_session.commit()

        # Create references with source
        reference_manager.create_reference({
            "content": "Quote 1",
            "entry": entry,
            "source": source
        })
        reference_manager.create_reference({
            "content": "Quote 2",
            "entry": entry,
            "source": source
        })
        db_session.commit()

        references = reference_manager.get_references_for_source(source)
        assert len(references) >= 2

    def test_get_sources_by_type(self, reference_manager, db_session):
        """Test get_sources_by_type returns sources of specific type."""
        reference_manager.create_source({"type": "book", "title": "Book 1"})
        reference_manager.create_source({"type": "book", "title": "Book 2"})
        reference_manager.create_source({"type": "film", "title": "Film 1"})
        db_session.commit()

        result = reference_manager.get_sources_by_type("book")
        assert len(result) == 2
        assert all(s.type == ReferenceType.BOOK for s in result)


class TestReferenceManagerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_source_with_whitespace_title_normalized(self, reference_manager, db_session):
        """Test source title with whitespace is normalized."""
        source = reference_manager.create_source({
            "type": "book",
            "title": "  Spaces  "
        })
        assert source.title == "Spaces"

    def test_source_without_author(self, reference_manager, db_session):
        """Test creating source without author is allowed."""
        source = reference_manager.create_source({
            "type": "film",
            "title": "No Author Film"
        })
        assert source.author is None

