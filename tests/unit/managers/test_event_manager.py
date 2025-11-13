"""
test_event_manager.py
---------------------
Unit tests for EventManager CRUD operations.

Tests event management including soft delete, restore, and relationships
with entries and people.

Target Coverage: 90%+
"""
import pytest
from datetime import date, datetime, timezone
from dev.database.models import Event, Entry, Person
from dev.core.exceptions import ValidationError, DatabaseError


class TestEventManagerExists:
    """Test EventManager.exists() method."""

    def test_exists_returns_false_when_not_found(self, event_manager):
        """Test exists returns False for non-existent event."""
        assert event_manager.exists("nonexistent") is False

    def test_exists_returns_true_when_found(self, event_manager, db_session):
        """Test exists returns True when event exists."""
        event = Event(event="paris_trip", title="Paris Trip")
        db_session.add(event)
        db_session.commit()

        assert event_manager.exists("paris_trip") is True

    def test_exists_normalizes_input(self, event_manager, db_session):
        """Test exists normalizes whitespace."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        assert event_manager.exists("  paris_trip  ") is True

    def test_exists_empty_string_returns_false(self, event_manager):
        """Test exists returns False for empty string."""
        assert event_manager.exists("") is False

    def test_exists_none_returns_false(self, event_manager):
        """Test exists returns False for None."""
        assert event_manager.exists(None) is False

    def test_exists_excludes_deleted_by_default(self, event_manager, db_session):
        """Test exists excludes soft-deleted events by default."""
        event = Event(event="deleted_trip", deleted_at=datetime.now(timezone.utc))
        db_session.add(event)
        db_session.commit()

        assert event_manager.exists("deleted_trip") is False

    def test_exists_includes_deleted_when_requested(self, event_manager, db_session):
        """Test exists includes deleted events when requested."""
        event = Event(event="deleted_trip", deleted_at=datetime.now(timezone.utc))
        db_session.add(event)
        db_session.commit()

        assert event_manager.exists("deleted_trip", include_deleted=True) is True


class TestEventManagerGet:
    """Test EventManager.get() method."""

    def test_get_returns_none_when_not_found(self, event_manager):
        """Test get returns None for non-existent event."""
        result = event_manager.get("nonexistent")
        assert result is None

    def test_get_returns_event_when_found_by_name(self, event_manager, db_session):
        """Test get returns event when it exists."""
        event = Event(event="paris_trip", title="Paris Trip")
        db_session.add(event)
        db_session.commit()

        result = event_manager.get("paris_trip")
        assert result is not None
        assert result.event == "paris_trip"
        assert result.title == "Paris Trip"

    def test_get_returns_event_when_found_by_id(self, event_manager, db_session):
        """Test get returns event by ID."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        result = event_manager.get(event_id=event.id)
        assert result is not None
        assert result.id == event.id

    def test_get_normalizes_input(self, event_manager, db_session):
        """Test get normalizes whitespace."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        result = event_manager.get("  paris_trip  ")
        assert result is not None
        assert result.event == "paris_trip"

    def test_get_excludes_deleted_by_default(self, event_manager, db_session):
        """Test get excludes soft-deleted events by default."""
        event = Event(event="deleted_trip", deleted_at=datetime.now(timezone.utc))
        db_session.add(event)
        db_session.commit()

        result = event_manager.get("deleted_trip")
        assert result is None

    def test_get_includes_deleted_when_requested(self, event_manager, db_session):
        """Test get includes deleted events when requested."""
        event = Event(event="deleted_trip", deleted_at=datetime.now(timezone.utc))
        db_session.add(event)
        db_session.commit()

        result = event_manager.get("deleted_trip", include_deleted=True)
        assert result is not None

    def test_get_prefers_id_over_name(self, event_manager, db_session):
        """Test get prefers ID when both name and ID provided."""
        event1 = Event(event="event1")
        event2 = Event(event="event2")
        db_session.add_all([event1, event2])
        db_session.commit()

        result = event_manager.get(event_name="event1", event_id=event2.id)
        assert result.id == event2.id


class TestEventManagerGetAll:
    """Test EventManager.get_all() method."""

    def test_get_all_empty(self, event_manager):
        """Test get_all returns empty list when no events."""
        result = event_manager.get_all()
        assert result == []

    def test_get_all_returns_all_events(self, event_manager, db_session):
        """Test get_all returns all events."""
        events = [
            Event(event="trip1", title="First Trip"),
            Event(event="trip2", title="Second Trip"),
            Event(event="trip3", title="Third Trip"),
        ]
        for event in events:
            db_session.add(event)
        db_session.commit()

        result = event_manager.get_all()
        assert len(result) == 3
        event_names = {e.event for e in result}
        assert event_names == {"trip1", "trip2", "trip3"}

    def test_get_all_ordered_by_event_name(self, event_manager, db_session):
        """Test get_all returns events ordered alphabetically."""
        events = [
            Event(event="zebra"),
            Event(event="apple"),
            Event(event="banana"),
        ]
        for event in events:
            db_session.add(event)
        db_session.commit()

        result = event_manager.get_all()
        event_names = [e.event for e in result]
        assert event_names == ["apple", "banana", "zebra"]

    def test_get_all_excludes_deleted_by_default(self, event_manager, db_session):
        """Test get_all excludes soft-deleted events by default."""
        events = [
            Event(event="active1"),
            Event(event="deleted1", deleted_at=datetime.now(timezone.utc)),
            Event(event="active2"),
        ]
        for event in events:
            db_session.add(event)
        db_session.commit()

        result = event_manager.get_all()
        assert len(result) == 2
        event_names = {e.event for e in result}
        assert event_names == {"active1", "active2"}

    def test_get_all_includes_deleted_when_requested(self, event_manager, db_session):
        """Test get_all includes deleted events when requested."""
        events = [
            Event(event="active1"),
            Event(event="deleted1", deleted_at=datetime.now(timezone.utc)),
            Event(event="active2"),
        ]
        for event in events:
            db_session.add(event)
        db_session.commit()

        result = event_manager.get_all(include_deleted=True)
        assert len(result) == 3


class TestEventManagerCreate:
    """Test EventManager.create() method."""

    def test_create_minimal_event(self, event_manager):
        """Test create with minimal required fields."""
        event = event_manager.create({"event": "paris_trip"})

        assert event is not None
        assert event.event == "paris_trip"
        assert event.id is not None

    def test_create_event_with_all_fields(self, event_manager):
        """Test create with all optional fields."""
        event = event_manager.create({
            "event": "paris_trip",
            "title": "Paris Trip 2023",
            "description": "Two week trip to Paris with family",
        })

        assert event.event == "paris_trip"
        assert event.title == "Paris Trip 2023"
        assert event.description == "Two week trip to Paris with family"

    def test_create_normalizes_event_name(self, event_manager):
        """Test create normalizes event name."""
        event = event_manager.create({"event": "  paris_trip  "})

        assert event.event == "paris_trip"

    def test_create_raises_on_missing_event_name(self, event_manager):
        """Test create raises ValidationError when event name missing."""
        with pytest.raises(ValidationError):
            event_manager.create({})

    def test_create_raises_on_empty_event_name(self, event_manager):
        """Test create raises ValidationError for empty event name."""
        with pytest.raises(ValidationError):
            event_manager.create({"event": ""})

    def test_create_raises_on_duplicate_event(self, event_manager, db_session):
        """Test create raises DatabaseError when event already exists."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        with pytest.raises(DatabaseError, match="already exists"):
            event_manager.create({"event": "paris_trip"})

    def test_create_raises_when_deleted_event_exists(self, event_manager, db_session):
        """Test create raises when deleted event with same name exists."""
        event = Event(event="paris_trip", deleted_at=datetime.now(timezone.utc))
        db_session.add(event)
        db_session.commit()

        with pytest.raises(DatabaseError, match="exists but is deleted"):
            event_manager.create({"event": "paris_trip"})

    def test_create_with_entries(self, event_manager, db_session):
        """Test create event with linked entries."""
        entry1 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        entry2 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry-2024-01-02.md")
        db_session.add_all([entry1, entry2])
        db_session.commit()

        event = event_manager.create({
            "event": "paris_trip",
            "entries": [entry1, entry2],
        })

        assert len(event.entries) == 2
        assert entry1 in event.entries
        assert entry2 in event.entries

    def test_create_with_people(self, event_manager, db_session):
        """Test create event with linked people."""
        person1 = Person(name="Alice")
        person2 = Person(name="Bob")
        db_session.add_all([person1, person2])
        db_session.commit()

        event = event_manager.create({
            "event": "paris_trip",
            "people": [person1, person2],
        })

        assert len(event.people) == 2
        assert person1 in event.people
        assert person2 in event.people


