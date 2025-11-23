"""
wiki_indexes.py
---------------
Custom index builders for wiki entity pages.

This module contains complex index builders that group entities in special ways:
- People: Grouped by relationship category
- Entries: Grouped by year
- Locations: Hierarchical grouping (country → region → city)
- Cities: Grouped by country/region
- Events: Grouped by year

These builders are used by the GenericEntityExporter when an entity requires
custom index organization beyond simple alphabetical lists.

Used by sql2wiki.py entity export operations.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from collections import defaultdict
from itertools import groupby

from dev.core.logging_manager import PalimpsestLogger
from dev.builders.wiki import write_if_changed


# Category ordering for people index
CATEGORY_ORDER = [
    "Family", "Friend", "Romantic", "Colleague",
    "Professional", "Acquaintance", "Public", "Main",
    "Secondary", "Archive", "Unsorted", "Unknown"
]


def build_people_index(
    people: List,  # List[WikiPerson]
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
        f"- **Total People**: {len(people)}",
        f"- **Categories**: {len([c for c in CATEGORY_ORDER if c in by_category])}",
        "",
    ])

    # Write index file
    index_path = wiki_dir / "people" / "people.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"

    return write_if_changed(index_path, content, force)


def build_entries_index(
    entries: List,  # List[WikiEntry]
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for entries (groups by year).

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

    # Group by year
    by_year = defaultdict(list)
    for entry in entries:
        year = entry.date.year
        by_year[year].append(entry)

    # Build index lines
    lines = [
        "# Palimpsest — Journal Entries",
        "",
        "Index of all journal entries, organized by year.",
        "",
    ]

    # Add each year in reverse order (most recent first)
    for year in sorted(by_year.keys(), reverse=True):
        year_entries = by_year[year]
        lines.extend(["", f"## {year} ({len(year_entries)} entries)", ""])

        # Sort entries by date
        year_entries.sort(key=lambda e: e.date)

        for entry in year_entries:
            rel_path = entry.path.relative_to(wiki_dir)
            date_str = entry.date.strftime("%B %d")  # e.g., "January 15"
            word_str = f"{entry.word_count} words"
            lines.append(f"- [[{rel_path}|{date_str}]] ({word_str})")

    # Add statistics
    total_words = sum(e.word_count for e in entries)
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- **Total Entries**: {len(entries)}",
        f"- **Total Words**: {total_words:,}",
        f"- **Years Covered**: {len(by_year)}",
        f"- **Average Words per Entry**: {total_words // len(entries) if entries else 0}",
        "",
    ])

    # Write index file
    index_path = wiki_dir / "entries" / "entries.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"

    return write_if_changed(index_path, content, force)


def build_locations_index(
    locations: List,  # List[WikiLocation]
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for locations (hierarchical grouping).

    Groups locations by country → region → city for easy navigation.

    Args:
        locations: List of WikiLocation instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building locations index")

    # Group by country → region → city
    by_country = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for location in locations:
        country = location.country or "Unknown"
        region = location.region or "Unspecified"
        city = location.city or "Unknown City"
        by_country[country][region][city].append(location)

    # Build index lines
    lines = [
        "# Palimpsest — Locations",
        "",
        "Index of all locations, organized by country → region → city.",
        "",
    ]

    # Add each country
    for country in sorted(by_country.keys()):
        lines.extend(["", f"## {country}", ""])

        regions = by_country[country]
        for region in sorted(regions.keys()):
            if region != "Unspecified":
                lines.append(f"### {region}")
                lines.append("")

            cities = regions[region]
            for city in sorted(cities.keys()):
                city_locations = cities[city]
                lines.append(f"#### {city}")
                lines.append("")

                # Sort by mention count
                city_locations.sort(key=lambda loc: (-loc.mentions, loc.name.lower()))

                for location in city_locations:
                    rel_path = location.path.relative_to(wiki_dir)
                    mention_str = f"{location.mentions} mention" + ("s" if location.mentions != 1 else "")
                    lines.append(f"- [[{rel_path}|{location.name}]] ({mention_str})")

                lines.append("")

    # Add statistics
    lines.extend([
        "---",
        "",
        "## Statistics",
        "",
        f"- **Total Locations**: {len(locations)}",
        f"- **Countries**: {len(by_country)}",
        "",
    ])

    # Write index file
    index_path = wiki_dir / "locations" / "locations.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"

    return write_if_changed(index_path, content, force)


def build_cities_index(
    cities: List,  # List[WikiCity]
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for cities (grouped by country/region).

    Args:
        cities: List of WikiCity instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building cities index")

    # Group by country → region
    by_country = defaultdict(lambda: defaultdict(list))

    for city in cities:
        country = city.country or "Unknown"
        region = city.region or "Unspecified"
        by_country[country][region].append(city)

    # Build index lines
    lines = [
        "# Palimpsest — Cities",
        "",
        "Index of all cities, organized by country and region.",
        "",
    ]

    # Add each country
    for country in sorted(by_country.keys()):
        lines.extend(["", f"## {country}", ""])

        regions = by_country[country]
        for region in sorted(regions.keys()):
            if region != "Unspecified":
                lines.append(f"### {region}")
                lines.append("")

            region_cities = regions[region]
            # Sort by mention count
            region_cities.sort(key=lambda c: (-c.mentions, c.name.lower()))

            for city in region_cities:
                rel_path = city.path.relative_to(wiki_dir)
                mention_str = f"{city.mentions} mention" + ("s" if city.mentions != 1 else "")
                lines.append(f"- [[{rel_path}|{city.name}]] ({mention_str})")

            lines.append("")

    # Add statistics
    lines.extend([
        "---",
        "",
        "## Statistics",
        "",
        f"- **Total Cities**: {len(cities)}",
        f"- **Countries**: {len(by_country)}",
        "",
    ])

    # Write index file
    index_path = wiki_dir / "cities" / "cities.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"

    return write_if_changed(index_path, content, force)


def build_events_index(
    events: List,  # List[WikiEvent]
    wiki_dir: Path,
    force: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> str:
    """
    Custom index builder for events (grouped by year).

    Args:
        events: List of WikiEvent instances
        wiki_dir: Vimwiki root directory
        force: Force write even if unchanged
        logger: Optional logger

    Returns:
        Status: "created", "updated", or "skipped"
    """
    if logger:
        logger.log_debug("Building events index")

    # Group by year
    by_year = defaultdict(list)
    for event in events:
        if event.date:
            year = event.date.year
        else:
            year = "Unknown"
        by_year[year].append(event)

    # Build index lines
    lines = [
        "# Palimpsest — Events",
        "",
        "Index of all events, organized by year.",
        "",
    ]

    # Add each year in reverse order (most recent first)
    years = [y for y in by_year.keys() if y != "Unknown"]
    years.sort(reverse=True)
    if "Unknown" in by_year:
        years.append("Unknown")

    for year in years:
        year_events = by_year[year]
        lines.extend(["", f"## {year} ({len(year_events)} events)", ""])

        # Sort by date if available, then by name
        year_events.sort(key=lambda e: (e.date if e.date else "", e.name.lower()))

        for event in year_events:
            rel_path = event.path.relative_to(wiki_dir)
            mention_str = f"{event.mentions} mention" + ("s" if event.mentions != 1 else "")
            lines.append(f"- [[{rel_path}|{event.name}]] ({mention_str})")

    # Add statistics
    lines.extend([
        "",
        "---",
        "",
        "## Statistics",
        "",
        f"- **Total Events**: {len(events)}",
        f"- **Years Covered**: {len([y for y in years if y != 'Unknown'])}",
        "",
    ])

    # Write index file
    index_path = wiki_dir / "events" / "events.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(lines) + "\n"

    return write_if_changed(index_path, content, force)
