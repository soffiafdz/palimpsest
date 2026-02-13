#!/usr/bin/env python3
"""
exporter.py
-----------
Wiki generation orchestrator.

Iterates over all entity types, builds context dicts via
WikiContextBuilder, renders templates via WikiRenderer, and writes
wiki pages to disk. Handles orphan cleanup (files on disk with no
corresponding DB entity).

Key Features:
    - Single session_scope wrapping all operations
    - Progress logging every 100 entities
    - Change detection (only writes if content differs)
    - Orphan file cleanup for deleted entities
    - Section-based generation (journal, manuscript, indexes)

Usage:
    from dev.wiki.exporter import WikiExporter
    from dev.database.manager import PalimpsestDB

    db = PalimpsestDB()
    exporter = WikiExporter(db)
    exporter.generate_all()

Dependencies:
    - WikiRenderer for Jinja2 rendering
    - WikiContextBuilder for DB → context dict conversion
    - Entity configs from dev.wiki.configs
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.paths import WIKI_DIR, WIKI_TEMPLATES_DIR
from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Arc,
    City,
    Entry,
    Event,
    Location,
    Motif,
    Person,
    Poem,
    ReferenceSource,
    Tag,
    Theme,
)
from dev.database.models.enums import RelationType
from dev.database.models.manuscript import Chapter, Character, ManuscriptScene, Part
from dev.wiki.configs import JOURNAL_CONFIGS, MANUSCRIPT_CONFIGS, INDEX_CONFIGS
from dev.wiki.context import WikiContextBuilder
from dev.wiki.renderer import WikiRenderer


class WikiExporter:
    """
    Orchestrates wiki page generation from database.

    Iterates entity types via configs, builds context, renders
    templates, writes files, and cleans up orphaned pages.

    Attributes:
        db: PalimpsestDB instance
        output_dir: Root wiki output directory
        logger: Optional logger
        renderer: WikiRenderer instance
        stats: Generation statistics
    """

    def __init__(
        self,
        db: PalimpsestDB,
        output_dir: Optional[Path] = None,
        logger: Optional[PalimpsestLogger] = None,
    ) -> None:
        """
        Initialize wiki exporter.

        Args:
            db: Database manager instance
            output_dir: Wiki output directory (defaults to data/wiki)
            logger: Optional logger for progress tracking
        """
        self.db = db
        self.output_dir = output_dir or WIKI_DIR
        self.logger = logger
        self.renderer = WikiRenderer(WIKI_TEMPLATES_DIR)

        # Stats
        self.stats: Dict[str, int] = {}
        self.generated_files: Set[Path] = set()

    def generate_all(
        self,
        section: Optional[str] = None,
        entity_type: Optional[str] = None,
    ) -> None:
        """
        Generate all wiki pages from database.

        Args:
            section: Optional filter: "journal", "manuscript", "indexes"
            entity_type: Optional filter: entity name (e.g., "people")
        """
        safe_logger(self.logger).log_info("Starting wiki generation")

        with self.db.session_scope() as session:
            builder = WikiContextBuilder(session)

            if not section or section == "journal":
                self._generate_journal_entries(session, builder)
                self._generate_journal_entities(
                    session, builder, entity_type
                )

            if not section or section == "manuscript":
                self._generate_manuscript_entities(
                    session, builder, entity_type
                )

            if not section or section == "indexes":
                self._generate_indexes(session, builder)

            # Orphan cleanup
            if not entity_type:
                self._cleanup_orphans()

        safe_logger(self.logger).log_info(
            f"Wiki generation complete: {self.stats}"
        )

    def _generate_journal_entries(
        self,
        session: Session,
        builder: WikiContextBuilder,
    ) -> None:
        """
        Generate Entry wiki pages.

        Entries use a special path pattern (YYYY/YYYY-MM-DD.md) and
        are always generated (no visibility filter).

        Args:
            session: Active SQLAlchemy session
            builder: WikiContextBuilder instance
        """
        entries = session.query(Entry).order_by(Entry.date).all()
        total = len(entries)
        changed = 0

        for i, entry in enumerate(entries, 1):
            ctx = builder.build_entry_context(entry)
            year = entry.date.strftime("%Y")
            filename = f"{entry.date.isoformat()}.md"
            output_path = self.output_dir / "journal" / "entries" / year / filename

            if self.renderer.render_to_file(
                "journal/entry.jinja2", ctx, output_path
            ):
                changed += 1

            self.generated_files.add(output_path)

            if i % 100 == 0 or i == total:
                safe_logger(self.logger).log_debug(
                    f"Generating entries: {i}/{total}"
                )

        # Rating subpages for entries with rating_justification
        for entry in entries:
            if entry.rating_justification:
                self._generate_rating_subpage(entry)

        self.stats["entries"] = total
        self.stats["entries_changed"] = changed

    def _generate_rating_subpage(self, entry: Entry) -> None:
        """
        Generate rating justification subpage for an entry.

        Args:
            entry: Entry with rating_justification
        """
        year = entry.date.strftime("%Y")
        filename = f"{entry.date.isoformat()}-rating.md"
        output_path = (
            self.output_dir / "journal" / "entries" / year / filename
        )

        content = (
            f"# Rating: {entry.rating}/5\n\n"
            f"← [[{entry.date.isoformat()}]]\n\n"
            f"---\n\n"
            f"{entry.rating_justification}\n"
        )

        if output_path.exists():
            existing = output_path.read_text(encoding="utf-8")
            if existing == content:
                self.generated_files.add(output_path)
                return

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        self.generated_files.add(output_path)

    def _generate_journal_entities(
        self,
        session: Session,
        builder: WikiContextBuilder,
        entity_type: Optional[str] = None,
    ) -> None:
        """
        Generate wiki pages for all journal entity types.

        Iterates configs, queries entities, builds contexts, renders.

        Args:
            session: Active SQLAlchemy session
            builder: WikiContextBuilder instance
            entity_type: Optional filter to generate only one type
        """
        for config in JOURNAL_CONFIGS:
            if entity_type and config.name != entity_type:
                continue

            entities = session.query(config.model).all()
            total = len(entities)
            changed = 0

            for i, entity in enumerate(entities, 1):
                if not config.should_generate(entity):
                    continue

                context_fn = getattr(builder, config.context_method)
                ctx = context_fn(entity)
                filename = config.filename_fn(entity)
                output_path = self.output_dir / config.output_subdir / filename

                if self.renderer.render_to_file(
                    config.template, ctx, output_path
                ):
                    changed += 1

                self.generated_files.add(output_path)

                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(
                        f"Generating {config.name}: {i}/{total}"
                    )

            self.stats[config.name] = total
            self.stats[f"{config.name}_changed"] = changed

    def _generate_manuscript_entities(
        self,
        session: Session,
        builder: WikiContextBuilder,
        entity_type: Optional[str] = None,
    ) -> None:
        """
        Generate wiki pages for all manuscript entity types.

        Iterates manuscript configs, queries entities, builds contexts,
        renders templates.

        Args:
            session: Active SQLAlchemy session
            builder: WikiContextBuilder instance
            entity_type: Optional filter to generate only one type
        """
        for config in MANUSCRIPT_CONFIGS:
            if entity_type and config.name != entity_type:
                continue

            entities = session.query(config.model).all()
            total = len(entities)
            changed = 0

            for i, entity in enumerate(entities, 1):
                if not config.should_generate(entity):
                    continue

                context_fn = getattr(builder, config.context_method)
                ctx = context_fn(entity)
                filename = config.filename_fn(entity)
                output_path = self.output_dir / config.output_subdir / filename

                if self.renderer.render_to_file(
                    config.template, ctx, output_path
                ):
                    changed += 1

                self.generated_files.add(output_path)

                if i % 100 == 0 or i == total:
                    safe_logger(self.logger).log_debug(
                        f"Generating {config.name}: {i}/{total}"
                    )

            self.stats[config.name] = total
            self.stats[f"{config.name}_changed"] = changed

    def _generate_indexes(
        self,
        session: Session,
        builder: WikiContextBuilder,
    ) -> None:
        """
        Generate all index pages.

        Args:
            session: Active SQLAlchemy session
            builder: WikiContextBuilder instance
        """
        for config in INDEX_CONFIGS:
            context_fn = getattr(self, config.context_method)
            ctx = context_fn(session)
            output_path = self.output_dir / config.output_path

            self.renderer.render_to_file(
                config.template, ctx, output_path
            )
            self.generated_files.add(output_path)

    def _cleanup_orphans(self) -> None:
        """
        Remove wiki files that no longer correspond to DB entities.

        Walks the output directory and removes any .md files not in
        the generated_files set.
        """
        if not self.output_dir.exists():
            return

        removed = 0
        for md_file in self.output_dir.rglob("*.md"):
            if md_file not in self.generated_files:
                md_file.unlink()
                removed += 1

        if removed:
            safe_logger(self.logger).log_info(
                f"Removed {removed} orphaned wiki files"
            )
        self.stats["orphans_removed"] = removed

    # ==============================================================
    #  INDEX CONTEXT BUILDERS
    # ==============================================================

    def _build_main_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for main index page.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with section counts and links
        """
        return {
            "entry_count": session.query(Entry).count(),
            "person_count": session.query(Person).count(),
            "location_count": session.query(Location).count(),
            "city_count": session.query(City).count(),
            "event_count": session.query(Event).count(),
            "arc_count": session.query(Arc).count(),
            "tag_count": session.query(Tag).count(),
            "theme_count": session.query(Theme).count(),
            "poem_count": session.query(Poem).count(),
            "reference_count": session.query(ReferenceSource).count(),
            "motif_count": session.query(Motif).count(),
        }

    def _build_people_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for People index page.

        Groups people by relation type with entry counts.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with people grouped by relation
        """
        people = session.query(Person).all()
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for person in people:
            if person.relation_type == RelationType.SELF:
                continue
            rel = (
                person.relation_type.value.capitalize()
                if person.relation_type
                else "Uncategorized"
            )
            groups[rel].append({
                "display_name": person.display_name,
                "slug": person.slug,
                "entry_count": person.entry_count,
            })

        # Sort each group by entry count descending
        for rel in groups:
            groups[rel].sort(key=lambda p: p["entry_count"], reverse=True)

        return {"groups": dict(groups), "total": len(people)}

    def _build_places_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for Places index page.

        Nests locations under cities.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with cities and their locations
        """
        cities = session.query(City).all()
        result = []
        for city in sorted(cities, key=lambda c: c.entry_count, reverse=True):
            locs = sorted(
                city.locations,
                key=lambda l: l.entry_count,
                reverse=True,
            )
            result.append({
                "name": city.name,
                "country": city.country,
                "entry_count": city.entry_count,
                "locations": [
                    {
                        "name": loc.name,
                        "entry_count": loc.entry_count,
                    }
                    for loc in locs
                    if loc.entry_count >= 3
                ],
            })
        return {"cities": result}

    def _build_entries_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for Entry index page (year → month listing).

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with hierarchical entry listing
        """
        entries = (
            session.query(Entry)
            .order_by(Entry.date.desc())
            .all()
        )
        builder = WikiContextBuilder(session)
        return {"entries": builder._build_entry_listing(entries)}

    def _build_events_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for Event index page (nested under arcs).

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with arcs and their events
        """
        arcs = session.query(Arc).all()
        events = session.query(Event).all()

        # Map events to arcs
        builder = WikiContextBuilder(session)
        arc_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        unlinked: List[Dict[str, Any]] = []

        for event in events:
            arc_name = builder._find_event_arc(event)
            event_dict = {
                "name": event.name,
                "scene_count": event.scene_count,
                "entry_count": event.entry_count,
            }
            if arc_name:
                arc_events[arc_name].append(event_dict)
            else:
                unlinked.append(event_dict)

        result = [
            {"name": name, "events": evts}
            for name, evts in sorted(arc_events.items())
        ]
        if unlinked:
            result.append({"name": "Unlinked", "events": unlinked})

        return {"arc_groups": result}

    def _build_arcs_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for Arc index page.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with all arcs and their metadata
        """
        arcs = session.query(Arc).all()
        return {
            "arcs": [
                {
                    "name": arc.name,
                    "description": arc.description,
                    "entry_count": arc.entry_count,
                    "first_date": (
                        arc.first_entry_date.isoformat()
                        if arc.first_entry_date else None
                    ),
                    "last_date": (
                        arc.last_entry_date.isoformat()
                        if arc.last_entry_date else None
                    ),
                }
                for arc in sorted(
                    arcs, key=lambda a: a.entry_count, reverse=True
                )
            ]
        }

    def _build_tags_themes_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for Tags & Themes index page.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with frequency-sorted tags and themes
        """
        tags = session.query(Tag).all()
        themes = session.query(Theme).all()

        return {
            "tags": [
                {"name": t.name, "count": t.usage_count}
                for t in sorted(
                    tags, key=lambda t: t.usage_count, reverse=True
                )
                if t.usage_count >= 2
            ],
            "themes": [
                {"name": t.name, "count": t.usage_count}
                for t in sorted(
                    themes, key=lambda t: t.usage_count, reverse=True
                )
                if t.usage_count >= 2
            ],
        }

    def _build_poems_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for Poems index page.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with all poems and version counts
        """
        poems = session.query(Poem).all()
        return {
            "poems": [
                {
                    "title": p.title,
                    "version_count": p.version_count,
                    "first_appearance": (
                        p.first_appearance.isoformat()
                        if p.first_appearance else None
                    ),
                }
                for p in sorted(poems, key=lambda p: p.title)
            ]
        }

    def _build_references_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for References index page.

        Groups sources by type.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with sources grouped by type
        """
        sources = session.query(ReferenceSource).all()
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for source in sources:
            type_name = source.type.value if source.type else "other"
            groups[type_name].append({
                "title": source.title,
                "author": source.author,
                "reference_count": source.reference_count,
            })

        # Sort each group by reference count
        for type_name in groups:
            groups[type_name].sort(
                key=lambda s: s["reference_count"], reverse=True
            )

        return {"groups": dict(groups)}

    def _build_manuscript_index_context(
        self, session: Session
    ) -> Dict[str, Any]:
        """
        Build context for Manuscript index page.

        Includes parts with their chapters, unassigned chapters,
        and total counts for characters and manuscript scenes.

        Args:
            session: Active SQLAlchemy session

        Returns:
            Dict with parts, unassigned_chapters, character_count,
            scene_count
        """
        builder = WikiContextBuilder(session)
        parts = session.query(Part).all()
        all_chapters = session.query(Chapter).all()

        # Find chapters not assigned to any part
        assigned_ids = set()
        for part in parts:
            for ch in part.chapters:
                assigned_ids.add(ch.id)

        unassigned = [ch for ch in all_chapters if ch.id not in assigned_ids]

        return {
            "parts": [builder.build_part_context(p) for p in parts],
            "unassigned_chapters": [
                {
                    "title": ch.title,
                    "number": ch.number,
                    "type": ch.type_display,
                    "status": ch.status_display,
                }
                for ch in unassigned
            ],
            "character_count": session.query(Character).count(),
            "scene_count": session.query(ManuscriptScene).count(),
        }
