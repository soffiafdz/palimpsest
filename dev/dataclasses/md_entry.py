#!/usr/bin/env python3
"""
md_entry.py
-------------------
Dataclass representing journal entries with YAML frontmatter.

This module handles the intermediary data structure for Markdown-based
journal entries with rich metadata. It serves as the bridge between:
- Human-edited Markdown files with YAML frontmatter
- Database ORM models (Entry, Person, Location, etc.)

The MdEntry class provides:
- YAML frontmatter parsing and generation
- Bidirectional conversion (Markdown ↔ Database)
- Validation of metadata structure
- Intelligent parsing of complex fields (locations, references, poems)

Key Design:
- Progressive complexity: supports minimal to extreme metadata
- Human-friendly: YAML remains hand-editable
- Database-mappable: every field maps to ORM models
- Lossless conversion: round-trip preserves all data
"""
from __future__ import annotations

import logging
import yaml
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Sequence, Tuple, TypedDict

from dev.core.exceptions import EntryParseError, EntryValidationError
from dev.core.validators import DataValidator
from dev.database.models import Entry
from dev.utils import md, parsers

logger = logging.getLogger(__name__)


# ----- Type Definitions -----


class PersonSpec(TypedDict, total=False):
    """Type specification for person metadata."""

    name: str
    full_name: str


class AliasSpec(TypedDict):
    """Type specification for alias metadata."""

    alias: Union[str, List[str]]
    name: str
    full_name: str  # Optional


class LocationSpec(TypedDict):
    """Type specification for location metadata."""

    name: str
    city: str


class DateSpec(TypedDict, total=False):
    """Type specification for mentioned date metadata."""

    date: str
    context: str
    locations: List[str]
    people: List[PersonSpec]


class ReferenceSourceSpec(TypedDict, total=False):
    """Type specification for reference source metadata."""

    title: str
    type: str
    author: str


class ReferenceSpec(TypedDict, total=False):
    """Type specification for reference metadata."""

    content: str
    description: str
    mode: str
    speaker: str
    source: ReferenceSourceSpec


class PoemSpec(TypedDict, total=False):
    """Type specification for poem metadata."""

    title: str
    content: str
    revision_date: str
    notes: str


class ManuscriptSpec(TypedDict, total=False):
    """Type specification for manuscript metadata."""

    status: str
    edited: bool
    themes: List[str]
    notes: str


class EntryMetadata(TypedDict, total=False):
    """Type specification for complete entry metadata structure."""

    # Required fields
    date: Union[str, date]
    word_count: int
    reading_time: float

    # Optional simple fields
    epigraph: str
    epigraph_attribution: str
    notes: str

    # Location fields
    city: Union[str, List[str]]
    locations: Union[List[str], Dict[str, List[str]]]

    # People fields
    people: List[PersonSpec]

    # Date references
    dates: List[Union[str, DateSpec]]

    # Simple list fields
    events: List[str]
    tags: List[str]
    related_entries: List[str]

    # Complex nested fields
    references: List[ReferenceSpec]
    poems: List[PoemSpec]
    manuscript: ManuscriptSpec


