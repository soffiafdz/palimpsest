"""
test_tag_manager.py
-------------------
Unit tests for TagManager CRUD operations.

Tests tag management - the simplest entity in the system with only
a many-to-many relationship to entries.

Target Coverage: 90%+
"""
from dev.database.models import Tag


class TestTagManagerExists:
    """Test TagManager.exists() method."""

    def test_exists_returns_false_when_not_found(self, tag_manager):
        """Test exists returns False for non-existent tag."""
        assert tag_manager.exists("nonexistent") is False

    def test_exists_returns_true_when_found(self, tag_manager, db_session):
        """Test exists returns True when tag exists."""
        # Create tag directly via SQLAlchemy (avoiding decorator issue)
        tag = Tag(tag="python")
        db_session.add(tag)
        db_session.commit()

        assert tag_manager.exists("python") is True

    def test_exists_normalizes_input(self, tag_manager, db_session):
        """Test exists normalizes whitespace."""
        tag = Tag(tag="python")
        db_session.add(tag)
        db_session.commit()

        assert tag_manager.exists("  python  ") is True

    def test_exists_empty_string_returns_false(self, tag_manager):
        """Test exists returns False for empty string."""
        assert tag_manager.exists("") is False

    def test_exists_none_returns_false(self, tag_manager):
        """Test exists returns False for None."""
        assert tag_manager.exists(None) is False


class TestTagManagerGet:
    """Test TagManager.get() method."""

    def test_get_returns_none_when_not_found(self, tag_manager):
        """Test get returns None for non-existent tag."""
        result = tag_manager.get("nonexistent")
        assert result is None

    def test_get_returns_tag_when_found(self, tag_manager, db_session):
        """Test get returns tag when it exists."""
        tag = Tag(tag="python")
        db_session.add(tag)
        db_session.commit()

        result = tag_manager.get("python")
        assert result is not None
        assert result.tag == "python"

    def test_get_normalizes_input(self, tag_manager, db_session):
        """Test get normalizes whitespace."""
        tag = Tag(tag="python")
        db_session.add(tag)
        db_session.commit()

        result = tag_manager.get("  python  ")
        assert result is not None
        assert result.tag == "python"

    def test_get_by_id(self, tag_manager, db_session):
        """Test get_by_id returns tag."""
        tag = Tag(tag="python")
        db_session.add(tag)
        db_session.commit()

        result = tag_manager.get_by_id(tag.id)
        assert result is not None
        assert result.id == tag.id


class TestTagManagerGetAll:
    """Test TagManager.get_all() method."""

    def test_get_all_empty(self, tag_manager):
        """Test get_all returns empty list when no tags."""
        result = tag_manager.get_all()
        assert result == []

    def test_get_all_returns_all_tags(self, tag_manager, db_session):
        """Test get_all returns all tags."""
        tags = [Tag(tag="python"), Tag(tag="testing"), Tag(tag="database")]
        for tag in tags:
            db_session.add(tag)
        db_session.commit()

        result = tag_manager.get_all()
        assert len(result) == 3
        tag_names = {t.tag for t in result}
        assert tag_names == {"python", "testing", "database"}

    def test_get_all_ordered_by_tag_name(self, tag_manager, db_session):
        """Test get_all returns tags ordered alphabetically."""
        tags = [Tag(tag="zebra"), Tag(tag="apple"), Tag(tag="banana")]
        for tag in tags:
            db_session.add(tag)
        db_session.commit()

        result = tag_manager.get_all(order_by="tag")
        tag_names = [t.tag for t in result]
        assert tag_names == ["apple", "banana", "zebra"]


class TestTagManagerGetOrCreate:
    """Test TagManager.get_or_create() method."""

    def test_get_or_create_returns_existing_tag(self, tag_manager, db_session):
        """Test get_or_create returns existing tag."""
        tag = Tag(tag="python")
        db_session.add(tag)
        db_session.commit()
        original_id = tag.id

        result = tag_manager.get_or_create("python")
        assert result.id == original_id

    def test_get_or_create_creates_new_tag(self, tag_manager, db_session):
        """Test get_or_create creates tag when not exists."""
        result = tag_manager.get_or_create("newtag")

        assert result is not None
        assert result.tag == "newtag"
        assert result.id is not None

    def test_get_or_create_normalizes_tag_name(self, tag_manager, db_session):
        """Test get_or_create normalizes whitespace."""
        result = tag_manager.get_or_create("  python  ")

        assert result.tag == "python"


