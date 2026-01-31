#!/usr/bin/env python3
"""
entity_summary.py
-----------------
Generate a frequency-based summary report of curated entities.

Reads per-year curation YAML files from the curation directory and
aggregates entity counts across all years, printing a formatted
text report to stdout.

Key Features:
    - Aggregates people by raw name across all year files
    - Aggregates locations by city and raw name
    - Sorts by total frequency (descending)
    - Shows per-year breakdowns sorted by most recent year first

Usage:
    python -m dev.bin.entity_summary                    # Both people and locations
    python -m dev.bin.entity_summary --type people      # People only
    python -m dev.bin.entity_summary --type locations   # Locations only

Dependencies:
    - PyYAML for reading curation files
    - dev.core.paths for CURATION_DIR
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import CURATION_DIR


def load_yaml(path: Path) -> Dict:
    """
    Load a YAML file and return its contents.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed YAML content as a dictionary
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_year(path: Path) -> str:
    """
    Extract the year prefix from a curation filename.

    Args:
        path: Path like 2024_people_curation.yaml

    Returns:
        Year string, e.g. "2024"
    """
    return path.name.split("_")[0]


def aggregate_people() -> Dict[str, Dict[str, int]]:
    """
    Aggregate people counts across all per-year curation files.

    Returns:
        Dict mapping raw_name -> {year: count_of_dates}
    """
    result: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path in sorted(CURATION_DIR.glob("*_people_curation.yaml")):
        year = extract_year(path)
        data = load_yaml(path)
        for raw_name, info in data.items():
            if not isinstance(info, dict) or "dates" not in info:
                continue
            count = len(info["dates"])
            result[raw_name][year] += count
    return dict(result)


def aggregate_locations() -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Aggregate location counts across all per-year curation files.

    Returns:
        Dict mapping city -> raw_name -> {year: count_of_dates}
    """
    result: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(int))
    )
    for path in sorted(CURATION_DIR.glob("*_locations_curation.yaml")):
        year = extract_year(path)
        data = load_yaml(path)
        for city, locations in data.items():
            if not isinstance(locations, dict):
                continue
            for raw_name, info in locations.items():
                if not isinstance(info, dict) or "dates" not in info:
                    continue
                count = len(info["dates"])
                result[city][raw_name][year] += count
    return dict(result)


def format_year_breakdown(year_counts: Dict[str, int]) -> str:
    """
    Format per-year counts as a comma-separated string, sorted descending by year.

    Args:
        year_counts: Mapping of year -> count

    Returns:
        Formatted string like "2025(18), 2024(23), 2023(6)"
    """
    parts = sorted(year_counts.items(), key=lambda x: x[0], reverse=True)
    return ", ".join(f"{y}({c})" for y, c in parts)


def total_count(year_counts: Dict[str, int]) -> int:
    """
    Sum all year counts.

    Args:
        year_counts: Mapping of year -> count

    Returns:
        Total count across all years
    """
    return sum(year_counts.values())


def print_people_report(data: Dict[str, Dict[str, int]], alphabetical: bool = False) -> None:
    """
    Print formatted people summary report to stdout.

    Args:
        data: Aggregated people data from aggregate_people()
        alphabetical: Sort alphabetically instead of by frequency
    """
    if alphabetical:
        sorted_items: List[Tuple[str, int, Dict[str, int]]] = sorted(
            [(name, total_count(yc), yc) for name, yc in data.items()],
            key=lambda x: x[0].lower(),
        )
        sort_label = "alphabetical"
    else:
        sorted_items = sorted(
            [(name, total_count(yc), yc) for name, yc in data.items()],
            key=lambda x: (-x[1], x[0]),
        )
        sort_label = "frequency"

    print(f"=== People Summary (by {sort_label}) ===")
    print(f"Total unique names: {len(sorted_items)}")
    print()

    if not sorted_items:
        return

    max_name = max(len(item[0]) for item in sorted_items)
    max_name = max(max_name, 4)

    for name, count, year_counts in sorted_items:
        entry_word = "entry " if count == 1 else "entries"
        count_str = f"{count:>3} {entry_word}"
        breakdown = format_year_breakdown(year_counts)
        print(f"{name:<{max_name}} | {count_str} | {breakdown}")


def print_locations_report(
    data: Dict[str, Dict[str, Dict[str, int]]], alphabetical: bool = False
) -> None:
    """
    Print formatted locations summary report to stdout.

    Args:
        data: Aggregated locations data from aggregate_locations()
        alphabetical: Sort alphabetically instead of by frequency
    """
    sort_label = "alphabetical" if alphabetical else "frequency"
    print(f"=== Locations Summary (by {sort_label}) ===")
    print()

    # Sort cities: _unassigned last, rest alphabetical
    cities = sorted(
        data.keys(),
        key=lambda c: (c.startswith("_"), c.lower()),
    )

    for city in cities:
        locations = data[city]
        if alphabetical:
            sorted_items: List[Tuple[str, int, Dict[str, int]]] = sorted(
                [(name, total_count(yc), yc) for name, yc in locations.items()],
                key=lambda x: x[0].lower(),
            )
        else:
            sorted_items = sorted(
                [(name, total_count(yc), yc) for name, yc in locations.items()],
                key=lambda x: (-x[1], x[0]),
            )

        print(f"--- {city} ---")

        if not sorted_items:
            print()
            continue

        max_name = max(len(item[0]) for item in sorted_items)
        max_name = max(max_name, 4)

        for name, count, year_counts in sorted_items:
            entry_word = "entry " if count == 1 else "entries"
            count_str = f"{count:>3} {entry_word}"
            breakdown = format_year_breakdown(year_counts)
            print(f"{name:<{max_name}} | {count_str} | {breakdown}")

        print()


def main() -> None:
    """
    Parse arguments and print the requested summary report.
    """
    parser = argparse.ArgumentParser(
        description="Summarize entity curation files by frequency."
    )
    parser.add_argument(
        "--type",
        choices=["people", "locations"],
        default=None,
        help="Entity type to summarize (default: both)",
    )
    parser.add_argument(
        "--alphabetical",
        action="store_true",
        help="Sort alphabetically instead of by frequency",
    )
    args = parser.parse_args()

    show_people = args.type in (None, "people")
    show_locations = args.type in (None, "locations")

    if show_people:
        print_people_report(aggregate_people(), alphabetical=args.alphabetical)
        if show_locations:
            print()

    if show_locations:
        print_locations_report(aggregate_locations(), alphabetical=args.alphabetical)


if __name__ == "__main__":
    main()
