#!/usr/bin/env python3
"""
extract_poems_refs.py
---------------------
Extract poems and references from MD frontmatter to legacy archive.

Reads all journal MD files, extracts poems and references fields,
resolving YAML anchors/aliases, and saves to legacy archive files.

Usage:
    python -m dev.pipeline.extract_poems_refs [--dry-run]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from dev.core.paths import MD_DIR, LEGACY_DIR


POEMS_ARCHIVE = LEGACY_DIR / "poems_archive.yaml"
REFS_ARCHIVE = LEGACY_DIR / "references_archive.yaml"


def extract_frontmatter_raw(content: str) -> tuple[str, str]:
    """Extract raw YAML frontmatter string and body."""
    if not content.startswith("---"):
        return "", content

    match = re.match(r"^---\n(.*?)\n---\n?(.*)$", content, re.DOTALL)
    if not match:
        return "", content

    return match.group(1), match.group(2)


def resolve_yaml_with_anchors(yaml_str: str) -> dict:
    """Parse YAML preserving anchor/alias resolution."""
    try:
        return yaml.safe_load(yaml_str) or {}
    except yaml.YAMLError:
        return {}


def extract_poem_content(poem: Dict[str, Any], epigraph: Optional[str]) -> Optional[str]:
    """
    Extract actual poem content, resolving aliases.

    If content is None (from *poem alias), use epigraph value.
    """
    content = poem.get("content")

    # If content is None, it was likely a YAML alias to epigraph
    if content is None and epigraph:
        return epigraph

    return content


def extract_all(dry_run: bool = False) -> tuple[dict, dict]:
    """
    Extract poems and references from all MD files.

    Args:
        dry_run: If True, don't write output files

    Returns:
        Tuple of (poems_archive, refs_archive) dicts
    """
    poems_archive: Dict[str, List[Dict[str, Any]]] = {}
    refs_archive: Dict[str, List[Dict[str, Any]]] = {}

    md_files = sorted(MD_DIR.glob("**/*.md"))
    print(f"Scanning {len(md_files)} MD files...")

    poems_count = 0
    refs_count = 0

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        yaml_str, _ = extract_frontmatter_raw(content)

        if not yaml_str:
            continue

        frontmatter = resolve_yaml_with_anchors(yaml_str)
        date_str = md_file.stem

        # Extract poems
        if "poems" in frontmatter and frontmatter["poems"]:
            epigraph = frontmatter.get("epigraph")
            poems_list = []

            for poem in frontmatter["poems"]:
                if isinstance(poem, dict):
                    poem_data = {
                        "title": poem.get("title", "Untitled"),
                    }

                    # Resolve content (may be alias)
                    content = extract_poem_content(poem, epigraph)
                    if content:
                        poem_data["content"] = content

                    # Include notes if present
                    if poem.get("notes"):
                        poem_data["notes"] = poem["notes"]

                    # Include revision_date if present
                    if poem.get("revision_date"):
                        poem_data["revision_date"] = str(poem["revision_date"])

                    poems_list.append(poem_data)

            if poems_list:
                poems_archive[date_str] = poems_list
                poems_count += len(poems_list)

        # Extract references
        if "references" in frontmatter and frontmatter["references"]:
            refs_list = []

            for ref in frontmatter["references"]:
                if isinstance(ref, dict):
                    ref_data = {}

                    # Content (may be multiline quote)
                    if ref.get("content"):
                        ref_data["content"] = ref["content"]

                    # Description
                    if ref.get("description"):
                        ref_data["description"] = ref["description"]

                    # Mode
                    if ref.get("mode"):
                        ref_data["mode"] = ref["mode"]

                    # Speaker
                    if ref.get("speaker"):
                        ref_data["speaker"] = ref["speaker"]

                    # Source info
                    if ref.get("source"):
                        source = ref["source"]
                        if isinstance(source, dict):
                            ref_data["source"] = {
                                k: v for k, v in source.items() if v
                            }

                    if ref_data:
                        refs_list.append(ref_data)

            if refs_list:
                refs_archive[date_str] = refs_list
                refs_count += len(refs_list)

    print(f"Found {poems_count} poems in {len(poems_archive)} entries")
    print(f"Found {refs_count} references in {len(refs_archive)} entries")

    if not dry_run:
        LEGACY_DIR.mkdir(parents=True, exist_ok=True)

        if poems_archive:
            with open(POEMS_ARCHIVE, "w", encoding="utf-8") as f:
                yaml.dump(
                    poems_archive,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=True,
                )
            print(f"Saved poems to {POEMS_ARCHIVE}")

        if refs_archive:
            with open(REFS_ARCHIVE, "w", encoding="utf-8") as f:
                yaml.dump(
                    refs_archive,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=True,
                )
            print(f"Saved references to {REFS_ARCHIVE}")
    else:
        print("[DRY RUN] Would save to", POEMS_ARCHIVE, "and", REFS_ARCHIVE)

    return poems_archive, refs_archive


def main():
    parser = argparse.ArgumentParser(description="Extract poems and references from MD frontmatter")
    parser.add_argument("--dry-run", action="store_true", help="Don't write output")
    args = parser.parse_args()

    extract_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