class TestTagManagerDelete:
    """Test TagManager.delete() method."""

    def test_delete_tag(self, tag_manager, db_session):
        """Test deleting a tag."""
        tag = Tag(tag="python")
        db_session.add(tag)
        db_session.commit()
        tag_id = tag.id

        tag_manager.delete(tag)
        db_session.commit()

        result = tag_manager.get_by_id(tag_id)
        assert result is None


class TestTagManagerLinkToEntry:
    """Test TagManager.link_to_entry() method."""

    def test_link_tag_to_entry(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test linking a tag to an entry."""
        # Create entry
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Create and link tag
        tag_manager.link_to_entry(entry, "python")
        db_session.commit()
        db_session.refresh(entry)

        assert len(entry.tags) >= 1
        tag_names = {t.tag for t in entry.tags}
        assert "python" in tag_names

    def test_link_creates_tag_if_not_exists(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test link_to_entry creates tag if doesn't exist."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        tag_manager.link_to_entry(entry, "newtag")
        db_session.commit()

        # Tag should now exist
        tag = tag_manager.get("newtag")
        assert tag is not None

    def test_link_tag_multiple_times_is_idempotent(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test linking same tag multiple times doesn't create duplicates."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        tag_manager.link_to_entry(entry, "python")
        tag_manager.link_to_entry(entry, "python")
        db_session.commit()
        db_session.refresh(entry)

        # Should only have one "python" tag
        python_tags = [t for t in entry.tags if t.tag == "python"]
        assert len(python_tags) == 1


class TestTagManagerUnlinkFromEntry:
    """Test TagManager.unlink_from_entry() method."""

    def test_unlink_tag_from_entry(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test unlinking a tag from entry."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Link then unlink
        tag_manager.link_to_entry(entry, "python")
        db_session.commit()
        tag_manager.unlink_from_entry(entry, "python")
        db_session.commit()
        db_session.refresh(entry)

        python_tags = [t for t in entry.tags if t.tag == "python"]
        assert len(python_tags) == 0

    def test_unlink_nonexistent_tag_is_safe(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test unlinking non-existent tag doesn't raise error."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Should not raise error
        tag_manager.unlink_from_entry(entry, "nonexistent")
        db_session.commit()


class TestTagManagerUpdateEntryTags:
    """Test TagManager.update_entry_tags() method."""

    def test_update_entry_tags_incremental(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test adding tags incrementally."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Add initial tags
        tag_manager.update_entry_tags(entry, ["python", "testing"], incremental=True)
        db_session.commit()
        db_session.refresh(entry)

        # Add more tags
        tag_manager.update_entry_tags(entry, ["database"], incremental=True)
        db_session.commit()
        db_session.refresh(entry)

        tag_names = {t.tag for t in entry.tags}
        assert len(tag_names) >= 3
        assert "python" in tag_names
        assert "testing" in tag_names
        assert "database" in tag_names

    def test_update_entry_tags_replacement(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test replacing all tags."""
        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Set initial tags
        tag_manager.update_entry_tags(entry, ["python", "testing"], incremental=False)
        db_session.commit()
        db_session.refresh(entry)

        # Replace with new tags
        tag_manager.update_entry_tags(entry, ["newtag"], incremental=False)
        db_session.commit()
        db_session.refresh(entry)

        tag_names = {t.tag for t in entry.tags}
        assert tag_names == {"newtag"}


class TestTagManagerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_tag_with_whitespace_normalized(self, tag_manager, db_session):
        """Test tag with whitespace is normalized."""
        tag = tag_manager.get_or_create("  python  ")
        assert tag.tag == "python"

    def test_tag_with_unicode(self, tag_manager, db_session):
        """Test tag with unicode characters."""
        tag = tag_manager.get_or_create("café")
        assert tag.tag == "café"

    def test_tag_with_hyphen(self, tag_manager, db_session):
        """Test tag with hyphen."""
        tag = tag_manager.get_or_create("machine-learning")
        assert tag.tag == "machine-learning"

    def test_get_all_with_usage_count_ordering(self, tag_manager, entry_manager, tmp_dir, db_session):
        """Test get_all can order by usage count."""
        # Create tags with different usage counts
        file_path1 = tmp_dir / "2024-01-15.md"
        file_path1.write_text("# Test")
        entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path1),
            "tags": ["popular", "common"]
        })

        file_path2 = tmp_dir / "2024-01-16.md"
        file_path2.write_text("# Test")
        entry_manager.create({
            "date": "2024-01-16",
            "file_path": str(file_path2),
            "tags": ["popular", "rare"]
        })
        db_session.commit()

        result = tag_manager.get_all(order_by="usage_count")
        # "popular" should be first (used 2 times)
        assert result[0].tag == "popular"
