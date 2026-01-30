#!/usr/bin/env python3
"""
summary.py
----------
Generate frequency-based summary reports of curated entities.

This module aggregates entity counts across all per-year curation files
and provides formatted reports for analysis and review.

Key Features:
    - Aggregates people by raw name across all years
    - Aggregates locations by city and raw name
    - Sorts by frequency or alphabetically
    - Shows per-year breakdowns (e.g., "2025(18), 2024(23)")

Output:
    Text reports to stdout or returned as SummaryData objects.

Usage:
    from dev.curation.summary import aggregate_people, aggregate_locations

    people_data = aggregate_people()
    locations_data = aggregate_locations()
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import CURATION_DIR, LOG_DIR
from dev.curation.models import SummaryData


# =============================================================================
# Utility Functions
# =============================================================================

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


def format_year_breakdown(year_counts: Dict[str, int]) -> str:
    """
    Format per-year counts as a comma-separated string.

    Sorted descending by year.

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


# =============================================================================
# Aggregation Functions
# =============================================================================

def aggregate_people() -> SummaryData:
    """
    Aggregate people counts across all per-year curation files.

    Returns:
        SummaryData with people aggregation
    """
    by_name: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for path in sorted(CURATION_DIR.glob("*_people_curation.yaml")):
        year = extract_year(path)
        data = load_yaml(path)
        for raw_name, info in data.items():
            if not isinstance(info, dict) or "dates" not in info:
                continue
            count = len(info["dates"])
            by_name[raw_name][year] += count

    return SummaryData(
        entity_type="people",
        total_unique=len(by_name),
        by_name=dict(by_name),
    )


def aggregate_locations() -> SummaryData:
    """
    Aggregate location counts across all per-year curation files.

    Returns:
        SummaryData with locations aggregation
    """
    by_city: Dict[str, Dict[str, Dict[str, int]]] = defaultdict(
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
                by_city[city][raw_name][year] += count

    # Calculate total unique locations
    total_unique = sum(len(locs) for locs in by_city.values())

    return SummaryData(
        entity_type="locations",
        total_unique=total_unique,
        by_name={},  # Not used for locations
        by_city=dict(by_city),
    )


# =============================================================================
# Report Formatting
# =============================================================================

def format_people_report(
    data: SummaryData,
    alphabetical: bool = False,
) -> List[str]:
    """
    Format people summary as a list of report lines.

    Args:
        data: SummaryData from aggregate_people()
        alphabetical: Sort alphabetically instead of by frequency

    Returns:
        List of formatted report lines
    """
    lines: List[str] = []

    if alphabetical:
        sorted_items: List[Tuple[str, int, Dict[str, int]]] = sorted(
            [(name, total_count(yc), yc) for name, yc in data.by_name.items()],
            key=lambda x: x[0].lower(),
        )
        sort_label = "alphabetical"
    else:
        sorted_items = sorted(
            [(name, total_count(yc), yc) for name, yc in data.by_name.items()],
            key=lambda x: (-x[1], x[0]),
        )
        sort_label = "frequency"

    lines.append(f"=== People Summary (by {sort_label}) ===")
    lines.append(f"Total unique names: {len(sorted_items)}")
    lines.append("")

    if not sorted_items:
        return lines

    max_name = max(len(item[0]) for item in sorted_items)
    max_name = max(max_name, 4)

    for name, count, year_counts in sorted_items:
        entry_word = "entry " if count == 1 else "entries"
        count_str = f"{count:>3} {entry_word}"
        breakdown = format_year_breakdown(year_counts)
        lines.append(f"{name:<{max_name}} | {count_str} | {breakdown}")

    return lines


def format_locations_report(
    data: SummaryData,
    alphabetical: bool = False,
) -> List[str]:
    """
    Format locations summary as a list of report lines.

    Args:
        data: SummaryData from aggregate_locations()
        alphabetical: Sort alphabetically instead of by frequency

    Returns:
        List of formatted report lines
    """
    lines: List[str] = []
    sort_label = "alphabetical" if alphabetical else "frequency"

    lines.append(f"=== Locations Summary (by {sort_label}) ===")
    lines.append("")

    if not data.by_city:
        return lines

    # Sort cities: _unassigned last, rest alphabetical
    cities = sorted(
        data.by_city.keys(),
        key=lambda c: (c.startswith("_"), c.lower()),
    )

    for city in cities:
        locations = data.by_city[city]
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

        lines.append(f"--- {city} ---")

        if not sorted_items:
            lines.append("")
            continue

        max_name = max(len(item[0]) for item in sorted_items)
        max_name = max(max_name, 4)

        for name, count, year_counts in sorted_items:
            entry_word = "entry " if count == 1 else "entries"
            count_str = f"{count:>3} {entry_word}"
            breakdown = format_year_breakdown(year_counts)
            lines.append(f"{name:<{max_name}} | {count_str} | {breakdown}")

        lines.append("")

    return lines


# =============================================================================
# Main Summary Function
# =============================================================================

def generate_summary(
    entity_type: Optional[str] = None,
    alphabetical: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> Tuple[Optional[SummaryData], Optional[SummaryData], List[str]]:
    """
    Generate summary reports for entities.

    Args:
        entity_type: 'people', 'locations', or None for both
        alphabetical: Sort alphabetically instead of by frequency
        logger: Optional logger for operation tracking

    Returns:
        Tuple of (people_data, locations_data, report_lines)
    """
    if logger is None:
        log_dir = LOG_DIR / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger = PalimpsestLogger(log_dir, component_name="summary")

    people_data: Optional[SummaryData] = None
    locations_data: Optional[SummaryData] = None
    report_lines: List[str] = []

    if entity_type in (None, "people"):
        people_data = aggregate_people()
        report_lines.extend(format_people_report(people_data, alphabetical))
        logger.log_info(people_data.summary())

        if entity_type is None:
            report_lines.append("")

    if entity_type in (None, "locations"):
        locations_data = aggregate_locations()
        report_lines.extend(format_locations_report(locations_data, alphabetical))
        logger.log_info(locations_data.summary())

    return people_data, locations_data, report_lines
