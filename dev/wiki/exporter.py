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
from dev.core.logging_manager import PalimpsestLogger
from dev.core.cli import ConversionStats
from dev.database.manager import PalimpsestDB

from dev.utils.wiki import slugify

from .renderer import WikiRenderer
from .configs import EntityConfig, ALL_CONFIGS


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

        if self.logger:
            self.logger.log_info(f"Exporting {config.plural}...")

        with self.db.session_scope() as session:
            entities = config.query(session)

            if not entities:
                if self.logger:
                    self.logger.log_info(f"No {config.plural} to export")
                return stats

            for entity in entities:
                self._export_entity(entity, config, force, stats)

        if self.logger:
            self.logger.log_info(
                f"Exported {config.plural}: "
                f"{stats.created} created, {stats.updated} updated, "
                f"{stats.skipped} unchanged"
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

        # Render template
        content = self.renderer.render(
            config.template,
            output_path=output_path,
            entity=entity,
            config=config,
        )

        # Write file
        if force:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content, encoding="utf-8")
            stats.updated += 1
        else:
            status = write_if_changed(output_path, content)
            if status == "created":
                stats.created += 1
            elif status == "updated":
                stats.updated += 1
            else:
                stats.skipped += 1

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
            total_stats.created += stats.created
            total_stats.updated += stats.updated
            total_stats.skipped += stats.skipped

        if self.logger:
            self.logger.log_info(
                f"Wiki export complete: "
                f"{total_stats.created} created, {total_stats.updated} updated, "
                f"{total_stats.skipped} unchanged"
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
            self._export_simple_index(session, "tags", "Tags", force, stats)
            self._export_simple_index(session, "themes", "Themes", force, stats)
            self._export_simple_index(session, "poems", "Poems", force, stats)
            self._export_simple_index(session, "references", "References", force, stats)

        # Export home dashboard
        home_stats = self.export_home(force)
        stats.created += home_stats.created
        stats.updated += home_stats.updated
        stats.skipped += home_stats.skipped

        if self.logger:
            self.logger.log_info(
                f"Index export complete: "
                f"{stats.created} created, {stats.updated} updated, "
                f"{stats.skipped} unchanged"
            )

        return stats

    def _export_people_index(
        self, session, force: bool, stats: ConversionStats
    ) -> None:
        """Export people index grouped by category."""
        from collections import defaultdict
        from dev.database.models import Person

        # Category ordering
        categories = [
            "Family", "Friend", "Romantic", "Colleague",
            "Professional", "Acquaintance", "Public", "Main",
            "Secondary", "Archive", "Unsorted", "Unknown"
        ]

        # Query all people
        people = session.query(Person).filter(Person.deleted_at.is_(None)).all()

        # Group by category
        groups = defaultdict(list)
        for person in people:
            category = person.relation_type.value.title() if person.relation_type else "Unknown"
            groups[category].append({
                "name": person.display_name,
                "path": f"people/{slugify(person.display_name)}.md",
                "mentions": len(person.entries),
            })

        # Write file
        output_path = self.wiki_dir / "people" / "people.md"

        # Render template
        content = self.renderer.render_index(
            "people",
            output_path,
            categories=categories,
            groups=dict(groups),
            total=len(people),
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

        # Group by year
        groups = defaultdict(list)
        for event in events:
            if event.date:
                year = event.date.year
            else:
                year = "Unknown"
            groups[year].append({
                "name": event.display_name,
                "path": f"events/{slugify(event.event)}.md",
                "mentions": len(event.entries),
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

        # Group by country → region → city
        groups = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        for loc in locations:
            country = loc.city.country or "Unknown" if loc.city else "Unknown"
            region = loc.city.region or "Unspecified" if loc.city else "Unspecified"
            city = loc.city.city if loc.city else "Unknown City"
            groups[country][region][city].append({
                "name": loc.name,
                "path": f"locations/{slugify(city)}/{slugify(loc.name)}.md",
                "mentions": len(loc.entries),
            })

        # Convert to regular dicts for template
        groups_dict = {
            c: {r: dict(cities) for r, cities in regions.items()}
            for c, regions in groups.items()
        }

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

        # Group by country → region
        groups = defaultdict(lambda: defaultdict(list))
        for city in cities:
            country = city.country or "Unknown"
            region = city.region or "Unspecified"
            groups[country][region].append({
                "name": city.city,
                "path": f"cities/{slugify(city.city)}.md",
                "mentions": sum(len(loc.entries) for loc in city.locations),
            })

        # Convert to regular dicts for template
        groups_dict = {c: dict(regions) for c, regions in groups.items()}

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

    def _export_simple_index(
        self,
        session,
        entity_type: str,
        title: str,
        force: bool,
        stats: ConversionStats,
    ) -> None:
        """Export a simple alphabetical index for an entity type."""
        from dev.database.models import Tag, Poem, ReferenceSource
        from dev.database.models_manuscript import Theme

        # Map entity type to model and query
        model_map = {
            "tags": (Tag, "tag", lambda t: len(t.entries)),
            "themes": (Theme, "theme", lambda t: len(t.entries)),
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
            stats.updated += 1
        else:
            status = write_if_changed(path, content)
            if status == "created":
                stats.created += 1
            elif status == "updated":
                stats.updated += 1
            else:
                stats.skipped += 1

    def export_home(self, force: bool = False) -> ConversionStats:
        """
        Export the main wiki home dashboard.

        Args:
            force: If True, regenerate even if unchanged

        Returns:
            Statistics for home page generation
        """
        from datetime import datetime

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
        )
        from dev.database.models_manuscript import Theme

        stats = ConversionStats()

        with self.db.session_scope() as session:
            # Gather statistics
            entries = session.query(Entry).all()
            people = session.query(Person).filter(Person.deleted_at.is_(None)).all()

            wiki_stats = {
                "entries": len(entries),
                "words": sum(e.word_count or 0 for e in entries),
                "years": len(set(e.date.year for e in entries)),
                "people": len(people),
                "locations": session.query(Location).count(),
                "cities": session.query(City).count(),
                "countries": len(
                    set(c.country for c in session.query(City).all() if c.country)
                ),
                "events": session.query(Event).filter(
                    Event.deleted_at.is_(None)
                ).count(),
                "tags": session.query(Tag).filter(Tag.deleted_at.is_(None)).count(),
                "themes": session.query(Theme).filter(
                    Theme.deleted_at.is_(None)
                ).count(),
                "poems": session.query(Poem).count(),
                "poem_versions": session.query(PoemVersion).count(),
                "references": session.query(ReferenceSource).count(),
            }

            # Recent entries (latest 5)
            recent_entries = [
                {
                    "date": e.date,
                    "path": f"entries/{e.date.year}/{e.date.isoformat()}.md",
                    "word_count": e.word_count or 0,
                }
                for e in sorted(entries, key=lambda x: x.date, reverse=True)[:5]
            ]

            # Most mentioned people (top 5)
            recent_people = sorted(
                [
                    {
                        "name": p.display_name,
                        "path": f"people/{slugify(p.display_name)}.md",
                        "mentions": len(p.entries),
                    }
                    for p in people
                ],
                key=lambda x: x["mentions"],
                reverse=True,
            )[:5]

            # Render home template
            output_path = self.wiki_dir / "index.md"
            content = self.renderer.render_index(
                "home",
                output_path,
                stats=wiki_stats,
                recent_entries=recent_entries,
                recent_people=recent_people,
                generated_at=datetime.now(),
            )

            self._write_index(output_path, content, force, stats)

        if self.logger:
            self.logger.log_info("Home dashboard exported")

        return stats