class TestEventManagerUpdate:
    """Test EventManager.update() method."""

    def test_update_event_name(self, event_manager, db_session):
        """Test update event identifier."""
        event = Event(event="old_name")
        db_session.add(event)
        db_session.commit()

        updated = event_manager.update(event, {"event": "new_name"})

        assert updated.event == "new_name"

    def test_update_title(self, event_manager, db_session):
        """Test update event title."""
        event = Event(event="trip", title="Old Title")
        db_session.add(event)
        db_session.commit()

        updated = event_manager.update(event, {"title": "New Title"})

        assert updated.title == "New Title"

    def test_update_description(self, event_manager, db_session):
        """Test update event description."""
        event = Event(event="trip")
        db_session.add(event)
        db_session.commit()

        updated = event_manager.update(event, {"description": "New description"})

        assert updated.description == "New description"

    def test_update_raises_when_event_not_found(self, event_manager):
        """Test update raises when event doesn't exist."""
        fake_event = Event(event="fake", id=99999)

        with pytest.raises(DatabaseError, match="does not exist"):
            event_manager.update(fake_event, {"title": "New"})

    def test_update_raises_when_event_deleted(self, event_manager, db_session):
        """Test update raises when event is soft-deleted."""
        event = Event(event="deleted", deleted_at=datetime.now(timezone.utc))
        db_session.add(event)
        db_session.commit()

        with pytest.raises(DatabaseError, match="Cannot update deleted event"):
            event_manager.update(event, {"title": "New"})

    def test_update_adds_entries_incrementally(self, event_manager, db_session):
        """Test update adds entries incrementally."""
        entry1 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        entry2 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry-2024-01-02.md")
        entry3 = Entry(date=date(2024, 1, 3), file_path="/path/to/entry-2024-01-03.md")
        event = Event(event="trip")
        event.entries.append(entry1)
        db_session.add_all([event, entry1, entry2, entry3])
        db_session.commit()

        event_manager.update(event, {"entries": [entry2, entry3]})

        assert len(event.entries) == 3
        assert entry1 in event.entries
        assert entry2 in event.entries
        assert entry3 in event.entries

    def test_update_adds_people_incrementally(self, event_manager, db_session):
        """Test update adds people incrementally."""
        person1 = Person(name="Alice")
        person2 = Person(name="Bob")
        event = Event(event="trip")
        event.people.append(person1)
        db_session.add_all([event, person1, person2])
        db_session.commit()

        event_manager.update(event, {"people": [person2]})

        assert len(event.people) == 2
        assert person1 in event.people
        assert person2 in event.people


