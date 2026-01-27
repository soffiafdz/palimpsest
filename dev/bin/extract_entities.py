#!/usr/bin/env python3
"""
extract_entities.py
-------------------
Extract people and locations from journal MD frontmatter AND narrative_analysis
scenes/threads for curation, organized by year.

Generates per-year curation files with all occurrences listed for each raw name,
making it easy to verify context and curate entities.

Output Format:
    # YYYY_people_curation.yaml
    Catherine:
      dates: [2024-01-05, 2024-02-10]
      canonical:
        name: null
        lastname: null
        alias: null

    # YYYY_locations_curation.yaml
    Montréal:
      Home:
        dates: [2024-01-05, 2024-02-10]
        canonical: null

Usage:
    python -m dev.bin.extract_entities [--dry-run]

Output:
    - data/curation/YYYY_people_curation.yaml (one per year)
    - data/curation/YYYY_locations_curation.yaml (one per year)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import MD_DIR, NARRATIVE_ANALYSIS_DIR, CURATION_DIR


# =============================================================================
# Data Structures
# =============================================================================

# People: year -> raw_name -> set of dates
PeopleData = Dict[str, Dict[str, Set[str]]]

# Locations: year -> city -> raw_name -> set of dates
LocationsData = Dict[str, Dict[str, Dict[str, Set[str]]]]


# =============================================================================
# MD Frontmatter Extraction
# =============================================================================

def extract_frontmatter(md_path: Path) -> Optional[Dict[str, Any]]:
    """Extract YAML frontmatter from a markdown file."""
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        print(f"Warning: Failed to read {md_path}: {e}")
        return None

    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        print(f"Warning: Failed to parse frontmatter in {md_path}: {e}")
        return None


def extract_from_md(
    md_path: Path,
    people_data: PeopleData,
    locations_data: LocationsData,
) -> None:
    """Extract people and locations from MD frontmatter into data structures."""
    frontmatter = extract_frontmatter(md_path)
    if not frontmatter:
        return

    # Get date
    date_val = frontmatter.get("date")
    if date_val and hasattr(date_val, "isoformat"):
        date_str = date_val.isoformat()
    elif date_val:
        date_str = str(date_val)
    else:
        date_str = md_path.stem

    # Extract year
    year = date_str[:4] if len(date_str) >= 4 else "unknown"

    # Extract people
    people_list = frontmatter.get("people", [])
    if people_list:
        if year not in people_data:
            people_data[year] = defaultdict(set)
        for person in people_list:
            if person:
                people_data[year][str(person)].add(date_str)

    # Extract locations (hierarchical: {City: [loc1, loc2]})
    locations_dict = frontmatter.get("locations", {})
    if isinstance(locations_dict, dict):
        if year not in locations_data:
            locations_data[year] = defaultdict(lambda: defaultdict(set))
        for city, locs in locations_dict.items():
            if not city or not locs:
                continue
            city_str = str(city)
            if isinstance(locs, list):
                for loc in locs:
                    if loc:
                        locations_data[year][city_str][str(loc)].add(date_str)
            elif locs:
                locations_data[year][city_str][str(locs)].add(date_str)


# =============================================================================
# Narrative Analysis Extraction
# =============================================================================

def extract_from_narrative_yaml(
    yaml_path: Path,
    people_data: PeopleData,
    locations_data: LocationsData,
) -> None:
    """Extract people and locations from narrative_analysis YAML."""
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        print(f"Warning: Failed to parse {yaml_path}: {e}")
        return

    if not data:
        return

    # Get date
    date_val = data.get("date", yaml_path.stem.split("_")[0])
    if date_val and hasattr(date_val, "isoformat"):
        date_str = date_val.isoformat()
    else:
        date_str = str(date_val) if date_val else yaml_path.stem

    year = date_str[:4] if len(date_str) >= 4 else "unknown"

    # Get city for locations
    city = data.get("city", "_unassigned")
    if not city:
        city = "_unassigned"
    city = str(city).strip()

    def add_people(person_list: List) -> None:
        if not person_list:
            return
        if year not in people_data:
            people_data[year] = defaultdict(set)
        for person in person_list:
            if person:
                people_data[year][str(person)].add(date_str)

    def add_locations(loc_list: List) -> None:
        if not loc_list:
            return
        if year not in locations_data:
            locations_data[year] = defaultdict(lambda: defaultdict(set))
        for location in loc_list:
            if location:
                locations_data[year][city][str(location)].add(date_str)

    # Extract from scenes
    for scene in data.get("scenes", []) or []:
        if not isinstance(scene, dict):
            continue
        add_people(scene.get("people", []))
        add_locations(scene.get("locations", []))

    # Extract from threads
    for thread in data.get("threads", []) or []:
        if not isinstance(thread, dict):
            continue
        add_people(thread.get("people", []))
        add_locations(thread.get("locations", []))


# =============================================================================
# Output Generation
# =============================================================================

def generate_people_yaml(year_data: Dict[str, Set[str]]) -> Dict[str, Any]:
    """Generate people curation YAML for a single year."""
    output = {}

    # Sort alphabetically by raw name
    for raw_name in sorted(year_data.keys(), key=str.lower):
        dates = sorted(year_data[raw_name])
        output[raw_name] = {
            "dates": dates,
            "canonical": {
                "name": None,
                "lastname": None,
                "alias": None,
            }
        }

    return output


def generate_locations_yaml(
    year_data: Dict[str, Dict[str, Set[str]]]
) -> Dict[str, Any]:
    """Generate locations curation YAML for a single year."""
    output = {}

    # Sort by city alphabetically
    for city in sorted(year_data.keys(), key=str.lower):
        city_locs = year_data[city]
        city_output = {}

        # Sort locations alphabetically within city
        for raw_name in sorted(city_locs.keys(), key=str.lower):
            dates = sorted(city_locs[raw_name])
            city_output[raw_name] = {
                "dates": dates,
                "canonical": None,
            }

        output[city] = city_output

    return output


def write_yaml_file(path: Path, data: Dict[str, Any], header: str) -> None:
    """Write YAML file with header comment."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n")
        yaml.dump(
            data,
            f,
            default_flow_style=None,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )


