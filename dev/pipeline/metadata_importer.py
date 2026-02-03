#!/usr/bin/env python3
"""
metadata_importer.py
--------------------
Import metadata YAML files into the database.

This module provides the MetadataImporter class which handles importing
metadata YAML files into the database, combining them with MD frontmatter
data for a complete Entry import.

Data Sources:
    - MD Frontmatter: people, locations, narrated_dates (entry-level, full set)
    - Metadata YAML: summary, rating, scenes, events, threads, etc. (analysis)

Key Features:
    - Per-file transactions (each YAML = one commit)
    - Uses EntityResolver for person/location resolution
    - Entry-level people/locations from MD frontmatter
    - Scene-level people/locations are subsets of entry-level
    - NarratedDate records from MD frontmatter
    - Fatal vs recoverable error handling with thresholds
    - Retry capability for failed imports
    - Detailed statistics and failure tracking

Transaction Strategy:
    - Each YAML file is imported in a single transaction
    - Failures are logged to failed_imports.json for retry
    - Stop at 5 consecutive failures OR 5% failure rate

Validation:
    - Pre-import: Metadata YAML files must pass validation
    - During-import: Schema validation before transaction
    - Post-import: Integrity checks (counts, FK validity)

Usage:
    from dev.pipeline.metadata_importer import MetadataImporter
    from dev.pipeline.entity_resolver import EntityResolver

    resolver = EntityResolver.load()
    importer = MetadataImporter(session, resolver)
    stats = importer.import_all(yaml_files)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import hashlib
import json
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# --- Third-party imports ---
import yaml
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import ValidationError
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import LOG_DIR, MD_DIR
from dev.pipeline.models import FailedImport, ImportStats
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
    PersonAlias,
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
# Metadata Importer
# =============================================================================

class MetadataImporter:
    """
    Import metadata YAML files into the database.

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
        dry_run: bool = False,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the importer.

        Args:
            session: Database session
            dry_run: If True, don't commit changes
            logger: Optional logger for operation tracking
        """
        self.session = session
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
        self._events: Dict[str, Event] = {}
        self._tags: Dict[str, Tag] = {}
        self._themes: Dict[str, Theme] = {}
        self._motifs: Dict[str, Motif] = {}
        self._reference_sources: Dict[str, ReferenceSource] = {}
        self._poems: Dict[str, Poem] = {}
        self._cities: Dict[str, City] = {}
        self._locations: Dict[str, Location] = {}

    def _clear_importer_caches(self) -> None:
        """
        Clear importer caches after a rollback.

        This ensures we don't try to reuse stale/detached objects.
        """
        self._arcs.clear()
        self._events.clear()
        self._tags.clear()
        self._themes.clear()
        self._motifs.clear()
        self._reference_sources.clear()
        self._poems.clear()
        self._cities.clear()
        self._locations.clear()

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
                # Rollback partial changes from failed file and clear stale caches
                self.session.rollback()
                self._clear_importer_caches()
                self.stats.failed += 1
                self.stats.consecutive_failures += 1
                self._record_failure(yaml_path, e)
                self.logger.log_error(f"FAILED {yaml_path.name}: {e}")

            self.stats.processed += 1

        # Save failed imports for retry
        if self.failed_imports:
            self._save_failed_imports()

        # In dry-run mode, rollback all changes at the end
        if self.dry_run:
            self.session.rollback()
            self.logger.log_info("Dry-run complete, all changes rolled back")

        return self.stats

    def _import_file(self, yaml_path: Path) -> None:
        """
        Import a single YAML file.

        Data Sources:
            - MD Frontmatter: entry-level people, locations (by city), narrated_dates
            - Metadata YAML: summary, rating, scenes, events, threads, arcs, etc.

        Args:
            yaml_path: Path to the metadata YAML file

        Raises:
            Various exceptions on failure (caught by import_all)
        """
        self.logger.log_info(f"Importing {yaml_path.name}...")

        # Load metadata YAML
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

        # Parse MD frontmatter for entry-level people/locations/narrated_dates
        md_frontmatter = self._parse_md_frontmatter(md_path)

        # Compute hashes for change detection
        md_hash = self._compute_file_hash(md_path)
        yaml_hash = self._compute_file_hash(yaml_path)

        # Check if entry already exists
        existing = self.session.query(Entry).filter_by(date=entry_date).first()
        if existing:
            # Check if either MD file or metadata YAML has changed
            md_changed = existing.file_hash != md_hash
            yaml_changed = existing.metadata_hash != yaml_hash

            if not md_changed and not yaml_changed:
                self.logger.log_info("  SKIPPED (unchanged)")
                self.stats.skipped += 1
                return
            else:
                # File(s) changed - delete existing entry and re-create
                change_type = []
                if md_changed:
                    change_type.append("MD")
                if yaml_changed:
                    change_type.append("YAML")
                self.logger.log_info(f"  UPDATING ({', '.join(change_type)} changed)")
                self.session.delete(existing)
                self.session.flush()

        # Create entry (from metadata YAML)
        entry = self._create_entry(entry_date, md_path, data, yaml_hash)

        # Link entry-level people from metadata YAML (ground truth for person definitions)
        # Link entry-level locations from MD frontmatter (full sets)
        self._link_entry_people(entry, data, md_frontmatter)

        # Validate people consistency between MD frontmatter and YAML
        self._validate_people_consistency(entry, data, md_frontmatter)

        self._link_entry_locations(entry, md_frontmatter)

        # Create NarratedDates from MD frontmatter
        self._create_narrated_dates_from_frontmatter(entry, md_frontmatter)

        # Validate scene subsets before creating scenes
        scenes_data = data.get("scenes", [])
        for scene_data in scenes_data:
            self._validate_scene_subsets(entry, data, scene_data, scene_data.get("name", "Unnamed Scene"))

        # Create scene-level entities (subsets of entry-level)
        self._create_scenes(entry, scenes_data)
        self._create_events(entry, data.get("events", []))
        self._create_threads(entry, data.get("threads", []))

        # Link analysis metadata
        self._link_arcs(entry, data.get("arcs", []))
        self._link_tags(entry, data.get("tags", []))
        self._link_themes(entry, data.get("themes", []))
        self._create_motif_instances(entry, data.get("motifs", []))
        self._create_references(entry, data.get("references", []))
        self._create_poems(entry, data.get("poems", []))

        # Commit or flush (dry-run keeps in session without committing)
        if self.dry_run:
            self.session.flush()
            self.logger.log_info("  OK (dry-run)")
            self.stats.entries_created += 1
        else:
            self.session.commit()
            self.logger.log_info("  OK")
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

        # Extract from filename: YYYY-MM-DD.yaml or YYYY-MM-DD_analysis.yaml
        stem = yaml_path.stem
        date_str = stem.replace("_analysis", "")  # Handle both formats
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

    def _parse_md_frontmatter(self, md_path: Path) -> Dict[str, Any]:
        """
        Parse YAML frontmatter from an MD file.

        Args:
            md_path: Path to the MD file

        Returns:
            Dictionary of frontmatter fields
        """
        content = md_path.read_text(encoding="utf-8")

        if not content.startswith("---"):
            return {}

        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}

        frontmatter_text = parts[1]
        return yaml.safe_load(frontmatter_text) or {}

    def _normalize_name(self, name: str) -> str:
        """
        Normalize a person name for comparison.

        Handles:
        - Accent/diacritic differences (Mónica vs Monica, Sofía vs Sofia)
        - Hyphen/space differences (María-José vs María José)

        Args:
            name: Name to normalize

        Returns:
            Lowercase name with accents stripped and hyphens converted to spaces
        """
        text = name.lower().strip()
        # Normalize hyphens to spaces
        text = text.replace("-", " ")
        # Normalize accents/diacritics
        normalized = unicodedata.normalize("NFD", text)
        without_accents = "".join(c for c in normalized if unicodedata.category(c)[0] != "M")
        return without_accents

    def _get_or_create_person(
        self,
        name: str,
        lastname: Optional[str],
        disambiguator: Optional[str],
        aliases: List[str]
    ) -> Optional["Person"]:
        """
        Get or create a person using slug as unique identifier.

        The slug is generated from name + lastname (preferred) or name + disambiguator.
        Aliases are stored but NOT used for matching (not globally unique).

        Args:
            name: Person's name
            lastname: Person's lastname (optional if disambiguator provided)
            disambiguator: Disambiguator (optional if lastname provided)
            aliases: List of aliases for this person (NOT used for matching)

        Returns:
            Person entity (existing or newly created), or None on error
        """
        # Generate slug for this person
        slug = Person.generate_slug(name, lastname, disambiguator)

        # Try to find existing person by slug
        person = self.session.query(Person).filter_by(slug=slug).first()
        if person:
            return person

        # Create new person with slug
        person = Person(
            name=name,
            lastname=lastname,
            disambiguator=disambiguator,
            slug=slug,
        )
        self.session.add(person)
        self.session.flush()

        # Add aliases
        for alias in aliases:
            person_alias = PersonAlias(person_id=person.id, alias=alias)
            self.session.add(person_alias)

        self.session.flush()
        return person

    def _get_or_create_city(self, city_name: str) -> City:
        """
        Get or create a city by name.

        Args:
            city_name: City name

        Returns:
            City entity (existing or newly created)
        """
        cache_key = city_name.lower()

        if cache_key in self._cities:
            return self._cities[cache_key]

        city = self.session.query(City).filter_by(name=city_name).first()
        if city:
            self._cities[cache_key] = city
            return city

        city = City(name=city_name)
        self.session.add(city)
        self.session.flush()
        self._cities[cache_key] = city
        return city

    def _get_or_create_location(self, loc_name: str, city: City) -> Location:
        """
        Get or create a location by name and city.

        Args:
            loc_name: Location name
            city: City entity

        Returns:
            Location entity (existing or newly created)
        """
        cache_key = f"{loc_name}|{city.name}".lower()

        if cache_key in self._locations:
            return self._locations[cache_key]

        location = (
            self.session.query(Location)
            .filter_by(name=loc_name, city_id=city.id)
            .first()
        )
        if location:
            self._locations[cache_key] = location
            return location

        location = Location(name=loc_name, city_id=city.id)
        self.session.add(location)
        self.session.flush()
        self._locations[cache_key] = location
        return location

    def _find_person_in_entry(self, name: str, entry: Entry) -> Optional[Person]:
        """
        Find a person in the entry's already-resolved people list.

        Scene/thread people should be subsets of entry-level people.
        This looks up a person by name from the entry's people list.
        Uses accent-normalized matching for flexibility.

        Args:
            name: Person name to find
            entry: Entry with already-resolved people

        Returns:
            Person entity if found, None otherwise
        """
        name_normalized = self._normalize_name(name)
        for person in entry.people:
            if self._normalize_name(person.name) == name_normalized:
                return person
            # Also check aliases
            for alias in person.aliases:
                if self._normalize_name(alias.alias) == name_normalized:
                    return person
        return None

    def _find_location_in_entry(self, name: str, entry: Entry) -> Optional[Location]:
        """
        Find a location in the entry's already-resolved locations list.

        Scene/thread locations should be subsets of entry-level locations.
        This looks up a location by name from the entry's locations list.
        Uses accent-normalized matching for flexibility.

        Args:
            name: Location name to find
            entry: Entry with already-resolved locations

        Returns:
            Location entity if found, None otherwise
        """
        name_normalized = self._normalize_name(name)
        for location in entry.locations:
            if self._normalize_name(location.name) == name_normalized:
                return location
        return None

    def _link_entry_people(
        self,
        entry: Entry,
        metadata: Dict[str, Any],
        md_frontmatter: Dict[str, Any]
    ) -> None:
        """
        Link entry-level people from metadata YAML (ground truth).

        The metadata YAML people section contains full person definitions with
        lastname/disambiguator/alias. This is the ground truth for person data.

        MD frontmatter people list is used for validation (ensuring all people
        in metadata are also in MD frontmatter).

        Args:
            entry: Entry entity to link people to
            metadata: Parsed metadata YAML dict (has full person definitions)
            md_frontmatter: Parsed MD frontmatter dict (has people names list)
        """
        people_list = metadata.get("people", [])
        if not people_list:
            return

        # Get MD frontmatter people for validation (normalized, including name parts)
        md_people_normalized: Set[str] = set()
        for p in md_frontmatter.get("people", []):
            normalized = self._normalize_name(p)
            md_people_normalized.add(normalized)
            # Add individual parts for multi-word names (e.g., "Paola Aguirre" -> "paola", "aguirre")
            for part in normalized.split():
                md_people_normalized.add(part)

        for person_data in people_list:
            # Handle both old format (string) and new format (dict)
            if isinstance(person_data, str):
                # Legacy format: just name
                person = self._get_or_create_person(person_data, None, None, [])
            else:
                # Full format with lastname/disambiguator/alias
                name = person_data.get("name")
                if not name:
                    self.logger.log_warning(f"Person entry missing 'name' field: {person_data}")
                    continue

                lastname = person_data.get("lastname")
                disambiguator = person_data.get("disambiguator")
                alias = person_data.get("alias")

                # Data quality check: person must have lastname OR disambiguator
                if not lastname and not disambiguator:
                    raise ValidationError(
                        f"Person '{name}' missing both lastname and disambiguator "
                        f"(entry: {entry.date.isoformat() if entry.date else 'unknown'})"
                    )

                # Validate person is in MD frontmatter (using normalized matching with parts)
                name_normalized = self._normalize_name(name)
                alias_match = False
                if alias:
                    aliases = alias if isinstance(alias, list) else [alias]
                    alias_match = any(self._normalize_name(a) in md_people_normalized for a in aliases)
                # Check full name or any part matches
                name_match = name_normalized in md_people_normalized or any(
                    part in md_people_normalized for part in name_normalized.split()
                )
                if not name_match and not alias_match:
                    raise ValidationError(
                        f"Person '{name}' in metadata YAML but not in MD frontmatter"
                    )

                # Handle alias as string or list
                if alias:
                    aliases = alias if isinstance(alias, list) else [alias]
                else:
                    aliases = []
                person = self._get_or_create_person(
                    name,
                    lastname,
                    disambiguator,
                    aliases
                )

            if person and person not in entry.people:
                entry.people.append(person)

    def _validate_people_consistency(
        self,
        entry: Entry,
        metadata: Dict[str, Any],
        md_frontmatter: Dict[str, Any]
    ) -> None:
        """
        Validate people consistency between MD frontmatter and metadata YAML.

        Ensures bidirectional equality:
        - Every person in metadata YAML has a match in MD frontmatter
        - Every person in MD frontmatter has a match in metadata YAML

        MD frontmatter can use: name only, full name (name lastname), or alias.
        Metadata YAML has full person definitions with name/lastname/disambiguator/alias.

        Args:
            entry: Entry entity with linked people from metadata YAML
            metadata: Parsed metadata YAML dict
            md_frontmatter: Parsed MD frontmatter dict

        Raises:
            ValueError: If people lists don't match bidirectionally
        """
        yaml_people = metadata.get("people", [])
        md_people = md_frontmatter.get("people", [])

        if not yaml_people and not md_people:
            return  # Both empty, valid

        # Build sets of normalized names from YAML people
        # Include individual name parts for multi-word names (e.g., "Miguel Ángel" -> "miguel", "angel", "miguel angel")
        yaml_names_normalized: Dict[str, str] = {}  # normalized -> original
        for person_data in yaml_people:
            if isinstance(person_data, str):
                normalized = self._normalize_name(person_data)
                yaml_names_normalized[normalized] = person_data
                # Add individual parts for multi-word names
                for part in normalized.split():
                    yaml_names_normalized[part] = person_data
            else:
                name = person_data.get("name")
                lastname = person_data.get("lastname")
                alias = person_data.get("alias")

                if name:
                    normalized_name = self._normalize_name(name)
                    yaml_names_normalized[normalized_name] = name
                    # Add individual parts
                    for part in normalized_name.split():
                        yaml_names_normalized[part] = name
                    if lastname:
                        full_name = f"{name} {lastname}"
                        normalized_full = self._normalize_name(full_name)
                        yaml_names_normalized[normalized_full] = full_name
                        # Add individual parts of full name
                        for part in normalized_full.split():
                            yaml_names_normalized[part] = full_name
                # Handle alias as string or list
                if alias:
                    if isinstance(alias, list):
                        for a in alias:
                            yaml_names_normalized[self._normalize_name(a)] = a
                    else:
                        yaml_names_normalized[self._normalize_name(alias)] = alias

        # Check 1: Every MD person must match a YAML person (normalized)
        unmatched_md = []
        for md_person in md_people:
            if self._normalize_name(md_person) not in yaml_names_normalized:
                unmatched_md.append(md_person)

        if unmatched_md:
            raise ValueError(
                f"MD frontmatter has people not in metadata YAML: {sorted(unmatched_md)}"
            )

        # Check 2: Every YAML person must match an MD person (normalized, with name parts)
        # Build MD people set with individual name parts for flexible matching
        md_people_normalized: Set[str] = set()
        for p in md_people:
            normalized = self._normalize_name(p)
            md_people_normalized.add(normalized)
            # Add individual parts for multi-word names
            for part in normalized.split():
                md_people_normalized.add(part)

        for person_data in yaml_people:
            if isinstance(person_data, str):
                normalized = self._normalize_name(person_data)
                # Check full name or any part
                if normalized in md_people_normalized:
                    continue
                if any(part in md_people_normalized for part in normalized.split()):
                    continue
                raise ValueError(
                    f"Metadata YAML has person '{person_data}' not in MD frontmatter"
                )
            else:
                name = person_data.get("name")
                lastname = person_data.get("lastname")
                alias = person_data.get("alias")

                # Try to find match in MD frontmatter (normalized, including parts)
                matched = False
                if name:
                    normalized_name = self._normalize_name(name)
                    if normalized_name in md_people_normalized:
                        matched = True
                    elif any(part in md_people_normalized for part in normalized_name.split()):
                        matched = True
                if not matched and lastname:
                    full_name = f"{name} {lastname}"
                    normalized_full = self._normalize_name(full_name)
                    if normalized_full in md_people_normalized:
                        matched = True
                    elif any(part in md_people_normalized for part in normalized_full.split()):
                        matched = True
                if not matched and alias:
                    # Handle alias as string or list
                    aliases = alias if isinstance(alias, list) else [alias]
                    for a in aliases:
                        if self._normalize_name(a) in md_people_normalized:
                            matched = True
                            break

                if not matched:
                    if alias:
                        identifier = f"{name} (alias: {alias})"
                    elif lastname:
                        identifier = f"{name} {lastname}"
                    else:
                        identifier = name
                    raise ValueError(
                        f"Metadata YAML has person '{identifier}' not in MD frontmatter"
                    )

    def _link_entry_locations(
        self, entry: Entry, md_frontmatter: Dict[str, Any]
    ) -> None:
        """
        Link entry-level locations from MD frontmatter.

        The MD frontmatter contains locations nested by city:
        locations:
          Montréal: [The Neuro, Home]
          Toronto: [Pearson Airport]

        Args:
            entry: Entry entity to link locations/cities to
            md_frontmatter: Parsed MD frontmatter dict
        """
        locations_data = md_frontmatter.get("locations", {})
        if not locations_data or not isinstance(locations_data, dict):
            return

        for city_name, loc_names in locations_data.items():
            # Get or create city
            city = self._get_or_create_city(city_name)
            if city not in entry.cities:
                entry.cities.append(city)

            # Get or create locations
            if isinstance(loc_names, list):
                for loc_name in loc_names:
                    location = self._get_or_create_location(str(loc_name), city)
                    if location not in entry.locations:
                        entry.locations.append(location)

    def _create_narrated_dates_from_frontmatter(
        self, entry: Entry, md_frontmatter: Dict[str, Any]
    ) -> None:
        """
        Create NarratedDate records from MD frontmatter.

        The MD frontmatter contains the full set of narrated dates:
        narrated_dates: [2024-01-28, 2024-01-27, ...]

        Args:
            entry: Entry entity to create NarratedDates for
            md_frontmatter: Parsed MD frontmatter dict
        """
        narrated_list = md_frontmatter.get("narrated_dates", [])
        if not narrated_list:
            return

        for date_val in narrated_list:
            if isinstance(date_val, date):
                nd = NarratedDate(date=date_val, entry_id=entry.id)
                self.session.add(nd)
            elif isinstance(date_val, str):
                try:
                    nd = NarratedDate(
                        date=date.fromisoformat(date_val), entry_id=entry.id
                    )
                    self.session.add(nd)
                except ValueError:
                    pass

    def _validate_scene_subsets(
        self,
        entry: Entry,
        metadata: Dict[str, Any],
        scene_data: Dict[str, Any],
        scene_name: str
    ) -> None:
        """
        Validate that scene people/locations/dates are subsets of entry-level.

        Scenes must reference only entities that exist in the metadata YAML
        people section (which is the source of truth for person data).

        Args:
            entry: Entry entity with entry-level locations/dates
            metadata: Parsed metadata YAML dict (has people section with aliases)
            scene_data: Scene dict from YAML
            scene_name: Scene name for error messages

        Raises:
            ValueError: If scene references entities not in entry-level data
        """
        # Validate scene people against metadata YAML people (with aliases)
        scene_people = scene_data.get("people", [])
        yaml_people = metadata.get("people", [])

        # Build normalized set from metadata YAML people including aliases and name parts
        metadata_people_normalized: Set[str] = set()
        for person_data in yaml_people:
            if isinstance(person_data, str):
                normalized = self._normalize_name(person_data)
                metadata_people_normalized.add(normalized)
                for part in normalized.split():
                    metadata_people_normalized.add(part)
            else:
                name = person_data.get("name")
                lastname = person_data.get("lastname")
                alias = person_data.get("alias")

                if name:
                    normalized_name = self._normalize_name(name)
                    metadata_people_normalized.add(normalized_name)
                    for part in normalized_name.split():
                        metadata_people_normalized.add(part)
                if lastname:
                    full_name = f"{name} {lastname}"
                    normalized_full = self._normalize_name(full_name)
                    metadata_people_normalized.add(normalized_full)
                    for part in normalized_full.split():
                        metadata_people_normalized.add(part)
                if alias:
                    aliases = alias if isinstance(alias, list) else [alias]
                    for a in aliases:
                        normalized_alias = self._normalize_name(a)
                        metadata_people_normalized.add(normalized_alias)
                        for part in normalized_alias.split():
                            metadata_people_normalized.add(part)

        for person_name in scene_people:
            normalized_scene_person = self._normalize_name(person_name)
            if normalized_scene_person not in metadata_people_normalized:
                # Also check individual parts
                parts_match = any(part in metadata_people_normalized for part in normalized_scene_person.split())
                if not parts_match:
                    raise ValueError(
                        f"Scene '{scene_name}' references person '{person_name}' "
                        f"not in metadata YAML people list"
                    )

        # Validate scene locations (normalized for flexible matching)
        scene_locations = scene_data.get("locations", [])
        entry_location_names_normalized = {self._normalize_name(loc.name) for loc in entry.locations}

        for loc_name in scene_locations:
            if self._normalize_name(loc_name) not in entry_location_names_normalized:
                raise ValueError(
                    f"Scene '{scene_name}' references location '{loc_name}' "
                    f"not in entry locations list"
                )

        # Validate scene dates
        scene_dates = scene_data.get("date")
        if scene_dates:
            if not isinstance(scene_dates, list):
                scene_dates = [scene_dates]

            entry_dates = {nd.date for nd in entry.narrated_dates}

            for scene_date in scene_dates:
                # Convert to date object if string
                if isinstance(scene_date, str):
                    try:
                        scene_date = date.fromisoformat(scene_date)
                    except ValueError:
                        # Skip validation for approximate dates (~2021, etc.)
                        continue

                if isinstance(scene_date, date) and scene_date not in entry_dates:
                    raise ValueError(
                        f"Scene '{scene_name}' references date {scene_date} "
                        f"not in entry narrated_dates"
                    )

    def _create_entry(
        self, entry_date: date, md_path: Path, data: Dict, metadata_hash: str
    ) -> Entry:
        """
        Create an Entry from YAML data.

        Args:
            entry_date: Date of the entry
            md_path: Path to corresponding MD file
            data: YAML data dict
            metadata_hash: Hash of metadata YAML file

        Returns:
            Created Entry entity
        """
        word_count = self._compute_word_count(md_path)
        reading_time = word_count / 250.0  # Average reading speed

        entry = Entry(
            date=entry_date,
            file_path=str(md_path.relative_to(MD_DIR.parent.parent)),
            file_hash=self._compute_file_hash(md_path),
            metadata_hash=metadata_hash,
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

            # Link people (from entry's already-resolved people - subset)
            for person_name in scene_data.get("people", []) or []:
                person = self._find_person_in_entry(str(person_name), entry)
                if person and person not in scene.people:
                    scene.people.append(person)
                elif not person:
                    raise ValidationError(
                        f"Scene '{scene.name}' person '{person_name}' not found in entry people"
                    )

            # Link locations (from entry's already-resolved locations - subset)
            for loc_name in scene_data.get("locations", []) or []:
                location = self._find_location_in_entry(str(loc_name), entry)
                if location and location not in scene.locations:
                    scene.locations.append(location)
                elif not location:
                    raise ValidationError(
                        f"Scene '{scene.name}' location '{loc_name}' not found in entry locations"
                    )

        # Store scene map on entry for event creation
        entry._scene_map = scene_map  # type: ignore

    def _add_scene_date(self, scene: Scene, date_value: Any) -> None:
        """
        Add a date to a scene.

        Stores dates as strings to support flexible formats:
        - Full date: 2021-11-15
        - Partial date: 2021-11
        - Approximate date: ~2021-11, ~2021
        - Year only: 2021

        Args:
            scene: Scene entity
            date_value: Date value (date or str)
        """
        if isinstance(date_value, date):
            # Convert date object to ISO string
            date_str = date_value.isoformat()
        elif isinstance(date_value, str):
            # Store string as-is (supports ~YYYY, YYYY-MM, etc.)
            date_str = date_value.strip()
        else:
            return

        sd = SceneDate(date=date_str, scene_id=scene.id)
        self.session.add(sd)

    def _create_events(self, entry: Entry, events_data: List[Dict]) -> None:
        """
        Create or link events for an entry.

        Events are shared across entries (M2M relationship). If an event with
        the same name already exists, link it to this entry. Otherwise, create
        a new event.

        Args:
            entry: Entry entity to link events to
            events_data: List of event dicts from YAML
        """
        scene_map = getattr(entry, "_scene_map", {})

        for event_data in events_data or []:
            event_name = event_data.get("name", "Unnamed Event")
            event = self._get_or_create_event(event_name)

            # Link entry to event (M2M)
            if entry not in event.entries:
                event.entries.append(entry)

            # Link scenes by name (M2M)
            for scene_name in event_data.get("scenes", []) or []:
                scene = scene_map.get(scene_name)
                if scene and scene not in event.scenes:
                    event.scenes.append(scene)

    def _get_or_create_event(self, name: str) -> Event:
        """
        Get or create an event by name.

        Events are unique by name and shared across entries.

        Args:
            name: Event name

        Returns:
            Event entity
        """
        key = name.lower()
        if key in self._events:
            return self._events[key]

        event = self.session.query(Event).filter_by(name=name).first()
        if not event:
            event = Event(name=name)
            self.session.add(event)
            self.session.flush()
            self.stats.events_created += 1

        self._events[key] = event
        return event

    def _create_threads(self, entry: Entry, threads_data: List[Dict]) -> None:
        """
        Create threads for an entry.

        Args:
            entry: Parent Entry entity
            threads_data: List of thread dicts from YAML
        """
        for thread_data in threads_data or []:
            # Parse from_date (stored as string to support ~YYYY, YYYY-MM, etc.)
            from_date_val = thread_data.get("from")
            if isinstance(from_date_val, date):
                from_date_str = from_date_val.isoformat()
            elif isinstance(from_date_val, str):
                from_date_str = from_date_val
            else:
                continue

            # Parse to_date (stored as string to support ~YYYY, YYYY-MM, etc.)
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
                from_date=from_date_str,
                to_date=to_date_str,
                referenced_entry_date=ref_entry_date,
                content=thread_data.get("content", ""),
                entry_id=entry.id,
            )
            self.session.add(thread)
            self.session.flush()
            self.stats.threads_created += 1

            # Link people (from entry's already-resolved people - subset)
            for person_name in thread_data.get("people", []) or []:
                person = self._find_person_in_entry(str(person_name), entry)
                if person and person not in thread.people:
                    thread.people.append(person)
                elif not person:
                    raise ValidationError(
                        f"Thread '{thread.name}' person '{person_name}' not found in entry people"
                    )

            # Link locations (from entry's already-resolved locations - subset)
            for loc_name in thread_data.get("locations", []) or []:
                location = self._find_location_in_entry(str(loc_name), entry)
                if location and location not in thread.locations:
                    thread.locations.append(location)
                elif not location:
                    raise ValidationError(
                        f"Thread '{thread.name}' location '{loc_name}' not found in entry locations"
                    )

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
