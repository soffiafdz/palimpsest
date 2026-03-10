"""
Database Commands
------------------

Commands for database operations.

Commands:
    - import: Import journal entry frontmatter YAML into database
"""
from __future__ import annotations

import click

from dev.core.paths import (
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
    JOURNAL_YAML_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.database.manager import PalimpsestDB
from dev.pipeline.metadata_importer import EntryImporter


@click.command("import")
@click.option("--dry-run", is_flag=True, help="Don't commit changes")
@click.option("-y", "--year", type=str, help="Import only specific year (e.g., 2024)")
@click.option("--years", type=str, help="Import year range (e.g., 2021-2025)")
@click.pass_context
def import_entries(ctx: click.Context, dry_run: bool, year: str, years: str) -> None:
    """
    Import metadata YAML files into database.

    Reads metadata YAML files (with narrative analysis) and MD frontmatter
    (with entry-level people/locations) to populate the database.

    Data sources:
    - MD Frontmatter: entry-level people, locations, narrated_dates
    - Metadata YAML: summary, rating, scenes, events, threads, etc.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    # Determine which years to import
    years_to_import = None
    if year:
        years_to_import = {year}
    elif years:
        if "-" in years:
            start_year, end_year = years.split("-")
            years_to_import = {str(y) for y in range(int(start_year), int(end_year) + 1)}
        else:
            years_to_import = {years}

    # Get YAML files from metadata/journal
    yaml_files = sorted(JOURNAL_YAML_DIR.glob("**/*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    # Filter by year if specified
    if years_to_import:
        yaml_files = [f for f in yaml_files if f.parent.name in years_to_import]

    click.echo(f"Found {len(yaml_files)} metadata YAML files to import")

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    try:
        with db.session_scope() as session:
            importer = EntryImporter(
                session=session,
                dry_run=dry_run,
                logger=logger,
            )
            stats = importer.import_all(yaml_files, failed_only=False)

        # Print results
        click.echo("")
        click.echo("=" * 60)
        click.echo("IMPORT RESULTS")
        click.echo("=" * 60)
        click.echo(stats.summary())
        click.echo("")
        click.echo(stats.entity_summary())
        click.echo("=" * 60)

        if stats.failed > 0:
            raise SystemExit(1)

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "import_metadata",
            additional_context={"dry_run": dry_run},
        )
        return

    # Auto-prune orphaned entities after successful import
    if not dry_run:
        from dev.database.cli.prune import _prune_entity_type

        click.echo("\nPruning orphaned entities...")
        total_pruned = 0
        for etype in [
            "people", "locations", "cities", "tags", "themes", "arcs",
            "events", "reference_sources", "poems", "motifs",
        ]:
            _, deleted = _prune_entity_type(db, etype, False, False)
            total_pruned += deleted
        if total_pruned:
            click.echo(f"Pruned {total_pruned} orphaned entities.")
        else:
            click.echo("No orphans found.")


__all__ = ["import_entries"]