# =============================================================================
# Main
# =============================================================================

def extract_all(dry_run: bool = False) -> Tuple[int, int]:
    """Extract all entities and generate per-year curation files."""
    people_data: PeopleData = {}
    locations_data: LocationsData = {}

    # --- Extract from MD frontmatter ---
    md_files = sorted(MD_DIR.glob("**/*.md"))
    print(f"Scanning {len(md_files)} MD files...")

    for md_path in md_files:
        extract_from_md(md_path, people_data, locations_data)

    # --- Extract from narrative_analysis ---
    yaml_files = sorted(NARRATIVE_ANALYSIS_DIR.glob("**/*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]
    print(f"Scanning {len(yaml_files)} narrative_analysis YAML files...")

    for yaml_path in yaml_files:
        extract_from_narrative_yaml(yaml_path, people_data, locations_data)

    # --- Statistics ---
    total_people = sum(len(year_data) for year_data in people_data.values())
    total_locations = sum(
        len(locs)
        for year_data in locations_data.values()
        for locs in year_data.values()
    )

    print(f"\nPeople: {total_people} unique names across {len(people_data)} years")
    print(f"Locations: {total_locations} unique names across {len(locations_data)} years")

    # --- Generate files ---
    if not dry_run:
        CURATION_DIR.mkdir(parents=True, exist_ok=True)

        people_header = """# People Curation File
#
# Format:
#   RawName:
#     dates: [list of entry dates where this name appears]
#     canonical:
#       name: First name
#       lastname: Last name
#       alias: Short alias (if any)
#
# Special markers:
#   same_as: OtherName    # This is the same person as OtherName
#   self: true            # This refers to the author
#   skip: true            # Invalid entry, ignore
#
# For disambiguation (two different people with same name):
#   Monica (college):
#     dates: [2015-01-05]
#     canonical: {name: Monica, lastname: García, alias: null}
#   Monica (work):
#     dates: [2024-03-15]
#     canonical: {name: Monica, lastname: López, alias: null}
"""

        locations_header = """# Locations Curation File
#
# Format:
#   CityName:
#     RawLocationName:
#       dates: [list of entry dates]
#       canonical: Canonical location name
#
# Special markers:
#   same_as: OtherLocation  # Same location as another entry
#   skip: true              # Invalid entry, ignore
"""

        # Write people files
        for year in sorted(people_data.keys()):
            year_yaml = generate_people_yaml(people_data[year])
            path = CURATION_DIR / f"{year}_people_curation.yaml"
            write_yaml_file(path, year_yaml, people_header)
            print(f"  Saved {path.name} ({len(people_data[year])} names)")

        # Write locations files
        for year in sorted(locations_data.keys()):
            year_yaml = generate_locations_yaml(locations_data[year])
            path = CURATION_DIR / f"{year}_locations_curation.yaml"
            write_yaml_file(path, year_yaml, locations_header)
            loc_count = sum(len(locs) for locs in locations_data[year].values())
            print(f"  Saved {path.name} ({loc_count} locations)")

    else:
        print("\n[DRY RUN] Would generate:")
        for year in sorted(people_data.keys()):
            print(f"  {year}_people_curation.yaml ({len(people_data[year])} names)")
        for year in sorted(locations_data.keys()):
            loc_count = sum(len(locs) for locs in locations_data[year].values())
            print(f"  {year}_locations_curation.yaml ({loc_count} locations)")

    return total_people, total_locations


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract people and locations for curation, organized by year"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write output files, just show statistics"
    )
    args = parser.parse_args()

    extract_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
