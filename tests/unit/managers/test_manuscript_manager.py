"""
test_manuscript_manager.py
--------------------------
Unit tests for ManuscriptManager operations.

Tests manuscript tracking including entry selection, character mapping,
story arcs, and thematic analysis.

Target Coverage: 90%+
"""
import pytest
from datetime import date
from dev.database.models import Entry, Person, Event
from dev.database.models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
    Arc,
    Theme,
    ManuscriptStatus,
)
from dev.core.exceptions import ValidationError, DatabaseError


# =============================================================================
# MANUSCRIPT ENTRY TESTS
# =============================================================================


class TestCreateOrUpdateEntry:
    """Test ManuscriptManager.create_or_update_entry() method."""

    def test_create_manuscript_entry_minimal(self, manuscript_manager, db_session):
        """Test creating manuscript entry with minimal data."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        ms_entry = manuscript_manager.create_or_update_entry(entry, {})

        assert ms_entry is not None
        assert ms_entry.entry_id == entry.id

    def test_create_manuscript_entry_with_status_enum(self, manuscript_manager, db_session):
        """Test creating with ManuscriptStatus enum."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        ms_entry = manuscript_manager.create_or_update_entry(
            entry, {"status": ManuscriptStatus.SOURCE}
        )

        assert ms_entry.status == ManuscriptStatus.SOURCE

    def test_create_manuscript_entry_with_status_string(self, manuscript_manager, db_session):
        """Test creating with status as string (flexible matching)."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        ms_entry = manuscript_manager.create_or_update_entry(entry, {"status": "source"})

        assert ms_entry.status == ManuscriptStatus.SOURCE

    def test_create_manuscript_entry_with_status_enum_name(self, manuscript_manager, db_session):
        """Test creating with status as enum name (SOURCE)."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        ms_entry = manuscript_manager.create_or_update_entry(entry, {"status": "SOURCE"})

        assert ms_entry.status == ManuscriptStatus.SOURCE

    def test_create_manuscript_entry_with_edited(self, manuscript_manager, db_session):
        """Test creating with edited flag."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        ms_entry = manuscript_manager.create_or_update_entry(entry, {"edited": True})

        assert ms_entry.edited is True

    def test_create_manuscript_entry_with_notes(self, manuscript_manager, db_session):
        """Test creating with notes."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        ms_entry = manuscript_manager.create_or_update_entry(
            entry, {"notes": "Important scene"}
        )

        assert ms_entry.notes == "Important scene"

    def test_create_manuscript_entry_with_themes(self, manuscript_manager, db_session):
        """Test creating with themes."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        ms_entry = manuscript_manager.create_or_update_entry(
            entry, {"themes": ["identity", "loss"]}
        )

        assert len(ms_entry.themes) == 2
        theme_names = [t.theme for t in ms_entry.themes]
        assert "identity" in theme_names
        assert "loss" in theme_names

    def test_update_manuscript_entry_changes_status(self, manuscript_manager, db_session):
        """Test updating manuscript entry changes status."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()
        entry_id = entry.id

        manuscript_manager.create_or_update_entry(
            entry, {"status": ManuscriptStatus.SOURCE}
        )
        db_session.commit()

        # Get fresh entry from database and explicitly load the relationship
        entry = db_session.get(Entry, entry_id)
        db_session.refresh(entry, ['manuscript'])  # Explicitly load the relationship

        ms_entry = manuscript_manager.create_or_update_entry(
            entry, {"status": ManuscriptStatus.FRAGMENTS}
        )

        assert ms_entry.status == ManuscriptStatus.FRAGMENTS

    def test_update_manuscript_entry_replaces_themes(self, manuscript_manager, db_session):
        """Test updating themes replaces (not appends)."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()
        entry_id = entry.id

        manuscript_manager.create_or_update_entry(entry, {"themes": ["identity", "loss"]})
        db_session.commit()

        # Get fresh entry from database and force-load the relationship
        entry = db_session.get(Entry, entry_id)
        _ = entry.manuscript  # Force load the relationship

        ms_entry = manuscript_manager.create_or_update_entry(entry, {"themes": ["memory"]})

        assert len(ms_entry.themes) == 1
        assert ms_entry.themes[0].theme == "memory"

    def test_create_manuscript_entry_raises_on_unpersisted_entry(self, manuscript_manager):
        """Test raises if entry not persisted."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")

        with pytest.raises(ValueError, match="Entry must be persisted"):
            manuscript_manager.create_or_update_entry(entry, {})


