#!/usr/bin/env python3
"""
test_import_json.py
-------------------
Tests for JSONImporter — database import from JSON export files.

Tests cover:
    - Round-trip: export → clear DB → import → verify data matches
    - Idempotency: import same data twice → no duplicates
    - Partial imports: missing entity types handled gracefully
    - Natural key resolution for M2M relationships
    - Manuscript entity import (chapters, scenes, sources, references)

Usage:
    python -m pytest tests/unit/pipeline/test_import_json.py -v
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
    Part,
    Person,
    PersonCharacterMap,
    Poem,
    PoemVersion,
    Reference,
    ReferenceSource,
    Scene,
    Tag,
    Theme,
    Thread,
)
from dev.database.models.metadata import Motif, MotifInstance, ThemeInstance
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
from dev.pipeline.import_json import JSONImporter


# =========================================================================
# Helpers
# =========================================================================


def _populate_db(session: Session) -> None:
    """
    Populate a test database with entities across all types.

    Creates a small but representative set of entities with all
    relationship types (FK, M2M, O2M) for round-trip testing.

    Args:
        session: Active SQLAlchemy session
    """
    # Leaf entities
    city = City(name="Montreal", country="Canada")
    session.add(city)
    session.flush()

    tag = Tag(name="writing")
    arc = Arc(name="The Long Wanting")
    theme = Theme(name="Loss")
    motif = Motif(name="Mirrors")
    session.add_all([tag, arc, theme, motif])
    session.flush()

    poem = Poem(title="The Gray Fence")
    ref_source = ReferenceSource(
        title="Nocturnes", author="Ishiguro", type=ReferenceType.BOOK,
    )
    session.add_all([poem, ref_source])
    session.flush()

    part = Part(number=1, title="The Archive")
    session.add(part)
    session.flush()

    # People
    person = Person(
        name="Sofia", lastname="Fernandez",
        slug="sofia_fernandez", relation_type=RelationType.SELF,
    )
    session.add(person)
    session.flush()

    # Locations
    location = Location(name="Café Olimpico", city_id=city.id)
    session.add(location)
    session.flush()

    # Entries with M2M
    entry = Entry(
        date=date(2024, 11, 8),
        file_path="content/md/2024/2024-11-08.md",
        word_count=1000,
    )
    session.add(entry)
    session.flush()
    entry.people.append(person)
    entry.locations.append(location)
    entry.cities.append(city)
    entry.arcs.append(arc)
    entry.tags.append(tag)

    # Scenes + Threads
    scene = Scene(
        name="Morning at the Café",
        description="A conversation over espresso.",
        entry_id=entry.id,
    )
    thread = Thread(
        name="The Espresso Thread",
        from_date="2024-11-08",
        to_date="2023-06-15",
        content="Coffee and silence.",
        entry_id=entry.id,
    )
    session.add_all([scene, thread])
    session.flush()
    scene.people.append(person)
    scene.locations.append(location)

    # Events
    event = Event(name="The Long November")
    session.add(event)
    session.flush()
    event.scenes.append(scene)
    entry.events.append(event)

    # Theme/Motif instances
    ti = ThemeInstance(
        theme_id=theme.id, entry_id=entry.id,
        description="Loss of home",
    )
    mi = MotifInstance(
        motif_id=motif.id, entry_id=entry.id,
        description="The mirror in the hallway",
    )
    session.add_all([ti, mi])

    # Poem versions
    pv = PoemVersion(
        poem_id=poem.id, entry_id=entry.id,
        content="The gray fence divides us still",
    )
    session.add(pv)

    # References
    ref = Reference(
        entry_id=entry.id,
        source_id=ref_source.id,
        content="the view from the window",
    )
    session.add(ref)

    # Manuscript: Chapter + Character
    chapter = Chapter(
        title="Espresso and Silence",
        number=1,
        part_id=part.id,
        type=ChapterType.PROSE,
        status=ChapterStatus.DRAFT,
    )
    session.add(chapter)
    session.flush()
    chapter.poems.append(poem)

    character = Character(
        name="Valeria", role="Protagonist",
        is_narrator=True, description="The narrator.",
    )
    session.add(character)
    session.flush()

    pcm = PersonCharacterMap(
        person_id=person.id,
        character_id=character.id,
        contribution=ContributionType.PRIMARY,
    )
    session.add(pcm)

    ms_scene = ManuscriptScene(
        name="The Espresso Pause",
        description="Valeria watches.",
        chapter_id=chapter.id,
        origin=SceneOrigin.JOURNALED,
        status=SceneStatus.DRAFT,
    )
    session.add(ms_scene)
    session.flush()
    ms_scene.characters.append(character)

    ms_source = ManuscriptSource(
        manuscript_scene_id=ms_scene.id,
        source_type=SourceType.SCENE,
        scene_id=scene.id,
    )
    session.add(ms_source)

    ms_ref = ManuscriptReference(
        chapter_id=chapter.id,
        source_id=ref_source.id,
        mode=ReferenceMode.THEMATIC,
        content="memory and loss",
    )
    session.add(ms_ref)

    session.commit()


def _clear_all_tables(session: Session) -> None:
    """
    Delete all rows from all entity tables in safe FK order.

    Args:
        session: Active SQLAlchemy session
    """
    # Delete in reverse FK order (dependents first)
    session.query(ManuscriptReference).delete()
    session.query(ManuscriptSource).delete()
    session.query(ManuscriptScene).delete()
    session.query(PersonCharacterMap).delete()
    session.query(Character).delete()
    session.query(Chapter).delete()
    session.query(Reference).delete()
    session.query(PoemVersion).delete()
    session.query(MotifInstance).delete()
    session.query(ThemeInstance).delete()
    session.query(Event).delete()
    session.query(Thread).delete()
    session.query(Scene).delete()
    session.query(Entry).delete()
    session.query(Location).delete()
    session.query(Person).delete()
    session.query(Part).delete()
    session.query(ReferenceSource).delete()
    session.query(Poem).delete()
    session.query(Arc).delete()
    session.query(Motif).delete()
    session.query(Theme).delete()
    session.query(Tag).delete()
    session.query(City).delete()
    session.flush()


def _write_json_file(base_dir, entity_type: str, filename: str, data: dict) -> None:
    """
    Write a single JSON file into the export directory structure.

    Args:
        base_dir: Root export directory (contains journal/)
        entity_type: Subdirectory name under journal/
        filename: JSON filename
        data: Data dict to serialize
    """
    entity_dir = base_dir / "journal" / entity_type
    entity_dir.mkdir(parents=True, exist_ok=True)
    path = entity_dir / filename
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


# =========================================================================
# Test Classes
# =========================================================================


class TestRoundTrip:
    """Test export → clear → import → verify cycle."""

    def test_full_roundtrip(self, db_session, test_db, tmp_dir):
        """
        Full round-trip: populate → export → clear → import → verify.

        Verifies that all entity types survive the export/import cycle
        with correct counts and relationships.
        """
        # Populate
        _populate_db(db_session)

        # Export
        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        # Clear
        _clear_all_tables(db_session)
        db_session.commit()
        assert db_session.query(Entry).count() == 0
        assert db_session.query(Person).count() == 0

        # Import
        importer = JSONImporter(test_db, input_dir=tmp_dir, logger=None)
        stats = importer.import_all()

        # Verify counts
        assert stats["cities"] == 1
        assert stats["tags"] == 1
        assert stats["arcs"] == 1
        assert stats["people"] == 1
        assert stats["locations"] == 1
        assert stats["entries"] == 1
        assert stats["scenes"] == 1
        assert stats["threads"] == 1
        assert stats["events"] == 1
        assert stats["chapters"] == 1
        assert stats["characters"] == 1

    def test_roundtrip_entry_m2m(self, db_session, test_db, tmp_dir):
        """
        Round-trip preserves entry M2M relationships.
        """
        _populate_db(db_session)

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        _clear_all_tables(db_session)
        db_session.commit()

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        entry = db_session.query(Entry).first()
        assert len(entry.people) == 1
        assert entry.people[0].slug == "sofia_fernandez"
        assert len(entry.locations) == 1
        assert len(entry.tags) == 1
        assert len(entry.arcs) == 1
        assert len(entry.events) == 1

    def test_roundtrip_scene_relationships(self, db_session, test_db, tmp_dir):
        """
        Round-trip preserves scene FK and M2M relationships.
        """
        _populate_db(db_session)

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        _clear_all_tables(db_session)
        db_session.commit()

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        scene = db_session.query(Scene).first()
        assert scene.entry_id is not None
        assert len(scene.people) == 1
        assert len(scene.locations) == 1

    def test_roundtrip_manuscript_entities(self, db_session, test_db, tmp_dir):
        """
        Round-trip preserves manuscript entities and relationships.
        """
        _populate_db(db_session)

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        _clear_all_tables(db_session)
        db_session.commit()

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        # Chapter has part and poem
        chapter = db_session.query(Chapter).first()
        assert chapter.part_id is not None
        assert len(chapter.poems) == 1
        assert chapter.poems[0].title == "The Gray Fence"

        # Character has person mapping
        pcm = db_session.query(PersonCharacterMap).first()
        assert pcm is not None
        assert pcm.contribution == ContributionType.PRIMARY

        # Manuscript scene has character and source
        ms_scene = db_session.query(ManuscriptScene).first()
        assert len(ms_scene.characters) == 1
        assert ms_scene.characters[0].name == "Valeria"

        ms_source = db_session.query(ManuscriptSource).first()
        assert ms_source.source_type == SourceType.SCENE
        assert ms_source.scene_id is not None

        # Manuscript reference
        ms_ref = db_session.query(ManuscriptReference).first()
        assert ms_ref.mode == ReferenceMode.THEMATIC

    def test_roundtrip_poem_versions(self, db_session, test_db, tmp_dir):
        """
        Round-trip preserves poem versions linked to entries.
        """
        _populate_db(db_session)

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        _clear_all_tables(db_session)
        db_session.commit()

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        pv = db_session.query(PoemVersion).first()
        assert pv is not None
        assert pv.content == "The gray fence divides us still"
        assert pv.poem_id is not None
        assert pv.entry_id is not None

    def test_roundtrip_theme_motif_instances(self, db_session, test_db, tmp_dir):
        """
        Round-trip preserves theme and motif instances with descriptions.
        """
        _populate_db(db_session)

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        _clear_all_tables(db_session)
        db_session.commit()

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        ti = db_session.query(ThemeInstance).first()
        assert ti is not None
        assert ti.description == "Loss of home"

        mi = db_session.query(MotifInstance).first()
        assert mi is not None
        assert mi.description == "The mirror in the hallway"


class TestIdempotency:
    """Test that importing the same data twice produces no duplicates."""

    def test_double_import_no_duplicates(self, db_session, test_db, tmp_dir):
        """
        Importing the same JSON twice yields the same entity counts.
        """
        _populate_db(db_session)

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        _clear_all_tables(db_session)
        db_session.commit()

        # First import
        importer1 = JSONImporter(test_db, input_dir=tmp_dir)
        stats1 = importer1.import_all()

        # Second import (same data)
        importer2 = JSONImporter(test_db, input_dir=tmp_dir)
        stats2 = importer2.import_all()

        # Counts should match
        assert stats1 == stats2

        # DB should not have duplicates
        assert db_session.query(Entry).count() == 1
        assert db_session.query(Person).count() == 1
        assert db_session.query(City).count() == 1
        assert db_session.query(Chapter).count() == 1
        assert db_session.query(Character).count() == 1

    def test_import_over_existing_data(self, db_session, test_db, tmp_dir):
        """
        Import over an existing populated DB updates without duplicating.
        """
        _populate_db(db_session)

        exporter = JSONExporter(test_db, output_dir=tmp_dir)
        exporter.export_all()

        # Import over the existing DB (without clearing)
        importer = JSONImporter(test_db, input_dir=tmp_dir)
        stats = importer.import_all()

        # Should still have 1 of each
        assert db_session.query(Entry).count() == 1
        assert db_session.query(Person).count() == 1


class TestPartialImport:
    """Test handling of missing or partial export directories."""

    def test_empty_directory_returns_zero_stats(self, test_db, tmp_dir):
        """
        Import from empty directory returns zero-count stats.
        """
        importer = JSONImporter(test_db, input_dir=tmp_dir)
        stats = importer.import_all()

        assert all(v == 0 for v in stats.values())

    def test_missing_entity_type_skipped(self, db_session, test_db, tmp_dir):
        """
        Missing entity type directories are silently skipped.
        """
        # Only write cities JSON
        _write_json_file(
            tmp_dir, "cities", "montreal.json",
            {"name": "Montreal", "country": "Canada"},
        )

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        stats = importer.import_all()

        assert stats["cities"] == 1
        assert stats.get("entries", 0) == 0
        assert db_session.query(City).count() == 1

    def test_corrupted_json_skipped(self, db_session, test_db, tmp_dir):
        """
        Corrupted JSON files are skipped without crashing.
        """
        entity_dir = tmp_dir / "journal" / "cities"
        entity_dir.mkdir(parents=True)

        # Valid file
        (entity_dir / "montreal.json").write_text(
            json.dumps({"name": "Montreal", "country": "Canada"})
        )
        # Corrupted file
        (entity_dir / "bad.json").write_text("{{not valid json")

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        stats = importer.import_all()

        assert stats["cities"] == 1  # Only valid file imported


class TestIndividualImports:
    """Test individual entity type imports with natural key resolution."""

    def test_import_city(self, db_session, test_db, tmp_dir):
        """Import creates city from JSON."""
        _write_json_file(
            tmp_dir, "cities", "montreal.json",
            {"name": "Montreal", "country": "Canada"},
        )

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        city = db_session.query(City).first()
        assert city.name == "Montreal"
        assert city.country == "Canada"

    def test_import_person_with_relation_type(self, db_session, test_db, tmp_dir):
        """Import creates person with enum relation type."""
        _write_json_file(
            tmp_dir, "people", "sofia_fernandez.json",
            {
                "slug": "sofia_fernandez",
                "name": "Sofia",
                "lastname": "Fernandez",
                "relation_type": "self",
            },
        )

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        person = db_session.query(Person).first()
        assert person.name == "Sofia"
        assert person.relation_type == RelationType.SELF

    def test_import_location_resolves_city(self, db_session, test_db, tmp_dir):
        """Import resolves location city FK from city name."""
        _write_json_file(
            tmp_dir, "cities", "montreal.json",
            {"name": "Montreal", "country": "Canada"},
        )
        _write_json_file(
            tmp_dir, "locations", "cafe.json",
            {"name": "Café X", "city": "Montreal"},
        )

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        loc = db_session.query(Location).first()
        assert loc.name == "Café X"
        city = db_session.query(City).first()
        assert loc.city_id == city.id

    def test_import_chapter_with_part(self, db_session, test_db, tmp_dir):
        """Import creates chapter resolving part FK."""
        _write_json_file(
            tmp_dir, "parts", "the-archive.json",
            {"number": 1, "title": "The Archive"},
        )
        _write_json_file(
            tmp_dir, "chapters", "espresso-and-silence.json",
            {
                "title": "Espresso and Silence",
                "number": 1,
                "type": "prose",
                "status": "draft",
                "part": 1,
            },
        )

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        chapter = db_session.query(Chapter).first()
        assert chapter.title == "Espresso and Silence"
        assert chapter.type == ChapterType.PROSE
        assert chapter.part_id is not None

    def test_import_manuscript_scene_with_characters(
        self, db_session, test_db, tmp_dir
    ):
        """Import creates manuscript scene resolving chapter FK and character M2M."""
        _write_json_file(
            tmp_dir, "chapters", "chapter.json",
            {
                "title": "Chapter One",
                "number": 1,
                "type": "prose",
                "status": "draft",
            },
        )
        _write_json_file(
            tmp_dir, "characters", "valeria.json",
            {"name": "Valeria", "role": "Protagonist"},
        )
        _write_json_file(
            tmp_dir, "manuscript_scenes", "the-pause.json",
            {
                "name": "The Pause",
                "chapter": "Chapter One",
                "origin": "journaled",
                "status": "draft",
                "characters": ["Valeria"],
            },
        )

        importer = JSONImporter(test_db, input_dir=tmp_dir)
        importer.import_all()

        ms = db_session.query(ManuscriptScene).first()
        assert ms.name == "The Pause"
        assert len(ms.characters) == 1
        assert ms.characters[0].name == "Valeria"
