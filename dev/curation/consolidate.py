#!/usr/bin/env python3
"""
consolidate.py
--------------
Consolidate per-year curation files into merged views.

This module merges multiple per-year curation files into single
consolidated files, resolving same_as chains and merging canonical
information.

Key Features:
    - Merges people curation files across years
    - Merges locations curation files across years
    - Resolves same_as chains to final canonicals
    - Merges aliases into lists when combining entries
    - Tracks skipped and self entries separately

Output Format:
    PersonKey:
      raw_names: [list of raw names that map to this person]
      dates:
        2025: [dates]
        2024: [dates]
      canonical:
        name: First name
        lastname: Last name
        alias: Alias or [list]

Usage:
    from dev.curation.consolidate import consolidate_people, consolidate_locations

    result = consolidate_people(["2023", "2024", "2025"])
    print(result.summary())
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger
from dev.core.paths import CURATION_DIR, LOG_DIR
from dev.curation.models import ConsolidationResult


# =============================================================================
# Utility Functions
# =============================================================================

def load_yaml(path: Path) -> Dict[str, Any]:
    """
    Load a YAML file.

    Args:
        path: Path to the YAML file

    Returns:
        Parsed YAML content as a dict
    """
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def is_all_null_canonical(canonical: Any) -> bool:
    """
    Check if a canonical dict has all null values.

    Args:
        canonical: Canonical dict to check

    Returns:
        True if all values are None
    """
    if not isinstance(canonical, dict):
        return False
    return all(v is None for v in canonical.values())


def get_effective_canonical(
    raw_name: str, entry: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """
    Get the effective canonical for an entry, applying conventions.

    Args:
        raw_name: Raw name key
        entry: Entry dict from curation file

    Returns:
        Effective canonical dict, or None if entry should be skipped
    """
    if entry.get("skip") is True:
        return None
    if entry.get("self") is True:
        return None
    if "same_as" in entry:
        return None  # Will be resolved via chain
    if "canonical" not in entry:
        return None  # Skip

    canonical = entry["canonical"]
    if isinstance(canonical, list):
        # Multi-person entry - return as-is
        return {"_multi": canonical}
    if not isinstance(canonical, dict):
        return None

    # All null convention: name = key
    if is_all_null_canonical(canonical):
        return {"name": raw_name, "lastname": None, "alias": None}

    return canonical


def canonical_key(canonical: Dict[str, Any]) -> str:
    """
    Create a unique key for a canonical to identify same person.

    Args:
        canonical: Canonical dict

    Returns:
        Unique key string
    """
    if "_multi" in canonical:
        # Multi-person entry gets unique key
        return f"_multi_{id(canonical)}"

    name = canonical.get("name", "").lower()
    lastname = (canonical.get("lastname") or "").lower()
    disambiguator = (canonical.get("disambiguator") or "").lower()

    if lastname:
        return f"{name}|{lastname}"
    elif disambiguator:
        return f"{name}||{disambiguator}"
    else:
        return f"{name}|"


def merge_canonicals(c1: Dict[str, Any], c2: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge two canonicals, preferring more complete info.

    Args:
        c1: First canonical dict
        c2: Second canonical dict

    Returns:
        Merged canonical dict
    """
    result = dict(c1)

    # Prefer non-null values
    for key in ["name", "lastname", "disambiguator"]:
        if not result.get(key) and c2.get(key):
            result[key] = c2[key]

    # Merge aliases into list
    aliases1 = result.get("alias") or []
    aliases2 = c2.get("alias") or []

    if isinstance(aliases1, str):
        aliases1 = [aliases1]
    if isinstance(aliases2, str):
        aliases2 = [aliases2]

    # Preserve order, remove dupes
    merged_aliases = list(dict.fromkeys(aliases1 + aliases2))
    if merged_aliases:
        result["alias"] = (
            merged_aliases if len(merged_aliases) > 1 else merged_aliases[0]
        )

    return result


# =============================================================================
# People Consolidation
# =============================================================================