class TestDeleteEntry:
    """Test ManuscriptManager.delete_entry() method."""

    def test_delete_manuscript_entry(self, manuscript_manager, db_session):
        """Test deleting manuscript entry (hard delete)."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        manuscript_manager.create_or_update_entry(entry, {"status": "source"})
        db_session.refresh(entry)
        assert entry.manuscript is not None

        manuscript_manager.delete_entry(entry)
        db_session.refresh(entry)

        assert entry.manuscript is None

    def test_delete_nonexistent_manuscript_entry_does_nothing(self, manuscript_manager, db_session):
        """Test deleting when no manuscript entry exists does nothing."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        # Should not raise error
        manuscript_manager.delete_entry(entry)


# =============================================================================
# MANUSCRIPT PERSON TESTS
# =============================================================================


class TestCreateOrUpdatePerson:
    """Test ManuscriptManager.create_or_update_person() method."""

    def test_create_manuscript_person(self, manuscript_manager, db_session):
        """Test creating manuscript person with character mapping."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        ms_person = manuscript_manager.create_or_update_person(
            person, {"character": "Alexandra"}
        )

        assert ms_person is not None
        assert ms_person.character == "Alexandra"

    def test_update_manuscript_person_changes_character(self, manuscript_manager, db_session):
        """Test updating manuscript person changes character name."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()
        person_id = person.id

        manuscript_manager.create_or_update_person(person, {"character": "Alexandra"})
        db_session.commit()

        # Get fresh person from database and force-load the relationship
        person = db_session.get(Person, person_id)
        _ = person.manuscript  # Force load the relationship

        ms_person = manuscript_manager.create_or_update_person(
            person, {"character": "Alexandria"}
        )

        assert ms_person.character == "Alexandria"

    def test_create_manuscript_person_raises_on_missing_character(
        self, manuscript_manager, db_session
    ):
        """Test raises if character name is missing."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        with pytest.raises(ValidationError, match="Character name is required"):
            manuscript_manager.create_or_update_person(person, {})

    def test_create_manuscript_person_raises_on_empty_character(
        self, manuscript_manager, db_session
    ):
        """Test raises if character name is empty."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        with pytest.raises(ValidationError, match="Character name is required"):
            manuscript_manager.create_or_update_person(person, {"character": ""})

    def test_create_manuscript_person_raises_on_unpersisted_person(self, manuscript_manager):
        """Test raises if person not persisted."""
        person = Person(name="Alice")

        with pytest.raises(ValueError, match="Person must be persisted"):
            manuscript_manager.create_or_update_person(person, {"character": "Alexandra"})


