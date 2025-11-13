#!/usr/bin/env python3
"""
sql2wiki.py
-----------
Export database entities to Vimwiki pages.

REFACTORED: Now uses GenericEntityExporter for all entity types.
Reduced from ~2,600 lines to ~900 lines by eliminating repetitive export functions.

This pipeline converts structured database records into human-readable
vimwiki entity pages (people, themes, tags, entries, locations, cities, events).

Features:
- Generic export system (dev/pipeline/entity_exporter.py)
- Custom index builders for complex grouping
- Export all entity types
- Batch export with filtering
- Update existing files or create new ones

Usage:
    # Export specific entity type
    python -m dev.pipeline.sql2wiki export people
    python -m dev.pipeline.sql2wiki export entries
    python -m dev.pipeline.sql2wiki export locations

    # Export all entities
    python -m dev.pipeline.sql2wiki export all

    # Force regeneration
    python -m dev.pipeline.sql2wiki export all --force
"""
from __future__ import annotations

import sys
import click
from pathlib import Path
from typing import List, Optional
from collections import defaultdict
from itertools import groupby

from dev.pipeline.entity_exporter import (
    EntityConfig,
    GenericEntityExporter,
    register_entity,
    get_exporter,
    write_if_changed,
)

from dev.dataclasses.wiki_person import Person as WikiPerson
from dev.dataclasses.wiki_theme import Theme as WikiTheme
from dev.dataclasses.wiki_tag import Tag as WikiTag
from dev.dataclasses.wiki_poem import Poem as WikiPoem
from dev.dataclasses.wiki_reference import Reference as WikiReference
from dev.dataclasses.wiki_entry import Entry as WikiEntry
from dev.dataclasses.wiki_location import Location as WikiLocation
from dev.dataclasses.wiki_city import City as WikiCity
from dev.dataclasses.wiki_event import Event as WikiEvent

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

from dev.database.manager import PalimpsestDB
from dev.core.paths import LOG_DIR, DB_PATH, WIKI_DIR, MD_DIR, ALEMBIC_DIR, BACKUP_DIR
from dev.core.exceptions import Sql2WikiError
from dev.core.logging_manager import PalimpsestLogger, handle_cli_error
from dev.core.cli_utils import setup_logger
from dev.core.cli_stats import ConversionStats
from dev.utils.wiki import relative_link

from sqlalchemy import select

# Category ordering for people index
CATEGORY_ORDER = [
    "Family", "Friend", "Romantic", "Colleague",
    "Professional", "Acquaintance", "Public", "Main",
    "Secondary", "Archive", "Unsorted", "Unknown"
]


# ===== CUSTOM INDEX BUILDERS =====
# These are kept for entities that need complex grouping logic


def build_people_index(
    people: List[WikiPerson],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for people (groups by category).

    Args:
        people: List of WikiPerson instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building people index")

    # Group by category
    by_category = defaultdict(list)
    for person in people:
        category = person.category or "Unknown"
        by_category[category].append(person)

    # Build index lines
    lines = [
        "# Palimpsest — People",
        "",
        "Index of all people mentioned in the journal, organized by relationship category.",
        "",
    ]

    # Add each category in order
    for category in CATEGORY_ORDER:
        if category not in by_category:
            continue

        category_people = by_category[category]
        # Sort by mention count (descending), then alphabetically
        category_people.sort(key=lambda p: (-p.mentions, p.name.lower()))

        lines.extend(["", f"## {category}", ""])

        for person in category_people:
            rel_path = person.path.relative_to(wiki_dir)
            mention_str = f"{person.mentions} mention" + ("s" if person.mentions != 1 else "")
            lines.append(f"- [[{rel_path}|{person.name}]] ({mention_str})")

    # Add statistics
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- Total people: {len(people)}",
        f"- Categories: {len(by_category)}",
        "",
    ])

    # Write
    index_path = wiki_dir / "people.md"
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"People index {status}")
        else:
            logger.log_debug("People index unchanged")

    return status


