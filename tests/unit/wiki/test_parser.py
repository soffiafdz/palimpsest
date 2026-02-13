#!/usr/bin/env python3
"""
test_parser.py
--------------
Tests for the WikiParser module.

Validates parsing of Chapter, Character, and ManuscriptScene wiki pages
back into structured dataclasses. Also covers entity resolution against
the database and the section splitter utility.

Test Classes:
    - TestSectionSplitter: _split_sections and _extract_preamble_before_hr
    - TestParseChapter: parse_chapter with full, minimal, and error cases
    - TestParseCharacter: parse_character with full, minimal, and error cases
    - TestParseManuscriptScene: parse_manuscript_scene with variations
    - TestEntityResolution: Wikilink resolution against DB entities

Dependencies:
    - pytest tmp_path fixture for temp markdown files
    - db_session fixture from conftest.py for entity resolution
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models import (
    Arc,
    Entry,
    Person,
    Poem,
    ReferenceSource,
    ReferenceType,
    RelationType,
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
from dev.wiki.parser import (
    ChapterData,
    CharacterData,
    ManuscriptSceneData,
    ParsedChapterScene,
    ParsedPersonMapping,
    ParsedReference,
    ParsedSceneSource,
    WikiParser,
    _extract_preamble_before_hr,
    _split_sections,
)


# ==================== Helpers ====================


def _write_md(tmp_path: Path, content: str, name: str = "test.md") -> Path:
    """
    Write markdown content to a temporary file and return its path.

    Args:
        tmp_path: pytest tmp_path fixture directory
        content: Markdown content to write
        name: Filename to use

    Returns:
        Path to the written file
    """
    file_path = tmp_path / name
    file_path.write_text(content, encoding="utf-8")
    return file_path


# ==================== Full Template Contents ====================

FULL_CHAPTER_MD = """\
# The Gray Fence

**Type:** Prose · **Status:** Draft
**Part:** [[Part 1: Arrival]]
3 scenes

---

## Characters
- [[Sofia]] · protagonist
- [[Clara]]

## Arcs
- [[The Long Wanting]]

---

## Scenes

### Morning at the Fence
Sofia watches Clara from the balcony.

*journaled* · included
- Scene: Scene: The Gray Fence
- Entry: Entry: 2024-11-15

---

### Night Walk
A restless walk through the Plateau.

*inferred* · draft

---

## References
- [[The Body Keeps the Score]] *(thematic)* — The body remembers
- [[Bluets]] *(direct)*

## Poems
- [[Untitled (November)]]
- [[After the Rain]]
"""

MINIMAL_CHAPTER_MD = """\
# Interlude

**Type:** Vignette · **Status:** Revised
"""

FULL_CHARACTER_MD = """\
# Clara

**Role:** love interest · **Narrator**

A French filmmaker who exists mostly in absence.

2 chapters

---

## Based On
- [[Clara Dupont]] *(primary)*
- [[Marie Leclerc]] *(inspiration)*

## Chapters
- [[The Gray Fence]] · Prose · Draft
"""

MINIMAL_CHARACTER_MD = """\
# Lena
"""

CHARACTER_NO_DESCRIPTION_MD = """\
# Thomas

**Role:** antagonist

3 chapters

---

## Based On
- [[Tom Rivera]] *(composite)*
"""

CHARACTER_NARRATOR_NO_ROLE_MD = """\
# Sofia

**Role:** protagonist · **Narrator**

The one who writes.

1 chapter
"""

FULL_SCENE_MD = """\
# Morning at the Fence

**Chapter:** [[The Gray Fence]]

*journaled* · included

Sofia watches Clara from the balcony.

---

## Sources
- **Scene:** Scene: The Gray Fence · [[2024-11-08]]
- **Entry:** Entry: 2024-11-15 · [[2024-11-15]]
- **External:** Interview notes, March 2024
"""

MINIMAL_SCENE_MD = """\
# A Fragment

*invented* · fragment
"""

UNASSIGNED_SCENE_MD = """\
# Loose Thread

*composite* · draft

A moment that doesn't belong anywhere yet.
"""

SCENE_MULTIPLE_SOURCES_MD = """\
# Layered Memory

**Chapter:** [[Interlude]]

*composite* · included

Multiple threads converge.

---

