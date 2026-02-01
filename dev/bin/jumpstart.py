#!/usr/bin/env python3
"""
jumpstart.py
------------
Transform narrative analysis files into clean metadata YAML format.

This script is part of Phase 14b: Jumpstart Migration. It performs file cleanup
only (no database operations) to create consistent YAML files ready for future
DB import.

Key Operations:
    1. Read narrative_analysis YAMLs (scenes, events, threads, arcs, tags, themes, motifs)
    2. Merge poems from legacy archive (by entry date)
    3. Merge references from legacy archive (by entry date)
    4. Resolve entity names (people, locations) via consolidated curation
    5. Write clean files to metadata/journal/YYYY/YYYY-MM-DD.yaml

Input Sources:
    - data/narrative_analysis/YYYY/YYYY-MM-DD_analysis.yaml
    - data/legacy/poems_archive.yaml
    - data/legacy/references_archive.yaml
    - data/curation/consolidated_people.yaml
    - data/curation/consolidated_locations.yaml

Output:
    - data/metadata/journal/YYYY/YYYY-MM-DD.yaml

Usage:
    python -m dev.bin.jumpstart [--dry-run] [--year YYYY] [--delete-source]

    --dry-run       Show what would be done without writing files
    --year YYYY     Process only entries from specific year
    --delete-source Delete narrative_analysis/ after successful transformation
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import (
    CURATION_DIR,
    JOURNAL_YAML_DIR,
    LEGACY_DIR,
    NARRATIVE_ANALYSIS_DIR,
)
from dev.utils.yaml_formatter import YAMLFormatter


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class PersonCanonical:
    """Canonical form of a person entity."""

    name: str
    lastname: Optional[str] = None
    alias: Optional[str | List[str]] = None
    disambiguator: Optional[str] = None
    dates: Set[str] = field(default_factory=set)  # Dates this person appears


def extract_base_name(raw_name: str) -> str:
    """Extract base name from parenthetical key like 'Paola (Sánchez)' -> 'Paola'."""
    import re
    match = re.match(r"^([^(]+?)(?:\s*\([^)]+\))?$", raw_name)
    return match.group(1).strip() if match else raw_name


@dataclass
class PeopleLookup:
    """Container for people lookup tables."""

    direct: Dict[str, PersonCanonical] = field(default_factory=dict)
    by_base_name: Dict[str, List[PersonCanonical]] = field(default_factory=dict)
    skipped: Set[str] = field(default_factory=set)  # Names exactly skipped
    skipped_by_date: Dict[str, Set[str]] = field(default_factory=dict)  # base_name -> dates

    def __len__(self) -> int:
        """Return count of unique people (not raw names)."""
        # Count unique people across all base names
        unique_people: Set[int] = set()
        for people_list in self.by_base_name.values():
            for person in people_list:
                unique_people.add(id(person))
        return len(unique_people)

    def is_skipped(self, raw_name: str, entry_date: str = "") -> bool:
        """Check if a name is intentionally skipped (optionally for a specific date)."""
        # Exact match
        if raw_name in self.skipped:
            return True
        # Base name + date match
        base = extract_base_name(raw_name)
        if base in self.skipped_by_date:
            if not entry_date or entry_date in self.skipped_by_date[base]:
                return True
        return False

    def resolve(self, raw_name: str, entry_date: str) -> Optional[PersonCanonical]:
        """
        Resolve a raw name to PersonCanonical using dates for disambiguation.
        """
        # Try direct lookup first
        if raw_name in self.direct:
            return self.direct[raw_name]

        # Try base name lookup with date disambiguation
        base = extract_base_name(raw_name)
        if base in self.by_base_name:
            candidates = self.by_base_name[base]

            # Filter by date
            matches = [p for p in candidates if entry_date in p.dates]

            if len(matches) == 1:
                return matches[0]
            # Multiple matches or no matches = unresolved

        return None


@dataclass
class TransformStats:
    """Statistics for the transformation run."""

    files_processed: int = 0
    files_written: int = 0
    files_skipped: int = 0
    people_resolved: int = 0
    people_unresolved: int = 0
    locations_resolved: int = 0
    locations_unresolved: int = 0
    poems_merged: int = 0
    references_merged: int = 0
    errors: List[str] = field(default_factory=list)
    # Track unresolved from curated years (these are errors)
    unresolved_people_curated: Dict[str, List[str]] = field(default_factory=dict)
    unresolved_locations_curated: Dict[str, List[str]] = field(default_factory=dict)


# =============================================================================
# Curation Loading
# =============================================================================


def load_consolidated_people(curation_dir: Path) -> PeopleLookup:
    """
    Load consolidated people curation and build lookups.

    Returns a PeopleLookup with:
    1. Direct lookup: raw_name -> PersonCanonical (for unique names)
    2. Base name lookup: base_name -> List[PersonCanonical] (for ambiguous names)

    The base name lookup is used when the direct lookup fails. It maps
    base names (e.g., 'Paola') to all people with that base name, along
    with their dates. The caller can then use dates to disambiguate.

    Args:
        curation_dir: Path to curation directory

    Returns:
        PeopleLookup object
    """
    people_file = curation_dir / "consolidated_people.yaml"
    if not people_file.exists():
        print(f"Warning: {people_file} not found")
        return PeopleLookup()

    with open(people_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    lookup = PeopleLookup()

    for person_key, info in data.items():
        if person_key.startswith("_"):
            continue  # Skip _skipped, _self sections

        canonical = info.get("canonical", {})
        if not canonical:
            continue

        # Handle multi-person entries (canonical is a list or has _multi_person)
        if isinstance(canonical, list) or canonical.get("_multi_person"):
            # For multi-person entries like "parents" or "Paolas",
            # we don't add to lookup - these need special handling
            continue

        # Handle canonical with name
        name = canonical.get("name")
        if not name:
            continue

        # Collect all dates for this person
        dates_dict = info.get("dates", {})
        all_dates: Set[str] = set()
        for year_dates in dates_dict.values():
            if isinstance(year_dates, list):
                all_dates.update(year_dates)

        person = PersonCanonical(
            name=name,
            lastname=canonical.get("lastname"),
            alias=canonical.get("alias"),
            disambiguator=canonical.get("disambiguator"),
            dates=all_dates,
        )

        # Map all raw_names to this canonical (direct lookup)
        raw_names = info.get("raw_names", [person_key])
        for raw_name in raw_names:
            lookup.direct[raw_name] = person
            # Also add base name to base_name_lookup
            base = extract_base_name(raw_name)
            if base not in lookup.by_base_name:
                lookup.by_base_name[base] = []
            if person not in lookup.by_base_name[base]:
                lookup.by_base_name[base].append(person)

        # Also add the person_key's base name
        base_key = extract_base_name(person_key)
        if base_key not in lookup.by_base_name:
            lookup.by_base_name[base_key] = []
        if person not in lookup.by_base_name[base_key]:
            lookup.by_base_name[base_key].append(person)

    # Load skipped entries (intentionally omitted people)
    skipped_section = data.get("_skipped", {})
    for skipped_name, skip_info in skipped_section.items():
        lookup.skipped.add(skipped_name)
        # Also index by base name + dates for date-aware skipping
        base = extract_base_name(skipped_name)
        if base not in lookup.skipped_by_date:
            lookup.skipped_by_date[base] = set()
        # Collect dates from skip_info
        if isinstance(skip_info, dict):
            dates_dict = skip_info.get("dates", {})
            for year_dates in dates_dict.values():
                if isinstance(year_dates, list):
                    lookup.skipped_by_date[base].update(year_dates)

    # Also load _self entries as skipped
    self_section = data.get("_self", {})
    for self_name, self_info in self_section.items():
        lookup.skipped.add(self_name)
        base = extract_base_name(self_name)
        if base not in lookup.skipped_by_date:
            lookup.skipped_by_date[base] = set()
        if isinstance(self_info, dict):
            dates_dict = self_info.get("dates", {})
            for year_dates in dates_dict.values():
                if isinstance(year_dates, list):
                    lookup.skipped_by_date[base].update(year_dates)

    return lookup


def load_consolidated_locations(
    curation_dir: Path,
) -> Tuple[Dict[str, Tuple[str, str]], Set[str]]:
    """
    Load consolidated locations curation and build raw_name -> (city, canonical_name) lookup.

    Args:
        curation_dir: Path to curation directory

    Returns:
        Tuple of (lookup dict, skipped set):
        - Dictionary mapping raw names to (city, canonical_name) tuples
        - Set of location names that should be skipped
    """
    locations_file = curation_dir / "consolidated_locations.yaml"
    if not locations_file.exists():
        print(f"Warning: {locations_file} not found")
        return {}, set()

    with open(locations_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    lookup: Dict[str, Tuple[str, str]] = {}
    skipped: Set[str] = set()

    # Load skipped entries from _skipped section
    skipped_section = data.get("_skipped", {})
    for city, locations in skipped_section.items():
        if isinstance(locations, dict):
            for loc_name in locations.keys():
                skipped.add(loc_name)

    for city, locations in data.items():
        if city.startswith("_"):
            continue  # Skip _skipped sections

        if not isinstance(locations, dict):
            continue

        for canonical_name, info in locations.items():
            if canonical_name.startswith("_"):
                continue

            # Map the canonical name itself
            lookup[canonical_name] = (city, canonical_name)

            # Map all raw_names
            if isinstance(info, dict):
                raw_names = info.get("raw_names", [])
                for raw_name in raw_names:
                    lookup[raw_name] = (city, canonical_name)

    return lookup, skipped


# =============================================================================
# Legacy Archive Loading
# =============================================================================


def load_legacy_poems(legacy_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load poems archive keyed by entry date.

    Args:
        legacy_dir: Path to legacy directory

    Returns:
        Dictionary mapping date strings to list of poem dicts
    """
    poems_file = legacy_dir / "poems_archive.yaml"
    if not poems_file.exists():
        return {}

    with open(poems_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return data


def load_legacy_references(legacy_dir: Path) -> Dict[str, List[Dict[str, Any]]]:
    """
    Load references archive keyed by entry date.

    Args:
        legacy_dir: Path to legacy directory

    Returns:
        Dictionary mapping date strings to list of reference dicts
    """
    refs_file = legacy_dir / "references_archive.yaml"
    if not refs_file.exists():
        return {}

    with open(refs_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    return data


# =============================================================================
# Entity Resolution
# =============================================================================


def resolve_location(
    raw_name: str,
    locations_lookup: Dict[str, Tuple[str, str]],
    unresolved: Set[str],
) -> Optional[Tuple[str, str]]:
    """
    Resolve a raw location name to (city, canonical_name).

    Args:
        raw_name: Raw location name from source file
        locations_lookup: Lookup dictionary from consolidated curation
        unresolved: Set to track unresolved names

    Returns:
        Tuple of (city, canonical_name), or None if unresolved
    """
    if raw_name in locations_lookup:
        return locations_lookup[raw_name]
    else:
        unresolved.add(raw_name)
        return None


# =============================================================================
# Transformation
# =============================================================================


def collect_entry_people(
    scenes: List[Dict[str, Any]],
    threads: List[Dict[str, Any]],
    people_lookup: PeopleLookup,
    entry_date: str,
    stats: TransformStats,
) -> List[Dict[str, Any]]:
    """
    Collect all unique people from scenes and threads.

    Args:
        scenes: List of scene dicts
        threads: List of thread dicts
        people_lookup: People resolution lookup
        entry_date: Entry date string (YYYY-MM-DD) for tracking errors
        stats: TransformStats to update

    Returns:
        List of person dicts with full canonical info
    """
    seen_names: Set[str] = set()
    people_list: List[Dict[str, Any]] = []
    unresolved: Set[str] = set()

    # People curated for 2021+
    year = int(entry_date[:4])
    is_curated_year = year >= 2021

    # Collect from scenes
    for scene in scenes:
        for raw_name in scene.get("people", []):
            person = people_lookup.resolve(raw_name, entry_date)
            if person:
                if person.name not in seen_names:
                    seen_names.add(person.name)
                    person_dict: Dict[str, Any] = {"name": person.name}
                    if person.lastname:
                        person_dict["lastname"] = person.lastname
                    if person.alias:
                        person_dict["alias"] = person.alias
                    people_list.append(person_dict)
            elif not people_lookup.is_skipped(raw_name, entry_date):
                # Only track as unresolved if not intentionally skipped
                unresolved.add(raw_name)

    # Collect from threads
    for thread in threads:
        for raw_name in thread.get("people", []):
            person = people_lookup.resolve(raw_name, entry_date)
            if person:
                if person.name not in seen_names:
                    seen_names.add(person.name)
                    person_dict = {"name": person.name}
                    if person.lastname:
                        person_dict["lastname"] = person.lastname
                    if person.alias:
                        person_dict["alias"] = person.alias
                    people_list.append(person_dict)
            elif not people_lookup.is_skipped(raw_name, entry_date):
                # Only track as unresolved if not intentionally skipped
                unresolved.add(raw_name)

    # Update stats
    stats.people_resolved += len(people_list)
    stats.people_unresolved += len(unresolved)

    # Track unresolved from curated years as errors
    if is_curated_year and unresolved:
        for name in unresolved:
            if name not in stats.unresolved_people_curated:
                stats.unresolved_people_curated[name] = []
            stats.unresolved_people_curated[name].append(entry_date)

    return people_list


def transform_scenes(
    scenes: List[Dict[str, Any]],
    people_lookup: PeopleLookup,
    locations_lookup: Dict[str, Tuple[str, str]],
    locations_skipped: Set[str],
    stats: TransformStats,
    entry_date: str,
) -> List[Dict[str, Any]]:
    """
    Transform scenes with resolved entities.

    Args:
        scenes: List of scene dicts from source
        people_lookup: People resolution lookup
        locations_lookup: Locations resolution lookup
        stats: Statistics to update
        entry_date: Entry date string for tracking errors

    Returns:
        List of transformed scene dicts
    """
    unresolved_people: Set[str] = set()
    unresolved_locations: Set[str] = set()
    total_locations: int = 0
    result = []

    # Locations curated for 2023+
    year = int(entry_date[:4])
    is_curated_year = year >= 2023

    for scene in scenes:
        transformed = {
            "name": scene.get("name", ""),
            "description": scene.get("description", ""),
        }

        # Handle date (can be single date or list)
        scene_date = scene.get("date")
        if scene_date:
            transformed["date"] = scene_date

        # Resolve people - use canonical name as reference
        raw_people = scene.get("people", [])
        if raw_people:
            resolved_people = []
            for raw_name in raw_people:
                person = people_lookup.resolve(raw_name, entry_date)
                if person:
                    resolved_people.append(person.name)
                elif people_lookup.is_skipped(raw_name, entry_date):
                    # Skipped people are omitted from output
                    pass
                else:
                    unresolved_people.add(raw_name)
                    resolved_people.append(raw_name)  # Keep raw if unresolved
            if resolved_people:
                transformed["people"] = resolved_people

        # Resolve locations
        raw_locations = scene.get("locations", [])
        if raw_locations:
            total_locations += len(raw_locations)
            resolved_locations = []
            for raw_name in raw_locations:
                loc = resolve_location(raw_name, locations_lookup, unresolved_locations)
                if loc:
                    resolved_locations.append(loc[1])  # Use canonical name
                else:
                    resolved_locations.append(raw_name)  # Keep raw if unresolved
            if resolved_locations:
                transformed["locations"] = resolved_locations

        result.append(transformed)

    # Update location stats (people stats handled at entry level)
    stats.locations_resolved += total_locations - len(unresolved_locations)
    stats.locations_unresolved += len(unresolved_locations)

    # Track unresolved from curated years as errors (excluding skipped)
    if is_curated_year and unresolved_locations:
        for name in unresolved_locations:
            if name in locations_skipped:
                continue  # Intentionally skipped
            if name not in stats.unresolved_locations_curated:
                stats.unresolved_locations_curated[name] = []
            stats.unresolved_locations_curated[name].append(entry_date)

    return result


def transform_entry(
    source_data: Dict[str, Any],
    entry_date: str,
    people_lookup: PeopleLookup,
    locations_lookup: Dict[str, Tuple[str, str]],
    locations_skipped: Set[str],
    poems_archive: Dict[str, List[Dict[str, Any]]],
    refs_archive: Dict[str, List[Dict[str, Any]]],
    stats: TransformStats,
) -> Dict[str, Any]:
    """
    Transform a single narrative analysis entry to clean metadata format.

    Args:
        source_data: Parsed YAML from narrative analysis file
        entry_date: Entry date string (YYYY-MM-DD)
        people_lookup: People resolution lookup
        locations_lookup: Locations resolution lookup
        locations_skipped: Set of location names to skip
        poems_archive: Poems keyed by date
        refs_archive: References keyed by date
        stats: Statistics to update

    Returns:
        Transformed metadata dictionary
    """
    result: Dict[str, Any] = {}

    # Copy core fields
    result["date"] = entry_date

    if "summary" in source_data:
        result["summary"] = source_data["summary"]

    if "rating" in source_data:
        result["rating"] = source_data["rating"]

    if "rating_justification" in source_data:
        result["rating_justification"] = source_data["rating_justification"]

    # Preserve sub_ratings for 2015-2019 (two-rubric rating system)
    # These won't be imported to DB (schema only supports single rating) but
    # should be preserved in the YAML for completeness
    if "sub_ratings" in source_data:
        result["sub_ratings"] = source_data["sub_ratings"]

    # Copy list fields directly
    if "arcs" in source_data:
        result["arcs"] = source_data["arcs"]

    if "tags" in source_data:
        result["tags"] = source_data["tags"]

    if "themes" in source_data:
        result["themes"] = source_data["themes"]

    if "motifs" in source_data:
        result["motifs"] = source_data["motifs"]

    # Collect all people from scenes and threads, build top-level people list
    scenes = source_data.get("scenes", [])
    threads = source_data.get("threads", [])
    people_list = collect_entry_people(
        scenes, threads, people_lookup, entry_date, stats
    )
    if people_list:
        result["people"] = people_list

    # Transform scenes with entity resolution
    if scenes:
        result["scenes"] = transform_scenes(
            scenes,
            people_lookup,
            locations_lookup,
            locations_skipped,
            stats,
            entry_date,
        )

    # Copy events (scene names should already match transformed names)
    if "events" in source_data:
        result["events"] = source_data["events"]

    # Copy threads (people references kept as-is, matched via top-level people)
    if threads:
        result["threads"] = threads

    # Merge poems from legacy archive
    if entry_date in poems_archive:
        result["poems"] = poems_archive[entry_date]
        stats.poems_merged += len(poems_archive[entry_date])

    # Merge references from legacy archive
    if entry_date in refs_archive:
        result["references"] = refs_archive[entry_date]
        stats.references_merged += len(refs_archive[entry_date])

    return result


# =============================================================================
# File Processing
# =============================================================================


def process_narrative_analysis(
    source_dir: Path,
    output_dir: Path,
    people_lookup: PeopleLookup,
    locations_lookup: Dict[str, Tuple[str, str]],
    locations_skipped: Set[str],
    poems_archive: Dict[str, List[Dict[str, Any]]],
    refs_archive: Dict[str, List[Dict[str, Any]]],
    year_filter: Optional[int],
    dry_run: bool,
    formatter: YAMLFormatter,
) -> TransformStats:
    """
    Process all narrative analysis files.

    Args:
        source_dir: Path to narrative_analysis directory
        output_dir: Path to metadata/journal directory
        people_lookup: People resolution lookup
        locations_lookup: Locations resolution lookup
        locations_skipped: Set of location names to skip
        poems_archive: Poems keyed by date
        refs_archive: References keyed by date
        year_filter: Optional year to filter by
        dry_run: If True, don't write files
        formatter: YAMLFormatter instance for output formatting

    Returns:
        TransformStats with processing results
    """
    stats = TransformStats()

    # Find all year directories
    if not source_dir.exists():
        stats.errors.append(f"Source directory not found: {source_dir}")
        return stats

    year_dirs = sorted([d for d in source_dir.iterdir() if d.is_dir()])

    for year_dir in year_dirs:
        year = year_dir.name

        # Apply year filter if specified
        if year_filter and year != str(year_filter):
            continue

        # Process all analysis files in this year
        analysis_files = sorted(year_dir.glob("*_analysis.yaml"))

        for analysis_file in analysis_files:
            stats.files_processed += 1

            # Extract date from filename (YYYY-MM-DD_analysis.yaml)
            entry_date = analysis_file.stem.replace("_analysis", "")

            try:
                # Load source data
                with open(analysis_file, "r", encoding="utf-8") as f:
                    source_data = yaml.safe_load(f) or {}

                # Transform
                transformed = transform_entry(
                    source_data,
                    entry_date,
                    people_lookup,
                    locations_lookup,
                    locations_skipped,
                    poems_archive,
                    refs_archive,
                    stats,
                )

                # Determine output path
                output_year_dir = output_dir / year
                output_file = output_year_dir / f"{entry_date}.yaml"

                if dry_run:
                    print(f"Would write: {output_file}")
                    stats.files_skipped += 1
                else:
                    # Create output directory
                    output_year_dir.mkdir(parents=True, exist_ok=True)

                    # Format and write transformed data
                    formatted_data = formatter.format_document(transformed)
                    formatted_yaml = formatter.format_dict(formatted_data)

                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write(formatted_yaml)
                        f.write("\n")

                    stats.files_written += 1

            except Exception as e:
                stats.errors.append(f"{analysis_file}: {e}")
                stats.files_skipped += 1

    return stats


# =============================================================================
# Main
# =============================================================================


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Transform narrative analysis files to clean metadata YAML"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without writing files",
    )
    parser.add_argument(
        "--year",
        type=int,
        help="Process only entries from specific year",
    )
    parser.add_argument(
        "--delete-source",
        action="store_true",
        help="Delete narrative_analysis/ after successful transformation",
    )

    args = parser.parse_args()

    print("Loading consolidated curation files...")
    people_lookup = load_consolidated_people(CURATION_DIR)
    locations_lookup, locations_skipped = load_consolidated_locations(CURATION_DIR)
    print(f"  People entries: {len(people_lookup)}")
    print(f"  Locations entries: {len(locations_lookup)}")

    print("\nLoading legacy archives...")
    poems_archive = load_legacy_poems(LEGACY_DIR)
    refs_archive = load_legacy_references(LEGACY_DIR)
    print(f"  Poems entries: {len(poems_archive)}")
    print(f"  References entries: {len(refs_archive)}")

    # Create YAML formatter
    formatter = YAMLFormatter()

    print("\nProcessing narrative analysis files...")
    stats = process_narrative_analysis(
        NARRATIVE_ANALYSIS_DIR,
        JOURNAL_YAML_DIR,
        people_lookup,
        locations_lookup,
        locations_skipped,
        poems_archive,
        refs_archive,
        args.year,
        args.dry_run,
        formatter,
    )

    # Print results
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Files processed: {stats.files_processed}")
    print(f"Files written: {stats.files_written}")
    print(f"Files skipped: {stats.files_skipped}")
    print(f"People resolved: {stats.people_resolved}")
    print(f"People unresolved: {stats.people_unresolved}")
    print(f"Locations resolved: {stats.locations_resolved}")
    print(f"Locations unresolved: {stats.locations_unresolved}")
    print(f"Poems merged: {stats.poems_merged}")
    print(f"References merged: {stats.references_merged}")

    if stats.errors:
        print(f"\nERRORS ({len(stats.errors)}):")
        for error in stats.errors[:10]:
            print(f"  ✗ {error}")
        if len(stats.errors) > 10:
            print(f"  ... and {len(stats.errors) - 10} more")

    # Report unresolved from curated years (these are curation errors)
    if stats.unresolved_people_curated:
        print(f"\n⚠ UNRESOLVED PEOPLE FROM CURATED YEARS (2021+):")
        for name, dates in sorted(stats.unresolved_people_curated.items()):
            print(f"  - {name}: {dates[:5]}{'...' if len(dates) > 5 else ''}")

    if stats.unresolved_locations_curated:
        print(f"\n⚠ UNRESOLVED LOCATIONS FROM CURATED YEARS (2023+):")
        for name, dates in sorted(stats.unresolved_locations_curated.items()):
            print(f"  - {name}: {dates[:5]}{'...' if len(dates) > 5 else ''}")

    # Handle source deletion
    if args.delete_source and not args.dry_run and not stats.errors:
        print("\n⚠ --delete-source specified but not implemented for safety")
        print("  Manually delete narrative_analysis/ after verifying output")

    if stats.errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