class TestDeletePerson:
    """Test ManuscriptManager.delete_person() method."""

    def test_soft_delete_manuscript_person(self, manuscript_manager, db_session):
        """Test soft deleting manuscript person."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        manuscript_manager.create_or_update_person(person, {"character": "Alexandra"})
        db_session.refresh(person)

        manuscript_manager.delete_person(
            person, deleted_by="admin", reason="No longer needed"
        )
        db_session.refresh(person)

        assert person.manuscript.deleted_at is not None
        assert person.manuscript.deleted_by == "admin"
        assert person.manuscript.deletion_reason == "No longer needed"

    def test_hard_delete_manuscript_person(self, manuscript_manager, db_session):
        """Test hard deleting manuscript person."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        manuscript_manager.create_or_update_person(person, {"character": "Alexandra"})
        db_session.refresh(person)
        assert person.manuscript is not None

        manuscript_manager.delete_person(person, hard_delete=True)
        db_session.refresh(person)

        assert person.manuscript is None

    def test_delete_nonexistent_manuscript_person_does_nothing(
        self, manuscript_manager, db_session
    ):
        """Test deleting when no manuscript person exists does nothing."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        # Should not raise error
        manuscript_manager.delete_person(person)


class TestRestorePerson:
    """Test ManuscriptManager.restore_person() method."""

    def test_restore_manuscript_person(self, manuscript_manager, db_session):
        """Test restoring soft-deleted manuscript person."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()
        person_id = person.id

        person = db_session.get(Person, person_id)
        _ = person.manuscript  # Force load
        manuscript_manager.create_or_update_person(person, {"character": "Alexandra"})
        db_session.commit()

        person = db_session.get(Person, person_id)
        _ = person.manuscript  # Force load
        manuscript_manager.delete_person(person)
        db_session.commit()

        person = db_session.get(Person, person_id)
        _ = person.manuscript  # Force load
        assert person.manuscript.deleted_at is not None

        restored = manuscript_manager.restore_person(person)

        assert restored.deleted_at is None
        assert restored.deleted_by is None
        assert restored.deletion_reason is None

    def test_restore_raises_on_nonexistent_manuscript_person(
        self, manuscript_manager, db_session
    ):
        """Test restore raises if no manuscript person exists."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        with pytest.raises(DatabaseError, match="No manuscript data"):
            manuscript_manager.restore_person(person)

    def test_restore_raises_on_not_deleted_manuscript_person(
        self, manuscript_manager, db_session
    ):
        """Test restore raises if manuscript person not deleted."""
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()
        person_id = person.id

        person = db_session.get(Person, person_id)
        _ = person.manuscript  # Force load
        manuscript_manager.create_or_update_person(person, {"character": "Alexandra"})
        db_session.commit()

        person = db_session.get(Person, person_id)
        _ = person.manuscript  # Force load
        with pytest.raises(DatabaseError, match="not deleted"):
            manuscript_manager.restore_person(person)


# =============================================================================
# MANUSCRIPT EVENT TESTS
# =============================================================================


class TestCreateOrUpdateEvent:
    """Test ManuscriptManager.create_or_update_event() method."""

    def test_create_manuscript_event_minimal(self, manuscript_manager, db_session):
        """Test creating manuscript event with minimal data."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        ms_event = manuscript_manager.create_or_update_event(event, {})

        assert ms_event is not None
        assert ms_event.event_id == event.id

    def test_create_manuscript_event_with_notes(self, manuscript_manager, db_session):
        """Test creating with notes."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        ms_event = manuscript_manager.create_or_update_event(
            event, {"notes": "Climactic scene"}
        )

        assert ms_event.notes == "Climactic scene"

    def test_create_manuscript_event_with_arc(self, manuscript_manager, db_session):
        """Test creating with arc (auto-creates arc)."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        ms_event = manuscript_manager.create_or_update_event(event, {"arc": "journey"})

        assert ms_event.arc is not None
        assert ms_event.arc.arc == "journey"

    def test_update_manuscript_event_changes_arc(self, manuscript_manager, db_session):
        """Test updating manuscript event changes arc."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        manuscript_manager.create_or_update_event(event, {"arc": "journey"})
        db_session.commit()

        # Get fresh event from database and force-load the relationship
        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load the relationship

        ms_event = manuscript_manager.create_or_update_event(event, {"arc": "resolution"})

        assert ms_event.arc.arc == "resolution"

    def test_create_manuscript_event_raises_on_unpersisted_event(self, manuscript_manager):
        """Test raises if event not persisted."""
        event = Event(event="paris_trip")

        with pytest.raises(ValueError, match="Event must be persisted"):
            manuscript_manager.create_or_update_event(event, {})


class TestDeleteEvent:
    """Test ManuscriptManager.delete_event() method."""

    def test_soft_delete_manuscript_event(self, manuscript_manager, db_session):
        """Test soft deleting manuscript event."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        manuscript_manager.create_or_update_event(event, {"notes": "Test"})
        db_session.refresh(event)

        manuscript_manager.delete_event(event, deleted_by="admin", reason="Not needed")
        db_session.refresh(event)

        assert event.manuscript.deleted_at is not None
        assert event.manuscript.deleted_by == "admin"
        assert event.manuscript.deletion_reason == "Not needed"

    def test_hard_delete_manuscript_event(self, manuscript_manager, db_session):
        """Test hard deleting manuscript event."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        manuscript_manager.create_or_update_event(event, {"notes": "Test"})
        db_session.refresh(event)
        assert event.manuscript is not None

        manuscript_manager.delete_event(event, hard_delete=True)
        db_session.refresh(event)

        assert event.manuscript is None

    def test_delete_nonexistent_manuscript_event_does_nothing(
        self, manuscript_manager, db_session
    ):
        """Test deleting when no manuscript event exists does nothing."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        # Should not raise error
        manuscript_manager.delete_event(event)


