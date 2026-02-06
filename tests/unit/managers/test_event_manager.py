"""
test_event_manager.py
---------------------
Unit tests for EventManager CRUD operations.

Tests event management as a SimpleManager-backed entity with
many-to-many relationships to both Entry and Scene.

Target Coverage: 90%+
"""
from datetime import date

from dev.core.exceptions import DatabaseError, ValidationError
from dev.database.models import Entry, Event, Scene


class TestEventManagerExists:
    """Test EventManager.exists() method."""

    def test_exists_returns_false_when_not_found(self, event_manager):
        """Test exists returns False for non-existent event."""
        assert event_manager.exists("nonexistent") is False

    def test_exists_returns_true_when_found(self, event_manager, db_session):
        """Test exists returns True when event exists."""
        event = Event(name="Birthday Party")
        db_session.add(event)
        db_session.commit()

        assert event_manager.exists("Birthday Party") is True

    def test_exists_normalizes_input(self, event_manager, db_session):
        """Test exists normalizes whitespace."""
        event = Event(name="Birthday Party")
        db_session.add(event)
        db_session.commit()

        assert event_manager.exists("  Birthday Party  ") is True

    def test_exists_empty_string_returns_false(self, event_manager):
        """Test exists returns False for empty string."""
        assert event_manager.exists("") is False

    def test_exists_none_returns_false(self, event_manager):
        """Test exists returns False for None."""
        assert event_manager.exists(None) is False


class TestEventManagerGet:
    """Test EventManager.get() method."""

    def test_get_returns_none_when_not_found(self, event_manager):
        """Test get returns None for non-existent event."""
        result = event_manager.get("nonexistent")
        assert result is None

    def test_get_returns_event_when_found(self, event_manager, db_session):
        """Test get returns event when it exists."""
        event = Event(name="Birthday Party")
        db_session.add(event)
        db_session.commit()

        result = event_manager.get("Birthday Party")
        assert result is not None
        assert result.name == "Birthday Party"

    def test_get_normalizes_input(self, event_manager, db_session):
        """Test get normalizes whitespace."""
        event = Event(name="Birthday Party")
        db_session.add(event)
        db_session.commit()

        result = event_manager.get("  Birthday Party  ")
        assert result is not None
        assert result.name == "Birthday Party"

    def test_get_by_id(self, event_manager, db_session):
        """Test get_by_id returns event."""
        event = Event(name="Birthday Party")
        db_session.add(event)
        db_session.commit()

        result = event_manager.get_by_id(event.id)
        assert result is not None
        assert result.id == event.id


class TestEventManagerGetAll:
    """Test EventManager.get_all() method."""

    def test_get_all_empty(self, event_manager):
        """Test get_all returns empty list when no events."""
        result = event_manager.get_all()
        assert result == []

    def test_get_all_returns_all_events(self, event_manager, db_session):
        """Test get_all returns all events."""
        events = [
            Event(name="Birthday Party"),
            Event(name="Wedding"),
            Event(name="Graduation"),
        ]
        for event in events:
            db_session.add(event)
        db_session.commit()

        result = event_manager.get_all()
        assert len(result) == 3
        event_names = {e.name for e in result}
        assert event_names == {"Birthday Party", "Wedding", "Graduation"}

    def test_get_all_ordered_by_name(self, event_manager, db_session):
        """Test get_all returns events ordered alphabetically."""
        events = [
            Event(name="Zebra Event"),
            Event(name="Apple Event"),
            Event(name="Banana Event"),
        ]
        for event in events:
            db_session.add(event)
        db_session.commit()

        result = event_manager.get_all(order_by="name")
        event_names = [e.name for e in result]
        assert event_names == ["Apple Event", "Banana Event", "Zebra Event"]


class TestEventManagerCreate:
    """Test EventManager.create() method."""

    def test_create_event(self, event_manager, db_session):
        """Test creating an event."""
        event = event_manager.create({"name": "Birthday Party"})

        assert event is not None
        assert event.name == "Birthday Party"
        assert event.id is not None

    def test_create_duplicate_raises_error(self, event_manager, db_session):
        """Test creating duplicate event raises error."""
        event_manager.create({"name": "Birthday Party"})
        db_session.commit()

        with raises_database_error():
            event_manager.create({"name": "Birthday Party"})

    def test_create_empty_name_raises_error(self, event_manager):
        """Test creating event with empty name raises error."""
        with raises_validation_error():
            event_manager.create({"name": ""})

    def test_create_missing_name_raises_error(self, event_manager):
        """Test creating event without name raises error."""
        with raises_validation_error():
            event_manager.create({})


class TestEventManagerGetOrCreate:
    """Test EventManager.get_or_create() method."""

    def test_get_or_create_returns_existing(self, event_manager, db_session):
        """Test get_or_create returns existing event."""
        event = Event(name="Birthday Party")
        db_session.add(event)
        db_session.commit()
        original_id = event.id

        result = event_manager.get_or_create("Birthday Party")
        assert result.id == original_id

    def test_get_or_create_creates_new(self, event_manager, db_session):
        """Test get_or_create creates event when not exists."""
        result = event_manager.get_or_create("New Event")

        assert result is not None
        assert result.name == "New Event"
        assert result.id is not None

    def test_get_or_create_normalizes_name(self, event_manager, db_session):
        """Test get_or_create normalizes whitespace."""
        result = event_manager.get_or_create("  Birthday Party  ")
        assert result.name == "Birthday Party"