@dataclass
class MdEntry:
    """
    Represents a journal entry parsed from Markdown with YAML frontmatter.

    This is the intermediary format between:
    - .md files with YAML (human-edited)
    - Database ORM models (structured storage)

    Attributes:
        date: Entry date (required)
        body: Markdown content lines after frontmatter
        metadata: Parsed YAML frontmatter as dictionary
        file_path: Source file path if loaded from file
        frontmatter_raw: Original YAML text for reference

    Examples:
        >>> # Load from file
        >>> entry = MdEntry.from_file(Path("2024-01-15.md"))
        >>>
        >>> # Convert to database format
        >>> db_metadata = entry.to_database_metadata()
        >>>
        >>> # Generate updated markdown
        >>> markdown_text = entry.to_markdown()
    """

    date: date
    body: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    file_path: Optional[Path] = None
    frontmatter_raw: str = ""

    # ---- Construction Methods ----
    @classmethod
    def from_file(cls, file_path: Path, verbose: bool = False) -> MdEntry:
        """
        Parse a Markdown file with YAML frontmatter.

        Args:
            file_path: Path to .md file
            verbose: Enable debug logging

        Returns:
            Parsed MdEntry instance

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid (no frontmatter, no date)
            yaml.YAMLError: If YAML is malformed

        Examples:
            >>> entry = MdEntry.from_file(Path("journal/2024/2024-01-15.md"))
            >>> print(entry.date)
            2024-01-15
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if verbose:
            logger.debug(f"Reading file: {file_path}")

        content: str = file_path.read_text(encoding="utf-8")
        return cls.from_markdown_text(content, file_path, verbose)

    @classmethod
    def from_markdown_text(
        cls, content: str, file_path: Optional[Path] = None, verbose: bool = False
    ) -> MdEntry:
        """
        Parse Markdown text with YAML frontmatter.

        Expected format:
            ---
            date: 2024-01-15
            key: value
            ---

            # Body content here

        Args:
            content: Full markdown file content
            file_path: Optional source file path
            verbose: Enable debug logging

        Returns:
            Parsed MdEntry instance

        Raises:
            ValueError: If no frontmatter or missing date
            yaml.YAMLError: If YAML is malformed
        """
        if verbose:
            logger.debug("Parsing markdown content")

        # Split frontmatter from body
        frontmatter_text: str
        body_lines: List[str]
        frontmatter_text, body_lines = md.split_frontmatter(content)

        if not frontmatter_text:
            raise EntryValidationError("No YAML frontmatter found (must start with ---)")

        try:
            metadata: Any = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise EntryParseError(f"Invalid YAML frontmatter: {e}") from e

        if not isinstance(metadata, dict):
            raise EntryValidationError("YAML frontmatter must be a dictionary")

        # Extract required date field
        if "date" not in metadata:
            raise EntryValidationError("Missing required 'date' field in frontmatter")

        entry_date = DataValidator.normalize_date(metadata["date"])
        if entry_date is None:
            raise EntryValidationError(f"Invalid date format: {metadata['date']}")

        if verbose:
            logger.debug(f"Parsed entry for {entry_date}")
            logger.debug(
                f"Metadata fields: {len(metadata)}, Body lines: {len(body_lines)}"
            )

        return cls(
            date=entry_date,
            body=body_lines,
            metadata=metadata,
            file_path=file_path,
            frontmatter_raw=frontmatter_text,
        )

    @classmethod
    def from_database(
        cls,
        entry: Entry,  # Entry ORM object
        body_lines: List[str],
        file_path: Optional[Path] = None,
    ) -> MdEntry:
        """
        Create MdEntry from database Entry ORM object.

        This is used by sql2yaml to export database → Markdown.

        Args:
            entry: SQLAlchemy Entry ORM instance
            body_lines: Markdown body content
            file_path: Target file path

        Returns:
            MdEntry with metadata populated from database

        Examples:
            >>> with db.session_scope() as session:
            ...     entry_orm = db.get_entry(session, "2024-01-15")
            ...     body = read_body_from_somewhere()
            ...     md_entry = MdEntry.from_database(entry_orm, body)
        """
        # Build basic metadata
        metadata: Dict[str, Any] = {
            "date": entry.date,
            "word_count": entry.word_count,
            "reading_time": entry.reading_time,
        }

        # Optional simple fields
        if entry.epigraph:
            metadata["epigraph"] = entry.epigraph
        if entry.epigraph_attribution:
            metadata["epigraph_attribution"] = entry.epigraph_attribution
        if entry.notes:
            metadata["notes"] = entry.notes

        # Complex metadata - use helper methods
        city = cls._build_cities_metadata(entry)
        if city is not None:
            metadata["city"] = city

        locations = cls._build_locations_metadata(entry)
        if locations is not None:
            metadata["locations"] = locations

        people = cls._build_people_metadata(entry)
        if people is not None:
            metadata["people"] = people

        dates = cls._build_dates_metadata(entry)
        if dates is not None:
            metadata["dates"] = dates

        # Simple list fields
        if entry.events:
            metadata["events"] = [evt.event for evt in entry.events]

        if entry.tags:
            metadata["tags"] = [tag.tag for tag in entry.tags]

        if entry.related_entries:
            metadata["related_entries"] = [
                r_e.date.isoformat() for r_e in entry.related_entries
            ]

        # Complex nested metadata
        references = cls._build_references_metadata(entry)
        if references is not None:
            metadata["references"] = references

        poems = cls._build_poems_metadata(entry)
        if poems is not None:
            metadata["poems"] = poems

        manuscript = cls._build_manuscript_metadata(entry)
        if manuscript is not None:
            metadata["manuscript"] = manuscript

        return cls(
            date=entry.date,
            body=body_lines,
            metadata=metadata,
            file_path=file_path,
            frontmatter_raw="",
        )

    # ---- Conversion Methods ----
    def to_database_metadata(self) -> Dict[str, Any]:
        """
        Convert MdEntry metadata to format expected by PalimpsestDB.

        This transforms the human-friendly YAML format into the structure
        needed for database.create_entry() and database.update_entry().

        Returns:
            Dictionary with normalized database-ready metadata

        Examples:
            >>> entry = MdEntry.from_file(Path("2024-01-15.md"))
            >>> db_meta = entry.to_database_metadata()
            >>> with db.session_scope() as session:
            ...     db.create_entry(session, db_meta)
        """
        # Validate required fields
        if not self.date:
            raise EntryValidationError("Entry date is required")

        if not self.file_path:
            raise EntryValidationError("File path is required for database operations")

        # Validate and normalize basic metrics
        word_count = self.metadata.get("word_count", 0)
        if not isinstance(word_count, int) or word_count < 0:
            logger.warning(f"Invalid word_count: {word_count}, defaulting to 0")
            word_count = 0

        reading_time = self.metadata.get("reading_time", 0.0)
        if not isinstance(reading_time, (int, float)) or reading_time < 0:
            logger.warning(f"Invalid reading_time: {reading_time}, defaulting to 0.0")
            reading_time = 0.0

        db_meta: Dict[str, Any] = {
            "date": self.date,
            "word_count": word_count,
            "reading_time": float(reading_time),
        }

        # Add file path if available
        if self.file_path:
            db_meta["file_path"] = str(self.file_path)

        # Related entries
        if "related_entries" in self.metadata:
            db_meta["related_entries"] = [
                d
                for d in self.metadata["related_entries"]
                if DataValidator.validate_date_string(d)
            ]

        # Parse city/cities
        if "city" in self.metadata and self.metadata["city"]:
            db_meta["cities"] = self._parse_city_field(self.metadata["city"])

        # Parse locations
        locations_by_city = {}
        if "locations" in self.metadata and self.metadata["locations"]:
            locations_by_city = self._parse_locations_field(
                self.metadata["locations"], db_meta.get("cities", [])
            )

            # Flatten to list of dicts with city context
            locations_list = []
            for city_name, loc_names in locations_by_city.items():
                for loc_name in loc_names:
                    locations_list.append({"name": loc_name, "city": city_name})

            db_meta["locations"] = locations_list

        # Parse people
        people_parsed = None
        if "people" in self.metadata and self.metadata["people"]:
            people_parsed = self._parse_people_field(self.metadata["people"])

            if "people" in people_parsed:
                db_meta["people"] = people_parsed["people"]
            if "alias" in people_parsed:
                db_meta["alias"] = people_parsed["alias"]

        # Dates: including their own locations and people
        parsed_dates = []
        exclude_entry_date = False
        has_dates_field = "dates" in self.metadata and self.metadata["dates"]

        if has_dates_field:
            parsed_dates, exclude_entry_date = self._parse_dates_field(
                self.metadata["dates"],
                people_parsed,
            )

        if not exclude_entry_date:
            entry_date_str: str = self.date.isoformat()

            if entry_date_str not in [d["date"] for d in parsed_dates]:
                entry_date_item: Dict[str, Any] = {"date": entry_date_str}

                # Add locations/people ONLY if NO dates field
                # (if dates field exists, user must explicitly include entry date)
                if not has_dates_field:
                    if "locations" in db_meta:
                        entry_date_item["locations"] = [
                            loc["name"] for loc in db_meta["locations"]
                        ]

                    if "people" in db_meta or "alias" in db_meta:
                        all_people = []
                        if "people" in db_meta:
                            all_people.extend(db_meta["people"])
                        if "alias" in db_meta:
                            all_people.extend(db_meta["alias"])
                        entry_date_item["people"] = all_people

                parsed_dates.append(entry_date_item)

        if parsed_dates:
            db_meta["dates"] = parsed_dates

        # References
        if "references" in self.metadata:
            db_meta["references"] = self._parse_references_field(
                self.metadata["references"]
            )

        # Poems
        if "poems" in self.metadata:
            db_meta["poems"] = self._parse_poems_field(self.metadata["poems"])

        # Manuscript metadata
        if "manuscript" in self.metadata:
            db_meta["manuscript"] = self.metadata["manuscript"]

        # Simple string/list fields with validation
        for db_field in ["epigraph", "epigraph_attribution", "notes"]:
            if db_field in self.metadata and self.metadata[db_field]:
                value = self.metadata[db_field]
                if isinstance(value, str):
                    normalized = DataValidator.normalize_string(value)
                    if normalized:
                        db_meta[db_field] = normalized
                else:
                    logger.warning(f"{db_field} should be a string, got {type(value)}")

        # List fields with validation
        for db_field in ["events", "tags"]:
            if db_field in self.metadata and self.metadata[db_field]:
                value = self.metadata[db_field]
                if isinstance(value, list):
                    validated_list = [
                        DataValidator.normalize_string(item)
                        for item in value
                        if DataValidator.normalize_string(item)
                    ]
                    if validated_list:
                        db_meta[db_field] = validated_list
                elif isinstance(value, str):
                    # Single string - convert to list
                    normalized = DataValidator.normalize_string(value)
                    if normalized:
                        db_meta[db_field] = [normalized]
                else:
                    logger.warning(f"{db_field} should be a list, got {type(value)}")

        return db_meta

    def to_markdown(self) -> str:
        """
        Generate complete Markdown content with YAML frontmatter.

        Returns:
            Full markdown file content as string

        Examples:
            >>> entry = MdEntry.from_database(entry_orm, body_lines)
            >>> markdown_text = entry.to_markdown()
            >>> Path("output.md").write_text(markdown_text)
        """
        yaml_content: str = self._generate_yaml_frontmatter()

        lines: List[str] = ["---", yaml_content, "---", ""]
        lines.extend(self.body)

        return "\n".join(lines)

    # ----- Database Conversion Helpers -----
    @staticmethod
    def _build_cities_metadata(entry: Entry) -> Optional[Union[str, List[str]]]:
        """Extract city/cities metadata from database Entry."""
        if not entry.cities:
            return None
        if len(entry.cities) == 1:
            return entry.cities[0].city
        return [c.city for c in entry.cities]

    @staticmethod
    def _build_locations_metadata(entry: Entry) -> Optional[Union[List[str], Dict[str, List[str]]]]:
        """Extract locations metadata from database Entry."""
        if not entry.locations:
            return None

        if not entry.cities or len(entry.cities) == 1:
            # No cities or single city - flat list of locations
            return [loc.name for loc in entry.locations]
        else:
            # Multiple cities - nested dict grouped by city
            locations_dict = {}
            for loc in entry.locations:
                city_name = loc.city.city
                if city_name not in locations_dict:
                    locations_dict[city_name] = []
                locations_dict[city_name].append(loc.name)
            return locations_dict

    @staticmethod
    def _build_people_metadata(entry: Entry) -> Optional[List[Dict[str, Any]]]:
        """Extract people and aliases metadata from database Entry."""
        if not entry.people and not entry.aliases_used:
            return None

        people_list = []
        aliases_by_person: Dict[int, Dict[str, Any]] = {}

        if entry.aliases_used:
            for alias in entry.aliases_used:
                person_id = alias.person_id
                if person_id not in aliases_by_person:
                    aliases_by_person[person_id] = {
                        "alias": [],
                        "name": alias.person.name,
                    }
                    if alias.person.name_fellow and alias.person.full_name:
                        fname = alias.person.full_name
                        aliases_by_person[person_id]["full_name"] = fname
                aliases_by_person[person_id]["alias"].append(alias.alias)

        for p in entry.people:
            if aliases_by_person and p.id in aliases_by_person:
                continue
            if p.name_fellow:
                people_list.append({"full_name": p.full_name})
            else:
                people_list.append({"name": p.name})

        people_list.extend(aliases_by_person.values())
        return people_list

    @staticmethod
    def _build_dates_metadata(entry: Entry) -> Optional[List[Union[str, Dict[str, Any]]]]:
        """Extract mentioned dates with context from database Entry."""
        if not entry.dates:
            return None

        dates_list = []

        # Check if entry date is in mentioned dates
        entry_date_in_mentioned = any(md.date == entry.date for md in entry.dates)

        # Add ~ if entry date NOT in mentioned dates
        if not entry_date_in_mentioned:
            dates_list.append("~")

        # Build all date items as dicts
        for md in entry.dates:
            date_dict: Dict = {"date": md.date.isoformat()}

            # Add locations
            if md.locations:
                date_dict["locations"] = [loc.name for loc in md.locations]

            # Add people
            if md.people:
                people_formatted = []
                for person in md.people:
                    if person.name_fellow:
                        people_formatted.append({"full_name": person.full_name})
                    else:
                        people_formatted.append({"name": person.name})
                date_dict["people"] = people_formatted

            # Add context
            if md.context:
                date_dict["context"] = md.context

            dates_list.append(date_dict)

        return dates_list

    @staticmethod
    def _build_references_metadata(entry: Entry) -> Optional[List[Dict[str, Any]]]:
        """Extract references metadata from database Entry."""
        if not entry.references:
            return None

        refs_list: List[Dict[str, Any]] = []
        for ref in entry.references:
            ref_dict: Dict[str, Any] = {}

            # Content is now optional
            if ref.content:
                ref_dict["content"] = ref.content

            # Add description if present
            if ref.description:
                ref_dict["description"] = ref.description

            # Add mode (default is direct)
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
    def _build_poems_metadata(entry: Entry) -> Optional[List[Dict[str, Any]]]:
        """Extract poems metadata from database Entry."""
        if not entry.poems:
            return None

        poems_list: List[Dict[str, Any]] = []
        for pv in entry.poems:
            poem_dict: Dict[str, Any] = {
                "title": pv.poem.title if pv.poem else "Untitled",
                "content": pv.content,
                "revision_date": pv.revision_date.isoformat(),
            }
            if pv.notes:
                poem_dict["notes"] = pv.notes
            poems_list.append(poem_dict)
        return poems_list

    @staticmethod
    def _build_manuscript_metadata(entry: Entry) -> Optional[Dict[str, Any]]:
        """Extract manuscript metadata from database Entry."""
        if not entry.manuscript:
            return None

        ms = entry.manuscript
        ms_dict: Dict[str, Any] = {
            "status": ms.status.value,
            "edited": ms.edited,
        }
        if ms.themes:
            ms_dict["themes"] = [theme.theme for theme in ms.themes]
        if ms.notes:
            ms_dict["notes"] = ms.notes
        return ms_dict

    # ----- Parsing Helpers -----
    def _parse_city_field(self, city_data: Union[str, List[str]]) -> List[str]:
        """
        Parse city field (single city or list of cities).

        Supports both formats:
        - Single string: "Montreal"
        - List of strings: ["Montreal", "Toronto"]

        Returns:
            List of city names (always a list, even for single city)

        Examples:
            >>> _parse_city_field("Montreal")
            ["Montreal"]
            >>> _parse_city_field(["Montreal", "Toronto"])
            ["Montreal", "Toronto"]
        """
        if isinstance(city_data, str):
            return [city_data.strip()]
        if isinstance(city_data, list):
            return [str(c).strip() for c in city_data if str(c).strip()]

        # Explicit fallback for unexpected types
        logger.warning(f"Invalid city_data type: {type(city_data)}")
        return []

    def _parse_locations_field(
        self, locations_data: Union[List[str], Dict[str, List[str]]], cities: List[str]
    ) -> Dict[str, List[str]]:
        """
        Parse locations field supporting both flat and nested formats.

        Formats:
        - Flat list (single city): ["Café X", "Park Y"]
        - Nested dict (multiple cities): {"Montreal": ["Café X"], "Toronto": ["Park Y"]}

        Args:
            locations_data: Either flat list or nested dict
            cities: List of cities from city field (for validation)

        Returns:
            Dict mapping city names to lists of location names

        Examples:
            >>> _parse_locations_field(["Café X", "Park Y"], ["Montreal"])
            {"Montreal": ["Café X", "Park Y"]}

            >>> _parse_locations_field(
            ...     {"Montreal": ["Café X"], "Toronto": ["Park Y"]},
            ...     ["Montreal", "Toronto"]
            ... )
            {"Montreal": ["Café X"], "Toronto": ["Park Y"]}
        """
        result = {}

        if isinstance(locations_data, list):
            # Flat list - all locations belong to single city
            if len(cities) != 1:
                logger.warning("Flat location list but multiple cities specified")
                return {}
            result[cities[0]] = [str(loc).strip() for loc in locations_data]

        elif isinstance(locations_data, dict):
            # Nested dict - locations grouped by city
            for city, locs in locations_data.items():
                city_name = str(city).strip()
                if isinstance(locs, list):
                    result[city_name] = [str(loc).strip() for loc in locs]
                elif isinstance(locs, str):
                    result[city_name] = [locs.strip()]

        return result

    def _parse_people_field(
        self, people_list: List[Union[str, Dict]]
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
             people_list: List of person specifications (strings or dicts)

        Returns dict with:
            - "people": List of person specs (strings/dicts)
            - "alias": List of alias strings that were mentioned

         Examples:
             >>> _parse_people_field(["John", "Jane Smith", "Bob (Robert)", "@Bobby"])
             {
                "people": [
                    {"name": "John"},
                    {"full_name": "Jane Smith"},
                    {"name": "Bob", "full_name": "Robert"},
                ],
                "alias": [{"alias": "Bobby"}]
             }
        """
        normalized_people = []
        aliases_mentioned = []

        for person_item in people_list:
            name: Optional[str] = None
            full_name: Optional[str] = None
            alias: Optional[Sequence[str]] = None

            if isinstance(person_item, dict):
                person_dict = {}
                if "name" in person_item:
                    name = DataValidator.normalize_string(person_item["name"])
                if "full_name" in person_item:
                    full_name = DataValidator.normalize_string(person_item["full_name"])
                if "alias" in person_item:
                    alias_raw = person_item["alias"]
                    if isinstance(alias_raw, str):
                        alias_raw = [alias_raw]

                    aliases_raw = [
                        DataValidator.normalize_string(a) for a in alias_raw if a
                    ]
                    alias = [a for a in aliases_raw if a]

                if full_name:
                    person_dict["full_name"] = full_name

                if name:
                    person_dict["name"] = name

                if person_dict:
                    normalized_people.append(person_dict)

                if alias:
                    alias_dict: Dict[str, Any] = {"alias": alias}
                    if person_dict:
                        alias_dict.update(person_dict)
                    aliases_mentioned.append(alias_dict)

                continue

            person_str = DataValidator.normalize_string(person_item)
            if not person_str:
                continue

            # Extract name and expansion
            primary, expansion = parsers.extract_name_and_expansion(person_str)

            # Check if alias
            if primary.startswith("@"):
                alias = parsers.split_hyphenated_to_spaces(primary[1:])
                if expansion:
                    if " " in expansion:
                        full_name = expansion
                    else:
                        name = parsers.split_hyphenated_to_spaces(expansion)
            elif " " in primary:
                full_name = primary
            else:
                name = parsers.split_hyphenated_to_spaces(primary)
                full_name = expansion

            if alias:
                if name or full_name:
                    aliases_mentioned.append(
                        {
                            "alias": alias,
                            "name": name,
                            "full_name": full_name,
                        }
                    )
                else:
                    aliases_mentioned.append(alias)

            if name or full_name:
                normalized_people.append({"name": name, "full_name": full_name})

        return {"people": normalized_people, "alias": aliases_mentioned}

    @staticmethod
    def _find_person_in_parsed(
        person_str: str, people_parsed: Dict[str, List]
    ) -> Optional[Dict[str, Any]]:
        """
        Look up a person string in the people_parsed structure.

        Searches both the "people" list and "alias" list to find a matching
        person specification.

        Args:
            person_str: Person name or alias to find
            people_parsed: Parsed people structure with "people" and/or "alias" keys

        Returns:
            Matching person dict if found, otherwise {"name": person_str}
        """
        # Check in people list
        if "people" in people_parsed:
            for person_spec in people_parsed["people"]:
                if isinstance(person_spec, dict):
                    # Check name or full_name matches
                    if (
                        person_spec.get("name") == person_str
                        or person_spec.get("full_name") == person_str
                    ):
                        return person_spec
                elif person_spec == person_str:
                    return {"name": person_str}

        # Check in alias list
        if "alias" in people_parsed:
            for alias_spec in people_parsed["alias"]:
                if isinstance(alias_spec, dict):
                    alias_vals = alias_spec.get("alias", [])
                    if not isinstance(alias_vals, list):
                        alias_vals = [alias_vals]

                    if person_str in alias_vals:
                        return alias_spec

        # Not found - treat as simple name
        return {"name": person_str}

    def _parse_dates_field(
        self,
        dates_data: Union[List[Union[str, Dict]], Dict],
        people_parsed: Optional[Dict[str, List]],
    ) -> Tuple[List, bool]:
        """
        Parse dates field with inline or nested format.
        Associates locations/people to specific dates.

        For people values in dates, looks them up in people_parsed
        in order to get their keys.

        Supports:
        - Simple date: "2025-06-01"
        - Inline context: "2025-06-01 (thesis exam)"
        - Nested format: {"date": "2025-06-01", "context": "thesis exam"}

        Args:
            dates_data: List of date specifications
            locations_by_city: {city: [locations]} from locations field
            people_parsed: Result from _parse_people_field() with keys already assigned
                Example: {
                    "people": [{"name": "Clara"}],
                    "alias": [{"alias": "Majo", "name": "María-José"}]
                }

        Returns:
            Tuple of (parsed_dates, exclude_entry_date_flag)

        Examples:
            >>> _parse_dates_field([
            ...     "2025-06-01",
            ...     "2025-06-15 (birthday party at #Church)",
            ...     {"date": "2025-07-01", "context": "celebration", "person": "Alda"}
            ... ])
            [
                {"date": "2025-06-01"},
                {
                    "date": "2025-06-15",
                    "context": "birthday party at Church",
                    "locations": "Church,
                },
                {
                    "date": "2025-07-01",
                    "context": "celebration",
                    "people": "Alda",
                }
            ]
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
                date_obj, raw_context = parsers.parse_date_context(item)

                if not DataValidator.validate_date_string(date_obj):
                    logger.warning(f"Invalid date format, skipping: {date_obj}")
                    continue

                date_dict: Dict[str, Union[date, str, List]] = {"date": date_obj}

                if raw_context:
                    context_dict = parsers.extract_context_refs(raw_context)
                    date_dict.update(context_dict)

                normalized.append(date_dict)

            # --- Dictionary ---
            if isinstance(item, dict):
                if "date" not in item:
                    logger.warning(f"Date dict missing 'date' field: {item}")
                    continue

                if not DataValidator.validate_date_string(item["date"]):
                    logger.warning(f"Invalid date format, skipping: {item}")
                    continue

                date_dict = {"date": item["date"]}
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
                    date_dict["locations"] = [
                        DataValidator.normalize_string(loc)
                        for loc in all_locations
                        if DataValidator.normalize_string(loc)
                    ]

                # --- People - LOOKUP IN people_parsed ---
                if ("people" in item or people_context) and people_parsed:
                    people_field = item["people"]
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

                        person_spec = self._find_person_in_parsed(person_str, people_parsed)
                        if person_spec:
                            people_list.append(person_spec)

                    if people_list:
                        date_dict["people"] = people_list

                normalized.append(date_dict)

        return normalized, exclude_entry_date

    def _parse_references_field(
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
                "type": str (required: book/article/film/poem/etc),
                "author": str (optional)
            } (optional)
        }

        Args:
            refs_data: List of reference dictionaries

        Returns:
            List of validated reference dicts with normalized types

        Examples:
            >>> _parse_references_field([{
            ...     "content": "To be or not to be",
            ...     "mode": "direct",
            ...     "source": {
            ...         "title": "Hamlet",
            ...         "type": "book",
            ...         "author": "Shakespeare"
            ...     }
            ... }])
            [{
                "content": "To be or not to be",
                "mode": "direct",
                "source": {
                    "title": "Hamlet",
                    "type": ReferenceType.BOOK,
                    "author": "Shakespeare"
                }
            }]
        """
        normalized = []

        for ref in refs_data:
            if not isinstance(ref, dict):
                logger.warning(f"Invalid reference format: {ref}")
                continue

            content = DataValidator.normalize_string(ref.get("content"))
            description = DataValidator.normalize_string(ref.get("description"))
            if not content and not description:
                logger.warning(
                    "Reference missing both 'content' and 'description' fields"
                )
                continue

            ref_dict: Dict[str, Any] = {}

            if content:
                ref_dict["content"] = content

            if description:
                ref_dict["description"] = description

            # Optional mode (default: direct)
            mode = DataValidator.normalize_string(ref.get("mode", "direct"))
            if mode in ["direct", "indirect", "paraphrase", "visual"]:
                ref_dict["mode"] = mode
            else:
                logger.warning(
                    f"Invalid reference mode '{mode}', defaulting to 'direct'"
                )
                ref_dict["mode"] = "direct"

            # Optional speaker
            if "speaker" in ref:
                speaker = DataValidator.normalize_string(ref["speaker"])
                if speaker:
                    ref_dict["speaker"] = speaker

            # Optional source
            if "source" in ref and isinstance(ref["source"], dict):
                source = ref["source"]

                # Validate required source fields
                if "title" not in source or not source["title"]:
                    logger.warning(f"Source missing title: {source}")
                elif "type" not in source:
                    logger.warning(f"Source missing type: {source}")
                else:
                    # Normalize type enum (now includes 'poem')
                    source_type = DataValidator.normalize_reference_type(source["type"])
                    if source_type:
                        ref_dict["source"] = {
                            "title": DataValidator.normalize_string(source["title"]),
                            "type": source_type,  # This is now ReferenceType enum
                        }

                        # Optional author
                        if "author" in source:
                            author = DataValidator.normalize_string(source["author"])
                            if author:
                                ref_dict["source"]["author"] = author
                    else:
                        logger.warning(
                            f"Invalid source type '{source['type']}' in reference"
                        )

            normalized.append(ref_dict)

        return normalized

    def _parse_poems_field(
        self, poems_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Parse and normalize poems with Poem parent handling.

        Poem format:
        {
            "title": str (required),
            "content": str (required),
            "revision_date": str|date (optional, defaults to entry.date),
            "notes": str (optional),
            "version_hash": str (optional, auto-generated if not provided)
        }

        If revision_date is not provided or is invalid, it defaults to the
        entry's date, ensuring all poems have a documented revision date.

        Args:
            poems_data: List of poem dictionaries

        Returns:
            List of validated poem dicts ready for database

        Examples:
            >>> _parse_poems_field([{
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
        normalized = []

        for poem in poems_data:
            if not isinstance(poem, dict):
                logger.warning(f"Invalid poem format: {poem}")
                continue

            if "title" not in poem or not poem["title"]:
                logger.warning("Poem missing required 'title' field")
                continue

            if "content" not in poem or not poem["content"]:
                logger.warning("Reference missing required 'content' field")
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
                    poem_dict["revision_date"] = self.date
            else:
                # Default to entry date when revision_date is not specified
                poem_dict["revision_date"] = self.date

            # Optional notes
            if "notes" in poem:
                notes = DataValidator.normalize_string(poem["notes"])
                if notes:
                    poem_dict["notes"] = notes

            normalized.append(poem_dict)

        return normalized

    # ----- YAML Generation -----
    def _generate_yaml_frontmatter(self) -> str:
        """
        Generate YAML frontmatter from metadata.

        Creates human-readable, properly formatted YAML that preserves
        the progressive complexity design (minimal → comprehensive).
        """
        parts: List[str] = []

        # Required fields
        parts.append(f"date: {self.date.isoformat()}")
        parts.append(f"word_count: {self.metadata.get('word_count', 0)}")
        parts.append(f"reading_time: {self.metadata.get('reading_time', 0.0):.1f}")

        # Optional core metadata
        if self.metadata.get("epigraph"):
            parts.append(f'\nepigraph: "{md.yaml_escape(self.metadata["epigraph"])}"')

        if self.metadata.get("epigraph_attribution"):
            parts.append(
                f'epigraph_attribution: "{md.yaml_escape(self.metadata["epigraph_attribution"])}"'
            )

        # City
        if self.metadata.get("city"):
            city_data = self.metadata["city"]
            if isinstance(city_data, list):
                parts.append(f"\ncity: {md.yaml_list(city_data)}")
            else:
                parts.append(f"\ncity: {city_data}")

        # Locations
        if self.metadata.get("locations"):
            locs = self.metadata["locations"]
            if isinstance(locs, list):
                parts.append(f"\nlocations: {md.yaml_list(locs)}")
            elif isinstance(locs, dict):
                parts.append("\nlocations:")
                for city, venues in locs.items():
                    if isinstance(venues, list):
                        parts.append(f"  {city}: {md.yaml_list(venues)}")
                    else:
                        parts.append(f"  {city}: {venues}")

        # People
        if self.metadata.get("people"):
            people = self.metadata["people"]
            if any(isinstance(p, dict) for p in people) or len(people) >= 5:
                parts.append("\npeople:")
                for p in people:
                    if isinstance(p, dict):
                        if "alias" in p:
                            # Alias format: @alias or @alias (name)
                            alias_vals = p["alias"]
                            if isinstance(alias_vals, list):
                                alias_str = ", ".join(
                                    f"@{parsers.spaces_to_hyphenated(a)}"
                                    for a in alias_vals
                                )
                            else:
                                alias_str = (
                                    f"@{parsers.spaces_to_hyphenated(alias_vals)}"
                                )

                            if "full_name" in p:
                                parts.append(f'  - "{alias_str} ({p["full_name"]})"')
                            elif "name" in p:
                                parts.append(f'  - "{alias_str} ({p["name"]})"')
                            else:
                                parts.append(f"  - {alias_str}")
                        else:
                            # Regular person: name or full_name
                            name = parsers.spaces_to_hyphenated(p.get("name", ""))
                            full = p.get("full_name", "")
                            if full:
                                parts.append(f"  - {full}")
                            else:
                                parts.append(f"  - {name}")
                    else:
                        parts.append(f"  - {parsers.spaces_to_hyphenated(p)}")
            else:
                parts.append(f"\npeople: {md.yaml_list(people, hyphenated=True)}")

        # Simple list fields
        for db_field in ["events", "tags"]:
            if db_field in self.metadata and self.metadata[db_field]:
                parts.append(f"\n{db_field}: {md.yaml_list(self.metadata[db_field])}")

        # Dates (with optional context)
        if self.metadata.get("dates"):
            dates_data = self.metadata["dates"]
            parts.append("\ndates:")

            for date_item in dates_data:
                # Handle ~ opt-out
                if date_item == "~":
                    parts.append("  - ~")
                    continue

                # Date item is always a dict from from_database()
                if not isinstance(date_item, dict):
                    continue

                date_str = date_item.get("date")
                locations = date_item.get("locations", [])
                people = date_item.get("people", [])
                context = date_item.get("context")

                # DECIDE: Inline vs dict format
                if locations or people:
                    parts.append(f"  - date: {date_str}")

                    if locations:
                        parts.append(f"    locations: {md.yaml_list(locations)}")

                    if people:
                        parts.append("    people:")
                        for p in people:
                            if full := p.get("full_name", ""):
                                parts.append(f"      - {full}")
                            else:
                                name = parsers.spaces_to_hyphenated(p.get("name", ""))
                                parts.append(f"      - {name}")

                    if context:
                        parts.append(f'    context: "{md.yaml_escape(context)}"')

                else:
                    # Add text context
                    if context:
                        parts.append(f'  - "{date_str} ({context})"')
                    else:
                        # Just the date
                        parts.append(f'  - "{date_str}"')

        # Related entries
        if self.metadata.get("related_entries"):
            parts.append(
                f"\nrelated_entries: {md.yaml_list(self.metadata['related_entries'])}"
            )

        # References
        if self.metadata.get("references"):
            parts.append("\nreferences:")
            for ref in self.metadata["references"]:
                # Content or description (at least one required)
                if "content" in ref:
                    parts.append(f'  - content: "{md.yaml_escape(ref["content"])}"')
                elif "description" in ref:
                    parts.append(
                        f'  - description: "{md.yaml_escape(ref["description"])}"'
                    )

                # Mode (only if not default)
                if "mode" in ref and ref["mode"] != "direct":
                    parts.append(f'    mode: {ref["mode"]}')

                if "speaker" in ref:
                    parts.append(f'    speaker: "{md.yaml_escape(ref["speaker"])}"')

                if "source" in ref:
                    src = ref["source"]
                    if isinstance(src, dict):
                        parts.append("    source:")
                        parts.append(f'      title: "{md.yaml_escape(src["title"])}"')
                        parts.append(f'      type: {src.get("type", "unknown")}')
                        if "author" in src:
                            parts.append(
                                f'      author: "{md.yaml_escape(src["author"])}"'
                            )

        # Poems
        if self.metadata.get("poems"):
            parts.append("\npoems:")
            for poem in self.metadata["poems"]:
                parts.append(f'  - title: "{md.yaml_escape(poem["title"])}"')
                parts.append("    content: |")
                for line in poem["content"].splitlines():
                    parts.append(f"      {line}")
                if "revision_date" in poem:
                    parts.append(f'    revision_date: {poem["revision_date"]}')
                if "notes" in poem:
                    parts.append(f'    notes: "{md.yaml_escape(poem["notes"])}"')

        # Manuscript
        if self.metadata.get("manuscript"):
            ms = self.metadata["manuscript"]
            parts.append("\nmanuscript:")
            parts.append(f"  status: {ms.get('status', 'draft')}")
            parts.append(f"  edited: {str(ms.get('edited', False)).lower()}")
            if "themes" in ms and ms["themes"]:
                parts.append(f"  themes: {md.yaml_list(ms['themes'])}")
            if "notes" in ms:
                parts.append(f'  notes: {md.yaml_multiline(ms["notes"])}')

        # Notes (at end)
        if self.metadata.get("notes"):
            parts.append(f"\nnotes: {md.yaml_multiline(self.metadata['notes'])}")

        return "\n".join(parts)

    # ----- Validation -----
    def validate(self) -> List[str]:
        """
        Validate entry data and return list of issues.

        Returns:
            List of validation error messages (empty if valid)
        """
        issues: List[str] = []

        # Required fields
        if not self.date:
            issues.append("Missing date")

        if not self.body:
            issues.append("Empty body content")

        # Validate word_count
        if "word_count" in self.metadata:
            wc = DataValidator.normalize_int(self.metadata["word_count"])
            if wc is not None and wc < 0:
                issues.append("Word count cannot be negative")
            elif wc is None:
                issues.append("Word count must be a number")

        # Validate dates
        if "dates" in self.metadata:
            for date_item in self.metadata["dates"]:
                if isinstance(date_item, dict):
                    if "date" not in date_item:
                        issues.append("Date item missing 'date' field")
                    else:
                        if not DataValidator.validate_date_string(
                            str(date_item["date"])
                        ):
                            issues.append(f"Invalid date format: {date_item['date']}")
                elif isinstance(date_item, str):
                    if not DataValidator.validate_date_string(date_item):
                        issues.append(f"Invalid date format: {date_item}")

        return issues

    @property
    def is_valid(self) -> bool:
        """Check if entry has valid structure."""
        return len(self.validate()) == 0

    def __repr__(self) -> str:
        """String representation."""
        return f"<MdEntry(date={self.date}, file={self.file_path})>"

    def __str__(self) -> str:
        """Human-readable string."""
        return f"MdEntry {self.date.isoformat()} ({len(self.body)} lines)"