class TestEventManagerDelete:
    """Test EventManager.delete() method."""

    def test_delete_soft_deletes_by_default(self, event_manager, db_session):
        """Test delete performs soft delete by default."""
        event = Event(event="trip")
        db_session.add(event)
        db_session.commit()

        event_manager.delete(event)
        db_session.refresh(event)

        assert event.deleted_at is not None
        assert event_manager.get("trip") is None
        assert event_manager.get("trip", include_deleted=True) is not None

    def test_delete_records_deleted_by(self, event_manager, db_session):
        """Test delete records who deleted."""
        event = Event(event="trip")
        db_session.add(event)
        db_session.commit()

        event_manager.delete(event, deleted_by="admin")
        db_session.refresh(event)

        assert event.deleted_by == "admin"

    def test_delete_records_deletion_reason(self, event_manager, db_session):
        """Test delete records reason for deletion."""
        event = Event(event="trip")
        db_session.add(event)
        db_session.commit()

        event_manager.delete(event, reason="Duplicate entry")
        db_session.refresh(event)

        assert event.deletion_reason == "Duplicate entry"

    def test_delete_hard_delete_removes_event(self, event_manager, db_session):
        """Test hard delete permanently removes event."""
        event = Event(event="trip")
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        event_manager.delete(event, hard_delete=True)
        db_session.commit()

        result = db_session.get(Event, event_id)
        assert result is None

    def test_delete_by_id(self, event_manager, db_session):
        """Test delete can accept event ID."""
        event = Event(event="trip")
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        event_manager.delete(event_id)

        result = event_manager.get(event_id=event_id)
        assert result is None


