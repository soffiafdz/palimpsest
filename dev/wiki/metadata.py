#!/usr/bin/env python3
"""
metadata.py
-----------
YAML metadata file management for entity editing.

Provides export, validation, and import of structured YAML metadata
files that enable editing entity properties via the Neovim floating
window workflow. Each entity type has a defined schema of editable
fields and a corresponding YAML file layout.

File Layout:
    data/metadata/people/{slug}.yaml       - Per-entity
    data/metadata/locations/{slug}.yaml    - Per-entity
    data/metadata/cities.yaml              - Single file
    data/metadata/arcs.yaml                - Single file
    data/metadata/manuscript/parts.yaml    - Single file
    data/metadata/manuscript/chapters/{slug}.yaml   - Per-entity
    data/metadata/manuscript/characters/{slug}.yaml - Per-entity
    data/metadata/manuscript/scenes/{slug}.yaml     - Per-entity

Key Features:
    - Schema-driven field definitions per entity type
    - Export: DB → YAML files with change detection
    - Validate: Check YAML against schema and enum constraints
    - Import: YAML → DB with validation gate
    - Entity listing for autocomplete support

Usage:
    from dev.wiki.metadata import MetadataExporter, MetadataValidator

    exporter = MetadataExporter(db)
    exporter.export_all()                    # Export all types
    exporter.export_people()                 # Export people only
    exporter.list_entities("people")         # For autocomplete

    validator = MetadataValidator()
    diagnostics = validator.validate_file(Path("data/metadata/people/clara.yaml"))

Dependencies:
    - PalimpsestDB for database access
    - PyYAML for YAML serialization
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type

# --- Third-party imports ---
import yaml
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import (
    MANUSCRIPT_CHAPTERS_DIR,
    MANUSCRIPT_CHARACTERS_DIR,
    MANUSCRIPT_YAML_DIR,
    METADATA_DIR,
)
from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Arc,
    City,
    Location,
    Person,
)
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    ContributionType,
    RelationType,
    SceneOrigin,
    SceneStatus,
)
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptScene,
    Part,
)
from dev.utils.slugify import slugify
from dev.wiki.validator import Diagnostic


# ==================== Path Constants ====================

PEOPLE_YAML_DIR = METADATA_DIR / "people"
LOCATIONS_YAML_DIR = METADATA_DIR / "locations"
CITIES_YAML_PATH = METADATA_DIR / "cities.yaml"
ARCS_YAML_PATH = METADATA_DIR / "arcs.yaml"
MANUSCRIPT_PARTS_PATH = MANUSCRIPT_YAML_DIR / "parts.yaml"
MANUSCRIPT_SCENES_DIR = MANUSCRIPT_YAML_DIR / "scenes"


# ==================== Schema ====================

@dataclass
class FieldSpec:
    """
    Specification for an editable metadata field.

    Attributes:
        name: Field name as it appears in YAML
        field_type: Python type (str, int, bool)
        required: Whether the field must be present
        enum_values: Valid string values if constrained
    """

    name: str
    field_type: type = str
    required: bool = False
    enum_values: Optional[List[str]] = None


class MetadataSchema:
    """
    Editable field definitions and validation rules per entity type.

    Centralizes the mapping from entity types to their YAML-editable
    fields, valid enum values, and structural constraints.
    """

    PERSON_FIELDS: List[FieldSpec] = [
        FieldSpec("name", str, required=True),
        FieldSpec("lastname", str),
        FieldSpec("relation_type", str,
                  enum_values=RelationType.choices()),
    ]

    LOCATION_FIELDS: List[FieldSpec] = [
        FieldSpec("name", str, required=True),
        FieldSpec("city", str, required=True),
    ]

    CITY_FIELDS: List[FieldSpec] = [
        FieldSpec("name", str, required=True),
        FieldSpec("country", str),
    ]

    ARC_FIELDS: List[FieldSpec] = [
        FieldSpec("name", str, required=True),
        FieldSpec("description", str),
    ]

    CHAPTER_FIELDS: List[FieldSpec] = [
        FieldSpec("title", str, required=True),
        FieldSpec("number", int),
        FieldSpec("type", str, required=True,
                  enum_values=ChapterType.choices()),
        FieldSpec("status", str, required=True,
                  enum_values=ChapterStatus.choices()),
        FieldSpec("part", str),
    ]

    CHARACTER_FIELDS: List[FieldSpec] = [
        FieldSpec("name", str, required=True),
        FieldSpec("role", str),
        FieldSpec("is_narrator", bool),
        FieldSpec("description", str),
    ]

    SCENE_FIELDS: List[FieldSpec] = [
        FieldSpec("name", str, required=True),
        FieldSpec("chapter", str),
        FieldSpec("origin", str, required=True,
                  enum_values=SceneOrigin.choices()),
        FieldSpec("status", str, required=True,
                  enum_values=SceneStatus.choices()),
        FieldSpec("description", str),
    ]

    @classmethod
    def get_fields(cls, entity_type: str) -> List[FieldSpec]:
        """
        Get field specifications for an entity type.

        Args:
            entity_type: Entity type key (people, locations, cities, arcs,
                chapters, characters, scenes)

        Returns:
            List of FieldSpec instances

        Raises:
            ValueError: If entity_type is not recognized
        """
        mapping = {
            "people": cls.PERSON_FIELDS,
            "locations": cls.LOCATION_FIELDS,
            "cities": cls.CITY_FIELDS,
            "arcs": cls.ARC_FIELDS,
            "chapters": cls.CHAPTER_FIELDS,
            "characters": cls.CHARACTER_FIELDS,
            "scenes": cls.SCENE_FIELDS,
        }
        if entity_type not in mapping:
            raise ValueError(
                f"Unknown entity type: {entity_type}. "
                f"Valid types: {list(mapping.keys())}"
            )
        return mapping[entity_type]


# ==================== Exporter ====================

class MetadataExporter:
    """
    Exports database entities to structured YAML metadata files.

    Writes per-entity YAML files for people, locations, chapters,
    characters, and manuscript scenes. Writes single-file YAML for
    cities and arcs. Supports change detection to avoid unnecessary
    writes.

    Attributes:
        db: PalimpsestDB instance
        output_dir: Root metadata output directory
        logger: Optional logger
        stats: Export statistics
    """

    def __init__(
        self,
        db: PalimpsestDB,
        output_dir: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ) -> None:
        """
        Initialize the metadata exporter.

        Args:
            db: Database manager instance
            output_dir: Metadata output directory (defaults to METADATA_DIR)
            logger: Optional logger for progress tracking
        """
        self.db = db
        self.output_dir = output_dir or METADATA_DIR
        self.logger = logger
        self.stats: Dict[str, int] = {}

    def export_all(self, entity_type: Optional[str] = None) -> None:
        """
        Export all entity types to YAML files.

        Args:
            entity_type: Optional filter to export only one type
        """
        safe_logger(self.logger).log_info("Starting metadata export")

        with self.db.session_scope() as session:
            if not entity_type or entity_type == "people":
                self.export_people(session)
            if not entity_type or entity_type == "locations":
                self.export_locations(session)
            if not entity_type or entity_type == "cities":
                self.export_cities(session)
            if not entity_type or entity_type == "arcs":
                self.export_arcs(session)
            if not entity_type or entity_type == "chapters":
                self.export_chapters(session)
            if not entity_type or entity_type == "characters":
                self.export_characters(session)
            if not entity_type or entity_type == "scenes":
                self.export_scenes(session)

        safe_logger(self.logger).log_info(
            f"Metadata export complete: {self.stats}"
        )

    def export_people(self, session: Optional[Session] = None) -> None:
        """
        Export people to per-entity YAML files.

        Args:
            session: Optional SQLAlchemy session (opens one if not provided)
        """
        def _export(sess: Session) -> None:
            people_dir = self.output_dir / "people"
            people_dir.mkdir(parents=True, exist_ok=True)

            people = sess.query(Person).all()
            count = 0
            for person in people:
                data = {
                    "name": person.name,
                    "lastname": person.lastname,
                    "slug": person.slug,
                    "relation_type": (
                        person.relation_type.value
                        if person.relation_type else None
                    ),
                }
                filename = f"{person.slug}.yaml"
                if self._write_yaml(people_dir / filename, data):
                    count += 1
            self.stats["people"] = len(people)
            self.stats["people_changed"] = count

        if session:
            _export(session)
        else:
            with self.db.session_scope() as sess:
                _export(sess)

    def export_locations(self, session: Optional[Session] = None) -> None:
        """
        Export locations to per-entity YAML files.

        Args:
            session: Optional SQLAlchemy session
        """
        def _export(sess: Session) -> None:
            locations_dir = self.output_dir / "locations"
            locations_dir.mkdir(parents=True, exist_ok=True)

            locations = sess.query(Location).all()
            count = 0
            for location in locations:
                data = {
                    "name": location.name,
                    "city": location.city.name,
                }
                city_slug = slugify(location.city.name)
                loc_slug = slugify(location.name)
                sub_dir = locations_dir / city_slug
                sub_dir.mkdir(parents=True, exist_ok=True)
                if self._write_yaml(sub_dir / f"{loc_slug}.yaml", data):
                    count += 1
            self.stats["locations"] = len(locations)
            self.stats["locations_changed"] = count

        if session:
            _export(session)
        else:
            with self.db.session_scope() as sess:
                _export(sess)

    def export_cities(self, session: Optional[Session] = None) -> None:
        """
        Export cities to a single YAML file.

        Args:
            session: Optional SQLAlchemy session
        """
        def _export(sess: Session) -> None:
            cities = sess.query(City).all()
            data = [
                {
                    "name": city.name,
                    "country": city.country,
                }
                for city in cities
            ]
            path = self.output_dir / "cities.yaml"
            self._write_yaml(path, data)
            self.stats["cities"] = len(cities)

        if session:
            _export(session)
        else:
            with self.db.session_scope() as sess:
                _export(sess)

    def export_arcs(self, session: Optional[Session] = None) -> None:
        """
        Export arcs to a single YAML file.

        Args:
            session: Optional SQLAlchemy session
        """
        def _export(sess: Session) -> None:
            arcs = sess.query(Arc).all()
            data = [
                {
                    "name": arc.name,
                    "description": arc.description,
                }
                for arc in arcs
            ]
            path = self.output_dir / "arcs.yaml"
            self._write_yaml(path, data)
            self.stats["arcs"] = len(arcs)

        if session:
            _export(session)
        else:
            with self.db.session_scope() as sess:
                _export(sess)

    def export_chapters(self, session: Optional[Session] = None) -> None:
        """
        Export chapters to per-entity YAML files.

        Args:
            session: Optional SQLAlchemy session
        """
        def _export(sess: Session) -> None:
            chapters_dir = self.output_dir / "manuscript" / "chapters"
            chapters_dir.mkdir(parents=True, exist_ok=True)

            chapters = sess.query(Chapter).all()
            count = 0
            for chapter in chapters:
                data = {
                    "title": chapter.title,
                    "number": chapter.number,
                    "type": chapter.type.value,
                    "status": chapter.status.value,
                    "part": (
                        chapter.part.display_name
                        if chapter.part else None
                    ),
                }
                filename = f"{slugify(chapter.title)}.yaml"
                if self._write_yaml(chapters_dir / filename, data):
                    count += 1
            self.stats["chapters"] = len(chapters)
            self.stats["chapters_changed"] = count

        if session:
            _export(session)
        else:
            with self.db.session_scope() as sess:
                _export(sess)

    def export_characters(self, session: Optional[Session] = None) -> None:
        """
        Export characters to per-entity YAML files.

        Args:
            session: Optional SQLAlchemy session
        """
        def _export(sess: Session) -> None:
            characters_dir = self.output_dir / "manuscript" / "characters"
            characters_dir.mkdir(parents=True, exist_ok=True)

            characters = sess.query(Character).all()
            count = 0
            for character in characters:
                based_on = []
                for mapping in character.person_mappings:
                    based_on.append({
                        "person": mapping.person.display_name,
                        "contribution": mapping.contribution.value,
                    })

                data = {
                    "name": character.name,
                    "role": character.role,
                    "is_narrator": character.is_narrator,
                    "description": character.description,
                    "based_on": based_on if based_on else None,
                }
                filename = f"{slugify(character.name)}.yaml"
                if self._write_yaml(characters_dir / filename, data):
                    count += 1
            self.stats["characters"] = len(characters)
            self.stats["characters_changed"] = count

        if session:
            _export(session)
        else:
            with self.db.session_scope() as sess:
                _export(sess)

    def export_scenes(self, session: Optional[Session] = None) -> None:
        """
        Export manuscript scenes to per-entity YAML files.

        Args:
            session: Optional SQLAlchemy session
        """
        def _export(sess: Session) -> None:
            scenes_dir = self.output_dir / "manuscript" / "scenes"
            scenes_dir.mkdir(parents=True, exist_ok=True)

            ms_scenes = sess.query(ManuscriptScene).all()
            count = 0
            for ms_scene in ms_scenes:
                data = {
                    "name": ms_scene.name,
                    "chapter": (
                        ms_scene.chapter.title
                        if ms_scene.chapter else None
                    ),
                    "origin": ms_scene.origin.value,
                    "status": ms_scene.status.value,
                    "description": ms_scene.description,
                }
                filename = f"{slugify(ms_scene.name)}.yaml"
                if self._write_yaml(scenes_dir / filename, data):
                    count += 1
            self.stats["scenes"] = len(ms_scenes)
            self.stats["scenes_changed"] = count

        if session:
            _export(session)
        else:
            with self.db.session_scope() as sess:
                _export(sess)

    def list_entities(
        self, entity_type: str, format: str = "names"
    ) -> List[str]:
        """
        List entity names for autocomplete support.

        Args:
            entity_type: Entity type key
            format: Output format ("names" or "json")

        Returns:
            List of entity names/titles
        """
        model_map = {
            "people": (Person, "display_name"),
            "locations": (Location, "name"),
            "cities": (City, "name"),
            "arcs": (Arc, "name"),
            "chapters": (Chapter, "title"),
            "characters": (Character, "name"),
            "scenes": (ManuscriptScene, "name"),
        }

        if entity_type not in model_map:
            raise ValueError(f"Unknown entity type: {entity_type}")

        model, attr = model_map[entity_type]
        names: List[str] = []

        with self.db.session_scope() as session:
            entities = session.query(model).all()
            for entity in entities:
                names.append(getattr(entity, attr))

        return sorted(names)

    def _write_yaml(self, path: Path, data: Any) -> bool:
        """
        Write YAML file with change detection.

        Only writes if content differs from existing file.

        Args:
            path: Output file path
            data: Data to serialize as YAML

        Returns:
            True if file was written (new or changed), False if unchanged
        """
        # Remove None values for cleaner YAML
        if isinstance(data, dict):
            data = {k: v for k, v in data.items() if v is not None}

        content = yaml.dump(
            data, default_flow_style=False, allow_unicode=True, sort_keys=False
        )

        if path.exists():
            existing = path.read_text(encoding="utf-8")
            if existing == content:
                return False

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return True


# ==================== Validator ====================

class MetadataValidator:
    """
    Validates YAML metadata files against entity schemas.

    Checks for required fields, valid enum values, and structural
    correctness. Returns diagnostics compatible with the wiki
    validator format.

    Attributes:
        _schema: MetadataSchema class reference
    """

    def validate_file(
        self, path: Path, entity_type: Optional[str] = None
    ) -> List[Diagnostic]:
        """
        Validate a single YAML metadata file.

        Args:
            path: Path to the YAML file
            entity_type: Entity type (auto-detected from path if None)

        Returns:
            List of Diagnostic instances
        """
        diagnostics: List[Diagnostic] = []
        file_str = str(path)

        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except yaml.YAMLError as e:
            diagnostics.append(Diagnostic(
                file=file_str, line=1, col=1,
                end_line=1, end_col=1,
                severity="error",
                code="INVALID_YAML",
                message=f"YAML parse error: {e}",
            ))
            return diagnostics

        if data is None:
            diagnostics.append(Diagnostic(
                file=file_str, line=1, col=1,
                end_line=1, end_col=1,
                severity="error",
                code="EMPTY_FILE",
                message="YAML file is empty",
            ))
            return diagnostics

        # Auto-detect entity type from path
        if entity_type is None:
            entity_type = self._detect_entity_type(path)

        if entity_type is None:
            diagnostics.append(Diagnostic(
                file=file_str, line=1, col=1,
                end_line=1, end_col=1,
                severity="warning",
                code="UNKNOWN_TYPE",
                message="Cannot determine entity type from path",
            ))
            return diagnostics

        # Handle single-file formats (cities, arcs, parts)
        if isinstance(data, list):
            for i, item in enumerate(data):
                diagnostics.extend(
                    self._validate_entity(item, entity_type, file_str, i + 1)
                )
        else:
            diagnostics.extend(
                self._validate_entity(data, entity_type, file_str)
            )

        return diagnostics

    def _validate_entity(
        self,
        data: Dict[str, Any],
        entity_type: str,
        file_path: str,
        list_index: Optional[int] = None,
    ) -> List[Diagnostic]:
        """
        Validate a single entity dict against its schema.

        Args:
            data: Entity data dict
            entity_type: Entity type key
            file_path: File path for diagnostics
            list_index: Index in list if from a list file

        Returns:
            List of diagnostics
        """
        diagnostics: List[Diagnostic] = []
        prefix = f"[{list_index}] " if list_index else ""

        try:
            fields = MetadataSchema.get_fields(entity_type)
        except ValueError:
            return diagnostics

        for field_spec in fields:
            value = data.get(field_spec.name)

            # Check required fields
            if field_spec.required and value is None:
                diagnostics.append(Diagnostic(
                    file=file_path, line=1, col=1,
                    end_line=1, end_col=1,
                    severity="error",
                    code="MISSING_REQUIRED_FIELD",
                    message=(
                        f"{prefix}Required field missing: {field_spec.name}"
                    ),
                ))
                continue

            # Check enum values
            if (
                value is not None
                and field_spec.enum_values
                and str(value) not in field_spec.enum_values
            ):
                diagnostics.append(Diagnostic(
                    file=file_path, line=1, col=1,
                    end_line=1, end_col=1,
                    severity="error",
                    code="INVALID_ENUM_VALUE",
                    message=(
                        f"{prefix}Invalid value for {field_spec.name}: "
                        f"'{value}'. "
                        f"Valid values: {field_spec.enum_values}"
                    ),
                ))

            # Check type
            if (
                value is not None
                and field_spec.field_type != str
                and not isinstance(value, field_spec.field_type)
            ):
                diagnostics.append(Diagnostic(
                    file=file_path, line=1, col=1,
                    end_line=1, end_col=1,
                    severity="error",
                    code="INVALID_TYPE",
                    message=(
                        f"{prefix}Field {field_spec.name} should be "
                        f"{field_spec.field_type.__name__}, "
                        f"got {type(value).__name__}"
                    ),
                ))

        return diagnostics

    def _detect_entity_type(self, path: Path) -> Optional[str]:
        """
        Detect entity type from file path.

        Args:
            path: File path to analyze

        Returns:
            Entity type key or None if unrecognized
        """
        path_str = str(path)

        if "/people/" in path_str:
            return "people"
        elif "/locations/" in path_str:
            return "locations"
        elif path_str.endswith("cities.yaml"):
            return "cities"
        elif path_str.endswith("arcs.yaml"):
            return "arcs"
        elif "/chapters/" in path_str:
            return "chapters"
        elif "/characters/" in path_str:
            return "characters"
        elif "/scenes/" in path_str:
            return "scenes"
        elif path_str.endswith("parts.yaml"):
            return "chapters"  # Parts use similar schema

        return None


# ==================== Importer ====================

class MetadataImporter:
    """
    Imports YAML metadata files into the database.

    Validates files before import and applies changes within
    a single transaction. Supports per-file and batch import.

    Attributes:
        db: PalimpsestDB instance
        validator: MetadataValidator for pre-import checks
        logger: Optional logger
        stats: Import statistics
    """

    def __init__(
        self,
        db: PalimpsestDB,
        input_dir: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ) -> None:
        """
        Initialize the metadata importer.

        Args:
            db: Database manager instance
            input_dir: Metadata directory (defaults to METADATA_DIR)
            logger: Optional logger
        """
        self.db = db
        self.input_dir = input_dir or METADATA_DIR
        self.validator = MetadataValidator()
        self.logger = logger
        self.stats: Dict[str, int] = {}

    def import_file(self, path: Path) -> List[Diagnostic]:
        """
        Import a single YAML metadata file.

        Validates the file first, then applies changes to the database.

        Args:
            path: Path to the YAML file to import

        Returns:
            List of diagnostics (empty if successful)
        """
        # Validate first
        diagnostics = self.validator.validate_file(path)
        errors = [d for d in diagnostics if d.severity == "error"]
        if errors:
            return diagnostics

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        entity_type = self.validator._detect_entity_type(path)

        if entity_type is None:
            return diagnostics

        with self.db.session_scope() as session:
            if isinstance(data, list):
                for item in data:
                    self._import_entity(session, item, entity_type)
            else:
                self._import_entity(session, data, entity_type)
            session.commit()

        return []

    def import_all(self, entity_type: Optional[str] = None) -> Dict[str, int]:
        """
        Import all YAML metadata files for a given entity type.

        Args:
            entity_type: Optional type filter

        Returns:
            Dict of import statistics
        """
        safe_logger(self.logger).log_info("Starting metadata import")
        imported = 0
        errors = 0

        type_paths = {
            "people": self.input_dir / "people",
            "locations": self.input_dir / "locations",
            "cities": self.input_dir / "cities.yaml",
            "arcs": self.input_dir / "arcs.yaml",
            "chapters": self.input_dir / "manuscript" / "chapters",
            "characters": self.input_dir / "manuscript" / "characters",
            "scenes": self.input_dir / "manuscript" / "scenes",
        }

        for etype, path in type_paths.items():
            if entity_type and etype != entity_type:
                continue

            if path.is_file():
                diags = self.import_file(path)
                if any(d.severity == "error" for d in diags):
                    errors += 1
                else:
                    imported += 1
            elif path.is_dir():
                for yaml_file in sorted(path.rglob("*.yaml")):
                    diags = self.import_file(yaml_file)
                    if any(d.severity == "error" for d in diags):
                        errors += 1
                    else:
                        imported += 1

        self.stats = {"imported": imported, "errors": errors}
        safe_logger(self.logger).log_info(
            f"Metadata import complete: {self.stats}"
        )
        return self.stats

    def _import_entity(
        self, session: Session, data: Dict[str, Any], entity_type: str
    ) -> None:
        """
        Import a single entity from parsed YAML data.

        Args:
            session: SQLAlchemy session
            data: Entity data dict
            entity_type: Entity type key
        """
        if entity_type == "people":
            self._import_person(session, data)
        elif entity_type == "locations":
            self._import_location(session, data)
        elif entity_type == "cities":
            self._import_city(session, data)
        elif entity_type == "arcs":
            self._import_arc(session, data)
        elif entity_type == "chapters":
            self._import_chapter(session, data)
        elif entity_type == "characters":
            self._import_character(session, data)
        elif entity_type == "scenes":
            self._import_scene(session, data)

    def _import_person(
        self, session: Session, data: Dict[str, Any]
    ) -> None:
        """
        Update a person entity from YAML data.

        Args:
            session: SQLAlchemy session
            data: Person data dict with name, lastname, relation_type
        """
        slug = data.get("slug")
        if not slug:
            return

        person = session.query(Person).filter(Person.slug == slug).first()
        if not person:
            return

        if "relation_type" in data and data["relation_type"]:
            person.relation_type = RelationType(data["relation_type"])

    def _import_location(
        self, session: Session, data: Dict[str, Any]
    ) -> None:
        """
        Update a location entity from YAML data.

        Args:
            session: SQLAlchemy session
            data: Location data dict
        """
        name = data.get("name")
        if not name:
            return

        location = session.query(Location).filter(
            Location.name == name
        ).first()
        if not location:
            return
        # Location has few editable fields beyond name/city

    def _import_city(
        self, session: Session, data: Dict[str, Any]
    ) -> None:
        """
        Update a city entity from YAML data.

        Args:
            session: SQLAlchemy session
            data: City data dict with name, country
        """
        name = data.get("name")
        if not name:
            return

        city = session.query(City).filter(City.name == name).first()
        if not city:
            return

        if "country" in data:
            city.country = data["country"]

    def _import_arc(
        self, session: Session, data: Dict[str, Any]
    ) -> None:
        """
        Update an arc entity from YAML data.

        Args:
            session: SQLAlchemy session
            data: Arc data dict with name, description
        """
        name = data.get("name")
        if not name:
            return

        arc = session.query(Arc).filter(Arc.name == name).first()
        if not arc:
            return

        if "description" in data:
            arc.description = data["description"]

    def _import_chapter(
        self, session: Session, data: Dict[str, Any]
    ) -> None:
        """
        Update a chapter entity from YAML data.

        Args:
            session: SQLAlchemy session
            data: Chapter data dict
        """
        title = data.get("title")
        if not title:
            return

        chapter = session.query(Chapter).filter(
            Chapter.title == title
        ).first()
        if not chapter:
            return

        if "type" in data:
            chapter.type = ChapterType(data["type"])
        if "status" in data:
            chapter.status = ChapterStatus(data["status"])
        if "number" in data:
            chapter.number = data["number"]

    def _import_character(
        self, session: Session, data: Dict[str, Any]
    ) -> None:
        """
        Update a character entity from YAML data.

        Args:
            session: SQLAlchemy session
            data: Character data dict
        """
        name = data.get("name")
        if not name:
            return

        character = session.query(Character).filter(
            Character.name == name
        ).first()
        if not character:
            return

        if "role" in data:
            character.role = data["role"]
        if "is_narrator" in data:
            character.is_narrator = data["is_narrator"]
        if "description" in data:
            character.description = data["description"]

    def _import_scene(
        self, session: Session, data: Dict[str, Any]
    ) -> None:
        """
        Update a manuscript scene entity from YAML data.

        Args:
            session: SQLAlchemy session
            data: Scene data dict
        """
        name = data.get("name")
        if not name:
            return

        ms_scene = session.query(ManuscriptScene).filter(
            ManuscriptScene.name == name
        ).first()
        if not ms_scene:
            return

        if "origin" in data:
            ms_scene.origin = SceneOrigin(data["origin"])
        if "status" in data:
            ms_scene.status = SceneStatus(data["status"])
        if "description" in data:
            ms_scene.description = data["description"]
        if "chapter" in data:
            if data["chapter"]:
                chapter = session.query(Chapter).filter(
                    Chapter.title == data["chapter"]
                ).first()
                ms_scene.chapter_id = chapter.id if chapter else None
            else:
                ms_scene.chapter_id = None
