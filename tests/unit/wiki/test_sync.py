#!/usr/bin/env python3
"""
test_sync.py
------------
Tests for the WikiSync manuscript synchronization orchestrator.

Validates the full sync cycle (validate, ingest, regenerate) and
individual operations against a test database with real entities
and temporary wiki file structures.

Key Test Areas:
    - SyncResult data tracking and success semantics
    - Validation gate (errors block ingestion)
    - Per-entity-type ingestion (chapters, characters, scenes)
    - Full and partial sync cycle orchestration
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.analysis import Arc
from dev.database.models.core import Entry
from dev.database.models.creative import Poem, ReferenceSource
from dev.database.models.entities import Person, Tag
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    ContributionType,
    ReferenceMode,
    ReferenceType,
    RelationType,
    SceneOrigin,
    SceneStatus,
    SourceType,
)
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptReference,
    ManuscriptScene,
    ManuscriptSource,
    Part,
    PersonCharacterMap,
)
from dev.wiki.sync import SyncResult, WikiSync


# ==================== Fixtures ====================

@pytest.fixture
def mock_logger():
    """
    Create a mock logger compatible with WikiSync.

    WikiSync calls self.logger.info() which NullLogger does not provide.
    A MagicMock auto-creates any attribute accessed on it.
    """
    return MagicMock()


@pytest.fixture
def populated_wiki(tmp_path, test_db, db_session):
    """
    Create a wiki directory structure with manuscript files and DB entities.

    Populates the database with chapters, characters, manuscript scenes,
    people, arcs, poems, reference sources, entries, and a part. Writes
    corresponding markdown files to a temporary wiki directory tree.

    The markdown files follow the exact format produced by the Jinja2
    templates in dev/wiki/templates/manuscript/.

    Returns:
        Tuple of (wiki_dir Path, db_session, dict of created entities)
    """
    wiki_dir = tmp_path / "wiki"
    manuscript_dir = wiki_dir / "manuscript"
    chapters_dir = manuscript_dir / "chapters"
    characters_dir = manuscript_dir / "characters"
    scenes_dir = manuscript_dir / "scenes"
    chapters_dir.mkdir(parents=True)
    characters_dir.mkdir(parents=True)
    scenes_dir.mkdir(parents=True)

    # --- DB entities ---

    # Part
    part = Part(number=1, title="The Beginning")
    db_session.add(part)
    db_session.flush()

    # Chapter
    chapter = Chapter(
        title="The Gray Fence",
        type=ChapterType.PROSE,
        status=ChapterStatus.DRAFT,
        part_id=part.id,
    )
    db_session.add(chapter)
    db_session.flush()

    # Second chapter (for scene reassignment tests)
    chapter2 = Chapter(
        title="Warm Pavement",
        type=ChapterType.VIGNETTE,
        status=ChapterStatus.DRAFT,
    )
    db_session.add(chapter2)
    db_session.flush()

    # Character
    character = Character(
        name="Lucia",
        role="Protagonist",
        is_narrator=True,
        description="The one who remembers.",
    )
    db_session.add(character)
    db_session.flush()

    second_char = Character(
        name="Emilio",
        role="Love interest",
        is_narrator=False,
        description="The one who forgets.",
    )
    db_session.add(second_char)
    db_session.flush()

    # People
    sofia = Person(
        name="Sofia", lastname="Fernandez",
        slug="sofia_fernandez", relation_type=RelationType.SELF,
    )
    clara = Person(
        name="Clara", lastname="Dupont",
        slug="clara_dupont", relation_type=RelationType.ROMANTIC,
    )
    db_session.add_all([sofia, clara])
    db_session.flush()

    # Arc
    arc = Arc(name="The Long Wanting", description="A story of longing.")
    db_session.add(arc)
    db_session.flush()

    # Poem
    poem = Poem(title="The Loop")
    db_session.add(poem)
    db_session.flush()

    # Reference source
    ref_source = ReferenceSource(
        title="Nocturnes", author="Kazuo Ishiguro",
        type=ReferenceType.BOOK,
    )
    db_session.add(ref_source)
    db_session.flush()

    # Tag (used for validatable wikilink files)
    tag = Tag(name="loneliness")
    db_session.add(tag)
    db_session.flush()

    # Entry (for manuscript scene sources)
    entry = Entry(
        date=date(2024, 11, 8),
        file_path="2024/2024-11-08.md",
        word_count=1247,
    )
    db_session.add(entry)
    db_session.flush()

    # Manuscript scene
    ms_scene = ManuscriptScene(
        name="Station Jarry Kiss",
        description="First kiss at the metro station.",
        chapter_id=chapter.id,
        origin=SceneOrigin.JOURNALED,
        status=SceneStatus.FRAGMENT,
    )
    db_session.add(ms_scene)
    db_session.flush()

    # Initial person-character mapping
    pcm = PersonCharacterMap(
        person_id=sofia.id,
        character_id=character.id,
        contribution=ContributionType.PRIMARY,
    )
    db_session.add(pcm)

    # Initial chapter relationships
    chapter.characters.append(character)
    chapter.arcs.append(arc)

    db_session.commit()

    # --- Wiki files ---

    # Chapter markdown follows the template format from chapter.jinja2.
    # Type/Status metadata line, optional Part, scene count, then ---
    # followed by H2 sections for Characters, Arcs, Scenes, References, Poems.
    chapter_md = (
        "# The Gray Fence\n\n"
        "**Type:** Vignette · **Status:** Revised\n"
        "**Part:** [[Part 1: The Beginning]]\n"
        "1 scenes\n\n"
        "---\n\n"
        "## Characters\n\n"
        "- [[Lucia]] · Protagonist\n"
        "- [[Emilio]] · Love interest\n\n"
        "## Arcs\n\n"
        "- [[The Long Wanting]]\n\n"
        "---\n\n"
        "## Scenes\n\n"
        "### Station Jarry Kiss\n"
        "First kiss at the metro.\n\n"
        "*journaled* · draft\n"
        "- Entry: 2024-11-08\n\n"
        "---\n\n"
        "## References\n\n"
        "- [[Nocturnes]] *(thematic)* — the mood of waiting\n\n"
        "## Poems\n\n"
        "- [[The Loop]]\n"
    )
    (chapters_dir / "the-gray-fence.md").write_text(chapter_md)

    # Character markdown follows character.jinja2.
    # Note: ROLE_RE only matches when role line is the last line of preamble.
    # With a description present, role is not extracted by the parser.
    character_md = (
        "# Lucia\n\n"
        "**Role:** Narrator · **Narrator**\n\n"
        "The woman who chose to remember everything.\n\n"
        "1 chapter\n\n"
        "---\n\n"
        "## Based On\n\n"
        "- [[Sofia Fernandez]] *(primary)*\n"
        "- [[Clara Dupont]] *(inspiration)*\n\n"
        "## Chapters\n\n"
        "- [[The Gray Fence]] · Prose · Draft\n"
    )
    (characters_dir / "lucia.md").write_text(character_md)

    # Manuscript scene markdown follows manuscript_scene.jinja2.
    scene_md = (
        "# Station Jarry Kiss\n\n"
        "**Chapter:** [[The Gray Fence]]\n\n"
        "*composite* · draft\n\n"
        "The greeting kiss that bookends the goodbye.\n\n"
        "---\n\n"
        "## Sources\n\n"
        "- **Entry:** Morning encounter · [[2024-11-08]]\n"
        "- **External:** Overheard conversation\n"
    )
    (scenes_dir / "station-jarry-kiss.md").write_text(scene_md)

    entities = {
        "part": part,
        "chapter": chapter,
        "chapter2": chapter2,
        "character": character,
        "second_char": second_char,
        "sofia": sofia,
        "clara": clara,
        "arc": arc,
        "poem": poem,
        "ref_source": ref_source,
        "tag": tag,
        "entry": entry,
        "ms_scene": ms_scene,
    }

    return wiki_dir, db_session, entities


@pytest.fixture
def sync_instance(test_db, populated_wiki, mock_logger):
    """
    Create a WikiSync instance wired to the test database and temp wiki dir.

    Returns:
        Tuple of (WikiSync instance, wiki_dir, db_session, entities dict)
    """
    wiki_dir, db_session, entities = populated_wiki
    sync = WikiSync(test_db, wiki_dir=wiki_dir, logger=mock_logger)
    return sync, wiki_dir, db_session, entities


# ==================== TestSyncResult ====================

class TestSyncResult:
    """Tests for the SyncResult data structure."""

    def test_empty_result_success(self):
        """An empty SyncResult with no errors reports success=True."""
        result = SyncResult()
        assert result.success is True
        assert result.files_validated == 0
        assert result.files_ingested == 0
        assert result.files_generated == 0
        assert result.files_changed == 0

    def test_result_with_errors_not_success(self):
        """A SyncResult with errors reports success=False."""
        result = SyncResult()
        result.errors.append("Something went wrong")
        assert result.success is False

    def test_summary_includes_stats(self):
        """Summary includes validated, ingested, generated, and error counts."""
        result = SyncResult()
        result.files_validated = 5
        result.files_ingested = 3
        result.files_generated = 10
        result.files_changed = 2
        result.updates["chapters"] = 2
        result.updates["characters"] = 1
        result.warnings.append("minor issue")
        result.errors.append("critical issue")

        summary = result.summary()
        assert "Validated: 5 files" in summary
        assert "Ingested: 3 files" in summary
        assert "chapters: 2 updated" in summary
        assert "characters: 1 updated" in summary
        assert "Generated: 10 files (2 changed)" in summary
        assert "Warnings: 1" in summary
        assert "Errors: 1" in summary
        assert "critical issue" in summary

    def test_updates_dict_tracks_entity_types(self):
        """Updates dict has keys for chapters, characters, and scenes."""
        result = SyncResult()
        assert "chapters" in result.updates
        assert "characters" in result.updates
        assert "scenes" in result.updates
        assert all(v == 0 for v in result.updates.values())

        result.updates["chapters"] = 3
        result.updates["scenes"] = 7
        assert result.updates["chapters"] == 3
        assert result.updates["scenes"] == 7


# ==================== TestSyncValidation ====================

class TestSyncValidation:
    """Tests for the validation gate in the sync cycle."""

    def test_validation_passes_for_valid_files(
        self, test_db, db_session, tmp_path, mock_logger
    ):
        """Manuscript files with only resolvable wikilinks pass validation.

        The WikiValidator resolves wikilinks against Person, Location,
        Arc, Tag, Theme, Poem, ReferenceSource, and Entry names. It does
        not resolve Character, Chapter, or Part names. This test uses
        only entity types the validator knows about.
        """
        wiki_dir = tmp_path / "validwiki"
        manuscript_dir = wiki_dir / "manuscript" / "chapters"
        manuscript_dir.mkdir(parents=True)

        # Create DB entities the validator can resolve
        arc = Arc(name="The Long Wanting")
        poem = Poem(title="The Loop")
        ref = ReferenceSource(
            title="Nocturnes", author="Ishiguro", type=ReferenceType.BOOK,
        )
        db_session.add_all([arc, poem, ref])
        db_session.commit()

        # Write a chapter file with only resolvable wikilinks
        valid_md = (
            "# Valid Chapter\n\n"
            "**Type:** Prose · **Status:** Draft\n"
            "0 scenes\n\n"
            "---\n\n"
            "## Arcs\n\n"
            "- [[The Long Wanting]]\n\n"
            "## Poems\n\n"
            "- [[The Loop]]\n\n"
            "## References\n\n"
            "- [[Nocturnes]] *(thematic)*\n"
        )
        (manuscript_dir / "valid-chapter.md").write_text(valid_md)

        sync = WikiSync(test_db, wiki_dir=wiki_dir, logger=mock_logger)
        result = SyncResult()
        sync._validate(wiki_dir / "manuscript", result)

        assert result.success is True
        assert result.files_validated == 1

    def test_validation_fails_for_unresolved_wikilinks(
        self, test_db, tmp_path, mock_logger
    ):
        """Files with unresolved wikilinks produce validation errors."""
        wiki_dir = tmp_path / "badwiki"
        manuscript_dir = wiki_dir / "manuscript" / "chapters"
        manuscript_dir.mkdir(parents=True)

        bad_md = (
            "# Broken Chapter\n\n"
            "**Type:** Prose · **Status:** Draft\n\n"
            "## Characters\n\n"
            "- [[Nonexistent Character]]\n"
        )
        (manuscript_dir / "broken.md").write_text(bad_md)

        sync = WikiSync(test_db, wiki_dir=wiki_dir, logger=mock_logger)
        result = SyncResult()
        sync._validate(wiki_dir / "manuscript", result)

        assert result.success is False
        assert any("Nonexistent Character" in e for e in result.errors)

    def test_missing_manuscript_dir_returns_error(
        self, test_db, tmp_path, mock_logger
    ):
        """Sync with nonexistent manuscript directory returns error."""
        sync = WikiSync(test_db, wiki_dir=tmp_path, logger=mock_logger)
        result = sync.sync_manuscript()

        assert result.success is False
        assert any("Manuscript directory not found" in e for e in result.errors)


# ==================== TestSyncIngestion ====================

class TestSyncIngestion:
    """Tests for wiki-to-DB ingestion of manuscript entities.

    All ingestion tests call _ingest directly, bypassing validation.
    The _ingest method opens its own DB session via db.session_scope(),
    parses wiki files, updates entities, and commits. The test then
    refreshes entities on the original db_session to verify changes.
    """

    def test_ingest_chapter_updates_type_and_status(
        self, sync_instance
    ):
        """Ingesting a chapter updates its type and status from wiki."""
        sync, wiki_dir, db_session, entities = sync_instance
        chapter = entities["chapter"]

        # Chapter wiki says Vignette/Revised, DB has Prose/Draft
        assert chapter.type == ChapterType.PROSE
        assert chapter.status == ChapterStatus.DRAFT

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(chapter)
        assert chapter.type == ChapterType.VIGNETTE
        assert chapter.status == ChapterStatus.REVISED
        assert result.updates["chapters"] >= 1

    def test_ingest_chapter_updates_m2m_characters(
        self, sync_instance
    ):
        """Ingesting a chapter updates its character M2M relationships."""
        sync, wiki_dir, db_session, entities = sync_instance
        chapter = entities["chapter"]

        # Initially has only Lucia
        assert len(chapter.characters) == 1
        assert chapter.characters[0].name == "Lucia"

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(chapter)
        char_names = sorted([c.name for c in chapter.characters])
        assert char_names == ["Emilio", "Lucia"]

    def test_ingest_chapter_updates_arcs_and_poems(
        self, sync_instance
    ):
        """Ingesting a chapter updates arc and poem M2M relationships."""
        sync, wiki_dir, db_session, entities = sync_instance
        chapter = entities["chapter"]

        # Initially has arc but no poems
        assert len(chapter.arcs) == 1
        assert len(chapter.poems) == 0

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(chapter)
        assert len(chapter.arcs) == 1
        assert chapter.arcs[0].name == "The Long Wanting"
        assert len(chapter.poems) == 1
        assert chapter.poems[0].title == "The Loop"

    def test_ingest_chapter_updates_references(
        self, sync_instance
    ):
        """Ingesting a chapter creates ManuscriptReference records."""
        sync, wiki_dir, db_session, entities = sync_instance
        chapter = entities["chapter"]

        # No references initially
        assert len(chapter.references) == 0

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(chapter)
        assert len(chapter.references) == 1
        ref = chapter.references[0]
        assert ref.source.title == "Nocturnes"
        assert ref.mode == ReferenceMode.THEMATIC
        assert ref.content == "the mood of waiting"

    def test_ingest_character_updates_narrator_and_description(
        self, sync_instance
    ):
        """Ingesting a character updates is_narrator flag and description.

        The parser's ROLE_RE uses $ without re.MULTILINE, so the role
        field is only extracted when the Role line is the last line of
        the preamble. When a description follows the Role line, role
        is parsed as None. This is a known parser limitation.
        """
        sync, wiki_dir, db_session, entities = sync_instance
        character = entities["character"]

        assert character.description == "The one who remembers."
        assert character.is_narrator is True

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(character)
        # is_narrator is detected via NARRATOR_RE (separate from ROLE_RE)
        assert character.is_narrator is True
        # Description is updated from wiki
        assert "chose to remember" in character.description
        assert result.updates["characters"] >= 1

    def test_ingest_character_role_from_minimal_page(
        self, sync_instance
    ):
        """Ingesting a minimal character page (no description) extracts role.

        The ROLE_RE regex matches when the Role line is at the end of
        the preamble (no description or chapter count lines following).
        """
        sync, wiki_dir, db_session, entities = sync_instance

        # Create a character with a minimal page (role as last preamble line)
        minimal_char = Character(
            name="Thomas", role=None, is_narrator=False,
        )
        db_session.add(minimal_char)
        db_session.commit()

        minimal_md = "# Thomas\n\n**Role:** sidekick"
        chars_dir = wiki_dir / "manuscript" / "characters"
        (chars_dir / "thomas.md").write_text(minimal_md)

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(minimal_char)
        assert minimal_char.role == "sidekick"
        assert minimal_char.is_narrator is False

    def test_ingest_manuscript_scene_updates_origin_status_chapter(
        self, sync_instance
    ):
        """Ingesting a manuscript scene updates origin, status, and chapter."""
        sync, wiki_dir, db_session, entities = sync_instance
        ms_scene = entities["ms_scene"]

        # DB has journaled/fragment
        assert ms_scene.origin == SceneOrigin.JOURNALED
        assert ms_scene.status == SceneStatus.FRAGMENT

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(ms_scene)
        # Wiki says composite/draft
        assert ms_scene.origin == SceneOrigin.COMPOSITE
        assert ms_scene.status == SceneStatus.DRAFT
        assert ms_scene.description == (
            "The greeting kiss that bookends the goodbye."
        )
        assert ms_scene.chapter_id == entities["chapter"].id
        assert result.updates["scenes"] >= 1

    def test_ingest_manuscript_scene_updates_sources(
        self, sync_instance
    ):
        """Ingesting a manuscript scene replaces source records."""
        sync, wiki_dir, db_session, entities = sync_instance
        ms_scene = entities["ms_scene"]

        # Initially no sources
        assert len(ms_scene.sources) == 0

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        db_session.refresh(ms_scene)
        sources = ms_scene.sources
        assert len(sources) == 2

        source_types = {s.source_type for s in sources}
        assert SourceType.ENTRY in source_types
        assert SourceType.EXTERNAL in source_types

        ext_source = next(
            s for s in sources if s.source_type == SourceType.EXTERNAL
        )
        assert ext_source.external_note == "Overheard conversation"

    def test_ingest_parse_error_does_not_block_other_files(
        self, sync_instance
    ):
        """A parse error in one file does not prevent ingestion of others."""
        sync, wiki_dir, db_session, entities = sync_instance

        # Write a malformed chapter file (no Type/Status metadata)
        bad_chapter = (
            wiki_dir / "manuscript" / "chapters" / "broken-chapter.md"
        )
        bad_chapter.write_text(
            "# Broken Chapter\n\nNo type or status metadata here.\n"
        )

        result = SyncResult()
        sync._ingest(wiki_dir / "manuscript", result)

        # The good files should still have been ingested
        # (the-gray-fence.md chapter, lucia.md character,
        # station-jarry-kiss.md scene)
        assert result.files_ingested >= 2
        # The broken file should produce an error
        assert any("broken-chapter.md" in e for e in result.errors)


# ==================== TestSyncCycle ====================

class TestSyncCycle:
    """Tests for the full and partial sync cycle orchestration."""

    def test_full_sync_runs_validate_ingest_regenerate(
        self, sync_instance
    ):
        """Full sync runs all three stages: validate, ingest, regenerate.

        The validator is mocked to return no diagnostics so that
        ingestion proceeds without being blocked by wikilinks to
        entity types the validator does not resolve (Characters, Parts).
        """
        sync, wiki_dir, db_session, entities = sync_instance

        with patch.object(
            sync.validator, "validate_directory", return_value={}
        ), patch.object(sync, "_regenerate") as mock_regen:
            result = sync.sync_manuscript()

        assert result.files_validated == 0  # mock returns empty dict
        assert result.files_ingested > 0
        mock_regen.assert_called_once()

    def test_ingest_only_skips_regeneration(self, sync_instance):
        """Ingest-only mode skips the regeneration step."""
        sync, wiki_dir, db_session, entities = sync_instance

        with patch.object(
            sync.validator, "validate_directory", return_value={}
        ), patch.object(sync, "_regenerate") as mock_regen:
            result = sync.sync_manuscript(ingest_only=True)

        assert result.files_ingested > 0
        mock_regen.assert_not_called()

    def test_generate_only_skips_validation_and_ingestion(
        self, sync_instance
    ):
        """Generate-only mode skips validation and ingestion entirely."""
        sync, wiki_dir, db_session, entities = sync_instance

        with patch.object(sync, "_validate") as mock_validate, \
             patch.object(sync, "_ingest") as mock_ingest, \
             patch.object(sync, "_regenerate") as mock_regen:
            result = sync.sync_manuscript(generate_only=True)

        mock_validate.assert_not_called()
        mock_ingest.assert_not_called()
        mock_regen.assert_called_once()

    def test_validation_errors_block_ingestion(self, sync_instance):
        """Validation errors prevent the ingestion step from running."""
        sync, wiki_dir, db_session, entities = sync_instance

        # Write a file with an unresolved wikilink to trigger error
        bad_file = wiki_dir / "manuscript" / "chapters" / "invalid.md"
        bad_file.write_text(
            "# Invalid Chapter\n\n"
            "**Type:** Prose · **Status:** Draft\n\n"
            "## Characters\n\n"
            "- [[Ghost Person Who Does Not Exist]]\n"
        )

        with patch.object(sync, "_ingest") as mock_ingest:
            result = sync.sync_manuscript()

        assert result.success is False
        mock_ingest.assert_not_called()