def build_entries_index(
    entries: List[WikiEntry],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for entries (groups by year/month).

    Args:
        entries: List of WikiEntry instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building entries index")

    # Sort by date (descending - most recent first)
    sorted_entries = sorted(entries, key=lambda e: e.date, reverse=True)

    # Build index lines
    lines = [
        "# Palimpsest — Entries",
        "",
        "Chronological index of all journal entries.",
        "",
    ]

    # Group by year
    for year, year_entries in groupby(sorted_entries, key=lambda e: e.date.year):
        year_entries_list = list(year_entries)
        lines.extend([
            f"## {year}",
            "",
            f"**Total entries:** {len(year_entries_list)}",
            "",
        ])

        # Group by month within year
        for month, month_entries in groupby(year_entries_list, key=lambda e: e.date.month):
            month_entries_list = list(month_entries)
            month_name = month_entries_list[0].date.strftime("%B")

            lines.extend([f"### {month_name}", ""])

            for entry in month_entries_list:
                rel_path = entry.path.relative_to(wiki_dir)
                word_count_str = f"{entry.word_count} words" if entry.word_count else "no content"

                # Add entity count indicator
                entity_indicator = ""
                if entry.entity_count > 0:
                    entity_indicator = f" ({entry.entity_count} entities)"

                lines.append(
                    f"- [[{rel_path}|{entry.date.isoformat()}]] "
                    f"— {word_count_str}{entity_indicator}"
                )

            lines.append("")

    # Add statistics
    total_words = sum(e.word_count for e in sorted_entries)
    total_reading_time = sum(e.reading_time for e in sorted_entries)

    lines.extend([
        "---",
        "",
        "## Statistics",
        "",
        f"- Total entries: {len(sorted_entries)}",
        f"- Total words: {total_words:,}",
        f"- Total reading time: {total_reading_time:.1f} minutes ({total_reading_time/60:.1f} hours)",
        f"- Average words per entry: {total_words/len(sorted_entries):.0f}" if sorted_entries else "- Average words per entry: 0",
        "",
    ])

    # Write
    index_path = wiki_dir / "entries.md"
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"Entries index {status}")
        else:
            logger.log_debug("Entries index unchanged")

    return status


def build_locations_index(
    locations: List[WikiLocation],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for locations (groups by city).

    Args:
        locations: List of WikiLocation instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    index_path = wiki_dir / "locations.md"

    # Group locations by city
    locations_by_city = defaultdict(list)
    for loc in locations:
        locations_by_city[loc.city].append(loc)

    lines = [
        "# Palimpsest — Locations",
        "",
        "Geographic locations and venues visited.",
        "",
    ]

    # Statistics
    total_locations = len(locations)
    total_visits = sum(loc.visit_count for loc in locations)
    total_cities = len(locations_by_city)

    lines.extend([
        "## Statistics",
        "",
        f"- **Total Locations:** {total_locations}",
        f"- **Total Cities:** {total_cities}",
        f"- **Total Visits:** {total_visits}",
        "",
    ])

    # Locations by city
    lines.extend(["## Locations by City", ""])

    # Sort cities by total visits
    sorted_cities = sorted(
        locations_by_city.keys(),
        key=lambda city: sum(loc.visit_count for loc in locations_by_city[city]),
        reverse=True
    )

    for city in sorted_cities:
        city_locations = sorted(locations_by_city[city], key=lambda l: (-l.visit_count, l.name))
        total_city_visits = sum(loc.visit_count for loc in city_locations)

        lines.append(f"### {city} ({total_city_visits} visits)")
        lines.append("")

        for loc in city_locations:
            link = relative_link(index_path, loc.path)
            visit_str = f"{loc.visit_count} visit" + ("s" if loc.visit_count != 1 else "")
            lines.append(f"- [[{link}|{loc.name}]] ({visit_str})")

        lines.append("")

    # Most visited locations (top 20)
    lines.extend(["## Most Visited", ""])
    sorted_locations = sorted(locations, key=lambda l: (-l.visit_count, l.name))
    for loc in sorted_locations[:20]:
        link = relative_link(index_path, loc.path)
        visit_str = f"{loc.visit_count} visit" + ("s" if loc.visit_count != 1 else "")
        lines.append(f"- [[{link}|{loc.name}]] ({loc.city}) — {visit_str}")

    if len(sorted_locations) > 20:
        lines.append(f"- ... and {len(sorted_locations) - 20} more")

    lines.append("")

    # Write
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"Locations index {status}")
        else:
            logger.log_debug("Locations index unchanged")

    return status


