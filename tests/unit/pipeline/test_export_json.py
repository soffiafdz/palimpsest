#!/usr/bin/env python3
"""
test_export_json.py
-------------------
Tests for JSONExporter — the sole database export system.

Tests cover:
    - Entity serialization for all entity types (using natural keys)
    - Change detection (added/modified/deleted)
    - File writing with proper directory structure
    - Loading existing exports for comparison
    - README generation

Usage:
    python -m pytest tests/unit/pipeline/test_export_json.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json
from datetime import date

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.database.models import (
    Arc,
    Chapter,
    Character,
    City,
    Entry,
    Event,
    Location,
    ManuscriptReference,
    ManuscriptScene,
    ManuscriptSource,
    Motif,
    MotifInstance,
    Part,
    Person,
    PersonCharacterMap,
    Reference,
    ReferenceSource,
    Scene,
    SceneDate,
    Tag,
    Theme,
    Thread,
)
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    ContributionType,
    ReferenceMode,
    ReferenceType,
    RelationType,
    SceneOrigin,
    SceneStatus,
    SourceType,
)
from dev.pipeline.export_json import JSONExporter


# =========================================================================
# Helpers
# =========================================================================


def _create_entry(session: Session, entry_date: str = "2024-01-15") -> Entry:
    """Create a minimal entry for testing."""
    entry = Entry(
        date=date.fromisoformat(entry_date),
        file_path=f"content/md/2024/{entry_date}.md",
        file_hash="abc123",
        metadata_hash="def456",
        word_count=500,
        reading_time=2.5,
        summary="Test entry",
    )
    session.add(entry)
    session.flush()
    return entry


def _create_person(
    session: Session,
    name: str = "Alice",
    lastname: str = "Smith",
    relation_type: RelationType = RelationType.FRIEND,
) -> Person:
    """Create a person for testing."""
    slug = Person.generate_slug(name, lastname, None)
    person = Person(name=name, lastname=lastname, slug=slug, relation_type=relation_type)
    session.add(person)
    session.flush()
    return person


def _create_city(session: Session, name: str = "Montreal") -> City:
    """Create a city for testing."""
    city = City(name=name, country="Canada")
    session.add(city)
    session.flush()
    return city


def _create_location(session: Session, name: str = "Cafe X", city_id: int = 1) -> Location:
    """Create a location for testing."""
    loc = Location(name=name, city_id=city_id)
    session.add(loc)
    session.flush()
    return loc


def _create_scene(
    session: Session, name: str = "Morning Coffee", entry_id: int = 1
) -> Scene:
    """Create a scene for testing."""
    scene = Scene(name=name, description="Test scene", entry_id=entry_id)
    session.add(scene)
    session.flush()
    return scene


def _create_tag(session: Session, name: str = "writing") -> Tag:
    """Create a tag for testing."""
    tag = Tag(name=name)
    session.add(tag)
    session.flush()
    return tag


# =========================================================================
# Test Classes
# =========================================================================


class TestExportEntries:
    """Test entry serialization with natural key relationships."""

    def test_export_entry_basic_fields(self, db_session, test_db, tmp_dir):
        """Entry export includes all scalar fields."""
        _create_entry(db_session, "2024-01-15")
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_entries(db_session)

        assert "2024-01-15" in result
        data = result["2024-01-15"]
        assert data["date"] == "2024-01-15"
        assert data["file_path"] == "content/md/2024/2024-01-15.md"
        assert data["file_hash"] == "abc123"
        assert data["word_count"] == 500
        assert data["summary"] == "Test entry"

    def test_export_entry_relationship_natural_keys(self, db_session, test_db, tmp_dir):
        """Entry export includes natural keys for all M2M relationships."""
        entry = _create_entry(db_session, "2024-01-15")
        person = _create_person(db_session)
        tag = _create_tag(db_session)
        entry.people.append(person)
        entry.tags.append(tag)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_entries(db_session)

        data = result["2024-01-15"]
        assert person.slug in data["people"]
        assert tag.name in data["tags"]

    def test_export_entry_empty_relationships(self, db_session, test_db, tmp_dir):
        """Entry with no relationships exports empty lists."""
        entry = _create_entry(db_session)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_entries(db_session)

        data = result[entry.date.isoformat()]
        assert data["people"] == []
        assert data["tags"] == []
        assert data["scenes"] == []

    def test_export_entry_rating(self, db_session, test_db, tmp_dir):
        """Entry rating is exported as float."""
        entry = _create_entry(db_session)
        entry.rating = 4.5
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_entries(db_session)

        assert result[entry.date.isoformat()]["rating"] == 4.5

    def test_export_entry_null_rating(self, db_session, test_db, tmp_dir):
        """Entry with no rating exports None."""
        entry = _create_entry(db_session)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_entries(db_session)

        assert result[entry.date.isoformat()]["rating"] is None

    def test_export_updates_stats(self, db_session, test_db, tmp_dir):
        """Export method tracks entity counts in stats."""
        _create_entry(db_session, "2024-01-15")
        _create_entry(db_session, "2024-01-16")
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        exporter._export_entries(db_session)

        assert exporter.stats["entries"] == 2


class TestExportPeople:
    """Test person serialization with slug."""

    def test_export_person_fields(self, db_session, test_db, tmp_dir):
        """Person export includes all fields including slug."""
        person = _create_person(db_session, "Alice", "Smith", RelationType.FRIEND)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_people(db_session)

        data = result[person.slug]
        assert data["slug"] == person.slug
        assert data["name"] == "Alice"
        assert data["lastname"] == "Smith"
        assert data["relation_type"] == "friend"

    def test_export_person_null_relation(self, db_session, test_db, tmp_dir):
        """Person with no relation_type exports None."""
        slug = Person.generate_slug("Unknown", "Person", None)
        person = Person(name="Unknown", lastname="Person", slug=slug)
        db_session.add(person)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_people(db_session)

        assert result[person.slug]["relation_type"] is None

    def test_export_person_with_disambiguator(self, db_session, test_db, tmp_dir):
        """Person with disambiguator exports it."""
        slug = Person.generate_slug("Alice", None, "tall")
        person = Person(name="Alice", disambiguator="tall", slug=slug)
        db_session.add(person)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_people(db_session)

        assert result[person.slug]["disambiguator"] == "tall"


class TestExportScenes:
    """Test scene serialization with natural keys."""

    def test_export_scene_fields(self, db_session, test_db, tmp_dir):
        """Scene export includes all fields."""
        entry = _create_entry(db_session)
        _create_scene(db_session, "Morning Coffee", entry.id)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_scenes(db_session)

        key = f"Morning Coffee::{entry.date.isoformat()}"
        data = result[key]
        assert data["name"] == "Morning Coffee"
        assert data["description"] == "Test scene"
        assert data["entry_date"] == entry.date.isoformat()

    def test_export_scene_with_dates(self, db_session, test_db, tmp_dir):
        """Scene with dates exports date strings."""
        entry = _create_entry(db_session)
        scene = _create_scene(db_session, "Morning Coffee", entry.id)
        sd = SceneDate(scene_id=scene.id, date="2024-01-15")
        db_session.add(sd)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_scenes(db_session)

        key = f"Morning Coffee::{entry.date.isoformat()}"
        assert "2024-01-15" in result[key]["dates"]

    def test_export_scene_with_people(self, db_session, test_db, tmp_dir):
        """Scene with people exports people slugs."""
        entry = _create_entry(db_session)
        scene = _create_scene(db_session, "Morning Coffee", entry.id)
        person = _create_person(db_session)
        scene.people.append(person)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_scenes(db_session)

        key = f"Morning Coffee::{entry.date.isoformat()}"
        assert person.slug in result[key]["people"]

    def test_export_scene_with_locations(self, db_session, test_db, tmp_dir):
        """Scene with locations exports location natural keys."""
        entry = _create_entry(db_session)
        city = _create_city(db_session)
        loc = _create_location(db_session, "Cafe X", city.id)
        scene = _create_scene(db_session, "Morning Coffee", entry.id)
        scene.locations.append(loc)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_scenes(db_session)

        key = f"Morning Coffee::{entry.date.isoformat()}"
        assert "Cafe X::Montreal" in result[key]["locations"]


class TestExportEvents:
    """Test event serialization."""

    def test_export_event_with_scenes(self, db_session, test_db, tmp_dir):
        """Event export includes scene natural keys."""
        entry = _create_entry(db_session)
        scene = _create_scene(db_session, "Morning Coffee", entry.id)
        event = Event(name="Daily Routine")
        db_session.add(event)
        db_session.flush()
        event.scenes.append(scene)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_events(db_session)

        data = result["Daily Routine"]
        assert data["name"] == "Daily Routine"
        scene_key = f"Morning Coffee::{entry.date.isoformat()}"
        assert scene_key in data["scenes"]


class TestExportThreads:
    """Test thread serialization with natural keys."""

    def test_export_thread_fields(self, db_session, test_db, tmp_dir):
        """Thread export includes all fields with natural keys."""
        entry = _create_entry(db_session)
        thread = Thread(
            name="The Bookend Kiss",
            from_date="2024-01-15",
            to_date="2023",
            content="Connection between moments",
            entry_id=entry.id,
        )
        db_session.add(thread)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_threads(db_session)

        key = f"The Bookend Kiss::{entry.date.isoformat()}"
        data = result[key]
        assert data["name"] == "The Bookend Kiss"
        assert data["from_date"] == "2024-01-15"
        assert data["to_date"] == "2023"
        assert data["content"] == "Connection between moments"
        assert data["entry_date"] == entry.date.isoformat()

    def test_export_thread_with_people(self, db_session, test_db, tmp_dir):
        """Thread with people exports people slugs."""
        entry = _create_entry(db_session)
        person = _create_person(db_session)
        thread = Thread(
            name="Memory Thread",
            from_date="2024-01-15",
            to_date="2020",
            content="Test",
            entry_id=entry.id,
        )
        db_session.add(thread)
        db_session.flush()
        thread.people.append(person)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_threads(db_session)

        key = f"Memory Thread::{entry.date.isoformat()}"
        assert person.slug in result[key]["people"]


class TestExportSimpleEntities:
    """Test serialization of tags, themes, arcs, motifs."""

    def test_export_tags(self, db_session, test_db, tmp_dir):
        """Tag export includes name."""
        _create_tag(db_session, "writing")
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_tags(db_session)

        assert result["writing"]["name"] == "writing"

    def test_export_themes(self, db_session, test_db, tmp_dir):
        """Theme export includes name."""
        theme = Theme(name="identity")
        db_session.add(theme)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_themes(db_session)

        assert result["identity"]["name"] == "identity"

    def test_export_arcs(self, db_session, test_db, tmp_dir):
        """Arc export includes name and description."""
        arc = Arc(name="The Long Wanting", description="A narrative arc")
        db_session.add(arc)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_arcs(db_session)

        data = result["The Long Wanting"]
        assert data["name"] == "The Long Wanting"
        assert data["description"] == "A narrative arc"

    def test_export_motifs(self, db_session, test_db, tmp_dir):
        """Motif export includes name."""
        motif = Motif(name="water")
        db_session.add(motif)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_motifs(db_session)

        assert result["water"]["name"] == "water"

    def test_export_motif_instances(self, db_session, test_db, tmp_dir):
        """MotifInstance export includes motif name and entry date."""
        entry = _create_entry(db_session)
        motif = Motif(name="water")
        db_session.add(motif)
        db_session.flush()
        mi = MotifInstance(
            description="Water imagery",
            motif_id=motif.id,
            entry_id=entry.id,
        )
        db_session.add(mi)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_motif_instances(db_session)

        key = f"water::{entry.date.isoformat()}"
        data = result[key]
        assert data["motif"] == "water"
        assert data["entry_date"] == entry.date.isoformat()
        assert data["description"] == "Water imagery"


class TestExportReferences:
    """Test reference serialization with natural keys."""

    def test_export_reference_with_mode(self, db_session, test_db, tmp_dir):
        """Reference export includes natural keys."""
        entry = _create_entry(db_session)
        source = ReferenceSource(
            title="Important Book",
            author="Author Name",
            type=ReferenceType.BOOK,
        )
        db_session.add(source)
        db_session.flush()
        ref = Reference(
            content="Quote from book",
            description="A key passage",
            mode=ReferenceMode.DIRECT,
            source_id=source.id,
            entry_id=entry.id,
        )
        db_session.add(ref)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_references(db_session)

        key = f"Important Book::direct::{entry.date.isoformat()}"
        data = result[key]
        assert data["content"] == "Quote from book"
        assert data["mode"] == "direct"
        assert data["source"] == "Important Book"
        assert data["entry_date"] == entry.date.isoformat()

    def test_export_reference_source(self, db_session, test_db, tmp_dir):
        """ReferenceSource export includes type enum."""
        source = ReferenceSource(
            title="Important Book",
            author="Author Name",
            type=ReferenceType.BOOK,
            url="https://example.com",
        )
        db_session.add(source)
        db_session.flush()
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_reference_sources(db_session)

        data = result["Important Book"]
        assert data["title"] == "Important Book"
        assert data["type"] == "book"
        assert data["url"] == "https://example.com"


class TestChangeDetection:
    """Test _generate_changes for added/modified/deleted entities."""

    def test_detect_added_entity(self, test_db, tmp_dir):
        """New entity in new_exports generates '+' change."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"tags": {}}
        new = {"tags": {"writing": {"name": "writing"}}}

        exporter._generate_changes(old, new)

        assert len(exporter.changes) == 1
        assert exporter.changes[0].startswith("+ tag")
        assert "writing" in exporter.changes[0]

    def test_detect_deleted_entity(self, test_db, tmp_dir):
        """Entity in old but not new generates '-' change."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"tags": {"old-tag": {"name": "old-tag"}}}
        new = {"tags": {}}

        exporter._generate_changes(old, new)

        assert len(exporter.changes) == 1
        assert exporter.changes[0].startswith("- tag")

    def test_detect_modified_entity(self, test_db, tmp_dir):
        """Changed entity generates '~' change with field descriptions."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"tags": {"myTag": {"name": "old-name"}}}
        new = {"tags": {"myTag": {"name": "new-name"}}}

        exporter._generate_changes(old, new)

        assert len(exporter.changes) == 1
        assert exporter.changes[0].startswith("~ tag")
        assert "old-name" in exporter.changes[0]
        assert "new-name" in exporter.changes[0]

    def test_no_changes_when_equal(self, test_db, tmp_dir):
        """Identical exports generate no changes."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        data = {"tags": {"same": {"name": "same"}}}

        exporter._generate_changes(data, data)

        assert len(exporter.changes) == 0

    def test_detect_relationship_changes(self, test_db, tmp_dir):
        """Changes to natural key lists describe additions/removals."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"entries": {"2024-01-15": {"date": "2024-01-15", "people": ["alice_smith", "bob_jones"]}}}
        new = {"entries": {"2024-01-15": {"date": "2024-01-15", "people": ["bob_jones", "charlie_brown"]}}}

        exporter._generate_changes(old, new)

        assert len(exporter.changes) == 1
        change = exporter.changes[0]
        assert "+people" in change or "-people" in change

    def test_text_field_change_not_verbose(self, test_db, tmp_dir):
        """Text field changes say [changed] instead of showing full diff."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"entries": {"2024-01-15": {"date": "2024-01-15", "summary": "old text"}}}
        new = {"entries": {"2024-01-15": {"date": "2024-01-15", "summary": "new text"}}}

        exporter._generate_changes(old, new)

        assert "[changed]" in exporter.changes[0]


class TestWriteExports:
    """Test file writing with proper directory structure."""

    def test_write_entry_files(self, test_db, tmp_dir):
        """Entries are written to entries/YYYY/YYYY-MM-DD.json."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exports = {
            "entries": {
                "2024-01-15": {"date": "2024-01-15", "summary": "Test"},
            },
            "people": {},
            "locations": {},
            "cities": {},
            "scenes": {},
            "events": {},
            "threads": {},
            "arcs": {},
            "poems": {},
            "references": {},
            "reference_sources": {},
            "tags": {},
            "themes": {},
            "motifs": {},
            "motif_instances": {},
        }

        exporter._write_exports(exports)

        entry_file = tmp_dir / "journal" / "entries" / "2024" / "2024-01-15.json"
        assert entry_file.exists()
        data = json.loads(entry_file.read_text())
        assert data["date"] == "2024-01-15"

    def test_write_people_files(self, test_db, tmp_dir):
        """People are written to people/{name}.json."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exports = {
            "entries": {},
            "people": {
                "alice_smith": {"slug": "alice_smith", "name": "Alice", "lastname": "Smith", "disambiguator": None},
            },
            "locations": {},
            "cities": {},
            "scenes": {},
            "events": {},
            "threads": {},
            "arcs": {},
            "poems": {},
            "references": {},
            "reference_sources": {},
            "tags": {},
            "themes": {},
            "motifs": {},
            "motif_instances": {},
        }

        exporter._write_exports(exports)

        people_dir = tmp_dir / "journal" / "people"
        assert people_dir.exists()
        json_files = list(people_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_write_location_files(self, test_db, tmp_dir):
        """Locations are written to locations/{city}/{location}.json."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exports = {
            "entries": {},
            "people": {},
            "locations": {
                "Cafe X::Montreal": {"name": "Cafe X", "city": "Montreal"},
            },
            "cities": {
                "Montreal": {"name": "Montreal", "country": "Canada"},
            },
            "scenes": {},
            "events": {},
            "threads": {},
            "arcs": {},
            "poems": {},
            "references": {},
            "reference_sources": {},
            "tags": {},
            "themes": {},
            "motifs": {},
            "motif_instances": {},
        }

        exporter._write_exports(exports)

        loc_dir = tmp_dir / "journal" / "locations" / "montreal"
        assert loc_dir.exists()

    def test_write_scene_files(self, test_db, tmp_dir):
        """Scenes are written to scenes/{YYYY-MM-DD}/{scene-name}.json."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exports = {
            "entries": {},
            "people": {},
            "locations": {},
            "cities": {},
            "scenes": {
                "Morning Coffee::2024-01-15": {"name": "Morning Coffee", "entry_date": "2024-01-15"},
            },
            "events": {},
            "threads": {},
            "arcs": {},
            "poems": {},
            "references": {},
            "reference_sources": {},
            "tags": {},
            "themes": {},
            "motifs": {},
            "motif_instances": {},
        }

        exporter._write_exports(exports)

        scenes_dir = tmp_dir / "journal" / "scenes" / "2024-01-15"
        assert scenes_dir.exists()
        json_files = list(scenes_dir.glob("*.json"))
        assert len(json_files) == 1

    def test_write_simple_entities(self, test_db, tmp_dir):
        """Simple entities are written to {type}/{slug}.json."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exports = {
            "entries": {},
            "people": {},
            "locations": {},
            "cities": {},
            "scenes": {},
            "events": {
                "Daily Routine": {"name": "Daily Routine", "scenes": []},
            },
            "threads": {},
            "arcs": {},
            "poems": {},
            "references": {},
            "reference_sources": {},
            "tags": {
                "writing": {"name": "writing"},
            },
            "themes": {},
            "motifs": {},
            "motif_instances": {},
        }

        exporter._write_exports(exports)

        tag_file = tmp_dir / "journal" / "tags" / "writing.json"
        assert tag_file.exists()

        event_file = tmp_dir / "journal" / "events" / "daily-routine.json"
        assert event_file.exists()


