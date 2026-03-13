#!/usr/bin/env python3
"""
sync_state.py
-------------
Git-based change detection for incremental sync.

Tracks the last-imported commit hash of the ``data/`` submodule and
uses ``git diff`` to determine which files changed since the last
successful sync.  This allows ``plm sync`` to process only changed
files instead of re-importing everything.

Key Features:
    - Stores per-machine sync state alongside the database
    - Uses git diff to detect changed export and metadata files
    - Filters results by file type (JSON exports vs YAML metadata)
    - Gracefully falls back to full import when state is missing

Usage:
    from dev.pipeline.sync_state import (
        get_data_head, get_stored_sync_hash, store_sync_hash,
        get_changed_files,
    )

    stored = get_stored_sync_hash()
    current = get_data_head()
    if stored and current and stored != current:
        changed = get_changed_files(stored, current)

Dependencies:
    - git CLI (for submodule operations)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import subprocess
from pathlib import Path
from typing import Optional, Set

# --- Local imports ---
from dev.core.paths import DATA_DIR, JOURNAL_YAML_DIR, MD_DIR, SYNC_STATE_PATH


def get_data_head() -> Optional[str]:
    """
    Get the current HEAD commit hash of the data submodule.

    Returns:
        The full SHA-1 hash string, or ``None`` if the data
        directory is not a git repository.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=DATA_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_stored_sync_hash() -> Optional[str]:
    """
    Read the last-synced commit hash from the state file.

    Returns:
        The stored commit hash, or ``None`` if the state file
        does not exist (first run or after DB reset).
    """
    if not SYNC_STATE_PATH.exists():
        return None
    content = SYNC_STATE_PATH.read_text().strip()
    return content if content else None


def store_sync_hash(commit_hash: str) -> None:
    """
    Write the current commit hash to the state file.

    Args:
        commit_hash: The full SHA-1 hash to store.
    """
    SYNC_STATE_PATH.write_text(commit_hash + "\n")


def get_changed_files(from_hash: str, to_hash: str) -> Set[Path]:
    """
    Get files changed between two commits in the data submodule.

    Only includes files that currently exist on disk (deletions are
    excluded since orphan pruning handles those separately).

    Args:
        from_hash: Starting commit hash (last successful sync).
        to_hash: Ending commit hash (current HEAD).

    Returns:
        Set of absolute ``Path`` objects for each changed file.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", f"{from_hash}..{to_hash}"],
            cwd=DATA_DIR,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()

    changed: Set[Path] = set()
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        abs_path = DATA_DIR / line
        if abs_path.exists():
            changed.add(abs_path)
    return changed


def filter_json_export_files(changed: Set[Path]) -> Set[Path]:
    """
    Filter changed files to only JSON export files.

    Selects files under ``data/exports/journal/**/*.json``.

    Args:
        changed: Full set of changed file paths.

    Returns:
        Subset containing only JSON export files.
    """
    exports_dir = DATA_DIR / "exports" / "journal"
    return {f for f in changed if f.suffix == ".json" and exports_dir in f.parents}


def filter_metadata_files(changed: Set[Path]) -> Set[Path]:
    """
    Filter changed files to entity metadata YAML files.

    Selects files under ``data/metadata/**/*.yaml`` but excludes
    ``data/metadata/journal/`` (those are entry metadata, handled
    by the entries import step).

    Args:
        changed: Full set of changed file paths.

    Returns:
        Subset containing only entity metadata YAML files.
    """
    metadata_dir = DATA_DIR / "metadata"
    journal_metadata_dir = metadata_dir / "journal"
    return {
        f for f in changed
        if f.suffix == ".yaml"
        and metadata_dir in f.parents
        and journal_metadata_dir not in f.parents
        and f.parent != journal_metadata_dir
    }


def filter_entry_files(changed: Set[Path]) -> Set[Path]:
    """
    Filter changed files to journal entry YAML and MD files.

    Selects files under ``data/metadata/journal/`` (.yaml) and
    ``data/journal/content/md/`` (.md). Returns the YAML paths
    only, since EntryImporter iterates YAMLs and derives MD paths.

    Args:
        changed: Full set of changed file paths.

    Returns:
        Subset containing only entry YAML files whose YAML or
        corresponding MD changed.
    """
    changed_yamls = {
        f for f in changed
        if f.suffix == ".yaml"
        and (JOURNAL_YAML_DIR in f.parents or f.parent == JOURNAL_YAML_DIR)
    }

    # For changed MD files, find the corresponding YAML
    for f in changed:
        if f.suffix == ".md" and (MD_DIR in f.parents or f.parent == MD_DIR):
            # MD: data/journal/content/md/YYYY/YYYY-MM-DD.md
            # YAML: data/metadata/journal/YYYY/YYYY-MM-DD.yaml
            yaml_path = JOURNAL_YAML_DIR / f.parent.name / f.with_suffix(".yaml").name
            if yaml_path.exists():
                changed_yamls.add(yaml_path)

    return changed_yamls