class TestEventManagerRestore:
    """Test EventManager.restore() method."""

    def test_restore_soft_deleted_event(self, event_manager, db_session):
        """Test restore brings back soft-deleted event."""
        event = Event(
            event="trip",
            deleted_at=datetime.now(timezone.utc),
            deleted_by="admin",
            deletion_reason="Accident",
        )
        db_session.add(event)
        db_session.commit()

        restored = event_manager.restore(event)

        assert restored.deleted_at is None
        assert restored.deleted_by is None
        assert restored.deletion_reason is None
        assert event_manager.get("trip") is not None

    def test_restore_raises_when_not_deleted(self, event_manager, db_session):
        """Test restore raises when event is not deleted."""
        event = Event(event="trip")
        db_session.add(event)
        db_session.commit()

        with pytest.raises(DatabaseError, match="is not deleted"):
            event_manager.restore(event)

    def test_restore_by_id(self, event_manager, db_session):
        """Test restore can accept event ID."""
        event = Event(event="trip", deleted_at=datetime.now(timezone.utc))
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        event_manager.restore(event_id)

        result = event_manager.get("trip")
        assert result is not None


class TestEventManagerLinkToEntry:
    """Test EventManager.link_to_entry() method."""

    def test_link_to_entry_adds_entry(self, event_manager, db_session):
        """Test linking event to entry."""
        event = Event(event="trip")
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        db_session.add_all([event, entry])
        db_session.commit()

        event_manager.link_to_entry(event, entry)

        assert entry in event.entries

    def test_link_to_entry_idempotent(self, event_manager, db_session):
        """Test linking same entry twice doesn't duplicate."""
        event = Event(event="trip")
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        event.entries.append(entry)
        db_session.add_all([event, entry])
        db_session.commit()

        event_manager.link_to_entry(event, entry)

        assert len(event.entries) == 1

    def test_link_to_entry_raises_on_unpersisted_event(self, event_manager, db_session):
        """Test linking raises if event not persisted."""
        event = Event(event="trip")
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        db_session.add(entry)
        db_session.commit()

        with pytest.raises(ValueError, match="Event must be persisted"):
            event_manager.link_to_entry(event, entry)

    def test_link_to_entry_raises_on_unpersisted_entry(self, event_manager, db_session):
        """Test linking raises if entry not persisted."""
        event = Event(event="trip")
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        db_session.add(event)
        db_session.commit()

        with pytest.raises(ValueError, match="Entry must be persisted"):
            event_manager.link_to_entry(event, entry)


class TestEventManagerUnlinkFromEntry:
    """Test EventManager.unlink_from_entry() method."""

    def test_unlink_from_entry_removes_entry(self, event_manager, db_session):
        """Test unlinking event from entry."""
        event = Event(event="trip")
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        event.entries.append(entry)
        db_session.add_all([event, entry])
        db_session.commit()

        result = event_manager.unlink_from_entry(event, entry)

        assert result is True
        assert entry not in event.entries

    def test_unlink_from_entry_returns_false_when_not_linked(self, event_manager, db_session):
        """Test unlinking returns False when not linked."""
        event = Event(event="trip")
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        db_session.add_all([event, entry])
        db_session.commit()

        result = event_manager.unlink_from_entry(event, entry)

        assert result is False


