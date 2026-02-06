"""
test_poem_manager.py
--------------------
Unit tests for PoemManager CRUD operations and version tracking.

Tests poem management including version tracking, hash-based deduplication,
and parent-child relationship between Poem and PoemVersion entities.

Target Coverage: 90%+
"""
import pytest

from dev.database.models import Poem, PoemVersion
from dev.core.exceptions import ValidationError, DatabaseError


class TestPoemManagerExists:
    """Test PoemManager.poem_exists() method."""

    def test_exists_returns_false_when_not_found(self, poem_manager):
        """Test exists returns False for non-existent poem."""
        assert poem_manager.poem_exists("Nonexistent Poem") is False

    def test_exists_returns_true_when_found(self, poem_manager, db_session):
        """Test exists returns True when poem exists."""
        poem_manager.create_poem({"title": "Autumn Reverie"})
        db_session.commit()

        assert poem_manager.poem_exists("Autumn Reverie") is True

    def test_exists_normalizes_input(self, poem_manager, db_session):
        """Test exists normalizes whitespace."""
        poem_manager.create_poem({"title": "Autumn Reverie"})
        db_session.commit()

        assert poem_manager.poem_exists("  Autumn Reverie  ") is True

    def test_exists_empty_string_returns_false(self, poem_manager):
        """Test exists returns False for empty string."""
        assert poem_manager.poem_exists("") is False


class TestPoemManagerGetPoem:
    """Test PoemManager.get_poem() method."""

    def test_get_poem_returns_none_when_not_found(self, poem_manager):
        """Test get_poem returns None for non-existent poem."""
        result = poem_manager.get_poem(title="Nonexistent")
        assert result is None

    def test_get_poem_by_title(self, poem_manager, db_session):
        """Test get poem by title."""
        created = poem_manager.create_poem({"title": "Summer Days"})
        db_session.commit()

        result = poem_manager.get_poem(title="Summer Days")
        assert result is not None
        assert result.id == created.id
        assert result.title == "Summer Days"

    def test_get_poem_by_id(self, poem_manager, db_session):
        """Test get poem by ID."""
        created = poem_manager.create_poem({"title": "Winter Nights"})
        db_session.commit()

        result = poem_manager.get_poem(poem_id=created.id)
        assert result is not None
        assert result.id == created.id

    def test_get_poem_returns_first_when_multiple_same_title(self, poem_manager, db_session):
        """Test get_poem returns first match when multiple poems have same title."""
        poem1 = poem_manager.create_poem({"title": "Duplicate"})
        poem_manager.create_poem({"title": "Duplicate"})
        db_session.commit()

        result = poem_manager.get_poem(title="Duplicate")
        assert result is not None
        assert result.id == poem1.id


class TestPoemManagerGetAllPoems:
    """Test PoemManager.get_all_poems() method."""

    def test_get_all_poems_empty(self, poem_manager):
        """Test get_all_poems returns empty list when no poems."""
        result = poem_manager.get_all_poems()
        assert result == []

    def test_get_all_poems_returns_all(self, poem_manager, db_session):
        """Test get_all_poems returns all poems."""
        poem_manager.create_poem({"title": "Poem A"})
        poem_manager.create_poem({"title": "Poem B"})
        poem_manager.create_poem({"title": "Poem C"})
        db_session.commit()

        result = poem_manager.get_all_poems()
        assert len(result) == 3
        titles = {p.title for p in result}
        assert titles == {"Poem A", "Poem B", "Poem C"}

    def test_get_all_poems_ordered_by_title(self, poem_manager, db_session):
        """Test get_all_poems returns poems ordered by title."""
        poem_manager.create_poem({"title": "Zebra"})
        poem_manager.create_poem({"title": "Apple"})
        poem_manager.create_poem({"title": "Banana"})
        db_session.commit()

        result = poem_manager.get_all_poems()
        titles = [p.title for p in result]
        assert titles == ["Apple", "Banana", "Zebra"]


class TestPoemManagerCreatePoem:
    """Test PoemManager.create_poem() method."""

    def test_create_minimal_poem(self, poem_manager, db_session):
        """Test creating poem with minimal fields."""
        poem = poem_manager.create_poem({"title": "Simple Poem"})

        assert poem is not None
        assert poem.id is not None
        assert poem.title == "Simple Poem"

    def test_create_poem_missing_title_raises_error(self, poem_manager):
        """Test creating poem without title raises error."""
        with pytest.raises(ValidationError):
            poem_manager.create_poem({})

    def test_create_poem_empty_title_raises_error(self, poem_manager):
        """Test creating poem with empty title raises error."""
        with pytest.raises(ValidationError):
            poem_manager.create_poem({"title": ""})

    def test_create_poem_allows_duplicate_titles(self, poem_manager, db_session):
        """Test multiple poems can have same title."""
        poem1 = poem_manager.create_poem({"title": "Duplicate"})
        poem2 = poem_manager.create_poem({"title": "Duplicate"})
        db_session.commit()

        assert poem1.id != poem2.id
        assert poem1.title == poem2.title == "Duplicate"


