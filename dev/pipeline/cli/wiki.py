"""
Wiki Synchronization Commands
------------------------------

Commands for bidirectional sync between SQL database and Vimwiki pages.

Commands:
    - export-wiki: Export database entities to vimwiki (SQL → wiki)
    - import-wiki: Import wiki edits back to database (wiki → SQL)

This handles the wiki presentation and editing layer.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import sys
from pathlib import Path

# --- Third party imports ---
import click

# --- Local imports ---
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
    from dev.wiki import WikiExporter
    from dev.wiki.configs import (
        PERSON_CONFIG, LOCATION_CONFIG, CITY_CONFIG, ENTRY_CONFIG,
        EVENT_CONFIG, TAG_CONFIG, THEME_CONFIG, REFERENCE_CONFIG,
        POEM_CONFIG, ALL_CONFIGS,
    )
    from dev.builders.wiki_pages import (
        export_index,
        export_stats,
        export_timeline,
        export_analysis_report,
    )

    # Map entity names to configs
    config_map = {
        "people": PERSON_CONFIG,
        "locations": LOCATION_CONFIG,
        "cities": CITY_CONFIG,
        "entries": ENTRY_CONFIG,
        "events": EVENT_CONFIG,
        "tags": TAG_CONFIG,
        "themes": THEME_CONFIG,
        "references": REFERENCE_CONFIG,
        "poems": POEM_CONFIG,
    }

    logger: PalimpsestLogger = ctx.obj["logger"]
    wiki_path = Path(wiki_dir)

    db = PalimpsestDB(
        db_path=DB_PATH,
        alembic_dir=ALEMBIC_DIR,
        log_dir=LOG_DIR,
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )

    exporter = WikiExporter(db, wiki_path, logger)

    try:
        if entity_type == "index":
            click.echo(f"Exporting wiki homepage to {wiki_path}/index.md")
            status = export_index(db, wiki_path, MD_DIR, force, logger)
            click.echo(f"Index {status}")
        elif entity_type == "stats":
            click.echo(f"Exporting statistics dashboard to {wiki_path}/stats.md")
            status = export_stats(db, wiki_path, MD_DIR, force, logger)
            click.echo(f"Statistics {status}")
        elif entity_type == "timeline":
            click.echo(f"Exporting timeline to {wiki_path}/timeline.md")
            status = export_timeline(db, wiki_path, MD_DIR, force, logger)
            click.echo(f"Timeline {status}")
        elif entity_type == "analysis":
            click.echo(f"Exporting analysis report to {wiki_path}/analysis.md")
            status = export_analysis_report(db, wiki_path, MD_DIR, force, logger)
            click.echo(f"Analysis report {status}")
        elif entity_type == "all":
            click.echo(f"Exporting all entities to {wiki_path}/")
            stats = exporter.export_all(force)

            # Export special pages
            export_index(db, wiki_path, MD_DIR, force, logger)
            export_stats(db, wiki_path, MD_DIR, force, logger)
            export_timeline(db, wiki_path, MD_DIR, force, logger)
            export_analysis_report(db, wiki_path, MD_DIR, force, logger)

            click.echo(f"\nAll exports complete:")
            click.echo(f"  Created: {stats.created}")
            click.echo(f"  Updated: {stats.updated}")
            click.echo(f"  Unchanged: {stats.skipped}")
        else:
            config = config_map[entity_type]
            click.echo(f"Exporting {config.plural} to {wiki_path}/{config.folder}/")
            stats = exporter.export_entity_type(config, force)

            click.echo(f"\n{config.plural.title()} export complete:")
            click.echo(f"  Created: {stats.created}")
            click.echo(f"  Updated: {stats.updated}")
            click.echo(f"  Unchanged: {stats.skipped}")

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
