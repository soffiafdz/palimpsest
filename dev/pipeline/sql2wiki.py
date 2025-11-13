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
from sqlalchemy.orm import joinedload

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


# ===== CUSTOM EXPORT FUNCTIONS =====


def export_entries_with_navigation(
    exporter: GenericEntityExporter,
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> ConversionStats:
    """
    Custom export function for entries that includes prev/next navigation.

    This function exports all entries with chronological navigation links,
    allowing readers to navigate between entries sequentially.

    Args:
        exporter: The GenericEntityExporter instance
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory
        force: Force write all files
        logger: Optional logger

    Returns:
        ConversionStats with results
    """
    stats = ConversionStats()

    if logger:
        logger.log_operation("export_entries_start", {"wiki_dir": str(wiki_dir)})

    with db.session_scope() as session:
        # Query all entries sorted by date
        query = select(DBEntry)

        # Add eager loads
        for load_path in exporter.config.eager_loads:
            if "." in load_path:
                parts = load_path.split(".")
                attr = getattr(DBEntry, parts[0])
                load = joinedload(attr)
                for part in parts[1:]:
                    load = load.joinedload(getattr(attr.property.mapper.class_, part))
                query = query.options(load)
            else:
                query = query.options(joinedload(getattr(DBEntry, load_path)))

        # Order by date
        query = query.order_by(DBEntry.date)

        # Execute query
        db_entries = session.execute(query).scalars().unique().all()

        if not db_entries:
            if logger:
                logger.log_warning("No entries found in database")
            return stats

        if logger:
            logger.log_info(f"Found {len(db_entries)} entries in database")

        # Export each entry with prev/next navigation
        wiki_entities = []
        for i, db_entry in enumerate(db_entries):
            stats.files_processed += 1

            try:
                # Get prev/next entries
                prev_entry = db_entries[i - 1] if i > 0 else None
                next_entry = db_entries[i + 1] if i < len(db_entries) - 1 else None

                # Convert to wiki entity with navigation
                wiki_entry = WikiEntry.from_database(
                    db_entry, wiki_dir, journal_dir, prev_entry, next_entry
                )

                # Ensure output directory exists
                wiki_entry.path.parent.mkdir(parents=True, exist_ok=True)

                # Generate wiki content
                content = "\n".join(wiki_entry.to_wiki())

                # Write if changed
                status = write_if_changed(wiki_entry.path, content, force)

                if status == "created":
                    stats.entries_created += 1
                elif status == "updated":
                    stats.entries_updated += 1
                elif status == "skipped":
                    stats.entries_skipped += 1

                if logger:
                    logger.log_debug(f"entry {wiki_entry.date}: {status}")

                wiki_entities.append(wiki_entry)

            except Exception as e:
                stats.errors += 1
                if logger:
                    logger.log_error(e, {
                        "operation": "export_entry",
                        "entity": str(db_entry)
                    })

        # Build index
        if exporter.config.index_builder:
            index_status = exporter.config.index_builder(
                wiki_entities, wiki_dir, force, logger
            )
        else:
            index_status = exporter.build_index(
                wiki_entities, wiki_dir, force, logger
            )

    return stats


# ===== INDEX/HOMEPAGE (Special Case - Not an Entity) =====


def export_index(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export wiki homepage (index.md) with navigation and statistics.

    Creates vimwiki/index.md as the central navigation hub with:
    - Quick navigation to all entity indexes
    - Statistics summary
    - Recent activity

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory (unused but kept for consistency)
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_operation("export_index_start", {"wiki_dir": str(wiki_dir)})

    index_path = wiki_dir / "index.md"

    with db.session_scope() as session:
        # Gather statistics from database
        from sqlalchemy import func

        # Entry statistics
        entries_query = select(DBEntry).order_by(DBEntry.date.desc())
        all_entries = session.execute(entries_query).scalars().all()
        total_entries = len(all_entries)
        total_words = sum(e.word_count for e in all_entries)

        first_date = all_entries[-1].date if all_entries else None
        last_date = all_entries[0].date if all_entries else None
        span_days = (last_date - first_date).days if (first_date and last_date) else 0

        # People statistics
        people_query = select(DBPerson).order_by(func.count(DBEntry.id).desc())
        all_people = session.execute(select(DBPerson)).scalars().all()
        total_people = len(all_people)

        # Count categories (using relation_type)
        categories = set(p.relation_type for p in all_people if p.relation_type)
        total_categories = len(categories)

        # Entity counts
        total_tags = session.execute(select(func.count(DBTag.id))).scalar()
        total_poems = session.execute(select(func.count(DBPoem.id))).scalar()
        total_references = session.execute(select(func.count(DBReferenceSource.id))).scalar()
        total_locations = session.execute(select(func.count(DBLocation.id))).scalar()
        total_cities = session.execute(select(func.count(DBCity.id))).scalar()
        total_events = session.execute(select(func.count(DBEvent.id))).scalar()

        # Note: Themes are in models_manuscript, need different import
        total_themes = session.execute(select(func.count(DBTheme.id))).scalar()

        # Build homepage content
        lines = [
            "# Palimpsest — Metadata Wiki",
            "",
            "Welcome to the Palimpsest metadata wiki for manuscript development.",
            "",
            "## Quick Navigation",
            "",
            "### Content",
        ]

        # Entry navigation
        entry_span = ""
        if total_entries > 0 and first_date and last_date:
            entry_span = f" — {total_entries} entries spanning {span_days} days"
        elif total_entries > 0:
            entry_span = f" — {total_entries} entries"

        lines.append(f"- [[entries.md|Journal Entries]]{entry_span}")
        lines.append("- [[timeline.md|Timeline]] — Calendar view by year/month")
        lines.append("- [[stats.md|Statistics Dashboard]] — Analytics and insights")
        lines.append("- [[analysis.md|Analysis Report]] — Entity relationships and patterns")
        lines.append("")

        # People & Places
        lines.append("### People & Places")
        people_desc = f" — {total_people} " + ("person" if total_people == 1 else "people")
        if total_categories > 0:
            people_desc += f" across {total_categories} " + ("category" if total_categories == 1 else "categories")
        lines.append(f"- [[people.md|People]]{people_desc}")

        if total_locations > 0:
            loc_desc = f" — {total_locations} location" + ("s" if total_locations != 1 else "")
        else:
            loc_desc = " — (empty)"
        lines.append(f"- [[locations.md|Locations]]{loc_desc}")

        if total_cities > 0:
            city_desc = f" — {total_cities} " + ("city" if total_cities == 1 else "cities")
        else:
            city_desc = " — (empty)"
        lines.append(f"- [[cities.md|Cities]]{city_desc}")
        lines.append("")

        # Narrative Elements
        lines.append("### Narrative Elements")

        if total_events > 0:
            event_desc = f" — {total_events} event" + ("s" if total_events != 1 else "")
        else:
            event_desc = " — (empty)"
        lines.append(f"- [[events.md|Events]]{event_desc}")

        if total_themes > 0:
            theme_desc = f" — {total_themes} theme" + ("s" if total_themes != 1 else "")
        else:
            theme_desc = " — (empty)"
        lines.append(f"- [[themes.md|Themes]]{theme_desc}")

        if total_tags > 0:
            tag_desc = f" — {total_tags} tag" + ("s" if total_tags != 1 else "")
        else:
            tag_desc = " — (empty)"
        lines.append(f"- [[tags.md|Tags]]{tag_desc}")
        lines.append("")

        # Creative Work
        lines.append("### Creative Work")

        if total_poems > 0:
            poem_desc = f" — {total_poems} poem" + ("s" if total_poems != 1 else "")
        else:
            poem_desc = " — (empty)"
        lines.append(f"- [[poems.md|Poems]]{poem_desc}")

        if total_references > 0:
            ref_desc = f" — {total_references} reference" + ("s" if total_references != 1 else "")
        else:
            ref_desc = " — (empty)"
        lines.append(f"- [[references.md|References]]{ref_desc}")
        lines.append("")

        # Statistics
        lines.extend([
            "## Statistics",
            "",
            f"- **Total Entries:** {total_entries}",
        ])

        if first_date and last_date:
            lines.append(f"- **Date Range:** {first_date.isoformat()} to {last_date.isoformat()}")

        if total_words > 0:
            avg_words = total_words // total_entries if total_entries > 0 else 0
            lines.append(f"- **Total Words:** {total_words:,}")
            lines.append(f"- **Average Words per Entry:** {avg_words}")

        lines.extend([
            f"- **People Mentioned:** {total_people}",
            f"- **Active Tags:** {total_tags}",
            "",
        ])

        # Recent Activity
        if total_entries > 0:
            lines.extend([
                "## Recent Activity",
                "",
                "### Latest Entries",
                "",
            ])

            # Show last 5 entries
            for entry in all_entries[:5]:
                entry_year = entry.date.year
                entry_path = wiki_dir / "entries" / str(entry_year) / f"{entry.date.isoformat()}.md"
                entry_link = relative_link(index_path, entry_path)
                word_str = f"{entry.word_count} words" if entry.word_count else "no content"
                lines.append(f"- [[{entry_link}|{entry.date.isoformat()}]] — {word_str}")

            lines.append("")

        # Most mentioned people
        if total_people > 0:
            lines.extend([
                "### Most Mentioned People",
                "",
            ])

            # Get people sorted by mention count
            people_with_mentions = [(p, len(p.entries)) for p in all_people]
            people_with_mentions.sort(key=lambda x: (-x[1], x[0].name))

            # Show top 5
            for person, mention_count in people_with_mentions[:5]:
                if mention_count > 0:
                    person_path = wiki_dir / "people" / f"{person.display_name.lower().replace(' ', '_')}.md"
                    person_link = relative_link(index_path, person_path)
                    category = f" ({person.relationship_display.lower()})" if person.relation_type else ""
                    mention_str = f"{mention_count} mention" + ("s" if mention_count != 1 else "")
                    lines.append(f"- [[{person_link}|{person.display_name}]] — {mention_str}{category}")

            lines.append("")

        # Write
        content = "\n".join(lines)
        status = write_if_changed(index_path, content, force)

        if logger:
            if status in ("created", "updated"):
                logger.log_info(f"Index {status}")
            else:
                logger.log_debug("Index unchanged")
            logger.log_operation("export_index_complete", {"status": status})

        return status


# ===== STATISTICS DASHBOARD (Special Case - Not an Entity) =====


def export_stats(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export statistics dashboard (stats.md) with comprehensive analytics.

    Creates vimwiki/stats.md with:
    - Writing statistics (words, frequency, streaks)
    - People network (mentions, relationships)
    - Geographic coverage (locations, cities)
    - Thematic analysis (themes, tags)
    - Timeline analysis (entry frequency)
    - ASCII visualizations

    Args:
        db: Database manager
        wiki_dir: Vimwiki root directory
        journal_dir: Journal entries directory (unused but kept for consistency)
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_operation("export_stats_start", {"wiki_dir": str(wiki_dir)})

    stats_path = wiki_dir / "stats.md"

    with db.session_scope() as session:
        from sqlalchemy import func
        from datetime import datetime
        from collections import Counter

        # Entry statistics
        entries_query = select(DBEntry).order_by(DBEntry.date)
        all_entries = session.execute(entries_query).scalars().all()
        total_entries = len(all_entries)

        if total_entries == 0:
            if logger:
                logger.log_warning("No entries found for statistics")
            return "skipped"

        total_words = sum(e.word_count for e in all_entries)
        avg_words = total_words // total_entries if total_entries > 0 else 0

        first_date = all_entries[0].date
        last_date = all_entries[-1].date
        span_days = (last_date - first_date).days

        # People statistics
        all_people = session.execute(select(DBPerson)).scalars().all()
        total_people = len(all_people)

        # Tag statistics
        all_tags = session.execute(select(DBTag)).scalars().all()
        total_tags = len(all_tags)

        # Location statistics
        total_locations = session.execute(select(func.count(DBLocation.id))).scalar()
        total_cities = session.execute(select(func.count(DBCity.id))).scalar()

        # Event statistics
        total_events = session.execute(select(func.count(DBEvent.id))).scalar()

        # Theme statistics
        total_themes = session.execute(select(func.count(DBTheme.id))).scalar()

        # Build statistics dashboard
        lines = [
            "# Palimpsest — Statistics Dashboard",
            "",
            "Comprehensive analytics and insights from your journal.",
            "",
        ]

        # ===== Writing Activity =====
        lines.extend([
            "## Writing Activity",
            "",
            "### Overview",
            "",
            f"- **Total Entries:** {total_entries}",
            f"- **Total Words:** {total_words:,}",
            f"- **Average Words per Entry:** {avg_words}",
            f"- **Date Range:** {first_date.isoformat()} to {last_date.isoformat()}",
            f"- **Span:** {span_days} days",
            "",
        ])

        # Entry frequency by month (last 12 months)
        lines.extend([
            "### Entry Frequency (Last 12 Months)",
            "",
        ])

        # Group entries by year-month
        entries_by_month = defaultdict(int)
        for entry in all_entries:
            month_key = f"{entry.date.year}-{entry.date.month:02d}"
            entries_by_month[month_key] += 1

        # Get last 12 months
        from datetime import date
        current_month = date.today().replace(day=1)
        months = []
        for i in range(12):
            month_date = date(current_month.year, current_month.month, 1)
            if i > 0:
                # Go back i months
                month = current_month.month - i
                year = current_month.year
                while month <= 0:
                    month += 12
                    year -= 1
                month_date = date(year, month, 1)
            months.append(month_date)

        months.reverse()  # Oldest first

        # ASCII bar chart
        max_count = max(entries_by_month.values()) if entries_by_month else 1
        for month_date in months:
            month_key = f"{month_date.year}-{month_date.month:02d}"
            count = entries_by_month.get(month_key, 0)
            bar_length = int((count / max_count) * 20) if max_count > 0 else 0
            bar = "█" * bar_length if bar_length > 0 else "░"
            month_name = month_date.strftime("%b %Y")
            lines.append(f"{month_name:12s} {bar:20s} ({count})")

        lines.append("")

        # Word count distribution
        lines.extend([
            "### Word Count Distribution",
            "",
        ])

        # Group by word count ranges
        word_ranges = {
            "0-100": 0,
            "101-250": 0,
            "251-500": 0,
            "501-1000": 0,
            "1000+": 0,
        }

        for entry in all_entries:
            wc = entry.word_count
            if wc == 0:
                word_ranges["0-100"] += 1
            elif wc <= 100:
                word_ranges["0-100"] += 1
            elif wc <= 250:
                word_ranges["101-250"] += 1
            elif wc <= 500:
                word_ranges["251-500"] += 1
            elif wc <= 1000:
                word_ranges["501-1000"] += 1
            else:
                word_ranges["1000+"] += 1

        # ASCII bar chart
        max_range_count = max(word_ranges.values())
        for range_name, count in word_ranges.items():
            if max_range_count > 0:
                bar_length = int((count / max_range_count) * 20)
                bar = "█" * bar_length if bar_length > 0 else "░"
                pct = (count / total_entries) * 100 if total_entries > 0 else 0
                lines.append(f"{range_name:12s} {bar:20s} {count:3d} ({pct:.1f}%)")

        lines.append("")

        # ===== People Network =====
        lines.extend([
            "## People Network",
            "",
            f"**Total People:** {total_people}",
            "",
        ])

        if total_people > 0:
            # Most mentioned people
            people_with_counts = [(p, len(p.entries)) for p in all_people]
            people_with_counts.sort(key=lambda x: (-x[1], x[0].name))

            lines.extend([
                "### Most Mentioned People (Top 10)",
                "",
            ])

            for person, count in people_with_counts[:10]:
                if count > 0:
                    category = person.relationship_display if person.relation_type else "Unknown"
                    lines.append(f"- **{person.display_name}** — {count} mentions ({category})")

            lines.append("")

            # Relationship distribution
            lines.extend([
                "### Relationship Distribution",
                "",
            ])

            relation_counts = Counter()
            for person in all_people:
                if person.relation_type:
                    relation_counts[person.relationship_display] += 1
                else:
                    relation_counts["Unknown"] += 1

            # ASCII bar chart
            max_relation_count = max(relation_counts.values()) if relation_counts else 1
            for relation, count in relation_counts.most_common():
                bar_length = int((count / max_relation_count) * 20)
                bar = "█" * bar_length
                pct = (count / total_people) * 100 if total_people > 0 else 0
                lines.append(f"{relation:15s} {bar:20s} {count:3d} ({pct:.1f}%)")

            lines.append("")

        # ===== Geographic Coverage =====
        lines.extend([
            "## Geographic Coverage",
            "",
            f"- **Total Locations:** {total_locations}",
            f"- **Total Cities:** {total_cities}",
            "",
        ])

        # ===== Thematic Analysis =====
        lines.extend([
            "## Thematic Analysis",
            "",
            f"- **Total Themes:** {total_themes}",
            f"- **Total Tags:** {total_tags}",
            "",
        ])

        if total_tags > 0:
            # Tag usage
            tags_with_counts = [(t, len(t.entries)) for t in all_tags]
            tags_with_counts.sort(key=lambda x: (-x[1], x[0].tag))

            lines.extend([
                "### Most Used Tags",
                "",
            ])

            for tag, count in tags_with_counts[:10]:
                if count > 0:
                    lines.append(f"- **{tag.tag}** — {count} entries")

            lines.append("")

        # ===== Events =====
        lines.extend([
            "## Events",
            "",
            f"- **Total Events:** {total_events}",
            "",
        ])

        # ===== Timeline Heatmap =====
        lines.extend([
            "## Timeline Heatmap",
            "",
            "Entry frequency by year:",
            "",
        ])

        # Group by year
        entries_by_year = defaultdict(int)
        for entry in all_entries:
            entries_by_year[entry.date.year] += 1

        # Yearly breakdown
        for year in sorted(entries_by_year.keys()):
            count = entries_by_year[year]
            max_year_count = max(entries_by_year.values())
            bar_length = int((count / max_year_count) * 30) if max_year_count > 0 else 0
            bar = "█" * bar_length
            lines.append(f"{year}: {bar} ({count} entries)")

        lines.append("")

        # ===== Summary =====
        lines.extend([
            "## Summary",
            "",
            "### Entity Counts",
            "",
            f"| Entity | Count |",
            f"|--------|-------|",
            f"| Entries | {total_entries} |",
            f"| People | {total_people} |",
            f"| Locations | {total_locations} |",
            f"| Cities | {total_cities} |",
            f"| Events | {total_events} |",
            f"| Themes | {total_themes} |",
            f"| Tags | {total_tags} |",
            "",
            "### Writing Metrics",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Words | {total_words:,} |",
            f"| Average Words/Entry | {avg_words} |",
            f"| Entries per Day | {total_entries/max(span_days, 1):.2f} |",
            f"| Days Active | {span_days} |",
            "",
        ])

        # Write
        content = "\n".join(lines)
        status = write_if_changed(stats_path, content, force)

        if logger:
            if status in ("created", "updated"):
                logger.log_info(f"Statistics dashboard {status}")
            else:
                logger.log_debug("Statistics dashboard unchanged")
            logger.log_operation("export_stats_complete", {"status": status})

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


def export_analysis_report(
    db: PalimpsestDB,
    wiki_dir: Path,
    journal_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Export comprehensive analysis report with visualizations.

    Creates wiki/analysis.md with:
    - Entity relationship network analysis
    - Activity patterns over time
    - Connection statistics
    - Temporal heatmaps (ASCII art)
    - Most active periods and people

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
        logger.log_operation("export_analysis_start", {"wiki_dir": str(wiki_dir)})

    analysis_path = wiki_dir / "analysis.md"

    with db.session_scope() as session:
        # Query all entries with relationships
        query = (
            select(DBEntry)
            .options(
                joinedload(DBEntry.people),
                joinedload(DBEntry.locations),
                joinedload(DBEntry.cities),
                joinedload(DBEntry.events),
                joinedload(DBEntry.tags),
            )
            .order_by(DBEntry.date)
        )
        db_entries = session.execute(query).unique().scalars().all()

        if not db_entries:
            if logger:
                logger.log_warning("No entries found for analysis")
            return "skipped"

        # Collect statistics
        from collections import Counter
        from datetime import datetime

        # Entity counters
        person_counter = Counter()
        location_counter = Counter()
        city_counter = Counter()
        event_counter = Counter()
        tag_counter = Counter()

        # Temporal data
        entries_by_month = defaultdict(int)
        entries_by_year = defaultdict(int)
        entries_by_dow = defaultdict(int)  # day of week
        word_count_by_year = defaultdict(int)

        # Relationship co-occurrence
        person_colocation = defaultdict(lambda: defaultdict(int))  # person -> city -> count

        for entry in db_entries:
            # Count entities
            for person in entry.people:
                person_counter[person.display_name] += 1

            for location in entry.locations:
                location_counter[location.name] += 1

            for city in entry.cities:
                city_counter[city.city] += 1

            for event in entry.events:
                event_counter[event.display_name] += 1

            for tag in entry.tags:
                tag_counter[tag.tag] += 1

            # Temporal patterns
            entries_by_year[entry.date.year] += 1
            entries_by_month[f"{entry.date.year}-{entry.date.month:02d}"] += 1
            entries_by_dow[entry.date.strftime("%A")] += 1
            word_count_by_year[entry.date.year] += entry.word_count or 0

            # Co-location analysis
            for person in entry.people:
                for city in entry.cities:
                    person_colocation[person.display_name][city.city] += 1

        lines = [
            "# Palimpsest — Analysis Report",
            "",
            "Comprehensive analysis of journal entities, relationships, and patterns.",
            "",
            "---",
            "",
        ]

        # === OVERVIEW ===
        total_entries = len(db_entries)
        total_people = len(person_counter)
        total_locations = len(location_counter)
        total_cities = len(city_counter)
        total_events = len(event_counter)
        total_tags = len(tag_counter)
        total_words = sum(e.word_count or 0 for e in db_entries)

        lines.extend([
            "## Overview",
            "",
            f"| Metric | Count |",
            f"| --- | --- |",
            f"| **Total Entries** | {total_entries} |",
            f"| **Unique People** | {total_people} |",
            f"| **Unique Locations** | {total_locations} |",
            f"| **Unique Cities** | {total_cities} |",
            f"| **Events** | {total_events} |",
            f"| **Tags** | {total_tags} |",
            f"| **Total Words** | {total_words:,} |",
            f"| **Average Words/Entry** | {total_words / total_entries if total_entries > 0 else 0:.0f} |",
            "",
        ])

        # === ACTIVITY PATTERNS ===
        lines.extend([
            "## Activity Patterns",
            "",
            "### Entries by Year",
            "",
        ])

        # ASCII bar chart for entries by year
        max_year_count = max(entries_by_year.values()) if entries_by_year else 1
        for year in sorted(entries_by_year.keys()):
            count = entries_by_year[year]
            bar_length = int((count / max_year_count) * 50)
            bar = "█" * bar_length
            lines.append(f"{year}: {bar} {count} entries ({word_count_by_year[year]:,} words)")
        lines.append("")

        # === TOP ENTITIES ===
        lines.extend([
            "## Most Mentioned Entities",
            "",
            "### Top 10 People",
            "",
        ])

        for person, count in person_counter.most_common(10):
            person_slug = person.lower().replace(" ", "_")
            person_path = wiki_dir / "people" / f"{person_slug}.md"
            person_link = relative_link(analysis_path, person_path)
            lines.append(f"{count:3d}× [[{person_link}|{person}]]")
        lines.append("")

        lines.extend([
            "### Top 10 Locations",
            "",
        ])

        for location, count in location_counter.most_common(10):
            lines.append(f"{count:3d}× {location}")
        lines.append("")

        lines.extend([
            "### Top 10 Cities",
            "",
        ])

        for city, count in city_counter.most_common(10):
            city_slug = city.lower().replace(" ", "_")
            city_path = wiki_dir / "cities" / f"{city_slug}.md"
            city_link = relative_link(analysis_path, city_path)
            lines.append(f"{count:3d}× [[{city_link}|{city}]]")
        lines.append("")

        lines.extend([
            "### Top 15 Tags",
            "",
        ])

        for tag, count in tag_counter.most_common(15):
            tag_slug = tag.lower().replace(" ", "_")
            tag_path = wiki_dir / "tags" / f"{tag_slug}.md"
            tag_link = relative_link(analysis_path, tag_path)
            lines.append(f"{count:3d}× [[{tag_link}|#{tag}]]")
        lines.append("")

        # === DAY OF WEEK ANALYSIS ===
        lines.extend([
            "## Temporal Patterns",
            "",
            "### Entries by Day of Week",
            "",
        ])

        dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        max_dow_count = max(entries_by_dow.values()) if entries_by_dow else 1
        for dow in dow_order:
            count = entries_by_dow.get(dow, 0)
            bar_length = int((count / max_dow_count) * 40)
            bar = "█" * bar_length
            lines.append(f"{dow:9s}: {bar} {count}")
        lines.append("")

        # === RELATIONSHIP ANALYSIS ===
        lines.extend([
            "## Relationship Networks",
            "",
            "### People-City Co-occurrences",
            "",
            "Top people and their most frequent cities:",
            "",
        ])

        # Show top 5 people and their city associations
        for person, _ in person_counter.most_common(5):
            if person in person_colocation:
                cities = person_colocation[person]
                top_cities = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:3]
                city_str = ", ".join([f"{city} ({count}×)" for city, count in top_cities])

                person_slug = person.lower().replace(" ", "_")
                person_path = wiki_dir / "people" / f"{person_slug}.md"
                person_link = relative_link(analysis_path, person_path)

                lines.append(f"- **[[{person_link}|{person}]]**: {city_str}")
        lines.append("")

        # === MONTHLY HEATMAP ===
        lines.extend([
            "## Activity Heatmap",
            "",
            "### Monthly Activity (Last 12 Months)",
            "",
        ])

        # Get last 12 months
        if db_entries:
            last_date = db_entries[-1].date
            import calendar

            months_list = []
            for i in range(11, -1, -1):
                year = last_date.year
                month = last_date.month - i
                if month <= 0:
                    year -= 1
                    month += 12
                month_key = f"{year}-{month:02d}"
                months_list.append((month_key, year, month))

            for month_key, year, month in months_list:
                count = entries_by_month.get(month_key, 0)
                # Create intensity indicator
                if count == 0:
                    intensity = "░░░"
                elif count <= 2:
                    intensity = "▒▒▒"
                elif count <= 5:
                    intensity = "▓▓▓"
                else:
                    intensity = "███"

                month_name = calendar.month_abbr[month]
                lines.append(f"{year}-{month:02d} ({month_name}): {intensity} {count} entries")
            lines.append("")

        # === NAVIGATION ===
        lines.extend([
            "---",
            "",
            "## See Also",
            "",
            "- [[index.md|Home]]",
            "- [[stats.md|Statistics Dashboard]]",
            "- [[timeline.md|Timeline View]]",
            "- [[people.md|All People]]",
            "- [[cities.md|All Cities]]",
            "- [[tags.md|All Tags]]",
            "",
        ])

        # Write
        content = "\n".join(lines)
        status = write_if_changed(analysis_path, content, force)

        if logger:
            if status in ("created", "updated"):
                logger.log_info(f"Analysis report {status}")
            else:
                logger.log_debug("Analysis report unchanged")
            logger.log_operation("export_analysis_complete", {"status": status})

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