class TestPoemManagerUpdatePoem:
    """Test PoemManager.update_poem() method."""

    def test_update_poem_title(self, poem_manager, db_session):
        """Test updating poem title."""
        poem = poem_manager.create_poem({"title": "Old Title"})
        db_session.commit()

        poem_manager.update_poem(poem, {"title": "New Title"})
        db_session.commit()
        db_session.refresh(poem)

        assert poem.title == "New Title"

    def test_update_nonexistent_poem_raises_error(self, poem_manager):
        """Test updating non-existent poem raises error."""
        fake_poem = Poem()
        fake_poem.id = 99999

        with pytest.raises(DatabaseError):
            poem_manager.update_poem(fake_poem, {"title": "Test"})


class TestPoemManagerDeletePoem:
    """Test PoemManager.delete_poem() method."""

    def test_delete_poem(self, poem_manager, db_session):
        """Test deleting a poem."""
        poem = poem_manager.create_poem({"title": "To Delete"})
        db_session.commit()
        poem_id = poem.id

        poem_manager.delete_poem(poem)
        db_session.commit()

        result = poem_manager.get_poem(poem_id=poem_id)
        assert result is None


class TestPoemManagerGetOrCreatePoem:
    """Test PoemManager.get_or_create_poem() method."""

    def test_get_or_create_returns_existing(self, poem_manager, db_session):
        """Test get_or_create returns existing poem."""
        poem = poem_manager.create_poem({"title": "Existing"})
        db_session.commit()
        original_id = poem.id

        result = poem_manager.get_or_create_poem("Existing")
        assert result.id == original_id

    def test_get_or_create_creates_new(self, poem_manager, db_session):
        """Test get_or_create creates new poem when not exists."""
        result = poem_manager.get_or_create_poem("New Poem")

        assert result is not None
        assert result.title == "New Poem"
        assert result.id is not None

    def test_get_or_create_empty_title_raises_error(self, poem_manager):
        """Test get_or_create with empty title raises error."""
        with pytest.raises(ValidationError):
            poem_manager.get_or_create_poem("")


class TestPoemManagerCreateVersion:
    """Test PoemManager.create_version() method."""

    def test_create_version_with_explicit_poem(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test creating version with explicit poem object."""
        # Create entry first
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        poem = poem_manager.create_poem({"title": "Seasons"})
        db_session.commit()

        version = poem_manager.create_version({
            "title": "Seasons",
            "content": "Spring, summer, fall, winter.",
            "poem": poem,
            "entry": entry
        })

        assert version.poem.id == poem.id

    def test_create_version_missing_title_raises_error(self, poem_manager):
        """Test creating version without title raises error."""
        with pytest.raises(ValidationError):
            poem_manager.create_version({"content": "Content without title"})

    def test_create_version_missing_content_raises_error(self, poem_manager):
        """Test creating version without content raises error."""
        with pytest.raises(ValidationError):
            poem_manager.create_version({"title": "Title without content"})

    def test_create_version_deduplication(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test creating duplicate version returns existing."""
        # Create entry first
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Create first version
        version1 = poem_manager.create_version({
            "title": "Duplicate Test",
            "content": "Same content here.",
            "entry": entry
        })
        db_session.commit()

        # Try to create duplicate
        version2 = poem_manager.create_version({
            "title": "Duplicate Test",
            "content": "Same content here.",  # Same content
            "poem": version1.poem,
            "entry": entry
        })

        # Should return the same version
        assert version2.id == version1.id


class TestPoemManagerUpdateVersion:
    """Test PoemManager.update_version() method."""

    def test_update_nonexistent_version_raises_error(self, poem_manager):
        """Test updating non-existent version raises error."""
        fake_version = PoemVersion()
        fake_version.id = 99999

        with pytest.raises(DatabaseError):
            poem_manager.update_version(fake_version, {"content": "Test"})


class TestPoemManagerDeleteVersion:
    """Test PoemManager.delete_version() method."""

    def test_delete_version(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test deleting a version."""
        # Create entry first
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        version = poem_manager.create_version({
            "title": "To Delete",
            "content": "Will be deleted.",
            "entry": entry
        })
        db_session.commit()
        version_id = version.id

        poem_manager.delete_version(version)
        db_session.commit()

        result = poem_manager.get_version(version_id)
        assert result is None

    def test_delete_version_keeps_parent_poem(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test deleting version doesn't delete parent poem."""
        # Create entry first
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        version = poem_manager.create_version({
            "title": "Keep Poem",
            "content": "Delete version only.",
            "entry": entry
        })
        db_session.commit()
        poem_id = version.poem.id

        poem_manager.delete_version(version)
        db_session.commit()

        # Poem should still exist
        poem = poem_manager.get_poem(poem_id=poem_id)
        assert poem is not None


class TestPoemManagerGetVersion:
    """Test PoemManager.get_version() method."""

    def test_get_version_by_id(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test get version by ID."""
        # Create entry first
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        created = poem_manager.create_version({
            "title": "Get Test",
            "content": "Test content.",
            "entry": entry
        })
        db_session.commit()

        result = poem_manager.get_version(created.id)
        assert result is not None
        assert result.id == created.id

    def test_get_version_returns_none_when_not_found(self, poem_manager):
        """Test get_version returns None for non-existent version."""
        result = poem_manager.get_version(99999)
        assert result is None


class TestPoemManagerGetAllVersions:
    """Test PoemManager.get_all_versions() method."""

    def test_get_all_versions_empty(self, poem_manager):
        """Test get_all_versions returns empty when no versions."""
        result = poem_manager.get_all_versions()
        assert result == []

    def test_get_all_versions_returns_all(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test get_all_versions returns all versions."""
        # Create entries
        file_path1 = tmp_dir / "2024-01-15.md"
        file_path1.write_text("# Test")
        entry1 = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path1)
        })
        file_path2 = tmp_dir / "2024-01-16.md"
        file_path2.write_text("# Test")
        entry2 = entry_manager.create({
            "date": "2024-01-16",
            "file_path": str(file_path2)
        })
        file_path3 = tmp_dir / "2024-01-17.md"
        file_path3.write_text("# Test")
        entry3 = entry_manager.create({
            "date": "2024-01-17",
            "file_path": str(file_path3)
        })
        db_session.commit()

        poem_manager.create_version({"title": "V1", "content": "Content 1", "entry": entry1})
        poem_manager.create_version({"title": "V2", "content": "Content 2", "entry": entry2})
        poem_manager.create_version({"title": "V3", "content": "Content 3", "entry": entry3})
        db_session.commit()

        result = poem_manager.get_all_versions()
        assert len(result) >= 3