class TestLoadExistingExports:
    """Test loading old JSON files for comparison."""

    def test_load_empty_directory(self, test_db, tmp_dir):
        """Loading from non-existent directory returns empty dicts."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        result = exporter._load_existing_exports()

        assert result == {}

    def test_load_existing_json(self, test_db, tmp_dir):
        """Loading existing JSON files returns proper structure."""
        # Write a JSON file manually
        journal_dir = tmp_dir / "journal" / "tags"
        journal_dir.mkdir(parents=True)
        tag_data = {"name": "writing"}
        (journal_dir / "writing.json").write_text(json.dumps(tag_data))

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        result = exporter._load_existing_exports()

        assert "tags" in result
        assert "writing" in result["tags"]
        assert result["tags"]["writing"]["name"] == "writing"

    def test_skip_corrupted_files(self, test_db, tmp_dir):
        """Corrupted JSON files are skipped with warning."""
        journal_dir = tmp_dir / "journal" / "tags"
        journal_dir.mkdir(parents=True)
        (journal_dir / "bad.json").write_text("not valid json {{{")

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        result = exporter._load_existing_exports()

        # Should not crash, corrupted file is skipped
        assert "tags" in result
        assert len(result["tags"]) == 0

    def test_skip_files_without_natural_key(self, test_db, tmp_dir):
        """JSON files without natural key fields are skipped."""
        journal_dir = tmp_dir / "journal" / "tags"
        journal_dir.mkdir(parents=True)
        (journal_dir / "no-name.json").write_text(json.dumps({"other": "field"}))

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        result = exporter._load_existing_exports()

        assert len(result["tags"]) == 0


class TestWriteReadme:
    """Test README generation."""

    def test_readme_no_changes(self, test_db, tmp_dir):
        """README with no changes says 'No changes'."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.stats = {"entries": 5, "people": 3}

        exporter._write_readme()

        readme = (tmp_dir / "README.md").read_text()
        assert "No changes since last export" in readme
        assert "5" in readme  # entry count

    def test_readme_with_changes(self, test_db, tmp_dir):
        """README with changes categorizes added/modified/deleted."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.stats = {"entries": 5}
        exporter.changes = [
            "+ tag writing",
            "~ entry 2024-01-15: ~summary [changed]",
            "- tag old-tag",
        ]

        exporter._write_readme()

        readme = (tmp_dir / "README.md").read_text()
        assert "### Added" in readme
        assert "### Modified" in readme
        assert "### Deleted" in readme
        assert "1 added, 1 modified, 1 deleted" in readme


class TestGetEntitySlug:
    """Test human-readable slug generation."""

    def test_entry_slug_is_date(self, test_db, tmp_dir):
        """Entry slug is the date string."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        slug = exporter._get_entity_slug("entries", {"date": "2024-01-15"})
        assert slug == "2024-01-15"

    def test_people_slug_uses_slug_field(self, test_db, tmp_dir):
        """People slug uses the slug field."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        slug = exporter._get_entity_slug(
            "people", {"slug": "alice_smith", "name": "Alice", "lastname": "Smith"}
        )
        assert slug == "alice_smith"

    def test_generic_slug_uses_name(self, test_db, tmp_dir):
        """Other entities use name field."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        slug = exporter._get_entity_slug("tags", {"name": "writing"})
        assert slug == "writing"

    def test_fallback_slug_uses_unknown(self, test_db, tmp_dir):
        """Entity without name/title/slug falls back to unknown."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        slug = exporter._get_entity_slug("unknown_type", {"other": "field"})
        assert slug == "unknown"


class TestDescribeFieldChanges:
    """Test field change description formatting."""

    def test_relationship_additions(self, test_db, tmp_dir):
        """Added items in relationship lists are described."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"people": ["alice_smith"]}
        new = {"people": ["alice_smith", "bob_jones"]}
        result = exporter._describe_field_changes(old, new)
        assert "+people" in result

    def test_relationship_removals(self, test_db, tmp_dir):
        """Removed items in relationship lists are described."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"people": ["alice_smith", "bob_jones"]}
        new = {"people": ["alice_smith"]}
        result = exporter._describe_field_changes(old, new)
        assert "-people" in result

    def test_scalar_changes(self, test_db, tmp_dir):
        """Scalar field changes show old->new."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"word_count": 500}
        new = {"word_count": 600}
        result = exporter._describe_field_changes(old, new)
        assert "500" in result
        assert "600" in result

    def test_text_changes_abbreviated(self, test_db, tmp_dir):
        """Text field changes are abbreviated to [changed]."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"summary": "old text"}
        new = {"summary": "new text"}
        result = exporter._describe_field_changes(old, new)
        assert "[changed]" in result

    def test_changes_limited_to_five(self, test_db, tmp_dir):
        """Field changes are limited to 5 per entity."""
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        old = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5, "f": 6}
        new = {"a": 10, "b": 20, "c": 30, "d": 40, "e": 50, "f": 60}
        result = exporter._describe_field_changes(old, new)
        # Should have at most 5 comma-separated parts
        assert result.count(",") <= 4


# =========================================================================
# Manuscript Export Tests
# =========================================================================


class TestExportParts:
    """Test part serialization."""

    def test_export_part_fields(self, db_session, test_db, tmp_dir):
        """Part export includes number and title."""
        part = Part(number=1, title="Arrival")
        db_session.add(part)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_parts(db_session)

        data = result["1"]
        assert data["number"] == 1
        assert data["title"] == "Arrival"

    def test_export_part_null_fields(self, db_session, test_db, tmp_dir):
        """Part with null number/title exports None."""
        part = Part()
        db_session.add(part)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_parts(db_session)

        # Should have a key (fallback to part-{id})
        keys = list(result.keys())
        assert len(keys) == 1
        data = result[keys[0]]
        assert data["number"] is None
        assert data["title"] is None

    def test_export_parts_stats(self, db_session, test_db, tmp_dir):
        """Export tracks part count in stats."""
        db_session.add(Part(number=1, title="Part One"))
        db_session.add(Part(number=2, title="Part Two"))
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        exporter._export_parts(db_session)

        assert exporter.stats["parts"] == 2


class TestExportChapters:
    """Test chapter serialization with natural keys."""

    def test_export_chapter_fields(self, db_session, test_db, tmp_dir):
        """Chapter export includes all scalar fields and enum values."""
        chapter = Chapter(
            title="The Gray Fence",
            number=1,
            type=ChapterType.PROSE,
            status=ChapterStatus.DRAFT,
            content="A brief moment.",
        )
        db_session.add(chapter)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_chapters(db_session)

        data = result["The Gray Fence"]
        assert data["title"] == "The Gray Fence"
        assert data["number"] == 1
        assert data["type"] == "prose"
        assert data["status"] == "draft"
        assert data["content"] == "A brief moment."
        assert data["part"] is None

    def test_export_chapter_with_part(self, db_session, test_db, tmp_dir):
        """Chapter export includes part number when assigned."""
        part = Part(number=1, title="Arrival")
        db_session.add(part)
        db_session.flush()
        chapter = Chapter(title="First Chapter", part_id=part.id)
        db_session.add(chapter)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_chapters(db_session)

        assert result["First Chapter"]["part"] == 1

    def test_export_chapter_relationship_natural_keys(self, db_session, test_db, tmp_dir):
        """Chapter export includes character names and arc names."""
        chapter = Chapter(title="Test Chapter")
        char = Character(name="Sofia", is_narrator=True)
        arc = Arc(name="The Long Wanting")
        db_session.add_all([chapter, char, arc])
        db_session.flush()
        chapter.characters.append(char)
        chapter.arcs.append(arc)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_chapters(db_session)

        data = result["Test Chapter"]
        assert "Sofia" in data["characters"]
        assert "The Long Wanting" in data["arcs"]

    def test_export_chapter_empty_relationships(self, db_session, test_db, tmp_dir):
        """Chapter with no relationships exports empty lists."""
        chapter = Chapter(title="Empty Chapter")
        db_session.add(chapter)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_chapters(db_session)

        data = result["Empty Chapter"]
        assert data["poems"] == []
        assert data["characters"] == []
        assert data["arcs"] == []


class TestExportCharacters:
    """Test character serialization."""

    def test_export_character_fields(self, db_session, test_db, tmp_dir):
        """Character export includes all fields."""
        char = Character(
            name="Sofia",
            description="The narrator",
            role="protagonist",
            is_narrator=True,
        )
        db_session.add(char)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_characters(db_session)

        data = result["Sofia"]
        assert data["name"] == "Sofia"
        assert data["description"] == "The narrator"
        assert data["role"] == "protagonist"
        assert data["is_narrator"] is True

    def test_export_character_minimal(self, db_session, test_db, tmp_dir):
        """Character with only name exports nulls for optional fields."""
        char = Character(name="Minor")
        db_session.add(char)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_characters(db_session)

        data = result["Minor"]
        assert data["name"] == "Minor"
        assert data["description"] is None
        assert data["role"] is None
        assert data["is_narrator"] is False


class TestExportPersonCharacterMaps:
    """Test person-character mapping serialization with natural keys."""

    def test_export_mapping_fields(self, db_session, test_db, tmp_dir):
        """PersonCharacterMap export includes all fields with natural keys."""
        person = _create_person(db_session, "Maria", "Garcia")
        char = Character(name="Sofia")
        db_session.add(char)
        db_session.flush()
        mapping = PersonCharacterMap(
            person_id=person.id,
            character_id=char.id,
            contribution=ContributionType.PRIMARY,
            notes="Main inspiration",
        )
        db_session.add(mapping)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_person_character_maps(db_session)

        key = f"{person.slug}::Sofia"
        data = result[key]
        assert data["person"] == person.slug
        assert data["character"] == "Sofia"
        assert data["contribution"] == "primary"
        assert data["notes"] == "Main inspiration"

    def test_export_mapping_null_notes(self, db_session, test_db, tmp_dir):
        """Mapping without notes exports None."""
        person = _create_person(db_session, "Ana", "Lopez")
        char = Character(name="Clara")
        db_session.add(char)
        db_session.flush()
        mapping = PersonCharacterMap(
            person_id=person.id,
            character_id=char.id,
            contribution=ContributionType.INSPIRATION,
        )
        db_session.add(mapping)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_person_character_maps(db_session)

        key = f"{person.slug}::Clara"
        data = result[key]
        assert data["contribution"] == "inspiration"
        assert data["notes"] is None


class TestExportManuscriptScenes:
    """Test manuscript scene serialization with natural keys."""

    def test_export_scene_fields(self, db_session, test_db, tmp_dir):
        """ManuscriptScene export includes all fields with natural keys."""
        chapter = Chapter(title="Test Chapter")
        db_session.add(chapter)
        db_session.flush()
        scene = ManuscriptScene(
            name="Morning at the Fence",
            description="A quiet scene",
            chapter_id=chapter.id,
            origin=SceneOrigin.JOURNALED,
            status=SceneStatus.INCLUDED,
            notes="Key scene",
        )
        db_session.add(scene)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_manuscript_scenes(db_session)

        data = result["Morning at the Fence"]
        assert data["name"] == "Morning at the Fence"
        assert data["description"] == "A quiet scene"
        assert data["chapter"] == "Test Chapter"
        assert data["origin"] == "journaled"
        assert data["status"] == "included"
        assert data["notes"] == "Key scene"

    def test_export_scene_minimal(self, db_session, test_db, tmp_dir):
        """ManuscriptScene with only required fields exports nulls."""
        chapter = Chapter(title="Test Chapter")
        db_session.add(chapter)
        db_session.flush()
        scene = ManuscriptScene(
            name="Fragment",
            chapter_id=chapter.id,
            origin=SceneOrigin.INVENTED,
            status=SceneStatus.FRAGMENT,
        )
        db_session.add(scene)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_manuscript_scenes(db_session)

        data = result["Fragment"]
        assert data["description"] is None
        assert data["notes"] is None
        assert data["origin"] == "invented"
        assert data["status"] == "fragment"


class TestExportManuscriptSources:
    """Test manuscript source serialization with natural keys."""

    def test_export_entry_source(self, db_session, test_db, tmp_dir):
        """ManuscriptSource with entry source_type exports entry date."""
        entry = _create_entry(db_session)
        chapter = Chapter(title="Test Chapter")
        db_session.add(chapter)
        db_session.flush()
        ms_scene = ManuscriptScene(
            name="Test Scene",
            chapter_id=chapter.id,
            origin=SceneOrigin.JOURNALED,
            status=SceneStatus.FRAGMENT,
        )
        db_session.add(ms_scene)
        db_session.flush()
        source = ManuscriptSource(
            manuscript_scene_id=ms_scene.id,
            source_type=SourceType.ENTRY,
            entry_id=entry.id,
        )
        db_session.add(source)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_manuscript_sources(db_session)

        # Key should contain scene name, source type, and entry date
        keys = list(result.keys())
        assert len(keys) == 1
        data = result[keys[0]]
        assert data["source_type"] == "entry"
        assert data["entry_date"] == entry.date.isoformat()
        assert data["scene"] is None
        assert data["thread"] is None

    def test_export_external_source(self, db_session, test_db, tmp_dir):
        """ManuscriptSource with external type exports external_note."""
        chapter = Chapter(title="Test Chapter")
        db_session.add(chapter)
        db_session.flush()
        ms_scene = ManuscriptScene(
            name="Test Scene",
            chapter_id=chapter.id,
            origin=SceneOrigin.INVENTED,
            status=SceneStatus.FRAGMENT,
        )
        db_session.add(ms_scene)
        db_session.flush()
        source = ManuscriptSource(
            manuscript_scene_id=ms_scene.id,
            source_type=SourceType.EXTERNAL,
            external_note="Family story told by mother",
        )
        db_session.add(source)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_manuscript_sources(db_session)

        keys = list(result.keys())
        assert len(keys) == 1
        data = result[keys[0]]
        assert data["source_type"] == "external"
        assert data["external_note"] == "Family story told by mother"


class TestExportManuscriptReferences:
    """Test manuscript reference serialization with natural keys."""

    def test_export_reference_fields(self, db_session, test_db, tmp_dir):
        """ManuscriptReference export includes all fields with natural keys."""
        chapter = Chapter(title="Test Chapter")
        ref_source = ReferenceSource(
            title="Important Book",
            author="Author",
            type=ReferenceType.BOOK,
        )
        db_session.add_all([chapter, ref_source])
        db_session.flush()
        ref = ManuscriptReference(
            chapter_id=chapter.id,
            source_id=ref_source.id,
            mode=ReferenceMode.DIRECT,
            content="A notable quote",
            notes="Use in opening",
        )
        db_session.add(ref)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_manuscript_references(db_session)

        key = "Test Chapter::Important Book"
        data = result[key]
        assert data["chapter"] == "Test Chapter"
        assert data["source"] == "Important Book"
        assert data["mode"] == "direct"
        assert data["content"] == "A notable quote"
        assert data["notes"] == "Use in opening"

    def test_export_reference_thematic(self, db_session, test_db, tmp_dir):
        """ManuscriptReference with thematic mode and no content."""
        chapter = Chapter(title="Test Chapter")
        ref_source = ReferenceSource(
            title="Film",
            author="Director",
            type=ReferenceType.FILM,
        )
        db_session.add_all([chapter, ref_source])
        db_session.flush()
        ref = ManuscriptReference(
            chapter_id=chapter.id,
            source_id=ref_source.id,
            mode=ReferenceMode.THEMATIC,
        )
        db_session.add(ref)
        db_session.commit()

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter._build_lookups(db_session)
        result = exporter._export_manuscript_references(db_session)

        key = "Test Chapter::Film"
        data = result[key]
        assert data["mode"] == "thematic"
        assert data["content"] is None
        assert data["notes"] is None
