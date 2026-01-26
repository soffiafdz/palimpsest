#!/usr/bin/env python3
"""
exporter.py
-----------
Export database entities to wiki markdown files.

Provides a unified exporter that handles all entity types using
configuration objects and Jinja2 templates. This replaces the
individual wiki dataclass exporters with a single, clean interface.

Usage:
    exporter = WikiExporter(db, wiki_dir, logger)
    stats = exporter.export_entity_type(PERSON_CONFIG)
    stats = exporter.export_all()
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.cli import ConversionStats
from dev.database.manager import PalimpsestDB

from dev.utils.wiki import slugify

from .renderer import WikiRenderer
from .configs import EntityConfig, ALL_CONFIGS, MANUSCRIPT_CONFIGS


def write_if_changed(path: Path, content: str) -> str:
    """
    Write content to file only if it differs from existing content.

    Args:
        path: Target file path
        content: Content to write

    Returns:
        Status string: "created", "updated", or "unchanged"
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return "unchanged"
        path.write_text(content, encoding="utf-8")
        return "updated"
    else:
        path.write_text(content, encoding="utf-8")
        return "created"


class WikiExporter:
    """
    Export database entities to wiki markdown using Jinja2 templates.

    This class provides a unified interface for exporting all entity types,
    replacing the individual wiki dataclass exporters with a single
    configuration-driven implementation.

    Attributes:
        db: Database manager instance
        wiki_dir: Root wiki directory
        renderer: Jinja2 wiki renderer
        logger: Optional logger for operation tracking
    """

    def __init__(
        self,
        db: PalimpsestDB,
        wiki_dir: Path,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the wiki exporter.

        Args:
            db: Database manager instance
            wiki_dir: Root wiki directory for output
            logger: Optional logger for operation tracking
        """
        self.db = db
        self.wiki_dir = wiki_dir
        self.renderer = WikiRenderer(wiki_dir)
        self.logger = logger

    def export_entity_type(
        self,
        config: EntityConfig,
        force: bool = False,
    ) -> ConversionStats:
        """
        Export all entities of a given type to wiki pages.

        Args:
            config: Entity configuration defining query and template
            force: If True, regenerate files even if unchanged

        Returns:
            Statistics with counts of created/updated/skipped files
        """
        stats = ConversionStats()

        safe_logger(self.logger).log_info(f"Exporting {config.plural}...")

        with self.db.session_scope() as session:
            entities = config.query(session)

            if not entities:
                safe_logger(self.logger).log_info(f"No {config.plural} to export")
                return stats

            for entity in entities:
                self._export_entity(entity, config, force, stats)

        safe_logger(self.logger).log_info(
            f"Exported {config.plural}: "
            f"{stats.entries_created} created, {stats.entries_updated} updated, "
            f"{stats.entries_skipped} unchanged"
        )

        return stats

    def _export_entity(
        self,
        entity,
        config: EntityConfig,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """
        Export a single entity to its wiki page.

        Args:
            entity: Database entity to export
            config: Entity configuration
            force: If True, regenerate even if unchanged
            stats: Statistics object to update
        """
        # Determine output path
        slug = config.get_slug(entity)
        output_path = self.wiki_dir / config.folder / f"{slug}.md"

        # Compute extra context for specific entity types
        extra_context = {}
        if config.name == "person":
            extra_context = self._compute_person_context(entity)

        # Render template
        content = self.renderer.render(
            config.template,
            output_path=output_path,
            entity=entity,
            config=config,
            **extra_context,
        )

        # Write file
        if force:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            stats.entries_updated += 1
        else:
            status = write_if_changed(output_path, content)
            if status == "created":
                stats.entries_created += 1
            elif status == "updated":
                stats.entries_updated += 1
            else:
                stats.entries_skipped += 1

    def _compute_person_context(self, person) -> dict:
        """
        Compute extra context for person template.

        Args:
            person: Person entity

        Returns:
            Dict with co_appearances and locations data
        """
        from collections import Counter

        # Compute co-appearances (people who appear in the same entries)
        co_appearance_counter = Counter()
        for entry in person.entries:
            for other_person in entry.people:
                if other_person.id != person.id:
                    co_appearance_counter[other_person] += 1

        co_appearances = [
            {
                "name": p.display_name,
                "slug": slugify(p.display_name),
                "count": count,
            }
            for p, count in co_appearance_counter.most_common(10)
        ]

        # Compute locations from scenes
        location_counter = Counter()
        for scene in person.scenes:
            for location in scene.locations:
                location_counter[location] += 1

        locations = [
            {
                "name": loc.name,
                "slug": slugify(loc.name),
                "city": loc.city.name if loc.city else "Unknown",
                "city_slug": slugify(loc.city.name) if loc.city else "unknown",
                "count": count,
            }
            for loc, count in location_counter.most_common(10)
        ]

        return {
            "co_appearances": co_appearances,
            "locations": locations,
        }

    def export_all(self, force: bool = False) -> ConversionStats:
        """
        Export all entity types to wiki.

        Args:
            force: If True, regenerate all files

        Returns:
            Combined statistics for all entity types
        """
        total_stats = ConversionStats()

        for config in ALL_CONFIGS:
            stats = self.export_entity_type(config, force)
            total_stats.entries_created += stats.entries_created
            total_stats.entries_updated += stats.entries_updated
            total_stats.entries_skipped += stats.entries_skipped

        safe_logger(self.logger).log_info(
            f"Wiki export complete: "
            f"{total_stats.entries_created} created, {total_stats.entries_updated} updated, "
            f"{total_stats.entries_skipped} unchanged"
        )

        return total_stats

    def export_indexes(self, force: bool = False) -> ConversionStats:
        """
        Export index pages for all entity types and home dashboard.

        Args:
            force: If True, regenerate all indexes

        Returns:
            Statistics for index generation
        """
        stats = ConversionStats()

        with self.db.session_scope() as session:
            # Export each index type
            self._export_people_index(session, force, stats)
            self._export_entries_index(session, force, stats)
            self._export_events_index(session, force, stats)
            self._export_locations_index(session, force, stats)
            self._export_cities_index(session, force, stats)
            self._export_threads_index(session, force, stats)
            self._export_simple_index(session, "tags", "Tags", force, stats)
            self._export_simple_index(session, "themes", "Themes", force, stats)
            self._export_simple_index(session, "poems", "Poems", force, stats)
            self._export_simple_index(session, "references", "References", force, stats)

        # Export home dashboard
        home_stats = self.export_home(force)
        stats.entries_created += home_stats.entries_created
        stats.entries_updated += home_stats.entries_updated
        stats.entries_skipped += home_stats.entries_skipped

        safe_logger(self.logger).log_info(
            f"Index export complete: "
            f"{stats.entries_created} created, {stats.entries_updated} updated, "
            f"{stats.entries_skipped} unchanged"
        )

        return stats

    def _export_people_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export people index grouped by category with frequency bars."""
        from collections import Counter, defaultdict
        from dev.database.models import Person

        # Category ordering
        categories = [
            "Family", "Friend", "Romantic", "Colleague",
            "Professional", "Acquaintance", "Public", "Main",
            "Secondary", "Archive", "Unsorted", "Unknown"
        ]

        # Query all people
        people = session.query(Person).filter(Person.deleted_at.is_(None)).all()

        # Find max mentions for bar normalization
        all_mentions = [len(p.entries) for p in people]
        max_mentions = max(all_mentions) if all_mentions else 1

        # Group by category with frequency bars
        groups = defaultdict(list)
        category_counts = Counter()

        for person in people:
            category = person.relation_type.value.title() if person.relation_type else "Unknown"
            mentions = len(person.entries)
            bar_length = int((mentions / max_mentions) * 15) if max_mentions else 0
            bar = "█" * bar_length + "░" * (15 - bar_length)

            groups[category].append({
                "name": person.display_name,
                "path": f"people/{slugify(person.display_name)}.md",
                "mentions": mentions,
                "bar": bar,
            })
            category_counts[category] += 1

        # Top people (across all categories)
        top_people = sorted(
            [
                {
                    "name": p.display_name,
                    "path": f"people/{slugify(p.display_name)}.md",
                    "mentions": len(p.entries),
                    "category": p.relation_type.value.title() if p.relation_type else "Unknown",
                }
                for p in people
            ],
            key=lambda x: x["mentions"],
            reverse=True,
        )[:15]

        # Category distribution
        max_cat_count = max(category_counts.values()) if category_counts else 1
        category_distribution = []
        for cat in categories:
            if cat in category_counts:
                count = category_counts[cat]
                bar_length = int((count / max_cat_count) * 20)
                bar = "█" * bar_length + "░" * (20 - bar_length)
                category_distribution.append({
                    "name": cat,
                    "count": count,
                    "bar": bar,
                })

        # Most recent appearance
        recent_appearance = None
        people_with_entries = [p for p in people if p.entries]
        if people_with_entries:
            sorted_people = sorted(
                people_with_entries,
                key=lambda p: max(e.date for e in p.entries),
                reverse=True
            )
            most_recent = sorted_people[0]
            latest_entry = max(most_recent.entries, key=lambda e: e.date)
            recent_appearance = {
                "name": most_recent.display_name,
                "path": f"people/{slugify(most_recent.display_name)}.md",
                "date": latest_entry.date,
            }

        # Write file
        output_path = self.wiki_dir / "people" / "people.md"

        # Render template
        content = self.renderer.render_index(
            "people",
            output_path,
            categories=categories,
            groups=dict(groups),
            total=len(people),
            top_people=top_people,
            category_distribution=category_distribution,
            recent_appearance=recent_appearance,
        )
        self._write_index(output_path, content, force, stats)

    def _export_entries_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export entries index grouped by year."""
        from collections import defaultdict
        from dev.database.models import Entry

        # Query all entries
        entries = session.query(Entry).all()

        # Group by year
        groups = defaultdict(list)
        total_words = 0
        for entry in entries:
            year = entry.date.year
            groups[year].append({
                "date": entry.date,
                "path": f"entries/{year}/{entry.date.isoformat()}.md",
                "word_count": entry.word_count or 0,
            })
            total_words += entry.word_count or 0

        # Write file
        output_path = self.wiki_dir / "entries" / "entries.md"

        # Render template
        content = self.renderer.render_index(
            "entries",
            output_path,
            years=list(groups.keys()),
            groups=dict(groups),
            total=len(entries),
            total_words=total_words,
        )
        self._write_index(output_path, content, force, stats)

    def _export_events_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export events index grouped by year."""
        from collections import defaultdict
        from dev.database.models import Event

        # Query all events
        events = session.query(Event).filter(Event.deleted_at.is_(None)).all()

        # Group by year (derive from first entry date)
        groups = defaultdict(list)
        for event in events:
            # Get year from first entry if available
            if event.entries:
                first_entry_date = min(e.date for e in event.entries)
                year = first_entry_date.year
            else:
                year = "Unknown"
            groups[year].append({
                "name": event.name,
                "path": f"events/{slugify(event.name)}.md",
                "scenes": len(event.scenes),
            })

        # Sort years (numbers first, then "Unknown")
        years = sorted([y for y in groups.keys() if y != "Unknown"], reverse=True)
        if "Unknown" in groups:
            years.append("Unknown")

        # Write file
        output_path = self.wiki_dir / "events" / "events.md"

        # Render template
        content = self.renderer.render_index(
            "events",
            output_path,
            years=years,
            groups=dict(groups),
            total=len(events),
        )
        self._write_index(output_path, content, force, stats)

    def _export_locations_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export locations index with hierarchical grouping."""
        from collections import defaultdict
        from dev.database.models import Location

        # Query all locations
        locations = session.query(Location).all()

        # Group by country → city
        groups = defaultdict(lambda: defaultdict(list))
        for loc in locations:
            country = loc.city.country or "Unknown" if loc.city else "Unknown"
            city = loc.city.name if loc.city else "Unknown City"
            groups[country][city].append({
                "name": loc.name,
                "path": f"locations/{slugify(city)}/{slugify(loc.name)}.md",
                "mentions": len(loc.entries),
            })

        # Convert to regular dicts for template
        groups_dict = {c: dict(cities) for c, cities in groups.items()}

        # Write file
        output_path = self.wiki_dir / "locations" / "locations.md"

        # Render template
        content = self.renderer.render_index(
            "locations",
            output_path,
            countries=list(groups.keys()),
            groups=groups_dict,
            total=len(locations),
        )
        self._write_index(output_path, content, force, stats)

    def _export_cities_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export cities index grouped by country/region."""
        from collections import defaultdict
        from dev.database.models import City

        # Query all cities
        cities = session.query(City).all()

        # Group by country
        groups = defaultdict(list)
        for city in cities:
            country = city.country or "Unknown"
            groups[country].append({
                "name": city.name,
                "path": f"cities/{slugify(city.name)}.md",
                "mentions": sum(len(loc.entries) for loc in city.locations),
            })

        # Convert to regular dict for template
        groups_dict = dict(groups)

        # Write file
        output_path = self.wiki_dir / "cities" / "cities.md"

        # Render template
        content = self.renderer.render_index(
            "cities",
            output_path,
            countries=list(groups.keys()),
            groups=groups_dict,
            total=len(cities),
        )
        self._write_index(output_path, content, force, stats)

    def _export_threads_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """
        Export threads dashboard showing temporal connections.

        This dashboard shows:
        - Thread statistics (past vs future)
        - Threads by entry
        - Temporal distance patterns
        """
        from collections import defaultdict
        from datetime import datetime

        from dev.database.models import Thread

        # Query all threads
        threads = session.query(Thread).all()

        # Basic stats
        past_count = len([t for t in threads if t.is_past_thread])
        future_count = len([t for t in threads if t.is_future_thread])

        thread_stats = {
            "past": past_count,
            "future": future_count,
            "total": len(threads),
        }

        # Group threads by entry
        threads_by_entry = defaultdict(list)
        for thread in threads:
            threads_by_entry[thread.entry.date].append({
                "name": thread.name,
                "from_date": thread.from_date,
                "to_date": thread.to_date,
                "content": thread.content,
                "is_past": thread.is_past_thread,
                "people": thread.people_names,
            })

        # Recent threads (last 10 entries with threads)
        recent_threads = []
        for entry_date in sorted(threads_by_entry.keys(), reverse=True)[:10]:
            recent_threads.append({
                "date": entry_date,
                "path": f"entries/{entry_date.year}/{entry_date.isoformat()}.md",
                "threads": threads_by_entry[entry_date],
            })

        # Threads by year
        threads_by_year = defaultdict(list)
        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        for thread in threads:
            year = thread.from_date.year
            month = thread.from_date.month

            # Find or create month entry
            month_entry = None
            for me in threads_by_year[year]:
                if me["month"] == month:
                    month_entry = me
                    break

            if not month_entry:
                month_entry = {
                    "month": month,
                    "month_name": month_names[month - 1],
                    "past_count": 0,
                    "future_count": 0,
                }
                threads_by_year[year].append(month_entry)

            if thread.is_past_thread:
                month_entry["past_count"] += 1
            else:
                month_entry["future_count"] += 1

        # Sort months within each year
        for year in threads_by_year:
            threads_by_year[year].sort(key=lambda x: x["month"])

        # Render template
        output_path = self.wiki_dir / "narrative" / "threads" / "threads.md"

        content = self.renderer.render_index(
            "threads",
            output_path,
            stats=thread_stats,
            recent_threads=recent_threads,
            threads_by_year=dict(threads_by_year),
            generated_at=datetime.now(),
        )
        self._write_index(output_path, content, force, stats)

    def _export_simple_index(
        self,
        session,
        entity_type: str,
        title: str,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """Export a simple alphabetical index for an entity type."""
        from dev.database.models import Poem, ReferenceSource, Tag, Theme

        # Map entity type to model and query
        model_map = {
            "tags": (Tag, "name", lambda t: len(t.entries)),
            "themes": (Theme, "name", lambda t: len(t.entries)),
            "poems": (Poem, "title", lambda p: len(p.versions)),
            "references": (ReferenceSource, "title", lambda r: len(r.references)),
        }

        if entity_type not in model_map:
            return

        model, name_attr, count_fn = model_map[entity_type]
        entities = session.query(model).all()

        items = []
        for entity in entities:
            name = getattr(entity, name_attr, str(entity))
            items.append({
                "name": name,
                "path": f"{entity_type}/{slugify(name)}.md",
                "mentions": count_fn(entity),
            })

        # Write file
        output_path = self.wiki_dir / entity_type / f"{entity_type}.md"

        # Render template
        content = self.renderer.render_index(
            "simple",
            output_path,
            title=title,
            description=f"Index of all {title.lower()} in the journal.",
            items=items,
        )
        self._write_index(output_path, content, force, stats)

    def _write_index(
        self, path: Path, content: str, force: bool, stats: ConversionStats
    ) -> None:
        """Write index file and update stats."""
        if force:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            stats.entries_updated += 1
        else:
            status = write_if_changed(path, content)
            if status == "created":
                stats.entries_created += 1
            elif status == "updated":
                stats.entries_updated += 1
            else:
                stats.entries_skipped += 1

    def export_home(self, force: bool = False) -> ConversionStats:
        """
        Export the main wiki home dashboard.

        Args:
            force: If True, regenerate even if unchanged

        Returns:
            Statistics for home page generation
        """
        from collections import defaultdict
        from datetime import datetime

        from sqlalchemy.orm import joinedload

        from dev.database.models import (
            City,
            Entry,
            Event,
            Location,
            Person,
            Poem,
            PoemVersion,
            ReferenceSource,
            Tag,
            Theme,
            Thread,
        )
        from dev.database.models.enums import RelationType

        stats = ConversionStats()

        with self.db.session_scope() as session:
            # Gather statistics with eager loading for recent entries
            entries = session.query(Entry).options(
                joinedload(Entry.people)
            ).all()
            people = session.query(Person).filter(Person.deleted_at.is_(None)).all()
            locations = session.query(Location).all()
            threads = session.query(Thread).all()

            # Calculate years span
            years = set(e.date.year for e in entries)
            first_year = min(years) if years else None
            last_year = max(years) if years else None

            # Count close relationships (family, friend, romantic)
            close_types = {RelationType.FAMILY, RelationType.FRIEND, RelationType.ROMANTIC}
            close_relationships = len([
                p for p in people
                if p.relation_type and p.relation_type in close_types
            ])

            # Count threads (past vs future)
            past_threads = len([t for t in threads if t.is_past_thread])
            future_threads = len([t for t in threads if t.is_future_thread])

            total_words = sum(e.word_count or 0 for e in entries)
            wiki_stats = {
                "entries": len(entries),
                "words": total_words,
                "avg_words": total_words // len(entries) if entries else 0,
                "years": len(years),
                "first_year": first_year,
                "last_year": last_year,
                "people": len(people),
                "close_relationships": close_relationships,
                "locations": len(locations),
                "cities": session.query(City).count(),
                "countries": len(
                    set(c.country for c in session.query(City).all() if c.country)
                ),
                "events": session.query(Event).count(),
                "threads": len(threads),
                "past_threads": past_threads,
                "future_threads": future_threads,
                "tags": session.query(Tag).count(),
                "themes": session.query(Theme).count(),
                "poems": session.query(Poem).count(),
                "poem_versions": session.query(PoemVersion).count(),
                "external_refs": session.query(ReferenceSource).count(),
            }

            # Recent entries (latest 5) with people names
            sorted_entries = sorted(entries, key=lambda x: x.date, reverse=True)[:5]
            recent_entries = [
                {
                    "date": e.date,
                    "path": f"entries/{e.date.year}/{e.date.isoformat()}.md",
                    "word_count": e.word_count or 0,
                    "people": [p.display_name for p in e.people[:3]],
                }
                for e in sorted_entries
            ]

            # Most mentioned people (top 5) with category
            recent_people = sorted(
                [
                    {
                        "name": p.display_name,
                        "path": f"people/{slugify(p.display_name)}.md",
                        "mentions": len(p.entries),
                        "category": p.relationship_display if p.relation_type else "Unknown",
                    }
                    for p in people
                ],
                key=lambda x: x["mentions"],
                reverse=True,
            )[:5]

            # Top locations by entry count
            top_locations = sorted(
                [
                    {
                        "name": loc.name,
                        "path": f"locations/{slugify(loc.city.name)}/{slugify(loc.name)}.md",
                        "visits": loc.entry_count,
                    }
                    for loc in locations if loc.city
                ],
                key=lambda x: x["visits"],
                reverse=True,
            )[:5]

            # Year distribution with bar chart
            entries_by_year = defaultdict(int)
            for entry in entries:
                entries_by_year[entry.date.year] += 1

            max_year_count = max(entries_by_year.values()) if entries_by_year else 1
            yearly_distribution = []
            for year in sorted(entries_by_year.keys()):
                count = entries_by_year[year]
                bar_length = int((count / max_year_count) * 20)
                bar = "█" * bar_length + "░" * (20 - bar_length)
                yearly_distribution.append({
                    "year": year,
                    "bar": bar,
                    "count": count,
                })

            # Render home template
            output_path = self.wiki_dir / "index.md"
            content = self.renderer.render_index(
                "home",
                output_path,
                stats=wiki_stats,
                recent_entries=recent_entries,
                recent_people=recent_people,
                top_locations=top_locations,
                yearly_distribution=yearly_distribution,
                generated_at=datetime.now(),
            )

            self._write_index(output_path, content, force, stats)

        safe_logger(self.logger).log_info("Home dashboard exported")

        return stats

    def export_stats(self, force: bool = False) -> ConversionStats:
        """
        Export the statistics dashboard.

        Args:
            force: If True, regenerate even if unchanged

        Returns:
            Statistics for stats page generation
        """
        from collections import Counter, defaultdict
        from datetime import date, datetime

        from dev.database.models import (
            City,
            Entry,
            Event,
            Location,
            Person,
            Tag,
            Theme,
        )

        stats = ConversionStats()

        with self.db.session_scope() as session:
            # Query entries
            entries = session.query(Entry).order_by(Entry.date).all()

            if not entries:
                safe_logger(self.logger).log_warning("No entries found for statistics")
                return stats

            total_entries = len(entries)
            total_words = sum(e.word_count or 0 for e in entries)
            avg_words = total_words // total_entries if total_entries else 0

            first_date = entries[0].date
            last_date = entries[-1].date
            span_days = (last_date - first_date).days

            # People
            people = session.query(Person).filter(Person.deleted_at.is_(None)).all()
            total_people = len(people)

            # Tags
            tags = session.query(Tag).all()

            # Counts
            total_locations = session.query(Location).count()
            total_cities = session.query(City).count()
            total_events = session.query(Event).count()
            total_themes = session.query(Theme).count()

            # Monthly frequency (last 12 months)
            entries_by_month = defaultdict(int)
            for entry in entries:
                month_key = f"{entry.date.year}-{entry.date.month:02d}"
                entries_by_month[month_key] += 1

            current_month = date.today().replace(day=1)
            months = []
            for i in range(12):
                month = current_month.month - i
                year = current_month.year
                while month <= 0:
                    month += 12
                    year -= 1
                month_date = date(year, month, 1)
                months.append(month_date)
            months.reverse()

            max_month_count = max(entries_by_month.values()) if entries_by_month else 1
            monthly_frequency = []
            for month_date in months:
                month_key = f"{month_date.year}-{month_date.month:02d}"
                count = entries_by_month.get(month_key, 0)
                bar_length = int((count / max_month_count) * 20) if max_month_count else 0
                bar = "█" * bar_length if bar_length else "░"
                monthly_frequency.append({
                    "name": month_date.strftime("%b %Y"),
                    "bar": bar,
                    "count": count,
                })

            # Word count distribution
            word_ranges = {"0-100": 0, "101-250": 0, "251-500": 0, "501-1000": 0, "1000+": 0}
            for entry in entries:
                wc = entry.word_count or 0
                if wc <= 100:
                    word_ranges["0-100"] += 1
                elif wc <= 250:
                    word_ranges["101-250"] += 1
                elif wc <= 500:
                    word_ranges["251-500"] += 1
                elif wc <= 1000:
                    word_ranges["501-1000"] += 1
                else:
                    word_ranges["1000+"] += 1

            max_range = max(word_ranges.values())
            word_distribution = []
            for name, count in word_ranges.items():
                bar_length = int((count / max_range) * 20) if max_range else 0
                bar = "█" * bar_length if bar_length else "░"
                pct = (count / total_entries) * 100 if total_entries else 0
                word_distribution.append({
                    "name": name,
                    "bar": bar,
                    "count": count,
                    "percent": pct,
                })

            # Top people
            top_people = sorted(
                [
                    {
                        "name": p.display_name,
                        "mentions": len(p.entries),
                        "category": p.relationship_display if p.relation_type else "Unknown",
                    }
                    for p in people
                ],
                key=lambda x: (-x["mentions"], x["name"]),
            )

            # Relationship distribution
            relation_counts = Counter()
            for person in people:
                rel = person.relationship_display if person.relation_type else "Unknown"
                relation_counts[rel] += 1

            max_rel = max(relation_counts.values()) if relation_counts else 1
            relation_distribution = []
            for rel, count in relation_counts.most_common():
                bar_length = int((count / max_rel) * 20)
                bar = "█" * bar_length
                pct = (count / total_people) * 100 if total_people else 0
                relation_distribution.append({
                    "name": rel,
                    "bar": bar,
                    "count": count,
                    "percent": pct,
                })

            # Top tags
            top_tags = sorted(
                [{"name": t.name, "count": len(t.entries)} for t in tags],
                key=lambda x: (-x["count"], x["name"]),
            )

            # Yearly frequency
            entries_by_year = defaultdict(int)
            for entry in entries:
                entries_by_year[entry.date.year] += 1

            max_year = max(entries_by_year.values()) if entries_by_year else 1
            yearly_frequency = []
            for year in sorted(entries_by_year.keys()):
                count = entries_by_year[year]
                bar_length = int((count / max_year) * 30)
                bar = "█" * bar_length
                yearly_frequency.append({"year": year, "bar": bar, "count": count})

            # Render template
            output_path = self.wiki_dir / "stats.md"
            content = self.renderer.render_index(
                "stats",
                output_path,
                stats={
                    "entries": total_entries,
                    "words": total_words,
                    "avg_words": avg_words,
                    "first_date": first_date,
                    "last_date": last_date,
                    "span_days": span_days,
                    "people": total_people,
                    "locations": total_locations,
                    "cities": total_cities,
                    "events": total_events,
                    "themes": total_themes,
                    "tags": len(tags),
                    "entries_per_day": total_entries / max(span_days, 1),
                },
                monthly_frequency=monthly_frequency,
                word_distribution=word_distribution,
                top_people=top_people,
                relation_distribution=relation_distribution,
                top_tags=top_tags,
                yearly_frequency=yearly_frequency,
                generated_at=datetime.now(),
            )

            self._write_index(output_path, content, force, stats)

        safe_logger(self.logger).log_info("Statistics dashboard exported")

        return stats

    def export_timeline(self, force: bool = False) -> ConversionStats:
        """
        Export the timeline/calendar view with rich metadata overlay.

        Args:
            force: If True, regenerate even if unchanged

        Returns:
            Statistics for timeline page generation
        """
        from collections import defaultdict
        from datetime import datetime

        from sqlalchemy.orm import joinedload

        from dev.database.models import Entry

        stats = ConversionStats()

        with self.db.session_scope() as session:
            # Load entries with relationships for rich metadata
            entries = (
                session.query(Entry)
                .options(
                    joinedload(Entry.people),
                    joinedload(Entry.cities),
                    joinedload(Entry.tags),
                    joinedload(Entry.scenes),
                    joinedload(Entry.threads),
                )
                .order_by(Entry.date)
                .all()
            )

            if not entries:
                safe_logger(self.logger).log_warning("No entries found for timeline")
                return stats

            total_entries = len(entries)
            first_date = entries[0].date
            last_date = entries[-1].date
            span_days = (last_date - first_date).days

            # Group by year and month
            entries_by_year = defaultdict(lambda: defaultdict(list))
            for entry in entries:
                year = entry.date.year
                month = entry.date.month
                entries_by_year[year][month].append(entry)

            month_names = [
                "January", "February", "March", "April", "May", "June",
                "July", "August", "September", "October", "November", "December"
            ]

            # Build timeline structure with rich entry data
            timeline = []
            for year in sorted(entries_by_year.keys(), reverse=True):
                year_entries = []
                for month_entries in entries_by_year[year].values():
                    year_entries.extend(month_entries)

                year_count = len(year_entries)
                year_words = sum(e.word_count or 0 for e in year_entries)

                months = []
                for month in range(1, 13):
                    if month in entries_by_year[year]:
                        month_entries = entries_by_year[year][month]
                        months.append({
                            "name": month_names[month - 1],
                            "count": len(month_entries),
                            "entries": [
                                {
                                    "date": e.date,
                                    "path": f"entries/{year}/{e.date.isoformat()}.md",
                                    "word_count": e.word_count or 0,
                                    "people": [p.display_name for p in e.people],
                                    "cities": [c.name for c in e.cities],
                                    "tags": [t.name for t in e.tags],
                                    "scenes": len(e.scenes),
                                    "threads": len(e.threads),
                                }
                                for e in sorted(month_entries, key=lambda x: x.date, reverse=True)
                            ],
                        })
                timeline.append({
                    "year": year,
                    "count": year_count,
                    "words": year_words,
                    "months": months,
                })

            total_years = len(entries_by_year)

            # Render template
            output_path = self.wiki_dir / "timeline.md"
            content = self.renderer.render_index(
                "timeline",
                output_path,
                stats={
                    "entries": total_entries,
                    "years": total_years,
                    "span_days": span_days,
                    "first_date": first_date,
                    "last_date": last_date,
                    "avg_per_year": total_entries / total_years if total_years else 0,
                },
                timeline=timeline,
                generated_at=datetime.now(),
            )

            self._write_index(output_path, content, force, stats)

        safe_logger(self.logger).log_info("Timeline exported")

        return stats

    def export_analysis(self, force: bool = False) -> ConversionStats:
        """
        Export the analysis report.

        Args:
            force: If True, regenerate even if unchanged

        Returns:
            Statistics for analysis page generation
        """
        import calendar
        from collections import Counter, defaultdict
        from datetime import datetime

        from sqlalchemy.orm import joinedload

        from dev.database.models import Entry

        stats = ConversionStats()

        with self.db.session_scope() as session:
            entries = (
                session.query(Entry)
                .options(
                    joinedload(Entry.people),
                    joinedload(Entry.locations),
                    joinedload(Entry.cities),
                    joinedload(Entry.events),
                    joinedload(Entry.tags),
                )
                .order_by(Entry.date)
                .all()
            )

            if not entries:
                safe_logger(self.logger).log_warning("No entries found for analysis")
                return stats

            # Entity counters
            person_counter = Counter()
            location_counter = Counter()
            city_counter = Counter()
            tag_counter = Counter()

            # Temporal data
            entries_by_year = defaultdict(int)
            entries_by_dow = defaultdict(int)
            word_count_by_year = defaultdict(int)
            entries_by_month = defaultdict(int)

            # Co-occurrence
            person_colocation = defaultdict(lambda: defaultdict(int))

            for entry in entries:
                for person in entry.people:
                    person_counter[person.display_name] += 1
                for location in entry.locations:
                    location_counter[location.name] += 1
                for city in entry.cities:
                    city_counter[city.name] += 1
                for tag in entry.tags:
                    tag_counter[tag.name] += 1

                entries_by_year[entry.date.year] += 1
                entries_by_month[f"{entry.date.year}-{entry.date.month:02d}"] += 1
                entries_by_dow[entry.date.strftime("%A")] += 1
                word_count_by_year[entry.date.year] += entry.word_count or 0

                for person in entry.people:
                    for city in entry.cities:
                        person_colocation[person.display_name][city.name] += 1

            total_entries = len(entries)
            total_words = sum(e.word_count or 0 for e in entries)

            # Yearly activity
            max_year = max(entries_by_year.values()) if entries_by_year else 1
            yearly_activity = []
            for year in sorted(entries_by_year.keys()):
                count = entries_by_year[year]
                bar_length = int((count / max_year) * 50)
                bar = "█" * bar_length
                yearly_activity.append({
                    "year": year,
                    "bar": bar,
                    "count": count,
                    "words": word_count_by_year[year],
                })

            # Top entities
            top_people = [
                {
                    "name": name,
                    "count": count,
                    "path": f"people/{slugify(name)}.md",
                }
                for name, count in person_counter.most_common(10)
            ]

            top_locations = [
                {"name": name, "count": count}
                for name, count in location_counter.most_common(10)
            ]

            top_cities = [
                {
                    "name": name,
                    "count": count,
                    "path": f"cities/{slugify(name)}.md",
                }
                for name, count in city_counter.most_common(10)
            ]

            top_tags = [
                {
                    "name": name,
                    "count": count,
                    "path": f"tags/{slugify(name)}.md",
                }
                for name, count in tag_counter.most_common(15)
            ]

            # Day of week
            dow_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            max_dow = max(entries_by_dow.values()) if entries_by_dow else 1
            day_of_week = []
            for dow in dow_order:
                count = entries_by_dow.get(dow, 0)
                bar_length = int((count / max_dow) * 40)
                bar = "█" * bar_length
                day_of_week.append({"name": dow, "bar": bar, "count": count})

            # Person-city network
            person_city_network = []
            for name, _ in person_counter.most_common(5):
                if name in person_colocation:
                    cities = person_colocation[name]
                    top_cities_list = sorted(cities.items(), key=lambda x: x[1], reverse=True)[:3]
                    city_str = ", ".join([f"{city} ({c}×)" for city, c in top_cities_list])
                    person_city_network.append({
                        "name": name,
                        "path": f"people/{slugify(name)}.md",
                        "cities": city_str,
                    })

            # Monthly heatmap (last 12 months)
            monthly_heatmap = []
            if entries:
                last_date = entries[-1].date
                for i in range(11, -1, -1):
                    year = last_date.year
                    month = last_date.month - i
                    if month <= 0:
                        year -= 1
                        month += 12
                    month_key = f"{year}-{month:02d}"
                    count = entries_by_month.get(month_key, 0)
                    if count == 0:
                        intensity = "░░░"
                    elif count <= 2:
                        intensity = "▒▒▒"
                    elif count <= 5:
                        intensity = "▓▓▓"
                    else:
                        intensity = "███"
                    monthly_heatmap.append({
                        "key": month_key,
                        "name": calendar.month_abbr[month],
                        "intensity": intensity,
                        "count": count,
                    })

            # Render template
            output_path = self.wiki_dir / "analysis.md"
            content = self.renderer.render_index(
                "analysis",
                output_path,
                stats={
                    "entries": total_entries,
                    "people": len(person_counter),
                    "locations": len(location_counter),
                    "cities": len(city_counter),
                    "events": sum(len(e.events) for e in entries),
                    "tags": len(tag_counter),
                    "words": total_words,
                    "avg_words": total_words // total_entries if total_entries else 0,
                },
                yearly_activity=yearly_activity,
                top_people=top_people,
                top_locations=top_locations,
                top_cities=top_cities,
                top_tags=top_tags,
                day_of_week=day_of_week,
                person_city_network=person_city_network,
                monthly_heatmap=monthly_heatmap,
                generated_at=datetime.now(),
            )

            self._write_index(output_path, content, force, stats)

        safe_logger(self.logger).log_info("Analysis report exported")

        return stats

    # =========================================================================
    # MANUSCRIPT EXPORT METHODS
    # =========================================================================

    def export_manuscript(self, force: bool = False) -> ConversionStats:
        """
        Export all manuscript entity types to wiki/manuscript/.

        Args:
            force: If True, regenerate all files

        Returns:
            Combined statistics for all manuscript entity types
        """
        total_stats = ConversionStats()

        for config in MANUSCRIPT_CONFIGS:
            stats = self.export_entity_type(config, force)
            total_stats.entries_created += stats.entries_created
            total_stats.entries_updated += stats.entries_updated
            total_stats.entries_skipped += stats.entries_skipped

        safe_logger(self.logger).log_info(
            f"Manuscript export complete: "
            f"{total_stats.entries_created} created, {total_stats.entries_updated} updated, "
            f"{total_stats.entries_skipped} unchanged"
        )

        return total_stats

    def export_manuscript_indexes(self, force: bool = False) -> ConversionStats:
        """
        Export manuscript subwiki index pages.

        Args:
            force: If True, regenerate all indexes

        Returns:
            Statistics for manuscript index generation
        """
        stats = ConversionStats()

        with self.db.session_scope() as session:
            # Export manuscript home
            self._export_manuscript_home(session, force, stats)
            # Export manuscript entity indexes
            self._export_manuscript_chapters_index(session, force, stats)
            self._export_manuscript_characters_index(session, force, stats)
            self._export_manuscript_arcs_index(session, force, stats)
            self._export_manuscript_scenes_index(session, force, stats)

        safe_logger(self.logger).log_info(
            f"Manuscript index export complete: "
            f"{stats.entries_created} created, {stats.entries_updated} updated, "
            f"{stats.entries_skipped} unchanged"
        )

        return stats

    def _export_manuscript_home(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export manuscript subwiki home page."""
        from datetime import datetime

        from dev.database.models import Arc, Chapter, Character, ChapterStatus

        # Gather manuscript statistics
        chapters = session.query(Chapter).all()
        characters = session.query(Character).all()
        arcs = session.query(Arc).all()

        # Count by status
        status_counts = {}
        for status in ChapterStatus:
            status_counts[status.value] = len(
                [c for c in chapters if c.status == status]
            )

        ms_stats = {
            "chapters": len(chapters),
            "characters": len(characters),
            "arcs": len(arcs),
            "status_counts": status_counts,
        }

        # Render template
        output_path = self.wiki_dir / "manuscript" / "index.md"
        content = self.renderer.render_index(
            "manuscript_home",
            output_path,
            stats=ms_stats,
            generated_at=datetime.now(),
        )
        self._write_index(output_path, content, force, stats)

    def _export_manuscript_chapters_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export manuscript chapters index grouped by part."""
        from collections import defaultdict

        from dev.database.models import Chapter, Part

        chapters = session.query(Chapter).all()
        parts = session.query(Part).all()

        # Group by part
        groups = defaultdict(list)
        for chapter in chapters:
            part_name = chapter.part.title if chapter.part else "Unassigned"
            groups[part_name].append({
                "title": chapter.title,
                "number": chapter.number,
                "path": f"manuscript/chapters/{slugify(chapter.title)}.md",
                "status": chapter.status.value if chapter.status else "draft",
                "type": chapter.type.value if chapter.type else "prose",
            })

        # Sort chapters within each part by number
        for part_name in groups:
            groups[part_name].sort(key=lambda c: c["number"] or 999)

        # Render template
        output_path = self.wiki_dir / "manuscript" / "chapters" / "chapters.md"
        content = self.renderer.render_index(
            "manuscript_chapters",
            output_path,
            parts=[p.title for p in parts] + (["Unassigned"] if any(c.part is None for c in chapters) else []),
            groups=dict(groups),
            total=len(chapters),
        )
        self._write_index(output_path, content, force, stats)

    def _export_manuscript_characters_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export manuscript characters index."""
        from dev.database.models import Character

        characters = session.query(Character).order_by(Character.name).all()

        items = []
        for char in characters:
            # Get primary person mapping if available
            primary_person = None
            for mapping in char.person_mappings:
                if mapping.contribution.value == "primary":
                    primary_person = mapping.person.display_name
                    break

            items.append({
                "name": char.name,
                "path": f"manuscript/characters/{slugify(char.name)}.md",
                "role": char.role,
                "based_on": primary_person,
                "chapter_count": len(char.chapters),
            })

        # Render template
        output_path = self.wiki_dir / "manuscript" / "characters" / "characters.md"
        content = self.renderer.render_index(
            "manuscript_characters",
            output_path,
            items=items,
            total=len(characters),
        )
        self._write_index(output_path, content, force, stats)

    def _export_manuscript_arcs_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export story arcs index."""
        from dev.database.models import Arc

        arcs = session.query(Arc).order_by(Arc.name).all()

        items = []
        for arc in arcs:
            items.append({
                "name": arc.name,
                "path": f"narrative/arcs/{slugify(arc.name)}.md",
                "entry_count": arc.entry_count,
            })

        # Render template
        output_path = self.wiki_dir / "manuscript" / "arcs" / "arcs.md"
        content = self.renderer.render_index(
            "manuscript_arcs",
            output_path,
            items=items,
            total=len(arcs),
        )
        self._write_index(output_path, content, force, stats)

    def _export_manuscript_scenes_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export manuscript scenes index."""
        from dev.database.models import ManuscriptScene

        ms_scenes = session.query(ManuscriptScene).all()

        items = []
        for ms_scene in ms_scenes:
            items.append({
                "name": ms_scene.name,
                "path": f"manuscript/scenes/{slugify(ms_scene.name)}.md",
                "chapter": ms_scene.chapter.title if ms_scene.chapter else "Unassigned",
                "origin": ms_scene.origin.value if ms_scene.origin else "unknown",
                "status": ms_scene.status.value if ms_scene.status else "fragment",
            })

        # Render template
        output_path = self.wiki_dir / "manuscript" / "scenes" / "scenes.md"
        content = self.renderer.render_index(
            "manuscript_scenes",
            output_path,
            items=items,
            total=len(ms_scenes),
        )
        self._write_index(output_path, content, force, stats)

    # =========================================================================
    # Narrative Export (from manifest files)
    # =========================================================================

    def export_narrative(self, force: bool = False) -> ConversionStats:
        """
        Export narrative structure pages from manifest files.

        Exports arc and event pages from the narrative_analysis manifests,
        not from the database. This provides wiki pages for the
        scenes/events/arcs hierarchy.

        Args:
            force: If True, regenerate all pages

        Returns:
            Statistics for narrative export
        """
        from .narrative_parser import NarrativeParser

        stats = ConversionStats()
        parser = NarrativeParser()

        arcs = parser.get_arcs()
        events = parser.get_events()
        narrative_stats = parser.get_stats()

        # Build lookup dicts
        events_lookup = {e.name: e for e in events}
        arc_lookup = {a.name: a for a in arcs}

        # Export arcs index
        self._export_narrative_arcs_index(
            arcs, events_lookup, narrative_stats, force, stats
        )

        # Export individual arc pages
        for arc in arcs:
            self._export_narrative_arc_page(
                arc, arcs, events_lookup, force, stats
            )

        # Export events index
        self._export_narrative_events_index(
            events, arcs, events_lookup, narrative_stats, force, stats
        )

        # Export individual event pages
        for event in events:
            self._export_narrative_event_page(
                event, arc_lookup, force, stats
            )

        safe_logger(self.logger).log_info(
            f"Narrative export complete: "
            f"{stats.entries_created} created, {stats.entries_updated} updated, "
            f"{stats.entries_skipped} unchanged"
        )

        return stats

    def _export_narrative_arcs_index(
        self,
        arcs,
        events_lookup: dict,
        narrative_stats: dict,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """Export narrative arcs index page."""
        output_path = self.wiki_dir / "narrative" / "arcs" / "arcs.md"

        content = self.renderer.render_index(
            "narrative_arcs",
            output_path,
            arcs=arcs,
            events_lookup=events_lookup,
            stats=narrative_stats,
        )
        self._write_index(output_path, content, force, stats)

    def _export_narrative_arc_page(
        self,
        arc,
        arcs,
        events_lookup: dict,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """Export a single narrative arc page."""
        output_path = self.wiki_dir / "narrative" / "arcs" / f"{arc.slug}.md"

        content = self.renderer.render(
            "narrative_arc",
            output_path=output_path,
            arc=arc,
            arcs=arcs,
            events_lookup=events_lookup,
        )

        if force:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            stats.entries_updated += 1
        else:
            status = write_if_changed(output_path, content)
            if status == "created":
                stats.entries_created += 1
            elif status == "updated":
                stats.entries_updated += 1
            else:
                stats.entries_skipped += 1

    def _export_narrative_events_index(
        self,
        events,
        arcs,
        events_lookup: dict,
        narrative_stats: dict,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """Export narrative events index page."""
        output_path = self.wiki_dir / "narrative" / "events" / "events.md"

        content = self.renderer.render_index(
            "narrative_events",
            output_path,
            events=events,
            arcs=arcs,
            events_lookup=events_lookup,
            stats=narrative_stats,
        )
        self._write_index(output_path, content, force, stats)

    def _export_narrative_event_page(
        self,
        event,
        arc_lookup: dict,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """Export a single narrative event page."""
        output_path = self.wiki_dir / "narrative" / "events" / f"{event.slug}.md"

        content = self.renderer.render(
            "narrative_event",
            output_path=output_path,
            event=event,
            arc_lookup=arc_lookup,
        )

        if force:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            stats.entries_updated += 1
        else:
            status = write_if_changed(output_path, content)
            if status == "created":
                stats.entries_created += 1
            elif status == "updated":
                stats.entries_updated += 1
            else:
                stats.entries_skipped += 1