class TestEventManagerLinkToPerson:
    """Test EventManager.link_to_person() method."""

    def test_link_to_person_adds_person(self, event_manager, db_session):
        """Test linking event to person."""
        event = Event(event="trip")
        person = Person(name="Alice")
        db_session.add_all([event, person])
        db_session.commit()

        event_manager.link_to_person(event, person)

        assert person in event.people

    def test_link_to_person_idempotent(self, event_manager, db_session):
        """Test linking same person twice doesn't duplicate."""
        event = Event(event="trip")
        person = Person(name="Alice")
        event.people.append(person)
        db_session.add_all([event, person])
        db_session.commit()

        event_manager.link_to_person(event, person)

        assert len(event.people) == 1

    def test_link_to_person_raises_on_unpersisted_event(self, event_manager, db_session):
        """Test linking raises if event not persisted."""
        event = Event(event="trip")
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        with pytest.raises(ValueError, match="Event must be persisted"):
            event_manager.link_to_person(event, person)

    def test_link_to_person_raises_on_unpersisted_person(self, event_manager, db_session):
        """Test linking raises if person not persisted."""
        event = Event(event="trip")
        person = Person(name="Alice")
        db_session.add(event)
        db_session.commit()

        with pytest.raises(ValueError, match="Person must be persisted"):
            event_manager.link_to_person(event, person)


class TestEventManagerUnlinkFromPerson:
    """Test EventManager.unlink_from_person() method."""

    def test_unlink_from_person_removes_person(self, event_manager, db_session):
        """Test unlinking event from person."""
        event = Event(event="trip")
        person = Person(name="Alice")
        event.people.append(person)
        db_session.add_all([event, person])
        db_session.commit()

        result = event_manager.unlink_from_person(event, person)

        assert result is True
        assert person not in event.people

    def test_unlink_from_person_returns_false_when_not_linked(self, event_manager, db_session):
        """Test unlinking returns False when not linked."""
        event = Event(event="trip")
        person = Person(name="Alice")
        db_session.add_all([event, person])
        db_session.commit()

        result = event_manager.unlink_from_person(event, person)

        assert result is False