class TestRestoreEvent:
    """Test ManuscriptManager.restore_event() method."""

    def test_restore_manuscript_event(self, manuscript_manager, db_session):
        """Test restoring soft-deleted manuscript event."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        manuscript_manager.create_or_update_event(event, {"notes": "Test"})
        db_session.commit()

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        manuscript_manager.delete_event(event)
        db_session.commit()

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        assert event.manuscript.deleted_at is not None

        restored = manuscript_manager.restore_event(event)

        assert restored.deleted_at is None
        assert restored.deleted_by is None
        assert restored.deletion_reason is None

    def test_restore_raises_on_nonexistent_manuscript_event(
        self, manuscript_manager, db_session
    ):
        """Test restore raises if no manuscript event exists."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()

        with pytest.raises(DatabaseError, match="No manuscript data"):
            manuscript_manager.restore_event(event)

    def test_restore_raises_on_not_deleted_manuscript_event(
        self, manuscript_manager, db_session
    ):
        """Test restore raises if manuscript event not deleted."""
        event = Event(event="paris_trip")
        db_session.add(event)
        db_session.commit()
        event_id = event.id

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        manuscript_manager.create_or_update_event(event, {"notes": "Test"})
        db_session.commit()

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        with pytest.raises(DatabaseError, match="not deleted"):
            manuscript_manager.restore_event(event)


# =============================================================================
# ARC TESTS
# =============================================================================


class TestArcOperations:
    """Test Arc CRUD operations."""

    def test_get_arc_returns_none_when_not_found(self, manuscript_manager):
        """Test get_arc returns None for non-existent arc."""
        arc = manuscript_manager.get_arc("nonexistent")
        assert arc is None

    def test_get_arc_returns_arc_when_found(self, manuscript_manager, db_session):
        """Test get_arc returns arc when it exists."""
        arc = Arc(arc="journey")
        db_session.add(arc)
        db_session.commit()

        result = manuscript_manager.get_arc("journey")

        assert result is not None
        assert result.arc == "journey"

    def test_get_or_create_arc_returns_existing(self, manuscript_manager, db_session):
        """Test get_or_create_arc returns existing arc."""
        arc = Arc(arc="journey")
        db_session.add(arc)
        db_session.commit()

        result = manuscript_manager.get_or_create_arc("journey")

        assert result.id == arc.id

    def test_get_or_create_arc_creates_new(self, manuscript_manager, db_session):
        """Test get_or_create_arc creates new arc."""
        result = manuscript_manager.get_or_create_arc("journey")

        assert result is not None
        assert result.arc == "journey"

    def test_get_or_create_arc_raises_on_empty_name(self, manuscript_manager):
        """Test get_or_create_arc raises on empty arc name."""
        with pytest.raises(ValidationError, match="Arc name cannot be empty"):
            manuscript_manager.get_or_create_arc("")

    def test_get_all_arcs_empty(self, manuscript_manager):
        """Test get_all_arcs returns empty list when no arcs."""
        arcs = manuscript_manager.get_all_arcs()
        assert arcs == []

    def test_get_all_arcs_returns_all(self, manuscript_manager, db_session):
        """Test get_all_arcs returns all arcs."""
        arc1 = Arc(arc="journey")
        arc2 = Arc(arc="resolution")
        db_session.add_all([arc1, arc2])
        db_session.commit()

        arcs = manuscript_manager.get_all_arcs()

        assert len(arcs) == 2
        arc_names = [a.arc for a in arcs]
        assert "journey" in arc_names
        assert "resolution" in arc_names


# =============================================================================
# THEME TESTS
# =============================================================================


