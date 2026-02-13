#!/usr/bin/env python3
"""
parser.py
---------
Wiki page parser for bidirectional manuscript sync.

Parses manuscript wiki markdown pages back into structured dataclasses
that can be compared against or written to the database. Uses regex-based
section splitting and extraction patterns matched to the template output.

Key Features:
    - Parses Chapter, Character, and ManuscriptScene wiki pages
    - Extracts wikilinks, metadata lines, lists, and prose sections
    - Resolves wikilinks against database entities (cached)
    - Returns structured dataclasses ready for DB ingestion

Supported Page Types:
    - Chapter: title, type, status, part, characters, arcs, scenes,
      references, poems
    - Character: name, role, is_narrator, description, based_on mappings
    - ManuscriptScene: name, chapter, origin, status, description, sources

Usage:
    from dev.wiki.parser import WikiParser

    parser = WikiParser(db)
    chapter_data = parser.parse_chapter(Path("wiki/manuscript/chapters/foo.md"))
    character_data = parser.parse_character(Path("wiki/manuscript/characters/bar.md"))

Dependencies:
    - PalimpsestDB for wikilink resolution
    - re for markdown pattern matching
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# --- Local imports ---
from dev.database.manager import PalimpsestDB
from dev.database.models import (
    Arc,
    Entry,
    Person,
    Poem,
    ReferenceSource,
)
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    SceneOrigin,
    SceneStatus,
)
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptScene,
    Part,
)


# ==================== Constants ====================

WIKILINK_RE = re.compile(r'\[\[([^\]|]+)(?:\|([^\]]+))?\]\]')
H1_RE = re.compile(r'^# (.+)$', re.MULTILINE)
H2_RE = re.compile(r'^## (.+)$', re.MULTILINE)
H3_RE = re.compile(r'^### (.+)$', re.MULTILINE)
HR_RE = re.compile(r'^---\s*$', re.MULTILINE)

# Metadata line patterns
TYPE_STATUS_RE = re.compile(
    r'\*\*Type:\*\*\s*(\w+)\s*·\s*\*\*Status:\*\*\s*(\w+)'
)
PART_RE = re.compile(r'\*\*Part:\*\*\s*\[\[([^\]]+)\]\]')
CHAPTER_RE = re.compile(r'\*\*Chapter:\*\*\s*\[\[([^\]]+)\]\]')
ROLE_RE = re.compile(
    r'\*\*Role:\*\*\s*(.+?)(?:\s*·\s*\*\*Narrator\*\*)?$', re.MULTILINE
)
NARRATOR_RE = re.compile(r'\*\*Narrator\*\*')
ORIGIN_STATUS_RE = re.compile(r'^\*(\w+)\*\s*·\s*(\w+)\s*$', re.MULTILINE)

# List item patterns
CHAR_LIST_RE = re.compile(
    r'^-\s*\[\[([^\]]+)\]\](?:\s*·\s*(.+))?$', re.MULTILINE
)
SIMPLE_WIKILINK_LIST_RE = re.compile(
    r'^-\s*\[\[([^\]]+)\]\]', re.MULTILINE
)
REFERENCE_RE = re.compile(
    r'^-\s*\[\[([^\]]+)\]\]\s*\*\((\w+)\)\*'
    r'(?:\s*—\s*(.+))?$',
    re.MULTILINE,
)
BASED_ON_RE = re.compile(
    r'^-\s*\[\[([^\]]+)\]\]\s*\*\((\w+)\)\*$', re.MULTILINE
)

# Source patterns in manuscript scene
SOURCE_LINE_RE = re.compile(
    r'^-\s*\*\*(\w+):\*\*\s*(.+?)(?:\s*·\s*\[\[([^\]]+)\]\])?$',
    re.MULTILINE,
)

# Scene source patterns (within chapter scenes section)
SCENE_SOURCE_RE = re.compile(
    r'^-\s*(\w+):\s*(.+)$', re.MULTILINE
)


# ==================== Parsed Data Structures ====================

@dataclass
class ParsedSceneSource:
    """
    A parsed source reference from a manuscript scene.

    Attributes:
        source_type: Type of source (Scene, Entry, Thread, External)
        reference: Raw reference text
        entry_date: Optional entry date from wikilink
    """

    source_type: str
    reference: str
    entry_date: Optional[str] = None


@dataclass
class ParsedChapterScene:
    """
    A parsed scene entry within a chapter page.

    Attributes:
        name: Scene name from H3 heading
        description: Scene description text
        origin: Scene origin (journaled, inferred, etc.)
        status: Scene status (fragment, draft, etc.)
        sources: List of source references
    """

    name: str
    description: Optional[str] = None
    origin: Optional[str] = None
    status: Optional[str] = None
    sources: List[ParsedSceneSource] = field(default_factory=list)


@dataclass
class ParsedReference:
    """
    A parsed manuscript reference.

    Attributes:
        source_title: Reference source title from wikilink
        mode: Reference mode (direct, thematic, etc.)
        content: Optional quote or content
    """

    source_title: str
    mode: str
    content: Optional[str] = None


@dataclass
class ParsedPersonMapping:
    """
    A parsed person-to-character mapping.

    Attributes:
        person_name: Person display name from wikilink
        contribution: Contribution type (primary, composite, inspiration)
    """

    person_name: str
    contribution: str


@dataclass
class ChapterData:
    """
    Parsed data from a chapter wiki page.

    Contains all editable fields extracted from the markdown.
    Generated sections (below final ``---``) are ignored.

    Attributes:
        title: Chapter title from H1
        chapter_type: Chapter type string (prose, vignette, poem)
        status: Chapter status string (draft, revised, final)
        part_name: Part display name from wikilink (or None)
        characters: List of (name, role) tuples
        arcs: List of arc names
        scenes: List of parsed scene data
        references: List of parsed references
        poems: List of poem titles
    """

    title: str
    chapter_type: str
    status: str
    part_name: Optional[str] = None
    characters: List[Tuple[str, Optional[str]]] = field(default_factory=list)
    arcs: List[str] = field(default_factory=list)
    scenes: List[ParsedChapterScene] = field(default_factory=list)
    references: List[ParsedReference] = field(default_factory=list)
    poems: List[str] = field(default_factory=list)


@dataclass
class CharacterData:
    """
    Parsed data from a character wiki page.

    Contains all editable fields. The Chapters list (generated)
    is ignored by the parser.

    Attributes:
        name: Character name from H1
        role: Character role (or None)
        is_narrator: Whether marked as narrator
        description: Character description prose
        based_on: List of person mappings
    """

    name: str
    role: Optional[str] = None
    is_narrator: bool = False
    description: Optional[str] = None
    based_on: List[ParsedPersonMapping] = field(default_factory=list)


@dataclass
class ManuscriptSceneData:
    """
    Parsed data from a manuscript scene wiki page.

    Contains all editable fields above the final ``---``.

    Attributes:
        name: Scene name from H1
        chapter_name: Chapter title from wikilink (or None)
        origin: Scene origin string
        status: Scene status string
        description: Description prose
        sources: List of parsed source references
    """

    name: str
    chapter_name: Optional[str] = None
    origin: str = "journaled"
    status: str = "fragment"
    description: Optional[str] = None
    sources: List[ParsedSceneSource] = field(default_factory=list)


# ==================== Section Splitter ====================

def _split_sections(content: str) -> Dict[str, str]:
    """
    Split markdown content into sections keyed by H2 heading.

    Content before any H2 heading is stored under the key ``"_preamble"``.
    Content after the last ``---`` separator is ignored (generated content).

    Args:
        content: Full markdown content

    Returns:
        Dict mapping section name (lowercase) to section body text
    """
    # Trim generated content after last HR that follows an H2 section
    sections: Dict[str, str] = {}
    current_key = "_preamble"
    current_lines: List[str] = []

    for line in content.split("\n"):
        h2_match = H2_RE.match(line)
        if h2_match:
            # Save previous section
            sections[current_key] = "\n".join(current_lines).strip()
            current_key = h2_match.group(1).strip().lower()
            current_lines = []
        else:
            current_lines.append(line)

    # Save last section
    sections[current_key] = "\n".join(current_lines).strip()

    return sections


def _extract_preamble_before_hr(content: str) -> str:
    """
    Extract content before the first ``---`` separator.

    Args:
        content: Full markdown content

    Returns:
        Content before first HR, or full content if no HR found
    """
    match = HR_RE.search(content)
    if match:
        return content[:match.start()].strip()
    return content.strip()


# ==================== WikiParser ====================

class WikiParser:
    """
    Parses manuscript wiki pages into structured dataclasses.

    Extracts editable data from Chapter, Character, and ManuscriptScene
    wiki pages. Provides wikilink resolution against the database for
    entity matching during sync.

    Attributes:
        db: PalimpsestDB instance for entity resolution
        _entity_cache: Cached entity lookups by type
    """

    def __init__(self, db: PalimpsestDB) -> None:
        """
        Initialize the wiki parser.

        Args:
            db: PalimpsestDB instance for wikilink resolution
        """
        self.db = db
        self._entity_cache: Dict[str, Dict[str, int]] = {}

    def parse_chapter(self, file_path: Path) -> ChapterData:
        """
        Parse a chapter wiki page into structured data.

        Extracts title, metadata (type/status/part), characters, arcs,
        scenes with sources, references, and poems.

        Args:
            file_path: Path to the chapter markdown file

        Returns:
            ChapterData with all extracted fields

        Raises:
            ValueError: If required fields (title, type, status) are missing
        """
        content = file_path.read_text(encoding="utf-8")
        preamble = _extract_preamble_before_hr(content)
        sections = _split_sections(content)

        # Title from H1
        title_match = H1_RE.search(preamble)
        if not title_match:
            raise ValueError(f"No H1 title found in {file_path}")
        title = title_match.group(1).strip()

        # Type and Status from metadata line
        ts_match = TYPE_STATUS_RE.search(preamble)
        if not ts_match:
            raise ValueError(
                f"No Type/Status metadata found in {file_path}"
            )
        chapter_type = ts_match.group(1).strip().lower()
        status = ts_match.group(2).strip().lower()

        # Validate enum values
        _validate_enum(chapter_type, ChapterType, "chapter type", file_path)
        _validate_enum(status, ChapterStatus, "chapter status", file_path)

        # Part from wikilink
        part_match = PART_RE.search(preamble)
        part_name = part_match.group(1).strip() if part_match else None

        # Characters section
        characters: List[Tuple[str, Optional[str]]] = []
        if "characters" in sections:
            for match in CHAR_LIST_RE.finditer(sections["characters"]):
                name = match.group(1).strip()
                role = match.group(2).strip() if match.group(2) else None
                characters.append((name, role))

        # Arcs section
        arcs: List[str] = []
        if "arcs" in sections:
            for match in SIMPLE_WIKILINK_LIST_RE.finditer(sections["arcs"]):
                arcs.append(match.group(1).strip())

        # Scenes section
        scenes = self._parse_chapter_scenes(sections.get("scenes", ""))

        # References section
        references: List[ParsedReference] = []
        if "references" in sections:
            for match in REFERENCE_RE.finditer(sections["references"]):
                references.append(ParsedReference(
                    source_title=match.group(1).strip(),
                    mode=match.group(2).strip().lower(),
                    content=match.group(3).strip() if match.group(3) else None,
                ))

        # Poems section
        poems: List[str] = []
        if "poems" in sections:
            for match in SIMPLE_WIKILINK_LIST_RE.finditer(sections["poems"]):
                poems.append(match.group(1).strip())

        return ChapterData(
            title=title,
            chapter_type=chapter_type,
            status=status,
            part_name=part_name,
            characters=characters,
            arcs=arcs,
            scenes=scenes,
            references=references,
            poems=poems,
        )

    def parse_character(self, file_path: Path) -> CharacterData:
        """
        Parse a character wiki page into structured data.

        Extracts name, role, narrator flag, description, and
        person-character mappings. The Chapters list (generated)
        is ignored.

        Args:
            file_path: Path to the character markdown file

        Returns:
            CharacterData with all extracted fields

        Raises:
            ValueError: If required field (title) is missing
        """
        content = file_path.read_text(encoding="utf-8")
        preamble = _extract_preamble_before_hr(content)
        sections = _split_sections(content)

        # Title from H1
        title_match = H1_RE.search(preamble)
        if not title_match:
            raise ValueError(f"No H1 title found in {file_path}")
        name = title_match.group(1).strip()

        # Role and narrator from metadata line
        role: Optional[str] = None
        is_narrator = False

        role_match = ROLE_RE.search(preamble)
        if role_match:
            role = role_match.group(1).strip()
        if NARRATOR_RE.search(preamble):
            is_narrator = True

        # Description: prose between role line and count line in preamble
        description = self._extract_character_description(preamble)

        # Based On section
        based_on: List[ParsedPersonMapping] = []
        if "based on" in sections:
            for match in BASED_ON_RE.finditer(sections["based on"]):
                based_on.append(ParsedPersonMapping(
                    person_name=match.group(1).strip(),
                    contribution=match.group(2).strip().lower(),
                ))

        return CharacterData(
            name=name,
            role=role,
            is_narrator=is_narrator,
            description=description,
            based_on=based_on,
        )

    def parse_manuscript_scene(
        self, file_path: Path
    ) -> ManuscriptSceneData:
        """
        Parse a manuscript scene wiki page into structured data.

        Extracts name, chapter assignment, origin/status, description,
        and source references. Content below the final ``---`` (Context
        section) is ignored.

        Args:
            file_path: Path to the manuscript scene markdown file

        Returns:
            ManuscriptSceneData with all extracted fields

        Raises:
            ValueError: If required field (title) is missing
        """
        content = file_path.read_text(encoding="utf-8")
        preamble = _extract_preamble_before_hr(content)
        sections = _split_sections(content)

        # Title from H1
        title_match = H1_RE.search(preamble)
        if not title_match:
            raise ValueError(f"No H1 title found in {file_path}")
        name = title_match.group(1).strip()

        # Chapter from wikilink
        chapter_match = CHAPTER_RE.search(preamble)
        chapter_name = (
            chapter_match.group(1).strip() if chapter_match else None
        )

        # Origin and status from italic pattern
        origin = "journaled"
        status = "fragment"
        os_match = ORIGIN_STATUS_RE.search(preamble)
        if os_match:
            origin = os_match.group(1).strip().lower()
            status = os_match.group(2).strip().lower()

        _validate_enum(origin, SceneOrigin, "scene origin", file_path)
        _validate_enum(status, SceneStatus, "scene status", file_path)

        # Description: prose after origin/status line in preamble
        description = self._extract_scene_description(preamble)

        # Sources section
        sources: List[ParsedSceneSource] = []
        if "sources" in sections:
            sources = self._parse_sources_section(sections["sources"])

        return ManuscriptSceneData(
            name=name,
            chapter_name=chapter_name,
            origin=origin,
            status=status,
            description=description,
            sources=sources,
        )

    # ==================== Entity Resolution ====================

    def resolve_chapter(
        self, session: Any, title: str
    ) -> Optional[int]:
        """
        Resolve a chapter title to its database ID.

        Args:
            session: SQLAlchemy session
            title: Chapter title to look up

        Returns:
            Chapter ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "chapters")
        return cache.get(title.lower())

    def resolve_character(
        self, session: Any, name: str
    ) -> Optional[int]:
        """
        Resolve a character name to its database ID.

        Args:
            session: SQLAlchemy session
            name: Character name to look up

        Returns:
            Character ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "characters")
        return cache.get(name.lower())

    def resolve_part(
        self, session: Any, display_name: str
    ) -> Optional[int]:
        """
        Resolve a part display name to its database ID.

        Args:
            session: SQLAlchemy session
            display_name: Part display name to look up

        Returns:
            Part ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "parts")
        return cache.get(display_name.lower())

    def resolve_person(
        self, session: Any, display_name: str
    ) -> Optional[int]:
        """
        Resolve a person display name to its database ID.

        Args:
            session: SQLAlchemy session
            display_name: Person display name to look up

        Returns:
            Person ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "people")
        return cache.get(display_name.lower())

    def resolve_arc(
        self, session: Any, name: str
    ) -> Optional[int]:
        """
        Resolve an arc name to its database ID.

        Args:
            session: SQLAlchemy session
            name: Arc name to look up

        Returns:
            Arc ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "arcs")
        return cache.get(name.lower())

    def resolve_poem(
        self, session: Any, title: str
    ) -> Optional[int]:
        """
        Resolve a poem title to its database ID.

        Args:
            session: SQLAlchemy session
            title: Poem title to look up

        Returns:
            Poem ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "poems")
        return cache.get(title.lower())

    def resolve_reference_source(
        self, session: Any, title: str
    ) -> Optional[int]:
        """
        Resolve a reference source title to its database ID.

        Args:
            session: SQLAlchemy session
            title: Reference source title to look up

        Returns:
            ReferenceSource ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "reference_sources")
        return cache.get(title.lower())

    def resolve_manuscript_scene(
        self, session: Any, name: str
    ) -> Optional[int]:
        """
        Resolve a manuscript scene name to its database ID.

        Args:
            session: SQLAlchemy session
            name: Manuscript scene name to look up

        Returns:
            ManuscriptScene ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "manuscript_scenes")
        return cache.get(name.lower())

    def resolve_entry_by_date(
        self, session: Any, date_str: str
    ) -> Optional[int]:
        """
        Resolve an entry date string to its database ID.

        Args:
            session: SQLAlchemy session
            date_str: Date string in YYYY-MM-DD format

        Returns:
            Entry ID if found, None otherwise
        """
        cache = self._get_or_build_cache(session, "entries")
        return cache.get(date_str.lower())

    def clear_cache(self) -> None:
        """
        Clear all cached entity lookups.

        Call this when the database may have changed between
        parse operations.
        """
        self._entity_cache.clear()

    # ==================== Private Helpers ====================

    def _get_or_build_cache(
        self, session: Any, entity_type: str
    ) -> Dict[str, int]:
        """
        Get or build entity cache for a specific type.

        Lazily loads all entities of the given type into a dict
        mapping lowercased name/title → ID.

        Args:
            session: SQLAlchemy session
            entity_type: Type key (chapters, characters, etc.)

        Returns:
            Dict mapping lowercase name to entity ID
        """
        if entity_type in self._entity_cache:
            return self._entity_cache[entity_type]

        cache: Dict[str, int] = {}

        if entity_type == "chapters":
            for ch in session.query(Chapter).all():
                cache[ch.title.lower()] = ch.id
        elif entity_type == "characters":
            for char in session.query(Character).all():
                cache[char.name.lower()] = char.id
        elif entity_type == "parts":
            for part in session.query(Part).all():
                cache[part.display_name.lower()] = part.id
        elif entity_type == "people":
            for person in session.query(Person).all():
                cache[person.display_name.lower()] = person.id
        elif entity_type == "arcs":
            for arc in session.query(Arc).all():
                cache[arc.name.lower()] = arc.id
        elif entity_type == "poems":
            for poem in session.query(Poem).all():
                cache[poem.title.lower()] = poem.id
        elif entity_type == "reference_sources":
            for src in session.query(ReferenceSource).all():
                cache[src.title.lower()] = src.id
        elif entity_type == "manuscript_scenes":
            for ms in session.query(ManuscriptScene).all():
                cache[ms.name.lower()] = ms.id
        elif entity_type == "entries":
            for entry in session.query(Entry).all():
                cache[entry.date.isoformat()] = entry.id

        self._entity_cache[entity_type] = cache
        return cache

    def _parse_chapter_scenes(
        self, section_text: str
    ) -> List[ParsedChapterScene]:
        """
        Parse the Scenes section of a chapter page.

        Splits by H3 headings and extracts name, description,
        origin/status, and sources for each scene.

        Args:
            section_text: Text content of the ## Scenes section

        Returns:
            List of ParsedChapterScene instances in order
        """
        if not section_text.strip():
            return []

        scenes: List[ParsedChapterScene] = []
        scene_blocks = re.split(r'^### ', section_text, flags=re.MULTILINE)

        for block in scene_blocks:
            block = block.strip()
            if not block:
                continue

            lines = block.split("\n")
            name = lines[0].strip()

            description: Optional[str] = None
            origin: Optional[str] = None
            status: Optional[str] = None
            sources: List[ParsedSceneSource] = []

            # Parse remaining lines
            desc_lines: List[str] = []
            in_sources = False

            for line in lines[1:]:
                stripped = line.strip()

                # Check for origin/status pattern
                os_match = re.match(r'^\*(\w+)\*\s*·\s*(\w+)$', stripped)
                if os_match:
                    origin = os_match.group(1).lower()
                    status = os_match.group(2).lower()
                    in_sources = True
                    continue

                # Check for source lines (after origin/status)
                if in_sources:
                    src_match = re.match(
                        r'^-\s*(\w+):\s*(.+)$', stripped
                    )
                    if src_match:
                        sources.append(ParsedSceneSource(
                            source_type=src_match.group(1).strip(),
                            reference=src_match.group(2).strip(),
                        ))
                        continue

                # Everything else before origin/status is description
                if not in_sources and stripped:
                    desc_lines.append(stripped)

            if desc_lines:
                description = "\n".join(desc_lines)

            scenes.append(ParsedChapterScene(
                name=name,
                description=description,
                origin=origin,
                status=status,
                sources=sources,
            ))

        return scenes

    def _extract_character_description(self, preamble: str) -> Optional[str]:
        """
        Extract character description from preamble.

        Description is the prose between the role/narrator line
        and the chapter count line.

        Args:
            preamble: Content before the first ``---``

        Returns:
            Description text or None
        """
        lines = preamble.split("\n")
        desc_lines: List[str] = []
        in_description = False

        for line in lines:
            stripped = line.strip()

            # Skip title and role lines
            if stripped.startswith("# "):
                continue
            if stripped.startswith("**Role:**"):
                in_description = True
                continue

            # Stop at count line (N chapter(s))
            if re.match(r'^\d+ chapter', stripped):
                break

            if in_description and stripped:
                desc_lines.append(stripped)
            elif not stripped and in_description and desc_lines:
                desc_lines.append("")

        # Clean up trailing blank lines
        while desc_lines and not desc_lines[-1]:
            desc_lines.pop()

        if desc_lines:
            return "\n".join(desc_lines)
        return None

    def _extract_scene_description(self, preamble: str) -> Optional[str]:
        """
        Extract manuscript scene description from preamble.

        Description is the prose after the origin/status line.

        Args:
            preamble: Content before the first ``---``

        Returns:
            Description text or None
        """
        lines = preamble.split("\n")
        desc_lines: List[str] = []
        found_origin = False

        for line in lines:
            stripped = line.strip()

            # Skip until after origin/status line
            if re.match(r'^\*\w+\*\s*·\s*\w+$', stripped):
                found_origin = True
                continue

            if found_origin and stripped:
                desc_lines.append(stripped)
            elif found_origin and not stripped and desc_lines:
                desc_lines.append("")

        # Clean up trailing blank lines
        while desc_lines and not desc_lines[-1]:
            desc_lines.pop()

        if desc_lines:
            return "\n".join(desc_lines)
        return None

    def _parse_sources_section(
        self, section_text: str
    ) -> List[ParsedSceneSource]:
        """
        Parse the Sources section of a manuscript scene page.

        Extracts structured source lines matching the template format:
        ``- **Type:** reference · [[date]]``

        Args:
            section_text: Text content of the ## Sources section

        Returns:
            List of ParsedSceneSource instances
        """
        sources: List[ParsedSceneSource] = []

        for match in SOURCE_LINE_RE.finditer(section_text):
            source_type = match.group(1).strip()
            reference = match.group(2).strip()
            entry_date = match.group(3).strip() if match.group(3) else None

            # Clean wikilinks from reference text
            reference = WIKILINK_RE.sub(
                lambda m: m.group(1), reference
            )

            sources.append(ParsedSceneSource(
                source_type=source_type,
                reference=reference,
                entry_date=entry_date,
            ))

        return sources


# ==================== Validation Helpers ====================

def _validate_enum(
    value: str,
    enum_class: Any,
    field_name: str,
    file_path: Path,
) -> None:
    """
    Validate that a value is a valid enum member.

    Args:
        value: String value to validate
        enum_class: Enum class to check against
        field_name: Human-readable field name for error messages
        file_path: File path for error context

    Raises:
        ValueError: If value is not a valid enum member
    """
    valid_values = [e.value for e in enum_class]
    if value not in valid_values:
        raise ValueError(
            f"Invalid {field_name} '{value}' in {file_path}. "
            f"Valid values: {valid_values}"
        )
