#!/usr/bin/env python3
"""
test_chapter_manager.py
-----------------------
Tests for ChapterManager — manuscript chapter, part, scene, source, and reference management.

Usage:
    python -m pytest tests/unit/managers/test_chapter_manager.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.managers.chapter_manager import ChapterManager
from dev.database.models import (
    Arc,
    Chapter,
    Character,
    ManuscriptReference,
    ManuscriptScene,
    ManuscriptSource,
    Part,
    ReferenceSource,
)
from dev.database.models.enums import (
    ChapterStatus,
    ChapterType,
    ReferenceMode,
    ReferenceType,
    SceneOrigin,
    SceneStatus,
    SourceType,
)


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def chapter_manager(db_session):
    """Create ChapterManager instance for testing."""
    return ChapterManager(db_session)


@pytest.fixture
def sample_part(db_session):
    """Create a sample part."""
    part = Part(number=1, title="Arrival")
    db_session.add(part)
    db_session.flush()
    return part


@pytest.fixture
def sample_chapter(chapter_manager):
    """Create a sample chapter."""
    return chapter_manager.create({"title": "The Gray Fence", "type": "prose"})


@pytest.fixture
def sample_character(db_session):
    """Create a sample character."""
    char = Character(name="Sofia", role="protagonist", is_narrator=True)
    db_session.add(char)
    db_session.flush()
    return char


@pytest.fixture
def sample_arc(db_session):
    """Create a sample arc."""
    arc = Arc(name="The Long Wanting")
    db_session.add(arc)
    db_session.flush()
    return arc


@pytest.fixture
def sample_reference_source(db_session):
    """Create a sample reference source."""
    source = ReferenceSource(
        title="Important Book",
        author="Author",
        type=ReferenceType.BOOK,
    )
    db_session.add(source)
    db_session.flush()
    return source


# =========================================================================
# Test Classes
# =========================================================================


class TestChapterCreate:
    """Test chapter creation."""

    def test_create_basic(self, chapter_manager):
        """Create chapter with just title."""
        ch = chapter_manager.create({"title": "First Chapter"})
        assert ch.title == "First Chapter"
        assert ch.type == ChapterType.PROSE
        assert ch.status == ChapterStatus.DRAFT

    def test_create_with_type(self, chapter_manager):
        """Create chapter with explicit type."""
        ch = chapter_manager.create({"title": "Poem Chapter", "type": "poem"})
        assert ch.type == ChapterType.POEM

    def test_create_with_status(self, chapter_manager):
        """Create chapter with explicit status."""
        ch = chapter_manager.create({"title": "Final Chapter", "status": "final"})
        assert ch.status == ChapterStatus.FINAL

    def test_create_with_number(self, chapter_manager):
        """Create chapter with number."""
        ch = chapter_manager.create({"title": "Numbered", "number": 3})
        assert ch.number == 3

    def test_create_with_content(self, chapter_manager):
        """Create chapter with inline content."""
        ch = chapter_manager.create({
            "title": "Short Piece",
            "type": "vignette",
            "content": "A brief moment.",
        })
        assert ch.content == "A brief moment."
        assert ch.has_content

    def test_create_duplicate_raises(self, chapter_manager):
        """Creating duplicate chapter raises error."""
        chapter_manager.create({"title": "Unique"})
        with pytest.raises(Exception):
            chapter_manager.create({"title": "Unique"})

    def test_create_missing_title_raises(self, chapter_manager):
        """Creating chapter without title raises ValidationError."""
        with pytest.raises(Exception):
            chapter_manager.create({})


class TestChapterUpdate:
    """Test chapter field updates."""

    def test_update_status(self, chapter_manager, sample_chapter):
        """Update chapter status."""
        result = chapter_manager.update_status(sample_chapter, "revised")
        assert result.status == ChapterStatus.REVISED

    def test_update_invalid_status_raises(self, chapter_manager, sample_chapter):
        """Invalid status raises ValidationError."""
        with pytest.raises(Exception):
            chapter_manager.update_status(sample_chapter, "nonexistent")

    def test_update_fields(self, chapter_manager, sample_chapter):
        """Update chapter scalar fields."""
        updated = chapter_manager.update(sample_chapter, {"number": 5})
        assert updated.number == 5


class TestChapterPart:
    """Test part assignment and removal."""

    def test_assign_part(self, chapter_manager, sample_chapter, sample_part):
        """Assign chapter to part."""
        result = chapter_manager.assign_part(sample_chapter, sample_part.id)
        assert result.part_id == sample_part.id

    def test_clear_part(self, chapter_manager, sample_chapter, sample_part):
        """Clear chapter from part."""
        chapter_manager.assign_part(sample_chapter, sample_part.id)
        result = chapter_manager.clear_part(sample_chapter)
        assert result.part_id is None

    def test_assign_nonexistent_part_raises(self, chapter_manager, sample_chapter):
        """Assigning to nonexistent part raises error."""
        with pytest.raises(Exception):
            chapter_manager.assign_part(sample_chapter, 9999)


class TestChapterRelationships:
    """Test linking/unlinking characters and arcs."""

    def test_link_character(self, chapter_manager, sample_chapter, sample_character):
        """Link character to chapter."""
        chapter_manager.link_character(sample_chapter, sample_character.id)
        assert sample_character in sample_chapter.characters

    def test_unlink_character(self, chapter_manager, sample_chapter, sample_character):
        """Unlink character from chapter."""
        chapter_manager.link_character(sample_chapter, sample_character.id)
        chapter_manager.unlink_character(sample_chapter, sample_character.id)
        assert sample_character not in sample_chapter.characters

    def test_link_arc(self, chapter_manager, sample_chapter, sample_arc):
        """Link arc to chapter."""
        chapter_manager.link_arc(sample_chapter, sample_arc.id)
        assert sample_arc in sample_chapter.arcs

    def test_unlink_arc(self, chapter_manager, sample_chapter, sample_arc):
        """Unlink arc from chapter."""
        chapter_manager.link_arc(sample_chapter, sample_arc.id)
        chapter_manager.unlink_arc(sample_chapter, sample_arc.id)
        assert sample_arc not in sample_chapter.arcs

    def test_link_nonexistent_character_raises(self, chapter_manager, sample_chapter):
        """Linking nonexistent character raises error."""
        with pytest.raises(Exception):
            chapter_manager.link_character(sample_chapter, 9999)

    def test_duplicate_link_is_idempotent(self, chapter_manager, sample_chapter, sample_character):
        """Linking same character twice doesn't duplicate."""
        chapter_manager.link_character(sample_chapter, sample_character.id)
        chapter_manager.link_character(sample_chapter, sample_character.id)
        assert len([c for c in sample_chapter.characters if c.id == sample_character.id]) == 1


