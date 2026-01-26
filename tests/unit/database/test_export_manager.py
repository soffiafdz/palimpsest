#!/usr/bin/env python3
"""
test_export_manager.py
----------------------
Unit tests for ExportManager functionality.

Tests focus on the serialization methods that convert database models
to JSON-serializable dictionaries with the new model structure.

Key areas tested:
    - _serialize_entry() with narrated_dates, scenes, threads
    - _serialize_person() with new fields (alias, scene_count, characters)
    - Edge cases and error conditions
"""
# --- Standard library imports ---
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

# --- Third party imports ---
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# --- Local imports ---
from dev.database.export_manager import ExportManager
from dev.database.models import (
    Arc,
    Base,
    City,
    Entry,
    Event,
    Location,
    NarratedDate,
    Person,
    Poem,
    PoemVersion,
    Reference,
    ReferenceSource,
    Scene,
    SceneDate,
    Tag,
    Theme,
    Thread,
    Character,
    PersonCharacterMap,
)
from dev.database.models.enums import (
    ReferenceMode,
    ReferenceType,
    RelationType,
    ContributionType,
)


# --- Test Fixtures ---


@pytest.fixture
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def test_session(test_engine):
    """Create a test database session."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


# Replace db_session with test_session in all tests
@pytest.fixture
def db_session(test_session):
    """Alias for test_session to match test expectations."""
    return test_session


class TestSerializeEntry:
    """Tests for ExportManager._serialize_entry() method."""

    def test_serialize_minimal_entry(self, db_session):
        """Test serializing entry with only required fields."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        db_session.add(entry)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert result["id"] == entry.id
        assert result["date"] == "2024-01-15"
        assert result["file_path"] == "/test/path/2024-01-15.md"
        assert result["file_hash"] == "abc123"
        assert result["word_count"] == 0  # Defaults to 0 in model
        assert result["reading_time"] == 0.0  # Defaults to 0.0 in model
        assert result["summary"] is None
        assert result["rating"] is None
        assert result["narrated_dates"] == []
        assert result["cities"] == []
        assert result["locations"] == []
        assert result["people"] == []
        assert result["events"] == []
        assert result["tags"] == []
        assert result["themes"] == []
        assert result["arcs"] == []
        assert result["scenes"] == []
        assert result["threads"] == []
        assert result["references"] == []
        assert result["poems"] == []

    def test_serialize_entry_with_metadata(self, db_session):
        """Test serializing entry with summary and rating."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
            word_count=500,
            reading_time=2.5,
            summary="Test entry summary",
            rating=4,
            rating_justification="Important day",
        )
        db_session.add(entry)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert result["word_count"] == 500
        assert result["reading_time"] == 2.5
        assert result["summary"] == "Test entry summary"
        assert result["rating"] == 4
        assert result["rating_justification"] == "Important day"

    def test_serialize_entry_with_narrated_dates(self, db_session):
        """Test serializing entry with narrated dates."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        db_session.add(entry)
        db_session.flush()

        # Add narrated dates
        nd1 = NarratedDate(entry_id=entry.id, date=date(2024, 6, 1))
        nd2 = NarratedDate(entry_id=entry.id, date=date(2024, 8, 15))
        db_session.add_all([nd1, nd2])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["narrated_dates"]) == 2
        assert "2024-06-01" in result["narrated_dates"]
        assert "2024-08-15" in result["narrated_dates"]

    def test_serialize_entry_with_geography(self, db_session):
        """Test serializing entry with cities and locations."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        city = City(name="Montreal")
        location = Location(name="Cafe X", city=city)

        entry.cities.append(city)
        entry.locations.append(location)

        db_session.add_all([entry, city, location])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert result["cities"] == ["Montreal"]
        assert len(result["locations"]) == 1
        assert result["locations"][0]["name"] == "Cafe X"
        assert result["locations"][0]["city"] == "Montreal"

    def test_serialize_entry_with_location_no_city(self, db_session):
        """Test serializing entry with location whose city is None (handled by serializer)."""
        # Skip: Location requires city_id (non-nullable foreign key)
        # This test would require changing the model constraint
        # Testing serialization handling of None city is done via mock test instead
        pytest.skip("Location model requires city_id - cannot create location without city")

    def test_serialize_entry_with_people(self, db_session):
        """Test serializing entry with people."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        person1 = Person(name="\1")
        person2 = Person(alias="bob", name="Robert", lastname="Smith")

        entry.people.extend([person1, person2])
        db_session.add_all([entry, person1, person2])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["people"]) == 2
        assert "Alice" in result["people"]
        assert "Bob" in result["people"]

    def test_serialize_entry_with_tags_themes_events(self, db_session):
        """Test serializing entry with tags, themes, and events using 'name' field."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        tag = Tag(name="depression")
        theme = Theme(name="identity")
        event = Event(name="Birthday Party")

        entry.tags.append(tag)
        entry.themes.append(theme)
        entry.events.append(event)

        db_session.add_all([entry, tag, theme, event])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert result["tags"] == ["depression"]
        assert result["themes"] == ["identity"]
        assert result["events"] == ["Birthday Party"]

    def test_serialize_entry_with_arcs(self, db_session):
        """Test serializing entry with arcs."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        arc1 = Arc(name="Clara Arc", description="Relationship with Clara")
        arc2 = Arc(name="PhD Arc", description="PhD journey")

        entry.arcs.extend([arc1, arc2])
        db_session.add_all([entry, arc1, arc2])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["arcs"]) == 2
        assert "Clara Arc" in result["arcs"]
        assert "PhD Arc" in result["arcs"]

    def test_serialize_entry_with_references(self, db_session):
        """Test serializing entry with references."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        source = ReferenceSource(
            title="Important Book",
            type=ReferenceType.BOOK,
            author="Famous Author",
        )
        ref = Reference(
            entry=entry,
            source=source,
            content="Quote from book",
            description="Meaningful quote",
            mode=ReferenceMode.DIRECT,
        )

        db_session.add_all([entry, source, ref])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["references"]) == 1
        ref_data = result["references"][0]
        assert ref_data["content"] == "Quote from book"
        assert ref_data["description"] == "Meaningful quote"
        assert ref_data["mode"] == "direct"
        assert ref_data["source"]["title"] == "Important Book"
        assert ref_data["source"]["type"] == "book"
        assert ref_data["source"]["author"] == "Famous Author"

    def test_serialize_entry_with_reference_no_source(self, db_session):
        """Test serializing entry with reference that has no source."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        ref = Reference(
            entry=entry,
            content="Quote without source",
            mode=ReferenceMode.INDIRECT,
        )

        db_session.add_all([entry, ref])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["references"]) == 1
        ref_data = result["references"][0]
        assert ref_data["content"] == "Quote without source"
        assert ref_data["mode"] == "indirect"
        assert ref_data["source"] is None

    def test_serialize_entry_with_reference_no_mode(self, db_session):
        """Test serializing entry with reference with default mode."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        ref = Reference(
            entry=entry,
            content="Quote",
            mode=None,
        )

        db_session.add_all([entry, ref])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["references"]) == 1
        assert result["references"][0]["mode"] == "direct"  # Default

    def test_serialize_entry_with_poems(self, db_session):
        """Test serializing entry with poems."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        poem = Poem(title="Test Poem")
        version = PoemVersion(
            poem=poem,
            entry=entry,
            content="Roses are red\nViolets are blue",
            revision_date=date(2024, 1, 15),
        )

        db_session.add_all([poem, version, entry])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["poems"]) == 1
        poem_data = result["poems"][0]
        assert poem_data["title"] == "Test Poem"
        assert poem_data["content"] == "Roses are red\nViolets are blue"

    def test_serialize_entry_with_scenes(self, db_session):
        """Test serializing entry with scenes (new model structure)."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        person = Person(name="\1")
        location = Location(name="Cafe X")

        scene = Scene(
            entry=entry,
            name="Coffee Meeting",
            description="Meeting Alice at the cafe",
        )
        # Add dates to scene
        scene_date1 = SceneDate(scene=scene, date=date(2024, 1, 14))
        scene_date2 = SceneDate(scene=scene, date=date(2024, 1, 15))

        scene.people.append(person)
        scene.locations.append(location)

        db_session.add_all([entry, scene, person, location, scene_date1, scene_date2])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["scenes"]) == 1
        scene_data = result["scenes"][0]
        assert scene_data["name"] == "Coffee Meeting"
        assert scene_data["description"] == "Meeting Alice at the cafe"
        assert len(scene_data["dates"]) == 2
        assert "2024-01-14" in scene_data["dates"]
        assert "2024-01-15" in scene_data["dates"]
        assert scene_data["people"] == ["Alice"]
        assert scene_data["locations"] == ["Cafe X"]

    def test_serialize_entry_with_scene_no_dates(self, db_session):
        """Test serializing entry with scene that has no dates."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        scene = Scene(
            entry=entry,
            name="Undated Scene",
            description="Scene without specific date",
        )

        db_session.add_all([entry, scene])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["scenes"]) == 1
        assert result["scenes"][0]["dates"] == []

    def test_serialize_entry_with_threads(self, db_session):
        """Test serializing entry with threads (new model structure)."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        person = Person(name="\1")

        thread = Thread(
            entry=entry,
            name="The First Kiss",
            from_date=date(2024, 1, 15),
            to_date="2023-12",
            content="Connection between current kiss and past memory",
        )
        thread.people.append(person)

        db_session.add_all([entry, thread, person])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["threads"]) == 1
        thread_data = result["threads"][0]
        assert thread_data["name"] == "The First Kiss"
        assert thread_data["from_date"] == "2024-01-15"
        assert thread_data["to_date"] == "2023-12"
        assert thread_data["content"] == "Connection between current kiss and past memory"
        assert thread_data["people"] == ["Clara"]

    def test_serialize_entry_with_multiple_scenes_and_threads(self, db_session):
        """Test serializing entry with multiple scenes and threads."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )

        # Create multiple scenes
        scene1 = Scene(entry=entry, name="Morning", description="Waking up")
        scene2 = Scene(entry=entry, name="Afternoon", description="Working")

        # Create multiple threads
        thread1 = Thread(
            entry=entry,
            name="Thread 1",
            from_date=date(2024, 1, 15),
            to_date="2023",
            content="First thread",
        )
        thread2 = Thread(
            entry=entry,
            name="Thread 2",
            from_date=date(2024, 1, 15),
            to_date="2024-01-10",
            content="Second thread",
        )

        db_session.add_all([entry, scene1, scene2, thread1, thread2])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["scenes"]) == 2
        assert len(result["threads"]) == 2

    def test_serialize_entry_timestamps(self, db_session):
        """Test serializing entry with created_at and updated_at timestamps."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        db_session.add(entry)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        # Check that timestamps are serialized as ISO format
        assert result["created_at"] is not None
        assert "T" in result["created_at"]  # ISO format includes T
        assert result["updated_at"] is not None
        assert "T" in result["updated_at"]

    def test_serialize_entry_with_all_relationships(self, db_session):
        """Test serializing entry with all types of relationships populated."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
            word_count=1000,
            reading_time=5.0,
            summary="Complex entry",
            rating=9,
        )

        # Add all relationship types
        city = City(name="Montreal")
        location = Location(name="Home", city=city)
        person = Person(name="\1")
        tag = Tag(name="personal")
        theme = Theme(name="growth")
        arc = Arc(name="Test Arc", description="Arc description")
        event = Event(name="Important Event")

        entry.cities.append(city)
        entry.locations.append(location)
        entry.people.append(person)
        entry.tags.append(tag)
        entry.themes.append(theme)
        entry.arcs.append(arc)
        entry.events.append(event)

        db_session.add_all([entry, city, location, person, tag, theme, arc, event])
        db_session.flush()

        # Add narrated dates
        nd = NarratedDate(entry_id=entry.id, date=date(2024, 6, 1))
        db_session.add(nd)

        # Add scene
        scene = Scene(entry=entry, name="Test Scene", description="Scene desc")
        scene.people.append(person)
        scene.locations.append(location)
        db_session.add(scene)

        # Add thread
        thread = Thread(
            entry=entry,
            name="Test Thread",
            from_date=date(2024, 1, 15),
            to_date="2023",
            content="Thread content",
        )
        db_session.add(thread)

        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        # Verify all fields are populated
        assert result["word_count"] == 1000
        assert len(result["narrated_dates"]) == 1
        assert len(result["cities"]) == 1
        assert len(result["locations"]) == 1
        assert len(result["people"]) == 1
        assert len(result["tags"]) == 1
        assert len(result["themes"]) == 1
        assert len(result["arcs"]) == 1
        assert len(result["events"]) == 1
        assert len(result["scenes"]) == 1
        assert len(result["threads"]) == 1


