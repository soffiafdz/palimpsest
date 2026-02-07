#!/usr/bin/env python3
"""
export_json.py
--------------
Export database entities to JSON files for version control and cross-machine sync.

This module exports database entities to individual JSON files organized by entity type.
Unlike metadata YAML files (human-authored, per-entry ground truth), these JSON exports
are machine-generated, machine-focused files using IDs for relationships.

Key Features:
    - One JSON file per entity instance (not per entry)
    - ID-based relationships (no slug generation needed)
    - Unidirectional relationship storage (zero redundancy)
    - README.md with human-readable change log
    - Single git commit per export with detailed README
    - Fast JSON parsing and compact file size

Architecture:
    - Entry owns: people, locations, cities, tags, themes, arcs, scenes, events, threads
    - Scene owns: people, locations, dates
    - Event owns: scenes
    - Thread owns: people, locations, referenced_entry
    - Entities don't store back-references (derived on import)

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

    def _export_all_entities(self) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """
        Export all entities to in-memory JSON structures.

        Returns:
            Nested dict: {entity_type: {entity_id: json_data}}
        """
        exports = {}

        with self.db.session_scope() as session:
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

    def _export_entries(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all entries with their owned relationships."""
        entries = session.query(Entry).all()
        result = {}
        total = len(entries)

        for i, entry in enumerate(entries, 1):
            result[entry.id] = {
                "id": entry.id,
                "date": entry.date.isoformat(),
                "file_path": entry.file_path,
                "file_hash": entry.file_hash,
                "metadata_hash": entry.metadata_hash,
                "word_count": entry.word_count,
                "reading_time": entry.reading_time,
                "summary": entry.summary,
                "rating": float(entry.rating) if entry.rating else None,
                "rating_justification": entry.rating_justification,
                # Owned relationships (IDs only)
                "people_ids": [p.id for p in entry.people],
                "location_ids": [loc.id for loc in entry.locations],
                "city_ids": [c.id for c in entry.cities],
                "arc_ids": [a.id for a in entry.arcs],
                "tag_ids": [t.id for t in entry.tags],
                "theme_ids": [th.id for th in entry.themes],
                "scene_ids": [s.id for s in entry.scenes],
                "event_ids": [e.id for e in entry.events],
                "thread_ids": [th.id for th in entry.threads],
                "poem_ids": [pv.id for pv in entry.poems],
                "reference_ids": [r.id for r in entry.references],
                "motif_instance_ids": [mi.id for mi in entry.motif_instances],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting entries: {i}/{total}")

        self.stats["entries"] = len(result)
        return result

    def _export_people(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all people (no back-references to entries)."""
        people = session.query(Person).all()
        result = {}
        total = len(people)

        for i, person in enumerate(people, 1):
            result[person.id] = {
                "id": person.id,
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

    def _export_locations(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all locations."""
        locations = session.query(Location).all()
        result = {}
        total = len(locations)

        for i, loc in enumerate(locations, 1):
            result[loc.id] = {
                "id": loc.id,
                "name": loc.name,
                "city_id": loc.city_id,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting locations: {i}/{total}")

        self.stats["locations"] = len(result)
        return result

    def _export_cities(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all cities."""
        cities = session.query(City).all()
        result = {}

        for city in cities:
            result[city.id] = {
                "id": city.id,
                "name": city.name,
                "country": city.country,
            }

        self.stats["cities"] = len(result)
        return result

    def _export_scenes(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all scenes with their owned relationships."""
        scenes = session.query(Scene).all()
        result = {}
        total = len(scenes)

        for i, scene in enumerate(scenes, 1):
            # Get scene dates (already strings in flexible format)
            dates = [sd.date for sd in scene.dates]

            result[scene.id] = {
                "id": scene.id,
                "name": scene.name,
                "description": scene.description,
                "entry_id": scene.entry_id,
                "dates": dates,
                "people_ids": [p.id for p in scene.people],
                "location_ids": [loc.id for loc in scene.locations],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting scenes: {i}/{total}")

        self.stats["scenes"] = len(result)
        return result

    def _export_events(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all events with their owned relationships."""
        events = session.query(Event).all()
        result = {}
        total = len(events)

        for i, event in enumerate(events, 1):
            result[event.id] = {
                "id": event.id,
                "name": event.name,
                "scene_ids": [s.id for s in event.scenes],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting events: {i}/{total}")

        self.stats["events"] = len(result)
        return result

    def _export_threads(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all threads with their owned relationships."""
        threads = session.query(Thread).all()
        result = {}
        total = len(threads)

        for i, thread in enumerate(threads, 1):
            result[thread.id] = {
                "id": thread.id,
                "name": thread.name,
                "from_date": thread.from_date,  # Already a string (supports ~YYYY, ~YYYY-MM, YYYY-MM-DD)
                "to_date": thread.to_date,  # Already a string (YYYY, YYYY-MM, or YYYY-MM-DD)
                "referenced_entry_date": (
                    thread.referenced_entry_date.isoformat()
                    if thread.referenced_entry_date
                    else None
                ),
                "content": thread.content,
                "entry_id": thread.entry_id,
                "people_ids": [p.id for p in thread.people],
                "location_ids": [loc.id for loc in thread.locations],
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting threads: {i}/{total}")

        self.stats["threads"] = len(result)
        return result

    def _export_arcs(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all arcs."""
        arcs = session.query(Arc).all()
        result = {}

        for arc in arcs:
            result[arc.id] = {
                "id": arc.id,
                "name": arc.name,
                "description": arc.description,
            }

        self.stats["arcs"] = len(result)
        return result

    def _export_poems(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all poem versions."""
        poem_versions = session.query(PoemVersion).all()
        result = {}
        total = len(poem_versions)

        for i, pv in enumerate(poem_versions, 1):
            result[pv.id] = {
                "id": pv.id,
                "content": pv.content,
                "poem_id": pv.poem_id,
                "entry_id": pv.entry_id,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting poems: {i}/{total}")

        self.stats["poems"] = len(result)
        return result

    def _export_references(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all references."""
        references = session.query(Reference).all()
        result = {}
        total = len(references)

        for i, ref in enumerate(references, 1):
            result[ref.id] = {
                "id": ref.id,
                "content": ref.content,
                "description": ref.description,
                "mode": ref.mode.value if ref.mode else None,
                "source_id": ref.source_id,
                "entry_id": ref.entry_id,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting references: {i}/{total}")

        self.stats["references"] = len(result)
        return result

    def _export_reference_sources(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all reference sources."""
        sources = session.query(ReferenceSource).all()
        result = {}

        for source in sources:
            result[source.id] = {
                "id": source.id,
                "title": source.title,
                "author": source.author,
                "type": source.type.value if source.type else None,
                "url": source.url,
            }

        self.stats["reference_sources"] = len(result)
        return result

    def _export_tags(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all tags."""
        tags = session.query(Tag).all()
        result = {}

        for tag in tags:
            result[tag.id] = {
                "id": tag.id,
                "name": tag.name,
            }

        self.stats["tags"] = len(result)
        return result

    def _export_themes(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all themes."""
        themes = session.query(Theme).all()
        result = {}

        for theme in themes:
            result[theme.id] = {
                "id": theme.id,
                "name": theme.name,
            }

        self.stats["themes"] = len(result)
        return result

    def _export_motifs(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all motifs."""
        motifs = session.query(Motif).all()
        result = {}

        for motif in motifs:
            result[motif.id] = {
                "id": motif.id,
                "name": motif.name,
            }

        self.stats["motifs"] = len(result)
        return result

    def _export_motif_instances(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all motif instances."""
        instances = session.query(MotifInstance).all()
        result = {}
        total = len(instances)

        for i, mi in enumerate(instances, 1):
            result[mi.id] = {
                "id": mi.id,
                "description": mi.description,
                "motif_id": mi.motif_id,
                "entry_id": mi.entry_id,
            }

            # Progress feedback every 100 entities
            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(f"   Exporting motif instances: {i}/{total}")

        self.stats["motif_instances"] = len(result)
        return result

    # =========================================================================
    # MANUSCRIPT ENTITY EXPORT METHODS
    # =========================================================================

    def _export_parts(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all parts."""
        parts = session.query(Part).all()
        result = {}

        for part in parts:
            result[part.id] = {
                "id": part.id,
                "number": part.number,
                "title": part.title,
            }

        self.stats["parts"] = len(result)
        return result

    def _export_chapters(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all chapters with type/status enums and relationship IDs."""
        chapters = session.query(Chapter).all()
        result = {}

        for chapter in chapters:
            result[chapter.id] = {
                "id": chapter.id,
                "title": chapter.title,
                "number": chapter.number,
                "part_id": chapter.part_id,
                "type": chapter.type.value if chapter.type else None,
                "status": chapter.status.value if chapter.status else None,
                "content": chapter.content,
                "draft_path": chapter.draft_path,
                "poem_ids": [p.id for p in chapter.poems],
                "character_ids": [c.id for c in chapter.characters],
                "arc_ids": [a.id for a in chapter.arcs],
            }

        self.stats["chapters"] = len(result)
        return result

    def _export_characters(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all characters."""
        characters = session.query(Character).all()
        result = {}

        for char in characters:
            result[char.id] = {
                "id": char.id,
                "name": char.name,
                "description": char.description,
                "role": char.role,
                "is_narrator": char.is_narrator,
            }

        self.stats["characters"] = len(result)
        return result

    def _export_person_character_maps(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all person-character mappings."""
        mappings = session.query(PersonCharacterMap).all()
        result = {}

        for mapping in mappings:
            result[mapping.id] = {
                "id": mapping.id,
                "person_id": mapping.person_id,
                "character_id": mapping.character_id,
                "contribution": mapping.contribution.value if mapping.contribution else None,
                "notes": mapping.notes,
            }

        self.stats["person_character_maps"] = len(result)
        return result

    def _export_manuscript_scenes(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all manuscript scenes with origin/status enums."""
        scenes = session.query(ManuscriptScene).all()
        result = {}

        for scene in scenes:
            result[scene.id] = {
                "id": scene.id,
                "name": scene.name,
                "description": scene.description,
                "chapter_id": scene.chapter_id,
                "origin": scene.origin.value if scene.origin else None,
                "status": scene.status.value if scene.status else None,
                "notes": scene.notes,
            }

        self.stats["manuscript_scenes"] = len(result)
        return result

    def _export_manuscript_sources(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all manuscript sources with source_type polymorphism."""
        sources = session.query(ManuscriptSource).all()
        result = {}

        for source in sources:
            result[source.id] = {
                "id": source.id,
                "manuscript_scene_id": source.manuscript_scene_id,
                "source_type": source.source_type.value if source.source_type else None,
                "scene_id": source.scene_id,
                "entry_id": source.entry_id,
                "thread_id": source.thread_id,
                "external_note": source.external_note,
                "notes": source.notes,
            }

        self.stats["manuscript_sources"] = len(result)
        return result

    def _export_manuscript_references(self, session: Session) -> Dict[int, Dict[str, Any]]:
        """Export all manuscript references with mode enum."""
        refs = session.query(ManuscriptReference).all()
        result = {}

        for ref in refs:
            result[ref.id] = {
                "id": ref.id,
                "chapter_id": ref.chapter_id,
                "source_id": ref.source_id,
                "mode": ref.mode.value if ref.mode else None,
                "content": ref.content,
                "notes": ref.notes,
            }

        self.stats["manuscript_references"] = len(result)
        return result

    # =========================================================================
    # FILE OPERATIONS
    # =========================================================================

    def _load_existing_exports(self) -> Dict[str, Dict[int, Dict[str, Any]]]:
        """
        Load existing JSON files from disk for comparison.

        Scans data/exports/journal/ directory tree and loads all JSON files.
        Returns same structure as _export_all_entities for easy comparison.

        Returns:
            Nested dict: {entity_type: {entity_id: json_data}}
        """
        old_exports: Dict[str, Dict[int, Dict[str, Any]]] = {}

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

                # Get entity ID from JSON data
                entity_id = data.get("id")
                if entity_id is None:
                    safe_logger(self.logger).log_warning(f"Skipping {json_file}: no 'id' field")
                    continue

                # Store in structure
                if entity_type in old_exports:
                    old_exports[entity_type][entity_id] = data
                else:
                    safe_logger(self.logger).log_warning(f"Unknown entity type: {entity_type}")

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                safe_logger(self.logger).log_warning(f"Skipping corrupted file {json_file}: {e}")
                continue

        safe_logger(self.logger).log_debug(
            f"Loaded {sum(len(entities) for entities in old_exports.values())} existing entities"
        )

        return old_exports

    def _generate_changes(
        self,
        old_exports: Dict[str, Dict[int, Dict[str, Any]]],
        new_exports: Dict[str, Dict[int, Dict[str, Any]]],
    ) -> None:
        """
        Generate human-readable change descriptions by comparing old and new.

        Compares entity data and generates formatted change strings:
        - + entity added
        - ~ entity modified (with field changes)
        - - entity deleted

        Populates self.changes list with formatted change strings.
        """
        safe_logger(self.logger).log_debug("Generating change descriptions")

        # Track changes by entity type
        for entity_type in new_exports.keys():
            old_entities = old_exports.get(entity_type, {})
            new_entities = new_exports[entity_type]

            # Find added, modified, deleted
            old_ids = set(old_entities.keys())
            new_ids = set(new_entities.keys())

            added_ids = new_ids - old_ids
            deleted_ids = old_ids - new_ids
            common_ids = old_ids & new_ids

            # Generate descriptions for each change
            for entity_id in added_ids:
                entity_data = new_entities[entity_id]
                slug = self._get_entity_slug(entity_type, entity_data)
                self.changes.append(f"+ {entity_type[:-1]} {slug} (id={entity_id})")

            for entity_id in deleted_ids:
                entity_data = old_entities[entity_id]
                slug = self._get_entity_slug(entity_type, entity_data)
                self.changes.append(f"- {entity_type[:-1]} {slug} (id={entity_id})")

            for entity_id in common_ids:
                old_data = old_entities[entity_id]
                new_data = new_entities[entity_id]

                if old_data != new_data:
                    # Entity modified - describe what changed
                    slug = self._get_entity_slug(entity_type, new_data)
                    field_changes = self._describe_field_changes(old_data, new_data)
                    if field_changes:
                        change_desc = f"~ {entity_type[:-1]} {slug} (id={entity_id}): {field_changes}"
                        self.changes.append(change_desc)

        safe_logger(self.logger).log_debug(f"Generated {len(self.changes)} change descriptions")

    def _get_entity_slug(self, entity_type: str, entity_data: Dict[str, Any]) -> str:
        """
        Get human-readable slug for an entity.

        Args:
            entity_type: Type of entity (people, entries, etc.)
            entity_data: Entity JSON data

        Returns:
            Human-readable identifier (slug or date)
        """
        if entity_type == "entries":
            return entity_data["date"]
        elif entity_type == "people":
            # Use same logic as filename generation
            try:
                filename = generate_person_filename(
                    entity_data["name"],
                    entity_data.get("lastname"),
                    entity_data.get("disambiguator"),
                    entity_data["id"]
                )
                return filename.replace(".json", "")
            except ValueError:
                return entity_data["name"]
        elif entity_type == "locations":
            return entity_data["name"]
        elif entity_type == "scenes":
            return entity_data["name"]
        else:
            # Use name or title field
            return entity_data.get("name") or entity_data.get("title") or f"id-{entity_data['id']}"

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
            if key == "id":
                continue  # ID never changes

            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if old_val != new_val:
                # Describe the change
                if key.endswith("_ids") or key.endswith("_id"):
                    # Relationship changes - show additions/removals
                    if isinstance(old_val, list) and isinstance(new_val, list):
                        added = set(new_val) - set(old_val)
                        removed = set(old_val) - set(new_val)
                        if added:
                            changes.append(f"+{key} {list(added)}")
                        if removed:
                            changes.append(f"-{key} {list(removed)}")
                    elif old_val is None:
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

    def _write_exports(self, exports: Dict[str, Dict[int, Dict[str, Any]]]) -> None:
        """
        Write all JSON files to disk with proper directory structure and filenames.

        Implements design spec:
        - People: people/{first}_{last|disambig}.json
        - Locations: locations/{city}/{location}.json
        - Scenes: scenes/{YYYY-MM-DD}/{scene-name}.json
        - Entries: entries/{YYYY}/{YYYY-MM-DD}.json
        - Others: {entity_type}/{slug}.json
        """
        # Create base directories
        self.journal_dir.mkdir(parents=True, exist_ok=True)

        # Write each entity type with proper paths
        self._write_entries(exports.get("entries", {}))
        self._write_people(exports.get("people", {}))
        self._write_locations(exports.get("locations", {}), exports.get("cities", {}))
        self._write_scenes(exports.get("scenes", {}), exports.get("entries", {}))
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

    def _write_entries(self, entries: Dict[int, Dict[str, Any]]) -> None:
        """Write entries to entries/YYYY/YYYY-MM-DD.json"""
        entries_dir = self.journal_dir / "entries"

        total = len(entries)
        for i, entry_data in enumerate(entries.values(), 1):
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
                    f"Failed to write entry {entry_data.get('id', 'unknown')}: {e}"
                )

    def _write_people(self, people: Dict[int, Dict[str, Any]]) -> None:
        """Write people to people/{first}_{last|disambig}.json"""
        people_dir = self.journal_dir / "people"
        people_dir.mkdir(parents=True, exist_ok=True)

        total = len(people)
        for i, person_data in enumerate(people.values(), 1):
            try:
                filename = generate_person_filename(
                    person_data["name"],
                    person_data.get("lastname"),
                    person_data.get("disambiguator"),
                    person_data["id"]
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
                    f"Skipping person {person_data['id']} ({person_data['name']}): {e}"
                )

    def _write_locations(self, locations: Dict[int, Dict[str, Any]], cities: Dict[int, Dict[str, Any]]) -> None:
        """Write locations to locations/{city}/{location}.json"""
        locations_dir = self.journal_dir / "locations"

        # Build city ID to name lookup
        city_names = {city_data["id"]: city_data["name"] for city_data in cities.values()}

        total = len(locations)
        for i, loc_data in enumerate(locations.values(), 1):
            try:
                city_id = loc_data["city_id"]
                city_name = city_names.get(city_id, "unknown-city")

                filepath = locations_dir / generate_location_path(city_name, loc_data["name"])
                filepath.parent.mkdir(parents=True, exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(loc_data, f, indent=2, ensure_ascii=False)

                # Progress feedback every 100 files
                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(f"   Writing location files: {i}/{total}")

            except (KeyError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Failed to write location {loc_data.get('id', 'unknown')}: {e}"
                )

    def _write_scenes(self, scenes: Dict[int, Dict[str, Any]], entries: Dict[int, Dict[str, Any]]) -> None:
        """Write scenes to scenes/{YYYY-MM-DD}/{scene-name}.json"""
        scenes_dir = self.journal_dir / "scenes"

        # Build entry ID to date lookup
        entry_dates = {entry_data["id"]: entry_data["date"] for entry_data in entries.values()}

        total = len(scenes)
        for i, scene_data in enumerate(scenes.values(), 1):
            try:
                entry_id = scene_data["entry_id"]
                entry_date = entry_dates.get(entry_id, "unknown-date")

                filepath = scenes_dir / generate_scene_path(entry_date, scene_data["name"])
                filepath.parent.mkdir(parents=True, exist_ok=True)

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(scene_data, f, indent=2, ensure_ascii=False)

                # Progress feedback every 100 files
                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(f"   Writing scene files: {i}/{total}")

            except (KeyError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Failed to write scene {scene_data.get('id', 'unknown')}: {e}"
                )

    def _write_simple_entities(self, entity_type: str, entities: Dict[int, Dict[str, Any]]) -> None:
        """Write entities with simple slug-based filenames."""
        entity_dir = self.journal_dir / entity_type
        entity_dir.mkdir(parents=True, exist_ok=True)

        for entity_data in entities.values():
            try:
                name = entity_data.get("name") or entity_data.get("title") or str(entity_data["id"])
                filename = f"{slugify(name)}.json"
                filepath = entity_dir / filename

                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(entity_data, f, indent=2, ensure_ascii=False)

            except (KeyError, OSError) as e:
                safe_logger(self.logger).log_warning(
                    f"Failed to write {entity_type} {entity_data.get('id', 'unknown')}: {e}"
                )

    def _write_readme(self) -> None:
        """
        Generate and write README.md with human-readable change log.

        Creates formatted README with:
        - Export timestamp
        - Entity counts
        - Categorized changes (added, modified, deleted)
        - Human-readable entity identifiers (slugs, not IDs)
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
