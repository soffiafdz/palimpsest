"""
Statistics Dashboard Builder
-----------------------------

Creates comprehensive statistics dashboard with analytics and visualizations.

Functions:
    - export_stats: Export statistics dashboard (stats.md)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from datetime import date
from collections import defaultdict, Counter

from sqlalchemy import select, func

from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Entry as DBEntry,
    Person as DBPerson,
    Tag as DBTag,
    Location as DBLocation,
    City as DBCity,
    Event as DBEvent,
)
from dev.database.models_manuscript import Theme as DBTheme
from dev.core.logging_manager import PalimpsestLogger
from dev.builders.wiki import write_if_changed
from .utils import ascii_bar_chart, yearly_bar_chart


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