class TestEventManagerDelete:
    """Test EventManager.delete() method."""

    def test_delete_event(self, event_manager, db_session):
        """Test deleting an event."""
        event = Event(name="Birthday Party")
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        event_manager.delete(event)
        db_session.commit()

        result = event_manager.get_by_id(event_id)
        assert result is None


class TestEventManagerEntryRelationship:
    """Test EventManager entry relationship (M2M via event_entries)."""

    def test_link_event_to_entry(self, event_manager, db_session):
        """Test linking an event to an entry via generic link."""
        entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
        db_session.add(entry)
        db_session.flush()

        event = event_manager.get_or_create("Birthday Party")
        db_session.flush()

        event_manager._link(event, entry, "entries")
        db_session.commit()
        db_session.refresh(event)

        assert entry in event.entries

    def test_unlink_event_from_entry(self, event_manager, db_session):
        """Test unlinking an event from an entry."""
        entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
        db_session.add(entry)
        db_session.flush()

        event = event_manager.get_or_create("Birthday Party")
        db_session.flush()

        event_manager._link(event, entry, "entries")
        db_session.commit()

        result = event_manager._unlink(event, entry, "entries")
        db_session.commit()
        db_session.refresh(event)

        assert result is True
        assert entry not in event.entries


class TestEventManagerSceneRelationship:
    """Test EventManager scene relationship (M2M via event_scenes)."""

    def test_link_event_to_scene(self, event_manager, db_session):
        """Test linking an event to a scene."""
        entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
        db_session.add(entry)
        db_session.flush()

        scene = Scene(
            name="Morning Coffee",
            description="Having coffee at the cafe",
            entry_id=entry.id,
        )
        db_session.add(scene)
        db_session.flush()

        event = event_manager.get_or_create("Cafe Visit")
        db_session.flush()

        event_manager._link(event, scene, "scenes")
        db_session.commit()
        db_session.refresh(event)

        assert scene in event.scenes

    def test_unlink_event_from_scene(self, event_manager, db_session):
        """Test unlinking an event from a scene."""
        entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
        db_session.add(entry)
        db_session.flush()

        scene = Scene(
            name="Morning Coffee",
            description="Having coffee at the cafe",
            entry_id=entry.id,
        )
        db_session.add(scene)
        db_session.flush()

        event = event_manager.get_or_create("Cafe Visit")
        db_session.flush()

        event_manager._link(event, scene, "scenes")
        db_session.commit()

        result = event_manager._unlink(event, scene, "scenes")
        db_session.commit()
        db_session.refresh(event)

        assert result is True
        assert scene not in event.scenes

    def test_event_spans_multiple_scenes(self, event_manager, db_session):
        """Test an event can link to multiple scenes across entries."""
        entry1 = Entry(date=date(2024, 1, 15), file_path="/test/entry1.md")
        entry2 = Entry(date=date(2024, 1, 16), file_path="/test/entry2.md")
        db_session.add_all([entry1, entry2])
        db_session.flush()

        scene1 = Scene(
            name="Morning",
            description="Scene in first entry",
            entry_id=entry1.id,
        )
        scene2 = Scene(
            name="Evening",
            description="Scene in second entry",
            entry_id=entry2.id,
        )
        db_session.add_all([scene1, scene2])
        db_session.flush()

        event = event_manager.get_or_create("Multi-Day Event")
        db_session.flush()

        event_manager._link(event, scene1, "scenes")
        event_manager._link(event, scene2, "scenes")
        db_session.commit()
        db_session.refresh(event)

        assert len(event.scenes) == 2
        assert scene1 in event.scenes
        assert scene2 in event.scenes

    def test_invalid_relationship_raises_error(self, event_manager, db_session):
        """Test linking with invalid relationship name raises error."""
        event = event_manager.get_or_create("Test Event")
        db_session.flush()

        entry = Entry(date=date(2024, 1, 15), file_path="/test/entry.md")
        db_session.add(entry)
        db_session.flush()

        import pytest
        with pytest.raises(ValueError, match="does not have"):
            event_manager._link(event, entry, "nonexistent")


class TestEventManagerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_event_with_whitespace_normalized(self, event_manager, db_session):
        """Test event with whitespace is normalized."""
        event = event_manager.get_or_create("  Birthday Party  ")
        assert event.name == "Birthday Party"

    def test_event_with_unicode(self, event_manager, db_session):
        """Test event with unicode characters."""
        event = event_manager.get_or_create("Fête d'anniversaire")
        assert event.name == "Fête d'anniversaire"

    def test_event_with_hyphen(self, event_manager, db_session):
        """Test event with hyphen."""
        event = event_manager.get_or_create("New-Year-Party")
        assert event.name == "New-Year-Party"


# --- Helper context managers ---

import pytest
from contextlib import contextmanager


@contextmanager
def raises_database_error():
    """Context manager expecting DatabaseError."""
    with pytest.raises(DatabaseError):
        yield


@contextmanager
def raises_validation_error():
    """Context manager expecting ValidationError."""
    with pytest.raises(ValidationError):
        yield
