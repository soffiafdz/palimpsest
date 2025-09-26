#!/usr/bin/env python3
"""
md2json.py
-------------------
Synchronize a metadata registry (JSON) with frontmatter from Markdown files.

Features:
- Parses YAML frontmatter from each Markdown file in a directory.
- Validates and normalizes metadata using MetadataValidator.
- Records only non-default/curated metadata entries.
- Tracks and reports newly added and updated registry entries.
- Supports a dry-run mode to preview changes without writing.
- Uses the shared MetadataRegistry, MetaEntry, and MetadataValidator classes.

Typical usage:
    python md2json.py --input journal/md --output journal/metadata.json
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import sys
import warnings
import yaml
from pathlib import Path
from typing import Any

# --- Local imports ---
from code.metadata import MetadataRegistry, MetaEntry, MetadataValidator
from code.paths import MD_DIR, METADATA_JSON


# ----- Argument parser -----
def parse_args() -> argparse.Namespace:
    """
    Arguments:
        - input: Directory with Markdown entry files to be parsed.
        - output: Metadata JSON registry file to be updated/created.
        - glob: Glob pattern for Markdown file parsing.
        - dry-run: Do not write output file.
        - verbose: Logging.
    """
    p = argparse.ArgumentParser(
        description="Extract metadata: Markdown →  registry JSON."
    )

    # --- ARGUMENTS ---
    p.add_argument(
        "-i",
        "--input",
        default=str(MD_DIR),
        help=f"Path to the Markdown dir (default: {str(MD_DIR)})",
    )
    p.add_argument(
        "-o",
        "--output",
        default=str(METADATA_JSON),
        help="Path to metadata.json to update (will be created if missing)",
    )
    p.add_argument(
        "--glob", default="*.md", help="Glob pattern for Markdown files (default: *.md)"
    )
    p.add_argument(
        "--dry-run", action="store_true", help="If set, do not write output file"
    )
    p.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    return p.parse_args()


# ----- Main -----
def main() -> None:
    """
    Main entry point for the Markdown-to-metadata synchronization script.

    Scans a directory for Markdown files, extracts YAML frontmatter,
    validates and normalizes metadata, and updates the metadata registry JSON.
    Supports dry-run mode and reports added/updated entries.
    """
    # -- Setup --
    args = parse_args()
    input = Path(args.input)
    meta_path = Path(args.out)

    if not input.exists() or not input.is_dir():
        raise OSError(f"Input directory not found: {str(input)}")

    try:
        registry = MetadataRegistry(meta_path)
    except Exception as e:
        raise OSError(
            "Failed to load or create metadata registry at " f"{str(meta_path)}: {e}"
        )

    # -- Counter setup --
    count = 0
    added, updated = [], []

    # -- MD parsing --
    files = sorted(input.glob(args.glob))
    if not files:
        warnings.warn(
            "Warning: No Markdown files matched pattern "
            f"{args.glob} in {str(input)}",
            UserWarning,
        )

    for md_file in files:
        try:
            meta: dict[str, Any] = registry.validator.extract_yaml_frontmatter(md_file)
        except Exception as e:
            warnings.warn(f"Warning: Skipping {str(md_file)}: {e}", UserWarning)
            continue

        if not meta:
            if args.verbose:
                warnings.warn(
                    f"Warning: Skipping {str(md_file)}: no YAML frontmatter",
                    UserWarning,
                )
            continue

        meta = registry.validator.normalize(meta)
        if registry.validator.is_default(meta):
            if args.verbose:
                warnings.warn(
                    f"Warning: Skipping {str(md_file)}: only default metadata",
                    UserWarning,
                )
            continue

        if not registry.validator.validate(meta):
            warnings.warn(
                f"Warning: Skipping {str(md_file)} due to validation error", UserWarning
            )
            continue

        key = meta.get("date")
        if not key:
            warnings.warn(
                f"Warning: Skipping {str(md_file)}: missing 'date' field", UserWarning
            )
            continue

        existed = key in registry._data
        registry.update(key, meta)
        if existed:
            updated.append(key)
            if args.verbose:
                print(f"[md2json] →  Updated registry for {key} ({md_file.name})")
        else:
            added.append(key)
            if args.verbose:
                print(f"[md2json] →  Added registry for {key} ({md_file.name})")
        count += 1

    if added:
        print(f"[md2json] →  Newly added entries: {', '.join(added)}")
    if updated:
        print(f"[md2json] →  Updated entries: {', '.join(updated)}")

    if not args.dry_run:
        registry.save()
        print(
            f"[md2json] →  Synced metadata for {count} "
            f"Markdown files to {str(meta_path)}"
        )
    else:
        print(f"[md2json] →  (Dry-run) Would have written: {str(meta_path)}")


if __name__ == "__main__":
    main()
