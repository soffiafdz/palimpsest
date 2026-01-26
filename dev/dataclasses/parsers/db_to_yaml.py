#!/usr/bin/env python3
"""
db_to_yaml.py
-------------
Database Entry to YAML frontmatter exporter.

Converts database Entry ORM objects to YAML frontmatter-compatible metadata format.
Handles complex field building including people, locations, dates, references,
and poems. Used by MdEntry.from_database() for sql2yaml workflow.

Classes:
    DbToYamlExporter: Exporter with static methods for building metadata

Key Methods:
    build_cities_metadata: Extract city/cities (single or list)
    build_locations_metadata: Extract locations (flat or nested by city)
    build_people_metadata: Extract people with aliases
    build_dates_metadata: Extract mentioned dates with context
    build_references_metadata: Extract references with sources
    build_poems_metadata: Extract poems with revision dates
    build_manuscript_metadata: Extract manuscript status and themes

Usage:
    from dev.dataclasses.parsers import DbToYamlExporter

    exporter = DbToYamlExporter()
    cities = exporter.build_cities_metadata(entry)
    people = exporter.build_people_metadata(entry)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from typing import Dict, Any, List, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from dev.database.models import Entry


class DbToYamlExporter:
    """
    Exporter for converting database Entry objects to YAML metadata format.

    This exporter handles the conversion from normalized database structures
    into the human-friendly YAML format used in markdown frontmatter.
    """

    @staticmethod
    def build_cities_metadata(entry: Entry) -> Optional[Union[str, List[str]]]:
        """
        Extract city/cities metadata from database Entry.

        Args:
            entry: Database Entry ORM object

        Returns:
            Single city string if one city, list of cities if multiple,
            None if no cities

        Examples:
            >>> build_cities_metadata(entry_with_one_city)
            "Montreal"
            >>> build_cities_metadata(entry_with_multiple_cities)
            ["Montreal", "Toronto"]
        """
        if not entry.cities:
            return None
        if len(entry.cities) == 1:
            return entry.cities[0].name
        return [c.name for c in entry.cities]

    @staticmethod
    def build_locations_metadata(
        entry: Entry,
    ) -> Optional[Union[List[str], Dict[str, List[str]]]]:
        """
        Extract locations metadata from database Entry.

        Returns flat list for single city, nested dict for multiple cities.

        Args:
            entry: Database Entry ORM object

        Returns:
            - None if no locations
            - List of location names if single city or no cities
            - Dict mapping city names to location lists if multiple cities

        Examples:
            >>> build_locations_metadata(entry_single_city)
            ["Café X", "Park Y"]
            >>> build_locations_metadata(entry_multiple_cities)
            {"Montreal": ["Café X"], "Toronto": ["Park Y"]}
        """
        if not entry.locations:
            return None

        if not entry.cities or len(entry.cities) == 1:
            # No cities or single city - flat list of locations
            return [loc.name for loc in entry.locations]
        else:
            # Multiple cities - nested dict grouped by city
            locations_dict: Dict[str, List[str]] = {}
            for loc in entry.locations:
                city_name = loc.city.name
                if city_name not in locations_dict:
                    locations_dict[city_name] = []
                locations_dict[city_name].append(loc.name)
            return locations_dict

    @staticmethod
    def build_people_metadata(entry: Entry) -> Optional[List[Dict[str, Any]]]:
        """
        Extract people and aliases metadata from database Entry.

        Combines regular people and aliases into unified list format.
        Aliases are associated with their person's name/full_name.

        Args:
            entry: Database Entry ORM object

        Returns:
            List of person dictionaries with name/full_name/alias keys,
            None if no people or aliases

        Examples:
            >>> build_people_metadata(entry)
            [
                {"full_name": "John Smith"},
                {"name": "Jane"},
                {"alias": ["Johnny"], "name": "John", "full_name": "John Smith"}
            ]
        """
        if not entry.people and not entry.aliases_used:
            return None

        people_list: List[Dict[str, Any]] = []
        aliases_by_person: Dict[int, Dict[str, Any]] = {}

        # Import hyphenation utility
        from dev.utils.parsers import spaces_to_hyphenated

        # Helper function to re-hyphenate names for export
        def rehyphenate_name(name: str) -> str:
            """Re-hyphenate first name portion if it contains spaces."""
            if not name or " " not in name:
                return name
            # Hyphenate spaces in name
            return spaces_to_hyphenated(name)

        def rehyphenate_full_name(full_name: str) -> str:
            """Re-hyphenate only the first name portion of a full name."""
            if not full_name or " " not in full_name:
                return full_name
            # For now, just hyphenate ALL spaces - this matches the input format
            return spaces_to_hyphenated(full_name)

        # Process aliases first - group by person
        if entry.aliases_used:
            for alias in entry.aliases_used:
                person_id = alias.person_id
                if person_id not in aliases_by_person:
                    # Re-hyphenate the name for export
                    name_hyphenated = rehyphenate_name(alias.person.name) if alias.person.name else None
                    aliases_by_person[person_id] = {
                        "alias": [],
                        "name": name_hyphenated,
                    }
                    # Add full_name if name_fellow
                    if alias.person.name_fellow and alias.person.full_name:
                        fname_hyphenated = rehyphenate_full_name(alias.person.full_name)
                        aliases_by_person[person_id]["full_name"] = fname_hyphenated
                aliases_by_person[person_id]["alias"].append(alias.alias)

        # Process regular people (skip those already in aliases)
        for p in entry.people:
            if aliases_by_person and p.id in aliases_by_person:
                continue
            if p.name_fellow:
                full_name_hyphenated = rehyphenate_full_name(p.full_name)
                people_list.append({"full_name": full_name_hyphenated})
            else:
                name_hyphenated = rehyphenate_name(p.name)
                people_list.append({"name": name_hyphenated})

        # Add alias entries
        people_list.extend(aliases_by_person.values())
        return people_list

    @staticmethod
    def build_narrated_dates_metadata(
        entry: Entry,
    ) -> Optional[List[str]]:
        """
        Extract narrated dates from database Entry.

        Args:
            entry: Database Entry ORM object

        Returns:
            List of date strings in ISO format, None if no narrated dates

        Examples:
            >>> build_narrated_dates_metadata(entry)
            ["2024-01-15", "2024-01-16"]
        """
        if not entry.narrated_dates:
            return None

        return [nd.date.isoformat() for nd in entry.narrated_dates]

    @staticmethod
    def build_references_metadata(entry: Entry) -> Optional[List[Dict[str, Any]]]:
        """
        Extract references metadata from database Entry.

        Includes content, description, mode, speaker, and source information.

        Args:
            entry: Database Entry ORM object

        Returns:
            List of reference dictionaries, None if no references

        Examples:
            >>> build_references_metadata(entry)
            [
                {
                    "content": "Quote text",
                    "mode": "paraphrase",
                    "source": {
                        "title": "Book Title",
                        "type": "book",
                        "author": "Author Name"
                    }
                }
            ]
        """
        if not entry.references:
            return None

        refs_list: List[Dict[str, Any]] = []
        for ref in entry.references:
            ref_dict: Dict[str, Any] = {}

            # Content is optional
            if ref.content:
                ref_dict["content"] = ref.content

            # Add description if present
            if ref.description:
                ref_dict["description"] = ref.description

            # Add mode (default is direct, so only include if different)
            if ref.mode and ref.mode.value != "direct":
                ref_dict["mode"] = ref.mode.value

            if ref.speaker:
                ref_dict["speaker"] = ref.speaker

            if ref.source:
                ref_dict["source"] = {
                    "title": ref.source.title,
                    "type": ref.source.type.value,
                }
                if ref.source.author:
                    ref_dict["source"]["author"] = ref.source.author

            refs_list.append(ref_dict)

        return refs_list

    @staticmethod
    def build_poems_metadata(entry: Entry) -> Optional[List[Dict[str, Any]]]:
        """
        Extract poems metadata from database Entry.

        Includes title, content, revision_date, and notes.

        Args:
            entry: Database Entry ORM object

        Returns:
            List of poem dictionaries, None if no poems

        Examples:
            >>> build_poems_metadata(entry)
            [
                {
                    "title": "Ode to Joy",
                    "content": "Beautiful spark...",
                    "revision_date": "2024-01-15",
                    "notes": "First draft"
                }
            ]
        """
        if not entry.poems:
            return None

        poems_list: List[Dict[str, Any]] = []
        for pv in entry.poems:
            poem_dict: Dict[str, Any] = {
                "title": pv.poem.title if pv.poem else "Untitled",
                "content": pv.content,
            }
            if pv.revision_date:
                poem_dict["revision_date"] = pv.revision_date.isoformat()
            if pv.notes:
                poem_dict["notes"] = pv.notes
            poems_list.append(poem_dict)

        return poems_list

    # -------------------------------------------------------------------------
    # DEPRECATED: Manuscript metadata now tracked differently via Chapter model
    # -------------------------------------------------------------------------