## Sources
- **Scene:** Scene: At the Market · [[2024-06-12]]
- **Entry:** Entry: 2024-06-15 · [[2024-06-15]]
- **Thread:** Thread: The Bookend Kiss
- **External:** Personal correspondence, April 2024
"""


# ==================== Section Splitter Tests ====================


class TestSectionSplitter:
    """Tests for _split_sections and _extract_preamble_before_hr."""

    def test_splits_by_h2_headings(self) -> None:
        """Content is split into sections keyed by lowercase H2 heading."""
        content = "Preamble text\n\n## Characters\n- Alice\n\n## Arcs\n- Arc1"
        sections = _split_sections(content)
        assert "_preamble" in sections
        assert "characters" in sections
        assert "arcs" in sections
        assert "- Alice" in sections["characters"]
        assert "- Arc1" in sections["arcs"]

    def test_preamble_captured(self) -> None:
        """Content before any H2 heading goes into _preamble."""
        content = "# Title\n\nSome metadata\n\n## Section\nBody"
        sections = _split_sections(content)
        assert "# Title" in sections["_preamble"]
        assert "Some metadata" in sections["_preamble"]

    def test_empty_sections_handled(self) -> None:
        """Empty sections produce empty strings."""
        content = "## Empty\n## Also Empty\n## HasContent\nSomething"
        sections = _split_sections(content)
        assert sections["empty"] == ""
        assert sections["also empty"] == ""
        assert "Something" in sections["hascontent"]

    def test_no_h2_returns_preamble_only(self) -> None:
        """Content with no H2 headings is all captured in _preamble."""
        content = "# Just a Title\n\nSome body text."
        sections = _split_sections(content)
        assert len(sections) == 1
        assert "_preamble" in sections
        assert "Just a Title" in sections["_preamble"]

    def test_extract_preamble_before_hr(self) -> None:
        """Content before the first --- is extracted."""
        content = "# Title\n\nMeta line\n\n---\n\n## Ignored Section"
        result = _extract_preamble_before_hr(content)
        assert "# Title" in result
        assert "Meta line" in result
        assert "## Ignored Section" not in result

    def test_extract_preamble_no_hr(self) -> None:
        """When there is no ---, full content is returned stripped."""
        content = "# Title\n\nBody text"
        result = _extract_preamble_before_hr(content)
        assert result == "# Title\n\nBody text"


# ==================== Chapter Parsing Tests ====================


class TestParseChapter:
    """Tests for WikiParser.parse_chapter."""

    def setup_method(self) -> None:
        """Create a parser instance with a mock db (unused for parsing)."""
        self.parser = WikiParser.__new__(WikiParser)
        self.parser.db = None
        self.parser._entity_cache = {}

    def test_parse_full_chapter(self, tmp_path: Path) -> None:
        """Full chapter page parses all sections correctly."""
        f = _write_md(tmp_path, FULL_CHAPTER_MD)
        result = self.parser.parse_chapter(f)

        assert isinstance(result, ChapterData)
        assert result.title == "The Gray Fence"
        assert result.chapter_type == "prose"
        assert result.status == "draft"
        assert result.part_name == "Part 1: Arrival"
        assert len(result.characters) == 2
        assert len(result.arcs) == 1
        assert len(result.scenes) == 2
        assert len(result.references) == 2
        assert len(result.poems) == 2

    def test_parse_minimal_chapter(self, tmp_path: Path) -> None:
        """Minimal chapter with only title and type/status parses."""
        f = _write_md(tmp_path, MINIMAL_CHAPTER_MD)
        result = self.parser.parse_chapter(f)

        assert result.title == "Interlude"
        assert result.chapter_type == "vignette"
        assert result.status == "revised"
        assert result.part_name is None
        assert result.characters == []
        assert result.arcs == []
        assert result.scenes == []
        assert result.references == []
        assert result.poems == []

    def test_parse_characters_with_roles(self, tmp_path: Path) -> None:
        """Characters are extracted with optional roles."""
        f = _write_md(tmp_path, FULL_CHAPTER_MD)
        result = self.parser.parse_chapter(f)

        assert ("Sofia", "protagonist") in result.characters
        assert ("Clara", None) in result.characters

    def test_parse_scenes(self, tmp_path: Path) -> None:
        """Scenes within the chapter are parsed with name, description,
        origin, status, and sources."""
        f = _write_md(tmp_path, FULL_CHAPTER_MD)
        result = self.parser.parse_chapter(f)

        scene1 = result.scenes[0]
        assert isinstance(scene1, ParsedChapterScene)
        assert scene1.name == "Morning at the Fence"
        assert scene1.description == "Sofia watches Clara from the balcony."
        assert scene1.origin == "journaled"
        assert scene1.status == "included"
        assert len(scene1.sources) == 2
        assert scene1.sources[0].source_type == "Scene"
        assert scene1.sources[0].reference == "Scene: The Gray Fence"
        assert scene1.sources[1].source_type == "Entry"

        scene2 = result.scenes[1]
        assert scene2.name == "Night Walk"
        assert scene2.description == "A restless walk through the Plateau."
        assert scene2.origin == "inferred"
        assert scene2.status == "draft"
        assert scene2.sources == []

    def test_parse_references(self, tmp_path: Path) -> None:
        """References are extracted with source_title, mode, and content."""
        f = _write_md(tmp_path, FULL_CHAPTER_MD)
        result = self.parser.parse_chapter(f)

        ref1 = result.references[0]
        assert isinstance(ref1, ParsedReference)
        assert ref1.source_title == "The Body Keeps the Score"
        assert ref1.mode == "thematic"
        assert ref1.content == "The body remembers"

        ref2 = result.references[1]
        assert ref2.source_title == "Bluets"
        assert ref2.mode == "direct"
        assert ref2.content is None

    def test_parse_poems(self, tmp_path: Path) -> None:
        """Poems list is extracted from wikilinks."""
        f = _write_md(tmp_path, FULL_CHAPTER_MD)
        result = self.parser.parse_chapter(f)

        assert result.poems == ["Untitled (November)", "After the Rain"]

    def test_missing_title_raises(self, tmp_path: Path) -> None:
        """Missing H1 title raises ValueError."""
        f = _write_md(tmp_path, "**Type:** Prose · **Status:** Draft\n")
        with pytest.raises(ValueError, match="No H1 title"):
            self.parser.parse_chapter(f)

    def test_missing_type_status_raises(self, tmp_path: Path) -> None:
        """Missing type/status metadata line raises ValueError."""
        f = _write_md(tmp_path, "# Some Title\n\nNo metadata here.\n")
        with pytest.raises(ValueError, match="No Type/Status metadata"):
            self.parser.parse_chapter(f)

    def test_invalid_chapter_type_raises(self, tmp_path: Path) -> None:
        """Invalid chapter type value raises ValueError."""
        content = "# Bad Type\n\n**Type:** Novel · **Status:** Draft\n"
        f = _write_md(tmp_path, content)
        with pytest.raises(ValueError, match="Invalid chapter type"):
            self.parser.parse_chapter(f)

    def test_invalid_status_raises(self, tmp_path: Path) -> None:
        """Invalid chapter status value raises ValueError."""
        content = "# Bad Status\n\n**Type:** Prose · **Status:** Published\n"
        f = _write_md(tmp_path, content)
        with pytest.raises(ValueError, match="Invalid chapter status"):
            self.parser.parse_chapter(f)

    def test_parse_chapter_no_part(self, tmp_path: Path) -> None:
        """Chapter without a Part line returns part_name as None."""
        content = "# Standalone\n\n**Type:** Poem · **Status:** Final\n"
        f = _write_md(tmp_path, content)
        result = self.parser.parse_chapter(f)
        assert result.part_name is None

    def test_parse_arcs(self, tmp_path: Path) -> None:
        """Arcs section wikilinks are extracted as list of names."""
        f = _write_md(tmp_path, FULL_CHAPTER_MD)
        result = self.parser.parse_chapter(f)
        assert result.arcs == ["The Long Wanting"]


# ==================== Character Parsing Tests ====================


class TestParseCharacter:
    """Tests for WikiParser.parse_character."""

    def setup_method(self) -> None:
        """Create a parser instance with a mock db (unused for parsing)."""
        self.parser = WikiParser.__new__(WikiParser)
        self.parser.db = None
        self.parser._entity_cache = {}

    def test_parse_full_character(self, tmp_path: Path) -> None:
        """Full character page parses name, narrator flag, description,
        and based_on mappings."""
        f = _write_md(tmp_path, FULL_CHARACTER_MD)
        result = self.parser.parse_character(f)

        assert isinstance(result, CharacterData)
        assert result.name == "Clara"
        assert result.is_narrator is True
        assert result.description == "A French filmmaker who exists mostly in absence."
        assert len(result.based_on) == 2

    def test_parse_minimal_character(self, tmp_path: Path) -> None:
        """Minimal character with only a name parses."""
        f = _write_md(tmp_path, MINIMAL_CHARACTER_MD)
        result = self.parser.parse_character(f)

        assert result.name == "Lena"
        assert result.role is None
        assert result.is_narrator is False
        assert result.description is None
        assert result.based_on == []

    def test_parse_narrator_flag(self, tmp_path: Path) -> None:
        """Narrator flag is detected from **Narrator** in metadata."""
        f = _write_md(tmp_path, FULL_CHARACTER_MD)
        result = self.parser.parse_character(f)
        assert result.is_narrator is True

    def test_parse_without_narrator(self, tmp_path: Path) -> None:
        """Character without **Narrator** has is_narrator=False."""
        f = _write_md(tmp_path, CHARACTER_NO_DESCRIPTION_MD)
        result = self.parser.parse_character(f)
        assert result.is_narrator is False

    def test_parse_character_no_description(self, tmp_path: Path) -> None:
        """Character without prose description returns None."""
        f = _write_md(tmp_path, CHARACTER_NO_DESCRIPTION_MD)
        result = self.parser.parse_character(f)

        assert result.name == "Thomas"
        assert result.description is None

    def test_parse_multiple_based_on(self, tmp_path: Path) -> None:
        """Multiple based_on mappings are extracted with contribution types."""
        f = _write_md(tmp_path, FULL_CHARACTER_MD)
        result = self.parser.parse_character(f)

        assert len(result.based_on) == 2
        mapping1 = result.based_on[0]
        assert isinstance(mapping1, ParsedPersonMapping)
        assert mapping1.person_name == "Clara Dupont"
        assert mapping1.contribution == "primary"

        mapping2 = result.based_on[1]
        assert mapping2.person_name == "Marie Leclerc"
        assert mapping2.contribution == "inspiration"

    def test_missing_title_raises(self, tmp_path: Path) -> None:
        """Missing H1 title raises ValueError."""
        f = _write_md(tmp_path, "**Role:** sidekick\n\nSome text.\n")
        with pytest.raises(ValueError, match="No H1 title"):
            self.parser.parse_character(f)

    def test_character_with_description_and_narrator(
        self, tmp_path: Path
    ) -> None:
        """Character with both description and narrator flag parses correctly."""
        f = _write_md(tmp_path, CHARACTER_NARRATOR_NO_ROLE_MD)
        result = self.parser.parse_character(f)

        assert result.name == "Sofia"
        assert result.is_narrator is True
        assert result.description == "The one who writes."

    def test_parse_role_when_last_line(self, tmp_path: Path) -> None:
        """Role is extracted when the Role line is the last line of content.

        Notes:
            ROLE_RE uses $ without re.MULTILINE, so the role line must
            be at the end of the preamble for the regex to match.
        """
        content = "# Solo\n\n**Role:** sidekick"
        f = _write_md(tmp_path, content)
        result = self.parser.parse_character(f)
        assert result.role == "sidekick"


# ==================== Manuscript Scene Parsing Tests ====================


class TestParseManuscriptScene:
    """Tests for WikiParser.parse_manuscript_scene."""

    def setup_method(self) -> None:
        """Create a parser instance with a mock db (unused for parsing)."""
        self.parser = WikiParser.__new__(WikiParser)
        self.parser.db = None
        self.parser._entity_cache = {}

    def test_parse_full_scene(self, tmp_path: Path) -> None:
        """Full scene page parses all fields."""
        f = _write_md(tmp_path, FULL_SCENE_MD)
        result = self.parser.parse_manuscript_scene(f)

        assert isinstance(result, ManuscriptSceneData)
        assert result.name == "Morning at the Fence"
        assert result.chapter_name == "The Gray Fence"
        assert result.origin == "journaled"
        assert result.status == "included"
        assert result.description == "Sofia watches Clara from the balcony."
        assert len(result.sources) == 3

    def test_parse_minimal_scene(self, tmp_path: Path) -> None:
        """Minimal scene with only name and origin/status."""
        f = _write_md(tmp_path, MINIMAL_SCENE_MD)
        result = self.parser.parse_manuscript_scene(f)

        assert result.name == "A Fragment"
        assert result.chapter_name is None
        assert result.origin == "invented"
        assert result.status == "fragment"
        assert result.description is None
        assert result.sources == []

    def test_parse_unassigned_scene(self, tmp_path: Path) -> None:
        """Scene without a Chapter line returns chapter_name=None."""
        f = _write_md(tmp_path, UNASSIGNED_SCENE_MD)
        result = self.parser.parse_manuscript_scene(f)

        assert result.name == "Loose Thread"
        assert result.chapter_name is None
        assert result.origin == "composite"
        assert result.status == "draft"
        assert result.description == "A moment that doesn't belong anywhere yet."

    def test_parse_multiple_sources_including_external(
        self, tmp_path: Path
    ) -> None:
        """Scene with multiple source types including External."""
        f = _write_md(tmp_path, SCENE_MULTIPLE_SOURCES_MD)
        result = self.parser.parse_manuscript_scene(f)

        assert len(result.sources) == 4

        scene_src = result.sources[0]
        assert isinstance(scene_src, ParsedSceneSource)
        assert scene_src.source_type == "Scene"
        assert "At the Market" in scene_src.reference
        assert scene_src.entry_date == "2024-06-12"

        entry_src = result.sources[1]
        assert entry_src.source_type == "Entry"
        assert entry_src.entry_date == "2024-06-15"

        thread_src = result.sources[2]
        assert thread_src.source_type == "Thread"
        assert "Bookend Kiss" in thread_src.reference
        assert thread_src.entry_date is None

        external_src = result.sources[3]
        assert external_src.source_type == "External"
        assert "Personal correspondence" in external_src.reference

    def test_parse_scene_description(self, tmp_path: Path) -> None:
        """Scene description is the prose after origin/status line."""
        f = _write_md(tmp_path, FULL_SCENE_MD)
        result = self.parser.parse_manuscript_scene(f)
        assert result.description == "Sofia watches Clara from the balcony."

    def test_missing_title_raises(self, tmp_path: Path) -> None:
        """Missing H1 title raises ValueError."""
        content = "**Chapter:** [[Some Chapter]]\n\n*journaled* · included\n"
        f = _write_md(tmp_path, content)
        with pytest.raises(ValueError, match="No H1 title"):
            self.parser.parse_manuscript_scene(f)

    def test_defaults_when_no_origin_status(self, tmp_path: Path) -> None:
        """When origin/status line is absent, defaults are used."""
        content = "# Bare Scene\n"
        f = _write_md(tmp_path, content)
        result = self.parser.parse_manuscript_scene(f)
        assert result.origin == "journaled"
        assert result.status == "fragment"

    def test_invalid_origin_raises(self, tmp_path: Path) -> None:
        """Invalid scene origin value raises ValueError."""
        content = "# Bad Origin\n\n*magical* · fragment\n"
        f = _write_md(tmp_path, content)
        with pytest.raises(ValueError, match="Invalid scene origin"):
            self.parser.parse_manuscript_scene(f)

    def test_invalid_status_raises(self, tmp_path: Path) -> None:
        """Invalid scene status value raises ValueError."""
        content = "# Bad Status\n\n*journaled* · published\n"
        f = _write_md(tmp_path, content)
        with pytest.raises(ValueError, match="Invalid scene status"):
            self.parser.parse_manuscript_scene(f)


# ==================== Entity Resolution Tests ====================


class TestEntityResolution:
    """Tests for WikiParser entity resolution against the database."""

    def test_resolve_chapter_by_title(self, test_db, db_session) -> None:
        """resolve_chapter finds a chapter by its title."""
        ch = Chapter(
            title="The Gray Fence",
            type=ChapterType.PROSE,
            status=ChapterStatus.DRAFT,
        )
        db_session.add(ch)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_chapter(db_session, "The Gray Fence")
        assert result == ch.id

    def test_resolve_chapter_case_insensitive(
        self, test_db, db_session
    ) -> None:
        """resolve_chapter is case-insensitive."""
        ch = Chapter(
            title="First Light",
            type=ChapterType.PROSE,
            status=ChapterStatus.DRAFT,
        )
        db_session.add(ch)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_chapter(db_session, "first light")
        assert result == ch.id

    def test_resolve_character_by_name(self, test_db, db_session) -> None:
        """resolve_character finds a character by name."""
        char = Character(name="Clara", role="love interest")
        db_session.add(char)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_character(db_session, "Clara")
        assert result == char.id

    def test_resolve_person_by_display_name(
        self, test_db, db_session
    ) -> None:
        """resolve_person finds a person by display_name."""
        person = Person(
            name="Clara",
            lastname="Dupont",
            slug="clara_dupont",
            relation_type=RelationType.ROMANTIC,
        )
        db_session.add(person)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_person(db_session, "Clara Dupont")
        assert result == person.id

    def test_resolve_entry_by_date(self, test_db, db_session) -> None:
        """resolve_entry_by_date finds an entry by date string."""
        entry = Entry(
            date=date(2024, 11, 15),
            file_path="2024/2024-11-15.md",
            word_count=500,
            reading_time=2.5,
        )
        db_session.add(entry)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_entry_by_date(db_session, "2024-11-15")
        assert result == entry.id

    def test_resolve_unknown_entity_returns_none(
        self, test_db, db_session
    ) -> None:
        """Resolving a nonexistent entity returns None."""
        parser = WikiParser(test_db)
        assert parser.resolve_chapter(db_session, "Nonexistent") is None
        assert parser.resolve_character(db_session, "Nobody") is None
        assert parser.resolve_person(db_session, "Ghost") is None
        assert parser.resolve_entry_by_date(db_session, "1999-01-01") is None

    def test_cache_clearing(self, test_db, db_session) -> None:
        """clear_cache empties the internal entity cache."""
        ch = Chapter(
            title="Cached Chapter",
            type=ChapterType.PROSE,
            status=ChapterStatus.DRAFT,
        )
        db_session.add(ch)
        db_session.flush()

        parser = WikiParser(test_db)
        parser.resolve_chapter(db_session, "Cached Chapter")
        assert "chapters" in parser._entity_cache

        parser.clear_cache()
        assert parser._entity_cache == {}

    def test_resolve_arc_by_name(self, test_db, db_session) -> None:
        """resolve_arc finds an arc by name."""
        arc = Arc(name="The Long Wanting", description="A yearning arc.")
        db_session.add(arc)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_arc(db_session, "The Long Wanting")
        assert result == arc.id

    def test_resolve_poem_by_title(self, test_db, db_session) -> None:
        """resolve_poem finds a poem by title."""
        poem = Poem(title="Untitled (November)")
        db_session.add(poem)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_poem(db_session, "Untitled (November)")
        assert result == poem.id

    def test_resolve_reference_source(self, test_db, db_session) -> None:
        """resolve_reference_source finds a source by title."""
        src = ReferenceSource(
            title="The Body Keeps the Score",
            type=ReferenceType.BOOK,
        )
        db_session.add(src)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_reference_source(
            db_session, "The Body Keeps the Score"
        )
        assert result == src.id

    def test_resolve_manuscript_scene(self, test_db, db_session) -> None:
        """resolve_manuscript_scene finds a scene by name."""
        ms = ManuscriptScene(
            name="Morning at the Fence",
            origin=SceneOrigin.JOURNALED,
            status=SceneStatus.INCLUDED,
        )
        db_session.add(ms)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_manuscript_scene(
            db_session, "Morning at the Fence"
        )
        assert result == ms.id

    def test_resolve_part_by_display_name(
        self, test_db, db_session
    ) -> None:
        """resolve_part finds a part by display_name."""
        part = Part(number=1, title="Arrival")
        db_session.add(part)
        db_session.flush()

        parser = WikiParser(test_db)
        result = parser.resolve_part(db_session, "Part 1: Arrival")
        assert result == part.id

    def test_cache_reuse(self, test_db, db_session) -> None:
        """Second resolve call uses cached data instead of re-querying."""
        ch = Chapter(
            title="Reuse Test",
            type=ChapterType.VIGNETTE,
            status=ChapterStatus.REVISED,
        )
        db_session.add(ch)
        db_session.flush()

        parser = WikiParser(test_db)
        result1 = parser.resolve_chapter(db_session, "Reuse Test")
        result2 = parser.resolve_chapter(db_session, "Reuse Test")
        assert result1 == result2 == ch.id
        assert "chapters" in parser._entity_cache
