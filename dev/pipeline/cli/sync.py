#!/usr/bin/env python3
"""
sync.py
-------
Orchestrates cross-machine synchronization for the Palimpsest database.

Runs the full sync workflow in the correct order so that a freshly-pulled
``data/`` submodule converges with all local and remote changes:

1. JSON import   -- load shared DB state from ``data/exports/journal/``
2. Entries import -- process MD+YAML files where the content hash changed
3. Metadata import -- process entity YAML files (people, locations, etc.)
4. JSON export   -- re-snapshot DB if steps 2 or 3 introduced changes
5. Wiki generate -- regenerate wiki pages (skippable with ``--no-wiki``)
6. Git commit    -- commit inside ``data/`` submodule (only with ``--commit``)

Each step is logged with a one-line status. Verbose mode (``-v``) prints
per-entity detail from every importer/exporter.

Key Features:
    - Idempotent: safe to run repeatedly on the same data
    - Skips JSON export when nothing changed upstream
    - Optional wiki regeneration and data submodule commit
    - Dry-run mode previews all changes without writing

Usage:
    # Standard sync after git pull
    plm sync

    # Sync, skip wiki, auto-commit data submodule
    plm sync --no-wiki --commit

    # Dry-run preview
    plm sync --dry-run

    # Limit entries import to specific years
    plm sync --years 2024-2025

Dependencies:
    - dev.pipeline.import_json.JSONImporter
    - dev.pipeline.metadata_importer.EntryImporter
    - dev.wiki.metadata.MetadataImporter
    - dev.pipeline.export_json.JSONExporter
    - dev.wiki.exporter.WikiExporter
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import subprocess
from pathlib import Path
from typing import Any, Optional, Set

# --- Third-party imports ---
import click

# --- Local imports ---
from dev.core.logging_manager import handle_cli_error
from dev.core.paths import (
    ALEMBIC_DIR,
    BACKUP_DIR,
    DATA_DIR,
    DB_PATH,
    JOURNAL_YAML_DIR,
    LOG_DIR,
)


def _parse_years(years: Optional[str]) -> Optional[Set[str]]:
    """
    Parse a year or year-range string into a set of year strings.

    Args:
        years: A single year (``"2024"``) or a dash-separated range
               (``"2021-2025"``).  ``None`` means no filtering.

    Returns:
        A set of year strings, or ``None`` when no filter is requested.
    """
    if years is None:
        return None
    if "-" in years:
        start, end = years.split("-", 1)
        return {str(y) for y in range(int(start), int(end) + 1)}
    return {years}


def _collect_yaml_files(years_filter: Optional[Set[str]]) -> list:
    """
    Gather journal YAML files, optionally filtered by year.

    Files whose names start with ``_`` (e.g. ``_schema.yaml``) are
    excluded.

    Args:
        years_filter: If provided, only include files whose parent
                      directory name is in this set.

    Returns:
        A sorted list of ``Path`` objects pointing to YAML files.
    """
    yaml_files = sorted(JOURNAL_YAML_DIR.glob("**/*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]
    if years_filter:
        yaml_files = [f for f in yaml_files if f.parent.name in years_filter]
    return yaml_files


def _run_json_import(
    db: Any,
    logger: Any,
    verbose: bool,
    changed_files: Optional[Set[Path]] = None,
) -> int:
    """
    Step 1: Import shared DB state from JSON export files.

    Args:
        db: Initialised ``PalimpsestDB`` instance.
        logger: Pipeline logger.
        verbose: Print per-entity counts.
        changed_files: Set of changed file paths for incremental
            import. ``None`` means full import.

    Returns:
        Total number of entities imported across all types.
    """
    from dev.pipeline.import_json import JSONImporter

    importer = JSONImporter(db, logger=logger)
    stats = importer.import_all(changed_files=changed_files)

    total = sum(stats.values())
    if verbose:
        for entity_type, count in stats.items():
            if count > 0:
                click.echo(f"    {entity_type}: {count}")
    return total


def _run_entries_import(
    db: Any,
    logger: Any,
    years_filter: Optional[Set[str]],
    dry_run: bool,
    verbose: bool,
) -> int:
    """
    Step 2: Import journal entries from MD+YAML where hashes changed.

    Args:
        db: Initialised ``PalimpsestDB`` instance.
        logger: Pipeline logger.
        years_filter: Limit to these year directories, or all if ``None``.
        dry_run: Preview without committing.
        verbose: Print detailed summary.

    Returns:
        Number of entries processed (excluding skipped).
    """
    from dev.pipeline.metadata_importer import EntryImporter

    yaml_files = _collect_yaml_files(years_filter)
    if not yaml_files:
        click.echo("  No YAML files found for entries import.")
        return 0

    with db.session_scope() as session:
        importer = EntryImporter(
            session=session,
            dry_run=dry_run,
            logger=logger,
        )
        stats = importer.import_all(yaml_files, failed_only=False)

    if verbose:
        click.echo(f"    {stats.summary()}")
        click.echo(f"    {stats.entity_summary()}")

    return stats.processed


def _run_auto_prune(db: Any, verbose: bool) -> int:
    """
    Prune orphaned entities after entries import.

    Args:
        db: Initialised ``PalimpsestDB`` instance.
        verbose: Print per-type prune counts.

    Returns:
        Total number of orphaned entities deleted.
    """
    from dev.database.cli.prune import _prune_entity_type

    total_pruned = 0
    for etype in [
        "people", "locations", "cities", "tags", "themes", "arcs",
        "events", "reference_sources", "poems", "motifs",
    ]:
        _, deleted = _prune_entity_type(db, etype, False, False)
        total_pruned += deleted
        if verbose and deleted:
            click.echo(f"    {etype}: {deleted}")
    return total_pruned


def _run_metadata_import(
    db: Any,
    logger: Any,
    verbose: bool,
    changed_files: Optional[Set[Path]] = None,
) -> int:
    """
    Step 3: Import entity YAML metadata files.

    Args:
        db: Initialised ``PalimpsestDB`` instance.
        logger: Pipeline logger.
        verbose: Print per-type counts.
        changed_files: Set of changed file paths for incremental
            import. ``None`` means full import.

    Returns:
        Total number of entities imported.
    """
    from dev.wiki.metadata import MetadataImporter

    importer = MetadataImporter(db, logger=logger)
    stats = importer.import_all(changed_files=changed_files)

    total = sum(stats.values())
    if verbose:
        for entity_type, count in stats.items():
            if count > 0:
                click.echo(f"    {entity_type}: {count}")
    return total


def _run_json_export(
    db: Any,
    logger: Any,
    verbose: bool,
) -> None:
    """
    Step 4: Re-snapshot DB to JSON export files.

    Args:
        db: Initialised ``PalimpsestDB`` instance.
        logger: Pipeline logger.
        verbose: Print export stats.
    """
    from dev.pipeline.export_json import JSONExporter

    exporter = JSONExporter(db, logger=logger)
    exporter.export_all(commit=False)

    if verbose:
        for key, value in exporter.stats.items():
            click.echo(f"    {key}: {value}")


def _run_wiki_generate(
    db: Any,
    logger: Any,
    verbose: bool,
) -> None:
    """
    Step 5: Regenerate wiki pages from DB.

    Args:
        db: Initialised ``PalimpsestDB`` instance.
        logger: Pipeline logger.
        verbose: Print generation stats.
    """
    from dev.wiki.exporter import WikiExporter

    exporter = WikiExporter(db, logger=logger)
    exporter.generate_all()

    if verbose:
        for key, value in exporter.stats.items():
            click.echo(f"    {key}: {value}")


def _run_data_commit() -> bool:
    """
    Step 6: Stage and commit all changes inside the ``data/`` submodule.

    Only creates a commit when there are staged or unstaged changes.

    Returns:
        ``True`` if a commit was created, ``False`` if nothing to commit.
    """
    subprocess.run(
        ["git", "add", "-A"],
        cwd=DATA_DIR,
        check=True,
        capture_output=True,
    )

    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=DATA_DIR,
        check=True,
        capture_output=True,
        text=True,
    )

    if not result.stdout.strip():
        return False

    subprocess.run(
        ["git", "commit", "-m", "data update"],
        cwd=DATA_DIR,
        check=True,
        capture_output=True,
    )
    return True


@click.command()
@click.option(
    "--no-wiki",
    is_flag=True,
    default=False,
    help="Skip wiki page regeneration.",
)
@click.option(
    "--commit",
    "do_commit",
    is_flag=True,
    default=False,
    help="Auto-commit in data/ submodule after sync.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview changes without modifying the database.",
)
@click.option(
    "--years",
    type=str,
    default=None,
    help="Limit entries import scope (e.g. 2024 or 2021-2025).",
)
@click.option(
    "--full",
    is_flag=True,
    default=False,
    help="Force full reimport (ignore incremental state).",
)
@click.option(
    "-v", "--verbose",
    is_flag=True,
    default=False,
    help="Detailed step-by-step output.",
)
@click.pass_context
def sync(
    ctx: click.Context,
    no_wiki: bool,
    do_commit: bool,
    dry_run: bool,
    years: Optional[str],
    full: bool,
    verbose: bool,
) -> None:
    """Run the full cross-machine synchronization workflow.

    Orchestrates JSON import, entries import, metadata import,
    JSON export, wiki generation, and an optional data/ submodule
    commit in the correct dependency order.

    Defaults for --no-wiki, --commit, and --years can be set in
    .palimpsest.yaml (shared) or .palimpsest.local.yaml (per-host).
    CLI flags always override config values.

    \b
    Steps run in order:
      1. JSON import   -- load shared state from data/exports/journal/
      2. Entries import -- process MD+YAML where hash mismatches
      3. Metadata import -- process entity YAML files
      4. JSON export   -- re-snapshot if steps 2 or 3 made changes
      5. Wiki generate -- update wiki pages (skip with --no-wiki)
      6. Git commit    -- commit data/ submodule (only with --commit)
    """
    from dev.core.config import get_sync_config
    from dev.database.manager import PalimpsestDB
    from dev.pipeline.sync_state import (
        get_data_head,
        get_stored_sync_hash,
        store_sync_hash,
        get_changed_files,
        filter_json_export_files,
        filter_metadata_files,
    )

    logger = ctx.obj.get("logger")

    # Apply config defaults — CLI flags override config values
    cfg = get_sync_config()
    no_wiki = no_wiki or cfg["no_wiki"]
    do_commit = do_commit or cfg["auto_commit"]
    if years is None and cfg["years"]:
        years = cfg["years"]

    years_filter = _parse_years(years)

    # Determine sync mode: incremental vs full
    current_hash = get_data_head()
    stored_hash = get_stored_sync_hash()

    if full or stored_hash is None or current_hash is None:
        json_changed: Optional[Set[Path]] = None
        meta_changed: Optional[Set[Path]] = None
        sync_mode = "full"
        if full:
            reason = "--full flag"
        elif stored_hash is None:
            reason = "first sync (no stored state)"
        else:
            reason = "data/ is not a git repo"
    elif stored_hash == current_hash:
        json_changed = set()
        meta_changed = set()
        sync_mode = "incremental (no changes in data/)"
        reason = "HEAD unchanged"
    else:
        all_changed = get_changed_files(stored_hash, current_hash)
        json_changed = filter_json_export_files(all_changed)
        meta_changed = filter_metadata_files(all_changed)
        sync_mode = "incremental"
        reason = f"{len(all_changed)} files changed"

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    click.echo(f"Sync mode: {sync_mode} ({reason})")

    if dry_run:
        click.echo("[dry-run] Previewing sync steps (no DB writes).\n")

    try:
        # -- Step 1: JSON import --
        click.echo("[1/6] JSON import...")
        if not dry_run:
            if json_changed is not None and len(json_changed) == 0:
                click.echo("  No JSON changes; skipped.")
                json_total = 0
            else:
                json_total = _run_json_import(
                    db, logger, verbose, changed_files=json_changed,
                )
                click.echo(f"  Imported {json_total} entities from JSON.")
        else:
            json_total = 0
            click.echo("  Skipped (dry-run).")

        # -- Step 2: Entries import --
        scope_label = f" (years: {years})" if years else ""
        click.echo(f"[2/6] Entries import{scope_label}...")
        entries_changed = _run_entries_import(
            db, logger, years_filter, dry_run, verbose,
        )
        click.echo(f"  Processed {entries_changed} entries.")

        # -- Step 2b: Auto-prune orphans --
        if not dry_run and entries_changed > 0:
            click.echo("  Pruning orphaned entities...")
            pruned = _run_auto_prune(db, verbose)
            if pruned:
                click.echo(f"  Pruned {pruned} orphans.")

        # -- Step 3: Metadata import --
        click.echo("[3/6] Metadata import...")
        meta_total = 0
        if not dry_run:
            if meta_changed is not None and len(meta_changed) == 0:
                click.echo("  No metadata changes; skipped.")
            else:
                meta_total = _run_metadata_import(
                    db, logger, verbose, changed_files=meta_changed,
                )
                click.echo(f"  Imported {meta_total} metadata entities.")
        else:
            click.echo("  Skipped (dry-run).")

        # -- Step 4: JSON export (only if upstream steps changed data) --
        click.echo("[4/6] JSON export...")
        if dry_run:
            click.echo("  Skipped (dry-run).")
        elif entries_changed > 0 or meta_total > 0:
            _run_json_export(db, logger, verbose)
            click.echo("  DB re-exported to JSON.")
        else:
            click.echo("  No changes detected; skipped.")

        # -- Step 5: Wiki generate --
        if no_wiki:
            click.echo("[5/6] Wiki generate... skipped (--no-wiki).")
        elif dry_run:
            click.echo("[5/6] Wiki generate... skipped (dry-run).")
        else:
            click.echo("[5/6] Wiki generate...")
            _run_wiki_generate(db, logger, verbose)
            click.echo("  Wiki pages regenerated.")

        # -- Step 6: Git commit in data/ submodule --
        if do_commit and not dry_run:
            click.echo("[6/6] Data submodule commit...")
            committed = _run_data_commit()
            if committed:
                click.echo("  Committed changes in data/.")
            else:
                click.echo("  Nothing to commit.")
        elif do_commit and dry_run:
            click.echo("[6/6] Data submodule commit... skipped (dry-run).")
        else:
            click.echo("[6/6] Data submodule commit... skipped (use --commit).")

        # -- Store sync state --
        if not dry_run and current_hash:
            new_hash = get_data_head()
            if new_hash:
                store_sync_hash(new_hash)

        click.echo("\n[OK] Sync complete.")

    except SystemExit:
        raise
    except Exception as e:
        handle_cli_error(ctx, e, "sync")
        raise