class TestManuscriptScene:
    """Test manuscript scene CRUD within chapters."""

    def test_create_scene(self, chapter_manager, sample_chapter):
        """Create manuscript scene."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Morning at the Fence"}
        )
        assert scene.name == "Morning at the Fence"
        assert scene.chapter_id == sample_chapter.id
        assert scene.origin == SceneOrigin.JOURNALED
        assert scene.status == SceneStatus.FRAGMENT

    def test_create_scene_with_origin(self, chapter_manager, sample_chapter):
        """Create scene with explicit origin."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Imagined Scene", "origin": "invented"}
        )
        assert scene.origin == SceneOrigin.INVENTED

    def test_update_scene(self, chapter_manager, sample_chapter):
        """Update manuscript scene fields."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Old Name"}
        )
        updated = chapter_manager.update_manuscript_scene(
            scene, {"name": "New Name", "status": "included"}
        )
        assert updated.name == "New Name"
        assert updated.status == SceneStatus.INCLUDED

    def test_delete_scene(self, chapter_manager, sample_chapter, db_session):
        """Delete manuscript scene."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "To Delete"}
        )
        scene_id = scene.id
        chapter_manager.delete_manuscript_scene(scene)
        assert db_session.get(ManuscriptScene, scene_id) is None

    def test_get_scenes(self, chapter_manager, sample_chapter):
        """Get all scenes for chapter."""
        chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Scene 1"}
        )
        chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Scene 2"}
        )
        scenes = chapter_manager.get_manuscript_scenes(sample_chapter)
        assert len(scenes) == 2

    def test_create_scene_missing_name_raises(self, chapter_manager, sample_chapter):
        """Creating scene without name raises error."""
        with pytest.raises(Exception):
            chapter_manager.create_manuscript_scene(sample_chapter, {})


