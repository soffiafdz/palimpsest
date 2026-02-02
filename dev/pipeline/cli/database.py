"""
Database Synchronization Commands
----------------------------------

Commands for bidirectional sync between Markdown/YAML and SQL database.

Commands:
    - sync-db: Sync Markdown metadata into database (yaml → SQL)
    - export-db: Export database to Markdown files (SQL → yaml)

This handles the core database synchronization layer.
"""
from __future__ import annotations

import click
from pathlib import Path

from dev.core.paths import (
    MD_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
    JOURNAL_YAML_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.database.manager import PalimpsestDB
from dev.pipeline.yaml2sql import process_directory
from dev.pipeline.sql2yaml import export_entry_to_markdown
from dev.pipeline.metadata_importer import MetadataImporter


@click.command("sync-db")
@click.option(
    "-i",
    "--input",
    type=click.Path(),
    default=str(MD_DIR),
    help="Input directory with Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force update all entries")
@click.option("--dry-run", is_flag=True, help="Preview changes without modifying database")
@click.pass_context
def sync_db(ctx: click.Context, input: str, force: bool, dry_run: bool) -> None:
    """
    Synchronize database with Markdown metadata.

    This is STEP 3 of the pipeline - reads human-edited Markdown files
    with rich YAML frontmatter and populates the database.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("🔄 Syncing database from Markdown (DRY RUN - no database changes)...")
        click.echo()
        input_path = Path(input)

        md_files = sorted(input_path.rglob("*.md"))
        click.echo(f"Would process {len(md_files)} .md files:")

        with click.progressbar(
            md_files[:10] if len(md_files) > 10 else md_files,
            label="Scanning files",
            show_pos=True
        ) as files:
            for _md_file in files:
                pass  # Progress visualization

        if len(md_files) > 10:
            click.echo(f"  ... and {len(md_files) - 10} more files")

        click.echo(f"\nDatabase: {DB_PATH}")
        click.echo(f"Force update: {force}")
        click.echo("Auto-backup: Enabled")
        click.echo("\n💡 Run without --dry-run to execute database sync")
        return

    click.echo("🔄 Syncing database from Markdown...")

    try:
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=True,
        )

        stats = process_directory(
            input_dir=Path(input), db=db, force_update=force, logger=logger
        )

        click.echo("\n✅ Database sync complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Entries created: {stats.entries_created}")
        click.echo(f"  Entries updated: {stats.entries_updated}")
        click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "sync_db",
            additional_context={"input": input},
        )


@click.command("export-db")
@click.option(
    "-o",
    "--output",
    type=click.Path(),
    default=str(MD_DIR),
    help="Output directory for Markdown files",
)
@click.option("-f", "--force", is_flag=True, help="Force overwrite existing files")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing files")
@click.pass_context
def export_db(ctx: click.Context, output: str, force: bool, dry_run: bool) -> None:
    """
    Export database to Markdown files.

    This is the INVERSE of sync-db - reads database records and generates
    human-editable Markdown files with complete YAML frontmatter.
    """
    logger: PalimpsestLogger = ctx.obj["logger"]

    if dry_run:
        click.echo("📤 Exporting database to Markdown (DRY RUN - no files will be written)...")
        click.echo()

        try:
            db = PalimpsestDB(
                db_path=DB_PATH,
                alembic_dir=ALEMBIC_DIR,
                log_dir=LOG_DIR,
                backup_dir=BACKUP_DIR,
                enable_auto_backup=False,
            )

            with db.session_scope() as session:
                from dev.database.models import Entry
                entry_count = session.query(Entry).count()

                click.echo(f"Would export {entry_count} database entries")
                click.echo(f"Output directory: {output}")
                click.echo(f"Force overwrite: {force}")
                click.echo("Preserve body content: True")

                sample_entries = session.query(Entry).order_by(Entry.date.desc()).limit(5).all()
                click.echo("\nSample entries that would be exported:")
                for entry in sample_entries:
                    year = entry.date.year
                    filename = f"{entry.date.isoformat()}.md"
                    click.echo(f"  • {output}/{year}/{filename}")

                click.echo(f"\n  ... and {max(0, entry_count - 5)} more entries")
                click.echo("\n💡 Run without --dry-run to execute export")
                return

        except Exception as e:
            handle_cli_error(ctx, e, "export_db_dry_run")
            return

    click.echo("📤 Exporting database to Markdown...")

    try:
        db = PalimpsestDB(
            db_path=DB_PATH,
            alembic_dir=ALEMBIC_DIR,
            log_dir=LOG_DIR,
            backup_dir=BACKUP_DIR,
            enable_auto_backup=False,
        )

        with db.session_scope() as session:
            stats = db.export_manager.export_hierarchical(
                session,
                export_entry_to_markdown,
                threshold=500,
                output_dir=Path(output),
                force_overwrite=force,
                preserve_body=True,
                logger=logger,
            )

        click.echo("\n✅ Export complete:")
        click.echo(f"  Total entries: {stats['total_entries']}")
        click.echo(f"  Processed: {stats['processed']}")
        if stats.get("errors", 0) > 0:
            click.echo(f"  Errors: {stats['errors']}")
        click.echo(f"  Duration: {stats['duration']:.2f}s")

    except Exception as e:
        handle_cli_error(
            ctx,
            e,
            "export_db",
            additional_context={"output": output},
        )


@click.command("import-metadata")
@click.option("--dry-run", is_flag=True, help="Don't commit changes")
@click.option("-y", "--year", type=str, help="Import only specific year (e.g., 2024)")
@click.option("--years", type=str, help="Import year range (e.g., 2021-2025)")
@click.pass_context
def import_metadata(ctx: click.Context, dry_run: bool, year: str, years: str) -> None:
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

    # Create database session
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Run import
        importer = MetadataImporter(
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
    finally:
        session.close()


@click.command("prune-orphans")
@click.option(
    "--type",
    "entity_type",
    type=click.Choice(["people", "locations", "cities", "tags", "themes", "arcs", "all"]),
    default="all",
    help="Type of entity to prune",
)
@click.option("--list", "list_only", is_flag=True, help="Only list orphans, don't delete")
@click.option("--dry-run", is_flag=True, help="Show what would be deleted")
@click.pass_context
def prune_orphans(ctx: click.Context, entity_type: str, list_only: bool, dry_run: bool) -> None:
    """Remove orphaned entities from database."""
    from dev.database.cli.prune import _prune_entity_type

    logger: PalimpsestLogger = ctx.obj["logger"]
    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    types_to_check = []
    if entity_type == "all":
        types_to_check = ["people", "locations", "cities", "tags", "themes", "arcs"]
    else:
        types_to_check = [entity_type]

    total_orphans = 0
    total_deleted = 0

    for etype in types_to_check:
        orphans, deleted = _prune_entity_type(db, etype, list_only, dry_run)
        total_orphans += orphans
        total_deleted += deleted

    click.echo("\n" + "=" * 60)
    if list_only:
        click.echo(f"Total orphaned entities: {total_orphans}")
    elif dry_run:
        click.echo(f"Would delete {total_orphans} orphaned entities")
    else:
        click.echo(f"✅ Deleted {total_deleted} orphaned entities")
    click.echo("=" * 60)


__all__ = ["sync_db", "export_db", "import_metadata", "prune_orphans"]
