#!/usr/bin/env python3
"""
metadata_entry.py
-----------------
Dataclass representing journal metadata from standalone YAML files.

This module handles the intermediary data structure for metadata YAML files
that contain narrative analysis (scenes, events, threads, arcs, etc.).

These files are companions to the Markdown prose files and contain:
- Narrative analysis (scenes, events, threads)
- Editorial metadata (summary, rating, rating_justification)
- Controlled vocabulary (arcs, tags, themes, motifs)
- Creative content (poems, references)

Key Design:
- Separate from MD prose: metadata lives in YAML, not frontmatter
- Human-populated: created by txt2md skeleton, filled by human
- Validate-only mode: check entities against curation without DB
- Database-mappable: every field maps to ORM models

Data Flow:
    txt2md creates skeleton → Human populates → Validate → DB import

Usage:
    from dev.dataclasses.metadata_entry import MetadataEntry
    from dev.curation.resolve import EntityResolver

    # Load and parse
    entry = MetadataEntry.from_file(Path("2024-12-03.yaml"))

    # Validate entities against curation
    resolver = EntityResolver.load()
    result = entry.validate_entities(resolver)
    if result.has_errors:
        for error in result.errors:
            print(error)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Set, TypedDict, Union

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.exceptions import MetadataValidationError
from dev.core.validators import DataValidator

if TYPE_CHECKING:
    from dev.curation.resolve import EntityResolver


# =============================================================================
# Type Definitions
# =============================================================================


class MotifSpec(TypedDict, total=False):
    """Type specification for motif metadata."""

    name: str
    description: str


class SceneSpec(TypedDict, total=False):
    """Type specification for scene metadata."""

    name: str
    description: str
    date: Union[str, List[str]]
    people: List[str]
    locations: List[str]


class EventSpec(TypedDict, total=False):
    """Type specification for event metadata."""

    name: str
    scenes: List[str]


class ThreadSpec(TypedDict, total=False):
    """Type specification for thread metadata."""

    name: str
    from_: str  # 'from' is a Python keyword
    to: str
    entry: Optional[str]
    content: str
    people: List[str]
    locations: List[str]


class ReferenceSourceSpec(TypedDict, total=False):
    """Type specification for reference source metadata."""

    title: str
    author: str
    type: str
    url: str


class ReferenceSpec(TypedDict, total=False):
    """Type specification for reference metadata."""

    content: str
    description: str
    mode: str
    source: ReferenceSourceSpec


class PoemSpec(TypedDict, total=False):
    """Type specification for poem metadata."""

    title: str
    content: str


# =============================================================================
# Validation Result
# =============================================================================


@dataclass
class MetadataValidationResult:
    """
    Results from metadata validation.

    Tracks structural errors (blocking) and entity warnings (non-blocking).

    Attributes:
        file_path: Path to the validated file
        errors: List of structural error messages (blocking)
        warnings: List of entity warnings with suggestions
    """

    file_path: str = ""
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        """Check if there are blocking errors."""
        return len(self.errors) > 0

    @property
    def is_valid(self) -> bool:
        """Check if structurally valid (ignores warnings)."""
        return not self.has_errors

    def add_error(self, message: str) -> None:
        """
        Add a blocking error message.

        Args:
            message: Error message to add
        """
        self.errors.append(message)

    def add_warning(self, message: str) -> None:
        """
        Add a non-blocking warning message.

        Args:
            message: Warning message to add
        """
        self.warnings.append(message)

    def summary(self) -> str:
        """
        Get human-readable summary.

        Returns:
            Formatted summary string
        """
        if self.is_valid:
            if self.warnings:
                return f"Valid (with {len(self.warnings)} warnings)"
            return "Valid"
        return f"Invalid: {len(self.errors)} errors, {len(self.warnings)} warnings"


# =============================================================================
# MetadataEntry Dataclass
# =============================================================================


@dataclass
class MetadataEntry:
    """
    Represents journal metadata parsed from standalone YAML files.

    This is the intermediary format for metadata YAML files that contain
    narrative analysis and editorial metadata. It is separate from the
    Markdown prose files.

    Attributes:
        date: Entry date (required, matches the MD file)
        summary: Editorial summary of the entry
        rating: Numeric rating (typically 0-5)
        rating_justification: Explanation for the rating
        arcs: Story arcs this entry belongs to
        tags: Keyword tags
        themes: Thematic elements
        motifs: Motif instances with descriptions
        scenes: Narrative scenes with metadata
        events: Event groupings of scenes
        threads: Temporal connections to other moments
        poems: Poems in this entry
        references: External references and citations
        file_path: Source file path if loaded from file
        raw_data: Original parsed YAML for reference

    Examples:
        >>> entry = MetadataEntry.from_file(Path("2024-12-03.yaml"))
        >>> print(entry.date)
        2024-12-03
        >>> for scene in entry.scenes:
        ...     print(scene["name"])
    """

    # Required field
    date: date

    # Editorial metadata
    summary: str = ""
    rating: Optional[float] = None
    rating_justification: str = ""

    # Controlled vocabulary
    arcs: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)

    # Complex fields
    motifs: List[MotifSpec] = field(default_factory=list)
    scenes: List[SceneSpec] = field(default_factory=list)
    events: List[EventSpec] = field(default_factory=list)
    threads: List[ThreadSpec] = field(default_factory=list)
    poems: List[PoemSpec] = field(default_factory=list)
    references: List[ReferenceSpec] = field(default_factory=list)

    # Source tracking
    file_path: Optional[Path] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)

    # =========================================================================
    # Construction Methods
    # =========================================================================

    @classmethod
    def from_file(cls, file_path: Path) -> MetadataEntry:
        """
        Parse a metadata YAML file.

        Args:
            file_path: Path to .yaml metadata file

        Returns:
            Parsed MetadataEntry instance

        Raises:
            FileNotFoundError: If file doesn't exist
            MetadataValidationError: If YAML is invalid or missing date
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Metadata file not found: {file_path}")

        content = file_path.read_text(encoding="utf-8")
        return cls.from_yaml_text(content, file_path)

    @classmethod
    def from_yaml_text(
        cls, content: str, file_path: Optional[Path] = None
    ) -> MetadataEntry:
        """
        Parse metadata from YAML text.

        Args:
            content: YAML file content
            file_path: Optional source file path

        Returns:
            Parsed MetadataEntry instance

        Raises:
            MetadataValidationError: If YAML is invalid or missing date
        """
        try:
            data: Any = yaml.safe_load(content)
        except yaml.YAMLError as e:
            raise MetadataValidationError(f"Invalid YAML: {e}") from e

        if not isinstance(data, dict):
            raise MetadataValidationError("YAML content must be a dictionary")

        return cls.from_dict(data, file_path)

    @classmethod
    def from_dict(
        cls, data: Dict[str, Any], file_path: Optional[Path] = None
    ) -> MetadataEntry:
        """
        Create MetadataEntry from parsed dictionary.

        Args:
            data: Parsed YAML dictionary
            file_path: Optional source file path

        Returns:
            MetadataEntry instance

        Raises:
            MetadataValidationError: If missing required fields
        """
        # Extract required date field
        if "date" not in data:
            raise MetadataValidationError("Missing required 'date' field")

        entry_date = DataValidator.normalize_date(data["date"])
        if entry_date is None:
            raise MetadataValidationError(f"Invalid date format: {data['date']}")

        # Extract optional fields with defaults
        return cls(
            date=entry_date,
            summary=data.get("summary", "") or "",
            rating=cls._parse_rating(data.get("rating")),
            rating_justification=data.get("rating_justification", "") or "",
            arcs=cls._parse_string_list(data.get("arcs")),
            tags=cls._parse_string_list(data.get("tags")),
            themes=cls._parse_string_list(data.get("themes")),
            motifs=cls._parse_motifs(data.get("motifs")),
            scenes=cls._parse_scenes(data.get("scenes")),
            events=cls._parse_events(data.get("events")),
            threads=cls._parse_threads(data.get("threads")),
            poems=cls._parse_poems(data.get("poems")),
            references=cls._parse_references(data.get("references")),
            file_path=file_path,
            raw_data=data,
        )

    # =========================================================================
    # Parsing Helpers
    # =========================================================================

    @staticmethod
    def _parse_rating(value: Any) -> Optional[float]:
        """Parse rating value to float or None."""
        if value is None:
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _parse_string_list(value: Any) -> List[str]:
        """Parse a list of strings, handling None and single strings."""
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
        return []

    @staticmethod
    def _parse_motifs(value: Any) -> List[MotifSpec]:
        """Parse motifs list."""
        if not value or not isinstance(value, list):
            return []

        motifs = []
        for item in value:
            if isinstance(item, dict):
                motif: MotifSpec = {
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                }
                if motif["name"]:
                    motifs.append(motif)
        return motifs

    @staticmethod
    def _parse_scenes(value: Any) -> List[SceneSpec]:
        """Parse scenes list."""
        if not value or not isinstance(value, list):
            return []

        scenes = []
        for item in value:
            if isinstance(item, dict):
                scene: SceneSpec = {
                    "name": item.get("name", ""),
                    "description": item.get("description", ""),
                }

                # Date can be string or list
                if "date" in item:
                    scene["date"] = item["date"]

                # Optional people and locations
                if "people" in item and item["people"]:
                    scene["people"] = MetadataEntry._parse_string_list(item["people"])
                if "locations" in item and item["locations"]:
                    scene["locations"] = MetadataEntry._parse_string_list(
                        item["locations"]
                    )

                if scene["name"]:
                    scenes.append(scene)
        return scenes

    @staticmethod
    def _parse_events(value: Any) -> List[EventSpec]:
        """Parse events list."""
        if not value or not isinstance(value, list):
            return []

        events = []
        for item in value:
            if isinstance(item, dict):
                event: EventSpec = {
                    "name": item.get("name", ""),
                    "scenes": MetadataEntry._parse_string_list(item.get("scenes")),
                }
                if event["name"]:
                    events.append(event)
        return events

    @staticmethod
    def _parse_threads(value: Any) -> List[ThreadSpec]:
        """Parse threads list."""
        if not value or not isinstance(value, list):
            return []

        threads = []
        for item in value:
            if isinstance(item, dict):
                thread: ThreadSpec = {
                    "name": item.get("name", ""),
                    "from_": item.get("from", ""),
                    "to": item.get("to", ""),
                    "content": item.get("content", ""),
                }

                if "entry" in item:
                    thread["entry"] = item["entry"]
                if "people" in item and item["people"]:
                    thread["people"] = MetadataEntry._parse_string_list(item["people"])
                if "locations" in item and item["locations"]:
                    thread["locations"] = MetadataEntry._parse_string_list(
                        item["locations"]
                    )

                if thread["name"]:
                    threads.append(thread)
        return threads

    @staticmethod
    def _parse_poems(value: Any) -> List[PoemSpec]:
        """Parse poems list."""
        if not value or not isinstance(value, list):
            return []

        poems = []
        for item in value:
            if isinstance(item, dict):
                poem: PoemSpec = {
                    "title": item.get("title", ""),
                    "content": item.get("content", ""),
                }
                if poem["title"] or poem["content"]:
                    poems.append(poem)
        return poems

    @staticmethod
    def _parse_references(value: Any) -> List[ReferenceSpec]:
        """Parse references list."""
        if not value or not isinstance(value, list):
            return []

        references = []
        for item in value:
            if isinstance(item, dict):
                ref: ReferenceSpec = {}

                if "content" in item:
                    ref["content"] = item["content"]
                if "description" in item:
                    ref["description"] = item["description"]
                if "mode" in item:
                    ref["mode"] = item["mode"]

                if "source" in item and isinstance(item["source"], dict):
                    source: ReferenceSourceSpec = {}
                    src = item["source"]
                    if "title" in src:
                        source["title"] = src["title"]
                    if "author" in src:
                        source["author"] = src["author"]
                    if "type" in src:
                        source["type"] = src["type"]
                    if "url" in src:
                        source["url"] = src["url"]
                    ref["source"] = source

                if ref:
                    references.append(ref)
        return references

    # =========================================================================
    # Name Matching Helpers
    # =========================================================================

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Normalize name for comparison: lowercase, remove accents, normalize separators.

        Args:
            name: Name to normalize

        Returns:
            Normalized name string
        """
        text = name.lower().strip()
        text = text.replace("-", " ").replace(".", " ")
        text = " ".join(text.split())  # Collapse multiple spaces
        normalized = unicodedata.normalize("NFD", text)
        return "".join(c for c in normalized if unicodedata.category(c)[0] != "M")

    def _build_yaml_people_set(self) -> tuple[Set[str], Set[str]]:
        """
        Build sets of valid people names from YAML people section.

        Returns:
            Tuple of (original_names, normalized_names) sets
        """
        yaml_people = self.raw_data.get("people", [])
        original_names: Set[str] = set()
        normalized_names: Set[str] = set()

        def add_name(name: str) -> None:
            original_names.add(name)
            norm = self._normalize_name(name)
            normalized_names.add(norm)
            # Also add version without spaces (for "DrFranck" vs "Dr Franck")
            normalized_names.add(norm.replace(" ", ""))
            # Multi-word names: add each word
            parts = name.split()
            if len(parts) > 1:
                for part in parts:
                    original_names.add(part)
                    normalized_names.add(self._normalize_name(part))

        for person_data in yaml_people:
            if isinstance(person_data, str):
                add_name(person_data)
            elif isinstance(person_data, dict):
                name = person_data.get("name", "")
                lastname = person_data.get("lastname", "")
                alias = person_data.get("alias")

                if name:
                    add_name(name)
                    if lastname:
                        add_name(f"{name} {lastname}")

                if alias:
                    if isinstance(alias, list):
                        for a in alias:
                            add_name(a)
                    else:
                        add_name(alias)

        return original_names, normalized_names

    def _person_matches(
        self, person: str, original_names: Set[str], normalized_names: Set[str]
    ) -> bool:
        """
        Check if a person name matches the valid people set.

        Args:
            person: Person name to check
            original_names: Set of original (non-normalized) valid names
            normalized_names: Set of normalized valid names

        Returns:
            True if person matches, False otherwise
        """
        if person in original_names:
            return True
        norm = self._normalize_name(person)
        if norm in normalized_names:
            return True
        if norm.replace(" ", "") in normalized_names:
            return True
        return False

    # =========================================================================
    # Validation Methods
    # =========================================================================

    def validate_structure(self) -> MetadataValidationResult:
        """
        Validate structural integrity of metadata.

        Checks for:
        - Required fields present
        - Correct field types
        - Scene names match event scene references

        Returns:
            MetadataValidationResult with any errors found
        """
        result = MetadataValidationResult(
            file_path=str(self.file_path) if self.file_path else ""
        )

        # Required fields
        if not self.date:
            result.add_error("Missing required 'date' field")

        # Scene names must be unique
        scene_names = [s.get("name", "") for s in self.scenes if s.get("name")]
        if len(scene_names) != len(set(scene_names)):
            result.add_error("Duplicate scene names found")

        # Event scene references must exist
        for event in self.events:
            event_name = event.get("name", "unknown")
            for scene_name in event.get("scenes", []):
                if scene_name not in scene_names:
                    result.add_error(
                        f"Event '{event_name}' references unknown scene: {scene_name}"
                    )

        # Motifs must have name and description
        for motif in self.motifs:
            if not motif.get("name"):
                result.add_error("Motif missing 'name' field")
            if not motif.get("description"):
                result.add_warning(f"Motif '{motif.get('name')}' missing description")

        # Scenes must have name and description
        for scene in self.scenes:
            if not scene.get("name"):
                result.add_error("Scene missing 'name' field")
            if not scene.get("description"):
                result.add_warning(f"Scene '{scene.get('name')}' missing description")

        return result

    def validate_entities(
        self, resolver: Any  # EntityResolver, avoid circular import
    ) -> MetadataValidationResult:
        """
        Validate entity references against curation.

        Checks all people and location references in scenes and threads
        against the EntityResolver's curation maps. Unknown entities are
        reported as warnings with suggestions.

        Args:
            resolver: EntityResolver instance with loaded curation

        Returns:
            MetadataValidationResult with warnings for unknown entities
        """
        # Start with structural validation
        result = self.validate_structure()

        # Collect all person references
        people_refs: set = set()
        for scene in self.scenes:
            for person in scene.get("people", []):
                people_refs.add(person)
        for thread in self.threads:
            for person in thread.get("people", []):
                people_refs.add(person)

        # Validate people
        for person_name in people_refs:
            lookup = resolver.validate_person(person_name)
            if not lookup.found:
                msg = f"Unknown person: '{person_name}'"
                if lookup.suggestions:
                    msg += f" (suggestions: {', '.join(lookup.suggestions[:3])})"
                result.add_warning(msg)

        # Collect all location references
        location_refs: set = set()
        for scene in self.scenes:
            for location in scene.get("locations", []):
                location_refs.add(location)
        for thread in self.threads:
            for location in thread.get("locations", []):
                location_refs.add(location)

        # Validate locations
        for location_name in location_refs:
            lookup = resolver.validate_location(location_name)
            if not lookup.found:
                msg = f"Unknown location: '{location_name}'"
                if lookup.suggestions:
                    msg += f" (suggestions: {', '.join(lookup.suggestions[:3])})"
                result.add_warning(msg)

        return result

    def validate_people_consistency(
        self, md_frontmatter: Dict[str, Any]
    ) -> MetadataValidationResult:
        """
        Validate people consistency between MD frontmatter and metadata YAML.

        Ensures bidirectional equality with normalization:
        - Every person in metadata YAML has a match in MD frontmatter
        - Every person in MD frontmatter has a match in metadata YAML
        - Every person has lastname OR disambiguator (data quality check)

        Matching uses accent normalization, hyphen/space handling, and multi-word
        name expansion. MD frontmatter can use: name, full name, alias, or name parts.

        Args:
            md_frontmatter: Parsed MD frontmatter dict

        Returns:
            MetadataValidationResult with any errors found
        """
        result = MetadataValidationResult(
            file_path=str(self.file_path) if self.file_path else ""
        )

        md_people = md_frontmatter.get("people", []) or []
        yaml_people = self.raw_data.get("people", []) or []

        if not yaml_people and not md_people:
            return result  # Both empty, valid

        # Check data quality: each person must have lastname OR disambiguator
        for person_data in yaml_people:
            if isinstance(person_data, dict):
                name = person_data.get("name")
                lastname = person_data.get("lastname")
                disambiguator = person_data.get("disambiguator")

                if not lastname and not disambiguator:
                    entry_date = self.date.isoformat() if self.date else "unknown"
                    result.add_error(
                        f"Person '{name}' missing both lastname and disambiguator "
                        f"(entry: {entry_date})"
                    )

        # Build sets from YAML people (with normalization)
        yaml_original, yaml_normalized = self._build_yaml_people_set()

        # Build sets from MD frontmatter (with normalization)
        md_original: Set[str] = set()
        md_normalized: Set[str] = set()
        for person in md_people:
            md_original.add(person)
            norm = self._normalize_name(person)
            md_normalized.add(norm)
            md_normalized.add(norm.replace(" ", ""))
            # Multi-word: add parts
            parts = person.split()
            if len(parts) > 1:
                for part in parts:
                    md_original.add(part)
                    md_normalized.add(self._normalize_name(part))

        # Check 1: Every MD person must match a YAML person
        for person in md_people:
            if not self._person_matches(person, yaml_original, yaml_normalized):
                result.add_error(
                    f"MD frontmatter has person '{person}' not in metadata YAML"
                )

        # Check 2: Every YAML person must match an MD person
        # Match if any of: name, lastname, name parts, full name, or alias matches
        for person_data in yaml_people:
            if isinstance(person_data, str):
                # Check full string and its parts
                matched = self._person_matches(person_data, md_original, md_normalized)
                if not matched:
                    for part in person_data.split():
                        if self._person_matches(part, md_original, md_normalized):
                            matched = True
                            break
                if not matched:
                    result.add_error(
                        f"Metadata YAML has person '{person_data}' not in MD frontmatter"
                    )
            elif isinstance(person_data, dict):
                name = person_data.get("name", "")
                lastname = person_data.get("lastname", "")
                alias = person_data.get("alias")

                # Check if any form matches
                matched = False

                # Check full name
                if name and self._person_matches(name, md_original, md_normalized):
                    matched = True

                # Check individual name parts (for multi-word first names)
                if not matched and name:
                    for part in name.split():
                        if self._person_matches(part, md_original, md_normalized):
                            matched = True
                            break

                # Check lastname alone
                if not matched and lastname:
                    if self._person_matches(lastname, md_original, md_normalized):
                        matched = True

                # Check full name with lastname
                if not matched and lastname:
                    full = f"{name} {lastname}"
                    if self._person_matches(full, md_original, md_normalized):
                        matched = True

                # Check aliases
                if not matched and alias:
                    aliases = [alias] if isinstance(alias, str) else alias
                    for a in aliases:
                        if self._person_matches(a, md_original, md_normalized):
                            matched = True
                            break

                if not matched:
                    if alias:
                        identifier = f"{name} (alias: {alias})"
                    elif lastname:
                        identifier = f"{name} {lastname}"
                    else:
                        identifier = name
                    result.add_error(
                        f"Metadata YAML has person '{identifier}' not in MD frontmatter"
                    )

        return result

    def validate_scene_subsets(
        self, md_frontmatter: Dict[str, Any]
    ) -> MetadataValidationResult:
        """
        Validate that scene people/locations/dates are subsets of entry-level.

        - Scene people must be subset of YAML people section (with normalization)
        - Scene locations must be subset of MD frontmatter locations
        - Scene dates must be subset of MD frontmatter narrated_dates

        Args:
            md_frontmatter: Parsed MD frontmatter dict

        Returns:
            MetadataValidationResult with any errors found
        """
        result = MetadataValidationResult(
            file_path=str(self.file_path) if self.file_path else ""
        )

        # Build valid people set from YAML people section (with normalization)
        yaml_people_original, yaml_people_normalized = self._build_yaml_people_set()

        # Build entry-level locations from MD frontmatter
        entry_locations: Set[str] = set()
        locations_data = md_frontmatter.get("locations", {})
        if isinstance(locations_data, dict):
            for loc_list in locations_data.values():
                if isinstance(loc_list, list):
                    entry_locations.update(loc_list)

        # Build entry-level dates from MD frontmatter
        entry_dates: Set[date] = set()
        narrated_dates = md_frontmatter.get("narrated_dates", [])
        for date_val in narrated_dates:
            if isinstance(date_val, date):
                entry_dates.add(date_val)
            elif isinstance(date_val, str):
                try:
                    entry_dates.add(date.fromisoformat(date_val))
                except ValueError:
                    pass

        # Validate each scene
        for scene_data in self.scenes:
            scene_name = scene_data.get("name", "Unnamed Scene")

            # Validate scene people against YAML people section
            for person_name in scene_data.get("people", []):
                if not self._person_matches(
                    person_name, yaml_people_original, yaml_people_normalized
                ):
                    result.add_error(
                        f"Scene '{scene_name}' references person '{person_name}' "
                        f"not in YAML people section"
                    )

            # Validate scene locations against MD frontmatter
            for loc_name in scene_data.get("locations", []):
                if loc_name not in entry_locations:
                    result.add_error(
                        f"Scene '{scene_name}' references location '{loc_name}' "
                        f"not in entry locations list"
                    )

            # Validate scene dates against MD frontmatter narrated_dates
            scene_dates = scene_data.get("date")
            if scene_dates:
                if not isinstance(scene_dates, list):
                    scene_dates = [scene_dates]

                for scene_date in scene_dates:
                    # Convert to date object if string
                    if isinstance(scene_date, str):
                        try:
                            scene_date = date.fromisoformat(scene_date)
                        except ValueError:
                            # Skip validation for approximate dates (~2021, etc.)
                            continue

                    if isinstance(scene_date, date) and scene_date not in entry_dates:
                        result.add_error(
                            f"Scene '{scene_name}' references date {scene_date} "
                            f"not in entry narrated_dates"
                        )

        return result

    def get_all_people(self) -> List[str]:
        """
        Get all unique person references from scenes and threads.

        Returns:
            List of unique person names
        """
        people: set = set()
        for scene in self.scenes:
            for person in scene.get("people", []):
                people.add(person)
        for thread in self.threads:
            for person in thread.get("people", []):
                people.add(person)
        return sorted(people)

    def get_all_locations(self) -> List[str]:
        """
        Get all unique location references from scenes and threads.

        Returns:
            List of unique location names
        """
        locations: set = set()
        for scene in self.scenes:
            for location in scene.get("locations", []):
                locations.add(location)
        for thread in self.threads:
            for location in thread.get("locations", []):
                locations.add(location)
        return sorted(locations)

    # =========================================================================
    # Conversion Methods
    # =========================================================================

    def to_database_metadata(self) -> Dict[str, Any]:
        """
        Convert MetadataEntry to format expected by database import.

        Transforms the parsed metadata into the structure needed for
        database entity creation.

        Returns:
            Dictionary with normalized database-ready metadata
        """
        db_meta: Dict[str, Any] = {
            "date": self.date,
            "summary": self.summary,
            "rating": self.rating,
            "rating_justification": self.rating_justification,
        }

        # Simple lists
        if self.arcs:
            db_meta["arcs"] = self.arcs
        if self.tags:
            db_meta["tags"] = self.tags
        if self.themes:
            db_meta["themes"] = self.themes

        # Complex structures
        if self.motifs:
            db_meta["motifs"] = self.motifs
        if self.scenes:
            db_meta["scenes"] = self.scenes
        if self.events:
            db_meta["events"] = self.events
        if self.threads:
            # Convert from_ back to from for database
            db_meta["threads"] = [
                {
                    "name": t.get("name", ""),
                    "from": t.get("from_", ""),
                    "to": t.get("to", ""),
                    "entry": t.get("entry"),
                    "content": t.get("content", ""),
                    "people": t.get("people", []),
                    "locations": t.get("locations", []),
                }
                for t in self.threads
            ]
        if self.poems:
            db_meta["poems"] = self.poems
        if self.references:
            db_meta["references"] = self.references

        return db_meta

    def __repr__(self) -> str:
        """String representation."""
        return f"<MetadataEntry(date={self.date}, file={self.file_path})>"

    def __str__(self) -> str:
        """Human-readable string."""
        parts = [f"MetadataEntry {self.date.isoformat()}"]
        if self.scenes:
            parts.append(f"{len(self.scenes)} scenes")
        if self.events:
            parts.append(f"{len(self.events)} events")
        return f"({', '.join(parts)})"
