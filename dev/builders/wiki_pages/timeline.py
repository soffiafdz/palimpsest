"""
Timeline/Calendar Builder
--------------------------

Creates chronological timeline view of all journal entries.

Functions:
    - export_timeline: Export timeline view (timeline.md)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional
from collections import defaultdict

from sqlalchemy import select

from dev.database.manager import PalimpsestDB
from dev.database.models import Entry as DBEntry
from dev.core.logging_manager import PalimpsestLogger
from dev.builders.wiki import write_if_changed
from dev.utils.md import relative_link


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
