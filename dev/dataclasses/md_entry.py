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
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import logging
import yaml
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, TypedDict

# --- Local imports ---
from dev.core.exceptions import EntryParseError, EntryValidationError
from dev.core.validators import DataValidator
from dev.database.models import Entry
from dev.utils import md, parsers
from dev.dataclasses.md_entry_validator import MdEntryValidator
from dev.dataclasses.parsers import DbToYamlExporter, YamlToDbParser

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
            raise EntryValidationError(
                "No YAML frontmatter found (must start with ---)"
            )

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

        # Complex metadata - use DbToYamlExporter
        exporter = DbToYamlExporter()

        city = exporter.build_cities_metadata(entry)
        if city is not None:
            metadata["city"] = city

        locations = exporter.build_locations_metadata(entry)
        if locations is not None:
            metadata["locations"] = locations

        people = exporter.build_people_metadata(entry)
        if people is not None:
            metadata["people"] = people

        dates = exporter.build_dates_metadata(entry)
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
        references = exporter.build_references_metadata(entry)
        if references is not None:
            metadata["references"] = references

        poems = exporter.build_poems_metadata(entry)
        if poems is not None:
            metadata["poems"] = poems

        manuscript = exporter.build_manuscript_metadata(entry)
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

        # Create parser instance
        parser = YamlToDbParser(self.date, self.metadata)

        # Parse city/cities
        if "city" in self.metadata and self.metadata["city"]:
            db_meta["cities"] = parser.parse_city_field(self.metadata["city"])

        # Parse locations
        locations_by_city = {}
        if "locations" in self.metadata and self.metadata["locations"]:
            locations_by_city = parser.parse_locations_field(
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
            people_parsed = parser.parse_people_field(self.metadata["people"])

            if "people" in people_parsed:
                db_meta["people"] = people_parsed["people"]
            if "alias" in people_parsed:
                db_meta["alias"] = people_parsed["alias"]

        # Dates: including their own locations and people
        parsed_dates = []
        exclude_entry_date = False
        has_dates_field = "dates" in self.metadata and self.metadata["dates"]

        if has_dates_field:
            parsed_dates, exclude_entry_date = parser.parse_dates_field(
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
            db_meta["references"] = parser.parse_references_field(
                self.metadata["references"]
            )

        # Poems
        if "poems" in self.metadata:
            db_meta["poems"] = parser.parse_poems_field(self.metadata["poems"])

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
        parts.append(f"reading_time: {self.metadata.get('reading_time', 0.0):.2f}")

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
                        # hyphenated=True preserves existing hyphens with underscores
                        parts.append(f"    locations: {md.yaml_list(locations, hyphenated=True)}")

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
        return MdEntryValidator.validate_entry(self.date, self.body, self.metadata)

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