class TestThemeOperations:
    """Test Theme CRUD operations."""

    def test_get_theme_returns_none_when_not_found(self, manuscript_manager):
        """Test get_theme returns None for non-existent theme."""
        theme = manuscript_manager.get_theme("nonexistent")
        assert theme is None

    def test_get_theme_returns_theme_when_found(self, manuscript_manager, db_session):
        """Test get_theme returns theme when it exists."""
        theme = Theme(theme="identity")
        db_session.add(theme)
        db_session.commit()

        result = manuscript_manager.get_theme("identity")

        assert result is not None
        assert result.theme == "identity"

    def test_get_or_create_theme_returns_existing(self, manuscript_manager, db_session):
        """Test get_or_create_theme returns existing theme."""
        theme = Theme(theme="identity")
        db_session.add(theme)
        db_session.commit()

        result = manuscript_manager.get_or_create_theme("identity")

        assert result.id == theme.id

    def test_get_or_create_theme_creates_new(self, manuscript_manager, db_session):
        """Test get_or_create_theme creates new theme."""
        result = manuscript_manager.get_or_create_theme("identity")

        assert result is not None
        assert result.theme == "identity"

    def test_get_or_create_theme_raises_on_empty_name(self, manuscript_manager):
        """Test get_or_create_theme raises on empty theme name."""
        with pytest.raises(ValidationError, match="Theme name cannot be empty"):
            manuscript_manager.get_or_create_theme("")

    def test_get_all_themes_empty(self, manuscript_manager):
        """Test get_all_themes returns empty list when no themes."""
        themes = manuscript_manager.get_all_themes()
        assert themes == []

    def test_get_all_themes_returns_all(self, manuscript_manager, db_session):
        """Test get_all_themes returns all themes."""
        theme1 = Theme(theme="identity")
        theme2 = Theme(theme="loss")
        db_session.add_all([theme1, theme2])
        db_session.commit()

        themes = manuscript_manager.get_all_themes()

        assert len(themes) == 2
        theme_names = [t.theme for t in themes]
        assert "identity" in theme_names
        assert "loss" in theme_names


# =============================================================================
# QUERY METHODS TESTS
# =============================================================================


class TestGetReadyEntries:
    """Test ManuscriptManager.get_ready_entries() method."""

    def test_get_ready_entries_returns_empty_when_none(self, manuscript_manager):
        """Test returns empty list when no ready entries."""
        result = manuscript_manager.get_ready_entries()
        assert result == []

    def test_get_ready_entries_returns_edited_with_content_status(
        self, manuscript_manager, db_session
    ):
        """Test returns entries that are edited=True and status.is_content=True."""
        entry1 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry1.md")
        entry2 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry2.md")
        entry3 = Entry(date=date(2024, 1, 3), file_path="/path/to/entry3.md")
        db_session.add_all([entry1, entry2, entry3])
        db_session.commit()

        # Ready: edited=True, status=SOURCE (is_content=True)
        manuscript_manager.create_or_update_entry(
            entry1, {"edited": True, "status": ManuscriptStatus.SOURCE}
        )
        # Not ready: edited=False
        manuscript_manager.create_or_update_entry(
            entry2, {"edited": False, "status": ManuscriptStatus.SOURCE}
        )
        # Not ready: status=REFERENCE (is_content=False)
        manuscript_manager.create_or_update_entry(
            entry3, {"edited": True, "status": ManuscriptStatus.REFERENCE}
        )

        result = manuscript_manager.get_ready_entries()

        assert len(result) == 1
        assert result[0].entry_id == entry1.id

    def test_get_ready_entries_sorted_by_date(self, manuscript_manager, db_session):
        """Test returns entries sorted by date."""
        entry1 = Entry(date=date(2024, 1, 3), file_path="/path/to/entry1.md")
        entry2 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry2.md")
        entry3 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry3.md")
        db_session.add_all([entry1, entry2, entry3])
        db_session.commit()

        for entry in [entry1, entry2, entry3]:
            manuscript_manager.create_or_update_entry(
                entry, {"edited": True, "status": ManuscriptStatus.SOURCE}
            )

        result = manuscript_manager.get_ready_entries()

        dates = [me.entry.date for me in result]
        assert dates == [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3)]