class TestSerializePerson:
    """Tests for ExportManager._serialize_person() method."""

    def test_serialize_minimal_person(self, db_session):
        """Test serializing person with only required fields."""
        person = Person(
            name="Alice",
            display_name="Alice",
        )
        db_session.add(person)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert result["id"] == person.id
        assert result["name"] == "Alice"
        assert result["alias"] is None
        assert result["lastname"] is None
        assert result["display_name"] == "Alice"
        assert result["relation_type"] is None
        assert result["entry_count"] == 0
        assert result["scene_count"] == 0
        assert result["first_appearance"] is None
        assert result["last_appearance"] is None
        assert result["characters"] == []

    def test_serialize_person_with_alias(self, db_session):
        """Test serializing person with alias field (new structure)."""
        person = Person(
            alias="bob",
            name="Robert",
            lastname="Smith",
            display_name="Bob",
        )
        db_session.add(person)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert result["alias"] == "bob"
        assert result["name"] == "Robert"
        assert result["lastname"] == "Smith"
        assert result["display_name"] == "Bob"

    def test_serialize_person_with_relation_type(self, db_session):
        """Test serializing person with relation type."""
        person = Person(
            name="Alice",
            display_name="Alice",
            relation_type=RelationType.FRIEND,
        )
        db_session.add(person)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert result["relation_type"] == "friend"

    def test_serialize_person_with_counts(self, db_session):
        """Test serializing person with entry and scene counts."""
        # Counts are computed properties based on relationships
        person = Person(name="Alice")
        entry = Entry(date=date(2024, 1, 15), file_path="/test.md", file_hash="abc")
        person.entries.append(entry)

        db_session.add_all([person, entry])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert result["entry_count"] == 1  # One related entry
        assert result["scene_count"] == 0  # No related scenes

    def test_serialize_person_with_appearances(self, db_session):
        """Test serializing person with first and last appearance dates."""
        # Appearances are computed from related entries
        person = Person(name="Alice")
        entry1 = Entry(date=date(2023, 1, 1), file_path="/2023.md", file_hash="abc")
        entry2 = Entry(date=date(2024, 12, 31), file_path="/2024.md", file_hash="def")
        person.entries.extend([entry1, entry2])

        db_session.add_all([person, entry1, entry2])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert result["first_appearance"] == "2023-01-01"
        assert result["last_appearance"] == "2024-12-31"

    def test_serialize_person_with_characters(self, db_session):
        """Test serializing person with character mappings (new structure)."""
        person = Person(
            name="Alice",
            display_name="Alice",
        )
        character = Character(name="Protagonist")
        mapping = PersonCharacterMap(
            person=person,
            character=character,
            contribution=ContributionType.PRIMARY,
        )

        db_session.add_all([person, character, mapping])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert len(result["characters"]) == 1
        char_data = result["characters"][0]
        assert char_data["name"] == "Protagonist"
        assert char_data["contribution"] == "primary"

    def test_serialize_person_with_multiple_characters(self, db_session):
        """Test serializing person with multiple character mappings."""
        person = Person(
            name="Alice",
            display_name="Alice",
        )
        char1 = Character(name="Main Character")
        char2 = Character(name="Supporting Character")
        mapping1 = PersonCharacterMap(
            person=person,
            character=char1,
            contribution=ContributionType.PRIMARY,
        )
        mapping2 = PersonCharacterMap(
            person=person,
            character=char2,
            contribution=ContributionType.COMPOSITE,
        )

        db_session.add_all([person, char1, char2, mapping1, mapping2])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert len(result["characters"]) == 2
        char_names = [c["name"] for c in result["characters"]]
        assert "Main Character" in char_names
        assert "Supporting Character" in char_names

    def test_serialize_person_full_data(self, db_session):
        """Test serializing person with all fields populated."""
        person = Person(
            alias="alice",
            name="Alice",
            lastname="Johnson",
            display_name="Alice J.",
            relation_type=RelationType.FRIEND,
            entry_count=10,
            scene_count=25,
            first_appearance=date(2023, 1, 1),
            last_appearance=date(2024, 12, 31),
        )
        character = Character(name="Hero")
        mapping = PersonCharacterMap(
            person=person,
            character=character,
            contribution=ContributionType.PRIMARY,
        )

        db_session.add_all([person, character, mapping])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        # Verify all fields
        assert result["alias"] == "alice"
        assert result["name"] == "Alice"
        assert result["lastname"] == "Johnson"
        assert result["display_name"] == "Alice J."
        assert result["relation_type"] == "friend"
        assert result["entry_count"] == 10
        assert result["scene_count"] == 25
        assert result["first_appearance"] == "2023-01-01"
        assert result["last_appearance"] == "2024-12-31"
        assert len(result["characters"]) == 1
        assert result["characters"][0]["name"] == "Hero"
        assert result["characters"][0]["contribution"] == "primary"


class TestSerializeEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_serialize_entry_with_null_date(self, db_session):
        """Test serializing entry with null date field."""
        entry = Entry(
            date=None,
            file_path="/test/path/entry.md",
            file_hash="abc123",
        )
        db_session.add(entry)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert result["date"] is None

    def test_serialize_entry_with_null_timestamps(self, db_session):
        """Test serializing entry with null timestamps."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
            created_at=None,
            updated_at=None,
        )
        db_session.add(entry)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert result["created_at"] is None
        assert result["updated_at"] is None

    def test_serialize_reference_with_partial_source(self, db_session):
        """Test serializing reference with source missing type."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        source = ReferenceSource(
            title="Book Title",
            type=None,
            author="Author Name",
        )
        ref = Reference(
            entry=entry,
            source=source,
            content="Quote",
        )

        db_session.add_all([entry, source, ref])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["references"]) == 1
        assert result["references"][0]["source"]["type"] is None

    def test_serialize_poem_with_no_title(self, db_session):
        """Test serializing poem version where poem has no title."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        # Poem model should have title, but test None handling
        poem = Poem(title=None)
        version = PoemVersion(
            poem=poem,
            entry=entry,
            content="Test content",
        )

        db_session.add_all([poem, version, entry])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["poems"]) == 1
        assert result["poems"][0]["title"] is None

    def test_serialize_person_with_no_relation_type(self, db_session):
        """Test serializing person with null relation type."""
        person = Person(
            name="Alice",
            display_name="Alice",
            relation_type=None,
        )
        db_session.add(person)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert result["relation_type"] is None

    def test_serialize_person_with_zero_counts(self, db_session):
        """Test serializing person with zero entry and scene counts."""
        person = Person(
            name="Alice",
            display_name="Alice",
            )
        db_session.add(person)
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_person(person)

        assert result["entry_count"] == 0
        assert result["scene_count"] == 0

    def test_serialize_thread_with_no_people(self, db_session):
        """Test serializing thread with empty people list."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        thread = Thread(
            entry=entry,
            name="Solo Thread",
            from_date=date(2024, 1, 15),
            to_date="2023",
            content="Thread with no people",
        )

        db_session.add_all([entry, thread])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["threads"]) == 1
        assert result["threads"][0]["people"] == []

    def test_serialize_scene_with_no_people_or_locations(self, db_session):
        """Test serializing scene with empty people and locations."""
        entry = Entry(
            date=date(2024, 1, 15),
            file_path="/test/path/2024-01-15.md",
            file_hash="abc123",
        )
        scene = Scene(
            entry=entry,
            name="Empty Scene",
            description="Scene with no people or locations",
        )

        db_session.add_all([entry, scene])
        db_session.commit()

        exporter = ExportManager()
        result = exporter._serialize_entry(entry)

        assert len(result["scenes"]) == 1
        assert result["scenes"][0]["people"] == []
        assert result["scenes"][0]["locations"] == []
