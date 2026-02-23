#!/usr/bin/env python3
"""
context.py
----------
Context builders for wiki template rendering.

Transforms SQLAlchemy model instances into plain dict structures
suitable for Jinja2 templates. Each builder method queries an entity's
relationships and computes aggregates (frequencies, co-occurrences,
timeline distributions) needed by the wiki page templates.

Key Features:
    - One builder method per entity type (Entry, Person, Location, etc.)
    - Aggregate helpers for timeline tables, co-occurrences, frequent people
    - Tier-aware rendering (narrator/frequent/infrequent for people, etc.)
    - Narrator exclusion from frequency lists
    - All computation is batch-friendly (no lazy queries in templates)

Design:
    - Context dicts use plain types (str, int, list, dict) — no ORM objects
    - People referenced by display_name, locations by name
    - Entries referenced by date string (YYYY-MM-DD)
    - All lists pre-sorted for template consumption

Usage:
    from dev.wiki.context import WikiContextBuilder

    builder = WikiContextBuilder(session)
    ctx = builder.build_entry_context(entry)
    # Pass ctx to renderer.render("journal/entry.jinja2", ctx)

Dependencies:
    - SQLAlchemy session with loaded entity relationships
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import calendar
from collections import Counter, defaultdict
from datetime import date
from typing import Any, Dict, List, Optional, Set

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
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
    Scene,
    Tag,
    Theme,
)
from dev.database.models.enums import RelationType
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptScene,
    Part,
)
from dev.utils.slugify import slugify


# ==================== Thresholds ====================

FREQUENT_PERSON_THRESHOLD = 20
FREQUENT_LOCATION_THRESHOLD = 20
MID_LOCATION_THRESHOLD = 3
TAG_DASHBOARD_THRESHOLD = 5
REFSOURCE_SUBPAGE_THRESHOLD = 15
MOTIF_SUBPAGE_THRESHOLD = 15
EVENT_SUBPAGE_THRESHOLD = 15
CO_OCCURRENCE_MIN_ENTRIES = 5
CO_OCCURRENCE_MIN_OVERLAP = 3


class WikiContextBuilder:
    """
    Builds template context dicts from database entities.

    Each ``build_*_context`` method takes an ORM entity and returns
    a flat dict of template variables. Aggregate computations are
    performed eagerly so templates remain logic-free.

    Attributes:
        session: Active SQLAlchemy session
    """

    def __init__(self, session: Session) -> None:
        """
        Initialize context builder.

        Args:
            session: Active SQLAlchemy session with entities loaded
        """
        self.session = session

    # ==============================================================
    #  ENTRY
    # ==============================================================

    def build_entry_context(self, entry: Entry) -> Dict[str, Any]:
        """
        Build context dict for an Entry wiki page.

        Computes people grouped by relation, places nested by city,
        events with arc labels, threads with full display data,
        and compact theme/tag lists.

        Args:
            entry: Entry model instance with relationships loaded

        Returns:
            Dict with keys: entry_date, date_str, summary, rating,
            word_count, reading_time, people_groups, places, events,
            threads, themes, tags, references, poems
        """
        return {
            "entry_date": entry.date,
            "date_str": entry.date.isoformat(),
            "summary": entry.summary,
            "rating": entry.rating,
            "word_count": entry.word_count,
            "reading_time": entry.reading_time_display,
            "people_groups": self._build_people_groups(entry.people),
            "places": self._build_places(entry.locations, entry.cities),
            "narrative": self._build_entry_narrative(
                entry.scenes, entry.events, entry.arcs
            ),
            "threads": [self._build_thread_display(t) for t in entry.threads],
            "themes": [t.name for t in entry.themes],
            "tags": [t.name for t in entry.tags],
            "references": self._build_entry_references(entry.references),
            "poems": self._build_entry_poems(entry.poems),
            "motifs": [
                mi.motif.name
                for mi in entry.motif_instances
                if mi.motif
            ],
        }

    def _build_people_groups(
        self, people: List[Person]
    ) -> List[Dict[str, Any]]:
        """
        Group people by relation type, excluding narrator.

        If most people lack relation_type, returns a flat alphabetical
        list. Otherwise groups by relation with "Uncategorized" bucket.

        Args:
            people: List of Person entities

        Returns:
            List of dicts with keys: relation (str or None), names (list of str)
        """
        # Exclude narrator
        non_narrator = [
            p for p in people
            if p.relation_type != RelationType.SELF
        ]
        if not non_narrator:
            return []

        # Check if enough people have relation_type for grouping
        categorized = [p for p in non_narrator if p.relation_type]
        if len(categorized) < len(non_narrator) / 2:
            # Flat alphabetical list
            names = sorted(p.display_name for p in non_narrator)
            return [{"relation": None, "names": names}]

        # Group by relation type
        groups: Dict[Optional[str], List[str]] = defaultdict(list)
        # Define display order
        relation_order = [
            RelationType.ROMANTIC,
            RelationType.FAMILY,
            RelationType.FRIEND,
            RelationType.COLLEAGUE,
            RelationType.PROFESSIONAL,
            RelationType.ACQUAINTANCE,
            RelationType.PUBLIC,
            RelationType.OTHER,
        ]
        for person in non_narrator:
            rel = person.relation_type
            display = rel.value.capitalize() if rel else "Uncategorized"
            groups[display].append(person.display_name)

        result = []
        # Add in defined order
        for rel_type in relation_order:
            label = rel_type.value.capitalize()
            if label in groups:
                result.append({
                    "relation": label,
                    "names": sorted(groups[label]),
                })
        # Add uncategorized last
        if "Uncategorized" in groups:
            result.append({
                "relation": "Uncategorized",
                "names": sorted(groups["Uncategorized"]),
            })
        return result

    def _build_places(
        self,
        locations: List[Location],
        cities: List[City],
    ) -> List[Dict[str, Any]]:
        """
        Build nested City → Location structure for places.

        Args:
            locations: Entry's locations
            cities: Entry's cities

        Returns:
            List of dicts with keys: name, locations, neighborhoods
        """
        if not locations and not cities:
            return []

        # Group locations by city, then by neighborhood
        city_data: Dict[str, Dict[Optional[str], List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for loc in locations:
            city_data[loc.city.name][loc.neighborhood].append(loc.name)

        result = []
        for city_name in sorted(city_data.keys()):
            hood_groups = city_data[city_name]
            neighborhoods = []
            ungrouped: List[str] = []

            for hood_name, locs in sorted(
                hood_groups.items(),
                key=lambda x: (x[0] is None, x[0] or ""),
            ):
                if hood_name is None:
                    ungrouped = sorted(locs)
                else:
                    neighborhoods.append({
                        "name": hood_name,
                        "locations": sorted(locs),
                    })

            result.append({
                "name": city_name,
                "locations": ungrouped,
                "neighborhoods": neighborhoods,
            })

        return result

    def _build_entry_narrative(
        self,
        scenes: List[Scene],
        events: List[Event],
        arcs: List[Arc],
    ) -> List[Dict[str, Any]]:
        """
        Build arc-grouped narrative structure for an entry page.

        Groups events by arc, with each event listing only the
        scenes from this entry. Standalone events (no arc) are
        grouped under a None-named bucket. Scenes not linked to
        any event appear under a standalone scenes bucket.

        Args:
            scenes: Entry's Scene entities
            events: Entry's Event entities
            arcs: Entry's Arc entities

        Returns:
            List of arc group dicts:
              - name: str or None (arc name, None for standalone)
              - events: list of event dicts:
                  - name: str (event name)
                  - scenes: list of scene dicts:
                      - name: str
                      - dates: list of date objects
        """
        entry_scene_ids = {s.id for s in scenes}

        # Map event → arc name
        event_arc: Dict[int, Optional[str]] = {}
        for event in events:
            arc_name = None
            for arc in arcs:
                arc_entry_ids = {e.id for e in arc.entries}
                event_entry_ids = {e.id for e in event.entries}
                if arc_entry_ids & event_entry_ids:
                    arc_name = arc.name
                    break
            event_arc[event.id] = arc_name

        # Build event dicts with only this entry's scenes
        claimed_scene_ids: Set[int] = set()
        arc_events: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(
            list
        )
        for event in events:
            event_scenes = [
                {
                    "name": s.name,
                    "dates": [sd.date for sd in s.dates],
                }
                for s in event.scenes
                if s.id in entry_scene_ids
            ]
            claimed_scene_ids.update(
                s.id for s in event.scenes if s.id in entry_scene_ids
            )
            arc_events[event_arc[event.id]].append({
                "name": event.name,
                "scenes": event_scenes,
            })

        # Collect unclaimed scenes (not linked to any event)
        unclaimed = [
            {
                "name": s.name,
                "dates": [sd.date for sd in s.dates],
            }
            for s in scenes
            if s.id not in claimed_scene_ids
        ]

        # Build ordered result: named arcs first, then standalone
        result = []
        for arc in arcs:
            if arc.name in arc_events:
                result.append({
                    "name": arc.name,
                    "events": arc_events.pop(arc.name),
                })
        # Standalone events (no arc)
        if None in arc_events:
            result.append({
                "name": None,
                "events": arc_events[None],
            })
        # Unclaimed scenes as pseudo-events
        if unclaimed:
            standalone_bucket = next(
                (g for g in result if g["name"] is None), None
            )
            if standalone_bucket is None:
                standalone_bucket = {"name": None, "events": []}
                result.append(standalone_bucket)
            standalone_bucket["events"].append({
                "name": None,
                "scenes": unclaimed,
            })

        return result

    def _build_thread_display(self, thread: Any) -> Dict[str, Any]:
        """
        Build thread display dict from Thread model.

        Args:
            thread: Thread model instance

        Returns:
            Dict with keys: name, from_date, to_date,
            referenced_entry_date, content, people, locations
        """
        # Group locations by city
        loc_groups: Dict[str, List[str]] = defaultdict(list)
        for loc in thread.locations:
            loc_groups[loc.city.name].append(loc.name)

        locations = [
            {"city": city, "names": names}
            for city, names in sorted(loc_groups.items())
        ]

        return {
            "name": thread.name,
            "from_date": thread.from_date,
            "to_date": thread.to_date,
            "referenced_entry_date": (
                thread.referenced_entry_date.isoformat()
                if thread.referenced_entry_date
                else None
            ),
            "content": thread.content,
            "people": [p.display_name for p in thread.people],
            "locations": locations,
        }

    def _build_entry_references(
        self, references: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Build reference display list for Entry page.

        Args:
            references: Entry's Reference instances

        Returns:
            List of dicts with keys: content, source_title, author, mode
        """
        result = []
        for ref in references:
            result.append({
                "content": ref.content or ref.description or "",
                "source_title": ref.source.title,
                "author": ref.source.author,
                "mode": ref.mode.value if ref.mode else "thematic",
            })
        return result

    def _build_entry_poems(
        self, poem_versions: List[Any]
    ) -> List[Dict[str, Any]]:
        """
        Build poem display list for Entry page.

        Args:
            poem_versions: Entry's PoemVersion instances

        Returns:
            List of dicts with keys: title, version
        """
        result = []
        for pv in poem_versions:
            # Compute version number (chronological order)
            all_versions = sorted(
                pv.poem.versions,
                key=lambda v: v.entry.date if v.entry else date.min,
            )
            version_num = next(
                (i + 1 for i, v in enumerate(all_versions) if v.id == pv.id),
                None,
            )
            result.append({
                "title": pv.poem.title,
                "version": version_num,
            })
        return result

    # ==============================================================
    #  PERSON
    # ==============================================================

    def build_person_context(self, person: Person) -> Dict[str, Any]:
        """
        Build context dict for a Person wiki page.

        Auto-selects tier (narrator/frequent/infrequent) based on
        entry_count and relation_type. Each tier produces different
        context keys for its template layout.

        Args:
            person: Person model instance

        Returns:
            Dict with tier-appropriate context. Common keys: display_name,
            relation, entry_count, slug, tier. Tier-specific keys vary.
        """
        is_narrator = person.relation_type == RelationType.SELF
        entry_count = person.entry_count

        aliases = [a.alias for a in person.aliases] if person.aliases else []

        base = {
            "display_name": person.display_name,
            "slug": person.slug,
            "aliases": aliases,
            "relation": (
                person.relation_type.value if person.relation_type else None
            ),
            "entry_count": entry_count,
            "first_appearance": (
                person.first_appearance.isoformat()
                if person.first_appearance else None
            ),
            "last_appearance": (
                person.last_appearance.isoformat()
                if person.last_appearance else None
            ),
            "characters": self._build_character_mappings(person),
        }

        if is_narrator:
            base["tier"] = "narrator"
            base["top_companions"] = self._build_top_companions(person)
            base["top_places"] = self._build_person_top_places(person)
        elif entry_count >= FREQUENT_PERSON_THRESHOLD:
            base["tier"] = "frequent"
            base["has_entries_subpage"] = True
            base["date_range"] = self._date_range_str(
                person.first_appearance, person.last_appearance
            )
            base["arc_event_spine"] = self._build_arc_event_spine(person)
            base["entries"] = self._build_entry_listing(
                sorted(person.entries, key=lambda e: e.date, reverse=True)
            )
            base["entries_outside_events"] = (
                self._build_entries_outside_events(person)
            )
            base["places"] = self._build_person_top_places(person)
            base["companions"] = self._build_companions(person)
            base["threads"] = [
                self._build_thread_display(t) for t in person.threads
            ]
        else:
            base["tier"] = "infrequent"
            base["entries"] = self._build_entry_listing(
                sorted(person.entries, key=lambda e: e.date, reverse=True)
            )
            base["places"] = self._build_person_places_simple(person)

        return base

    def _build_top_companions(
        self, person: Person, limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Compute top co-appearing people for narrator page.

        Groups companions by relation type with entry counts.

        Args:
            person: The narrator Person
            limit: Maximum companions to return

        Returns:
            List of relation groups with companion lists
        """
        # Count co-appearances via shared entries
        co_counts: Counter = Counter()
        for entry in person.entries:
            for other in entry.people:
                if other.id != person.id:
                    co_counts[other.id] = co_counts.get(other.id, 0) + 1

        # Get top people
        top_ids = [pid for pid, _ in co_counts.most_common(limit)]
        top_people = [
            p for p in self.session.query(Person).filter(
                Person.id.in_(top_ids)
            ).all()
        ] if top_ids else []

        # Build lookup
        people_by_id = {p.id: p for p in top_people}

        # Group by relation
        groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for pid, count in co_counts.most_common(limit):
            p = people_by_id.get(pid)
            if not p:
                continue
            rel = p.relation_type.value.capitalize() if p.relation_type else "Uncategorized"
            groups[rel].append({
                "name": p.display_name,
                "count": count,
            })

        # Order groups
        relation_order = [
            "Romantic", "Family", "Friend", "Colleague",
            "Professional", "Acquaintance", "Public", "Other",
            "Uncategorized",
        ]
        result = []
        for rel in relation_order:
            if rel in groups:
                result.append({
                    "relation": rel,
                    "companions": sorted(
                        groups[rel], key=lambda x: x["count"], reverse=True
                    ),
                })
        return result

    def _build_person_top_places(
        self, person: Person, limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Compute top locations for a person, nested by city.

        Uses scene-level data (scene_people + scene_locations join).

        Args:
            person: Person entity
            limit: Max locations per city

        Returns:
            List of city dicts with location lists and counts
        """
        loc_entries: Dict[tuple, set] = defaultdict(set)
        loc_hoods: Dict[tuple, Optional[str]] = {}
        for scene in person.scenes:
            for loc in scene.locations:
                key = (loc.city.name, loc.name)
                loc_entries[key].add(scene.entry_id)
                loc_hoods[key] = loc.neighborhood
        loc_counts: Counter = Counter(
            {key: len(eids) for key, eids in loc_entries.items()}
        )

        # Group by city, then by neighborhood
        city_hood_locs: Dict[
            str, Dict[Optional[str], List[Dict[str, Any]]]
        ] = defaultdict(lambda: defaultdict(list))
        for (city_name, loc_name), count in loc_counts.most_common():
            hood = loc_hoods.get((city_name, loc_name))
            city_hood_locs[city_name][hood].append({
                "name": loc_name, "count": count,
            })

        result = []
        for city_name in sorted(city_hood_locs.keys()):
            hood_groups = city_hood_locs[city_name]
            neighborhoods = []
            ungrouped: List[Dict[str, Any]] = []

            for hood_name, locs in sorted(
                hood_groups.items(),
                key=lambda x: (x[0] is None, x[0] or ""),
            ):
                trimmed = locs[:limit]
                if hood_name is None:
                    ungrouped = trimmed
                else:
                    neighborhoods.append({
                        "name": hood_name,
                        "locations": trimmed,
                    })

            result.append({
                "name": city_name,
                "neighborhoods": neighborhoods,
                "locations": ungrouped,
            })
        return result

    def _build_person_places_simple(
        self, person: Person
    ) -> List[Dict[str, Any]]:
        """
        Build simple city-grouped location list for infrequent people.

        Args:
            person: Person entity

        Returns:
            List of city dicts with location name lists
        """
        city_locs: Dict[str, Set[str]] = defaultdict(set)
        for scene in person.scenes:
            for loc in scene.locations:
                city_locs[loc.city.name].add(loc.name)

        return [
            {"name": city, "locations": sorted(locs)}
            for city, locs in sorted(city_locs.items())
        ]

    def _build_arc_event_spine(
        self, person: Person
    ) -> List[Dict[str, Any]]:
        """
        Build Arc → Event → Entry hierarchy for frequent people.

        Traverses: Person → Scene → Event → Entry → Arc to build
        the narrative spine showing how this person weaves through arcs.

        Args:
            person: Person entity

        Returns:
            List of arc dicts, each with nested event dicts
        """
        # Collect events involving this person
        person_events: Dict[int, Event] = {}
        for scene in person.scenes:
            for event in scene.events:
                person_events[event.id] = event

        # Group events by arc
        arc_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        unlinked_events: List[Dict[str, Any]] = []

        for event in person_events.values():
            # Find arc for this event
            event_arc = None
            for entry in event.entries:
                for arc in entry.arcs:
                    arc_entry_ids = {e.id for e in arc.entries}
                    event_entry_ids = {e.id for e in event.entries}
                    if arc_entry_ids & event_entry_ids:
                        event_arc = arc
                        break
                if event_arc:
                    break

            # Get entries where this person appears with this event
            person_entry_ids = {e.id for e in person.entries}
            event_entries = sorted(
                [e for e in event.entries if e.id in person_entry_ids],
                key=lambda e: e.date,
            )
            entry_dates = [e.date.isoformat() for e in event_entries]

            event_dict = {
                "name": event.name,
                "description": (
                    event.scenes[0].description
                    if event.scenes else ""
                ),
                "entry_dates": entry_dates,
            }

            if event_arc:
                arc_events[event_arc.name].append(event_dict)
            else:
                unlinked_events.append(event_dict)

        # Sort helper: earliest entry_date
        def _event_sort_key(ev: Dict[str, Any]) -> str:
            return ev["entry_dates"][0] if ev["entry_dates"] else "9999"

        # Build result
        result = []
        for arc_name, events in sorted(arc_events.items()):
            # Get arc details
            arc = self.session.query(Arc).filter(
                Arc.name == arc_name
            ).first()
            arc_entries = [
                e for e in (arc.entries if arc else [])
                if e.id in {e.id for e in person.entries}
            ]
            result.append({
                "name": arc_name,
                "entry_count": len(arc_entries),
                "date_range": self._date_range_str(
                    min((e.date for e in arc_entries), default=None),
                    max((e.date for e in arc_entries), default=None),
                ) if arc_entries else "",
                "events": sorted(events, key=_event_sort_key),
            })

        if unlinked_events:
            result.append({
                "name": "Standalone events",
                "entry_count": None,
                "date_range": None,
                "events": sorted(unlinked_events, key=_event_sort_key),
            })

        return result

    def _build_entries_outside_events(
        self, person: Person
    ) -> List[Dict[str, Any]]:
        """
        Find entries where person appears but not in any event.

        Args:
            person: Person entity

        Returns:
            Hierarchical entry listing (year → month groups)
        """
        # Collect entries that appear in events via person's scenes
        event_entry_ids: Set[int] = set()
        for scene in person.scenes:
            for event in scene.events:
                for entry in event.entries:
                    event_entry_ids.add(entry.id)

        outside = [
            e for e in person.entries if e.id not in event_entry_ids
        ]
        return self._build_entry_listing(
            sorted(outside, key=lambda e: e.date, reverse=True)
        )

    def _build_companions(
        self, person: Person, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Build co-appearing people list for frequent person page.

        Args:
            person: Person entity
            limit: Max companions to return

        Returns:
            List of dicts with name and shared count
        """
        co_counts: Counter = Counter()
        for entry in person.entries:
            for other in entry.people:
                if (
                    other.id != person.id
                    and other.relation_type != RelationType.SELF
                ):
                    co_counts[other.id] += 1

        top_ids = [pid for pid, _ in co_counts.most_common(limit)]
        people_by_id = {
            p.id: p
            for p in self.session.query(Person).filter(
                Person.id.in_(top_ids)
            ).all()
        } if top_ids else {}

        return [
            {
                "name": people_by_id[pid].display_name,
                "count": count,
            }
            for pid, count in co_counts.most_common(limit)
            if pid in people_by_id
        ]

    def _build_character_mappings(
        self, person: Person
    ) -> List[Dict[str, Any]]:
        """
        Build manuscript character mapping list.

        Args:
            person: Person entity

        Returns:
            List of dicts with character name and contribution type
        """
        return [
            {
                "name": mapping.character.name,
                "contribution": mapping.contribution.value,
            }
            for mapping in person.character_mappings
        ]

    # ==============================================================
    #  LOCATION
    # ==============================================================

    def build_location_context(self, location: Location) -> Dict[str, Any]:
        """
        Build context dict for a Location wiki page.

        Auto-selects tier (20+/3-19/1-2) based on entry count.

        Args:
            location: Location model instance

        Returns:
            Dict with tier-appropriate context
        """
        entry_count = location.entry_count

        city_slug = slugify(location.city.name)
        loc_slug = slugify(location.name)

        base: Dict[str, Any] = {
            "name": location.name,
            "city": location.city.name,
            "neighborhood": location.neighborhood,
            "slug": loc_slug,
            "metadata_id": f"{city_slug}/{loc_slug}",
            "entry_count": entry_count,
            "first_visit": (
                location.first_visit.isoformat()
                if location.first_visit else None
            ),
            "last_visit": (
                location.last_visit.isoformat()
                if location.last_visit else None
            ),
        }

        if entry_count >= FREQUENT_LOCATION_THRESHOLD:
            base["tier"] = "dashboard"
            base["has_entries_subpage"] = True
            base["date_range"] = self._date_range_str(
                location.first_visit, location.last_visit
            )
            base["timeline"] = self._compute_monthly_counts(
                location.entries
            )
            base["events_here"] = self._build_location_events(location)
            base["entries"] = self._build_entry_listing(
                sorted(
                    location.entries, key=lambda e: e.date, reverse=True
                )
            )
            base["entries_outside_events"] = (
                self._build_location_entries_outside_events(location)
            )
            base["frequent_people"] = self._build_location_people(location)
            base["threads"] = [
                self._build_thread_display(t) for t in location.threads
            ]
        elif entry_count >= MID_LOCATION_THRESHOLD:
            base["tier"] = "mid"
            base["date_range"] = self._date_range_str(
                location.first_visit, location.last_visit
            )
            base["events_here"] = self._build_location_events(location)
            base["entries"] = self._build_entry_listing(
                sorted(
                    location.entries, key=lambda e: e.date, reverse=True
                )
            )
            base["frequent_people"] = self._build_location_people(location)
        else:
            base["tier"] = "minimal"
            base["entries"] = self._build_entry_listing(
                sorted(
                    location.entries, key=lambda e: e.date, reverse=True
                )
            )

        return base

    def _build_location_events(
        self, location: Location
    ) -> List[Dict[str, Any]]:
        """
        Build events-at-this-location structure, nested under arcs.

        Args:
            location: Location entity

        Returns:
            List of arc dicts with nested event dicts
        """
        # Find events via scenes at this location
        loc_events: Dict[int, Event] = {}
        for scene in location.scenes:
            for event in scene.events:
                loc_events[event.id] = event

        arc_events: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        unlinked: List[Dict[str, Any]] = []

        for event in loc_events.values():
            event_arc = self._find_event_arc(event)
            entry_dates = sorted(
                [e.date.isoformat() for e in event.entries]
            )
            event_dict = {
                "name": event.name,
                "description": (
                    event.scenes[0].description if event.scenes else ""
                ),
                "entry_dates": entry_dates,
            }
            if event_arc:
                arc_events[event_arc].append(event_dict)
            else:
                unlinked.append(event_dict)

        def _event_sort_key(ev: Dict[str, Any]) -> str:
            return ev["entry_dates"][0] if ev["entry_dates"] else "9999"

        result = []
        for arc_name, events in sorted(arc_events.items()):
            result.append({
                "name": arc_name,
                "events": sorted(events, key=_event_sort_key),
            })
        if unlinked:
            result.append({
                "name": "Standalone events",
                "events": sorted(unlinked, key=_event_sort_key),
            })
        return result

    def _build_location_people(
        self, location: Location, limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Compute frequent people at a location via scene joins.

        For each person, collects the entry IDs where they co-occur
        with this location, then resolves those to sorted date strings.
        Templates use ``entry_dates`` for inline display (<=5 entries)
        or link to a subpage (>5 entries).

        Args:
            location: Location entity
            limit: Max people to return

        Returns:
            List of dicts with keys: name, slug, count, entry_dates,
            entry_ids. Narrator excluded.
        """
        people_entries: Dict[int, set] = defaultdict(set)
        for scene in location.scenes:
            for person in scene.people:
                if person.relation_type != RelationType.SELF:
                    people_entries[person.id].add(scene.entry_id)
        people_counts: Counter = Counter(
            {pid: len(eids) for pid, eids in people_entries.items()}
        )

        top_ids = [pid for pid, _ in people_counts.most_common(limit)]
        people_by_id = {
            p.id: p
            for p in self.session.query(Person).filter(
                Person.id.in_(top_ids)
            ).all()
        } if top_ids else {}

        # Resolve entry dates for each person
        all_entry_ids: Set[int] = set()
        for pid in top_ids:
            all_entry_ids.update(people_entries[pid])
        entry_date_map: Dict[int, str] = {}
        if all_entry_ids:
            for entry in self.session.query(Entry).filter(
                Entry.id.in_(all_entry_ids)
            ).all():
                entry_date_map[entry.id] = entry.date.isoformat()

        result = []
        for pid, count in people_counts.most_common(limit):
            person = people_by_id.get(pid)
            if not person:
                continue
            eids = people_entries[pid]
            dates = sorted(
                (entry_date_map[eid] for eid in eids if eid in entry_date_map),
                reverse=True,
            )
            result.append({
                "name": person.display_name,
                "slug": person.slug,
                "count": count,
                "entry_dates": dates,
                "entry_ids": sorted(eids),
            })

        return result

    def _build_location_entries_outside_events(
        self, location: Location
    ) -> List[Dict[str, Any]]:
        """
        Find entries at this location not covered by events.

        Args:
            location: Location entity

        Returns:
            Hierarchical entry listing
        """
        event_entry_ids: Set[int] = set()
        for scene in location.scenes:
            for event in scene.events:
                for entry in event.entries:
                    event_entry_ids.add(entry.id)

        outside = [
            e for e in location.entries if e.id not in event_entry_ids
        ]
        return self._build_entry_listing(
            sorted(outside, key=lambda e: e.date, reverse=True)
        )

    # ==============================================================
    #  CITY
    # ==============================================================

    def build_city_context(self, city: City) -> Dict[str, Any]:
        """
        Build context dict for a City wiki page.

        Args:
            city: City model instance

        Returns:
            Dict with city overview, top locations, timeline
        """
        locations = sorted(
            city.locations, key=lambda l: l.entry_count, reverse=True
        )

        # Group locations by neighborhood
        hood_locs: Dict[Optional[str], List[Dict[str, Any]]] = defaultdict(
            list
        )
        for loc in locations:
            hood_locs[loc.neighborhood].append({
                "name": loc.name,
                "entry_count": loc.entry_count,
            })

        neighborhoods = []
        ungrouped: List[Dict[str, Any]] = []
        for hood_name, locs in sorted(
            hood_locs.items(),
            key=lambda x: (x[0] is None, x[0] or ""),
        ):
            if hood_name is None:
                ungrouped = locs
            else:
                neighborhoods.append({
                    "name": hood_name,
                    "locations": locs,
                })

        any_neighborhoods = len(neighborhoods) > 0

        return {
            "name": city.name,
            "country": city.country,
            "entry_count": city.entry_count,
            "location_count": city.location_count,
            "first_mentioned": (
                city.first_mentioned.isoformat()
                if city.first_mentioned else None
            ),
            "last_mentioned": (
                city.last_mentioned.isoformat()
                if city.last_mentioned else None
            ),
            "date_range": self._date_range_str(
                city.first_mentioned, city.last_mentioned
            ),
            "timeline": self._compute_monthly_counts(city.entries),
            "any_neighborhoods": any_neighborhoods,
            "neighborhoods": neighborhoods,
            "top_locations": ungrouped,
            "frequent_people": self._build_city_people(city),
        }

    def _build_city_people(
        self, city: City, limit: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Compute frequent people across all city locations.

        Args:
            city: City entity
            limit: Max people

        Returns:
            List of dicts with name and count
        """
        people_counts: Counter = Counter()
        for loc in city.locations:
            for scene in loc.scenes:
                for person in scene.people:
                    if person.relation_type != RelationType.SELF:
                        people_counts[person.id] += 1

        top_ids = [pid for pid, _ in people_counts.most_common(limit)]
        people_by_id = {
            p.id: p
            for p in self.session.query(Person).filter(
                Person.id.in_(top_ids)
            ).all()
        } if top_ids else {}

        return [
            {"name": people_by_id[pid].display_name, "count": count}
            for pid, count in people_counts.most_common(limit)
            if pid in people_by_id
        ]

    # ==============================================================
    #  EVENT
    # ==============================================================

    def build_event_context(self, event: Event) -> Dict[str, Any]:
        """
        Build context dict for an Event wiki page.

        Args:
            event: Event model instance

        Returns:
            Dict with event overview, scenes, people, locations, entries
        """
        arc = self._find_event_arc(event)

        # Build scene details
        scenes = []
        for scene in event.scenes:
            # Group locations by city
            loc_groups: Dict[str, List[str]] = defaultdict(list)
            for loc in scene.locations:
                loc_groups[loc.city.name].append(loc.name)

            scenes.append({
                "name": scene.name,
                "description": scene.description,
                "date": scene.primary_date,
                "people": [p.display_name for p in scene.people
                           if p.relation_type != RelationType.SELF],
                "locations": [
                    {"city": city, "names": names}
                    for city, names in sorted(loc_groups.items())
                ],
                "entry_date": scene.entry.date.isoformat(),
            })

        result: Dict[str, Any] = {
            "name": event.name,
            "slug": slugify(event.name),
            "arc": arc,
            "scene_count": event.scene_count,
            "entry_count": event.entry_count,
            "scenes": scenes,
            "entry_dates": sorted(
                [e.date.isoformat() for e in event.entries]
            ),
        }

        if len(scenes) >= EVENT_SUBPAGE_THRESHOLD:
            result["has_scenes_subpage"] = True

        return result

    # ==============================================================
    #  ARC
    # ==============================================================

    def build_arc_context(self, arc: Arc) -> Dict[str, Any]:
        """
        Build context dict for an Arc wiki page.

        Args:
            arc: Arc model instance

        Returns:
            Dict with arc overview, timeline, events, key people/places
        """
        # Collect events in this arc
        arc_entry_ids = {e.id for e in arc.entries}
        all_events = self.session.query(Event).all()
        arc_events = []
        for event in all_events:
            event_entry_ids = {e.id for e in event.entries}
            if event_entry_ids & arc_entry_ids:
                arc_events.append(event)

        # Key people across arc entries
        people_counts: Counter = Counter()
        for entry in arc.entries:
            for person in entry.people:
                if person.relation_type != RelationType.SELF:
                    people_counts[person.id] += 1

        top_people_ids = [
            pid for pid, _ in people_counts.most_common(10)
        ]
        people_by_id = {
            p.id: p
            for p in self.session.query(Person).filter(
                Person.id.in_(top_people_ids)
            ).all()
        } if top_people_ids else {}

        return {
            "name": arc.name,
            "slug": slugify(arc.name),
            "has_entries_subpage": True,
            "description": arc.description,
            "entry_count": arc.entry_count,
            "date_range": self._date_range_str(
                arc.first_entry_date, arc.last_entry_date
            ),
            "timeline": self._compute_monthly_counts(arc.entries),
            "chapters": [
                {"title": ch.title, "type": ch.type_display}
                for ch in arc.chapters
            ],
            "events": sorted(
                [
                    {
                        "name": e.name,
                        "entry_count": e.entry_count,
                        "scene_count": e.scene_count,
                        "entry_dates": sorted(
                            [en.date.isoformat() for en in e.entries]
                        ),
                    }
                    for e in arc_events
                ],
                key=lambda ev: ev["entry_dates"][0] if ev["entry_dates"] else "9999",
            ),
            "frequent_people": [
                {
                    "name": people_by_id[pid].display_name,
                    "count": count,
                }
                for pid, count in people_counts.most_common(10)
                if pid in people_by_id
            ],
            "entries": self._build_entry_listing(
                sorted(arc.entries, key=lambda e: e.date, reverse=True)
            ),
        }

    # ==============================================================
    #  TAG
    # ==============================================================

    def build_tag_context(self, tag: Tag) -> Dict[str, Any]:
        """
        Build context dict for a Tag wiki page.

        Tags with 5+ entries get full dashboard (timeline, patterns,
        frequent people). Tags with 2-4 entries get minimal page.
        Tags with 1 entry get no page (filtered in exporter).

        Args:
            tag: Tag model instance

        Returns:
            Dict with tier-appropriate context
        """
        entry_count = tag.usage_count
        entries = sorted(tag.entries, key=lambda e: e.date, reverse=True)

        base: Dict[str, Any] = {
            "name": tag.name,
            "slug": slugify(tag.name),
            "entry_count": entry_count,
            "entries": self._build_entry_listing(entries),
        }

        if entry_count >= TAG_DASHBOARD_THRESHOLD:
            base["tier"] = "dashboard"
            base["has_entries_subpage"] = True
            base["date_range"] = self._date_range_str(
                entries[-1].date if entries else None,
                entries[0].date if entries else None,
            )
            base["recent_dates"] = [
                e.date.isoformat() for e in entries[:5]
            ]
            base["timeline"] = self._compute_monthly_counts(entries)
            base["patterns"] = self._compute_co_occurrences(entries)
            base["frequent_people"] = self._compute_frequent_people(entries)
        else:
            base["tier"] = "minimal"

        return base

    # ==============================================================
    #  THEME
    # ==============================================================

    def build_theme_context(self, theme: Theme) -> Dict[str, Any]:
        """
        Build context dict for a Theme wiki page.

        Same tier logic as tags but with separate thresholds.

        Args:
            theme: Theme model instance

        Returns:
            Dict with tier-appropriate context
        """
        entry_count = theme.usage_count
        entries = sorted(
            theme.entries, key=lambda e: e.date, reverse=True
        )

        base: Dict[str, Any] = {
            "name": theme.name,
            "slug": slugify(theme.name),
            "entry_count": entry_count,
            "entries": self._build_entry_listing(entries),
        }

        if entry_count >= TAG_DASHBOARD_THRESHOLD:
            base["tier"] = "dashboard"
            base["has_entries_subpage"] = True
            base["date_range"] = self._date_range_str(
                entries[-1].date if entries else None,
                entries[0].date if entries else None,
            )
            base["recent_dates"] = [
                e.date.isoformat() for e in entries[:5]
            ]
            base["timeline"] = self._compute_monthly_counts(entries)
            base["patterns"] = self._compute_co_occurrences(entries)
            base["frequent_people"] = self._compute_frequent_people(entries)
        else:
            base["tier"] = "minimal"

        return base

    # ==============================================================
    #  POEM
    # ==============================================================

    def build_poem_context(self, poem: Poem) -> Dict[str, Any]:
        """
        Build context dict for a Poem wiki page.

        Args:
            poem: Poem model instance

        Returns:
            Dict with poem title, versions, appearances
        """
        versions = sorted(
            poem.versions,
            key=lambda v: v.entry.date if v.entry else date.min,
            reverse=True,
        )
        return {
            "title": poem.title,
            "version_count": poem.version_count,
            "first_appearance": (
                poem.first_appearance.isoformat()
                if poem.first_appearance else None
            ),
            "last_appearance": (
                poem.last_appearance.isoformat()
                if poem.last_appearance else None
            ),
            "versions": [
                {
                    "number": i + 1,
                    "entry_date": v.entry.date.isoformat() if v.entry else None,
                    "content": v.content,
                    "line_count": v.line_count,
                    "word_count": v.word_count,
                }
                for i, v in enumerate(versions)
            ],
            "chapters": [
                {"title": ch.title}
                for ch in poem.chapters
            ],
        }

    # ==============================================================
    #  REFERENCE SOURCE
    # ==============================================================

    def build_reference_source_context(
        self, source: ReferenceSource
    ) -> Dict[str, Any]:
        """
        Build context dict for a Reference Source wiki page.

        Args:
            source: ReferenceSource model instance

        Returns:
            Dict with source info and chronological references
        """
        refs = sorted(
            source.references,
            key=lambda r: r.entry.date if r.entry else date.min,
        )
        all_refs = [
            {
                "entry_date": r.entry.date.isoformat() if r.entry else None,
                "mode": r.mode.value if r.mode else "thematic",
                "content": r.content,
                "description": r.description,
            }
            for r in refs
        ]

        result: Dict[str, Any] = {
            "title": source.title,
            "slug": slugify(source.title),
            "author": source.author,
            "type": source.type.value if source.type else None,
            "url": source.url,
            "reference_count": source.reference_count,
            "first_referenced": (
                source.first_referenced.isoformat()
                if source.first_referenced else None
            ),
            "last_referenced": (
                source.last_referenced.isoformat()
                if source.last_referenced else None
            ),
            "references": all_refs,
        }

        if len(all_refs) >= REFSOURCE_SUBPAGE_THRESHOLD:
            result["has_refs_subpage"] = True
            result["recent_references"] = all_refs[-10:]

        return result

    # ==============================================================
    #  MOTIF
    # ==============================================================

    def build_motif_context(self, motif: Motif) -> Dict[str, Any]:
        """
        Build context dict for a Motif wiki page.

        Args:
            motif: Motif model instance

        Returns:
            Dict with motif name, instance count, entries with descriptions
        """
        instances = sorted(
            motif.instances,
            key=lambda i: i.entry.date if i.entry else date.min,
            reverse=True,
        )
        entries = [i.entry for i in instances if i.entry]

        all_instances = [
            {
                "entry_date": (
                    i.entry.date.isoformat() if i.entry else None
                ),
                "description": i.description,
            }
            for i in instances
        ]

        result: Dict[str, Any] = {
            "name": motif.name,
            "slug": slugify(motif.name),
            "instance_count": motif.instance_count,
            "date_range": self._date_range_str(
                entries[-1].date if entries else None,
                entries[0].date if entries else None,
            ),
            "timeline": self._compute_monthly_counts(entries),
            "instances": all_instances,
            "entries": self._build_entry_listing(
                sorted(entries, key=lambda e: e.date, reverse=True)
            ),
        }

        if len(all_instances) >= MOTIF_SUBPAGE_THRESHOLD:
            result["has_entries_subpage"] = True
            result["recent_instances"] = all_instances[:10]

        return result

    # ==============================================================
    #  CHAPTER
    # ==============================================================

    def build_chapter_context(self, chapter: Chapter) -> Dict[str, Any]:
        """
        Build context dict for a Chapter wiki page.

        Computes characters, arcs, poems, scenes with sources,
        and manuscript references for the chapter.

        Args:
            chapter: Chapter model instance with relationships loaded

        Returns:
            Dict with keys: title, number, type, status, part,
            scene_count, characters, arcs, poems, scenes, references
        """
        return {
            "title": chapter.title,
            "slug": slugify(chapter.title),
            "number": chapter.number,
            "type": chapter.type_display,
            "status": chapter.status_display,
            "part": chapter.part.display_name if chapter.part else None,
            "scene_count": chapter.scene_count,
            "characters": [
                {
                    "name": c.name,
                    "role": c.role,
                }
                for c in chapter.characters
            ],
            "arcs": [{"name": a.name} for a in chapter.arcs],
            "poems": [{"title": p.title} for p in chapter.poems],
            "scenes": [
                {
                    "name": ms.name,
                    "description": ms.description,
                    "origin": ms.origin_display,
                    "status": ms.status_display,
                    "sources": [
                        self._build_manuscript_source(src)
                        for src in ms.sources
                    ],
                }
                for ms in chapter.scenes
            ],
            "references": [
                {
                    "source_title": ref.source.title,
                    "mode": ref.mode_display,
                    "content": ref.content,
                }
                for ref in chapter.references
            ],
        }

    # ==============================================================
    #  CHARACTER
    # ==============================================================

    def build_character_context(
        self, character: Character
    ) -> Dict[str, Any]:
        """
        Build context dict for a Character wiki page.

        Includes chapters where the character appears and
        the real people the character is based on.

        Args:
            character: Character model instance with relationships loaded

        Returns:
            Dict with keys: name, description, role, is_narrator,
            chapter_count, chapters, based_on
        """
        return {
            "name": character.name,
            "slug": slugify(character.name),
            "description": character.description,
            "role": character.role,
            "is_narrator": character.is_narrator,
            "chapter_count": character.chapter_count,
            "chapters": [
                {
                    "title": ch.title,
                    "type": ch.type_display,
                    "status": ch.status_display,
                }
                for ch in character.chapters
            ],
            "based_on": [
                {
                    "person_name": mapping.person.display_name,
                    "person_slug": mapping.person.slug,
                    "contribution": mapping.contribution_display,
                }
                for mapping in character.person_mappings
            ],
        }

    # ==============================================================
    #  MANUSCRIPT SCENE
    # ==============================================================

    def build_manuscript_scene_context(
        self, ms_scene: ManuscriptScene
    ) -> Dict[str, Any]:
        """
        Build context dict for a ManuscriptScene wiki page.

        Includes chapter assignment, origin/status, and
        source material links with entry dates.

        Args:
            ms_scene: ManuscriptScene model instance with relationships loaded

        Returns:
            Dict with keys: name, description, chapter, origin,
            status, sources
        """
        return {
            "name": ms_scene.name,
            "slug": slugify(ms_scene.name),
            "description": ms_scene.description,
            "chapter": ms_scene.chapter.title if ms_scene.chapter else None,
            "origin": ms_scene.origin_display,
            "status": ms_scene.status_display,
            "sources": [
                self._build_manuscript_source(src)
                for src in ms_scene.sources
            ],
        }

    # ==============================================================
    #  PART
    # ==============================================================

    def build_part_context(self, part: Part) -> Dict[str, Any]:
        """
        Build context dict for a Part wiki page.

        Parts are book sections that group chapters. Used
        primarily for the manuscript index page.

        Args:
            part: Part model instance with relationships loaded

        Returns:
            Dict with keys: display_name, number, title,
            chapter_count, chapters
        """
        slug = slugify(part.title) if part.title else f"part-{part.number}"

        # Count scenes across all chapters
        scene_count = sum(
            len(ch.scenes) for ch in part.chapters
        )

        return {
            "display_name": part.display_name,
            "number": part.number,
            "title": part.title,
            "slug": slug,
            "chapter_count": part.chapter_count,
            "scene_count": scene_count,
            "chapters": [
                {
                    "title": ch.title,
                    "number": ch.number,
                    "type": ch.type_display,
                    "status": ch.status_display,
                }
                for ch in part.chapters
            ],
        }

    def _build_manuscript_source(self, src: Any) -> Dict[str, Any]:
        """
        Build context dict for a single ManuscriptSource.

        Breaks the source reference into linkable components
        so templates can wikilink scene names, entry dates,
        and thread names instead of rendering plain text.

        Args:
            src: ManuscriptSource model instance

        Returns:
            Dict with type, reference_name, entry_date, external_note
        """
        from dev.database.models.enums import SourceType

        entry_date = None
        reference_name = None

        if src.source_type == SourceType.SCENE and src.scene:
            reference_name = src.scene.name
            entry_date = src.scene.entry.date.isoformat()
        elif src.source_type == SourceType.ENTRY and src.entry:
            entry_date = src.entry.date.isoformat()
        elif src.source_type == SourceType.THREAD and src.thread:
            reference_name = src.thread.name
            entry_date = src.thread.entry.date.isoformat()
        elif src.source_type == SourceType.EXTERNAL:
            reference_name = src.external_note or ""

        return {
            "type": src.source_type_display,
            "reference_name": reference_name,
            "entry_date": entry_date,
            "external_note": src.external_note if src.source_type == SourceType.EXTERNAL else None,
        }

    # ==============================================================
    #  SHARED HELPERS
    # ==============================================================

    def _compute_monthly_counts(
        self, entries: List[Entry]
    ) -> Dict[str, int]:
        """
        Compute monthly entry counts for timeline_table filter.

        Args:
            entries: List of Entry entities

        Returns:
            Dict mapping "YYYY-MM" → count
        """
        counts: Dict[str, int] = {}
        for entry in entries:
            key = entry.date.strftime("%Y-%m")
            counts[key] = counts.get(key, 0) + 1
        return counts

    def _compute_co_occurrences(
        self, entries: List[Entry]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Compute tag and theme co-occurrence for patterns section.

        Only includes co-occurrences with overlap >= 3 entries.
        Only computed when entity has 5+ entries.

        Args:
            entries: List of Entry entities

        Returns:
            Dict with "tags" and "themes" lists of {name, count}
        """
        if len(entries) < CO_OCCURRENCE_MIN_ENTRIES:
            return {}

        tag_counts: Counter = Counter()
        theme_counts: Counter = Counter()

        for entry in entries:
            for tag in entry.tags:
                tag_counts[tag.name] += 1
            for theme in entry.themes:
                theme_counts[theme.name] += 1

        result: Dict[str, List[Dict[str, Any]]] = {}

        tag_list = [
            {"name": name, "count": count}
            for name, count in tag_counts.most_common()
            if count >= CO_OCCURRENCE_MIN_OVERLAP
        ]
        if tag_list:
            result["tags"] = tag_list

        theme_list = [
            {"name": name, "count": count}
            for name, count in theme_counts.most_common()
            if count >= CO_OCCURRENCE_MIN_OVERLAP
        ]
        if theme_list:
            result["themes"] = theme_list

        return result

    def _compute_frequent_people(
        self, entries: List[Entry], limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Compute most frequent people across a set of entries.

        Narrator excluded.

        Args:
            entries: List of Entry entities
            limit: Max people to return

        Returns:
            List of dicts with name and count
        """
        people_counts: Counter = Counter()
        for entry in entries:
            for person in entry.people:
                if person.relation_type != RelationType.SELF:
                    people_counts[person.display_name] += 1

        return [
            {"name": name, "count": count}
            for name, count in people_counts.most_common(limit)
        ]

    def _build_entry_listing(
        self, entries: List[Entry]
    ) -> List[Dict[str, Any]]:
        """
        Build hierarchical entry listing: year → month → optional week.

        Months with 8+ entries get week grouping. Months with fewer
        entries are listed inline. Entries must be pre-sorted
        (newest first).

        Args:
            entries: Pre-sorted list of Entry entities (newest first)

        Returns:
            List of year dicts, each with month dicts
        """
        if not entries:
            return []

        # Group by year, then month
        year_months: Dict[int, Dict[int, List[str]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for entry in entries:
            d = entry.date
            year_months[d.year][d.month].append(d.isoformat())

        result = []
        for year in sorted(year_months.keys(), reverse=True):
            months_data = year_months[year]
            year_total = sum(len(dates) for dates in months_data.values())

            month_list = []
            for month in sorted(months_data.keys()):
                dates = sorted(months_data[month])
                month_name = calendar.month_name[month]

                if len(dates) >= 8:
                    # Week grouping
                    weeks: Dict[int, List[str]] = defaultdict(list)
                    for d_str in dates:
                        d = date.fromisoformat(d_str)
                        week_num = (d.day - 1) // 7 + 1
                        weeks[week_num].append(d_str)
                    month_list.append({
                        "name": month_name,
                        "count": len(dates),
                        "weeks": [
                            {"number": w, "dates": weeks[w]}
                            for w in sorted(weeks.keys())
                        ],
                    })
                else:
                    month_list.append({
                        "name": month_name,
                        "count": len(dates),
                        "dates": dates,
                    })

            result.append({
                "year": year,
                "count": year_total,
                "months": month_list,
            })

        return result

    def _find_event_arc(self, event: Event) -> Optional[str]:
        """
        Find the arc name associated with an event.

        Checks arc membership by finding shared entries between
        the event and any arc.

        Args:
            event: Event entity

        Returns:
            Arc name string or None if unlinked
        """
        event_entry_ids = {e.id for e in event.entries}
        for entry in event.entries:
            for arc in entry.arcs:
                arc_entry_ids = {e.id for e in arc.entries}
                if arc_entry_ids & event_entry_ids:
                    return arc.name
        return None

    def _date_range_str(
        self,
        start: Optional[date],
        end: Optional[date],
    ) -> Optional[str]:
        """
        Format a date range as abbreviated string.

        Args:
            start: Start date (may be None)
            end: End date (may be None)

        Returns:
            Formatted range or None if both dates are None
        """
        if not start or not end:
            return None
        from dev.wiki.filters import date_range
        return date_range(start, end)