class TestGetEntriesByStatus:
    """Test ManuscriptManager.get_entries_by_status() method."""

    def test_get_entries_by_status_with_enum(self, manuscript_manager, db_session):
        """Test get entries by status using enum."""
        entry1 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry1.md")
        entry2 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry2.md")
        db_session.add_all([entry1, entry2])
        db_session.commit()

        manuscript_manager.create_or_update_entry(
            entry1, {"status": ManuscriptStatus.SOURCE}
        )
        manuscript_manager.create_or_update_entry(
            entry2, {"status": ManuscriptStatus.FRAGMENTS}
        )

        result = manuscript_manager.get_entries_by_status(ManuscriptStatus.SOURCE)

        assert len(result) == 1
        assert result[0].entry_id == entry1.id

    def test_get_entries_by_status_with_string(self, manuscript_manager, db_session):
        """Test get entries by status using string."""
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry.md")
        db_session.add(entry)
        db_session.commit()

        manuscript_manager.create_or_update_entry(entry, {"status": "source"})

        result = manuscript_manager.get_entries_by_status("source")

        assert len(result) == 1

    def test_get_entries_by_status_returns_empty_when_none(self, manuscript_manager):
        """Test returns empty list when no entries with status."""
        result = manuscript_manager.get_entries_by_status(ManuscriptStatus.SOURCE)
        assert result == []


class TestGetEventsByArc:
    """Test ManuscriptManager.get_events_by_arc() method."""

    def test_get_events_by_arc_returns_linked_events(
        self, manuscript_manager, db_session
    ):
        """Test returns all events in an arc."""
        arc = Arc(arc="journey")
        event1 = Event(event="paris_trip")
        event2 = Event(event="london_visit")
        event3 = Event(event="home_return")
        db_session.add_all([arc, event1, event2, event3])
        db_session.commit()

        manuscript_manager.create_or_update_event(event1, {"arc": "journey"})
        manuscript_manager.create_or_update_event(event2, {"arc": "journey"})
        manuscript_manager.create_or_update_event(event3, {"arc": "resolution"})

        result = manuscript_manager.get_events_by_arc(arc)

        assert len(result) == 2
        event_ids = [me.event_id for me in result]
        assert event1.id in event_ids
        assert event2.id in event_ids

    def test_get_events_by_arc_excludes_deleted_by_default(
        self, manuscript_manager, db_session
    ):
        """Test excludes soft-deleted events by default."""
        arc = Arc(arc="journey")
        event = Event(event="paris_trip")
        db_session.add_all([arc, event])
        db_session.commit()
        arc_id = arc.id
        event_id = event.id

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        manuscript_manager.create_or_update_event(event, {"arc": "journey"})
        db_session.commit()

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        manuscript_manager.delete_event(event)
        db_session.commit()

        arc = db_session.get(Arc, arc_id)
        result = manuscript_manager.get_events_by_arc(arc)

        assert len(result) == 0

    def test_get_events_by_arc_includes_deleted_when_requested(
        self, manuscript_manager, db_session
    ):
        """Test includes soft-deleted events when requested."""
        arc = Arc(arc="journey")
        event = Event(event="paris_trip")
        db_session.add_all([arc, event])
        db_session.commit()
        arc_id = arc.id
        event_id = event.id

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        manuscript_manager.create_or_update_event(event, {"arc": "journey"})
        db_session.commit()

        event = db_session.get(Event, event_id)
        _ = event.manuscript  # Force load
        manuscript_manager.delete_event(event)
        db_session.commit()

        arc = db_session.get(Arc, arc_id)
        result = manuscript_manager.get_events_by_arc(arc, include_deleted=True)

        assert len(result) == 1


class TestGetEntriesByTheme:
    """Test ManuscriptManager.get_entries_by_theme() method."""

    def test_get_entries_by_theme_returns_linked_entries(
        self, manuscript_manager, db_session
    ):
        """Test returns all entries with a theme."""
        entry1 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry1.md")
        entry2 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry2.md")
        entry3 = Entry(date=date(2024, 1, 3), file_path="/path/to/entry3.md")
        db_session.add_all([entry1, entry2, entry3])
        db_session.commit()

        manuscript_manager.create_or_update_entry(entry1, {"themes": ["identity"]})
        manuscript_manager.create_or_update_entry(entry2, {"themes": ["identity", "loss"]})
        manuscript_manager.create_or_update_entry(entry3, {"themes": ["loss"]})

        theme = manuscript_manager.get_theme("identity")
        result = manuscript_manager.get_entries_by_theme(theme)

        assert len(result) == 2
        entry_ids = [me.entry_id for me in result]
        assert entry1.id in entry_ids
        assert entry2.id in entry_ids