class TestEventManagerGetByDateRange:
    """Test EventManager.get_by_date_range() method."""

    def test_get_by_date_range_returns_events_in_range(self, event_manager, db_session):
        """Test get events with entries in date range."""
        event1 = Event(event="trip1")
        event2 = Event(event="trip2")
        entry1 = Entry(date=date(2024, 1, 15), file_path="/path/to/entry-2024-01-15.md")
        entry2 = Entry(date=date(2024, 2, 15), file_path="/path/to/entry-2024-02-15.md")
        event1.entries.append(entry1)
        event2.entries.append(entry2)
        db_session.add_all([event1, event2, entry1, entry2])
        db_session.commit()

        result = event_manager.get_by_date_range(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        assert len(result) == 1
        assert result[0].event == "trip1"

    def test_get_by_date_range_with_only_start_date(self, event_manager, db_session):
        """Test get events from start date onwards."""
        event1 = Event(event="trip1")
        event2 = Event(event="trip2")
        entry1 = Entry(date=date(2024, 1, 15), file_path="/path/to/entry-2024-01-15.md")
        entry2 = Entry(date=date(2024, 2, 15), file_path="/path/to/entry-2024-02-15.md")
        event1.entries.append(entry1)
        event2.entries.append(entry2)
        db_session.add_all([event1, event2, entry1, entry2])
        db_session.commit()

        result = event_manager.get_by_date_range(start_date=date(2024, 2, 1))

        assert len(result) == 1
        assert result[0].event == "trip2"

    def test_get_by_date_range_with_only_end_date(self, event_manager, db_session):
        """Test get events up to end date."""
        event1 = Event(event="trip1")
        event2 = Event(event="trip2")
        entry1 = Entry(date=date(2024, 1, 15), file_path="/path/to/entry-2024-01-15.md")
        entry2 = Entry(date=date(2024, 2, 15), file_path="/path/to/entry-2024-02-15.md")
        event1.entries.append(entry1)
        event2.entries.append(entry2)
        db_session.add_all([event1, event2, entry1, entry2])
        db_session.commit()

        result = event_manager.get_by_date_range(end_date=date(2024, 1, 31))

        assert len(result) == 1
        assert result[0].event == "trip1"

    def test_get_by_date_range_excludes_deleted(self, event_manager, db_session):
        """Test get_by_date_range excludes deleted events."""
        event = Event(event="trip", deleted_at=datetime.now(timezone.utc))
        entry = Entry(date=date(2024, 1, 15), file_path="/path/to/entry-2024-01-15.md")
        event.entries.append(entry)
        db_session.add_all([event, entry])
        db_session.commit()

        result = event_manager.get_by_date_range(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
        )

        assert len(result) == 0


class TestEventManagerGetForPerson:
    """Test EventManager.get_for_person() method."""

    def test_get_for_person_returns_linked_events(self, event_manager, db_session):
        """Test get all events for a person."""
        person = Person(name="Alice")
        event1 = Event(event="trip1")
        event2 = Event(event="trip2")
        event3 = Event(event="trip3")
        event1.people.append(person)
        event2.people.append(person)
        db_session.add_all([person, event1, event2, event3])
        db_session.commit()

        result = event_manager.get_for_person(person)

        assert len(result) == 2
        event_names = {e.event for e in result}
        assert event_names == {"trip1", "trip2"}

    def test_get_for_person_excludes_deleted(self, event_manager, db_session):
        """Test get_for_person excludes deleted events."""
        person = Person(name="Alice")
        event1 = Event(event="trip1")
        event2 = Event(event="trip2", deleted_at=datetime.now(timezone.utc))
        event1.people.append(person)
        event2.people.append(person)
        db_session.add_all([person, event1, event2])
        db_session.commit()

        result = event_manager.get_for_person(person)

        assert len(result) == 1
        assert result[0].event == "trip1"

    def test_get_for_person_includes_deleted_when_requested(self, event_manager, db_session):
        """Test get_for_person includes deleted when requested."""
        person = Person(name="Alice")
        event1 = Event(event="trip1")
        event2 = Event(event="trip2", deleted_at=datetime.now(timezone.utc))
        event1.people.append(person)
        event2.people.append(person)
        db_session.add_all([person, event1, event2])
        db_session.commit()

        result = event_manager.get_for_person(person, include_deleted=True)

        assert len(result) == 2


class TestEventManagerGetForEntry:
    """Test EventManager.get_for_entry() method."""

    def test_get_for_entry_returns_linked_events(self, event_manager, db_session):
        """Test get all events for an entry."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        event1 = Event(event="trip1")
        event2 = Event(event="trip2")
        event3 = Event(event="trip3")
        event1.entries.append(entry)
        event2.entries.append(entry)
        db_session.add_all([entry, event1, event2, event3])
        db_session.commit()

        result = event_manager.get_for_entry(entry)

        assert len(result) == 2
        event_names = {e.event for e in result}
        assert event_names == {"trip1", "trip2"}

    def test_get_for_entry_excludes_deleted(self, event_manager, db_session):
        """Test get_for_entry excludes deleted events."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        event1 = Event(event="trip1")
        event2 = Event(event="trip2", deleted_at=datetime.now(timezone.utc))
        event1.entries.append(entry)
        event2.entries.append(entry)
        db_session.add_all([entry, event1, event2])
        db_session.commit()

        result = event_manager.get_for_entry(entry)

        assert len(result) == 1
        assert result[0].event == "trip1"

    def test_get_for_entry_includes_deleted_when_requested(self, event_manager, db_session):
        """Test get_for_entry includes deleted when requested."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        event1 = Event(event="trip1")
        event2 = Event(event="trip2", deleted_at=datetime.now(timezone.utc))
        event1.entries.append(entry)
        event2.entries.append(entry)
        db_session.add_all([entry, event1, event2])
        db_session.commit()

        result = event_manager.get_for_entry(entry, include_deleted=True)

        assert len(result) == 2
