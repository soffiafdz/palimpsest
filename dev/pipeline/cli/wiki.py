"""
Wiki Synchronization Commands
------------------------------

Commands for bidirectional sync between SQL database and Vimwiki pages.

Commands:
    - export-wiki: Export database entities to vimwiki (SQL → wiki)
    - import-wiki: Import wiki edits back to database (wiki → SQL)

This handles the wiki presentation and editing layer.
"""
from __future__ import annotations

import sys
import click
from pathlib import Path

from dev.core.paths import (
    MD_DIR,
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
    WIKI_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.database.manager import PalimpsestDB


@click.command("export-wiki")
@click.argument(
    "entity_type",
    type=click.Choice([
        "entries", "locations", "cities", "events", "timeline", "index", "stats", "analysis",
        "people", "themes", "tags", "poems", "references", "all"
    ]),
)
@click.option("-f", "--force", is_flag=True, help="Force regenerate all files")
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Vimwiki root directory",
)
@click.pass_context
def export_wiki(ctx: click.Context, entity_type: str, force: bool, wiki_dir: str) -> None:
    """Export database entities to vimwiki pages."""
    from dev.pipeline.sql2wiki import (
        export_index,
        export_stats,
        export_timeline,
        export_analysis_report,
        get_exporter,
    )

    logger: PalimpsestLogger = ctx.obj["logger"]
    wiki_path = Path(wiki_dir)
    journal_dir = MD_DIR

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    try:
        if entity_type == "index":
            click.echo(f"📤 Exporting wiki homepage to {wiki_path}/index.md")
            status = export_index(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Index {status}")
        elif entity_type == "stats":
            click.echo(f"📤 Exporting statistics dashboard to {wiki_path}/stats.md")
            status = export_stats(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Statistics {status}")
        elif entity_type == "timeline":
            click.echo(f"📤 Exporting timeline to {wiki_path}/timeline.md")
            status = export_timeline(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Timeline {status}")
        elif entity_type == "analysis":
            click.echo(f"📤 Exporting analysis report to {wiki_path}/analysis.md")
            status = export_analysis_report(db, wiki_path, journal_dir, force, logger)
            click.echo(f"\n✅ Analysis report {status}")
        elif entity_type == "all":
            click.echo(f"📤 Exporting all entities to {wiki_path}/")
            all_stats = []
            for entity_name in ["entries", "locations", "cities", "events", "people", "themes", "tags", "poems", "references"]:
                exporter = get_exporter(entity_name)
                stats = exporter.export_all(db, wiki_path, journal_dir, force, logger)
                all_stats.append(stats)

            export_index(db, wiki_path, journal_dir, force, logger)
            export_stats(db, wiki_path, journal_dir, force, logger)
            export_timeline(db, wiki_path, journal_dir, force, logger)
            export_analysis_report(db, wiki_path, journal_dir, force, logger)

            total_files = sum(s.files_processed for s in all_stats)
            total_created = sum(s.entries_created for s in all_stats)
            total_updated = sum(s.entries_updated for s in all_stats)
            total_skipped = sum(s.entries_skipped for s in all_stats)
            total_errors = sum(s.errors for s in all_stats)
            total_duration = sum(s.duration() for s in all_stats)

            click.echo("\n✅ All exports complete:")
            click.echo(f"  Total files: {total_files}")
            click.echo(f"  Created: {total_created}")
            click.echo(f"  Updated: {total_updated}")
            click.echo(f"  Skipped: {total_skipped}")
            if total_errors > 0:
                click.echo(f"  ⚠️  Errors: {total_errors}")
            click.echo(f"  Duration: {total_duration:.2f}s")
        else:
            exporter = get_exporter(entity_type)
            click.echo(f"📤 Exporting {exporter.config.plural} to {wiki_path}/{exporter.config.output_subdir}/")
            stats = exporter.export_all(db, wiki_path, journal_dir, force, logger)

            click.echo(f"\n✅ {exporter.config.plural.title()} export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

    except Exception as e:
        handle_cli_error(ctx, e, "export_wiki", {"entity_type": entity_type})


@click.command("import-wiki")
@click.argument(
    "entity_type",
    type=click.Choice([
        "people", "themes", "tags", "entries", "events",
        "manuscript-entries", "manuscript-characters", "manuscript-events",
        "all", "manuscript-all"
    ]),
)
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Wiki root directory",
)
@click.pass_context
def import_wiki(ctx: click.Context, entity_type: str, wiki_dir: str) -> None:
    """Import wiki edits back to database."""
    from dev.pipeline.wiki2sql import (
        import_people,
        import_themes,
        import_tags,
        import_entries,
        import_events,
        import_all,
        import_all_manuscript_entries,
        import_all_manuscript_characters,
        import_all_manuscript_events,
        ImportStats,
    )

    logger: PalimpsestLogger = ctx.obj["logger"]
    wiki_path = Path(wiki_dir)

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    try:
        click.echo(f"📥 Importing {entity_type} from {wiki_path}/")

        if entity_type == "people":
            stats = import_people(wiki_path, db, logger)
        elif entity_type == "themes":
            stats = import_themes(wiki_path, db, logger)
        elif entity_type == "tags":
            stats = import_tags(wiki_path, db, logger)
        elif entity_type == "entries":
            stats = import_entries(wiki_path, db, logger)
        elif entity_type == "events":
            stats = import_events(wiki_path, db, logger)
        elif entity_type == "manuscript-entries":
            stats = import_all_manuscript_entries(db, wiki_path, logger)
        elif entity_type == "manuscript-characters":
            stats = import_all_manuscript_characters(db, wiki_path, logger)
        elif entity_type == "manuscript-events":
            stats = import_all_manuscript_events(db, wiki_path, logger)
        elif entity_type == "manuscript-all":
            combined_stats = ImportStats()
            for import_func in [
                import_all_manuscript_entries,
                import_all_manuscript_characters,
                import_all_manuscript_events,
            ]:
                s = import_func(db, wiki_path, logger)
                combined_stats.files_processed += s.files_processed
                combined_stats.records_updated += s.records_updated
                combined_stats.records_skipped += s.records_skipped
                combined_stats.errors += s.errors
            stats = combined_stats
        elif entity_type == "all":
            stats = import_all(wiki_path, db, logger)
        else:
            click.echo(f"❌ Unknown entity type: {entity_type}")
            sys.exit(1)

        click.echo("\n✅ Import complete:")
        click.echo(f"  Files processed: {stats.files_processed}")
        click.echo(f"  Records updated: {stats.records_updated}")
        click.echo(f"  Records skipped: {stats.records_skipped}")
        if stats.errors > 0:
            click.echo(f"  ⚠️  Errors: {stats.errors}")

    except Exception as e:
        handle_cli_error(ctx, e, "import_wiki", {"entity_type": entity_type})


__all__ = ["export_wiki", "import_wiki"]