def build_cities_index(
    cities: List[WikiCity],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for cities (groups by country).

    Args:
        cities: List of WikiCity instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    index_path = wiki_dir / "cities.md"

    lines = [
        "# Palimpsest — Cities",
        "",
        "Geographic regions where journal entries take place.",
        "",
    ]

    # Statistics
    total_cities = len(cities)
    total_entries = sum(city.entry_count for city in cities)
    total_locations = sum(city.location_count for city in cities)

    lines.extend([
        "## Statistics",
        "",
        f"- **Total Cities:** {total_cities}",
        f"- **Total Entries:** {total_entries}",
        f"- **Total Locations:** {total_locations}",
        "",
    ])

    # Group by country
    cities_by_country = defaultdict(list)
    for city in cities:
        country = city.country or "Unknown"
        cities_by_country[country].append(city)

    lines.extend(["## Cities by Country", ""])

    # Sort countries by total entries
    sorted_countries = sorted(
        cities_by_country.keys(),
        key=lambda country: sum(c.entry_count for c in cities_by_country[country]),
        reverse=True
    )

    for country in sorted_countries:
        country_cities = sorted(cities_by_country[country], key=lambda c: (-c.entry_count, c.name))
        total_country_entries = sum(c.entry_count for c in country_cities)

        lines.append(f"### {country} ({total_country_entries} entries)")
        lines.append("")

        for city in country_cities:
            link = relative_link(index_path, city.path)
            entry_str = f"{city.entry_count} entr" + ("ies" if city.entry_count != 1 else "y")
            loc_str = f"{city.location_count} location" + ("s" if city.location_count != 1 else "")
            lines.append(f"- [[{link}|{city.name}]] ({entry_str}, {loc_str})")

        lines.append("")

    # Most visited cities (top 20)
    lines.extend(["## Most Visited", ""])
    sorted_cities = sorted(cities, key=lambda c: (-c.entry_count, c.name))
    for city in sorted_cities[:20]:
        link = relative_link(index_path, city.path)
        entry_str = f"{city.entry_count} entr" + ("ies" if city.entry_count != 1 else "y")
        lines.append(f"- [[{link}|{city.name}]] ({city.country}) — {entry_str}")

    if len(sorted_cities) > 20:
        lines.append(f"- ... and {len(sorted_cities) - 20} more")

    lines.append("")

    # Write
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"Cities index {status}")
        else:
            logger.log_debug("Cities index unchanged")

    return status


