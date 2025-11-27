"""
Wiki Homepage/Index Builder
----------------------------

Creates the main index.md homepage with navigation and statistics.

Functions:
    - export_index: Export wiki homepage
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from sqlalchemy import select, func

from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Entry as DBEntry,
    Person as DBPerson,
    Tag as DBTag,
    Poem as DBPoem,
    ReferenceSource as DBReferenceSource,
    Location as DBLocation,
    City as DBCity,
    Event as DBEvent,
)
from dev.database.models_manuscript import Theme as DBTheme
from dev.core.logging_manager import PalimpsestLogger
from dev.builders.wiki import write_if_changed
from dev.utils.md import relative_link


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
        # Entry statistics
        entries_query = select(DBEntry).order_by(DBEntry.date.desc())
        all_entries = session.execute(entries_query).scalars().all()
        total_entries = len(all_entries)
        total_words = sum(e.word_count for e in all_entries)

        first_date = all_entries[-1].date if all_entries else None
        last_date = all_entries[0].date if all_entries else None
        span_days = (last_date - first_date).days if (first_date and last_date) else 0

        # People statistics
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
