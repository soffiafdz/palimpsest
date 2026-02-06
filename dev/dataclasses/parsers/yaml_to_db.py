#!/usr/bin/env python3
"""
yaml_to_db.py
-------------
YAML frontmatter to database format parser.

Converts YAML frontmatter structures to database-compatible metadata format.
Handles complex field parsing including people, locations, dates, references,
and poems. Used by MdEntry.to_database_metadata() for yaml2sql workflow.

Classes:
    YamlToDbParser: Parser for converting YAML to database format

Key Methods:
    parse_city_field: Parse city/cities (single or list)
    parse_locations_field: Parse flat or nested location structures
    parse_people_field: Parse people with name/full_name/alias logic
    parse_dates_field: Parse dates with locations/people associations
    parse_references_field: Parse references with source handling
    parse_poems_field: Parse poems with revision dates

Usage:
    from dev.dataclasses.parsers import YamlToDbParser

    parser = YamlToDbParser(entry_date, metadata)
    cities = parser.parse_city_field(metadata["city"])
    people = parser.parse_people_field(metadata["people"])
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import logging
from datetime import date
from typing import Dict, Any, List, Optional, Union, Tuple

# --- Local imports ---
from dev.core.validators import DataValidator
from dev.utils import parsers

logger = logging.getLogger(__name__)


class YamlToDbParser:
    """
    Parser for converting YAML frontmatter to database metadata format.

    This parser handles the conversion of user-friendly YAML structures
    into the normalized format expected by the database layer.
    """

    def __init__(self, entry_date: date, metadata: Dict[str, Any]):
        """
        Initialize parser with entry context.

        Args:
            entry_date: The entry's primary date
            metadata: Raw YAML metadata dictionary
        """
        self.entry_date = entry_date
        self.metadata = metadata

    def parse_city_field(self, city_data: Union[str, List[str]]) -> List[str]:
        """
        Parse city field (single city or list of cities).

        Supports both formats:
        - Single string: "Montreal"
        - List of strings: ["Montreal", "Toronto"]

        Args:
            city_data: City name(s) from YAML

        Returns:
            List of city names (always a list, even for single city)

        Examples:
            >>> parser.parse_city_field("Montreal")
            ["Montreal"]
            >>> parser.parse_city_field(["Montreal", "Toronto"])
            ["Montreal", "Toronto"]
        """
        if isinstance(city_data, str):
            return [city_data.strip()]
        if isinstance(city_data, list):
            return [str(c).strip() for c in city_data if str(c).strip()]

        logger.warning(f"Invalid city_data type: {type(city_data)}")
        return []

    def parse_locations_field(
        self, locations_data: Union[str, List[str], Dict[str, List[str]]], cities: List[str]
    ) -> Dict[str, List[str]]:
        """
        Parse locations field supporting both flat and nested formats.

        Formats:
        - Flat list (single city): ["Café X", "Park Y"]
        - Nested dict (multiple cities): {"Montreal": ["Café X"], "Toronto": ["Park Y"]}

        Handles hyphen/underscore conversion:
        - "Cinema-Moderne" → "Cinema Moderne"
        - "Rue_St-Hubert" → "Rue St-Hubert" (underscore preserves hyphens)

        Args:
            locations_data: Either flat list or nested dict
            cities: List of cities from city field (for validation)

        Returns:
            Dict mapping city names to lists of location names

        Examples:
            >>> parse_locations_field(["Café X", "Park Y"], ["Montreal"])
            {"Montreal": ["Café X", "Park Y"]}

            >>> parse_locations_field(
            ...     {"Montreal": ["Café X"], "Toronto": ["Park Y"]},
            ...     ["Montreal", "Toronto"]
            ... )
            {"Montreal": ["Café X"], "Toronto": ["Park Y"]}
        """
        from dev.utils.parsers import split_hyphenated_to_spaces

        result = {}

        # Normalize single string to list
        if isinstance(locations_data, str):
            locations_data = [locations_data]

        if isinstance(locations_data, list):
            # Flat list - all locations belong to single city
            if len(cities) != 1:
                logger.warning("Flat location list but multiple cities specified")
                return {}
            result[cities[0]] = [
                split_hyphenated_to_spaces(str(loc).strip()) for loc in locations_data
            ]

        elif isinstance(locations_data, dict):
            # Nested dict - locations grouped by city
            for city, locs in locations_data.items():
                city_name = str(city).strip()
                if isinstance(locs, list):
                    result[city_name] = [
                        split_hyphenated_to_spaces(str(loc).strip()) for loc in locs
                    ]
                elif isinstance(locs, str):
                    result[city_name] = [split_hyphenated_to_spaces(locs.strip())]

        return result

    def parse_people_field(
        self, people_list: Union[str, List[Union[str, Dict]]]
    ) -> Dict[str, Any]:
        """
        Parse people field with name/full_name/alias logic.

        Supports multiple formats:
        - Simple name: "John" → {name: "John"}
        - Hyphenated name: "Jean-Paul" → {name: "Jean Paul"}
        - Full name: "John Smith" → {full_name: "John Smith"}
        - Name with expansion: "John (John Smith)" → {name: "John", full_name: "John Smith"}
        - Alias format: "@Johnny" → {alias: "Johnny"}
        - Alias with name: "@Johnny (John)" → {alias: "Johnny", name: "John"}
        - Dict format: {"name": "John", "full_name": "John Smith"}

        Rules:
        - Single word (may be hyphenated): treated as name only
        - Multiple words: treated as full_name only
        - Parentheses: name (full_name) format
        - Starts with @: alias format
        - Hyphens in single-word names converted to spaces

        Args:
            people_list: List of person specifications from YAML

        Returns:
            Dict with keys "people" and "alias", each containing list of parsed specs

        Examples:
            >>> parse_people_field(["John", "Jane Smith"])
            {"people": [{"name": "John"}, {"full_name": "Jane Smith"}], "alias": []}

            >>> parse_people_field(["@Johnny (John)", "Jane"])
            {"people": [{"name": "Jane"}], "alias": [{"alias": "Johnny", "name": "John"}]}
        """
        result: Dict[str, List[Dict[str, Optional[str]]]] = {"people": [], "alias": []}

        # Normalize single string to list
        if isinstance(people_list, str):
            people_list = [people_list]

        for item in people_list:
            # Dict format - use directly
            if isinstance(item, dict):
                if "alias" in item:
                    result["alias"].append(item)
                else:
                    result["people"].append(item)
                continue

            # String format - parse
            if not isinstance(item, str):
                continue

            person_str = item.strip()
            if not person_str:
                continue

            # Alias format (starts with @)
            if person_str.startswith("@"):
                alias_str = person_str[1:]  # Remove @

                # Check for name in parentheses: "@Alias (Name)"
                if "(" in alias_str and alias_str.endswith(")"):
                    alias_part, name_part = alias_str.split("(", 1)
                    alias = alias_part.strip()
                    name = name_part.rstrip(")").strip()
                    result["alias"].append({"alias": alias, "name": name})
                else:
                    result["alias"].append({"alias": alias_str})
                continue

            # Regular name format
            # Check for full_name in parentheses: "Name (Full Name)"
            if "(" in person_str and person_str.endswith(")"):
                name_part, full_part = person_str.split("(", 1)
                name = name_part.strip()
                full_name = full_part.rstrip(")").strip()

                # Replace hyphens with spaces in name (or underscores if present)
                from dev.utils.parsers import split_hyphenated_to_spaces
                name = split_hyphenated_to_spaces(name)

                result["people"].append({"name": name, "full_name": full_name})
                continue

            # Simple name/full_name (no parentheses)
            # CRITICAL: Split by spaces FIRST to identify entity boundaries
            # Then dehyphenate each part for storage
            # Example: "María-José Castro" → ["María-José", "Castro"] (2 entities)
            #   First entity = first_name(s): "María-José"
            #   Rest = last_name(s): "Castro"
            #   Then dehyphenate: first_name="María José", last_name="Castro"

            from dev.utils.parsers import split_hyphenated_to_spaces

            # Split by spaces to identify entity boundaries (BEFORE dehyphenation)
            parts = person_str.split()

            if len(parts) > 1:
                # Multiple entities → construct full_name with proper structure
                # First part is first_name(s), rest is last_name(s)
                first_name_raw = parts[0]
                last_name_raw = " ".join(parts[1:])

                # Now dehyphenate each part for storage
                first_name = split_hyphenated_to_spaces(first_name_raw)
                last_name = split_hyphenated_to_spaces(last_name_raw)

                # Construct full_name
                full_name = f"{first_name} {last_name}"

                result["people"].append({"name": first_name, "full_name": full_name})
            else:
                # Single entity → just a name
                name = split_hyphenated_to_spaces(person_str)
                result["people"].append({"name": name, "full_name": None})

        return result

    @staticmethod
    def find_person_in_parsed(
        person_str: str, people_parsed: Dict[str, List]
    ) -> Optional[Dict[str, Optional[str]]]:
        """
        Look up a person string in the parsed people structure.

        Used when dates or other fields reference people by name.
        Searches through both regular people and aliases.

        Args:
            person_str: Name to look up (can be "@Alias" or "Name")
            people_parsed: Result from parse_people_field()

        Returns:
            Person dict if found, None otherwise

        Examples:
            >>> people = {"people": [{"name": "John"}], "alias": [{"alias": "Johnny", "name": "John"}]}
            >>> find_person_in_parsed("John", people)
            {"name": "John"}
            >>> find_person_in_parsed("@Johnny", people)
            {"alias": "Johnny", "name": "John"}
        """
        search_str = person_str.strip()

        # Handle @alias format
        if search_str.startswith("@"):
            alias_name = search_str[1:]
            for alias_spec in people_parsed.get("alias", []):
                if alias_spec.get("alias") == alias_name:
                    return alias_spec
            return None

        # Search in regular people
        # Priority: exact name match > exact full_name match > first name of full_name
        for person_spec in people_parsed.get("people", []):
            # Exact match on name field
            if person_spec.get("name") == search_str:
                return person_spec
            # Exact match on full_name field
            if person_spec.get("full_name") == search_str:
                return person_spec

        # Second pass: try matching against first name from full_name
        # This allows "Daniel" to match {"name": "Daniel", "full_name": "Daniel Andrews"}
        for person_spec in people_parsed.get("people", []):
            name = person_spec.get("name")
            if name and search_str:
                # If name matches search exactly, already returned above
                # Check if search_str matches first word of name (for compound first names)
                first_word = name.split()[0] if " " in name else name
                if first_word == search_str:
                    return person_spec

        return None

    def parse_dates_field(
        self,
        dates_data: Union[List[Union[str, Dict]], Dict],
        people_parsed: Optional[Dict[str, List]],
    ) -> Tuple[List, bool]:
        """
        Parse dates field with inline or nested format.

        Associates locations/people/events to specific dates (moments).
        For people values in dates, looks them up in people_parsed.

        Supports two types of date entries:
        - MOMENT (default): An event that actually happened on the referenced date
        - REFERENCE: A contextual link where the action happens on entry date,
          but references something from another time

        Formats:
        - Simple date: "2025-06-01" → moment
        - Inline context: "2025-06-01 (thesis exam)" → moment
        - Reference prefix: "~2025-01-11 (negatives from anti-date)" → reference
        - Nested format: {"date": "2025-06-01", "context": "..."} → moment
        - Explicit reference: {"date": "2025-01-11", "type": "reference", ...}
        - Entry date shorthand: {"date": "."} → moment on entry date
        - Opt-out marker: "~" alone (excludes entry date from moments)
        - Events: {"date": "2025-06-01", "events": ["summer-trip"]}

        Args:
            dates_data: List of date specifications
            people_parsed: Result from parse_people_field() with keys already assigned

        Returns:
            Tuple of (parsed_dates, exclude_entry_date_flag)
            Each parsed date includes a "type" field: "moment" or "reference"

        Examples:
            >>> parse_dates_field([
            ...     "2025-06-01",
            ...     "~2025-01-11 (negatives from anti-date)",
            ...     {"date": "2025-07-01", "type": "reference", "context": "..."}
            ... ], people_parsed)
            ([{"date": "2025-06-01", "type": "moment"},
              {"date": "2025-01-11", "type": "reference", ...}, ...], False)
        """
        if isinstance(dates_data, dict):
            dates_data = [dates_data]

        normalized = []
        exclude_entry_date = False

        for item in dates_data:
            # --- Opt-out trigger ---
            if item == "~" or item is None:
                exclude_entry_date = True
                continue

            # --- Inline string ---
            if isinstance(item, str):
                # Check for reference prefix (~)
                is_reference = False
                date_str = item
                if item.startswith("~"):
                    is_reference = True
                    date_str = item[1:].lstrip()  # Remove ~ and any leading whitespace

                date_obj, raw_context = parsers.parse_date_context(date_str)

                if not DataValidator.validate_date_string(date_obj):
                    logger.warning(f"Invalid date format, skipping: {date_obj}")
                    continue

                date_dict: Dict[str, Union[date, str, List]] = {
                    "date": date_obj,
                    "type": "reference" if is_reference else "moment",
                }

                if raw_context:
                    context_dict = parsers.extract_context_refs(raw_context)
                    date_dict.update(context_dict)

                normalized.append(date_dict)

            # --- Dictionary ---
            if isinstance(item, dict):
                if "date" not in item:
                    logger.warning(f"Date dict missing 'date' field: {item}")
                    continue

                # Handle '.' as shorthand for entry date
                date_value = item["date"]
                if date_value == ".":
                    date_value = self.entry_date.isoformat()
                # Convert datetime.date objects to ISO strings
                elif isinstance(date_value, date):
                    date_value = date_value.isoformat()
                # Validate date format (now handles both strings and datetime.date)
                elif not DataValidator.validate_date_string(date_value):
                    logger.warning(f"Invalid date format, skipping: {item}")
                    continue

                # Handle type field (default to "moment")
                moment_type = item.get("type", "moment")
                if moment_type not in ("moment", "reference"):
                    logger.warning(
                        f"Invalid moment type '{moment_type}', defaulting to 'moment'"
                    )
                    moment_type = "moment"

                date_dict = {"date": date_value, "type": moment_type}
                all_locations = []
                people_context = []

                # Context
                raw_context = item.get("context", "")
                if raw_context:
                    context_dict = parsers.extract_context_refs(raw_context)
                    if "locations" in context_dict and context_dict["locations"]:
                        all_locations.extend(context_dict["locations"])
                    if "people" in context_dict and context_dict["people"]:
                        people_context.extend(context_dict["people"])
                    date_dict.update(context_dict)

                # --- Locations ---
                if "locations" in item:
                    locs_field = item["locations"]
                    if isinstance(locs_field, str):
                        all_locations.append(locs_field)
                    elif isinstance(locs_field, list):
                        all_locations.extend(locs_field)

                if all_locations:
                    from dev.utils.parsers import split_hyphenated_to_spaces
                    date_dict["locations"] = [
                        split_hyphenated_to_spaces(normalized_loc)
                        for loc in all_locations
                        if (normalized_loc := DataValidator.normalize_string(loc))
                    ]

                # --- People - LOOKUP IN people_parsed ---
                if ("people" in item or people_context) and people_parsed:
                    people_field = item.get("people", [])
                    if not isinstance(people_field, list):
                        people_field = [people_field]

                    people_field.extend(people_context)

                    people_list = []

                    for person_value in people_field:
                        # If already a dict, use as-is
                        if isinstance(person_value, dict):
                            people_list.append(person_value)
                            continue

                        # String value - look up in people_parsed using helper
                        person_str = DataValidator.normalize_string(person_value)
                        if not person_str:
                            continue

                        person_spec = self.find_person_in_parsed(person_str, people_parsed)
                        if person_spec:
                            people_list.append(person_spec)

                    if people_list:
                        date_dict["people"] = people_list

                # --- Events ---
                if "events" in item:
                    events_field = item["events"]
                    if isinstance(events_field, str):
                        events_field = [events_field]

                    if isinstance(events_field, list):
                        # Normalize event names (hyphen to space, strip)
                        from dev.utils.parsers import split_hyphenated_to_spaces
                        events_list = [
                            split_hyphenated_to_spaces(normalized_ev)
                            for ev in events_field
                            if (normalized_ev := DataValidator.normalize_string(ev))
                        ]
                        if events_list:
                            date_dict["events"] = events_list

                normalized.append(date_dict)

        return normalized, exclude_entry_date

    def parse_references_field(
        self, refs_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse and normalize references with source handling.

        Reference format:
        {
            "content": str (optional, but content or description required),
            "description": str (optional),
            "mode": str (optional, default: "direct"),
            "speaker": str (optional),
            "source": {
                "title": str (required),
                "type": str (required),
                "author": str (optional)
            }
        }

        Args:
            refs_data: List of reference dictionaries from YAML

        Returns:
            List of normalized reference dictionaries
        """
        normalized = []

        for ref in refs_data:
            if not isinstance(ref, dict):
                continue

            ref_dict: Dict[str, Any] = {}

            # Content and description
            if "content" in ref:
                ref_dict["content"] = ref["content"]
            if "description" in ref:
                ref_dict["description"] = ref["description"]

            # Mode
            if "mode" in ref:
                ref_dict["mode"] = ref["mode"]

            # Speaker
            if "speaker" in ref:
                ref_dict["speaker"] = ref["speaker"]

            # Source
            if "source" in ref and isinstance(ref["source"], dict):
                source = ref["source"]
                source_dict: Dict[str, str] = {}

                if "title" in source:
                    source_dict["title"] = source["title"]
                if "type" in source:
                    source_dict["type"] = source["type"]
                if "author" in source:
                    source_dict["author"] = source["author"]

                if source_dict:
                    ref_dict["source"] = source_dict

            if ref_dict:
                normalized.append(ref_dict)

        return normalized

    def parse_poems_field(
        self, poems_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse and normalize poems with Poem parent handling.

        Poem format:
        {
            "title": str (required),
            "content": str (required),
            "revision_date": str|date (optional, defaults to entry.date),
            "notes": str (optional)
        }

        If revision_date is not provided or is invalid, it defaults to the
        entry's date, ensuring all poems have a documented revision date.

        Args:
            poems_data: List of poem dictionaries

        Returns:
            List of validated poem dicts ready for database

        Examples:
            >>> parse_poems_field([{
            ...     "title": "Ode to Joy",
            ...     "content": "Beautiful spark of divinity...",
            ...     "revision_date": "2024-01-15",
            ...     "notes": "First draft"
            ... }])
            [{
                "title": "Ode to Joy",
                "content": "Beautiful spark of divinity...",
                "revision_date": date(2024, 1, 15),
                "notes": "First draft"
            }]
        """
        from dev.core.validators import DataValidator

        normalized = []

        for poem in poems_data:
            if not isinstance(poem, dict):
                logger.warning(f"Invalid poem format: {poem}")
                continue

            if "title" not in poem or not poem["title"]:
                logger.warning("Poem missing required 'title' field")
                continue

            if "content" not in poem or not poem["content"]:
                logger.warning("Poem missing required 'content' field")
                continue

            poem_dict: Dict[str, Any] = {
                "title": DataValidator.normalize_string(poem["title"]),
                "content": DataValidator.normalize_string(poem["content"]),
            }

            # Optional revision_date (defaults to entry date if not provided)
            if "revision_date" in poem:
                rev_date = DataValidator.normalize_date(poem["revision_date"])
                if rev_date:
                    poem_dict["revision_date"] = rev_date
                else:
                    logger.warning(
                        f"Invalid revision_date in poem '{poem['title']}': {poem['revision_date']} - using entry date"
                    )
                    poem_dict["revision_date"] = self.entry_date
            else:
                # Default to entry date when revision_date is not specified
                poem_dict["revision_date"] = self.entry_date

            # Optional notes
            if "notes" in poem:
                notes = DataValidator.normalize_string(poem["notes"])
                if notes:
                    poem_dict["notes"] = notes

            normalized.append(poem_dict)

        return normalized
