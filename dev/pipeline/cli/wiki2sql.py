"""
Wiki→SQL Pipeline Commands
---------------------------

Commands for importing wiki data back into the database.

Commands:
    - import-wiki: Import wiki pages to database

This is the Wiki→SQL reverse pathway.
"""
from __future__ import annotations

import sys
import click
from pathlib import Path

from dev.core.paths import (
    DB_PATH,
    ALEMBIC_DIR,
    LOG_DIR,
    BACKUP_DIR,
    WIKI_DIR,
)
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.database.manager import PalimpsestDB


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


__all__ = ["import_wiki"]
