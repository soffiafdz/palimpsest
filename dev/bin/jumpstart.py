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


# =============================================================================
# Curation Loading
# =============================================================================


def load_consolidated_people(curation_dir: Path) -> Dict[str, PersonCanonical]:
    """
    Load consolidated people curation and build raw_name -> canonical lookup.

    Args:
        curation_dir: Path to curation directory

    Returns:
        Dictionary mapping raw names to PersonCanonical objects
    """
    people_file = curation_dir / "consolidated_people.yaml"
    if not people_file.exists():
        print(f"Warning: {people_file} not found")
        return {}

    with open(people_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    lookup: Dict[str, PersonCanonical] = {}

    for person_key, info in data.items():
        if person_key.startswith("_"):
            continue  # Skip _skipped, _self sections

        canonical = info.get("canonical", {})
        if not canonical:
            continue

        # Handle multi-person entries (canonical is a list)
        if isinstance(canonical, list):
            # For multi-person entries like "parents" or "Paolas",
            # we don't add to lookup - these need special handling
            continue

        # Handle canonical with name
        name = canonical.get("name")
        if not name:
            continue

        person = PersonCanonical(
            name=name,
            lastname=canonical.get("lastname"),
            alias=canonical.get("alias"),
            disambiguator=canonical.get("disambiguator"),
        )

        # Map all raw_names to this canonical
        raw_names = info.get("raw_names", [person_key])
        for raw_name in raw_names:
            lookup[raw_name] = person

    return lookup


def load_consolidated_locations(
    curation_dir: Path,
) -> Dict[str, Tuple[str, str]]:
    """
    Load consolidated locations curation and build raw_name -> (city, canonical_name) lookup.

    Args:
        curation_dir: Path to curation directory

    Returns:
        Dictionary mapping raw names to (city, canonical_name) tuples
    """
    locations_file = curation_dir / "consolidated_locations.yaml"
    if not locations_file.exists():
        print(f"Warning: {locations_file} not found")
        return {}

    with open(locations_file, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    lookup: Dict[str, Tuple[str, str]] = {}

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

    return lookup


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


def resolve_person(
    raw_name: str,
    people_lookup: Dict[str, PersonCanonical],
    unresolved: Set[str],
) -> Optional[Dict[str, Any]]:
    """
    Resolve a raw person name to canonical form.

    Args:
        raw_name: Raw person name from source file
        people_lookup: Lookup dictionary from consolidated curation
        unresolved: Set to track unresolved names

    Returns:
        Dictionary with canonical person info, or None if skip/unresolved
    """
    if raw_name in people_lookup:
        person = people_lookup[raw_name]
        result: Dict[str, Any] = {"name": person.name}
        if person.lastname:
            result["lastname"] = person.lastname
        if person.alias:
            result["alias"] = person.alias
        return result
    else:
        unresolved.add(raw_name)
        # Return raw name as-is for uncurated entries
        return {"name": raw_name}


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


def transform_scenes(
    scenes: List[Dict[str, Any]],
    people_lookup: Dict[str, PersonCanonical],
    locations_lookup: Dict[str, Tuple[str, str]],
    stats: TransformStats,
) -> List[Dict[str, Any]]:
    """
    Transform scenes with resolved entities.

    Args:
        scenes: List of scene dicts from source
        people_lookup: People resolution lookup
        locations_lookup: Locations resolution lookup
        stats: Statistics to update

    Returns:
        List of transformed scene dicts
    """
    unresolved_people: Set[str] = set()
    unresolved_locations: Set[str] = set()
    result = []

    for scene in scenes:
        transformed = {
            "name": scene.get("name", ""),
            "description": scene.get("description", ""),
        }

        # Handle date (can be single date or list)
        scene_date = scene.get("date")
        if scene_date:
            transformed["date"] = scene_date

        # Resolve people
        raw_people = scene.get("people", [])
        if raw_people:
            resolved_people = []
            for raw_name in raw_people:
                person = resolve_person(raw_name, people_lookup, unresolved_people)
                if person:
                    # Use alias if available, otherwise name
                    if person.get("alias"):
                        alias = person["alias"]
                        if isinstance(alias, list):
                            resolved_people.append(alias[0])
                        else:
                            resolved_people.append(alias)
                    else:
                        resolved_people.append(person["name"])
            if resolved_people:
                transformed["people"] = resolved_people

        # Resolve locations
        raw_locations = scene.get("locations", [])
        if raw_locations:
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

    # Update stats
    stats.people_resolved += len(raw_people) - len(unresolved_people) if raw_people else 0
    stats.people_unresolved += len(unresolved_people)
    stats.locations_resolved += len(raw_locations) - len(unresolved_locations) if raw_locations else 0
    stats.locations_unresolved += len(unresolved_locations)

    return result


def transform_entry(
    source_data: Dict[str, Any],
    entry_date: str,
    people_lookup: Dict[str, PersonCanonical],
    locations_lookup: Dict[str, Tuple[str, str]],
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

    # Copy list fields directly
    if "arcs" in source_data:
        result["arcs"] = source_data["arcs"]

    if "tags" in source_data:
        result["tags"] = source_data["tags"]

    if "themes" in source_data:
        result["themes"] = source_data["themes"]

    if "motifs" in source_data:
        result["motifs"] = source_data["motifs"]

    # Transform scenes with entity resolution
    if "scenes" in source_data:
        result["scenes"] = transform_scenes(
            source_data["scenes"],
            people_lookup,
            locations_lookup,
            stats,
        )

    # Copy events (scene names should already match transformed names)
    if "events" in source_data:
        result["events"] = source_data["events"]

    # Copy threads
    if "threads" in source_data:
        result["threads"] = source_data["threads"]

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
    people_lookup: Dict[str, PersonCanonical],
    locations_lookup: Dict[str, Tuple[str, str]],
    poems_archive: Dict[str, List[Dict[str, Any]]],
    refs_archive: Dict[str, List[Dict[str, Any]]],
    year_filter: Optional[int],
    dry_run: bool,
) -> TransformStats:
    """
    Process all narrative analysis files.

    Args:
        source_dir: Path to narrative_analysis directory
        output_dir: Path to metadata/journal directory
        people_lookup: People resolution lookup
        locations_lookup: Locations resolution lookup
        poems_archive: Poems keyed by date
        refs_archive: References keyed by date
        year_filter: Optional year to filter by
        dry_run: If True, don't write files

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

                    # Write transformed data
                    with open(output_file, "w", encoding="utf-8") as f:
                        f.write("# Exported from jumpstart — do not edit manually\n")
                        yaml.dump(
                            transformed,
                            f,
                            default_flow_style=False,
                            allow_unicode=True,
                            sort_keys=False,
                        )

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
    locations_lookup = load_consolidated_locations(CURATION_DIR)
    print(f"  People entries: {len(people_lookup)}")
    print(f"  Locations entries: {len(locations_lookup)}")

    print("\nLoading legacy archives...")
    poems_archive = load_legacy_poems(LEGACY_DIR)
    refs_archive = load_legacy_references(LEGACY_DIR)
    print(f"  Poems entries: {len(poems_archive)}")
    print(f"  References entries: {len(refs_archive)}")

    print("\nProcessing narrative analysis files...")
    stats = process_narrative_analysis(
        NARRATIVE_ANALYSIS_DIR,
        JOURNAL_YAML_DIR,
        people_lookup,
        locations_lookup,
        poems_archive,
        refs_archive,
        args.year,
        args.dry_run,
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

    # Handle source deletion
    if args.delete_source and not args.dry_run and not stats.errors:
        print("\n⚠ --delete-source specified but not implemented for safety")
        print("  Manually delete narrative_analysis/ after verifying output")

    if stats.errors:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
