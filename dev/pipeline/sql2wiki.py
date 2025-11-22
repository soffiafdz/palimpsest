#!/usr/bin/env python3
"""
sql2wiki.py
-----------
Export database entities to Vimwiki pages.

This pipeline orchestrates the export of structured database records into
human-readable vimwiki entity pages (people, themes, tags, entries, locations,
cities, events) and special pages (index, stats, timeline, analysis).

Uses builders from dev/builders/:
- wiki.py: GenericEntityExporter for entity export
- wiki_indexes.py: Custom index builders
- wiki_pages.py: Special page exports

Usage:
    # Export specific entity type
    python -m dev.pipeline.sql2wiki export people
    python -m dev.pipeline.sql2wiki export entries

    # Export all entities
    python -m dev.pipeline.sql2wiki export all

    # Export special pages
    python -m dev.pipeline.sql2wiki export index
    python -m dev.pipeline.sql2wiki export stats

    # Force regeneration
    python -m dev.pipeline.sql2wiki export all --force
"""
from __future__ import annotations

import click
from pathlib import Path

# Builder imports
from dev.builders.wiki import (
    EntityConfig,
    GenericEntityExporter,
    register_entity,
    get_exporter,
)
from dev.builders.wiki_indexes import (
    build_people_index,
    build_entries_index,
    build_locations_index,
    build_cities_index,
    build_events_index,
)
from dev.builders.wiki_pages import (
    export_entries_with_navigation,
    export_index,
    export_stats,
    export_timeline,
    export_analysis_report,
)

# Dataclass imports
from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_theme import Theme as WikiTheme
from dev.dataclasses.wiki_tag import Tag as WikiTag
from dev.dataclasses.wiki_poem import Poem as WikiPoem
from dev.dataclasses.wiki_reference import Reference as WikiReference
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.dataclasses.wiki_location import Location as WikiLocation
from dev.dataclasses.wiki_city import City as WikiCity
from dev.dataclasses.wiki_event import Event as WikiEvent

# Database model imports
from dev.database.models import (
    Person as DBPerson,
    Entry as DBEntry,
    Tag as DBTag,
    Poem as DBPoem,
    ReferenceSource as DBReferenceSource,
    Location as DBLocation,
    City as DBCity,
    Event as DBEvent,
)
from dev.database.models_manuscript import Theme as DBTheme

# Core imports
from dev.database.manager import PalimpsestDB
from dev.core.paths import LOG_DIR, DB_PATH, WIKI_DIR, MD_DIR, ALEMBIC_DIR, BACKUP_DIR
from dev.core.exceptions import Sql2WikiError
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.cli import setup_logger



