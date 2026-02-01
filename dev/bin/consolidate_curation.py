#!/usr/bin/env python3
"""
consolidate_curation.py
-----------------------
Consolidate per-year curation files into single merged files with validation.

Handles both people and locations curation files, merging entries across years,
resolving same_as references, and detecting conflicts.

Validation checks:
    - Circular same_as references
    - Dangling same_as references
    - Parenthetical keys without disambiguation (people only)
    - Same first-name-only across years without differentiation (people only)

Usage:
    python -m dev.bin.consolidate_curation --type people --years 2021-2025
    python -m dev.bin.consolidate_curation --type locations --years 2023-2025
    python -m dev.bin.consolidate_curation --type people --years 2021-2025 --validate-only
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import CURATION_DIR


@dataclass
class ValidationResult:
    """Results from curation validation."""

    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    ambiguous: List[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0

    def print_report(self) -> None:
        """Print validation report to stdout."""
        if self.errors:
            print("\n=== ERRORS (must fix) ===")
            for e in self.errors:
                print(f"  {e}")

        if self.warnings:
            print("\n=== WARNINGS ===")
            for w in self.warnings:
                print(f"  {w}")

        if self.ambiguous:
            print("\n=== AMBIGUOUS (review needed) ===")
            for a in self.ambiguous:
                print(f"  {a}")

        if self.is_valid and not self.warnings and not self.ambiguous:
            print("\n✓ Validation passed")
        elif self.is_valid:
            print(f"\n✓ Validation passed with {len(self.warnings)} warnings, "
                  f"{len(self.ambiguous)} ambiguous entries")
        else:
            print(f"\n✗ Validation failed: {len(self.errors)} errors")


def load_yaml(path: Path) -> Dict[str, Any]:
    """Load a YAML file."""
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def extract_base_name(raw_name: str) -> str:
    """Extract base name from a parenthetical key like 'Vlad (Work)' -> 'Vlad'."""
    match = re.match(r"^([^(]+?)(?:\s*\([^)]+\))?$", raw_name)
    return match.group(1).strip() if match else raw_name


def has_parenthetical(raw_name: str) -> bool:
    """Check if raw name has parenthetical disambiguation like 'Vlad (Work)'."""
    return bool(re.search(r"\([^)]+\)$", raw_name.strip()))


def validate_people_curation(
    all_entries: Dict[str, Dict[str, Dict[str, Any]]]
) -> ValidationResult:
    """
    Validate people curation data across years.

    Checks:
        1. Circular same_as references
        2. Dangling same_as references
        3. Parenthetical keys without lastname or disambiguator
        4. Same first-name-only across years without differentiation

    Args:
        all_entries: Dict of year -> raw_name -> entry

    Returns:
        ValidationResult with errors, warnings, and ambiguous entries
    """
    result = ValidationResult()

    # Track entries by base name for cross-year comparison
    # base_name -> [(year, raw_name, canonical)]
    by_base_name: Dict[str, List[Tuple[str, str, Optional[Dict[str, Any]]]]] = {}

    for year, entries in all_entries.items():
        for raw_name, entry in entries.items():
            if not isinstance(entry, dict):
                continue

            # Skip entries that are explicitly skipped or self
            if entry.get("skip") is True or entry.get("self") is True:
                continue

            # Check same_as references
            if "same_as" in entry:
                target = entry["same_as"]
                if isinstance(target, str):
                    # Check for dangling
                    if target not in entries:
                        result.errors.append(
                            f"[{year}] Dangling same_as: '{raw_name}' -> '{target}' (not found)"
                        )
                    # Check for circular (simple case)
                    elif entries.get(target, {}).get("same_as") == raw_name:
                        result.errors.append(
                            f"[{year}] Circular same_as: '{raw_name}' <-> '{target}'"
                        )
                continue  # same_as entries don't have their own canonical

            # Skip entries without canonical (implicit skip)
            if "canonical" not in entry:
                continue

            canonical = entry["canonical"]
            if isinstance(canonical, list):
                # Multi-person entry, skip validation
                continue
            if not isinstance(canonical, dict):
                continue

            # Check parenthetical keys
            if has_parenthetical(raw_name):
                has_lastname = bool(canonical.get("lastname"))
                has_disambig = bool(canonical.get("disambiguator"))
                if not has_lastname and not has_disambig:
                    result.errors.append(
                        f"[{year}] Parenthetical key without disambiguation: "
                        f"'{raw_name}' needs lastname or disambiguator field"
                    )

            # Track for cross-year comparison
            base = extract_base_name(raw_name)
            if base not in by_base_name:
                by_base_name[base] = []
            by_base_name[base].append((year, raw_name, canonical))

    # Cross-year validation for first-name-only entries
    for base_name, occurrences in by_base_name.items():
        # Get unique years
        years_seen = set(year for year, _, _ in occurrences)
        if len(years_seen) < 2:
            continue  # Only appears in one year, no cross-year issue

        # Group by canonical key to see if they're the same person
        canonical_groups: Dict[str, List[Tuple[str, str]]] = {}
        # Also track disambiguation status per entry
        disambiguated_entries: List[Tuple[str, str, str]] = []  # (year, raw_name, ckey)
        undisambiguated_entries: List[Tuple[str, str, str]] = []  # (year, raw_name, ckey)

        for year, raw_name, canonical in occurrences:
            if canonical is None:
                continue
            # Check if first-name-only (no lastname, no disambiguator)
            has_lastname = bool(canonical.get("lastname"))
            has_disambig = bool(canonical.get("disambiguator"))
            ckey = canonical_key(canonical)

            if has_lastname or has_disambig:
                disambiguated_entries.append((year, raw_name, ckey))
            else:
                undisambiguated_entries.append((year, raw_name, ckey))
                # First-name-only across multiple years
                if ckey not in canonical_groups:
                    canonical_groups[ckey] = []
                canonical_groups[ckey].append((year, raw_name))

        # Flag ambiguous entries (first-name-only in multiple years)
        for ckey, entries_list in canonical_groups.items():
            entry_years = set(year for year, _ in entries_list)
            if len(entry_years) > 1:
                years_str = ", ".join(sorted(entry_years))
                entries_str = "; ".join(f"{y}: {n}" for y, n in sorted(entries_list))
                result.ambiguous.append(
                    f"'{base_name}' appears in multiple years without disambiguation: "
                    f"[{years_str}] - Same person? If not, add disambiguator. ({entries_str})"
                )

        # Flag inconsistent disambiguation across years
        # (some years have it, some don't - likely same person with inconsistent curation)
        if disambiguated_entries and undisambiguated_entries:
            disamb_years = set(year for year, _, _ in disambiguated_entries)
            undis_years = set(year for year, _, _ in undisambiguated_entries)
            disamb_str = "; ".join(f"{y}: {n}" for y, n, _ in sorted(disambiguated_entries))
            undis_str = "; ".join(f"{y}: {n}" for y, n, _ in sorted(undisambiguated_entries))
            result.warnings.append(
                f"'{base_name}' has inconsistent disambiguation across years: "
                f"WITH disambig [{', '.join(sorted(disamb_years))}]: {disamb_str} | "
                f"WITHOUT [{', '.join(sorted(undis_years))}]: {undis_str}"
            )

    return result


def validate_locations_curation(
    all_entries: Dict[str, Dict[str, Dict[str, Any]]]
) -> ValidationResult:
    """
    Validate locations curation data across years.

    Checks:
        1. Circular same_as references
        2. Dangling same_as references

    Args:
        all_entries: Dict of year -> city -> raw_name -> entry

    Returns:
        ValidationResult with errors and warnings
    """
    result = ValidationResult()

    for year, cities in all_entries.items():
        for city, locations in cities.items():
            if not isinstance(locations, dict):
                continue

            for raw_name, entry in locations.items():
                if not isinstance(entry, dict):
                    continue

                if entry.get("skip") is True:
                    continue

                # Check same_as references
                if "same_as" in entry:
                    target = entry["same_as"]
                    if isinstance(target, str):
                        # Check for dangling
                        if target not in locations:
                            result.errors.append(
                                f"[{year}:{city}] Dangling same_as: "
                                f"'{raw_name}' -> '{target}' (not found)"
                            )
                        # Check for circular
                        elif locations.get(target, {}).get("same_as") == raw_name:
                            result.errors.append(
                                f"[{year}:{city}] Circular same_as: "
                                f"'{raw_name}' <-> '{target}'"
                            )

    return result


def is_all_null_canonical(canonical: Any) -> bool:
    """Check if a canonical dict has all null values."""
    if not isinstance(canonical, dict):
        return False
    return all(v is None for v in canonical.values())


def get_effective_canonical(raw_name: str, entry: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Get the effective canonical for an entry, applying conventions.

    Returns None if entry should be skipped.
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
    """Create a unique key for a canonical to identify same person."""
    if "_multi" in canonical:
        # Multi-person entry gets unique key
        return f"_multi_{id(canonical)}"

    name = (canonical.get("name") or "").lower()
    lastname = (canonical.get("lastname") or "").lower()
    disambiguator = (canonical.get("disambiguator") or "").lower()

    if lastname:
        return f"{name}|{lastname}"
    elif disambiguator:
        return f"{name}||{disambiguator}"
    else:
        return f"{name}|"


def merge_canonicals(c1: Dict[str, Any], c2: Dict[str, Any]) -> Dict[str, Any]:
    """Merge two canonicals, preferring more complete info."""
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

    merged_aliases = list(dict.fromkeys(aliases1 + aliases2))  # Preserve order, remove dupes
    if merged_aliases:
        result["alias"] = merged_aliases if len(merged_aliases) > 1 else merged_aliases[0]

    return result


def consolidate_people(years: List[str]) -> Tuple[
    Dict[str, Dict[str, Any]],  # merged people
    Dict[str, Dict[str, Any]],  # skipped
    Dict[str, Dict[str, Any]],  # self
    List[str],                   # conflicts
]:
    """
    Consolidate people curation files for given years.

    Returns:
        Tuple of (merged_people, skipped, self_entries, conflicts)
    """
    # First pass: collect all entries and resolve same_as
    all_entries: Dict[str, Dict[str, Dict[str, Any]]] = {}  # year -> raw_name -> entry

    for year in years:
        path = CURATION_DIR / f"{year}_people_curation.yaml"
        if not path.exists():
            print(f"Warning: {path} not found")
            continue

        data = load_yaml(path)
        all_entries[year] = data

    # Build same_as resolution map per year
    def resolve_same_as(year: str, raw_name: str, visited: Set[str]) -> Optional[Tuple[str, Dict[str, Any]]]:
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
    conflicts: List[str] = []

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
                    conflicts.append(f"{raw_name}: different canonicals")

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

    return merged, skipped, self_entries, conflicts


def consolidate_locations(years: List[str]) -> Tuple[
    Dict[str, Dict[str, Dict[str, Any]]],  # merged: city -> location -> data
    Dict[str, Dict[str, Dict[str, Any]]],  # skipped: city -> location -> data
    List[str],                              # conflicts
]:
    """
    Consolidate locations curation files for given years.

    Returns:
        Tuple of (merged_locations, skipped, conflicts)
    """
    # Collect all entries: year -> city -> raw_name -> entry
    all_entries: Dict[str, Dict[str, Dict[str, Any]]] = {}

    for year in years:
        path = CURATION_DIR / f"{year}_locations_curation.yaml"
        if not path.exists():
            print(f"Warning: {path} not found")
            continue

        data = load_yaml(path)
        all_entries[year] = data

    def resolve_same_as(
        year: str, city: str, raw_name: str, visited: Set[str]
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """Resolve same_as chain within a city, return (final_name, entry) or None."""
        key = f"{city}:{raw_name}"
        if key in visited:
            return None  # Circular
        visited.add(key)

        entry = all_entries.get(year, {}).get(city, {}).get(raw_name)
        if not entry:
            return None

        if "same_as" in entry and entry["same_as"]:
            target = entry["same_as"]
            if isinstance(target, str):
                return resolve_same_as(year, city, target, visited)
            return None

        return (raw_name, entry)

    # Collect merged locations: city -> canonical_name -> data
    merged: Dict[str, Dict[str, Dict[str, Any]]] = {}
    skipped: Dict[str, Dict[str, Dict[str, Any]]] = {}
    conflicts: List[str] = []

    for year in years:
        data = all_entries.get(year, {})

        for city, locations in data.items():
            if not isinstance(locations, dict):
                continue

            if city not in merged:
                merged[city] = {}
            if city not in skipped:
                skipped[city] = {}

            for raw_name, entry in locations.items():
                if not isinstance(entry, dict):
                    continue

                dates = entry.get("dates", [])

                # Handle skipped
                if entry.get("skip") is True:
                    if raw_name not in skipped[city]:
                        skipped[city][raw_name] = {"dates": {}, "reason": "skip"}
                    skipped[city][raw_name]["dates"][year] = dates
                    continue

                # Handle same_as
                if "same_as" in entry:
                    resolved = resolve_same_as(year, city, raw_name, set())
                    if not resolved:
                        if raw_name not in skipped[city]:
                            skipped[city][raw_name] = {"dates": {}, "reason": "unresolved_same_as"}
                        skipped[city][raw_name]["dates"][year] = dates
                        continue
                    target_name, target_entry = resolved
                    canonical = target_entry.get("canonical")
                    if canonical is None:
                        canonical = target_name
                else:
                    canonical = entry.get("canonical")
                    if canonical is None:
                        canonical = raw_name

                # Merge into existing or create new
                if canonical in merged[city]:
                    existing = merged[city][canonical]
                    if raw_name not in existing["raw_names"]:
                        existing["raw_names"].append(raw_name)
                    if year not in existing["dates"]:
                        existing["dates"][year] = []
                    existing["dates"][year].extend(dates)
                else:
                    merged[city][canonical] = {
                        "raw_names": [raw_name],
                        "dates": {year: dates},
                        "canonical": canonical,
                    }

    # Clean up empty cities in skipped
    skipped = {city: locs for city, locs in skipped.items() if locs}

    return merged, skipped, conflicts


def format_output(
    merged: Dict[str, Dict[str, Any]],
    skipped: Dict[str, Dict[str, Any]],
    self_entries: Dict[str, Dict[str, Any]],
    conflicts: List[str],
) -> str:
    """Format the consolidated data as YAML string."""
    lines = [
        "# Consolidated People Curation File",
        "# Generated from per-year files",
        "#",
        "# Format:",
        "#   PersonKey:",
        "#     raw_names: [list of raw names that map to this person]",
        "#     dates:",
        "#       2025: [dates]",
        "#       2024: [dates]",
        "#     canonical:",
        "#       name: First name",
        "#       lastname: Last name (optional)",
        "#       alias: Alias or [list of aliases]",
        "#       disambiguator: Context (optional)",
        "#",
        "# _skipped: entries to ignore",
        "# _self: author references",
        "",
    ]

    if conflicts:
        lines.append("# CONFLICTS (review these):")
        for c in conflicts:
            lines.append(f"#   - {c}")
        lines.append("")

    # Sort merged by canonical name
    def sort_key(item):
        canonical = item[1]["canonical"]
        if "_multi" in canonical:
            return "zzz_multi"
        name = canonical.get("name", "")
        lastname = canonical.get("lastname") or ""
        return f"{name} {lastname}".lower()

    sorted_merged = sorted(merged.items(), key=sort_key)

    # Output merged people
    # Track used keys to detect duplicates
    used_keys: Dict[str, int] = {}

    for _, data in sorted_merged:
        canonical = data["canonical"]

        # Use canonical name as key, including disambiguator to avoid duplicates
        if "_multi" in canonical:
            key_name = data["raw_names"][0]
        else:
            name = canonical.get("name", "")
            lastname = canonical.get("lastname")
            disambiguator = canonical.get("disambiguator")

            if lastname:
                key_name = f"{name} {lastname}"
            elif disambiguator:
                key_name = f"{name} ({disambiguator})"
            else:
                key_name = name

        # Handle remaining duplicates by appending a number
        if key_name in used_keys:
            used_keys[key_name] += 1
            key_name = f"{key_name} #{used_keys[key_name]}"
        else:
            used_keys[key_name] = 1

        lines.append(f"{key_name}:")

        # Raw names
        raw_names = data["raw_names"]
        if len(raw_names) == 1:
            lines.append(f"  raw_names: [{raw_names[0]}]")
        else:
            lines.append(f"  raw_names: {raw_names}")

        # Dates by year
        lines.append("  dates:")
        for year in sorted(data["dates"].keys(), reverse=True):
            dates = sorted(set(data["dates"][year]))
            if dates:
                lines.append(f"    {year}: {dates}")

        # Canonical
        lines.append("  canonical:")
        if "_multi" in canonical:
            lines.append("    _multi_person: true")
            lines.append("    entries:")
            for c in canonical["_multi"]:
                lines.append(f"      - {c}")
        else:
            for field in ["name", "lastname", "alias", "disambiguator"]:
                val = canonical.get(field)
                if val is not None:
                    if isinstance(val, list):
                        lines.append(f"    {field}: {val}")
                    else:
                        lines.append(f"    {field}: {val}")
                elif field in ["name"]:
                    lines.append(f"    {field}: null")

        lines.append("")

    # Output skipped
    if skipped:
        lines.append("")
        lines.append("# ============================================================")
        lines.append("# SKIPPED ENTRIES")
        lines.append("# ============================================================")
        lines.append("")
        lines.append("_skipped:")

        for raw_name in sorted(skipped.keys()):
            data = skipped[raw_name]
            lines.append(f"  {raw_name}:")
            lines.append(f"    reason: {data['reason']}")
            lines.append("    dates:")
            for year in sorted(data["dates"].keys(), reverse=True):
                dates = data["dates"][year]
                if dates:
                    lines.append(f"      {year}: {dates}")
        lines.append("")

    # Output self
    if self_entries:
        lines.append("")
        lines.append("# ============================================================")
        lines.append("# SELF (AUTHOR) REFERENCES")
        lines.append("# ============================================================")
        lines.append("")
        lines.append("_self:")

        for raw_name in sorted(self_entries.keys()):
            data = self_entries[raw_name]
            lines.append(f"  {raw_name}:")
            lines.append("    dates:")
            for year in sorted(data["dates"].keys(), reverse=True):
                dates = data["dates"][year]
                if dates:
                    lines.append(f"      {year}: {dates}")
        lines.append("")

    return "\n".join(lines)


def format_locations_output(
    merged: Dict[str, Dict[str, Dict[str, Any]]],
    skipped: Dict[str, Dict[str, Dict[str, Any]]],
    conflicts: List[str],
) -> str:
    """Format consolidated locations data as YAML string."""
    lines = [
        "# Consolidated Locations Curation File",
        "# Generated from per-year files",
        "#",
        "# Format:",
        "#   CityName:",
        "#     CanonicalLocationName:",
        "#       raw_names: [list of raw names that map to this location]",
        "#       dates:",
        "#         2025: [dates]",
        "#         2024: [dates]",
        "#",
        "# _skipped: entries to ignore (nested under city)",
        "",
    ]

    if conflicts:
        lines.append("# CONFLICTS (review these):")
        for c in conflicts:
            lines.append(f"#   - {c}")
        lines.append("")

    # Sort cities, with _unassigned last
    city_order = sorted(c for c in merged.keys() if not c.startswith("_"))
    unassigned = [c for c in merged.keys() if c.startswith("_")]
    city_order.extend(sorted(unassigned))

    # Output merged locations by city
    for city in city_order:
        locations = merged[city]
        if not locations:
            continue

        lines.append(f"{city}:")

        for canonical in sorted(locations.keys()):
            data = locations[canonical]
            lines.append(f"  {canonical}:")

            # Raw names (only if different from canonical or multiple)
            raw_names = data["raw_names"]
            if len(raw_names) > 1 or (len(raw_names) == 1 and raw_names[0] != canonical):
                if len(raw_names) == 1:
                    lines.append(f"    raw_names: [{raw_names[0]}]")
                else:
                    lines.append(f"    raw_names: {raw_names}")

            # Dates by year
            lines.append("    dates:")
            for year in sorted(data["dates"].keys(), reverse=True):
                dates = sorted(set(data["dates"][year]))
                if dates:
                    lines.append(f"      {year}: {dates}")

        lines.append("")

    # Output skipped
    if skipped:
        lines.append("")
        lines.append("# ============================================================")
        lines.append("# SKIPPED ENTRIES")
        lines.append("# ============================================================")
        lines.append("")
        lines.append("_skipped:")

        for city in sorted(skipped.keys()):
            city_skipped = skipped[city]
            if not city_skipped:
                continue

            lines.append(f"  {city}:")
            for raw_name in sorted(city_skipped.keys()):
                data = city_skipped[raw_name]
                lines.append(f"    {raw_name}:")
                lines.append(f"      reason: {data['reason']}")
                lines.append("      dates:")
                for year in sorted(data["dates"].keys(), reverse=True):
                    dates = data["dates"][year]
                    if dates:
                        lines.append(f"        {year}: {dates}")
        lines.append("")

    return "\n".join(lines)


def parse_year_range(year_spec: str) -> List[str]:
    """Parse year specification like '2021-2025' into list of years."""
    if "-" in year_spec and len(year_spec) == 9:  # YYYY-YYYY format
        start, end = year_spec.split("-")
        return [str(y) for y in range(int(start), int(end) + 1)]
    return [year_spec]


def load_all_people_entries(years: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Load all people curation entries for given years."""
    all_entries: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for year in years:
        path = CURATION_DIR / f"{year}_people_curation.yaml"
        if path.exists():
            all_entries[year] = load_yaml(path)
        else:
            print(f"Warning: {path} not found")
    return all_entries


