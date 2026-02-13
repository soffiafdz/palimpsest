#!/usr/bin/env python3
"""
test_metadata.py
----------------
Tests for YAML metadata export, validation, and import.

Covers MetadataExporter, MetadataValidator, MetadataImporter, and
the MetadataSchema field definitions. Uses the same DB fixtures
as the wiki exporter tests.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path

# --- Third-party imports ---
import pytest
import yaml

# --- Local imports ---
from dev.database.models.analysis import Arc
from dev.database.models.core import Entry
from dev.database.models.entities import Person
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    ContributionType,
    RelationType,
    SceneOrigin,
    SceneStatus,
)
from dev.database.models.geography import City, Location
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptScene,
    Part,
    PersonCharacterMap,
)
from dev.wiki.metadata import (
    MetadataExporter,
    MetadataImporter,
    MetadataSchema,
    MetadataValidator,
)


# ==================== Fixtures ====================

@pytest.fixture
def metadata_output(tmp_path):
    """Temporary metadata output directory."""
    return tmp_path / "metadata"


@pytest.fixture
def populated_metadata_db(db_session):
    """
    Create test entities for metadata export/import testing.

    Includes city, locations, people, entries, arcs, and
    manuscript entities (part, chapters, characters, scenes).
    """
    # City + Locations
    city = City(name="Montreal", country="Canada")
    db_session.add(city)
    db_session.flush()

    cafe = Location(name="Café Olimpico", city_id=city.id)
    home = Location(name="Home", city_id=city.id)
    db_session.add_all([cafe, home])
    db_session.flush()

    # People
    sofia = Person(
        name="Sofia", lastname="Fernandez",
        slug="sofia_fernandez", relation_type=RelationType.SELF,
    )
    clara = Person(
        name="Clara", lastname="Dupont",
        slug="clara_dupont", relation_type=RelationType.ROMANTIC,
    )
    db_session.add_all([sofia, clara])
    db_session.flush()

    # Entry (needed for arcs)
    entry = Entry(
        date=date(2024, 11, 8),
        file_path="2024/2024-11-08.md",
        word_count=1000,
    )
    db_session.add(entry)
    db_session.flush()

    # Arc
    arc = Arc(name="The Long Wanting", description="A story of longing.")
    db_session.add(arc)
    db_session.flush()
    entry.arcs.append(arc)

    # Part + Chapter
    part = Part(number=1, title="The Archive")
    db_session.add(part)
    db_session.flush()

    chapter = Chapter(
        title="Espresso and Silence",
        number=1,
        part_id=part.id,
        type=ChapterType.PROSE,
        status=ChapterStatus.DRAFT,
    )
    db_session.add(chapter)
    db_session.flush()

    # Character
    character = Character(
        name="Valeria",
        role="Protagonist",
        is_narrator=True,
        description="The narrator, restless and observant.",
    )
    db_session.add(character)
    db_session.flush()

    pcm = PersonCharacterMap(
        person_id=sofia.id,
        character_id=character.id,
        contribution=ContributionType.PRIMARY,
    )
    db_session.add(pcm)

    # ManuscriptScene
    ms_scene = ManuscriptScene(
        name="The Espresso Pause",
        description="Valeria watches Lena across the table.",
        chapter_id=chapter.id,
        origin=SceneOrigin.JOURNALED,
        status=SceneStatus.DRAFT,
    )
    db_session.add(ms_scene)

    db_session.commit()
    return db_session


# ==================== Schema Tests ====================

class TestMetadataSchema:
    """Tests for MetadataSchema field definitions."""

    def test_person_fields(self):
        """Person schema has expected fields."""
        fields = MetadataSchema.get_fields("people")
        names = [f.name for f in fields]
        assert "name" in names
        assert "relation_type" in names

    def test_chapter_fields(self):
        """Chapter schema has enum-constrained fields."""
        fields = MetadataSchema.get_fields("chapters")
        type_field = next(f for f in fields if f.name == "type")
        assert "prose" in type_field.enum_values
        assert "vignette" in type_field.enum_values

    def test_unknown_type_raises(self):
        """Unknown entity type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown entity type"):
            MetadataSchema.get_fields("unknown")


# ==================== Exporter Tests ====================

