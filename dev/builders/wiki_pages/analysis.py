"""
Analysis Report Builder
------------------------

Creates comprehensive analysis report with entity relationships and patterns.

Functions:
    - export_analysis_report: Export analysis report (analysis.md)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from collections import defaultdict, Counter
import calendar

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from dev.database.manager import PalimpsestDB
from dev.database.models import Entry as DBEntry
from dev.core.logging_manager import PalimpsestLogger
from dev.builders.wiki import write_if_changed
from dev.utils.md import relative_link
from dev.utils.wiki import entity_path


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
            "| Metric | Count |",
            "| --- | --- |",
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
            person_path = entity_path(wiki_dir, "people", person)
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
            city_path = entity_path(wiki_dir, "cities", city)
            city_link = relative_link(analysis_path, city_path)
            lines.append(f"{count:3d}× [[{city_link}|{city}]]")
        lines.append("")

        lines.extend([
            "### Top 15 Tags",
            "",
        ])

        for tag, count in tag_counter.most_common(15):
            tag_path = entity_path(wiki_dir, "tags", tag)
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

                person_path = entity_path(wiki_dir, "people", person)
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
