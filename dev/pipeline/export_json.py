#!/usr/bin/env python3
"""
export_json.py
--------------
Export database entities to JSON files for version control and cross-machine sync.

This module exports database entities to individual JSON files organized by entity type.
Unlike metadata YAML files (human-authored, per-entry ground truth), these JSON exports
are machine-generated, machine-focused files using natural keys for relationships.

Key Features:
    - One JSON file per entity instance (not per entry)
    - Natural-key-based relationships (slugs, names, dates — no integer IDs)
    - Unidirectional relationship storage (zero redundancy)
    - README.md with human-readable change log
    - Single git commit per export with detailed README
    - Fast JSON parsing and compact file size

Architecture:
    - Relationships use natural keys: person slugs, entity names, entry dates
    - Entry owns: people, locations, cities, tags, themes, arcs, scenes, events, threads
    - Scene owns: people, locations, dates
    - Event owns: scenes
    - Thread owns: people, locations, referenced_entry
    - Entities don't store back-references (derived on import)
    - Lookup dicts built once per export for O(1) FK resolution

Directory Structure:
    data/exports/journal/
    ├── README.md
    ├── entries/YYYY/YYYY-MM-DD.json
    ├── people/{firstname}_{lastname|disambig}.json
    ├── locations/{city}/{location}.json
    ├── scenes/YYYY-MM-DD/{scene-name}.json
    ├── events/{event-name}.json
    ├── threads/{thread-name}.json
    └── ...

Usage:
    from dev.pipeline.export_json import JSONExporter
    from dev.database.manager import PalimpsestDB

    db = PalimpsestDB()
    exporter = JSONExporter(db)
    exporter.export_all()  # Exports all entities + README + git commit
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    Motif,
    MotifInstance,
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
from dev.utils.slugify import (
    slugify,
    generate_person_filename,
    generate_location_path,
    generate_scene_path,
    generate_entry_path,
)


class JSONExporter:
    """
    Exports database entities to individual JSON files with README changelog.

    Generates one JSON file per entity instance, organized by entity type.
    Tracks changes and generates human-readable README for git commits.
    Uses natural keys (names, slugs, dates) instead of integer IDs.
    """

    def __init__(
        self,
        db: PalimpsestDB,
        output_dir: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize JSON exporter.

        Args:
            db: Database manager instance
            output_dir: Output directory (defaults to data/exports)
            logger: Optional logger for operation tracking
        """
        self.db = db
        self.output_dir = output_dir or (ROOT / "data" / "exports")
        self.journal_dir = self.output_dir / "journal"
        self.logger = logger

        # Track changes for README
        self.changes: List[str] = []
        self.stats: Dict[str, int] = {}

        # Lookup dicts for FK resolution (populated by _build_lookups)
        self._entry_dates: Dict[int, str] = {}
        self._person_slugs: Dict[int, str] = {}
        self._city_names: Dict[int, str] = {}
        self._location_keys: Dict[int, str] = {}
        self._event_names: Dict[int, str] = {}
        self._arc_names: Dict[int, str] = {}
        self._tag_names: Dict[int, str] = {}
        self._theme_names: Dict[int, str] = {}
        self._motif_names: Dict[int, str] = {}
        self._source_titles: Dict[int, str] = {}
        self._poem_titles: Dict[int, str] = {}
        self._scene_keys: Dict[int, str] = {}
        self._thread_keys: Dict[int, str] = {}
        self._part_numbers: Dict[int, Optional[int]] = {}
        self._chapter_titles: Dict[int, str] = {}
        self._character_names: Dict[int, str] = {}
        self._ms_scene_names: Dict[int, str] = {}

    def _build_lookups(self, session: Session) -> None:
        """
        Build lookup dicts from all entity tables for O(1) FK resolution.

        Queries each entity table once and builds {int_id: natural_key_string}
        maps used by export methods to replace integer FK references with
        deterministic natural keys.

        Args:
            session: Active SQLAlchemy session
        """
        self._entry_dates = {e.id: e.date.isoformat() for e in session.query(Entry)}
        self._person_slugs = {p.id: p.slug for p in session.query(Person)}
        self._city_names = {c.id: c.name for c in session.query(City)}
        self._location_keys = {
            loc.id: f"{loc.name}::{self._city_names[loc.city_id]}"
            for loc in session.query(Location)
        }
        self._event_names = {e.id: e.name for e in session.query(Event)}
        self._arc_names = {a.id: a.name for a in session.query(Arc)}
        self._tag_names = {t.id: t.name for t in session.query(Tag)}
        self._theme_names = {t.id: t.name for t in session.query(Theme)}
        self._motif_names = {m.id: m.name for m in session.query(Motif)}
        self._source_titles = {s.id: s.title for s in session.query(ReferenceSource)}
        self._poem_titles = {p.id: p.title for p in session.query(Poem)}
        self._scene_keys = {
            s.id: f"{s.name}::{self._entry_dates[s.entry_id]}"
            for s in session.query(Scene)
        }
        self._thread_keys = {
            t.id: f"{t.name}::{self._entry_dates[t.entry_id]}"
            for t in session.query(Thread)
        }
        # Manuscript lookups
        self._part_numbers = {p.id: p.number for p in session.query(Part)}
        self._chapter_titles = {c.id: c.title for c in session.query(Chapter)}
        self._character_names = {c.id: c.name for c in session.query(Character)}
        self._ms_scene_names = {s.id: s.name for s in session.query(ManuscriptScene)}

    def export_all(self) -> None:
        """
        Export all entities to JSON files with README and git commit.

        This is the main entry point for full database export.
        Provides progress feedback and handles errors gracefully.
        """
        safe_logger(self.logger).log_info("🔄 Starting full database export to JSON")

        try:
            # Step 1: Load previous exports for diff
            safe_logger(self.logger).log_info("📂 Loading existing exports for comparison...")
            old_exports = self._load_existing_exports()
            old_count = sum(len(entities) for entities in old_exports.values())
            safe_logger(self.logger).log_info(f"   Found {old_count} existing entities")

            # Step 2: Export all entity types
            safe_logger(self.logger).log_info("📊 Exporting all entities from database...")
            new_exports = self._export_all_entities()
            new_count = sum(self.stats.values())
            safe_logger(self.logger).log_info(f"   Exported {new_count} entities")

            # Step 3: Generate change descriptions
            safe_logger(self.logger).log_info("🔍 Detecting changes...")
            self._generate_changes(old_exports, new_exports)
            safe_logger(self.logger).log_info(f"   Detected {len(self.changes)} changes")

            # Step 4: Write all JSON files
            safe_logger(self.logger).log_info("💾 Writing JSON files...")
            self._write_exports(new_exports)
            safe_logger(self.logger).log_info(f"   Wrote {new_count} files")

            # Step 5: Generate and write README
            safe_logger(self.logger).log_info("📝 Generating README...")
            self._write_readme()

            # Step 6: Git commit
            safe_logger(self.logger).log_info("🔐 Creating git commit...")
            self._git_commit()

            safe_logger(self.logger).log_info(
                f"✅ Export complete: {new_count} files exported, {len(self.changes)} changes"
            )

        except Exception as e:
            safe_logger(self.logger).log_error(
                e,
                {
                    "operation": "export_all",
                    "stats": self.stats,
                    "changes_detected": len(self.changes)
                }
            )
            raise

    def _export_all_entities(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Export all entities to in-memory JSON structures.

        Builds lookup dicts first, then exports each entity type using
        natural keys as dict keys.

        Returns:
            Nested dict: {entity_type: {natural_key: json_data}}
        """
        exports = {}

        with self.db.session_scope() as session:
            # Build lookup dicts for FK resolution
            self._build_lookups(session)

            # Journal entities
            exports["entries"] = self._export_entries(session)
            exports["people"] = self._export_people(session)
            exports["locations"] = self._export_locations(session)
            exports["cities"] = self._export_cities(session)
            exports["scenes"] = self._export_scenes(session)
            exports["events"] = self._export_events(session)
            exports["threads"] = self._export_threads(session)
            exports["arcs"] = self._export_arcs(session)
            exports["poems"] = self._export_poems(session)
            exports["references"] = self._export_references(session)
            exports["reference_sources"] = self._export_reference_sources(session)
            exports["tags"] = self._export_tags(session)
            exports["themes"] = self._export_themes(session)
            exports["motifs"] = self._export_motifs(session)
            exports["motif_instances"] = self._export_motif_instances(session)

            # Manuscript entities
            exports["parts"] = self._export_parts(session)
            exports["chapters"] = self._export_chapters(session)
            exports["characters"] = self._export_characters(session)
            exports["person_character_maps"] = self._export_person_character_maps(session)
            exports["manuscript_scenes"] = self._export_manuscript_scenes(session)
            exports["manuscript_sources"] = self._export_manuscript_sources(session)
            exports["manuscript_references"] = self._export_manuscript_references(session)

        return exports

    # =========================================================================
    # ENTITY EXPORT METHODS
    # =========================================================================

    def _export_entries(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all entries with their owned relationships.

        Dict key is entry date string (e.g. "2024-01-15").
        Relationships use natural keys instead of integer IDs.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping entry date to entry data
        """
        entries = session.query(Entry).all()
        result = {}
        total = len(entries)

        for i, entry in enumerate(entries, 1):
            key = entry.date.isoformat()
            result[key] = {
                "date": key,
                "file_path": entry.file_path,
                "file_hash": entry.file_hash,
                "metadata_hash": entry.metadata_hash,
                "word_count": entry.word_count,
                "reading_time": entry.reading_time,
                "summary": entry.summary,
                "rating": float(entry.rating) if entry.rating else None,
                "rating_justification": entry.rating_justification,
                # Owned relationships (natural keys)
                "people": [p.slug for p in entry.people],
                "locations": [self._location_keys[loc.id] for loc in entry.locations],
                "cities": [c.name for c in entry.cities],
                "arcs": [a.name for a in entry.arcs],
                "tags": [t.name for t in entry.tags],
                "themes": [th.name for th in entry.themes],
                "scenes": [s.name for s in entry.scenes],
                "events": [e.name for e in entry.events],
                "threads": [th.name for th in entry.threads],
                "poems": [self._poem_titles[pv.poem_id] for pv in entry.poems],
                "references": [
                    f"{self._source_titles[r.source_id]}::{r.mode.value}"
                    for r in entry.references
                ],
                "motif_instances": [
                    self._motif_names[mi.motif_id] for mi in entry.motif_instances
                ],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting entries: {i}/{total}")

        self.stats["entries"] = len(result)
        return result

    def _export_people(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all people (no back-references to entries).

        Dict key is person slug (e.g. "alice_smith").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping person slug to person data
        """
        people = session.query(Person).all()
        result = {}
        total = len(people)

        for i, person in enumerate(people, 1):
            result[person.slug] = {
                "slug": person.slug,
                "name": person.name,
                "lastname": person.lastname,
                "disambiguator": person.disambiguator,
                "relation_type": person.relation_type.value if person.relation_type else None,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting people: {i}/{total}")

        self.stats["people"] = len(result)
        return result

    def _export_locations(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all locations.

        Dict key is "name::city_name" (e.g. "Cafe X::Montreal").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping location key to location data
        """
        locations = session.query(Location).all()
        result = {}
        total = len(locations)

        for i, loc in enumerate(locations, 1):
            key = self._location_keys[loc.id]
            result[key] = {
                "name": loc.name,
                "city": self._city_names[loc.city_id],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting locations: {i}/{total}")

        self.stats["locations"] = len(result)
        return result

    def _export_cities(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all cities.

        Dict key is city name (e.g. "Montreal").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping city name to city data
        """
        cities = session.query(City).all()
        result = {}

        for city in cities:
            result[city.name] = {
                "name": city.name,
                "country": city.country,
            }

        self.stats["cities"] = len(result)
        return result

    def _export_scenes(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all scenes with their owned relationships.

        Dict key is "name::entry_date" (e.g. "Morning Coffee::2024-01-15").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping scene key to scene data
        """
        scenes = session.query(Scene).all()
        result = {}
        total = len(scenes)

        for i, scene in enumerate(scenes, 1):
            # Get scene dates (already strings in flexible format)
            dates = [sd.date for sd in scene.dates]

            key = self._scene_keys[scene.id]
            result[key] = {
                "name": scene.name,
                "description": scene.description,
                "entry_date": self._entry_dates[scene.entry_id],
                "dates": dates,
                "people": [p.slug for p in scene.people],
                "locations": [self._location_keys[loc.id] for loc in scene.locations],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting scenes: {i}/{total}")

        self.stats["scenes"] = len(result)
        return result

    def _export_events(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all events with their owned relationships.

        Dict key is event name (e.g. "Daily Routine").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping event name to event data
        """
        events = session.query(Event).all()
        result = {}
        total = len(events)

        for i, event in enumerate(events, 1):
            result[event.name] = {
                "name": event.name,
                "scenes": [self._scene_keys[s.id] for s in event.scenes],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting events: {i}/{total}")

        self.stats["events"] = len(result)
        return result

    def _export_threads(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all threads with their owned relationships.

        Dict key is "name::entry_date" (e.g. "The Bookend Kiss::2024-01-15").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping thread key to thread data
        """
        threads = session.query(Thread).all()
        result = {}
        total = len(threads)

        for i, thread in enumerate(threads, 1):
            key = self._thread_keys[thread.id]
            result[key] = {
                "name": thread.name,
                "from_date": thread.from_date,
                "to_date": thread.to_date,
                "referenced_entry_date": (
                    thread.referenced_entry_date.isoformat()
                    if thread.referenced_entry_date
                    else None
                ),
                "content": thread.content,
                "entry_date": self._entry_dates[thread.entry_id],
                "people": [p.slug for p in thread.people],
                "locations": [self._location_keys[loc.id] for loc in thread.locations],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting threads: {i}/{total}")

        self.stats["threads"] = len(result)
        return result

    def _export_arcs(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all arcs.

        Dict key is arc name (e.g. "The Long Wanting").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping arc name to arc data
        """
        arcs = session.query(Arc).all()
        result = {}

        for arc in arcs:
            result[arc.name] = {
                "name": arc.name,
                "description": arc.description,
            }

        self.stats["arcs"] = len(result)
        return result

    def _export_poems(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all poem versions.

        Dict key is "poem_title::entry_date" (e.g. "Untitled::2024-01-15").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping poem version key to poem version data
        """
        poem_versions = session.query(PoemVersion).all()
        result = {}
        total = len(poem_versions)

        for i, pv in enumerate(poem_versions, 1):
            poem_title = self._poem_titles[pv.poem_id]
            entry_date = self._entry_dates[pv.entry_id]
            key = f"{poem_title}::{entry_date}"
            result[key] = {
                "content": pv.content,
                "poem": poem_title,
                "entry_date": entry_date,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting poems: {i}/{total}")

        self.stats["poems"] = len(result)
        return result

    def _export_references(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all references.

        Dict key is "source_title::mode::entry_date"
        (e.g. "Important Book::direct::2024-01-15").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping reference key to reference data
        """
        references = session.query(Reference).all()
        result = {}
        total = len(references)

        for i, ref in enumerate(references, 1):
            source_title = self._source_titles[ref.source_id]
            mode = ref.mode.value if ref.mode else "unknown"
            entry_date = self._entry_dates[ref.entry_id]
            key = f"{source_title}::{mode}::{entry_date}"
            result[key] = {
                "content": ref.content,
                "description": ref.description,
                "mode": mode,
                "source": source_title,
                "entry_date": entry_date,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting references: {i}/{total}")

        self.stats["references"] = len(result)
        return result

    def _export_reference_sources(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all reference sources.

        Dict key is source title (e.g. "Important Book").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping source title to source data
        """
        sources = session.query(ReferenceSource).all()
        result = {}

        for source in sources:
            result[source.title] = {
                "title": source.title,
                "author": source.author,
                "type": source.type.value if source.type else None,
                "url": source.url,
            }

        self.stats["reference_sources"] = len(result)
        return result

    def _export_tags(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all tags.

        Dict key is tag name (e.g. "writing").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping tag name to tag data
        """
        tags = session.query(Tag).all()
        result = {}

        for tag in tags:
            result[tag.name] = {
                "name": tag.name,
            }

        self.stats["tags"] = len(result)
        return result

    def _export_themes(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all themes.

        Dict key is theme name (e.g. "identity").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping theme name to theme data
        """
        themes = session.query(Theme).all()
        result = {}

        for theme in themes:
            result[theme.name] = {
                "name": theme.name,
            }

        self.stats["themes"] = len(result)
        return result

    def _export_motifs(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all motifs.

        Dict key is motif name (e.g. "water").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping motif name to motif data
        """
        motifs = session.query(Motif).all()
        result = {}

        for motif in motifs:
            result[motif.name] = {
                "name": motif.name,
            }

        self.stats["motifs"] = len(result)
        return result

    def _export_motif_instances(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all motif instances.

        Dict key is "motif_name::entry_date" (e.g. "water::2024-01-15").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping motif instance key to motif instance data
        """
        instances = session.query(MotifInstance).all()
        result = {}
        total = len(instances)

        for i, mi in enumerate(instances, 1):
            motif_name = self._motif_names[mi.motif_id]
            entry_date = self._entry_dates[mi.entry_id]
            key = f"{motif_name}::{entry_date}"
            result[key] = {
                "description": mi.description,
                "motif": motif_name,
                "entry_date": entry_date,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting motif instances: {i}/{total}")

        self.stats["motif_instances"] = len(result)
        return result

    # =========================================================================
    # MANUSCRIPT ENTITY EXPORT METHODS
    # =========================================================================

    def _export_parts(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all parts.

        Dict key is part number as string, or title if no number.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping part key to part data
        """
        parts = session.query(Part).all()
        result = {}

        for part in parts:
            key = str(part.number) if part.number is not None else (part.title or f"part-{part.id}")
            result[key] = {
                "number": part.number,
                "title": part.title,
            }

        self.stats["parts"] = len(result)
        return result

    def _export_chapters(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all chapters with type/status enums and relationship natural keys.

        Dict key is chapter title (e.g. "The Gray Fence").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping chapter title to chapter data
        """
        chapters = session.query(Chapter).all()
        result = {}

        for chapter in chapters:
            result[chapter.title] = {
                "title": chapter.title,
                "number": chapter.number,
                "part": self._part_numbers.get(chapter.part_id) if chapter.part_id else None,
                "type": chapter.type.value if chapter.type else None,
                "status": chapter.status.value if chapter.status else None,
                "content": chapter.content,
                "draft_path": chapter.draft_path,
                "poems": [self._poem_titles[p.id] for p in chapter.poems],
                "characters": [c.name for c in chapter.characters],
                "arcs": [a.name for a in chapter.arcs],
            }

        self.stats["chapters"] = len(result)
        return result

    def _export_characters(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all characters.

        Dict key is character name (e.g. "Sofia").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping character name to character data
        """
        characters = session.query(Character).all()
        result = {}

        for char in characters:
            result[char.name] = {
                "name": char.name,
                "description": char.description,
                "role": char.role,
                "is_narrator": char.is_narrator,
            }

        self.stats["characters"] = len(result)
        return result

    def _export_person_character_maps(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all person-character mappings.

        Dict key is "person_slug::character_name"
        (e.g. "maria_garcia::Sofia").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping mapping key to mapping data
        """
        mappings = session.query(PersonCharacterMap).all()
        result = {}

        for mapping in mappings:
            person_slug = self._person_slugs[mapping.person_id]
            character_name = self._character_names[mapping.character_id]
            key = f"{person_slug}::{character_name}"
            result[key] = {
                "person": person_slug,
                "character": character_name,
                "contribution": mapping.contribution.value if mapping.contribution else None,
                "notes": mapping.notes,
            }

        self.stats["person_character_maps"] = len(result)
        return result

    def _export_manuscript_scenes(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all manuscript scenes with origin/status enums.

        Dict key is manuscript scene name (e.g. "Morning at the Fence").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping scene name to scene data
        """
        scenes = session.query(ManuscriptScene).all()
        result = {}

        for scene in scenes:
            result[scene.name] = {
                "name": scene.name,
                "description": scene.description,
                "chapter": self._chapter_titles.get(scene.chapter_id) if scene.chapter_id else None,
                "origin": scene.origin.value if scene.origin else None,
                "status": scene.status.value if scene.status else None,
                "notes": scene.notes,
            }

        self.stats["manuscript_scenes"] = len(result)
        return result

    def _export_manuscript_sources(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all manuscript sources with source_type polymorphism.

        Dict key is "manuscript_scene_name::source_type::index" for uniqueness.
        Since manuscript sources don't have a simple unique natural key,
        we use a composite of scene name, source type, and referenced entity.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping source key to source data
        """
        sources = session.query(ManuscriptSource).all()
        result = {}

        for source in sources:
            ms_scene_name = self._ms_scene_names[source.manuscript_scene_id]
            source_type = source.source_type.value if source.source_type else "unknown"

            # Build a unique key from source type + referenced entity
            ref_key = ""
            if source.scene_id:
                ref_key = self._scene_keys.get(source.scene_id, "")
            elif source.entry_id:
                ref_key = self._entry_dates.get(source.entry_id, "")
            elif source.thread_id:
                ref_key = self._thread_keys.get(source.thread_id, "")
            elif source.external_note:
                ref_key = slugify(source.external_note)[:50]

            key = f"{ms_scene_name}::{source_type}::{ref_key}"
            result[key] = {
                "manuscript_scene": ms_scene_name,
                "source_type": source_type,
                "scene": self._scene_keys.get(source.scene_id) if source.scene_id else None,
                "entry_date": self._entry_dates.get(source.entry_id) if source.entry_id else None,
                "thread": self._thread_keys.get(source.thread_id) if source.thread_id else None,
                "external_note": source.external_note,
                "notes": source.notes,
            }

        self.stats["manuscript_sources"] = len(result)
        return result

    def _export_manuscript_references(self, session: Session) -> Dict[str, Dict[str, Any]]:
        """
        Export all manuscript references with mode enum.

        Dict key is "chapter_title::source_title"
        (e.g. "The Gray Fence::Important Book").

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict mapping reference key to reference data
        """
        refs = session.query(ManuscriptReference).all()
        result = {}

        for ref in refs:
            chapter_title = self._chapter_titles[ref.chapter_id]
            source_title = self._source_titles[ref.source_id]
            key = f"{chapter_title}::{source_title}"
            result[key] = {
                "chapter": chapter_title,
                "source": source_title,
                "mode": ref.mode.value if ref.mode else None,
                "content": ref.content,
                "notes": ref.notes,
            }

        self.stats["manuscript_references"] = len(result)
        return result

    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================

    def _load_existing_exports(self) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        Load existing JSON files from disk for comparison.

        Scans data/exports/journal/ directory tree and loads all JSON files.
        Returns same structure as _export_all_entities for easy comparison.
        Extracts natural keys from file data based on entity type.

        Returns:
            Nested dict: {entity_type: {natural_key: json_data}}
        """
        old_exports: Dict[str, Dict[str, Dict[str, Any]]] = {}

        if not self.journal_dir.exists():
            # First export - no existing files
            return old_exports

        safe_logger(self.logger).log_debug("Loading existing exports for comparison")

        # Initialize all entity type dicts
        for entity_type in ["entries", "people", "locations", "cities", "scenes",
                           "events", "threads", "arcs", "poems", "references",
                           "reference_sources", "tags", "themes", "motifs", "motif_instances",
                           "parts", "chapters", "characters", "person_character_maps",
                           "manuscript_scenes", "manuscript_sources", "manuscript_references"]:
            old_exports[entity_type] = {}

        # Scan all JSON files in journal directory
        for json_file in self.journal_dir.rglob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # Determine entity type from directory structure
                relative_path = json_file.relative_to(self.journal_dir)
                entity_type = relative_path.parts[0]  # First directory (people, entries, etc.)

                # Extract natural key from data
                natural_key = self._extract_natural_key(entity_type, data)
                if natural_key is None:
                    safe_logger(self.logger).log_warning(
                        f"Skipping {json_file}: cannot extract natural key"
                    )
                    continue

                # Store in structure
                if entity_type in old_exports:
                    old_exports[entity_type][natural_key] = data
                else:
                    safe_logger(self.logger).log_warning(f"Unknown entity type: {entity_type}")

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                safe_logger(self.logger).log_warning(f"Skipping corrupted file {json_file}: {e}")
                continue

        safe_logger(self.logger).log_debug(
            f"Loaded {sum(len(entities) for entities in old_exports.values())} existing entities"
        )

        return old_exports

    def _extract_natural_key(self, entity_type: str, data: Dict[str, Any]) -> Optional[str]:
        """
        Extract the natural key from entity JSON data based on entity type.

        Args:
            entity_type: Type of entity (people, entries, etc.)
            data: Entity JSON data

        Returns:
            Natural key string, or None if data doesn't have required fields
        """
        if entity_type == "entries":
            return data.get("date")
        elif entity_type == "people":
            return data.get("slug")
        elif entity_type == "locations":
            name = data.get("name")
            city = data.get("city")
            if name and city:
                return f"{name}::{city}"
            return None
        elif entity_type == "cities":
            return data.get("name")
        elif entity_type == "scenes":
            name = data.get("name")
            entry_date = data.get("entry_date")
            if name and entry_date:
                return f"{name}::{entry_date}"
            return None
        elif entity_type == "threads":
            name = data.get("name")
            entry_date = data.get("entry_date")
            if name and entry_date:
                return f"{name}::{entry_date}"
            return None
        elif entity_type == "poems":
            poem = data.get("poem")
            entry_date = data.get("entry_date")
            if poem and entry_date:
                return f"{poem}::{entry_date}"
            return None
        elif entity_type == "references":
            source = data.get("source")
            mode = data.get("mode")
            entry_date = data.get("entry_date")
            if source and mode and entry_date:
                return f"{source}::{mode}::{entry_date}"
            return None
        elif entity_type == "motif_instances":
            motif = data.get("motif")
            entry_date = data.get("entry_date")
            if motif and entry_date:
                return f"{motif}::{entry_date}"
            return None
        elif entity_type == "person_character_maps":
            person = data.get("person")
            character = data.get("character")
            if person and character:
                return f"{person}::{character}"
            return None
        elif entity_type == "manuscript_references":
            chapter = data.get("chapter")
            source = data.get("source")
            if chapter and source:
                return f"{chapter}::{source}"
            return None
        elif entity_type == "manuscript_sources":
            ms_scene = data.get("manuscript_scene")
            source_type = data.get("source_type")
            # Reconstruct key from referenced entity
            ref_key = ""
            if data.get("scene"):
                ref_key = data["scene"]
            elif data.get("entry_date"):
                ref_key = data["entry_date"]
            elif data.get("thread"):
                ref_key = data["thread"]
            elif data.get("external_note"):
                ref_key = slugify(data["external_note"])[:50]
            if ms_scene and source_type:
                return f"{ms_scene}::{source_type}::{ref_key}"
            return None
        elif entity_type == "parts":
            number = data.get("number")
            if number is not None:
                return str(number)
            return data.get("title")
        elif entity_type == "chapters":
            return data.get("title")
        elif entity_type == "characters":
            return data.get("name")
        elif entity_type == "manuscript_scenes":
            return data.get("name")
        else:
            # Simple entities: events, arcs, tags, themes, motifs, reference_sources
            return data.get("name") or data.get("title")

    def _generate_changes(
        self,
        old_exports: Dict[str, Dict[str, Dict[str, Any]]],
        new_exports: Dict[str, Dict[str, Dict[str, Any]]],
    ) -> None:
        """
        Generate human-readable change descriptions by comparing old and new.

        Compares entity data and generates formatted change strings:
        - + entity added
        - ~ entity modified (with field changes)
        - - entity deleted

        Populates self.changes list with formatted change strings.

        Args:
            old_exports: Previous export data
            new_exports: Current export data
        """
        safe_logger(self.logger).log_debug("Generating change descriptions")

        # Track changes by entity type
        for entity_type in new_exports.keys():
            old_entities = old_exports.get(entity_type, {})
            new_entities = new_exports[entity_type]

            # Find added, modified, deleted
            old_keys = set(old_entities.keys())
            new_keys = set(new_entities.keys())

            added_keys = new_keys - old_keys
            deleted_keys = old_keys - new_keys
            common_keys = old_keys & new_keys

            # Generate descriptions for each change
            for key in added_keys:
                slug = self._get_entity_slug(entity_type, new_entities[key])
                self.changes.append(f"+ {entity_type[:-1]} {slug}")

            for key in deleted_keys:
                slug = self._get_entity_slug(entity_type, old_entities[key])
                self.changes.append(f"- {entity_type[:-1]} {slug}")

            for key in common_keys:
                old_data = old_entities[key]
                new_data = new_entities[key]

                if old_data != new_data:
                    # Entity modified - describe what changed
                    slug = self._get_entity_slug(entity_type, new_data)
                    field_changes = self._describe_field_changes(old_data, new_data)
                    if field_changes:
                        change_desc = f"~ {entity_type[:-1]} {slug}: {field_changes}"
                        self.changes.append(change_desc)

        safe_logger(self.logger).log_debug(f"Generated {len(self.changes)} change descriptions")

    def _get_entity_slug(self, entity_type: str, entity_data: Dict[str, Any]) -> str:
        """
        Get human-readable slug for an entity.

        Args:
            entity_type: Type of entity (people, entries, etc.)
            entity_data: Entity JSON data

        Returns:
            Human-readable identifier
        """
        if entity_type == "entries":
            return entity_data.get("date", "unknown")
        elif entity_type == "people":
            return entity_data.get("slug", entity_data.get("name", "unknown"))
        elif entity_type == "locations":
            return entity_data.get("name", "unknown")
        elif entity_type == "scenes":
            return entity_data.get("name", "unknown")
        else:
            return (
                entity_data.get("name")
                or entity_data.get("title")
                or entity_data.get("slug")
                or "unknown"
            )

    def _describe_field_changes(self, old_data: Dict[str, Any], new_data: Dict[str, Any]) -> str:
        """
        Describe what fields changed between old and new entity data.

        Args:
            old_data: Old entity JSON
            new_data: New entity JSON

        Returns:
            Comma-separated list of field changes
        """
        changes = []

        # Compare all fields
        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in all_keys:
            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if old_val != new_val:
                # Describe the change
                if isinstance(old_val, list) and isinstance(new_val, list):
                    # Relationship list changes - show additions/removals
                    added = set(new_val) - set(old_val) if all(isinstance(v, str) for v in new_val + old_val) else set()
                    removed = set(old_val) - set(new_val) if all(isinstance(v, str) for v in new_val + old_val) else set()
                    if added:
                        changes.append(f"+{key} {list(added)}")
                    if removed:
                        changes.append(f"-{key} {list(removed)}")
                    if not added and not removed:
                        changes.append(f"~{key}")
                elif isinstance(old_val, list) or isinstance(new_val, list):
                    # List to non-list or vice versa
                    if old_val is None:
                        changes.append(f"+{key}")
                    elif new_val is None:
                        changes.append(f"-{key}")
                    else:
                        changes.append(f"~{key}")
                elif key in ["summary", "description", "content", "rating_justification"]:
                    # Text fields - just note changed
                    changes.append(f"~{key} [changed]")
                else:
                    # Primitive fields - show old→new
                    changes.append(f"~{key} {old_val}→{new_val}")

        return ", ".join(changes[:5])  # Limit to first 5 changes per entity

    def _write_exports(self, exports: Dict[str, Dict[str, Dict[str, Any]]]) -> None:
        """
        Write all JSON files to disk with proper directory structure and filenames.

        Implements design spec:
        - People: people/{first}_{last|disambig}.json
        - Locations: locations/{city}/{location}.json
        - Scenes: scenes/{YYYY-MM-DD}/{scene-name}.json
        - Entries: entries/{YYYY}/{YYYY-MM-DD}.json
        - Others: {entity_type}/{slug}.json

        Args:
            exports: All entity data keyed by natural keys
        """
        # Create base directories
        self.journal_dir.mkdir(parents=True, exist_ok=True)

        # Write each entity type with proper paths
        self._write_entries(exports.get("entries", {}))
        self._write_people(exports.get("people", {}))
        self._write_locations(exports.get("locations", {}))
        self._write_scenes(exports.get("scenes", {}))
        self._write_simple_entities("events", exports.get("events", {}))
        self._write_simple_entities("threads", exports.get("threads", {}))
        self._write_simple_entities("arcs", exports.get("arcs", {}))
        self._write_simple_entities("tags", exports.get("tags", {}))
        self._write_simple_entities("themes", exports.get("themes", {}))
        self._write_simple_entities("motifs", exports.get("motifs", {}))
        self._write_simple_entities("poems", exports.get("poems", {}))
        self._write_simple_entities("references", exports.get("references", {}))
        self._write_simple_entities("reference_sources", exports.get("reference_sources", {}))
        self._write_simple_entities("motif_instances", exports.get("motif_instances", {}))
        self._write_simple_entities("cities", exports.get("cities", {}))

        # Manuscript entities
        self._write_simple_entities("parts", exports.get("parts", {}))
        self._write_simple_entities("chapters", exports.get("chapters", {}))
        self._write_simple_entities("characters", exports.get("characters", {}))
        self._write_simple_entities("person_character_maps", exports.get("person_character_maps", {}))
        self._write_simple_entities("manuscript_scenes", exports.get("manuscript_scenes", {}))
        self._write_simple_entities("manuscript_sources", exports.get("manuscript_sources", {}))
        self._write_simple_entities("manuscript_references", exports.get("manuscript_references", {}))

    def _write_entries(self, entries: Dict[str, Dict[str, Any]]) -> None:
        """
        Write entries to entries/YYYY/YYYY-MM-DD.json.

        Args:
            entries: Dict mapping entry date to entry data
        """
        entries_dir = self.journal_dir / "entries"

        total = len(entries)
        for i, (key, entry_data) in enumerate(entries.items(), 1):
            try:
                entry_date = entry_data["date"]
                filepath = entries_dir / generate_entry_path(entry_date)
                filepath.parent.mkdir(parents=True, exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(entry_data, f, indent=2, ensure_ascii=False)

                # Progress feedback every 100 files
                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(f"   Writing entry files: {i}/{total}")

            except (KeyError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Failed to write entry {key}: {e}"
                )

    def _write_people(self, people: Dict[str, Dict[str, Any]]) -> None:
        """
        Write people to people/{first}_{last|disambig}.json.

        Args:
            people: Dict mapping person slug to person data
        """
        people_dir = self.journal_dir / "people"
        people_dir.mkdir(parents=True, exist_ok=True)

        total = len(people)
        for i, (slug, person_data) in enumerate(people.items(), 1):
            try:
                filename = generate_person_filename(
                    person_data["name"],
                    person_data.get("lastname"),
                    person_data.get("disambiguator"),
                )
                filepath = people_dir / filename

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(person_data, f, indent=2, ensure_ascii=False)

                # Progress feedback every 100 files
                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(f"   Writing people files: {i}/{total}")

            except ValueError as e:
                # Person violates lastname OR disambiguator requirement
                safe_logger(self.logger).log_warning(
                    f"Skipping person {slug} ({person_data['name']}): {e}"
                )

    def _write_locations(self, locations: Dict[str, Dict[str, Any]]) -> None:
        """
        Write locations to locations/{city}/{location}.json.

        Args:
            locations: Dict mapping location key to location data
        """
        locations_dir = self.journal_dir / "locations"

        total = len(locations)
        for i, (key, loc_data) in enumerate(locations.items(), 1):
            try:
                city_name = loc_data["city"]
                filepath = locations_dir / generate_location_path(city_name, loc_data["name"])
                filepath.parent.mkdir(parents=True, exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(loc_data, f, indent=2, ensure_ascii=False)

                # Progress feedback every 100 files
                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(f"   Writing location files: {i}/{total}")

            except (KeyError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Failed to write location {key}: {e}"
                )

    def _write_scenes(self, scenes: Dict[str, Dict[str, Any]]) -> None:
        """
        Write scenes to scenes/{YYYY-MM-DD}/{scene-name}.json.

        Args:
            scenes: Dict mapping scene key to scene data
        """
        scenes_dir = self.journal_dir / "scenes"

        total = len(scenes)
        for i, (key, scene_data) in enumerate(scenes.items(), 1):
            try:
                entry_date = scene_data["entry_date"]
                filepath = scenes_dir / generate_scene_path(entry_date, scene_data["name"])
                filepath.parent.mkdir(parents=True, exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(scene_data, f, indent=2, ensure_ascii=False)

                # Progress feedback every 100 files
                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(f"   Writing scene files: {i}/{total}")

            except (KeyError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Failed to write scene {key}: {e}"
                )

    def _write_simple_entities(self, entity_type: str, entities: Dict[str, Dict[str, Any]]) -> None:
        """
        Write entities with simple slug-based filenames.

        Uses the natural key (dict key) to generate filenames.

        Args:
            entity_type: Entity type name (used as directory)
            entities: Dict mapping natural key to entity data
        """
        entity_dir = self.journal_dir / entity_type
        entity_dir.mkdir(parents=True, exist_ok=True)

        for key, entity_data in entities.items():
            try:
                name = entity_data.get("name") or entity_data.get("title") or key
                filename = f"{slugify(str(name))}.json"
                filepath = entity_dir / filename

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(entity_data, f, indent=2, ensure_ascii=False)

            except (KeyError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Failed to write {entity_type} {key}: {e}"
                )

    def _write_readme(self) -> None:
        """
        Generate and write README.md with human-readable change log.

        Creates formatted README with:
        - Export timestamp
        - Entity counts
        - Categorized changes (added, modified, deleted)
        - Human-readable entity identifiers (natural keys)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Build header
        readme_content = f"""# Database Export Log

**Last Export:** {timestamp}
**Total Entities:** {sum(self.stats.values())} files exported

## Entity Counts

- **Entries:** {self.stats.get('entries', 0)}
- **People:** {self.stats.get('people', 0)}
- **Locations:** {self.stats.get('locations', 0)}
- **Cities:** {self.stats.get('cities', 0)}
- **Scenes:** {self.stats.get('scenes', 0)}
- **Events:** {self.stats.get('events', 0)}
- **Threads:** {self.stats.get('threads', 0)}
- **Arcs:** {self.stats.get('arcs', 0)}
- **Poems:** {self.stats.get('poems', 0)}
- **References:** {self.stats.get('references', 0)}
- **Tags:** {self.stats.get('tags', 0)}
- **Themes:** {self.stats.get('themes', 0)}
- **Motifs:** {self.stats.get('motifs', 0)}
- **Parts:** {self.stats.get('parts', 0)}
- **Chapters:** {self.stats.get('chapters', 0)}
- **Characters:** {self.stats.get('characters', 0)}

## Latest Changes

"""

        if not self.changes:
            readme_content += "*No changes since last export*\n"
        else:
            # Group changes by type (+, ~, -)
            added = [c for c in self.changes if c.startswith('+')]
            modified = [c for c in self.changes if c.startswith('~')]
            deleted = [c for c in self.changes if c.startswith('-')]

            if added:
                readme_content += "### Added\n"
                for change in added[:50]:  # Limit to 50 per category
                    readme_content += f"- {change}\n"
                if len(added) > 50:
                    readme_content += f"- ... and {len(added) - 50} more\n"
                readme_content += "\n"

            if modified:
                readme_content += "### Modified\n"
                for change in modified[:50]:
                    readme_content += f"- {change}\n"
                if len(modified) > 50:
                    readme_content += f"- ... and {len(modified) - 50} more\n"
                readme_content += "\n"

            if deleted:
                readme_content += "### Deleted\n"
                for change in deleted[:50]:
                    readme_content += f"- {change}\n"
                if len(deleted) > 50:
                    readme_content += f"- ... and {len(deleted) - 50} more\n"
                readme_content += "\n"

            # Summary
            readme_content += f"**Total Changes:** {len(added)} added, {len(modified)} modified, {len(deleted)} deleted\n"

        readme_path = self.output_dir / "README.md"
        readme_path.write_text(readme_content, encoding="utf-8")

        safe_logger(self.logger).log_info(f"README written: {len(self.changes)} changes documented")

    def _git_commit(self) -> None:
        """
        Create git commit for all export files.

        Checks for changes before committing to avoid errors.
        Provides clear user feedback about git status.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        commit_message = f"DB export - {timestamp}"

        try:
            # Stage all files in exports directory
            subprocess.run(
                ["git", "add", str(self.output_dir)],
                cwd=ROOT,
                check=True,
                capture_output=True,
            )

            # Check if there are any changes to commit
            status_result = subprocess.run(
                ["git", "status", "--porcelain", str(self.output_dir)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            if not status_result.stdout.strip():
                # No changes to commit
                safe_logger(self.logger).log_info("No changes to commit (exports unchanged)")
                return

            # Commit changes
            subprocess.run(
                ["git", "commit", "-m", commit_message],
                cwd=ROOT,
                check=True,
                capture_output=True,
            )

            safe_logger(self.logger).log_info(f"✅ Git commit created: {commit_message}")

        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            safe_logger(self.logger).log_error(
                Exception(f"Git commit failed: {error_msg}"),
                {"operation": "git_commit", "timestamp": timestamp}
            )
        except FileNotFoundError:
            safe_logger(self.logger).log_warning(
                "Git not found - skipping commit. Export files written but not committed."
            )
