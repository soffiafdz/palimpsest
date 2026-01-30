#!/usr/bin/env python3
"""
importer.py
-----------
Database import from narrative_analysis YAMLs.

This module provides the CurationImporter class which handles importing
narrative analysis YAML files into the database, using curated entity
mappings for consistent resolution.

Key Features:
    - Per-file transactions (each YAML = one commit)
    - Uses EntityResolver for person/location resolution
    - Fatal vs recoverable error handling with thresholds
    - --failed-only retry capability
    - Detailed statistics and failure tracking

Transaction Strategy:
    - Each YAML file is imported in a single transaction
    - Failures are logged to failed_imports.json for retry
    - Stop at 5 consecutive failures OR 5% failure rate

Validation:
    - Pre-import: Curation files must pass validation
    - During-import: Schema validation before transaction
    - Post-import: Integrity checks (counts, FK validity)

Usage:
    from dev.curation.importer import CurationImporter

    importer = CurationImporter(session, resolver)
    stats = importer.import_all(yaml_files)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import hashlib
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# --- Third-party imports ---
import yaml
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import LOG_DIR, MD_DIR
from dev.curation.models import FailedImport, ImportStats
from dev.curation.resolve import EntityResolver
from dev.database.models import (
    Arc,
    Entry,
    Event,
    Motif,
    MotifInstance,
    NarratedDate,
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
from dev.database.models.enums import ReferenceMode, ReferenceType


# =============================================================================
# Curation Importer
# =============================================================================

class CurationImporter:
    """
    Main importer class for database migration from narrative_analysis YAMLs.

    Handles loading YAML files, creating database entities, and managing
    transactions with proper error handling.

    Attributes:
        session: Database session
        resolver: EntityResolver with curated mappings
        dry_run: If True, don't commit changes
        stats: ImportStats tracking progress
        failed_imports: List of FailedImport records
        logger: PalimpsestLogger for operation tracking
    """

    def __init__(
        self,
        session: Session,
        resolver: EntityResolver,
        dry_run: bool = False,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the importer.

        Args:
            session: Database session
            resolver: Entity resolver with curated mappings
            dry_run: If True, don't commit changes
            logger: Optional logger for operation tracking
        """
        self.session = session
        self.resolver = resolver
        self.dry_run = dry_run
        self.stats = ImportStats()
        self.failed_imports: List[FailedImport] = []

        if logger is None:
            log_dir = LOG_DIR / "operations"
            log_dir.mkdir(parents=True, exist_ok=True)
            self.logger = PalimpsestLogger(log_dir, component_name="importer")
        else:
            self.logger = logger

        # In-memory caches for deduplication
        self._arcs: Dict[str, Arc] = {}
        self._tags: Dict[str, Tag] = {}
        self._themes: Dict[str, Theme] = {}
        self._motifs: Dict[str, Motif] = {}
        self._reference_sources: Dict[str, ReferenceSource] = {}
        self._poems: Dict[str, Poem] = {}

    def import_all(
        self, yaml_files: List[Path], failed_only: bool = False
    ) -> ImportStats:
        """
        Import all YAML files.

        Args:
            yaml_files: List of YAML file paths to import
            failed_only: If True, only retry previously failed imports

        Returns:
            ImportStats with results
        """
        self.stats.total_files = len(yaml_files)

        # Load failed imports if retrying
        failed_paths: Set[str] = set()
        if failed_only:
            failed_paths = self._load_failed_imports()
            if not failed_paths:
                self.logger.log_info("No failed imports to retry.")
                return self.stats

        for yaml_path in yaml_files:
            # Skip if not in failed list (when retrying)
            if failed_only and str(yaml_path) not in failed_paths:
                self.stats.skipped += 1
                continue

            # Check thresholds
            if self.stats.should_stop():
                self.logger.log_warning(
                    f"Stopping due to failure threshold: "
                    f"{self.stats.consecutive_failures} consecutive failures, "
                    f"{self.stats.failure_rate:.1%} failure rate"
                )
                break

            try:
                self._import_file(yaml_path)
                self.stats.succeeded += 1
                self.stats.consecutive_failures = 0
            except Exception as e:
                self.stats.failed += 1
                self.stats.consecutive_failures += 1
                self._record_failure(yaml_path, e)
                self.logger.log_error(f"FAILED {yaml_path.name}: {e}")

            self.stats.processed += 1

        # Save failed imports for retry
        if self.failed_imports:
            self._save_failed_imports()

        return self.stats

    def _import_file(self, yaml_path: Path) -> None:
        """
        Import a single YAML file.

        Args:
            yaml_path: Path to the narrative_analysis YAML file

        Raises:
            Various exceptions on failure (caught by import_all)
        """
        self.logger.log_info(f"Importing {yaml_path.name}...")

        # Load YAML
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data:
            raise ValueError("Empty YAML file")

        # Extract date from filename or data
        entry_date = self._parse_date(data.get("date"), yaml_path)

        # Find corresponding MD file
        md_path = self._find_md_file(entry_date)
        if not md_path:
            raise FileNotFoundError(f"No MD file for date {entry_date}")

        # Check if entry already exists
        existing = self.session.query(Entry).filter_by(date=entry_date).first()
        if existing:
            self.logger.log_info(f"  SKIPPED (exists)")
            self.stats.skipped += 1
            return

        # Create entry
        entry = self._create_entry(entry_date, md_path, data)

        # Create related entities
        self._create_scenes(entry, data.get("scenes", []))
        self._create_events(entry, data.get("events", []))
        self._create_threads(entry, data.get("threads", []))
        self._link_arcs(entry, data.get("arcs", []))
        self._link_tags(entry, data.get("tags", []))
        self._link_themes(entry, data.get("themes", []))
        self._create_motif_instances(entry, data.get("motifs", []))
        self._create_references(entry, data.get("references", []))
        self._create_poems(entry, data.get("poems", []))
        self._create_narrated_dates(entry, data)

        # Commit or rollback
        if self.dry_run:
            self.session.rollback()
            self.logger.log_info(f"  OK (dry-run)")
        else:
            self.session.commit()
            self.logger.log_info(f"  OK")
            self.stats.entries_created += 1

    def _parse_date(self, date_value: Any, yaml_path: Path) -> date:
        """
        Parse date from YAML data or filename.

        Args:
            date_value: Date value from YAML (may be date, str, or None)
            yaml_path: Path to YAML file (for fallback extraction)

        Returns:
            Parsed date object
        """
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, str):
            return date.fromisoformat(date_value)

        # Extract from filename: YYYY-MM-DD_analysis.yaml
        stem = yaml_path.stem
        date_str = stem.replace("_analysis", "")
        return date.fromisoformat(date_str)

    def _find_md_file(self, entry_date: date) -> Optional[Path]:
        """
        Find the MD file for a given date.

        Args:
            entry_date: Date of the entry

        Returns:
            Path to MD file, or None if not found
        """
        year_dir = MD_DIR / str(entry_date.year)
        md_path = year_dir / f"{entry_date.isoformat()}.md"
        if md_path.exists():
            return md_path
        return None

    def _compute_file_hash(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of file contents.

        Args:
            file_path: Path to file

        Returns:
            Hex-encoded hash string
        """
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def _compute_word_count(self, file_path: Path) -> int:
        """
        Count words in MD file (excluding frontmatter).

        Args:
            file_path: Path to MD file

        Returns:
            Word count
        """
        content = file_path.read_text(encoding="utf-8")

        # Remove frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        return len(content.split())

    def _create_entry(
        self, entry_date: date, md_path: Path, data: Dict
    ) -> Entry:
        """
        Create an Entry from YAML data.

        Args:
            entry_date: Date of the entry
            md_path: Path to corresponding MD file
            data: YAML data dict

        Returns:
            Created Entry entity
        """
        word_count = self._compute_word_count(md_path)
        reading_time = word_count / 250.0  # Average reading speed

        entry = Entry(
            date=entry_date,
            file_path=str(md_path.relative_to(MD_DIR.parent.parent)),
            file_hash=self._compute_file_hash(md_path),
            word_count=word_count,
            reading_time=reading_time,
            summary=data.get("summary"),
            rating=data.get("rating"),
            rating_justification=data.get("rating_justification"),
        )

        self.session.add(entry)
        self.session.flush()
        return entry

    def _create_scenes(self, entry: Entry, scenes_data: List[Dict]) -> None:
        """
        Create scenes for an entry.

        Args:
            entry: Parent Entry entity
            scenes_data: List of scene dicts from YAML
        """
        scene_map: Dict[str, Scene] = {}  # For event linking

        for scene_data in scenes_data or []:
            scene = Scene(
                name=scene_data.get("name", "Unnamed Scene"),
                description=scene_data.get("description", ""),
                entry_id=entry.id,
            )
            self.session.add(scene)
            self.session.flush()

            scene_map[scene.name] = scene
            self.stats.scenes_created += 1

            # Create scene dates
            scene_date = scene_data.get("date")
            if scene_date:
                if isinstance(scene_date, list):
                    for d in scene_date:
                        self._add_scene_date(scene, d)
                else:
                    self._add_scene_date(scene, scene_date)

            # Link people
            for person_name in scene_data.get("people", []) or []:
                for person in self.resolver.resolve_people(
                    str(person_name), self.session
                ):
                    if person not in scene.people:
                        scene.people.append(person)
                        self.stats.people_created += 1

            # Link locations
            for loc_name in scene_data.get("locations", []) or []:
                location = self.resolver.resolve_location(
                    str(loc_name), self.session
                )
                if location and location not in scene.locations:
                    scene.locations.append(location)
                    self.stats.locations_created += 1

        # Store scene map on entry for event creation
        entry._scene_map = scene_map  # type: ignore

    def _add_scene_date(self, scene: Scene, date_value: Any) -> None:
        """
        Add a date to a scene.

        Args:
            scene: Scene entity
            date_value: Date value (date or str)
        """
        if isinstance(date_value, date):
            scene_date = date_value
        elif isinstance(date_value, str):
            scene_date = date.fromisoformat(date_value)
        else:
            return

        sd = SceneDate(date=scene_date, scene_id=scene.id)
        self.session.add(sd)

    def _create_events(self, entry: Entry, events_data: List[Dict]) -> None:
        """
        Create events for an entry.

        Args:
            entry: Parent Entry entity
            events_data: List of event dicts from YAML
        """
        scene_map = getattr(entry, "_scene_map", {})

        for event_data in events_data or []:
            event = Event(
                name=event_data.get("name", "Unnamed Event"),
                entry_id=entry.id,
            )
            self.session.add(event)
            self.session.flush()
            self.stats.events_created += 1

            # Link scenes by name
            for scene_name in event_data.get("scenes", []) or []:
                scene = scene_map.get(scene_name)
                if scene and scene not in event.scenes:
                    event.scenes.append(scene)

    def _create_threads(self, entry: Entry, threads_data: List[Dict]) -> None:
        """
        Create threads for an entry.

        Args:
            entry: Parent Entry entity
            threads_data: List of thread dicts from YAML
        """
        for thread_data in threads_data or []:
            # Parse from_date
            from_date_val = thread_data.get("from")
            if isinstance(from_date_val, date):
                from_date = from_date_val
            elif isinstance(from_date_val, str):
                from_date = date.fromisoformat(from_date_val)
            else:
                continue

            # Parse to_date (stored as string)
            to_date_val = thread_data.get("to", "")
            if isinstance(to_date_val, date):
                to_date_str = to_date_val.isoformat()
            else:
                to_date_str = str(to_date_val)

            # Parse referenced entry date
            ref_entry_val = thread_data.get("entry")
            ref_entry_date = None
            if isinstance(ref_entry_val, date):
                ref_entry_date = ref_entry_val
            elif isinstance(ref_entry_val, str):
                try:
                    ref_entry_date = date.fromisoformat(ref_entry_val)
                except ValueError:
                    pass

            thread = Thread(
                name=thread_data.get("name", "Unnamed Thread"),
                from_date=from_date,
                to_date=to_date_str,
                referenced_entry_date=ref_entry_date,
                content=thread_data.get("content", ""),
                entry_id=entry.id,
            )
            self.session.add(thread)
            self.session.flush()
            self.stats.threads_created += 1

            # Link people
            for person_name in thread_data.get("people", []) or []:
                for person in self.resolver.resolve_people(
                    str(person_name), self.session
                ):
                    if person not in thread.people:
                        thread.people.append(person)

            # Link locations
            for loc_name in thread_data.get("locations", []) or []:
                location = self.resolver.resolve_location(
                    str(loc_name), self.session
                )
                if location and location not in thread.locations:
                    thread.locations.append(location)

    def _link_arcs(self, entry: Entry, arcs_data: List[str]) -> None:
        """
        Link arcs to an entry.

        Args:
            entry: Entry entity
            arcs_data: List of arc names
        """
        for arc_name in arcs_data or []:
            arc = self._get_or_create_arc(arc_name)
            if arc not in entry.arcs:
                entry.arcs.append(arc)

    def _get_or_create_arc(self, name: str) -> Arc:
        """
        Get or create an arc by name.

        Args:
            name: Arc name

        Returns:
            Arc entity
        """
        key = name.lower()
        if key in self._arcs:
            return self._arcs[key]

        arc = self.session.query(Arc).filter_by(name=name).first()
        if not arc:
            arc = Arc(name=name)
            self.session.add(arc)
            self.session.flush()
            self.stats.arcs_created += 1

        self._arcs[key] = arc
        return arc

    def _link_tags(self, entry: Entry, tags_data: List[str]) -> None:
        """
        Link tags to an entry.

        Args:
            entry: Entry entity
            tags_data: List of tag names
        """
        for tag_name in tags_data or []:
            tag = self._get_or_create_tag(tag_name)
            if tag not in entry.tags:
                entry.tags.append(tag)

    def _get_or_create_tag(self, name: str) -> Tag:
        """
        Get or create a tag by name.

        Args:
            name: Tag name

        Returns:
            Tag entity
        """
        key = name.lower()
        if key in self._tags:
            return self._tags[key]

        tag = self.session.query(Tag).filter_by(name=name).first()
        if not tag:
            tag = Tag(name=name)
            self.session.add(tag)
            self.session.flush()
            self.stats.tags_created += 1

        self._tags[key] = tag
        return tag

    def _link_themes(self, entry: Entry, themes_data: List[str]) -> None:
        """
        Link themes to an entry.

        Args:
            entry: Entry entity
            themes_data: List of theme names
        """
        for theme_name in themes_data or []:
            theme = self._get_or_create_theme(theme_name)
            if theme not in entry.themes:
                entry.themes.append(theme)

    def _get_or_create_theme(self, name: str) -> Theme:
        """
        Get or create a theme by name.

        Args:
            name: Theme name

        Returns:
            Theme entity
        """
        key = name.lower()
        if key in self._themes:
            return self._themes[key]

        theme = self.session.query(Theme).filter_by(name=name).first()
        if not theme:
            theme = Theme(name=name)
            self.session.add(theme)
            self.session.flush()
            self.stats.themes_created += 1

        self._themes[key] = theme
        return theme

    def _create_motif_instances(
        self, entry: Entry, motifs_data: List[Dict]
    ) -> None:
        """
        Create motif instances for an entry.

        Args:
            entry: Entry entity
            motifs_data: List of motif dicts
        """
        for motif_data in motifs_data or []:
            motif_name = motif_data.get("name")
            description = motif_data.get("description", "")

            if not motif_name or not description:
                continue

            motif = self._get_or_create_motif(motif_name)

            instance = MotifInstance(
                motif_id=motif.id,
                entry_id=entry.id,
                description=description,
            )
            self.session.add(instance)

    def _get_or_create_motif(self, name: str) -> Motif:
        """
        Get or create a motif by name.

        Args:
            name: Motif name

        Returns:
            Motif entity
        """
        key = name.lower()
        if key in self._motifs:
            return self._motifs[key]

        motif = self.session.query(Motif).filter_by(name=name).first()
        if not motif:
            motif = Motif(name=name)
            self.session.add(motif)
            self.session.flush()
            self.stats.motifs_created += 1

        self._motifs[key] = motif
        return motif

    def _create_references(self, entry: Entry, refs_data: List[Dict]) -> None:
        """
        Create references for an entry.

        Args:
            entry: Entry entity
            refs_data: List of reference dicts
        """
        for ref_data in refs_data or []:
            # Handle nested source structure
            source_data = ref_data.get("source", {})
            if isinstance(source_data, str):
                # Simple string reference
                source_data = {"title": source_data}

            title = source_data.get("title")
            if not title:
                continue

            source = self._get_or_create_reference_source(source_data)

            # Parse mode
            mode_str = ref_data.get("mode", "direct")
            try:
                mode = ReferenceMode(mode_str)
            except ValueError:
                mode = ReferenceMode.DIRECT

            reference = Reference(
                entry_id=entry.id,
                source_id=source.id,
                content=ref_data.get("content"),
                description=ref_data.get("description"),
                mode=mode,
            )
            self.session.add(reference)
            self.stats.references_created += 1

    def _get_or_create_reference_source(
        self, source_data: Dict[str, Any]
    ) -> ReferenceSource:
        """
        Get or create a reference source.

        Args:
            source_data: Source dict with title, author, type, url

        Returns:
            ReferenceSource entity
        """
        title = source_data.get("title", "")
        key = title.lower()

        if key in self._reference_sources:
            return self._reference_sources[key]

        source = self.session.query(ReferenceSource).filter_by(title=title).first()
        if not source:
            # Parse type
            type_str = source_data.get("type", "book")
            try:
                ref_type = ReferenceType(type_str)
            except ValueError:
                ref_type = ReferenceType.BOOK

            source = ReferenceSource(
                title=title,
                author=source_data.get("author"),
                type=ref_type,
                url=source_data.get("url"),
            )
            self.session.add(source)
            self.session.flush()

        self._reference_sources[key] = source
        return source

    def _create_poems(self, entry: Entry, poems_data: List[Dict]) -> None:
        """
        Create poems for an entry.

        Args:
            entry: Entry entity
            poems_data: List of poem dicts
        """
        for poem_data in poems_data or []:
            title = poem_data.get("title")
            content = poem_data.get("content")

            if not title or not content:
                continue

            poem = self._get_or_create_poem(title)

            version = PoemVersion(
                poem_id=poem.id,
                entry_id=entry.id,
                content=content,
            )
            self.session.add(version)

    def _get_or_create_poem(self, title: str) -> Poem:
        """
        Get or create a poem by title.

        Args:
            title: Poem title

        Returns:
            Poem entity
        """
        key = title.lower()

        if key in self._poems:
            return self._poems[key]

        poem = self.session.query(Poem).filter_by(title=title).first()
        if not poem:
            poem = Poem(title=title)
            self.session.add(poem)
            self.session.flush()
            self.stats.poems_created += 1

        self._poems[key] = poem
        return poem

    def _create_narrated_dates(self, entry: Entry, data: Dict) -> None:
        """
        Create narrated dates from scene dates.

        Args:
            entry: Entry entity
            data: Full YAML data dict
        """
        narrated: Set[date] = set()

        for scene_data in data.get("scenes", []) or []:
            scene_date = scene_data.get("date")
            if scene_date:
                if isinstance(scene_date, list):
                    for d in scene_date:
                        if isinstance(d, date):
                            narrated.add(d)
                        elif isinstance(d, str):
                            try:
                                narrated.add(date.fromisoformat(d))
                            except ValueError:
                                pass
                elif isinstance(scene_date, date):
                    narrated.add(scene_date)
                elif isinstance(scene_date, str):
                    try:
                        narrated.add(date.fromisoformat(scene_date))
                    except ValueError:
                        pass

        for d in sorted(narrated):
            nd = NarratedDate(date=d, entry_id=entry.id)
            self.session.add(nd)

    def _record_failure(self, yaml_path: Path, error: Exception) -> None:
        """
        Record a failed import.

        Args:
            yaml_path: Path to the failed file
            error: Exception that occurred
        """
        self.failed_imports.append(
            FailedImport(
                file_path=str(yaml_path),
                error_type=type(error).__name__,
                error_message=str(error),
            )
        )

    def _load_failed_imports(self) -> Set[str]:
        """
        Load previously failed imports.

        Returns:
            Set of file paths that previously failed
        """
        failed_file = LOG_DIR / "jumpstart" / "failed_imports.json"
        if not failed_file.exists():
            return set()

        with open(failed_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        return {item["file_path"] for item in data.get("failures", [])}

    def _save_failed_imports(self) -> None:
        """Save failed imports for retry."""
        log_dir = LOG_DIR / "jumpstart"
        log_dir.mkdir(parents=True, exist_ok=True)

        failed_file = log_dir / "failed_imports.json"

        data = {
            "timestamp": datetime.now().isoformat(),
            "total_failures": len(self.failed_imports),
            "failures": [f.to_dict() for f in self.failed_imports],
        }

        with open(failed_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        self.logger.log_info(f"Failed imports saved to {failed_file}")
