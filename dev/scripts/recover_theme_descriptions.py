#!/usr/bin/env python3
"""
recover_theme_descriptions.py
-----------------------------
Recover theme descriptions from narrative_analysis YAML files.

Converts metadata themes from flat name lists to {name, description} dicts
by matching against narrative_analysis data. Also restores recurring themes
(2+ NA entries) that were dropped during curation.

Logic per entry:
    - Themes present in both metadata and NA → keep with NA description
    - Themes only in metadata (no NA match) → delete (no description available)
    - Themes only in NA with 2+ total NA occurrences → restore with description

Usage:
    # Dry run (report only, no file changes)
    python -m dev.scripts.recover_theme_descriptions --dry-run

    # Apply changes
    python -m dev.scripts.recover_theme_descriptions

    # Verbose output
    python -m dev.scripts.recover_theme_descriptions --verbose

Dependencies:
    - PyYAML
    - ruamel.yaml (for format-preserving writes)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# --- Third-party imports ---
import yaml
from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.scalarstring import FoldedScalarString

# --- Local imports ---
from dev.core.paths import DATA_DIR, JOURNAL_YAML_DIR


# =============================================================================
# Constants
# =============================================================================

MIN_RECURRENCE = 2  # Minimum NA entries for a dropped theme to be restored


# =============================================================================
# Data Loading
# =============================================================================


def load_na_themes(na_file: Path) -> Dict[str, str]:
    """
    Load themes from a narrative_analysis YAML file.

    Args:
        na_file: Path to the NA analysis YAML file

    Returns:
        Dict mapping theme name to description
    """
    try:
        with open(na_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return {}

    if not data or not isinstance(data, dict):
        return {}

    themes = data.get("themes", [])
    if not themes or not isinstance(themes, list):
        return {}

    result: Dict[str, str] = {}
    for item in themes:
        if isinstance(item, dict):
            name = item.get("name", "")
            desc = item.get("description", "")
            if name and desc:
                result[name] = desc
    return result


def load_metadata_themes(meta_file: Path) -> List[str]:
    """
    Load themes from a metadata YAML file (current flat string format).

    Args:
        meta_file: Path to the metadata YAML file

    Returns:
        List of theme name strings
    """
    try:
        with open(meta_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception:
        return []

    if not data or not isinstance(data, dict):
        return []

    themes = data.get("themes", [])
    if not themes or not isinstance(themes, list):
        return []

    return [str(t) for t in themes if isinstance(t, str)]


# =============================================================================
# Theme Analysis
# =============================================================================


def compute_recurring_dropped(
    na_dir: Path, meta_dir: Path
) -> Tuple[Set[str], Counter]:
    """
    Identify recurring NA themes that were dropped from metadata.

    Scans all NA files, counts theme occurrences, then checks which themes
    with 2+ NA appearances have zero metadata appearances.

    Args:
        na_dir: Path to narrative_analysis directory
        meta_dir: Path to metadata/journal directory

    Returns:
        Tuple of (set of recurring dropped theme names,
                  Counter mapping theme name to occurrence count)
    """
    # Count NA theme occurrences across all entries
    na_theme_counts: Counter = Counter()
    na_theme_entries: Dict[str, List[str]] = defaultdict(list)

    for year_dir in sorted(na_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for na_file in sorted(year_dir.glob("*_analysis.yaml")):
            date_str = na_file.stem.replace("_analysis", "")
            na_themes = load_na_themes(na_file)
            for name in na_themes:
                na_theme_counts[name] += 1
                na_theme_entries[name].append(date_str)

    # Count metadata theme occurrences
    meta_theme_names: Set[str] = set()
    for year_dir in sorted(meta_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        for meta_file in sorted(year_dir.glob("*.yaml")):
            for name in load_metadata_themes(meta_file):
                meta_theme_names.add(name)

    # Find recurring dropped: 2+ NA entries, 0 metadata entries
    recurring_dropped: Set[str] = set()
    for name, count in na_theme_counts.items():
        if count >= MIN_RECURRENCE and name not in meta_theme_names:
            recurring_dropped.add(name)

    return recurring_dropped, na_theme_counts


# =============================================================================
# Recovery Logic
# =============================================================================


def recover_entry_themes(
    meta_file: Path,
    na_file: Optional[Path],
    recurring_dropped: Set[str],
    verbose: bool = False,
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """
    Compute recovered themes for a single entry.

    Matches metadata themes against NA themes, drops unmatched metadata
    themes, and restores recurring dropped NA themes.

    Args:
        meta_file: Path to the metadata YAML file
        na_file: Path to the NA analysis YAML file (None if not available)
        recurring_dropped: Set of theme names eligible for restoration
        verbose: If True, print detailed per-entry changes

    Returns:
        Tuple of (new themes list as dicts, stats dict with counts)
    """
    meta_themes = load_metadata_themes(meta_file)
    na_themes = load_na_themes(na_file) if na_file else {}

    stats: Dict[str, int] = {
        "matched": 0,
        "deleted": 0,
        "restored": 0,
    }

    new_themes: List[Dict[str, str]] = []

    # Process metadata themes
    for name in meta_themes:
        if name in na_themes:
            new_themes.append({"name": name, "description": na_themes[name]})
            stats["matched"] += 1
            if verbose:
                print(f"  MATCH: {name}")
        else:
            stats["deleted"] += 1
            if verbose:
                print(f"  DELETE: {name} (no NA description)")

    # Restore recurring dropped themes from NA
    meta_set = set(meta_themes)
    for name, desc in na_themes.items():
        if name not in meta_set and name in recurring_dropped:
            new_themes.append({"name": name, "description": desc})
            stats["restored"] += 1
            if verbose:
                print(f"  RESTORE: {name}")

    return new_themes, stats


# =============================================================================
# File Writing
# =============================================================================


def write_updated_metadata(
    meta_file: Path, new_themes: List[Dict[str, str]]
) -> None:
    """
    Update the themes field in a metadata YAML file.

    Uses ruamel.yaml for format-preserving writes — only the themes
    section is modified, all other fields remain untouched.

    Args:
        meta_file: Path to the metadata YAML file to update
        new_themes: List of theme dicts with name and description
    """
    ryaml = YAML()
    ryaml.preserve_quotes = True
    ryaml.width = 80
    ryaml.indent(mapping=2, sequence=4, offset=2)

    with open(meta_file, encoding="utf-8") as f:
        data = ryaml.load(f)

    # Build themed entries using ruamel types to preserve formatting
    if new_themes:
        seq = CommentedSeq()
        for t in new_themes:
            cm = CommentedMap()
            cm["name"] = t["name"]
            desc = t.get("description", "")
            if desc:
                cm["description"] = FoldedScalarString(desc)
            seq.append(cm)
        data["themes"] = seq
    elif "themes" in data:
        del data["themes"]

    with open(meta_file, "w", encoding="utf-8") as f:
        ryaml.dump(data, f)


# =============================================================================
# Main
# =============================================================================


def main() -> None:
    """
    Run theme description recovery.

    Scans all metadata YAML files, matches themes against narrative_analysis
    data, and writes updated theme format with descriptions.
    """
    parser = argparse.ArgumentParser(
        description="Recover theme descriptions from narrative_analysis data"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Report changes without modifying files",
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Print detailed per-entry changes",
    )
    args = parser.parse_args()

    na_dir = DATA_DIR / "narrative_analysis"
    meta_dir = JOURNAL_YAML_DIR

    if not na_dir.exists():
        print(f"ERROR: narrative_analysis directory not found: {na_dir}")
        sys.exit(1)

    if not meta_dir.exists():
        print(f"ERROR: metadata/journal directory not found: {meta_dir}")
        sys.exit(1)

    # Phase 1: Identify recurring dropped themes
    print("Scanning for recurring dropped themes...")
    recurring_dropped, na_counts = compute_recurring_dropped(na_dir, meta_dir)
    print(f"Found {len(recurring_dropped)} recurring dropped themes (2+ NA entries)")

    if args.verbose and recurring_dropped:
        for name in sorted(recurring_dropped):
            print(f"  {name} ({na_counts[name]} NA entries)")

    # Phase 2: Process each metadata file
    print("\nProcessing metadata files...")
    total_stats: Dict[str, int] = {
        "files_processed": 0,
        "files_changed": 0,
        "matched": 0,
        "deleted": 0,
        "restored": 0,
        "no_themes": 0,
    }

    for year_dir in sorted(meta_dir.iterdir()):
        if not year_dir.is_dir():
            continue

        for meta_file in sorted(year_dir.glob("*.yaml")):
            date_str = meta_file.stem
            total_stats["files_processed"] += 1

            # Find corresponding NA file
            year = date_str[:4]
            na_file = na_dir / year / f"{date_str}_analysis.yaml"
            if not na_file.exists():
                na_file = None

            # Check if entry has themes
            meta_themes = load_metadata_themes(meta_file)
            na_themes = load_na_themes(na_file) if na_file else {}

            if not meta_themes and not any(
                n in recurring_dropped for n in na_themes
            ):
                total_stats["no_themes"] += 1
                continue

            if args.verbose:
                print(f"\n{date_str}:")

            new_themes, stats = recover_entry_themes(
                meta_file, na_file, recurring_dropped, args.verbose
            )

            total_stats["matched"] += stats["matched"]
            total_stats["deleted"] += stats["deleted"]
            total_stats["restored"] += stats["restored"]

            # Write changes
            has_changes = (
                stats["deleted"] > 0
                or stats["restored"] > 0
                or stats["matched"] > 0  # Format change even if same names
            )

            if has_changes:
                total_stats["files_changed"] += 1
                if not args.dry_run:
                    write_updated_metadata(meta_file, new_themes)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Files processed:  {total_stats['files_processed']}")
    print(f"Files changed:    {total_stats['files_changed']}")
    print(f"Files unchanged:  {total_stats['no_themes']}")
    print(f"Themes matched:   {total_stats['matched']}")
    print(f"Themes deleted:   {total_stats['deleted']}")
    print(f"Themes restored:  {total_stats['restored']}")

    if args.dry_run:
        print("\n(DRY RUN — no files were modified)")
    else:
        print(f"\nDone. Run 'plm metadata import' to rebuild the database.")


if __name__ == "__main__":
    main()
