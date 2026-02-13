#!/usr/bin/env python3
"""
test_context_manuscript.py
--------------------------
Tests for WikiContextBuilder manuscript methods.

Creates test manuscript entities (Part, Chapter, Character,
ManuscriptScene, ManuscriptSource, PersonCharacterMap) and
verifies that context builder methods produce correct
template-ready dicts.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.analysis import Arc, Scene, SceneDate, Thread
from dev.database.models.core import Entry
from dev.database.models.creative import Poem, ReferenceSource
from dev.database.models.entities import Person
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
from dev.database.models.geography import City, Location
from dev.database.models.manuscript import (
    Chapter,
    Character,
    ManuscriptReference,
    ManuscriptScene,
    ManuscriptSource,
    Part,
    PersonCharacterMap,
)
from dev.wiki.context import WikiContextBuilder


# ==================== Fixtures ====================


@pytest.fixture
def builder(db_session):
    """Create WikiContextBuilder with test session."""
    return WikiContextBuilder(db_session)


@pytest.fixture
def montreal(db_session):
    """Create Montreal city."""
    city = City(name="Montreal", country="Canada")
    db_session.add(city)
    db_session.flush()
    return city


@pytest.fixture
def cafe(db_session, montreal):
    """Create a cafe location in Montreal."""
    loc = Location(name="Cafe Olimpico", city_id=montreal.id)
    db_session.add(loc)
    db_session.flush()
    return loc


@pytest.fixture
def narrator(db_session):
    """Create narrator person (self)."""
    p = Person(
        name="Sofia", lastname="Fernandez",
        slug="sofia_fernandez", relation_type=RelationType.SELF,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def clara(db_session):
    """Create Clara (romantic)."""
    p = Person(
        name="Clara", lastname="Dupont",
        slug="clara_dupont", relation_type=RelationType.ROMANTIC,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def entry_nov8(db_session, narrator):
    """Create a sample entry."""
    entry = Entry(
        date=date(2024, 11, 8),
        file_path="2024/2024-11-08.md",
        word_count=1247,
        reading_time=6.2,
        summary="A day of encounters.",
        rating=4.0,
    )
    db_session.add(entry)
    db_session.flush()
    entry.people.append(narrator)
    db_session.flush()
    return entry


@pytest.fixture
def journal_scene(db_session, entry_nov8, clara, cafe):
    """Create a journal scene linked to entry."""
    scene = Scene(
        name="Morning at the Cafe",
        description="A conversation over espresso.",
        entry_id=entry_nov8.id,
    )
    db_session.add(scene)
    db_session.flush()
    scene.people.append(clara)
    scene.locations.append(cafe)
    sd = SceneDate(date="2024-11-08", scene_id=scene.id)
    db_session.add(sd)
    db_session.flush()
    return scene


@pytest.fixture
def thread(db_session, entry_nov8, clara):
    """Create a thread on the entry."""
    t = Thread(
        name="The Bookend Kiss",
        from_date="2024-11-08",
        to_date="2024-12",
        content="The greeting kiss bookends the goodbye.",
        entry_id=entry_nov8.id,
    )
    db_session.add(t)
    db_session.flush()
    t.people.append(clara)
    db_session.flush()
    return t


@pytest.fixture
def part(db_session):
    """Create a book part."""
    p = Part(number=1, title="The Beginning")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def chapter(db_session, part):
    """Create a chapter assigned to a part."""
    ch = Chapter(
        title="First Light",
        number=1,
        part_id=part.id,
        type=ChapterType.PROSE,
        status=ChapterStatus.DRAFT,
    )
    db_session.add(ch)
    db_session.flush()
    return ch


@pytest.fixture
def chapter_no_part(db_session):
    """Create a chapter without a part."""
    ch = Chapter(
        title="Interlude",
        type=ChapterType.VIGNETTE,
        status=ChapterStatus.REVISED,
    )
    db_session.add(ch)
    db_session.flush()
    return ch


@pytest.fixture
def character(db_session):
    """Create a fictional character."""
    c = Character(
        name="Elise",
        description="A restless writer in her late twenties.",
        role="protagonist",
        is_narrator=True,
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def character_secondary(db_session):
    """Create a secondary character."""
    c = Character(
        name="Lena",
        description="A photographer and confidant.",
        role="love interest",
        is_narrator=False,
    )
    db_session.add(c)
    db_session.flush()
    return c


@pytest.fixture
def person_character_map(db_session, narrator, character):
    """Map narrator person to character."""
    pcm = PersonCharacterMap(
        person_id=narrator.id,
        character_id=character.id,
        contribution=ContributionType.PRIMARY,
    )
    db_session.add(pcm)
    db_session.flush()
    return pcm


@pytest.fixture
def person_character_map_secondary(db_session, clara, character_secondary):
    """Map Clara to secondary character."""
    pcm = PersonCharacterMap(
        person_id=clara.id,
        character_id=character_secondary.id,
        contribution=ContributionType.INSPIRATION,
    )
    db_session.add(pcm)
    db_session.flush()
    return pcm


@pytest.fixture
def ms_scene(db_session, chapter):
    """Create a manuscript scene assigned to chapter."""
    ms = ManuscriptScene(
        name="The Cafe Encounter",
        description="Elise meets Lena for the first time.",
        chapter_id=chapter.id,
        origin=SceneOrigin.JOURNALED,
        status=SceneStatus.DRAFT,
    )
    db_session.add(ms)
    db_session.flush()
    return ms


@pytest.fixture
def ms_scene_unassigned(db_session):
    """Create a manuscript scene without a chapter."""
    ms = ManuscriptScene(
        name="The Unwritten Scene",
        description="A fragment yet to be placed.",
        origin=SceneOrigin.INVENTED,
        status=SceneStatus.FRAGMENT,
    )
    db_session.add(ms)
    db_session.flush()
    return ms


@pytest.fixture
def ms_source_scene(db_session, ms_scene, journal_scene):
    """Create a manuscript source linked to a journal scene."""
    src = ManuscriptSource(
        manuscript_scene_id=ms_scene.id,
        source_type=SourceType.SCENE,
        scene_id=journal_scene.id,
    )
    db_session.add(src)
    db_session.flush()
    return src


@pytest.fixture
def ms_source_entry(db_session, ms_scene, entry_nov8):
    """Create a manuscript source linked to an entry."""
    src = ManuscriptSource(
        manuscript_scene_id=ms_scene.id,
        source_type=SourceType.ENTRY,
        entry_id=entry_nov8.id,
    )
    db_session.add(src)
    db_session.flush()
    return src


@pytest.fixture
def ms_source_thread(db_session, ms_scene, thread):
    """Create a manuscript source linked to a thread."""
    src = ManuscriptSource(
        manuscript_scene_id=ms_scene.id,
        source_type=SourceType.THREAD,
        thread_id=thread.id,
    )
    db_session.add(src)
    db_session.flush()
    return src


@pytest.fixture
def ms_source_external(db_session, ms_scene):
    """Create an external manuscript source."""
    src = ManuscriptSource(
        manuscript_scene_id=ms_scene.id,
        source_type=SourceType.EXTERNAL,
        external_note="Memory of a childhood event",
    )
    db_session.add(src)
    db_session.flush()
    return src


@pytest.fixture
def arc(db_session):
    """Create an arc for chapter linking."""
    a = Arc(name="The Long Wanting", description="A story of longing.")
    db_session.add(a)
    db_session.flush()
    return a


@pytest.fixture
def poem(db_session):
    """Create a poem for chapter linking."""
    p = Poem(title="Untitled (November)")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def ref_source(db_session):
    """Create a reference source."""
    source = ReferenceSource(
        title="The Body Keeps the Score",
        author="van der Kolk",
        type=ReferenceType.BOOK,
    )
    db_session.add(source)
    db_session.flush()
    return source


@pytest.fixture
def manuscript_reference(db_session, chapter, ref_source):
    """Create a manuscript reference on a chapter."""
    ref = ManuscriptReference(
        chapter_id=chapter.id,
        source_id=ref_source.id,
        mode=ReferenceMode.THEMATIC,
        content="Trauma memory and the body",
    )
    db_session.add(ref)
    db_session.flush()
    return ref


@pytest.fixture
def chapter_with_relations(
    db_session, chapter, character, character_secondary,
    arc, poem, ms_scene, manuscript_reference,
):
    """Chapter with all relationships populated."""
    chapter.characters.extend([character, character_secondary])
    chapter.arcs.append(arc)
    chapter.poems.append(poem)
    db_session.flush()
    return chapter


# ==================== Chapter Context ====================

class TestBuildChapterContext:
    """Tests for build_chapter_context."""

    def test_basic_fields(self, builder, chapter, part):
        """Chapter context includes title, number, type, status, part."""
        ctx = builder.build_chapter_context(chapter)
        assert ctx["title"] == "First Light"
        assert ctx["number"] == 1
        assert ctx["type"] == "Prose"
        assert ctx["status"] == "Draft"
        assert ctx["part"] == "Part 1: The Beginning"

    def test_no_part(self, builder, chapter_no_part):
        """Chapter without part shows None."""
        ctx = builder.build_chapter_context(chapter_no_part)
        assert ctx["part"] is None
        assert ctx["type"] == "Vignette"
        assert ctx["status"] == "Revised"

    def test_scene_count(self, builder, chapter, ms_scene):
        """Scene count reflects manuscript scenes in chapter."""
        ctx = builder.build_chapter_context(chapter)
        assert ctx["scene_count"] == 1

    def test_characters(self, builder, chapter_with_relations):
        """Characters list includes name and role."""
        ctx = builder.build_chapter_context(chapter_with_relations)
        assert len(ctx["characters"]) == 2
        names = [c["name"] for c in ctx["characters"]]
        assert "Elise" in names
        assert "Lena" in names
        elise = next(c for c in ctx["characters"] if c["name"] == "Elise")
        assert elise["role"] == "protagonist"

    def test_arcs(self, builder, chapter_with_relations):
        """Arcs list includes arc names."""
        ctx = builder.build_chapter_context(chapter_with_relations)
        assert len(ctx["arcs"]) == 1
        assert ctx["arcs"][0]["name"] == "The Long Wanting"

    def test_poems(self, builder, chapter_with_relations):
        """Poems list includes poem titles."""
        ctx = builder.build_chapter_context(chapter_with_relations)
        assert len(ctx["poems"]) == 1
        assert ctx["poems"][0]["title"] == "Untitled (November)"

    def test_scenes_with_sources(
        self, builder, chapter, ms_scene, ms_source_scene
    ):
        """Scenes include source details."""
        ctx = builder.build_chapter_context(chapter)
        assert len(ctx["scenes"]) == 1
        scene = ctx["scenes"][0]
        assert scene["name"] == "The Cafe Encounter"
        assert scene["description"] == "Elise meets Lena for the first time."
        assert scene["origin"] == "Journaled"
        assert scene["status"] == "Draft"
        assert len(scene["sources"]) == 1
        assert scene["sources"][0]["type"] == "Scene"

    def test_references(self, builder, chapter, manuscript_reference):
        """References include source title, mode, content."""
        ctx = builder.build_chapter_context(chapter)
        assert len(ctx["references"]) == 1
        ref = ctx["references"][0]
        assert ref["source_title"] == "The Body Keeps the Score"
        assert ref["mode"] == "Thematic"
        assert ref["content"] == "Trauma memory and the body"

    def test_empty_chapter(self, builder, chapter_no_part):
        """Chapter with no relationships has empty lists."""
        ctx = builder.build_chapter_context(chapter_no_part)
        assert ctx["characters"] == []
        assert ctx["arcs"] == []
        assert ctx["poems"] == []
        assert ctx["scenes"] == []
        assert ctx["references"] == []
        assert ctx["scene_count"] == 0


# ==================== Character Context ====================

class TestBuildCharacterContext:
    """Tests for build_character_context."""

    def test_basic_fields(self, builder, character):
        """Character context includes name, description, role, is_narrator."""
        ctx = builder.build_character_context(character)
        assert ctx["name"] == "Elise"
        assert ctx["description"] == "A restless writer in her late twenties."
        assert ctx["role"] == "protagonist"
        assert ctx["is_narrator"] is True

    def test_chapter_count(
        self, builder, character, chapter_with_relations
    ):
        """Chapter count reflects chapters featuring this character."""
        ctx = builder.build_character_context(character)
        assert ctx["chapter_count"] == 1

    def test_chapters_list(
        self, builder, character, chapter_with_relations
    ):
        """Chapters list includes title, type, status."""
        ctx = builder.build_character_context(character)
        assert len(ctx["chapters"]) == 1
        ch = ctx["chapters"][0]
        assert ch["title"] == "First Light"
        assert ch["type"] == "Prose"
        assert ch["status"] == "Draft"

    def test_based_on(
        self, builder, character, person_character_map, narrator
    ):
        """Based-on list includes person name, slug, contribution."""
        ctx = builder.build_character_context(character)
        assert len(ctx["based_on"]) == 1
        person = ctx["based_on"][0]
        assert person["person_name"] == "Sofia Fernandez"
        assert person["person_slug"] == "sofia_fernandez"
        assert person["contribution"] == "Primary"

    def test_no_mappings(self, builder, character_secondary):
        """Character without person mappings has empty based_on."""
        ctx = builder.build_character_context(character_secondary)
        assert ctx["based_on"] == []
        assert ctx["is_narrator"] is False

    def test_character_no_chapters(self, builder, character):
        """Character not in any chapter has empty chapters and count 0."""
        ctx = builder.build_character_context(character)
        assert ctx["chapter_count"] == 0
        assert ctx["chapters"] == []


# ==================== ManuscriptScene Context ====================

class TestBuildManuscriptSceneContext:
    """Tests for build_manuscript_scene_context."""

    def test_basic_fields(self, builder, ms_scene, chapter):
        """Manuscript scene context includes name, chapter, origin, status."""
        ctx = builder.build_manuscript_scene_context(ms_scene)
        assert ctx["name"] == "The Cafe Encounter"
        assert ctx["description"] == "Elise meets Lena for the first time."
        assert ctx["chapter"] == "First Light"
        assert ctx["origin"] == "Journaled"
        assert ctx["status"] == "Draft"

    def test_unassigned_scene(self, builder, ms_scene_unassigned):
        """Unassigned scene has None chapter."""
        ctx = builder.build_manuscript_scene_context(ms_scene_unassigned)
        assert ctx["chapter"] is None
        assert ctx["origin"] == "Invented"
        assert ctx["status"] == "Fragment"

    def test_scene_source(
        self, builder, ms_scene, ms_source_scene
    ):
        """Source with journal scene shows correct type and reference."""
        ctx = builder.build_manuscript_scene_context(ms_scene)
        assert len(ctx["sources"]) == 1
        src = ctx["sources"][0]
        assert src["type"] == "Scene"
        assert "Morning at the Cafe" in src["reference"]

    def test_entry_source(
        self, builder, ms_scene, ms_source_entry, entry_nov8
    ):
        """Source with entry shows entry date."""
        ctx = builder.build_manuscript_scene_context(ms_scene)
        src = next(
            s for s in ctx["sources"] if s["type"] == "Entry"
        )
        assert src["entry_date"] == "2024-11-08"

    def test_thread_source(
        self, builder, ms_scene, ms_source_thread
    ):
        """Source with thread shows correct reference."""
        ctx = builder.build_manuscript_scene_context(ms_scene)
        src = next(
            s for s in ctx["sources"] if s["type"] == "Thread"
        )
        assert "The Bookend Kiss" in src["reference"]
        assert src["entry_date"] is None

    def test_external_source(
        self, builder, ms_scene, ms_source_external
    ):
        """External source shows external note."""
        ctx = builder.build_manuscript_scene_context(ms_scene)
        src = next(
            s for s in ctx["sources"] if s["type"] == "External"
        )
        assert "Memory of a childhood event" in src["reference"]
        assert src["entry_date"] is None

    def test_no_sources(self, builder, ms_scene_unassigned):
        """Scene without sources has empty list."""
        ctx = builder.build_manuscript_scene_context(ms_scene_unassigned)
        assert ctx["sources"] == []


# ==================== Part Context ====================

class TestBuildPartContext:
    """Tests for build_part_context."""

    def test_basic_fields(self, builder, part):
        """Part context includes display_name, number, title."""
        ctx = builder.build_part_context(part)
        assert ctx["display_name"] == "Part 1: The Beginning"
        assert ctx["number"] == 1
        assert ctx["title"] == "The Beginning"

    def test_chapter_count(self, builder, part, chapter):
        """Chapter count reflects chapters in this part."""
        ctx = builder.build_part_context(part)
        assert ctx["chapter_count"] == 1

    def test_chapters_list(self, builder, part, chapter):
        """Chapters list includes title, number, type, status."""
        ctx = builder.build_part_context(part)
        assert len(ctx["chapters"]) == 1
        ch = ctx["chapters"][0]
        assert ch["title"] == "First Light"
        assert ch["number"] == 1
        assert ch["type"] == "Prose"
        assert ch["status"] == "Draft"

    def test_empty_part(self, builder, db_session):
        """Part with no chapters has empty list and count 0."""
        p = Part(number=2, title="The Middle")
        db_session.add(p)
        db_session.flush()

        ctx = builder.build_part_context(p)
        assert ctx["chapter_count"] == 0
        assert ctx["chapters"] == []

    def test_part_title_only(self, builder, db_session):
        """Part with title but no number displays correctly."""
        p = Part(title="Epilogue")
        db_session.add(p)
        db_session.flush()

        ctx = builder.build_part_context(p)
        assert ctx["display_name"] == "Epilogue"
        assert ctx["number"] is None

    def test_part_number_only(self, builder, db_session):
        """Part with number but no title displays correctly."""
        p = Part(number=3)
        db_session.add(p)
        db_session.flush()

        ctx = builder.build_part_context(p)
        assert ctx["display_name"] == "Part 3"
        assert ctx["title"] is None