class TestManuscriptSource:
    """Test linking scenes to journal source material."""

    def test_add_scene_source(self, chapter_manager, sample_chapter):
        """Add source to manuscript scene."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Test Scene"}
        )
        source = chapter_manager.add_scene_source(
            scene, {"source_type": "entry", "entry_id": 1}
        )
        assert source.source_type == SourceType.ENTRY
        assert source.entry_id == 1

    def test_add_external_source(self, chapter_manager, sample_chapter):
        """Add external source with note."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Test Scene"}
        )
        source = chapter_manager.add_scene_source(
            scene, {
                "source_type": "external",
                "external_note": "Family story told by mother",
            }
        )
        assert source.source_type == SourceType.EXTERNAL
        assert source.external_note == "Family story told by mother"

    def test_remove_source(self, chapter_manager, sample_chapter, db_session):
        """Remove source from manuscript scene."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Test Scene"}
        )
        source = chapter_manager.add_scene_source(
            scene, {"source_type": "scene", "scene_id": 1}
        )
        source_id = source.id
        chapter_manager.remove_scene_source(source)
        assert db_session.get(ManuscriptSource, source_id) is None

    def test_invalid_source_type_raises(self, chapter_manager, sample_chapter):
        """Invalid source type raises error."""
        scene = chapter_manager.create_manuscript_scene(
            sample_chapter, {"name": "Test Scene"}
        )
        with pytest.raises(Exception):
            chapter_manager.add_scene_source(scene, {"source_type": "invalid"})


class TestManuscriptReference:
    """Test manuscript reference CRUD within chapters."""

    def test_create_reference(self, chapter_manager, sample_chapter, sample_reference_source):
        """Create manuscript reference."""
        ref = chapter_manager.create_manuscript_reference(
            sample_chapter,
            {"source_id": sample_reference_source.id, "mode": "direct", "content": "A quote"},
        )
        assert ref.chapter_id == sample_chapter.id
        assert ref.source_id == sample_reference_source.id
        assert ref.mode == ReferenceMode.DIRECT
        assert ref.content == "A quote"

    def test_create_reference_default_mode(self, chapter_manager, sample_chapter, sample_reference_source):
        """Reference defaults to THEMATIC mode."""
        ref = chapter_manager.create_manuscript_reference(
            sample_chapter, {"source_id": sample_reference_source.id}
        )
        assert ref.mode == ReferenceMode.THEMATIC

    def test_delete_reference(self, chapter_manager, sample_chapter, sample_reference_source, db_session):
        """Delete manuscript reference."""
        ref = chapter_manager.create_manuscript_reference(
            sample_chapter, {"source_id": sample_reference_source.id}
        )
        ref_id = ref.id
        chapter_manager.delete_manuscript_reference(ref)
        assert db_session.get(ManuscriptReference, ref_id) is None

    def test_nonexistent_source_raises(self, chapter_manager, sample_chapter):
        """Reference with nonexistent source raises error."""
        with pytest.raises(Exception):
            chapter_manager.create_manuscript_reference(
                sample_chapter, {"source_id": 9999}
            )


class TestPartOperations:
    """Test part CRUD."""

    def test_create_part(self, chapter_manager):
        """Create part with number and title."""
        part = chapter_manager.create_part({"number": 1, "title": "Arrival"})
        assert part.number == 1
        assert part.title == "Arrival"

    def test_get_part(self, chapter_manager, sample_part):
        """Get part by ID."""
        result = chapter_manager.get_part(sample_part.id)
        assert result is not None
        assert result.title == "Arrival"

    def test_get_all_parts(self, chapter_manager):
        """Get all parts ordered by number."""
        chapter_manager.create_part({"number": 2, "title": "Departure"})
        chapter_manager.create_part({"number": 1, "title": "Arrival"})
        parts = chapter_manager.get_all_parts()
        assert len(parts) == 2

    def test_update_part(self, chapter_manager, sample_part):
        """Update part fields."""
        updated = chapter_manager.update_part(sample_part, {"title": "New Title"})
        assert updated.title == "New Title"

    def test_delete_part(self, chapter_manager, sample_part, db_session):
        """Delete part (chapters become unassigned)."""
        part_id = sample_part.id
        chapter_manager.delete_part(sample_part)
        assert db_session.get(Part, part_id) is None
