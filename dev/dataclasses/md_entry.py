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
from typing import Dict, Any, List, Optional, Union

from dev.core.validators import DataValidator
from dev.database.models import Entry
from dev.utils import md, parsers

logger = logging.getLogger(__name__)


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
            raise ValueError("No YAML frontmatter found (must start with ---)")

        try:
            metadata: Any = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Invalid YAML frontmatter: {e}") from e

        if not isinstance(metadata, dict):
            raise ValueError("YAML frontmatter must be a dictionary")

        # Extract required date field
        if "date" not in metadata:
            raise ValueError("Missing required 'date' field in frontmatter")

        entry_date = DataValidator.normalize_date(metadata["date"])
        if entry_date is None:
            raise ValueError(f"Invalid date format: {metadata['date']}")

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

        # City/Cities
        if entry.cities:
            if len(entry.cities) == 1:
                city = entry.cities[0]
                metadata["city"] = city.city
            else:
                metadata["city"] = [c.city for c in entry.cities]

        # Locations
        if entry.locations:
            if len(entry.cities) == 1:
                # Single city - flat list of locations
                metadata["locations"] = [loc.name for loc in entry.locations]
            else:
                # Multiple cities - nested dict
                locations_dict = {}
                for loc in entry.locations:
                    city_name = loc.city.city
                    if city_name not in locations_dict:
                        locations_dict[city_name] = []
                    locations_dict[city_name].append(loc.name)
                metadata["locations"] = locations_dict

        # Relationships
        if entry.people:
            metadata["people"] = [
                (
                    {
                        "name": p.name,
                        "full_name": p.full_name,
                    }
                    if getattr(p, "name_fellow")
                    else p.name
                )
                for p in entry.people
            ]

        if entry.events:
            metadata["events"] = [evt.event for evt in entry.events]

        if entry.tags:
            metadata["tags"] = [tag.tag for tag in entry.tags]

        # Mentioned dates with context
        if entry.dates:
            dates_list: List[Union[str, Dict[str, str]]] = []
            for md in entry.dates:
                if md.context:
                    dates_list.append(
                        {"date": md.date.isoformat(), "context": md.context}
                    )
                else:
                    dates_list.append(md.date.isoformat())
            metadata["dates"] = dates_list

        # Related entries
        if entry.related_entries:
            metadata["related_entries"] = [
                r_e.date.isoformat() for r_e in entry.related_entries
            ]

        # References
        if entry.references:
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
            metadata["references"] = refs_list

        # Poems
        if entry.poems:
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
            metadata["poems"] = poems_list

        # Manuscript metadata
        if entry.manuscript:
            ms = entry.manuscript
            ms_dict: Dict[str, Any] = {
                "status": ms.status.value,
                "edited": ms.edited,
            }
            if ms.themes:
                ms_dict["themes"] = [theme.theme for theme in ms.themes]
            if ms.notes:
                ms_dict["notes"] = ms.notes
            metadata["manuscript"] = ms_dict

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
        if not self.date:
            raise ValueError("Entry date is required")

        if not self.file_path:
            raise ValueError("File path is required for database operations")

        db_meta: Dict[str, Any] = {
            "date": self.date,
            "word_count": self.metadata.get("word_count", 0),
            "reading_time": self.metadata.get("reading_time", 0.0),
        }

        # Add file path if available
        if self.file_path:
            db_meta["file_path"] = str(self.file_path)

        # Parse epigraph
        if "epigraph" in self.metadata:
            db_meta["epigraph"] = DataValidator.normalize_string(
                self.metadata["epigraph"]
            )

        if "epigraph_attribution" in self.metadata:
            db_meta["epigraph_attribution"] = DataValidator.normalize_string(
                self.metadata["epigraph_attribution"]
            )

        # Parse city/cities
        if "city" in self.metadata and self.metadata["city"]:
            db_meta["cities"] = self._parse_city_field(self.metadata["city"])

        # Parse locations
        if "locations" in self.metadata and self.metadata["locations"]:
            locations_dict = self._parse_locations_field(
                self.metadata["locations"], db_meta.get("cities", [])
            )

            # Flatten to list of dicts with city context
            locations_list = []
            for city_name, loc_names in locations_dict.items():
                for loc_name in loc_names:
                    locations_list.append({"name": loc_name, "city": city_name})

            db_meta["locations"] = locations_list

        # Parse people (handle hyphenated names)
        if "people" in self.metadata and self.metadata["people"]:
            db_meta["people"] = self._parse_people_field(self.metadata["people"])

        # Simple lists
        for db_field in ["events", "tags"]:
            if db_field in self.metadata and self.metadata[db_field]:
                db_meta[db_field] = DataValidator.normalize_string(
                    self.metadata[db_field]
                )

        # Dates with optional context
        if "dates" in self.metadata:
            db_meta["dates"] = self._parse_dates_field(self.metadata["dates"])

        # Related entries
        if "related_entries" in self.metadata:
            db_meta["related_entries"] = [
                d
                for d in self.metadata["related_entries"]
                if DataValidator.validate_date_string(d)
            ]

        # References
        if "references" in self.metadata:
            db_meta["references"] = self._parse_references_field(
                self.metadata["references"]
            )

        # Poems
        if "poems" in self.metadata:
            db_meta["poems"] = self._parse_poems_field(self.metadata["poems"])

        # Notes
        if "notes" in self.metadata:
            db_meta["notes"] = DataValidator.normalize_string(self.metadata["notes"])

        # Manuscript metadata
        if "manuscript" in self.metadata:
            db_meta["manuscript"] = self.metadata["manuscript"]

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
    ) -> List[Dict[str, Any]]:
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

         Returns:
             List of dicts with 'name', 'full_name', and/or 'alias' keys

         Examples:
             >>> _parse_people_field(["John", "Jane Smith", "Bob (Robert)", "@Bobby"])
             [
                 {"name": "John"},
                 {"full_name": "Jane Smith"},
                 {"name": "Bob", "full_name": "Robert"},
                 {"alias": "Bobby"}
             ]
        """
        normalized = []

        for person_item in people_list:
            if isinstance(person_item, dict):
                person_dict = {}
                if "name" in person_item:
                    person_dict["name"] = DataValidator.normalize_string(
                        person_item["name"]
                    )
                if "full_name" in person_item:
                    person_dict["full_name"] = DataValidator.normalize_string(
                        person_item["full_name"]
                    )
                if person_dict:
                    normalized.append(person_dict)
                continue

            alias: Optional[str] = None
            name: Optional[str] = None
            full_name: Optional[str] = None

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

            if alias or name or full_name:
                normalized.append(
                    {
                        "alias": alias,
                        "name": name,
                        "full_name": full_name,
                    }
                )

        return normalized

    def _parse_dates_field(
        self, dates_data: Union[List[str], List[Dict[str, str]]]
    ) -> List[Dict[str, str]]:
        """
        Parse dates field with inline or nested format.

        Supports:
        - Simple date: "2025-06-01"
        - Inline context: "2025-06-01 (thesis exam)"
        - Nested format: {"date": "2025-06-01", "context": "thesis exam"}

        Args:
            dates_data: List of date specifications

        Returns:
            List of dicts with 'date' and optional 'context' keys

        Examples:
            >>> _parse_dates_field([
            ...     "2025-06-01",
            ...     "2025-06-15 (birthday)",
            ...     {"date": "2025-07-01", "context": "celebration"}
            ... ])
            [
                {"date": "2025-06-01"},
                {"date": "2025-06-15", "context": "birthday"},
                {"date": "2025-07-01", "context": "celebration"}
            ]
        """
        normalized = []

        for item in dates_data:
            if isinstance(item, str):
                # Check for inline context
                date_obj, context = parsers.parse_date_context(item)

                if DataValidator.validate_date_string(date_obj):
                    date_dict = {"date": date_obj}
                    if context:
                        date_dict["context"] = context
                    normalized.append(date_dict)
                else:
                    logger.warning(f"Invalid date format, skipping: {date_obj}")

            elif isinstance(item, dict) and "date" in item:
                if DataValidator.validate_date_string(item["date"]):
                    normalized.append(item)
                else:
                    logger.warning(f"Invalid date format, skipping: {item}")

        return normalized

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
            "revision_date": str|date (optional),
            "notes": str (optional),
            "version_hash": str (optional, auto-generated if not provided)
        }

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

            # Optional revision_date
            if "revision_date" in poem:
                rev_date = DataValidator.normalize_date(poem["revision_date"])
                if rev_date:
                    poem_dict["revision_date"] = rev_date
                else:
                    logger.warning(
                        f"Invalid revision_date in poem '{poem['title']}': {poem['revision_date']}"
                    )

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
                [
                    (
                        parts.append(
                            f'  - "{parsers.spaces_to_hyphenated(p["name"])}'
                            f' ({p["full_name"]})"'
                        )
                        if isinstance(p, dict)
                        else parts.append(f"  - {parsers.spaces_to_hyphenated(p)}")
                    )
                    for p in people
                ]
            else:
                parts.append(f"\npeople: {md.yaml_list(people, hyphenated=True)}")

        # Simple list fields
        for db_field in ["events", "tags"]:
            if db_field in self.metadata and self.metadata[db_field]:
                parts.append(f"\n{db_field}: {md.yaml_list(self.metadata[db_field])}")

        # Dates (with optional context)
        if self.metadata.get("dates"):
            parts.append("\ndates:")
            for date_item in self.metadata["dates"]:
                if isinstance(date_item, dict):
                    parts.append(f'  - date: "{date_item["date"]}"')
                    if "context" in date_item:
                        parts.append(f'    context: "{date_item["context"]}"')
                else:
                    parts.append(f'  - "{date_item}"')

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
