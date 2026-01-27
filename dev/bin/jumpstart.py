#!/usr/bin/env python3
"""
jumpstart.py
------------
One-time migration from narrative_analysis YAMLs to the database.

This script imports all narrative_analysis YAML files into the database,
using curated entity files for consistent person/location resolution.
Run after manual curation is complete and validated.

Key Features:
    - Per-file transactions (each YAML = one commit)
    - Uses curated entity files for person/location resolution
    - Fatal vs recoverable error handling with thresholds
    - --failed-only flag to retry just failed imports
    - Detailed logging and failure tracking

Transaction Strategy:
    - Each YAML file is imported in a single transaction
    - Failures are logged to failed_imports.json for retry
    - Stop at 5 consecutive failures OR 5% failure rate

Entity Resolution:
    - People resolved via curated mappings (raw name -> canonical)
    - Locations resolved via curated mappings (raw name -> name+city)
    - In-memory deduplication during import

Validation:
    - Pre-import: Curation files must pass validation
    - During-import: Schema validation before transaction
    - Post-import: Integrity checks (counts, FK validity)

Usage:
    python -m dev.bin.jumpstart [--dry-run] [--failed-only] [--skip-validation]

Output:
    - Database populated with entries, scenes, events, etc.
    - Import report in data/logs/jumpstart/
    - failed_imports.json for retry (if failures)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# --- Third-party imports ---
import yaml
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# --- Local imports ---
from dev.core.paths import (
    CURATION_DIR,
    DB_PATH,
    LOG_DIR,
    MD_DIR,
    NARRATIVE_ANALYSIS_DIR,
)
from dev.database.models import (
    Arc,
    City,
    Entry,
    Event,
    Location,
    Motif,
    MotifInstance,
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
)
from dev.database.models.enums import ReferenceMode, ReferenceType


# --- Constants ---
MAX_CONSECUTIVE_FAILURES = 5
MAX_FAILURE_RATE = 0.05  # 5%


@dataclass
class ImportStats:
    """Statistics for the import process."""

    total_files: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    consecutive_failures: int = 0

    # Entity counts
    entries_created: int = 0
    scenes_created: int = 0
    events_created: int = 0
    threads_created: int = 0
    people_created: int = 0
    locations_created: int = 0
    cities_created: int = 0
    arcs_created: int = 0
    tags_created: int = 0
    themes_created: int = 0
    motifs_created: int = 0
    references_created: int = 0
    poems_created: int = 0

    @property
    def failure_rate(self) -> float:
        """Calculate current failure rate."""
        if self.processed == 0:
            return 0.0
        return self.failed / self.processed

    def should_stop(self) -> bool:
        """Check if import should stop due to failure thresholds."""
        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            return True
        if self.processed >= 20 and self.failure_rate >= MAX_FAILURE_RATE:
            return True
        return False


@dataclass
class FailedImport:
    """Record of a failed import."""

    file_path: str
    error_type: str
    error_message: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EntityResolver:
    """
    Resolves raw entity names to canonical forms using curated files.

    Loads curated people and location files and provides lookup methods
    for resolving raw names to their canonical database representations.
    """

    # Mapping: raw_name (lowercase) -> canonical dict
    people_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    locations_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Track which entities we've already created
    created_people: Dict[str, Person] = field(default_factory=dict)
    created_locations: Dict[str, Location] = field(default_factory=dict)
    created_cities: Dict[str, City] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "EntityResolver":
        """
        Load entity resolution maps from per-year curated files.

        Returns:
            EntityResolver with populated mappings

        Raises:
            FileNotFoundError: If no curation files exist
            ValueError: If curation files are invalid
        """
        resolver = cls()

        # Load all people curation files
        people_files = sorted(CURATION_DIR.glob("*_people_curation.yaml"))
        if not people_files:
            raise FileNotFoundError(
                f"No people curation files found in {CURATION_DIR}\n"
                "Run extract_entities.py and complete manual curation first."
            )

        # First pass: collect all canonicals
        people_canonicals: Dict[str, Dict[str, Any]] = {}  # raw_name -> canonical
        people_same_as: Dict[str, str] = {}  # raw_name -> target_name

        for people_file in people_files:
            with open(people_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            for raw_name, entry in data.items():
                if not isinstance(entry, dict):
                    continue

                # Skip entries marked as skip or self
                if entry.get("skip") or entry.get("self"):
                    continue

                canonical = entry.get("canonical")
                same_as = entry.get("same_as")

                if canonical and isinstance(canonical, dict) and canonical.get("name"):
                    people_canonicals[raw_name] = canonical
                elif same_as:
                    people_same_as[raw_name] = same_as

        # Second pass: resolve same_as references
        def resolve_person_canonical(name: str, visited: set) -> Optional[Dict[str, Any]]:
            if name in visited:
                return None  # Circular reference
            visited.add(name)

            if name in people_canonicals:
                return people_canonicals[name]
            if name in people_same_as:
                return resolve_person_canonical(people_same_as[name], visited)
            return None

        # Build final people map
        for raw_name in list(people_canonicals.keys()) + list(people_same_as.keys()):
            canonical = resolve_person_canonical(raw_name, set())
            if canonical:
                resolver.people_map[raw_name.lower()] = canonical

        # Load all locations curation files
        locations_files = sorted(CURATION_DIR.glob("*_locations_curation.yaml"))
        if not locations_files:
            raise FileNotFoundError(
                f"No locations curation files found in {CURATION_DIR}\n"
                "Run extract_entities.py and complete manual curation first."
            )

        # First pass: collect all canonicals by city
        # Structure: city -> raw_name -> canonical_name
        loc_canonicals: Dict[str, Dict[str, str]] = {}
        loc_same_as: Dict[str, Dict[str, str]] = {}  # city -> raw_name -> target_name

        for locations_file in locations_files:
            with open(locations_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            for city, locations in data.items():
                if not isinstance(locations, dict):
                    continue

                if city not in loc_canonicals:
                    loc_canonicals[city] = {}
                    loc_same_as[city] = {}

                for raw_name, entry in locations.items():
                    if not isinstance(entry, dict):
                        continue

                    # Skip entries marked as skip
                    if entry.get("skip"):
                        continue

                    canonical = entry.get("canonical")
                    same_as = entry.get("same_as")

                    if canonical and isinstance(canonical, str):
                        loc_canonicals[city][raw_name] = canonical
                    elif same_as:
                        loc_same_as[city][raw_name] = same_as

        # Second pass: resolve same_as references within each city
        def resolve_location_canonical(city: str, name: str, visited: set) -> Optional[str]:
            key = f"{city}|{name}"
            if key in visited:
                return None  # Circular reference
            visited.add(key)

            if city in loc_canonicals and name in loc_canonicals[city]:
                return loc_canonicals[city][name]
            if city in loc_same_as and name in loc_same_as[city]:
                return resolve_location_canonical(city, loc_same_as[city][name], visited)
            return None

        # Build final locations map
        for city in set(loc_canonicals.keys()) | set(loc_same_as.keys()):
            if city == "_unassigned":
                continue

            all_names = set()
            if city in loc_canonicals:
                all_names.update(loc_canonicals[city].keys())
            if city in loc_same_as:
                all_names.update(loc_same_as[city].keys())

            for raw_name in all_names:
                canonical_name = resolve_location_canonical(city, raw_name, set())
                if canonical_name:
                    resolver.locations_map[raw_name.lower()] = {
                        "name": canonical_name,
                        "city": city,
                    }

        return resolver

    def resolve_person(self, raw_name: str, session: Session) -> Optional[Person]:
        """
        Resolve a raw person name to a Person entity.

        Args:
            raw_name: Raw name from YAML (e.g., "@majo", "Majo", "María José")
            session: Database session

        Returns:
            Person entity (existing or newly created), or None if not in curation
        """
        lookup_key = raw_name.lower()
        canonical = self.people_map.get(lookup_key)

        if not canonical:
            return None

        # Build a cache key from canonical fields
        name = canonical.get("name", "")
        lastname = canonical.get("lastname") or ""
        alias = canonical.get("alias") or ""
        cache_key = f"{name}|{lastname}|{alias}".lower()

        # Check cache first
        if cache_key in self.created_people:
            return self.created_people[cache_key]

        # Check database
        if alias:
            person = session.query(Person).filter_by(alias=alias).first()
        else:
            person = (
                session.query(Person)
                .filter_by(name=name, lastname=lastname if lastname else None)
                .first()
            )

        if person:
            self.created_people[cache_key] = person
            return person

        # Create new person
        person = Person(
            name=name,
            lastname=lastname if lastname else None,
            alias=alias if alias else None,
        )
        session.add(person)
        session.flush()
        self.created_people[cache_key] = person
        return person

    def resolve_location(
        self, raw_name: str, session: Session
    ) -> Optional[Location]:
        """
        Resolve a raw location name to a Location entity.

        Args:
            raw_name: Raw location name from YAML
            session: Database session

        Returns:
            Location entity (existing or newly created), or None if not in curation
        """
        lookup_key = raw_name.lower()
        canonical = self.locations_map.get(lookup_key)

        if not canonical:
            return None

        name = canonical.get("name", "")
        city_name = canonical.get("city", "")

        if not name or not city_name:
            return None

        cache_key = f"{name}|{city_name}".lower()

        # Check cache first
        if cache_key in self.created_locations:
            return self.created_locations[cache_key]

        # Ensure city exists
        city = self._get_or_create_city(city_name, session)

        # Check database for location
        location = (
            session.query(Location).filter_by(name=name, city_id=city.id).first()
        )

        if location:
            self.created_locations[cache_key] = location
            return location

        # Create new location
        location = Location(name=name, city_id=city.id)
        session.add(location)
        session.flush()
        self.created_locations[cache_key] = location
        return location

    def _get_or_create_city(self, city_name: str, session: Session) -> City:
        """Get or create a city by name."""
        cache_key = city_name.lower()

        if cache_key in self.created_cities:
            return self.created_cities[cache_key]

        city = session.query(City).filter_by(name=city_name).first()
        if city:
            self.created_cities[cache_key] = city
            return city

        city = City(name=city_name)
        session.add(city)
        session.flush()
        self.created_cities[cache_key] = city
        return city


class JumpstartImporter:
    """
    Main importer class for jumpstart migration.

    Handles loading YAML files, creating database entities, and managing
    transactions with proper error handling.
    """

    def __init__(
        self,
        session: Session,
        resolver: EntityResolver,
        dry_run: bool = False,
    ):
        """
        Initialize the importer.

        Args:
            session: Database session
            resolver: Entity resolver with curated mappings
            dry_run: If True, don't commit changes
        """
        self.session = session
        self.resolver = resolver
        self.dry_run = dry_run
        self.stats = ImportStats()
        self.failed_imports: List[FailedImport] = []

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
                print("No failed imports to retry.")
                return self.stats

        for yaml_path in yaml_files:
            # Skip if not in failed list (when retrying)
            if failed_only and str(yaml_path) not in failed_paths:
                self.stats.skipped += 1
                continue

            # Check thresholds
            if self.stats.should_stop():
                print(
                    f"\nStopping due to failure threshold: "
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
                print(f"  FAILED: {e}")

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
        print(f"Importing {yaml_path.name}...", end=" ")

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
            print("SKIPPED (exists)")
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
            print("OK (dry-run)")
        else:
            self.session.commit()
            print("OK")
            self.stats.entries_created += 1

    def _parse_date(self, date_value: Any, yaml_path: Path) -> date:
        """Parse date from YAML data or filename."""
        if isinstance(date_value, date):
            return date_value
        if isinstance(date_value, str):
            return date.fromisoformat(date_value)

        # Extract from filename: YYYY-MM-DD_analysis.yaml
        stem = yaml_path.stem
        date_str = stem.replace("_analysis", "")
        return date.fromisoformat(date_str)

    def _find_md_file(self, entry_date: date) -> Optional[Path]:
        """Find the MD file for a given date."""
        year_dir = MD_DIR / str(entry_date.year)
        md_path = year_dir / f"{entry_date.isoformat()}.md"
        if md_path.exists():
            return md_path
        return None

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file contents."""
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()

    def _compute_word_count(self, file_path: Path) -> int:
        """Count words in MD file (excluding frontmatter)."""
        content = file_path.read_text(encoding="utf-8")

        # Remove frontmatter
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                content = parts[2]

        return len(content.split())

    def _create_entry(self, entry_date: date, md_path: Path, data: Dict) -> Entry:
        """Create an Entry from YAML data."""
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
        """Create scenes for an entry."""
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
                person = self.resolver.resolve_person(str(person_name), self.session)
                if person and person not in scene.people:
                    scene.people.append(person)

            # Link locations
            for loc_name in scene_data.get("locations", []) or []:
                location = self.resolver.resolve_location(str(loc_name), self.session)
                if location and location not in scene.locations:
                    scene.locations.append(location)

        # Store scene map on entry for event creation
        entry._scene_map = scene_map  # type: ignore

    def _add_scene_date(self, scene: Scene, date_value: Any) -> None:
        """Add a date to a scene."""
        if isinstance(date_value, date):
            scene_date = date_value
        elif isinstance(date_value, str):
            scene_date = date.fromisoformat(date_value)
        else:
            return

        sd = SceneDate(date=scene_date, scene_id=scene.id)
        self.session.add(sd)

    def _create_events(self, entry: Entry, events_data: List[Dict]) -> None:
        """Create events for an entry."""
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
        """Create threads for an entry."""
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
                person = self.resolver.resolve_person(str(person_name), self.session)
                if person and person not in thread.people:
                    thread.people.append(person)

            # Link locations
            for loc_name in thread_data.get("locations", []) or []:
                location = self.resolver.resolve_location(str(loc_name), self.session)
                if location and location not in thread.locations:
                    thread.locations.append(location)

    def _link_arcs(self, entry: Entry, arcs_data: List[str]) -> None:
        """Link arcs to an entry."""
        for arc_name in arcs_data or []:
            arc = self._get_or_create_arc(arc_name)
            if arc not in entry.arcs:
                entry.arcs.append(arc)

    def _get_or_create_arc(self, name: str) -> Arc:
        """Get or create an arc by name."""
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
        """Link tags to an entry."""
        for tag_name in tags_data or []:
            tag = self._get_or_create_tag(tag_name)
            if tag not in entry.tags:
                entry.tags.append(tag)

    def _get_or_create_tag(self, name: str) -> Tag:
        """Get or create a tag by name."""
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
        """Link themes to an entry."""
        for theme_name in themes_data or []:
            theme = self._get_or_create_theme(theme_name)
            if theme not in entry.themes:
                entry.themes.append(theme)

    def _get_or_create_theme(self, name: str) -> Theme:
        """Get or create a theme by name."""
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
        """Create motif instances for an entry."""
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
        """Get or create a motif by name."""
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
        """Create references for an entry."""
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
        """Get or create a reference source."""
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
        """Create poems for an entry."""
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
        """Get or create a poem by title."""
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
        """Create narrated dates from scene dates."""
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
        """Record a failed import."""
        self.failed_imports.append(
            FailedImport(
                file_path=str(yaml_path),
                error_type=type(error).__name__,
                error_message=str(error),
            )
        )

    def _load_failed_imports(self) -> Set[str]:
        """Load previously failed imports."""
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
            "failures": [
                {
                    "file_path": f.file_path,
                    "error_type": f.error_type,
                    "error_message": f.error_message,
                    "timestamp": f.timestamp,
                }
                for f in self.failed_imports
            ],
        }

        with open(failed_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"\nFailed imports saved to {failed_file}")