class TestPoemManagerGetVersionsForEntry:
    """Test PoemManager.get_versions_for_entry() method."""

    def test_get_versions_for_entry(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test get_versions_for_entry returns versions for specific entry."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        poem_manager.create_version({
            "title": "Entry Poem 1",
            "content": "First poem.",
            "entry": entry
        })

        poem_manager.create_version({
            "title": "Entry Poem 2",
            "content": "Second poem.",
            "entry": entry
        })
        db_session.commit()

        versions = poem_manager.get_versions_for_entry(entry)
        assert len(versions) >= 2


class TestPoemManagerGetLatestVersion:
    """Test PoemManager.get_latest_version() method."""

    def test_get_latest_version_returns_none_when_no_versions(self, poem_manager, db_session):
        """Test get_latest_version returns None when poem has no versions."""
        poem = poem_manager.create_poem({"title": "Empty Poem"})
        db_session.commit()

        result = poem_manager.get_latest_version(poem)
        assert result is None


class TestPoemManagerGetPoemsByTitle:
    """Test PoemManager.get_poems_by_title() method."""

    def test_get_poems_by_title_single(self, poem_manager, db_session):
        """Test get_poems_by_title with single poem."""
        poem_manager.create_poem({"title": "Unique Title"})
        db_session.commit()

        result = poem_manager.get_poems_by_title("Unique Title")
        assert len(result) == 1
        assert result[0].title == "Unique Title"

    def test_get_poems_by_title_multiple(self, poem_manager, db_session):
        """Test get_poems_by_title with multiple poems."""
        poem_manager.create_poem({"title": "Same Title"})
        poem_manager.create_poem({"title": "Same Title"})
        poem_manager.create_poem({"title": "Same Title"})
        db_session.commit()

        result = poem_manager.get_poems_by_title("Same Title")
        assert len(result) == 3

    def test_get_poems_by_title_empty(self, poem_manager):
        """Test get_poems_by_title returns empty when no matches."""
        result = poem_manager.get_poems_by_title("Nonexistent")
        assert result == []


class TestPoemManagerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_poem_with_whitespace_title_normalized(self, poem_manager, db_session):
        """Test poem title with whitespace is normalized."""
        poem = poem_manager.create_poem({"title": "  Spaces  "})
        assert poem.title == "Spaces"

    def test_poem_can_have_no_versions(self, poem_manager, db_session):
        """Test poem can exist without versions."""
        poem = poem_manager.create_poem({"title": "No Versions"})
        db_session.commit()

        versions = poem_manager.get_versions_for_poem(poem)
        assert len(versions) == 0

    def test_version_with_unicode_content(self, poem_manager, entry_manager, tmp_dir, db_session):
        """Test version with unicode characters."""
        # Create entry first
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        version = poem_manager.create_version({
            "title": "Unicode Test",
            "content": "Café français with émojis 🌟",
            "entry": entry
        })

        assert "Café" in version.content
        assert "🌟" in version.content