def build_events_index(
    events: List[WikiEvent],
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for events (groups by manuscript status).

    Args:
        events: List of WikiEvent instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    index_path = wiki_dir / "events.md"

    lines = [
        "# Palimpsest — Events",
        "",
        "Narrative events and periods spanning multiple journal entries.",
        "",
    ]

    # Statistics
    total_events = len(events)
    total_entries = sum(event.entry_count for event in events)

    lines.extend([
        "## Statistics",
        "",
        f"- **Total Events:** {total_events}",
        f"- **Total Entries:** {total_entries}",
        "",
    ])

    # Events by manuscript status
    events_with_manuscript = [e for e in events if e.has_manuscript_metadata]

    if events_with_manuscript:
        lines.extend(["## Events with Manuscript Metadata", ""])

        # Group by status
        by_status = defaultdict(list)
        for event in events_with_manuscript:
            status = event.manuscript_status or "No Status"
            by_status[status].append(event)

        for status in sorted(by_status.keys()):
            status_events = sorted(by_status[status], key=lambda e: (-e.entry_count, e.display_name))
            lines.append(f"### {status}")
            lines.append("")

            for event in status_events:
                link = relative_link(index_path, event.path)
                entry_str = f"{event.entry_count} entr" + ("ies" if event.entry_count != 1 else "y")
                date_range = ""
                if event.start_date and event.end_date:
                    date_range = f" ({event.start_date.isoformat()} to {event.end_date.isoformat()})"
                lines.append(f"- [[{link}|{event.display_name}]] ({entry_str}){date_range}")

            lines.append("")

    # All events chronologically
    lines.extend(["## All Events", ""])
    sorted_events = sorted(
        [e for e in events if e.start_date],
        key=lambda e: e.start_date,
        reverse=True
    )

    for event in sorted_events:
        link = relative_link(index_path, event.path)
        entry_str = f"{event.entry_count} entr" + ("ies" if event.entry_count != 1 else "y")
        date_range = ""
        if event.start_date and event.end_date:
            if event.start_date == event.end_date:
                date_range = f" ({event.start_date.isoformat()})"
            else:
                date_range = f" ({event.start_date.isoformat()} to {event.end_date.isoformat()})"
        lines.append(f"- [[{link}|{event.display_name}]] ({entry_str}){date_range}")

    # Events without dates
    events_no_dates = [e for e in events if not e.start_date]
    if events_no_dates:
        lines.append("")
        lines.append("### Events without dates")
        lines.append("")
        for event in sorted(events_no_dates, key=lambda e: e.display_name):
            link = relative_link(index_path, event.path)
            entry_str = f"{event.entry_count} entr" + ("ies" if event.entry_count != 1 else "y")
            lines.append(f"- [[{link}|{event.display_name}]] ({entry_str})")

    lines.append("")

    # Write
    content = "\n".join(lines)
    status = write_if_changed(index_path, content, force)

    if logger:
        if status in ("created", "updated"):
            logger.log_info(f"Events index {status}")
        else:
            logger.log_debug("Events index unchanged")

    return status


# ===== TIMELINE (Special Case - Not an Entity) =====


def export_timeline(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export timeline/calendar view of all journal entries.

    Creates vimwiki/timeline.md with year-by-year and month-by-month
    breakdown of all entries.

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_operation("export_timeline_start", {"wiki_dir": str(wiki_dir)})

    timeline_path = wiki_dir / "timeline.md"

    with db.session_scope() as session:
        # Query all entries (no need for relationships, just dates)
        query = select(DBEntry).order_by(DBEntry.date)
        db_entries = session.execute(query).scalars().all()

        if not db_entries:
            if logger:
                logger.log_warning("No entries found for timeline")
            return "skipped"

        # Group entries by year and month
        entries_by_year = defaultdict(lambda: defaultdict(list))
        for entry in db_entries:
            year = entry.date.year
            month = entry.date.month
            entries_by_year[year][month].append(entry)

        lines = [
            "# Palimpsest — Timeline",
            "",
            "Chronological calendar view of all journal entries.",
            "",
        ]

        # Statistics
        total_entries = len(db_entries)
        total_years = len(entries_by_year)
        first_entry = db_entries[0].date
        last_entry = db_entries[-1].date
        span_days = (last_entry - first_entry).days

        lines.extend([
            "## Statistics",
            "",
            f"- **Total Entries:** {total_entries}",
            f"- **Time Span:** {total_years} years ({span_days} days)",
            f"- **First Entry:** {first_entry.isoformat()}",
            f"- **Last Entry:** {last_entry.isoformat()}",
            f"- **Average per Year:** {total_entries / total_years:.1f} entries",
            "",
        ])

        # Year-by-year timeline (most recent first)
        lines.extend(["## Timeline by Year", ""])

        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        for year in sorted(entries_by_year.keys(), reverse=True):
            year_entries = sum(len(entries) for entries in entries_by_year[year].values())
            lines.append(f"### {year} ({year_entries} entries)")
            lines.append("")

            # Month-by-month breakdown
            for month in range(1, 13):
                if month in entries_by_year[year]:
                    month_entries = entries_by_year[year][month]
                    month_name = month_names[month - 1]

                    lines.append(f"#### {month_name} {year} ({len(month_entries)} entries)")
                    lines.append("")

                    # List entries (most recent first)
                    for entry in reversed(month_entries):
                        entry_year = entry.date.year
                        entry_path = wiki_dir / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
                        entry_link = relative_link(timeline_path, entry_path)

                        word_str = f"{entry.word_count} words" if entry.word_count else "no content"
                        lines.append(f"- [[{entry_link}|{entry.date.isoformat()}]] — {word_str}")

                    lines.append("")

        # Write
        content = "\n".join(lines)
        status = write_if_changed(timeline_path, content, force)

        if logger:
            if status in ("created", "updated"):
                logger.log_info(f"Timeline {status}")
            else:
                logger.log_debug("Timeline unchanged")
            logger.log_operation("export_timeline_complete", {"status": status})

        return status


# ===== ENTITY REGISTRATION =====
# Register all entity types with their configurations


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
        "entries", "locations", "cities", "events", "timeline",
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
        if entity_type == "timeline":
            # Special case: timeline is not an entity
            click.echo(f"📤 Exporting timeline to {wiki_dir}/timeline.md")
            status = export_timeline(db, wiki_dir, journal_dir, force, logger)

            if status in ("created", "updated"):
                click.echo(f"\n✅ Timeline {status}")
            else:
                click.echo(f"\n⏭️  Timeline {status}")

        elif entity_type == "all":
            # Export all entity types
            click.echo(f"📤 Exporting all entities to {wiki_dir}/")

            all_stats = []
            for entity_name in ["entries", "locations", "cities", "events", "people", "themes", "tags", "poems", "references"]:
                exporter = get_exporter(entity_name)
                stats = exporter.export_all(db, wiki_dir, journal_dir, force, logger)
                all_stats.append(stats)

            # Export timeline
            export_timeline(db, wiki_dir, journal_dir, force, logger)

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