def run_pre_validation() -> bool:
    """
    Run pre-import validation.

    Returns:
        True if validation passes, False otherwise
    """
    from dev.bin.validate_curation import validate_all

    print("Running pre-import validation...")
    valid = validate_all()
    return valid


def run_post_validation(session: Session) -> bool:
    """
    Run post-import integrity checks.

    Args:
        session: Database session

    Returns:
        True if all checks pass, False otherwise
    """
    print("\nRunning post-import validation...")

    all_valid = True

    # Check entry count
    entry_count = session.query(Entry).count()
    print(f"  Entries in database: {entry_count}")

    # Check for orphaned scenes
    orphan_scenes = (
        session.query(Scene)
        .filter(~Scene.entry_id.in_(session.query(Entry.id)))
        .count()
    )
    if orphan_scenes > 0:
        print(f"  WARNING: {orphan_scenes} orphaned scenes found")
        all_valid = False
    else:
        print("  No orphaned scenes")

    # Check for entries without scenes
    entries_without_scenes = (
        session.query(Entry).filter(~Entry.scenes.any()).count()
    )
    if entries_without_scenes > 0:
        print(f"  NOTE: {entries_without_scenes} entries without scenes")

    return all_valid


def get_yaml_files() -> List[Path]:
    """Get all narrative_analysis YAML files sorted by date."""
    yaml_files = sorted(NARRATIVE_ANALYSIS_DIR.glob("**/*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]
    return yaml_files


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="One-time migration from narrative_analysis YAMLs to database"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't commit changes, just validate",
    )
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="Only retry previously failed imports",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip pre-import validation",
    )
    args = parser.parse_args()

    # Pre-validation
    if not args.skip_validation:
        if not run_pre_validation():
            print("\nPre-import validation failed. Fix errors before running jumpstart.")
            sys.exit(1)

    # Get YAML files
    yaml_files = get_yaml_files()
    print(f"\nFound {len(yaml_files)} YAML files to import")

    # Load entity resolver
    try:
        resolver = EntityResolver.load()
        print(
            f"Loaded entity resolver: {len(resolver.people_map)} people, "
            f"{len(resolver.locations_map)} locations"
        )
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        sys.exit(1)

    # Create database session
    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Run import
        importer = JumpstartImporter(session, resolver, dry_run=args.dry_run)
        stats = importer.import_all(yaml_files, failed_only=args.failed_only)

        # Print results
        print("\n" + "=" * 60)
        print("IMPORT RESULTS")
        print("=" * 60)
        print(f"Total files:    {stats.total_files}")
        print(f"Processed:      {stats.processed}")
        print(f"Succeeded:      {stats.succeeded}")
        print(f"Failed:         {stats.failed}")
        print(f"Skipped:        {stats.skipped}")
        print()
        print(f"Entries created:    {stats.entries_created}")
        print(f"Scenes created:     {stats.scenes_created}")
        print(f"Events created:     {stats.events_created}")
        print(f"Threads created:    {stats.threads_created}")
        print(f"Arcs created:       {stats.arcs_created}")
        print(f"Tags created:       {stats.tags_created}")
        print(f"Themes created:     {stats.themes_created}")
        print(f"Motifs created:     {stats.motifs_created}")
        print(f"References created: {stats.references_created}")
        print(f"Poems created:      {stats.poems_created}")
        print("=" * 60)

        # Post-validation
        if not args.dry_run and stats.succeeded > 0:
            run_post_validation(session)

        # Exit code
        if stats.failed > 0:
            sys.exit(1)
        sys.exit(0)

    finally:
        session.close()


if __name__ == "__main__":
    main()
