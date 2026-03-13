#!/usr/bin/env python3
"""
import_json.py
--------------
Import database entities from JSON files exported by JSONExporter.

This module is the inverse of export_json.py. It reads individual JSON files
organized by entity type and imports them into the database using upsert
semantics (create if missing, update if existing). Natural keys are used to
resolve all foreign key relationships, making the import fully idempotent.

Key Features:
    - Idempotent upsert: safe to run multiple times on the same data
    - FK-dependency-ordered import (leaf entities first, dependents last)
    - Natural-key-based relationship resolution (slugs, names, dates)
    - Enum string-to-instance conversion for all typed fields
    - Single-transaction import with flush-based ID resolution

Architecture:
    - Builds natural_key -> DB_id lookup dicts as entities are created
    - Each _import_* method returns a lookup dict for downstream methods
    - Import order respects FK dependencies so lookups are available
    - M2M relationships resolved via ORM relationship attributes

Import Order (respects FK dependencies):
    1. Cities, Tags, Themes, Motifs, Arcs, Poems, ReferenceSources, Parts
    2. People (no FK deps)
    3. Locations (FK to City)
    4. Entries (M2M to many leaf entities)
    5. Scenes (FK to Entry, M2M to People/Locations)
    6. Threads (FK to Entry, M2M to People/Locations)
    7. Events (M2M to Scenes)
    8. ThemeInstances, MotifInstances (FK to Theme/Motif + Entry)
    9. PoemVersions (FK to Poem + Entry)
    10. References (FK to ReferenceSource + Entry)
    11. Chapters (FK to Part, M2M to Poems)
    12. Characters
    13. PersonCharacterMaps (FK to Person + Character)
    14. ManuscriptScenes (FK to Chapter, M2M to Characters)
    15. ManuscriptSources (FK to ManuscriptScene + Scene/Entry/Thread)
    16. ManuscriptReferences (FK to Chapter + ReferenceSource)

Usage:
    from dev.pipeline.import_json import JSONImporter
    from dev.database.manager import PalimpsestDB

    db = PalimpsestDB()
    importer = JSONImporter(db)
    stats = importer.import_all()

Dependencies:
    - dev.database.manager.PalimpsestDB for session management
    - dev.database.models for all ORM model classes
    - dev.core.paths.ROOT for default input directory resolution
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Type, TypeVar

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import ROOT
from dev.database.manager import PalimpsestDB
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
    SceneDate,
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


_T = TypeVar("_T")


def _resolve_m2m(
    session: Session,
    model: Type[_T],
    lookup: Dict[str, int],
    keys: List[str],
) -> List[_T]:
    """
    Resolve a list of natural keys to ORM instances via lookup dict.

    Args:
        session: SQLAlchemy session
        model: ORM model class
        lookup: Natural key to ID mapping
        keys: Natural keys to resolve

    Returns:
        List of resolved ORM instances (skips missing)
    """
    result: List[_T] = []
    for key in keys:
        if key in lookup:
            entity = session.get(model, lookup[key])
            if entity is not None:
                result.append(entity)
    return result


class JSONImporter:
    """
    Import database entities from JSON files with upsert semantics.

    Reads JSON files produced by JSONExporter and imports them into the
    database. Uses natural keys to resolve all relationships and supports
    idempotent re-import (existing entities are updated, new ones created).
    """

    def __init__(
        self,
        db: PalimpsestDB,
        input_dir: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize JSON importer.

        Args:
            db: Database manager instance
            input_dir: Input directory (defaults to data/exports)
            logger: Optional logger for operation tracking
        """
        self.db = db
        self.input_dir = input_dir or (ROOT / "data" / "exports")
        self.journal_dir = self.input_dir / "journal"
        self.logger = logger
        self.stats: Dict[str, int] = {}

    def import_all(
        self,
        changed_files: Optional[Set[Path]] = None,
    ) -> Dict[str, int]:
        """
        Import entity types from JSON files in dependency order.

        Runs the import inside a single session_scope transaction.
        Each entity type is imported in order, building lookup dicts
        that subsequent types use to resolve foreign keys.

        In incremental mode (``changed_files`` is a set), only entity
        types with changed files are imported.  Lookup dicts for
        unchanged types are built from DB queries instead.

        Args:
            changed_files: Set of changed file paths for incremental
                import.  ``None`` means full import (all files loaded).

        Returns:
            Dict mapping entity type names to count of imported entities

        Raises:
            Exception: If any import step fails (transaction is rolled back)
        """
        incremental = changed_files is not None
        mode = "incremental" if incremental else "full"
        safe_logger(self.logger).log_info(f"Starting {mode} JSON import")

        def _should_import(entity_type: str) -> bool:
            """Check if this entity type needs importing."""
            if changed_files is None:
                return True
            return self._has_changes(entity_type, changed_files)

        def _load(entity_type: str) -> List[Dict[str, Any]]:
            """Load JSON files, filtered in incremental mode."""
            return self._load_json_files(entity_type, changed_files)

        with self.db.session_scope() as session:
            # --- Phase 1: Leaf entities (no FK dependencies) ---
            if _should_import("cities"):
                self._import_cities(session, _load("cities"))
            city_lk = self._db_lookup_cities(session)

            if _should_import("tags"):
                self._import_tags(session, _load("tags"))
            tag_lk = self._db_lookup_tags(session)

            if _should_import("themes"):
                self._import_themes(session, _load("themes"))
            theme_lk = self._db_lookup_themes(session)

            if _should_import("motifs"):
                self._import_motifs(session, _load("motifs"))
            motif_lk = self._db_lookup_motifs(session)

            if _should_import("arcs"):
                self._import_arcs(session, _load("arcs"))
            arc_lk = self._db_lookup_arcs(session)

            if _should_import("poems"):
                self._import_poems(session, _load("poems"))
            poem_lk = self._db_lookup_poems(session)

            if _should_import("reference_sources"):
                self._import_reference_sources(session, _load("reference_sources"))
            source_lk = self._db_lookup_sources(session)

            if _should_import("parts"):
                self._import_parts(session, _load("parts"))
            part_lk = self._db_lookup_parts(session)

            # --- Phase 2: People (no FK deps) ---
            if _should_import("people"):
                self._import_people(session, _load("people"))
            people_lk = self._db_lookup_people(session)

            # --- Phase 3: Locations (FK to City) ---
            if _should_import("locations"):
                self._import_locations(
                    session, _load("locations"), city_lk
                )
            location_lk = self._db_lookup_locations(session)

            # --- Phase 4: Entries (M2M to many entities) ---
            entries_data = _load("entries")
            if entries_data:
                self._import_entries(
                    session,
                    entries_data,
                    people_lk,
                    location_lk,
                    city_lk,
                    arc_lk,
                    tag_lk,
                )
            entry_lk = self._db_lookup_entries(session)

            # --- Phase 5: Scenes (FK to Entry) ---
            if _should_import("scenes"):
                self._import_scenes(
                    session, _load("scenes"),
                    entry_lk, people_lk, location_lk,
                )
            scene_lk = self._db_lookup_scenes(session)

            # --- Phase 6: Threads (FK to Entry) ---
            if _should_import("threads"):
                self._import_threads(
                    session, _load("threads"),
                    entry_lk, people_lk, location_lk,
                )
            thread_lk = self._db_lookup_threads(session)

            # --- Phase 7: Events (M2M to Scenes + Entries) ---
            if _should_import("events"):
                self._import_events(
                    session, _load("events"), scene_lk
                )
            event_lk = self._db_lookup_events(session)

            # Link entries to events (only for changed entries)
            if entries_data:
                self._link_entry_events(
                    session, entries_data, entry_lk, event_lk
                )

            # --- Phase 8: Instance entities (FK to parent + Entry) ---
            if _should_import("theme_instances"):
                self._import_theme_instances(
                    session, _load("theme_instances"),
                    theme_lk, entry_lk,
                )
            if _should_import("motif_instances"):
                self._import_motif_instances(
                    session, _load("motif_instances"),
                    motif_lk, entry_lk,
                )

            # --- Phase 9: PoemVersions (FK to Poem + Entry) ---
            if _should_import("poems"):
                self._import_poem_versions(
                    session, _load("poems"), poem_lk, entry_lk
                )

            # --- Phase 10: References (FK to ReferenceSource + Entry) ---
            if _should_import("references"):
                self._import_references(
                    session, _load("references"),
                    source_lk, entry_lk,
                )

            # --- Phase 11: Chapters (FK to Part, M2M to Poems) ---
            if _should_import("chapters"):
                self._import_chapters(
                    session, _load("chapters"), part_lk, poem_lk
                )
            chapter_lk = self._db_lookup_chapters(session)

            # --- Phase 12: Characters ---
            if _should_import("characters"):
                self._import_characters(session, _load("characters"))
            character_lk = self._db_lookup_characters(session)

            # --- Phase 13: PersonCharacterMaps ---
            if _should_import("person_character_maps"):
                self._import_person_character_maps(
                    session, _load("person_character_maps"),
                    people_lk, character_lk,
                )

            # --- Phase 14: ManuscriptScenes (FK to Chapter, M2M Characters) ---
            if _should_import("manuscript_scenes"):
                self._import_manuscript_scenes(
                    session, _load("manuscript_scenes"),
                    chapter_lk, character_lk,
                )
            ms_scene_lk = self._db_lookup_ms_scenes(session)

            # --- Phase 15: ManuscriptSources ---
            if _should_import("manuscript_sources"):
                self._import_manuscript_sources(
                    session, _load("manuscript_sources"),
                    ms_scene_lk, scene_lk, entry_lk, thread_lk,
                )

            # --- Phase 16: ManuscriptReferences ---
            if _should_import("manuscript_references"):
                self._import_manuscript_references(
                    session, _load("manuscript_references"),
                    chapter_lk, source_lk,
                )

        total = sum(self.stats.values())
        safe_logger(self.logger).log_info(
            f"Import complete ({mode}): {total} entities imported"
        )
        return self.stats

    # =========================================================================
    # JSON FILE LOADING
    # =========================================================================

    def _load_json_files(
        self,
        entity_type: str,
        changed_files: Optional[Set[Path]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Load JSON files for an entity type from the export directory.

        Recursively globs *.json from journal/{entity_type}/ and parses
        each file into a dict.  When ``changed_files`` is provided, only
        files present in that set are loaded (incremental mode).

        Args:
            entity_type: Subdirectory name (e.g. "entries", "people")
            changed_files: If provided, only load files in this set.
                ``None`` loads all files (full import mode).

        Returns:
            List of parsed JSON dicts, one per file
        """
        entity_dir = self.journal_dir / entity_type
        if not entity_dir.exists():
            safe_logger(self.logger).log_debug(
                f"No directory for {entity_type}, skipping"
            )
            return []

        results: List[Dict[str, Any]] = []
        for json_file in sorted(entity_dir.rglob("*.json")):
            if changed_files is not None and json_file not in changed_files:
                continue
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                results.append(data)
            except (json.JSONDecodeError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Skipping corrupted file {json_file}: {e}"
                )
        return results

    def _has_changes(
        self,
        entity_type: str,
        changed_files: Set[Path],
    ) -> bool:
        """
        Check if any changed files belong to an entity type subdirectory.

        Args:
            entity_type: Subdirectory name (e.g. "entries", "people")
            changed_files: Set of changed file paths.

        Returns:
            ``True`` if at least one changed file is under the entity dir.
        """
        entity_dir = self.journal_dir / entity_type
        return any(entity_dir in f.parents for f in changed_files)

    # =========================================================================
    # DB LOOKUP BUILDERS (for incremental mode)
    # =========================================================================

    @staticmethod
    def _db_lookup_cities(session: Session) -> Dict[str, int]:
        """Build city name-to-ID lookup from database."""
        return {c.name: c.id for c in session.query(City).all()}

    @staticmethod
    def _db_lookup_tags(session: Session) -> Dict[str, int]:
        """Build tag name-to-ID lookup from database."""
        return {t.name: t.id for t in session.query(Tag).all()}

    @staticmethod
    def _db_lookup_themes(session: Session) -> Dict[str, int]:
        """Build theme name-to-ID lookup from database."""
        return {t.name: t.id for t in session.query(Theme).all()}

    @staticmethod
    def _db_lookup_motifs(session: Session) -> Dict[str, int]:
        """Build motif name-to-ID lookup from database."""
        return {m.name: m.id for m in session.query(Motif).all()}

    @staticmethod
    def _db_lookup_arcs(session: Session) -> Dict[str, int]:
        """Build arc name-to-ID lookup from database."""
        return {a.name: a.id for a in session.query(Arc).all()}

    @staticmethod
    def _db_lookup_poems(session: Session) -> Dict[str, int]:
        """Build poem title-to-ID lookup from database."""
        return {p.title: p.id for p in session.query(Poem).all()}

    @staticmethod
    def _db_lookup_sources(session: Session) -> Dict[str, int]:
        """Build reference source title-to-ID lookup from database."""
        return {s.title: s.id for s in session.query(ReferenceSource).all()}

    @staticmethod
    def _db_lookup_parts(session: Session) -> Dict[str, int]:
        """Build part number-to-ID lookup from database."""
        return {str(p.number): p.id for p in session.query(Part).all()}

    @staticmethod
    def _db_lookup_people(session: Session) -> Dict[str, int]:
        """Build person slug-to-ID lookup from database."""
        return {p.slug: p.id for p in session.query(Person).all()}

    @staticmethod
    def _db_lookup_locations(session: Session) -> Dict[str, int]:
        """Build location 'name::city'-to-ID lookup from database."""
        return {
            f"{loc.name}::{loc.city.name}": loc.id
            for loc in session.query(Location).all()
            if loc.city
        }

    @staticmethod
    def _db_lookup_entries(session: Session) -> Dict[str, int]:
        """Build entry date-to-ID lookup from database."""
        return {
            e.date.isoformat(): e.id
            for e in session.query(Entry).all()
        }

    @staticmethod
    def _db_lookup_scenes(session: Session) -> Dict[str, int]:
        """Build scene 'name::entry_date'-to-ID lookup from database."""
        return {
            f"{s.name}::{s.entry.date.isoformat()}": s.id
            for s in session.query(Scene).all()
            if s.entry
        }

    @staticmethod
    def _db_lookup_threads(session: Session) -> Dict[str, int]:
        """Build thread 'name::entry_date'-to-ID lookup from database."""
        return {
            f"{t.name}::{t.entry.date.isoformat()}": t.id
            for t in session.query(Thread).all()
            if t.entry
        }

    @staticmethod
    def _db_lookup_events(session: Session) -> Dict[str, int]:
        """Build event name-to-ID lookup from database."""
        return {e.name: e.id for e in session.query(Event).all()}

    @staticmethod
    def _db_lookup_chapters(session: Session) -> Dict[str, int]:
        """Build chapter title-to-ID lookup from database."""
        return {c.title: c.id for c in session.query(Chapter).all()}

    @staticmethod
    def _db_lookup_characters(session: Session) -> Dict[str, int]:
        """Build character name-to-ID lookup from database."""
        return {c.name: c.id for c in session.query(Character).all()}

    @staticmethod
    def _db_lookup_ms_scenes(session: Session) -> Dict[str, int]:
        """Build manuscript scene name-to-ID lookup from database."""
        return {
            ms.name: ms.id
            for ms in session.query(ManuscriptScene).all()
        }

    # =========================================================================
    # LEAF ENTITY IMPORTS
    # =========================================================================

    def _import_cities(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import cities from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of city JSON dicts

        Returns:
            Lookup dict mapping city name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            city = session.query(City).filter(City.name == name).first()
            if city:
                city.country = item.get("country")
            else:
                city = City(name=name, country=item.get("country"))
                session.add(city)
            session.flush()
            lookup[name] = city.id
        self.stats["cities"] = len(lookup)
        return lookup

    def _import_tags(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import tags from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of tag JSON dicts

        Returns:
            Lookup dict mapping tag name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            tag = session.query(Tag).filter(Tag.name == name).first()
            if not tag:
                tag = Tag(name=name)
                session.add(tag)
                session.flush()
            lookup[name] = tag.id
        self.stats["tags"] = len(lookup)
        return lookup

    def _import_themes(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import themes from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of theme JSON dicts

        Returns:
            Lookup dict mapping theme name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            theme = session.query(Theme).filter(Theme.name == name).first()
            if not theme:
                theme = Theme(name=name)
                session.add(theme)
                session.flush()
            lookup[name] = theme.id
        self.stats["themes"] = len(lookup)
        return lookup

    def _import_motifs(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import motifs from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of motif JSON dicts

        Returns:
            Lookup dict mapping motif name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            motif = session.query(Motif).filter(Motif.name == name).first()
            if not motif:
                motif = Motif(name=name)
                session.add(motif)
                session.flush()
            lookup[name] = motif.id
        self.stats["motifs"] = len(lookup)
        return lookup

    def _import_arcs(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import arcs from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of arc JSON dicts

        Returns:
            Lookup dict mapping arc name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            arc = session.query(Arc).filter(Arc.name == name).first()
            if arc:
                arc.description = item.get("description")
            else:
                arc = Arc(name=name, description=item.get("description"))
                session.add(arc)
            session.flush()
            lookup[name] = arc.id
        self.stats["arcs"] = len(lookup)
        return lookup

    def _import_poems(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import poem parent entities from PoemVersion JSON data.

        The export stores PoemVersions under the "poems" directory. Each
        PoemVersion references a poem title. This method extracts unique
        poem titles and creates the parent Poem entities.

        Args:
            session: Active SQLAlchemy session
            data: List of poem version JSON dicts (from poems/ directory)

        Returns:
            Lookup dict mapping poem title to database ID
        """
        lookup: Dict[str, int] = {}
        # Extract unique poem titles from version data
        titles = {item["poem"] for item in data if "poem" in item}
        for title in sorted(titles):
            poem = session.query(Poem).filter(Poem.title == title).first()
            if not poem:
                poem = Poem(title=title)
                session.add(poem)
                session.flush()
            lookup[title] = poem.id
        self.stats["poems"] = len(lookup)
        return lookup

    def _import_reference_sources(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import reference sources from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of reference source JSON dicts

        Returns:
            Lookup dict mapping source title to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            title = item["title"]
            source = (
                session.query(ReferenceSource)
                .filter(ReferenceSource.title == title)
                .first()
            )
            if source:
                source.author = item.get("author")
                source.type = ReferenceType(item["type"]) if item.get("type") else source.type
                source.url = item.get("url")
            else:
                source = ReferenceSource(
                    title=title,
                    author=item.get("author"),
                    type=ReferenceType(item["type"]) if item.get("type") else ReferenceType.OTHER,
                    url=item.get("url"),
                )
                session.add(source)
            session.flush()
            lookup[title] = source.id
        self.stats["reference_sources"] = len(lookup)
        return lookup

    def _import_parts(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import parts from JSON data.

        The natural key for parts is the number (as string) or title if
        no number is set.

        Args:
            session: Active SQLAlchemy session
            data: List of part JSON dicts

        Returns:
            Lookup dict mapping part number (int) to database ID.
            Parts without numbers are keyed by title string.
        """
        lookup: Dict[str, int] = {}
        for item in data:
            number = item.get("number")
            title = item.get("title")
            if number is not None:
                part = (
                    session.query(Part)
                    .filter(Part.number == number)
                    .first()
                )
            else:
                part = (
                    session.query(Part)
                    .filter(Part.title == title)
                    .first()
                )
            if part:
                part.number = number
                part.title = title
            else:
                part = Part(number=number, title=title)
                session.add(part)
            session.flush()
            key = str(number) if number is not None else (title or f"part-{part.id}")
            lookup[key] = part.id
        self.stats["parts"] = len(lookup)
        return lookup

    # =========================================================================
    # PEOPLE AND LOCATIONS
    # =========================================================================

    def _import_people(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import people from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of person JSON dicts

        Returns:
            Lookup dict mapping person slug to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            slug = item["slug"]
            person = session.query(Person).filter(Person.slug == slug).first()
            relation = (
                RelationType(item["relation_type"])
                if item.get("relation_type")
                else None
            )
            if person:
                person.name = item["name"]
                person.lastname = item.get("lastname")
                person.disambiguator = item.get("disambiguator")
                person.relation_type = relation
            else:
                person = Person(
                    name=item["name"],
                    lastname=item.get("lastname"),
                    disambiguator=item.get("disambiguator"),
                    slug=slug,
                    relation_type=relation,
                )
                session.add(person)
            session.flush()
            lookup[slug] = person.id
        self.stats["people"] = len(lookup)
        return lookup

    def _import_locations(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        city_lookup: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Import locations from JSON data, resolving city FK via lookup.

        Args:
            session: Active SQLAlchemy session
            data: List of location JSON dicts
            city_lookup: Mapping of city name to city ID

        Returns:
            Lookup dict mapping "name::city" to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            city_name = item["city"]
            city_id = city_lookup.get(city_name)
            if city_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping location '{name}': city '{city_name}' not found"
                )
                continue
            location = (
                session.query(Location)
                .filter(Location.name == name, Location.city_id == city_id)
                .first()
            )
            if not location:
                location = Location(name=name, city_id=city_id)
                session.add(location)
                session.flush()
            key = f"{name}::{city_name}"
            lookup[key] = location.id
        self.stats["locations"] = len(lookup)
        return lookup

    # =========================================================================
    # ENTRIES
    # =========================================================================

    def _import_entries(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        people_lk: Dict[str, int],
        location_lk: Dict[str, int],
        city_lk: Dict[str, int],
        arc_lk: Dict[str, int],
        tag_lk: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Import entries with all scalar fields and M2M relationships.

        Entry M2M relationships (people, locations, cities, arcs, tags) are
        resolved via lookup dicts. Events are linked later via
        _link_entry_events since they depend on scenes which depend on entries.

        Args:
            session: Active SQLAlchemy session
            data: List of entry JSON dicts
            people_lk: Slug-to-ID mapping for people
            location_lk: "name::city"-to-ID mapping for locations
            city_lk: Name-to-ID mapping for cities
            arc_lk: Name-to-ID mapping for arcs
            tag_lk: Name-to-ID mapping for tags

        Returns:
            Lookup dict mapping entry date string to database ID
        """
        lookup: Dict[str, int] = {}
        total = len(data)

        for i, item in enumerate(data, 1):
            entry_date = date.fromisoformat(item["date"])
            entry = (
                session.query(Entry)
                .filter(Entry.date == entry_date)
                .first()
            )
            if entry:
                # Update scalar fields
                entry.file_path = item["file_path"]
                entry.file_hash = item.get("file_hash")
                entry.metadata_hash = item.get("metadata_hash")
                entry.word_count = item.get("word_count", 0)
                entry.reading_time = item.get("reading_time", 0.0)
                entry.summary = item.get("summary")
                entry.rating = item.get("rating")
                entry.rating_justification = item.get("rating_justification")
            else:
                entry = Entry(
                    date=entry_date,
                    file_path=item["file_path"],
                    file_hash=item.get("file_hash"),
                    metadata_hash=item.get("metadata_hash"),
                    word_count=item.get("word_count", 0),
                    reading_time=item.get("reading_time", 0.0),
                    summary=item.get("summary"),
                    rating=item.get("rating"),
                    rating_justification=item.get("rating_justification"),
                )
                session.add(entry)
            session.flush()

            # Resolve M2M: people
            entry.people = _resolve_m2m(  # type: ignore[assignment]
                session, Person, people_lk, item.get("people", [])
            )

            # Resolve M2M: locations
            entry.locations = _resolve_m2m(  # type: ignore[assignment]
                session, Location, location_lk, item.get("locations", [])
            )

            # Resolve M2M: cities
            entry.cities = _resolve_m2m(  # type: ignore[assignment]
                session, City, city_lk, item.get("cities", [])
            )

            # Resolve M2M: arcs
            entry.arcs = _resolve_m2m(  # type: ignore[assignment]
                session, Arc, arc_lk, item.get("arcs", [])
            )

            # Resolve M2M: tags
            entry.tags = _resolve_m2m(  # type: ignore[assignment]
                session, Tag, tag_lk, item.get("tags", [])
            )

            lookup[item["date"]] = entry.id

            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(
                    f"   Importing entries: {i}/{total}"
                )

        self.stats["entries"] = len(lookup)
        return lookup

    def _link_entry_events(
        self,
        session: Session,
        entries_data: List[Dict[str, Any]],
        entry_lk: Dict[str, int],
        event_lk: Dict[str, int],
    ) -> None:
        """
        Link entries to events via M2M after both have been imported.

        This is deferred because events depend on scenes, which depend on
        entries. The entry JSON stores event names, but events must be
        imported after scenes.

        Args:
            session: Active SQLAlchemy session
            entries_data: Original entry JSON dicts (with event names)
            entry_lk: Date-to-ID mapping for entries
            event_lk: Name-to-ID mapping for events
        """
        for item in entries_data:
            entry_id = entry_lk.get(item["date"])
            if entry_id is None:
                continue
            event_names = item.get("events", [])
            if not event_names:
                continue
            entry = session.get(Entry, entry_id)
            if entry is None:
                continue
            entry.events = _resolve_m2m(  # type: ignore[assignment]
                session, Event, event_lk, event_names
            )

    # =========================================================================
    # SCENES AND THREADS
    # =========================================================================

    def _import_scenes(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        entry_lk: Dict[str, int],
        people_lk: Dict[str, int],
        location_lk: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Import scenes with FK to Entry and M2M to People/Locations.

        Also creates SceneDate children for each scene's date list.

        Args:
            session: Active SQLAlchemy session
            data: List of scene JSON dicts
            entry_lk: Date-to-ID mapping for entries
            people_lk: Slug-to-ID mapping for people
            location_lk: "name::city"-to-ID mapping for locations

        Returns:
            Lookup dict mapping "name::entry_date" to database ID
        """
        lookup: Dict[str, int] = {}
        total = len(data)

        for i, item in enumerate(data, 1):
            name = item["name"]
            entry_date = item["entry_date"]
            entry_id = entry_lk.get(entry_date)
            if entry_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping scene '{name}': entry '{entry_date}' not found"
                )
                continue

            scene = (
                session.query(Scene)
                .filter(Scene.name == name, Scene.entry_id == entry_id)
                .first()
            )
            if scene:
                scene.description = item["description"]
            else:
                scene = Scene(
                    name=name,
                    description=item["description"],
                    entry_id=entry_id,
                )
                session.add(scene)
            session.flush()

            # Upsert scene dates
            existing_dates = {sd.date for sd in scene.dates}
            for date_str in item.get("dates", []):
                if date_str not in existing_dates:
                    session.add(SceneDate(date=date_str, scene_id=scene.id))

            # Resolve M2M: people
            scene.people = _resolve_m2m(  # type: ignore[assignment]
                session, Person, people_lk, item.get("people", [])
            )

            # Resolve M2M: locations
            scene.locations = _resolve_m2m(  # type: ignore[assignment]
                session, Location, location_lk, item.get("locations", [])
            )

            key = f"{name}::{entry_date}"
            lookup[key] = scene.id

            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(
                    f"   Importing scenes: {i}/{total}"
                )

        self.stats["scenes"] = len(lookup)
        return lookup

    def _import_threads(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        entry_lk: Dict[str, int],
        people_lk: Dict[str, int],
        location_lk: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Import threads with FK to Entry and M2M to People/Locations.

        Args:
            session: Active SQLAlchemy session
            data: List of thread JSON dicts
            entry_lk: Date-to-ID mapping for entries
            people_lk: Slug-to-ID mapping for people
            location_lk: "name::city"-to-ID mapping for locations

        Returns:
            Lookup dict mapping "name::entry_date" to database ID
        """
        lookup: Dict[str, int] = {}
        total = len(data)

        for i, item in enumerate(data, 1):
            name = item["name"]
            entry_date = item["entry_date"]
            entry_id = entry_lk.get(entry_date)
            if entry_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping thread '{name}': entry '{entry_date}' not found"
                )
                continue

            ref_entry_date = (
                date.fromisoformat(item["referenced_entry_date"])
                if item.get("referenced_entry_date")
                else None
            )

            thread = (
                session.query(Thread)
                .filter(Thread.name == name, Thread.entry_id == entry_id)
                .first()
            )
            if thread:
                thread.from_date = item["from_date"]
                thread.to_date = item["to_date"]
                thread.referenced_entry_date = ref_entry_date
                thread.content = item["content"]
            else:
                thread = Thread(
                    name=name,
                    from_date=item["from_date"],
                    to_date=item["to_date"],
                    referenced_entry_date=ref_entry_date,
                    content=item["content"],
                    entry_id=entry_id,
                )
                session.add(thread)
            session.flush()

            # Resolve M2M: people
            thread.people = _resolve_m2m(  # type: ignore[assignment]
                session, Person, people_lk, item.get("people", [])
            )

            # Resolve M2M: locations
            thread.locations = _resolve_m2m(  # type: ignore[assignment]
                session, Location, location_lk, item.get("locations", [])
            )

            key = f"{name}::{entry_date}"
            lookup[key] = thread.id

            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(
                    f"   Importing threads: {i}/{total}"
                )

        self.stats["threads"] = len(lookup)
        return lookup

    # =========================================================================
    # EVENTS (depend on scenes)
    # =========================================================================

    def _import_events(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        scene_lk: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Import events with M2M to scenes.

        Args:
            session: Active SQLAlchemy session
            data: List of event JSON dicts
            scene_lk: "name::entry_date"-to-ID mapping for scenes

        Returns:
            Lookup dict mapping event name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            event = session.query(Event).filter(Event.name == name).first()
            if not event:
                event = Event(name=name)
                session.add(event)
                session.flush()

            # Resolve M2M: scenes
            event.scenes = _resolve_m2m(  # type: ignore[assignment]
                session, Scene, scene_lk, item.get("scenes", [])
            )

            lookup[name] = event.id
        self.stats["events"] = len(lookup)
        return lookup

    # =========================================================================
    # INSTANCE ENTITIES (FK to parent + Entry)
    # =========================================================================

    def _import_theme_instances(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        theme_lk: Dict[str, int],
        entry_lk: Dict[str, int],
    ) -> None:
        """
        Import theme instances linking themes to entries with descriptions.

        Args:
            session: Active SQLAlchemy session
            data: List of theme instance JSON dicts
            theme_lk: Name-to-ID mapping for themes
            entry_lk: Date-to-ID mapping for entries
        """
        count = 0
        for item in data:
            theme_name = item["theme"]
            entry_date = item["entry_date"]
            theme_id = theme_lk.get(theme_name)
            entry_id = entry_lk.get(entry_date)
            if theme_id is None or entry_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping theme instance '{theme_name}::{entry_date}': "
                    "missing theme or entry"
                )
                continue

            instance = (
                session.query(ThemeInstance)
                .filter(
                    ThemeInstance.theme_id == theme_id,
                    ThemeInstance.entry_id == entry_id,
                )
                .first()
            )
            if instance:
                instance.description = item["description"]
            else:
                instance = ThemeInstance(
                    description=item["description"],
                    theme_id=theme_id,
                    entry_id=entry_id,
                )
                session.add(instance)
            count += 1
        session.flush()
        self.stats["theme_instances"] = count

    def _import_motif_instances(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        motif_lk: Dict[str, int],
        entry_lk: Dict[str, int],
    ) -> None:
        """
        Import motif instances linking motifs to entries with descriptions.

        Args:
            session: Active SQLAlchemy session
            data: List of motif instance JSON dicts
            motif_lk: Name-to-ID mapping for motifs
            entry_lk: Date-to-ID mapping for entries
        """
        count = 0
        for item in data:
            motif_name = item["motif"]
            entry_date = item["entry_date"]
            motif_id = motif_lk.get(motif_name)
            entry_id = entry_lk.get(entry_date)
            if motif_id is None or entry_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping motif instance '{motif_name}::{entry_date}': "
                    "missing motif or entry"
                )
                continue

            instance = (
                session.query(MotifInstance)
                .filter(
                    MotifInstance.motif_id == motif_id,
                    MotifInstance.entry_id == entry_id,
                )
                .first()
            )
            if instance:
                instance.description = item["description"]
            else:
                instance = MotifInstance(
                    description=item["description"],
                    motif_id=motif_id,
                    entry_id=entry_id,
                )
                session.add(instance)
            count += 1
        session.flush()
        self.stats["motif_instances"] = count

    # =========================================================================
    # POEM VERSIONS (FK to Poem + Entry)
    # =========================================================================

    def _import_poem_versions(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        poem_lk: Dict[str, int],
        entry_lk: Dict[str, int],
    ) -> None:
        """
        Import poem versions linking poems to entries with content.

        The data comes from the same "poems" directory as _import_poems,
        but here each dict is treated as a PoemVersion record.

        Args:
            session: Active SQLAlchemy session
            data: List of poem version JSON dicts
            poem_lk: Title-to-ID mapping for poems
            entry_lk: Date-to-ID mapping for entries
        """
        count = 0
        for item in data:
            poem_title = item["poem"]
            entry_date = item["entry_date"]
            poem_id = poem_lk.get(poem_title)
            entry_id = entry_lk.get(entry_date)
            if poem_id is None or entry_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping poem version '{poem_title}::{entry_date}': "
                    "missing poem or entry"
                )
                continue

            pv = (
                session.query(PoemVersion)
                .filter(
                    PoemVersion.poem_id == poem_id,
                    PoemVersion.entry_id == entry_id,
                )
                .first()
            )
            if pv:
                pv.content = item["content"]
            else:
                pv = PoemVersion(
                    content=item["content"],
                    poem_id=poem_id,
                    entry_id=entry_id,
                )
                session.add(pv)
            count += 1
        session.flush()
        self.stats["poem_versions"] = count

    # =========================================================================
    # REFERENCES (FK to ReferenceSource + Entry)
    # =========================================================================

    def _import_references(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        source_lk: Dict[str, int],
        entry_lk: Dict[str, int],
    ) -> None:
        """
        Import references linking reference sources to entries.

        Args:
            session: Active SQLAlchemy session
            data: List of reference JSON dicts
            source_lk: Title-to-ID mapping for reference sources
            entry_lk: Date-to-ID mapping for entries
        """
        count = 0
        for item in data:
            source_title = item["source"]
            entry_date = item["entry_date"]
            mode_str = item["mode"]
            source_id = source_lk.get(source_title)
            entry_id = entry_lk.get(entry_date)
            if source_id is None or entry_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping reference '{source_title}::{entry_date}': "
                    "missing source or entry"
                )
                continue

            mode = ReferenceMode(mode_str)

            ref = (
                session.query(Reference)
                .filter(
                    Reference.source_id == source_id,
                    Reference.entry_id == entry_id,
                    Reference.mode == mode,
                )
                .first()
            )
            if ref:
                ref.content = item.get("content")
                ref.description = item.get("description")
            else:
                ref = Reference(
                    content=item.get("content"),
                    description=item.get("description"),
                    mode=mode,
                    source_id=source_id,
                    entry_id=entry_id,
                )
                session.add(ref)
            count += 1
        session.flush()
        self.stats["references"] = count

    # =========================================================================
    # MANUSCRIPT ENTITIES
    # =========================================================================

    def _import_chapters(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        part_lk: Dict[str, int],
        poem_lk: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Import chapters with FK to Part and M2M to Poems.

        Args:
            session: Active SQLAlchemy session
            data: List of chapter JSON dicts
            part_lk: Part-number-to-ID mapping
            poem_lk: Poem-title-to-ID mapping

        Returns:
            Lookup dict mapping chapter title to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            title = item["title"]
            chapter = (
                session.query(Chapter)
                .filter(Chapter.title == title)
                .first()
            )

            # Resolve part FK
            part_id = None
            if item.get("part") is not None:
                part_key = str(item["part"])
                part_id = part_lk.get(part_key)

            chapter_type = ChapterType(item["type"]) if item.get("type") else ChapterType.PROSE
            chapter_status = ChapterStatus(item["status"]) if item.get("status") else ChapterStatus.DRAFT
            chapter_date = date.fromisoformat(item["date"]) if item.get("date") else None

            if chapter:
                chapter.number = item.get("number")
                chapter.date = chapter_date
                chapter.part_id = part_id
                chapter.type = chapter_type
                chapter.status = chapter_status
                chapter.content = item.get("content")
                chapter.draft_path = item.get("draft_path")
            else:
                chapter = Chapter(
                    title=title,
                    number=item.get("number"),
                    date=chapter_date,
                    part_id=part_id,
                    type=chapter_type,
                    status=chapter_status,
                    content=item.get("content"),
                    draft_path=item.get("draft_path"),
                )
                session.add(chapter)
            session.flush()

            # Resolve M2M: poems
            chapter.poems = _resolve_m2m(  # type: ignore[assignment]
                session, Poem, poem_lk, item.get("poems", [])
            )

            lookup[title] = chapter.id
        self.stats["chapters"] = len(lookup)
        return lookup

    def _import_characters(
        self, session: Session, data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Import characters from JSON data.

        Args:
            session: Active SQLAlchemy session
            data: List of character JSON dicts

        Returns:
            Lookup dict mapping character name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            character = (
                session.query(Character)
                .filter(Character.name == name)
                .first()
            )
            if character:
                character.description = item.get("description")
                character.role = item.get("role")
                character.is_narrator = item.get("is_narrator", False)
            else:
                character = Character(
                    name=name,
                    description=item.get("description"),
                    role=item.get("role"),
                    is_narrator=item.get("is_narrator", False),
                )
                session.add(character)
            session.flush()
            lookup[name] = character.id
        self.stats["characters"] = len(lookup)
        return lookup

    def _import_person_character_maps(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        people_lk: Dict[str, int],
        character_lk: Dict[str, int],
    ) -> None:
        """
        Import person-character mappings.

        Args:
            session: Active SQLAlchemy session
            data: List of person-character map JSON dicts
            people_lk: Slug-to-ID mapping for people
            character_lk: Name-to-ID mapping for characters
        """
        count = 0
        for item in data:
            person_slug = item["person"]
            char_name = item["character"]
            person_id = people_lk.get(person_slug)
            character_id = character_lk.get(char_name)
            if person_id is None or character_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping person-character map '{person_slug}::{char_name}': "
                    "missing person or character"
                )
                continue

            contribution = (
                ContributionType(item["contribution"])
                if item.get("contribution")
                else ContributionType.PRIMARY
            )

            mapping = (
                session.query(PersonCharacterMap)
                .filter(
                    PersonCharacterMap.person_id == person_id,
                    PersonCharacterMap.character_id == character_id,
                )
                .first()
            )
            if mapping:
                mapping.contribution = contribution
                mapping.notes = item.get("notes")
            else:
                mapping = PersonCharacterMap(
                    person_id=person_id,
                    character_id=character_id,
                    contribution=contribution,
                    notes=item.get("notes"),
                )
                session.add(mapping)
            count += 1
        session.flush()
        self.stats["person_character_maps"] = count

    def _import_manuscript_scenes(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        chapter_lk: Dict[str, int],
        character_lk: Dict[str, int],
    ) -> Dict[str, int]:
        """
        Import manuscript scenes with FK to Chapter and M2M to Characters.

        Args:
            session: Active SQLAlchemy session
            data: List of manuscript scene JSON dicts
            chapter_lk: Title-to-ID mapping for chapters
            character_lk: Name-to-ID mapping for characters

        Returns:
            Lookup dict mapping manuscript scene name to database ID
        """
        lookup: Dict[str, int] = {}
        for item in data:
            name = item["name"]
            chapter_id = (
                chapter_lk.get(item["chapter"])
                if item.get("chapter")
                else None
            )
            origin = SceneOrigin(item["origin"]) if item.get("origin") else SceneOrigin.JOURNALED
            status = SceneStatus(item["status"]) if item.get("status") else SceneStatus.FRAGMENT

            ms_scene = (
                session.query(ManuscriptScene)
                .filter(ManuscriptScene.name == name)
                .first()
            )
            if ms_scene:
                ms_scene.description = item.get("description")
                ms_scene.chapter_id = chapter_id
                ms_scene.origin = origin
                ms_scene.status = status
                ms_scene.notes = item.get("notes")
                ms_scene.order = item.get("order")
            else:
                ms_scene = ManuscriptScene(
                    name=name,
                    description=item.get("description"),
                    chapter_id=chapter_id,
                    origin=origin,
                    status=status,
                    notes=item.get("notes"),
                    order=item.get("order"),
                )
                session.add(ms_scene)
            session.flush()

            # Resolve M2M: characters
            ms_scene.characters = _resolve_m2m(  # type: ignore[assignment]
                session, Character, character_lk, item.get("characters", [])
            )

            lookup[name] = ms_scene.id
        self.stats["manuscript_scenes"] = len(lookup)
        return lookup

    def _import_manuscript_sources(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        ms_scene_lk: Dict[str, int],
        scene_lk: Dict[str, int],
        entry_lk: Dict[str, int],
        thread_lk: Dict[str, int],
    ) -> None:
        """
        Import manuscript sources linking manuscript scenes to journal sources.

        Each source has a source_type that determines which FK is populated:
        scene, entry, thread, or external (no FK, uses external_note).

        Args:
            session: Active SQLAlchemy session
            data: List of manuscript source JSON dicts
            ms_scene_lk: Name-to-ID mapping for manuscript scenes
            scene_lk: "name::entry_date"-to-ID mapping for journal scenes
            entry_lk: Date-to-ID mapping for entries
            thread_lk: "name::entry_date"-to-ID mapping for threads
        """
        count = 0
        for item in data:
            ms_scene_name = item["manuscript_scene"]
            ms_scene_id = ms_scene_lk.get(ms_scene_name)
            if ms_scene_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping manuscript source: "
                    f"manuscript scene '{ms_scene_name}' not found"
                )
                continue

            source_type = SourceType(item["source_type"])

            # Resolve the polymorphic FK based on source_type
            scene_id = None
            entry_id = None
            thread_id = None

            if source_type == SourceType.SCENE and item.get("scene"):
                scene_id = scene_lk.get(item["scene"])
            elif source_type == SourceType.ENTRY and item.get("entry_date"):
                entry_id = entry_lk.get(item["entry_date"])
            elif source_type == SourceType.THREAD and item.get("thread"):
                thread_id = thread_lk.get(item["thread"])

            # Check for existing source with matching composite key
            query = session.query(ManuscriptSource).filter(
                ManuscriptSource.manuscript_scene_id == ms_scene_id,
                ManuscriptSource.source_type == source_type,
            )
            if scene_id is not None:
                query = query.filter(ManuscriptSource.scene_id == scene_id)
            elif entry_id is not None:
                query = query.filter(ManuscriptSource.entry_id == entry_id)
            elif thread_id is not None:
                query = query.filter(ManuscriptSource.thread_id == thread_id)
            elif source_type == SourceType.EXTERNAL:
                query = query.filter(
                    ManuscriptSource.external_note == item.get("external_note")
                )

            ms_source = query.first()
            if ms_source:
                ms_source.notes = item.get("notes")
                ms_source.external_note = item.get("external_note")
            else:
                ms_source = ManuscriptSource(
                    manuscript_scene_id=ms_scene_id,
                    source_type=source_type,
                    scene_id=scene_id,
                    entry_id=entry_id,
                    thread_id=thread_id,
                    external_note=item.get("external_note"),
                    notes=item.get("notes"),
                )
                session.add(ms_source)
            count += 1
        session.flush()
        self.stats["manuscript_sources"] = count

    def _import_manuscript_references(
        self,
        session: Session,
        data: List[Dict[str, Any]],
        chapter_lk: Dict[str, int],
        source_lk: Dict[str, int],
    ) -> None:
        """
        Import manuscript references linking chapters to reference sources.

        Args:
            session: Active SQLAlchemy session
            data: List of manuscript reference JSON dicts
            chapter_lk: Title-to-ID mapping for chapters
            source_lk: Title-to-ID mapping for reference sources
        """
        count = 0
        for item in data:
            chapter_title = item["chapter"]
            source_title = item["source"]
            chapter_id = chapter_lk.get(chapter_title)
            source_id = source_lk.get(source_title)
            if chapter_id is None or source_id is None:
                safe_logger(self.logger).log_warning(
                    f"Skipping manuscript reference "
                    f"'{chapter_title}::{source_title}': "
                    "missing chapter or source"
                )
                continue

            mode = (
                ReferenceMode(item["mode"])
                if item.get("mode")
                else ReferenceMode.THEMATIC
            )

            ref = (
                session.query(ManuscriptReference)
                .filter(
                    ManuscriptReference.chapter_id == chapter_id,
                    ManuscriptReference.source_id == source_id,
                )
                .first()
            )
            if ref:
                ref.mode = mode
                ref.content = item.get("content")
                ref.notes = item.get("notes")
            else:
                ref = ManuscriptReference(
                    chapter_id=chapter_id,
                    source_id=source_id,
                    mode=mode,
                    content=item.get("content"),
                    notes=item.get("notes"),
                )
                session.add(ref)
            count += 1
        session.flush()
        self.stats["manuscript_references"] = count
