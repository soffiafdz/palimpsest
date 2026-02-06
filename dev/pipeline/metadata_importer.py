#!/usr/bin/env python3
"""
metadata_importer.py
--------------------
Import metadata YAML files into the database.

This module provides the MetadataImporter class which handles importing
metadata YAML files into the database, combining them with MD frontmatter
data for a complete Entry import.

Delegates all entity creation and relationship processing to EntryManager,
which provides a single codepath for database writes.

Data Sources:
    - MD Frontmatter: people, locations, narrated_dates (entry-level, full set)
    - Metadata YAML: summary, rating, scenes, events, threads, etc. (analysis)

Key Features:
    - Per-file transactions (each YAML = one commit)
    - Delegates to EntryManager for all entity creation
    - Pre-import validation (people consistency, scene subsets)
    - Fatal vs recoverable error handling with thresholds
    - Retry capability for failed imports
    - Detailed statistics and failure tracking

Transaction Strategy:
    - Each YAML file is imported in a single transaction
    - Failures are logged to failed_imports.json for retry
    - Stop at 5 consecutive failures OR 5% failure rate

Validation:
    - Pre-import: Metadata YAML files must pass validation
    - During-import: People consistency, scene subset checks
    - Post-import: Integrity checks (counts, FK validity)

Usage:
    from dev.pipeline.metadata_importer import MetadataImporter

    importer = MetadataImporter(session)
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
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import LOG_DIR, MD_DIR
from dev.database.managers.entry_manager import EntryManager
from dev.pipeline.models import FailedImport, ImportStats


# =============================================================================
# Metadata Importer
# =============================================================================

class MetadataImporter:
    """
    Import metadata YAML files into the database.

    Handles loading YAML files, validating data, building merged metadata,
    and delegating to EntryManager for entity creation and relationship
    processing.

    Attributes:
        session: Database session
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

        self._entry_mgr = EntryManager(session, self.logger)

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
                # Rollback partial changes from failed file
                self.session.rollback()
                self.stats.failed += 1
                self.stats.consecutive_failures += 1
                self._record_failure(yaml_path, e)
                self.logger.log_error(e, {"file": yaml_path.name})

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

        Loads YAML and MD frontmatter, validates consistency, builds
        merged metadata, and delegates to EntryManager for creation
        or update.

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
        existing = self._entry_mgr.get(entry_date=entry_date)

        if existing:
            # Check if either MD file or metadata YAML has changed
            md_changed = existing.file_hash != md_hash
            yaml_changed = existing.metadata_hash != yaml_hash

            if not md_changed and not yaml_changed:
                self.logger.log_info("  SKIPPED (unchanged)")
                self.stats.skipped += 1
                return

        # Validate before any DB writes
        self._validate_people_consistency(data, md_frontmatter)

        scenes_data = data.get("scenes", [])
        for scene_data in scenes_data:
            self._validate_scene_subsets(
                data, md_frontmatter, scene_data,
                scene_data.get("name", "Unnamed Scene"),
            )

        # Build merged metadata
        merged = self._build_entry_metadata(
            entry_date, md_path, data, md_frontmatter, yaml_hash,
        )

        if existing:
            change_type = []
            if existing.file_hash != md_hash:
                change_type.append("MD")
            if existing.metadata_hash != yaml_hash:
                change_type.append("YAML")
            self.logger.log_info(
                f"  UPDATING ({', '.join(change_type)} changed)"
            )
            self._entry_mgr.update(
                existing, merged,
                sync_source="metadata-import",
                removed_by="import-metadata",
            )
        else:
            self._entry_mgr.create(
                merged,
                sync_source="metadata-import",
                removed_by="import-metadata",
            )

        self.stats.entries_created += 1

        # Commit or flush (dry-run keeps in session without committing)
        if self.dry_run:
            self.session.flush()
            self.logger.log_info("  OK (dry-run)")
        else:
            self.session.commit()
            self.logger.log_info("  OK")

    # =========================================================================
    # Metadata Building
    # =========================================================================

    def _build_entry_metadata(
        self,
        entry_date: date,
        md_path: Path,
        data: Dict[str, Any],
        md_frontmatter: Dict[str, Any],
        metadata_hash: str,
    ) -> Dict[str, Any]:
        """
        Build merged metadata dict from YAML + MD frontmatter.

        Merges data from both sources into the format expected by
        EntryManager.create() / update().

        Args:
            entry_date: Date of the entry
            md_path: Path to the MD file
            data: Parsed metadata YAML dict
            md_frontmatter: Parsed MD frontmatter dict
            metadata_hash: Hash of the metadata YAML file

        Returns:
            Merged metadata dict ready for EntryManager
        """
        word_count = self._compute_word_count(md_path)
        reading_time = word_count / 250.0

        # Normalize people: convert string entries to dicts
        people_raw = data.get("people", [])
        people_normalized: List[Dict[str, Any]] = []
        for person in people_raw or []:
            if isinstance(person, str):
                people_normalized.append({"name": person})
            elif isinstance(person, dict):
                people_normalized.append(person)

        return {
            # Scalar fields
            "date": entry_date,
            "file_path": str(md_path.relative_to(MD_DIR.parent.parent)),
            "file_hash": self._compute_file_hash(md_path),
            "metadata_hash": metadata_hash,
            "word_count": word_count,
            "reading_time": reading_time,
            "summary": data.get("summary"),
            "rating": data.get("rating"),
            "rating_justification": data.get("rating_justification"),
            # From YAML data
            "people": people_normalized,
            "scenes": data.get("scenes", []),
            "events": data.get("events", []),
            "threads": data.get("threads", []),
            "arcs": data.get("arcs", []),
            "tags": data.get("tags", []),
            "themes": data.get("themes", []),
            "motifs": data.get("motifs", []),
            "references": data.get("references", []),
            "poems": data.get("poems", []),
            # From MD frontmatter
            "locations": md_frontmatter.get("locations", {}),
            "narrated_dates": md_frontmatter.get("narrated_dates", []),
        }

    # =========================================================================
    # File Parsing Helpers
    # =========================================================================

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

    # =========================================================================
    # Validation
    # =========================================================================

    def _normalize_name(self, name: str) -> str:
        """
        Normalize a person name for comparison.

        Handles accent/diacritic differences and hyphen/space differences.

        Args:
            name: Name to normalize

        Returns:
            Lowercase name with accents stripped and hyphens converted to spaces
        """
        text = name.lower().strip()
        text = text.replace("-", " ")
        normalized = unicodedata.normalize("NFD", text)
        without_accents = "".join(
            c for c in normalized if unicodedata.category(c)[0] != "M"
        )
        return without_accents

    def _validate_people_consistency(
        self,
        metadata: Dict[str, Any],
        md_frontmatter: Dict[str, Any],
    ) -> None:
        """
        Validate people consistency between MD frontmatter and metadata YAML.

        Ensures bidirectional equality:
        - Every person in metadata YAML has a match in MD frontmatter
        - Every person in MD frontmatter has a match in metadata YAML

        Args:
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
        yaml_names_normalized: Dict[str, str] = {}  # normalized -> original
        for person_data in yaml_people:
            if isinstance(person_data, str):
                normalized = self._normalize_name(person_data)
                yaml_names_normalized[normalized] = person_data
                for part in normalized.split():
                    yaml_names_normalized[part] = person_data
            else:
                name = person_data.get("name")
                lastname = person_data.get("lastname")
                alias = person_data.get("alias")

                if name:
                    normalized_name = self._normalize_name(name)
                    yaml_names_normalized[normalized_name] = name
                    for part in normalized_name.split():
                        yaml_names_normalized[part] = name
                    if lastname:
                        full_name = f"{name} {lastname}"
                        normalized_full = self._normalize_name(full_name)
                        yaml_names_normalized[normalized_full] = full_name
                        for part in normalized_full.split():
                            yaml_names_normalized[part] = full_name
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

        # Check 2: Every YAML person must match an MD person (normalized)
        md_people_normalized: Set[str] = set()
        for p in md_people:
            normalized = self._normalize_name(p)
            md_people_normalized.add(normalized)
            for part in normalized.split():
                md_people_normalized.add(part)

        for person_data in yaml_people:
            if isinstance(person_data, str):
                normalized = self._normalize_name(person_data)
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

                matched = False
                if name:
                    normalized_name = self._normalize_name(name)
                    if normalized_name in md_people_normalized:
                        matched = True
                    elif any(
                        part in md_people_normalized
                        for part in normalized_name.split()
                    ):
                        matched = True
                if not matched and lastname:
                    full_name = f"{name} {lastname}"
                    normalized_full = self._normalize_name(full_name)
                    if normalized_full in md_people_normalized:
                        matched = True
                    elif any(
                        part in md_people_normalized
                        for part in normalized_full.split()
                    ):
                        matched = True
                if not matched and alias:
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

    def _validate_scene_subsets(
        self,
        metadata: Dict[str, Any],
        md_frontmatter: Dict[str, Any],
        scene_data: Dict[str, Any],
        scene_name: str,
    ) -> None:
        """
        Validate that scene people/locations/dates are subsets of entry-level.

        Operates on raw dicts (no ORM objects required).

        Args:
            metadata: Parsed metadata YAML dict (has people section with aliases)
            md_frontmatter: Parsed MD frontmatter dict
            scene_data: Scene dict from YAML
            scene_name: Scene name for error messages

        Raises:
            ValueError: If scene references entities not in entry-level data
        """
        # Validate scene people against metadata YAML people (with aliases)
        scene_people = scene_data.get("people", [])
        yaml_people = metadata.get("people", [])

        # Build normalized set from metadata YAML people
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
                parts_match = any(
                    part in metadata_people_normalized
                    for part in normalized_scene_person.split()
                )
                if not parts_match:
                    raise ValueError(
                        f"Scene '{scene_name}' references person '{person_name}' "
                        f"not in metadata YAML people list"
                    )

        # Validate scene locations against MD frontmatter locations
        scene_locations = scene_data.get("locations", [])
        locations_data = md_frontmatter.get("locations", {})
        entry_location_names_normalized: Set[str] = set()
        if isinstance(locations_data, dict):
            for _, loc_names in locations_data.items():
                if isinstance(loc_names, list):
                    for loc_name in loc_names:
                        entry_location_names_normalized.add(
                            self._normalize_name(str(loc_name))
                        )

        for loc_name in scene_locations:
            if self._normalize_name(loc_name) not in entry_location_names_normalized:
                raise ValueError(
                    f"Scene '{scene_name}' references location '{loc_name}' "
                    f"not in entry locations list"
                )

        # Validate scene dates against MD frontmatter narrated_dates
        scene_dates = scene_data.get("date")
        if scene_dates:
            if not isinstance(scene_dates, list):
                scene_dates = [scene_dates]

            narrated_list = md_frontmatter.get("narrated_dates", [])
            entry_dates: Set[date] = set()
            for date_val in narrated_list:
                if isinstance(date_val, date):
                    entry_dates.add(date_val)
                elif isinstance(date_val, str):
                    try:
                        entry_dates.add(date.fromisoformat(date_val))
                    except ValueError:
                        pass

            for scene_date in scene_dates:
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

    # =========================================================================
    # Failure Tracking
    # =========================================================================

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