def register_all_entities():
    """Register all entity configurations."""

    # People (custom index builder)
    register_entity("people", EntityConfig(
        name="person",
        plural="people",
        db_model=DBPerson,
        wiki_class=WikiPerson,
        output_subdir="people",
        index_filename="people.md",
        eager_loads=["entries", "manuscript"],
        index_builder=build_people_index,  # Custom
        sort_by="name",
        order_by="name",  # Use database column, not property
    ))

    # Themes (default index)
    register_entity("themes", EntityConfig(
        name="theme",
        plural="themes",
        db_model=DBTheme,
        wiki_class=WikiTheme,
        output_subdir="themes",
        index_filename="themes.md",
        eager_loads=["entries"],
        index_builder=None,  # Use default
        sort_by="name",
        order_by="theme",
    ))

    # Tags (default index)
    register_entity("tags", EntityConfig(
        name="tag",
        plural="tags",
        db_model=DBTag,
        wiki_class=WikiTag,
        output_subdir="tags",
        index_filename="tags.md",
        eager_loads=["entries"],
        index_builder=None,  # Use default
        sort_by="name",
        order_by="tag",
    ))

    # Poems (default index)
    register_entity("poems", EntityConfig(
        name="poem",
        plural="poems",
        db_model=DBPoem,
        wiki_class=WikiPoem,
        output_subdir="poems",
        index_filename="poems.md",
        eager_loads=["versions"],
        index_builder=None,  # Use default
        sort_by="title",
        order_by="title",
    ))

    # References (default index)
    register_entity("references", EntityConfig(
        name="reference",
        plural="references",
        db_model=DBReferenceSource,
        wiki_class=WikiReference,
        output_subdir="references",
        index_filename="references.md",
        eager_loads=["references"],
        index_builder=None,  # Use default
        sort_by="title",
        order_by="title",
    ))

    # Entries (custom index builder)
    register_entity("entries", EntityConfig(
        name="entry",
        plural="entries",
        db_model=DBEntry,
        wiki_class=WikiEntry,
        output_subdir="entries",
        index_filename="entries.md",
        eager_loads=[
            "dates",
            "cities",
            "locations.city",  # Nested load
            "people",
            "events",
            "tags",
            "poems",
            "references",
            "manuscript",
            "related_entries",
        ],
        index_builder=build_entries_index,  # Custom
        custom_export_all=export_entries_with_navigation,  # Custom export with prev/next navigation
        sort_by="date",
        order_by="date",
    ))

    # Locations (custom index builder)
    register_entity("locations", EntityConfig(
        name="location",
        plural="locations",
        db_model=DBLocation,
        wiki_class=WikiLocation,
        output_subdir="locations",
        index_filename="locations.md",
        eager_loads=[
            "city",
            "entries.people",  # Nested load
            "dates",
        ],
        index_builder=build_locations_index,  # Custom
        sort_by="name",
        order_by="name",
    ))

    # Cities (custom index builder)
    register_entity("cities", EntityConfig(
        name="city",
        plural="cities",
        db_model=DBCity,
        wiki_class=WikiCity,
        output_subdir="cities",
        index_filename="cities.md",
        eager_loads=[
            "entries",
            "locations",
        ],
        index_builder=build_cities_index,  # Custom
        sort_by="name",
        order_by="city",
    ))

    # Events (custom index builder)
    register_entity("events", EntityConfig(
        name="event",
        plural="events",
        db_model=DBEvent,
        wiki_class=WikiEvent,
        output_subdir="events",
        index_filename="events.md",
        eager_loads=[
            "entries",
            "people",
            "manuscript",
        ],
        index_builder=build_events_index,  # Custom
        sort_by="display_name",
        order_by="event",
    ))


# Register all entities on module import
register_all_entities()


# ===== CLI =====


@click.group()
@click.option(
    "--db-path",
    type=click.Path(),
    default=str(DB_PATH),
    help="Path to database file",
)
@click.option(
    "--wiki-dir",
    type=click.Path(),
    default=str(WIKI_DIR),
    help="Vimwiki root directory",
)
@click.option(
    "--journal-dir",
    type=click.Path(),
    default=str(MD_DIR),
    help="Journal entries directory",
)
@click.option(
    "--log-dir",
    type=click.Path(),
    default=str(LOG_DIR),
    help="Logging directory",
)
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose logging")
@click.pass_context
def cli(
    ctx: click.Context,
    db_path: str,
    wiki_dir: str,
    journal_dir: str,
    log_dir: str,
    verbose: bool,
) -> None:
    """Export database entities to vimwiki pages."""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    ctx.obj["wiki_dir"] = Path(wiki_dir)
    ctx.obj["journal_dir"] = Path(journal_dir)
    ctx.obj["log_dir"] = Path(log_dir)
    ctx.obj["verbose"] = verbose
    ctx.obj["logger"] = setup_logger(Path(log_dir), "sql2wiki")

    # Initialize database
    ctx.obj["db"] = PalimpsestDB(
        db_path=Path(db_path),
        alembic_dir=ALEMBIC_DIR,
        log_dir=Path(log_dir),
        backup_dir=BACKUP_DIR,
        enable_auto_backup=False,
    )