def load_all_locations_entries(years: List[str]) -> Dict[str, Dict[str, Dict[str, Any]]]:
    """Load all locations curation entries for given years."""
    all_entries: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for year in years:
        path = CURATION_DIR / f"{year}_locations_curation.yaml"
        if path.exists():
            all_entries[year] = load_yaml(path)
        else:
            print(f"Warning: {path} not found")
    return all_entries


def main():
    parser = argparse.ArgumentParser(
        description="Consolidate per-year curation files (people or locations)"
    )
    parser.add_argument(
        "--type",
        choices=["people", "locations"],
        required=True,
        help="Type of curation to consolidate"
    )
    parser.add_argument(
        "--years",
        nargs="+",
        required=True,
        help="Years to consolidate (e.g., 2023 2024 2025 or 2021-2025)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file path (default: CURATION_DIR/consolidated_{type}.yaml)"
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate, don't generate consolidated file"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Generate consolidated file even if validation fails"
    )
    args = parser.parse_args()

    # Expand year ranges
    years = []
    for spec in args.years:
        years.extend(parse_year_range(spec))

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = CURATION_DIR / f"consolidated_{args.type}.yaml"

    print(f"Validating {args.type} curation for years: {', '.join(years)}")

    # Load and validate
    if args.type == "people":
        all_entries = load_all_people_entries(years)
        validation = validate_people_curation(all_entries)
    else:
        all_entries = load_all_locations_entries(years)
        validation = validate_locations_curation(all_entries)

    validation.print_report()

    if args.validate_only:
        return

    if not validation.is_valid and not args.force:
        print("\n✗ Cannot consolidate: fix errors first (or use --force)")
        return

    print(f"\nConsolidating {args.type}...")

    if args.type == "people":
        merged, skipped, self_entries, conflicts = consolidate_people(years)

        print(f"Merged people: {len(merged)}")
        print(f"Skipped entries: {len(skipped)}")
        print(f"Self entries: {len(self_entries)}")
        if conflicts:
            print(f"Conflicts: {len(conflicts)}")
            for c in conflicts:
                print(f"  - {c}")

        output = format_output(merged, skipped, self_entries, conflicts)

    else:  # locations
        merged, skipped, conflicts = consolidate_locations(years)

        total_locations = sum(len(locs) for locs in merged.values())
        total_skipped = sum(len(locs) for locs in skipped.values())

        print(f"Cities: {len(merged)}")
        print(f"Merged locations: {total_locations}")
        print(f"Skipped entries: {total_skipped}")
        if conflicts:
            print(f"Conflicts: {len(conflicts)}")
            for c in conflicts:
                print(f"  - {c}")

        output = format_locations_output(merged, skipped, conflicts)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\nWritten to: {output_path}")


if __name__ == "__main__":
    main()