class TestMetadataExporter:
    """Tests for MetadataExporter."""

    def test_export_people(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export creates per-person YAML files."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="people")

        people_dir = metadata_output / "people"
        assert people_dir.is_dir()

        # Check that files exist
        files = list(people_dir.glob("*.yaml"))
        assert len(files) == 2  # sofia, clara

        # Check content
        clara_file = people_dir / "clara_dupont.yaml"
        assert clara_file.is_file()
        data = yaml.safe_load(clara_file.read_text())
        assert data["name"] == "Clara"
        assert data["relation_type"] == "romantic"

    def test_export_cities(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export creates single cities.yaml file."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="cities")

        cities_file = metadata_output / "cities.yaml"
        assert cities_file.is_file()
        data = yaml.safe_load(cities_file.read_text())
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "Montreal"
        assert data[0]["country"] == "Canada"

    def test_export_arcs(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export creates single arcs.yaml file."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="arcs")

        arcs_file = metadata_output / "arcs.yaml"
        assert arcs_file.is_file()
        data = yaml.safe_load(arcs_file.read_text())
        assert isinstance(data, list)
        assert data[0]["name"] == "The Long Wanting"

    def test_export_chapters(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export creates per-chapter YAML files."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="chapters")

        chapters_dir = metadata_output / "manuscript" / "chapters"
        files = list(chapters_dir.glob("*.yaml"))
        assert len(files) == 1

        data = yaml.safe_load(files[0].read_text())
        assert data["title"] == "Espresso and Silence"
        assert data["type"] == "prose"
        assert data["status"] == "draft"

    def test_export_characters(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export creates per-character YAML with based_on mappings."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="characters")

        chars_dir = metadata_output / "manuscript" / "characters"
        files = list(chars_dir.glob("*.yaml"))
        assert len(files) == 1

        data = yaml.safe_load(files[0].read_text())
        assert data["name"] == "Valeria"
        assert data["is_narrator"] is True
        assert data["based_on"] is not None
        assert len(data["based_on"]) == 1
        assert data["based_on"][0]["contribution"] == "primary"

    def test_export_scenes(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export creates per-scene YAML files."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="scenes")

        scenes_dir = metadata_output / "manuscript" / "scenes"
        files = list(scenes_dir.glob("*.yaml"))
        assert len(files) == 1

        data = yaml.safe_load(files[0].read_text())
        assert data["name"] == "The Espresso Pause"
        assert data["origin"] == "journaled"
        assert data["chapter"] == "Espresso and Silence"

    def test_export_all(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export all writes files for every entity type."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all()

        assert (metadata_output / "people").is_dir()
        assert (metadata_output / "locations").is_dir()
        assert (metadata_output / "cities.yaml").is_file()
        assert (metadata_output / "arcs.yaml").is_file()
        assert (metadata_output / "manuscript" / "chapters").is_dir()
        assert (metadata_output / "manuscript" / "characters").is_dir()
        assert (metadata_output / "manuscript" / "scenes").is_dir()

    def test_change_detection(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Second export reports 0 changes for unchanged data."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="people")

        exporter2 = MetadataExporter(test_db, output_dir=metadata_output)
        exporter2.export_all(entity_type="people")

        assert exporter2.stats.get("people_changed", 0) == 0

    def test_list_entities(
        self, test_db, populated_metadata_db
    ):
        """list_entities returns sorted entity names."""
        exporter = MetadataExporter(test_db)
        names = exporter.list_entities("people")
        assert len(names) == 2
        assert names == sorted(names)

    def test_list_entities_chapters(
        self, test_db, populated_metadata_db
    ):
        """list_entities returns chapter titles."""
        exporter = MetadataExporter(test_db)
        names = exporter.list_entities("chapters")
        assert "Espresso and Silence" in names

    def test_list_entities_unknown_type(self, test_db):
        """Unknown entity type raises ValueError."""
        exporter = MetadataExporter(test_db)
        with pytest.raises(ValueError):
            exporter.list_entities("unknown")


# ==================== Validator Tests ====================

class TestMetadataValidator:
    """Tests for MetadataValidator."""

    def test_valid_person_yaml(self, tmp_path):
        """Valid person YAML produces no diagnostics."""
        yaml_file = tmp_path / "people" / "test.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text(
            "name: Clara\nlastname: Dupont\nrelation_type: romantic\n"
        )

        validator = MetadataValidator()
        diagnostics = validator.validate_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 0

    def test_missing_required_field(self, tmp_path):
        """Missing required field produces error diagnostic."""
        yaml_file = tmp_path / "people" / "test.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text("lastname: Dupont\n")

        validator = MetadataValidator()
        diagnostics = validator.validate_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 1
        assert errors[0].code == "MISSING_REQUIRED_FIELD"

    def test_invalid_enum_value(self, tmp_path):
        """Invalid enum value produces error diagnostic."""
        yaml_file = tmp_path / "people" / "test.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text(
            "name: Clara\nrelation_type: enemy\n"
        )

        validator = MetadataValidator()
        diagnostics = validator.validate_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 1
        assert errors[0].code == "INVALID_ENUM_VALUE"

    def test_invalid_yaml_syntax(self, tmp_path):
        """Malformed YAML produces parse error diagnostic."""
        yaml_file = tmp_path / "people" / "test.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text("name: [unclosed bracket")

        validator = MetadataValidator()
        diagnostics = validator.validate_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 1
        assert errors[0].code == "INVALID_YAML"

    def test_empty_yaml_file(self, tmp_path):
        """Empty YAML file produces error diagnostic."""
        yaml_file = tmp_path / "people" / "test.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text("")

        validator = MetadataValidator()
        diagnostics = validator.validate_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 1
        assert errors[0].code == "EMPTY_FILE"

    def test_chapter_enum_validation(self, tmp_path):
        """Chapter type and status are validated against enums."""
        yaml_file = tmp_path / "chapters" / "test.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text(
            "title: Test\ntype: invalid_type\nstatus: draft\n"
        )

        validator = MetadataValidator()
        diagnostics = validator.validate_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert any("INVALID_ENUM_VALUE" == e.code for e in errors)

    def test_cities_list_validation(self, tmp_path):
        """Cities (list format) validates each entry."""
        yaml_file = tmp_path / "cities.yaml"
        yaml_file.write_text(
            "- name: Montreal\n  country: Canada\n"
            "- country: France\n"  # Missing required name
        )

        validator = MetadataValidator()
        diagnostics = validator.validate_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) == 1
        assert "MISSING_REQUIRED_FIELD" == errors[0].code


# ==================== Importer Tests ====================

class TestMetadataImporter:
    """Tests for MetadataImporter."""

    def test_import_person_updates_db(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Import updates person relation_type in DB."""
        # Export first
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="people")

        # Modify YAML
        clara_file = metadata_output / "people" / "clara_dupont.yaml"
        data = yaml.safe_load(clara_file.read_text())
        data["relation_type"] = "friend"
        clara_file.write_text(yaml.dump(data, allow_unicode=True))

        # Import
        importer = MetadataImporter(test_db, input_dir=metadata_output)
        diagnostics = importer.import_file(clara_file)
        assert len(diagnostics) == 0

        # Verify DB
        with test_db.session_scope() as session:
            clara = session.query(Person).filter(
                Person.slug == "clara_dupont"
            ).first()
            assert clara.relation_type == RelationType.FRIEND

    def test_import_chapter_updates_db(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Import updates chapter type and status in DB."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="chapters")

        # Modify YAML
        chapter_file = list(
            (metadata_output / "manuscript" / "chapters").glob("*.yaml")
        )[0]
        data = yaml.safe_load(chapter_file.read_text())
        data["type"] = "vignette"
        data["status"] = "revised"
        chapter_file.write_text(yaml.dump(data, allow_unicode=True))

        # Import
        importer = MetadataImporter(test_db, input_dir=metadata_output)
        diagnostics = importer.import_file(chapter_file)
        assert len(diagnostics) == 0

        # Verify DB
        with test_db.session_scope() as session:
            chapter = session.query(Chapter).filter(
                Chapter.title == "Espresso and Silence"
            ).first()
            assert chapter.type == ChapterType.VIGNETTE
            assert chapter.status == ChapterStatus.REVISED

    def test_import_invalid_file_returns_diagnostics(
        self, test_db, tmp_path
    ):
        """Import of invalid YAML returns error diagnostics."""
        yaml_file = tmp_path / "people" / "bad.yaml"
        yaml_file.parent.mkdir(parents=True)
        yaml_file.write_text("relation_type: enemy\n")  # Missing name

        importer = MetadataImporter(test_db, input_dir=tmp_path)
        diagnostics = importer.import_file(yaml_file)
        errors = [d for d in diagnostics if d.severity == "error"]
        assert len(errors) >= 1

    def test_roundtrip_no_changes(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """Export → import → export produces identical YAML."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="people")

        # Read first export
        clara_file = metadata_output / "people" / "clara_dupont.yaml"
        first_content = clara_file.read_text()

        # Import (no changes)
        importer = MetadataImporter(test_db, input_dir=metadata_output)
        importer.import_file(clara_file)

        # Re-export
        exporter2 = MetadataExporter(test_db, output_dir=metadata_output)
        exporter2.export_all(entity_type="people")

        second_content = clara_file.read_text()
        assert first_content == second_content

    def test_import_all(
        self, test_db, populated_metadata_db, metadata_output
    ):
        """import_all processes all files of a type."""
        exporter = MetadataExporter(test_db, output_dir=metadata_output)
        exporter.export_all(entity_type="people")

        importer = MetadataImporter(test_db, input_dir=metadata_output)
        stats = importer.import_all(entity_type="people")
        assert stats["imported"] == 2
        assert stats["errors"] == 0