@cli.command()
@click.argument(
    "entity_type",
    type=click.Choice([
        "entries", "locations", "cities", "events", "timeline", "index", "stats", "analysis",
        "people", "themes", "tags", "poems", "references",
        "all"
    ]),
)
@click.option("-f", "--force", is_flag=True, help="Force regenerate all files")
@click.pass_context
def export(ctx: click.Context, entity_type: str, force: bool) -> None:
    """Export database entities to vimwiki pages."""
    logger: PalimpsestLogger = ctx.obj["logger"]
    db: PalimpsestDB = ctx.obj["db"]
    wiki_dir: Path = ctx.obj["wiki_dir"]
    journal_dir: Path = ctx.obj["journal_dir"]

    try:
        if entity_type == "index":
            # Special case: homepage/index is not an entity
            click.echo(f"📤 Exporting wiki homepage to {wiki_dir}/index.md")
            status = export_index(db, wiki_dir, journal_dir, force, logger)

            if status in ("created", "updated"):
                click.echo(f"\n✅ Index {status}")
            else:
                click.echo(f"\n⏭️  Index {status}")

        elif entity_type == "stats":
            # Special case: statistics dashboard is not an entity
            click.echo(f"📤 Exporting statistics dashboard to {wiki_dir}/stats.md")
            status = export_stats(db, wiki_dir, journal_dir, force, logger)

            if status in ("created", "updated"):
                click.echo(f"\n✅ Statistics {status}")
            else:
                click.echo(f"\n⏭️  Statistics {status}")

        elif entity_type == "timeline":
            # Special case: timeline is not an entity
            click.echo(f"📤 Exporting timeline to {wiki_dir}/timeline.md")
            status = export_timeline(db, wiki_dir, journal_dir, force, logger)

            if status in ("created", "updated"):
                click.echo(f"\n✅ Timeline {status}")
            else:
                click.echo(f"\n⏭️  Timeline {status}")

        elif entity_type == "analysis":
            # Special case: analysis report is not an entity
            click.echo(f"📤 Exporting analysis report to {wiki_dir}/analysis.md")
            status = export_analysis_report(db, wiki_dir, journal_dir, force, logger)

            if status in ("created", "updated"):
                click.echo(f"\n✅ Analysis report {status}")
            else:
                click.echo(f"\n⏭️  Analysis report {status}")

        elif entity_type == "all":
            # Export all entity types
            click.echo(f"📤 Exporting all entities to {wiki_dir}/")

            all_stats = []
            for entity_name in ["entries", "locations", "cities", "events", "people", "themes", "tags", "poems", "references"]:
                exporter = get_exporter(entity_name)
                stats = exporter.export_all(db, wiki_dir, journal_dir, force, logger)
                all_stats.append(stats)

            # Export index (homepage)
            export_index(db, wiki_dir, journal_dir, force, logger)

            # Export statistics dashboard
            export_stats(db, wiki_dir, journal_dir, force, logger)

            # Export timeline
            export_timeline(db, wiki_dir, journal_dir, force, logger)

            # Export analysis report
            export_analysis_report(db, wiki_dir, journal_dir, force, logger)

            # Combined stats
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
            # Export single entity type using generic exporter
            exporter = get_exporter(entity_type)
            click.echo(f"📤 Exporting {exporter.config.plural} to {wiki_dir}/{exporter.config.output_subdir}/")

            stats = exporter.export_all(db, wiki_dir, journal_dir, force, logger)

            click.echo(f"\n✅ {exporter.config.plural.title()} export complete:")
            click.echo(f"  Files processed: {stats.files_processed}")
            click.echo(f"  Created: {stats.entries_created}")
            click.echo(f"  Updated: {stats.entries_updated}")
            click.echo(f"  Skipped: {stats.entries_skipped}")
            if stats.errors > 0:
                click.echo(f"  ⚠️  Errors: {stats.errors}")
            click.echo(f"  Duration: {stats.duration():.2f}s")

    except (Sql2WikiError, Exception) as e:
        handle_cli_error(ctx, e, "export", {"entity_type": entity_type})


if __name__ == "__main__":
    cli(obj={})