def consolidate_people(
    years: List[str],
    logger: Optional[PalimpsestLogger] = None,
) -> Tuple[ConsolidationResult, Dict[str, Any]]:
    """
    Consolidate people curation files for given years.

    Args:
        years: List of years to consolidate
        logger: Optional logger for operation tracking

    Returns:
        Tuple of (ConsolidationResult, output_data dict for YAML)
    """
    if logger is None:
        log_dir = LOG_DIR / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger = PalimpsestLogger(log_dir, component_name="consolidate")

    result = ConsolidationResult(years_processed=list(years))

    # First pass: collect all entries and resolve same_as
    all_entries: Dict[str, Dict[str, Dict[str, Any]]] = {}  # year -> raw_name -> entry

    for year in years:
        path = CURATION_DIR / f"{year}_people_curation.yaml"
        if not path.exists():
            logger.log_warning(f"{path} not found")
            continue

        data = load_yaml(path)
        all_entries[year] = data

    # Build same_as resolution map per year
    def resolve_same_as(
        year: str, raw_name: str, visited: Set[str]
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Resolve same_as chain, return (final_raw_name, entry) or None."""
        if raw_name in visited:
            return None  # Circular
        visited.add(raw_name)

        entry = all_entries.get(year, {}).get(raw_name)
        if not entry:
            return None

        if "same_as" in entry and entry["same_as"]:
            target = entry["same_as"]
            if isinstance(target, str):
                return resolve_same_as(year, target, visited)
            return None  # Invalid same_as (list?)

        return (raw_name, entry)

    # Collect merged people
    merged: Dict[str, Dict[str, Any]] = {}  # canonical_key -> merged data
    skipped: Dict[str, Dict[str, Any]] = {}
    self_entries: Dict[str, Dict[str, Any]] = {}

    for year in years:
        data = all_entries.get(year, {})

        for raw_name, entry in data.items():
            if not isinstance(entry, dict):
                continue

            dates = entry.get("dates", [])

            # Handle skipped
            if entry.get("skip") is True:
                if raw_name not in skipped:
                    skipped[raw_name] = {"dates": {}, "reason": "skip"}
                skipped[raw_name]["dates"][year] = dates
                continue

            # Handle self
            if entry.get("self") is True:
                if raw_name not in self_entries:
                    self_entries[raw_name] = {"dates": {}}
                self_entries[raw_name]["dates"][year] = dates
                continue

            # Handle no canonical
            if "canonical" not in entry and "same_as" not in entry:
                if raw_name not in skipped:
                    skipped[raw_name] = {"dates": {}, "reason": "no_canonical"}
                skipped[raw_name]["dates"][year] = dates
                continue

            # Resolve same_as
            if "same_as" in entry:
                resolved = resolve_same_as(year, raw_name, set())
                if not resolved:
                    if raw_name not in skipped:
                        skipped[raw_name] = {"dates": {}, "reason": "unresolved_same_as"}
                    skipped[raw_name]["dates"][year] = dates
                    continue
                target_name, target_entry = resolved
                canonical = get_effective_canonical(target_name, target_entry)
            else:
                canonical = get_effective_canonical(raw_name, entry)

            if not canonical:
                if raw_name not in skipped:
                    skipped[raw_name] = {"dates": {}, "reason": "no_canonical"}
                skipped[raw_name]["dates"][year] = dates
                continue

            # Get key for this canonical
            ckey = canonical_key(canonical)

            # Merge into existing or create new
            if ckey in merged:
                existing = merged[ckey]
                # Check for conflict
                existing_canonical = existing["canonical"]
                if canonical_key(existing_canonical) != ckey:
                    result.conflicts.append(f"{raw_name}: different canonicals")

                # Merge
                existing["canonical"] = merge_canonicals(existing_canonical, canonical)
                if raw_name not in existing["raw_names"]:
                    existing["raw_names"].append(raw_name)
                if year not in existing["dates"]:
                    existing["dates"][year] = []
                existing["dates"][year].extend(dates)
            else:
                merged[ckey] = {
                    "raw_names": [raw_name],
                    "dates": {year: dates},
                    "canonical": canonical,
                }

    # Update result stats
    result.merged_count = len(merged)
    result.skipped_count = len(skipped)
    result.self_count = len(self_entries)

    # Build output data
    output_data = _format_people_output(merged, skipped, self_entries, result.conflicts)

    return result, output_data


def _format_people_output(
    merged: Dict[str, Dict[str, Any]],
    skipped: Dict[str, Dict[str, Any]],
    self_entries: Dict[str, Dict[str, Any]],
    conflicts: List[str],
) -> Dict[str, Any]:
    """
    Format consolidated people data for YAML output.

    Args:
        merged: Merged people data
        skipped: Skipped entries
        self_entries: Self (author) entries
        conflicts: List of conflicts

    Returns:
        Dict formatted for YAML output
    """
    output: Dict[str, Any] = {}

    # Sort merged by canonical name
    def sort_key(item: Tuple[str, Dict[str, Any]]) -> str:
        canonical = item[1]["canonical"]
        if "_multi" in canonical:
            return "zzz_multi"
        name = canonical.get("name", "")
        lastname = canonical.get("lastname") or ""
        return f"{name} {lastname}".lower()

    sorted_merged = sorted(merged.items(), key=sort_key)

    # Output merged people
    for ckey, data in sorted_merged:
        canonical = data["canonical"]

        # Use canonical name as key
        if "_multi" in canonical:
            key_name = data["raw_names"][0]
        else:
            name = canonical.get("name", "")
            lastname = canonical.get("lastname")
            key_name = f"{name} {lastname}".strip() if lastname else name

        output[key_name] = {
            "raw_names": data["raw_names"],
            "dates": {
                year: sorted(set(dates))
                for year, dates in sorted(data["dates"].items(), reverse=True)
                if dates
            },
            "canonical": canonical,
        }

    # Add skipped section
    if skipped:
        output["_skipped"] = {
            raw_name: {
                "reason": data["reason"],
                "dates": {
                    year: dates
                    for year, dates in sorted(data["dates"].items(), reverse=True)
                    if dates
                },
            }
            for raw_name in sorted(skipped.keys())
            for data in [skipped[raw_name]]
        }

    # Add self section
    if self_entries:
        output["_self"] = {
            raw_name: {
                "dates": {
                    year: dates
                    for year, dates in sorted(data["dates"].items(), reverse=True)
                    if dates
                }
            }
            for raw_name in sorted(self_entries.keys())
            for data in [self_entries[raw_name]]
        }

    return output


# =============================================================================
# Locations Consolidation
# =============================================================================

def consolidate_locations(
    years: List[str],
    logger: Optional[PalimpsestLogger] = None,
) -> Tuple[ConsolidationResult, Dict[str, Any]]:
    """
    Consolidate locations curation files for given years.

    Args:
        years: List of years to consolidate
        logger: Optional logger for operation tracking

    Returns:
        Tuple of (ConsolidationResult, output_data dict for YAML)
    """
    if logger is None:
        log_dir = LOG_DIR / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger = PalimpsestLogger(log_dir, component_name="consolidate")

    result = ConsolidationResult(years_processed=list(years))

    # Collect all entries: city -> raw_name -> {canonical, dates: {year: [dates]}}
    merged: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
    skipped: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)

    for year in years:
        path = CURATION_DIR / f"{year}_locations_curation.yaml"
        if not path.exists():
            logger.log_warning(f"{path} not found")
            continue

        data = load_yaml(path)

        for city, locations in data.items():
            if not isinstance(locations, dict):
                continue

            # Build same_as resolution for this city/year
            same_as_map: Dict[str, str] = {}
            for raw_name, entry in locations.items():
                if isinstance(entry, dict) and "same_as" in entry:
                    same_as_map[raw_name] = entry["same_as"]

            def resolve_loc_same_as(name: str, visited: Set[str]) -> Optional[str]:
                if name in visited:
                    return None
                visited.add(name)
                if name in same_as_map:
                    return resolve_loc_same_as(same_as_map[name], visited)
                entry = locations.get(name)
                if entry and isinstance(entry, dict) and "canonical" in entry:
                    canonical = entry["canonical"]
                    return name if canonical is None else str(canonical)
                return None

            for raw_name, entry in locations.items():
                if not isinstance(entry, dict):
                    continue

                dates = entry.get("dates", [])

                # Handle skipped
                if entry.get("skip") is True:
                    if raw_name not in skipped[city]:
                        skipped[city][raw_name] = {"dates": {}}
                    skipped[city][raw_name]["dates"][year] = dates
                    continue

                # Handle no canonical
                if "canonical" not in entry and "same_as" not in entry:
                    if raw_name not in skipped[city]:
                        skipped[city][raw_name] = {"dates": {}}
                    skipped[city][raw_name]["dates"][year] = dates
                    continue

                # Resolve canonical
                if "same_as" in entry:
                    canonical = resolve_loc_same_as(raw_name, set())
                    if not canonical:
                        if raw_name not in skipped[city]:
                            skipped[city][raw_name] = {"dates": {}}
                        skipped[city][raw_name]["dates"][year] = dates
                        continue
                else:
                    canonical = entry["canonical"]
                    if canonical is None:
                        canonical = raw_name
                    else:
                        canonical = str(canonical)

                # Merge
                if canonical not in merged[city]:
                    merged[city][canonical] = {
                        "raw_names": [],
                        "dates": {},
                        "canonical": canonical,
                    }

                if raw_name not in merged[city][canonical]["raw_names"]:
                    merged[city][canonical]["raw_names"].append(raw_name)

                if year not in merged[city][canonical]["dates"]:
                    merged[city][canonical]["dates"][year] = []
                merged[city][canonical]["dates"][year].extend(dates)

    # Update result stats
    result.merged_count = sum(len(locs) for locs in merged.values())
    result.skipped_count = sum(len(locs) for locs in skipped.values())

    # Build output data
    output_data = _format_locations_output(dict(merged), dict(skipped))

    return result, output_data


def _format_locations_output(
    merged: Dict[str, Dict[str, Dict[str, Any]]],
    skipped: Dict[str, Dict[str, Dict[str, Any]]],
) -> Dict[str, Any]:
    """
    Format consolidated locations data for YAML output.

    Args:
        merged: Merged locations data by city
        skipped: Skipped entries by city

    Returns:
        Dict formatted for YAML output
    """
    output: Dict[str, Any] = {}

    # Sort cities (_unassigned last)
    cities = sorted(
        merged.keys(),
        key=lambda c: (c.startswith("_"), c.lower()),
    )

    for city in cities:
        city_output: Dict[str, Any] = {}
        for canonical in sorted(merged[city].keys()):
            data = merged[city][canonical]
            city_output[canonical] = {
                "raw_names": data["raw_names"],
                "dates": {
                    year: sorted(set(dates))
                    for year, dates in sorted(data["dates"].items(), reverse=True)
                    if dates
                },
            }
        output[city] = city_output

    # Add skipped section
    if skipped:
        skipped_output: Dict[str, Any] = {}
        for city in sorted(skipped.keys()):
            if skipped[city]:
                skipped_output[city] = {
                    raw_name: {
                        "dates": {
                            year: dates
                            for year, dates in sorted(
                                data["dates"].items(), reverse=True
                            )
                            if dates
                        }
                    }
                    for raw_name, data in sorted(skipped[city].items())
                }
        if skipped_output:
            output["_skipped"] = skipped_output

    return output


# =============================================================================
# Main Consolidation Function
# =============================================================================

def consolidate_and_write(
    years: List[str],
    entity_type: str,
    output_path: Optional[Path] = None,
    logger: Optional[PalimpsestLogger] = None,
) -> ConsolidationResult:
    """
    Consolidate curation files and write to output.

    Args:
        years: List of years to consolidate
        entity_type: 'people' or 'locations'
        output_path: Optional output path (default: CURATION_DIR)
        logger: Optional logger for operation tracking

    Returns:
        ConsolidationResult with outcomes

    Raises:
        ValueError: If entity_type is invalid
    """
    if logger is None:
        log_dir = LOG_DIR / "operations"
        log_dir.mkdir(parents=True, exist_ok=True)
        logger = PalimpsestLogger(log_dir, component_name="consolidate")

    if entity_type == "people":
        result, output_data = consolidate_people(years, logger)
        default_filename = f"{'-'.join(years)}_people_curation.yaml"
        header = """# Consolidated People Curation File
# Generated from per-year files
#
# Format:
#   PersonKey:
#     raw_names: [list of raw names that map to this person]
#     dates:
#       2025: [dates]
#       2024: [dates]
#     canonical:
#       name: First name
#       lastname: Last name (optional)
#       alias: Alias or [list of aliases]
#       disambiguator: Context (optional)
#
# _skipped: entries to ignore
# _self: author references
"""
    elif entity_type == "locations":
        result, output_data = consolidate_locations(years, logger)
        default_filename = f"{'-'.join(years)}_locations_curation.yaml"
        header = """# Consolidated Locations Curation File
# Generated from per-year files
#
# Format:
#   CityName:
#     CanonicalLocation:
#       raw_names: [list of raw names that map here]
#       dates:
#         2025: [dates]
#         2024: [dates]
#
# _skipped: entries to ignore
"""
    else:
        raise ValueError(f"Invalid entity_type: {entity_type}")

    # Determine output path
    if output_path is None:
        output_path = CURATION_DIR / default_filename

    result.output_path = str(output_path)

    # Write output
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n")
        yaml.dump(
            output_data,
            f,
            default_flow_style=None,
            allow_unicode=True,
            sort_keys=False,
            width=100,
        )

    logger.log_info(f"Written to: {output_path}")
    logger.log_info(result.summary())

    return result
