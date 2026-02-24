#!/usr/bin/env python3
"""
wiki_conftest.py
----------------
Shared fixtures for wiki integration tests.

Provides a richly populated database with entities across all types,
suitable for end-to-end testing of wiki generation, sync, linting,
and publishing workflows.

Fixtures:
    wiki_output: Temporary wiki output directory
    populated_wiki_db: Database with full entity graph
    wiki_exporter: Configured WikiExporter instance
    wiki_sync: Configured WikiSync instance
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.analysis import Arc, Event, Scene, SceneDate
from dev.database.models.core import Entry
from dev.database.models.creative import Poem, PoemVersion, Reference, ReferenceSource
from dev.database.models.entities import Person, Tag, Theme
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
from dev.database.models.metadata import Motif, MotifInstance


# ==================== Output Fixtures ====================

@pytest.fixture
def wiki_output(tmp_path):
    """Temporary wiki output directory."""
    return tmp_path / "wiki"


# ==================== Populated Database ====================

@pytest.fixture
def populated_wiki_db(db_session):
    """
    Create a rich entity graph for integration testing.

    Populates the database with:
    - 1 city, 5 locations
    - 8 people (including narrator)
    - 5 entries spanning 2 months
    - 5 tags, 3 themes
    - 2 arcs, 3 events
    - 5 scenes with dates, people, locations
    - 2 poems with versions
    - 2 reference sources with references
    - 1 motif with instances
    - 1 part, 2 chapters, 2 characters, 2 manuscript scenes

    Returns:
        The session with all entities committed.
    """
    # ---- City + Locations ----
    city = City(name="Montreal", country="Canada")
    db_session.add(city)
    db_session.flush()

    cafe = Location(name="Café Olimpico", city_id=city.id)
    home = Location(name="Home", city_id=city.id)
    park = Location(name="Parc La Fontaine", city_id=city.id)
    metro = Location(name="Station Jarry", city_id=city.id)
    library = Location(name="Grande Bibliothèque", city_id=city.id)
    db_session.add_all([cafe, home, park, metro, library])
    db_session.flush()

    # ---- People ----
    narrator = Person(
        name="Sofia", lastname="Fernandez",
        slug="sofia_fernandez", relation_type=RelationType.SELF,
    )
    clara = Person(
        name="Clara", lastname="Dupont",
        slug="clara_dupont", relation_type=RelationType.ROMANTIC,
    )
    majo = Person(
        name="Majo", lastname="Rivera",
        slug="majo_rivera", relation_type=RelationType.FRIEND,
    )
    daniel = Person(
        name="Daniel", lastname="Ortiz",
        slug="daniel_ortiz", relation_type=RelationType.FAMILY,
    )
    bea = Person(
        name="Bea", lastname="Moreau",
        slug="bea_moreau", relation_type=RelationType.ACQUAINTANCE,
    )
    therapist = Person(
        name="Dra. Luna", disambiguator="therapist",
        slug="dra-luna_therapist", relation_type=RelationType.PROFESSIONAL,
    )
    louis = Person(
        name="Louis", lastname="Tremblay",
        slug="louis_tremblay", relation_type=RelationType.COLLEAGUE,
    )
    sophie = Person(
        name="Sophie", lastname="Lefebvre",
        slug="sophie_lefebvre", relation_type=RelationType.FRIEND,
    )
    people = [narrator, clara, majo, daniel, bea, therapist, louis, sophie]
    db_session.add_all(people)
    db_session.flush()

    # ---- Entries ----
    entry1 = Entry(
        date=date(2024, 11, 8),
        file_path="2024/2024-11-08.md",
        word_count=1247, reading_time=6.2,
        summary="A day of encounters and reflections.",
        rating=4.0,
        rating_justification="Rich narrative detail and emotional depth.",
    )
    entry2 = Entry(
        date=date(2024, 11, 9),
        file_path="2024/2024-11-09.md",
        word_count=800, reading_time=4.0,
        summary="Quiet morning, writing at the café.",
    )
    entry3 = Entry(
        date=date(2024, 11, 15),
        file_path="2024/2024-11-15.md",
        word_count=1500, reading_time=7.5,
        summary="The long walk through the park.",
        rating=5.0,
    )
    entry4 = Entry(
        date=date(2024, 12, 1),
        file_path="2024/2024-12-01.md",
        word_count=600, reading_time=3.0,
        summary="First snow and therapy session.",
    )
    entry5 = Entry(
        date=date(2024, 12, 5),
        file_path="2024/2024-12-05.md",
        word_count=950, reading_time=4.7,
        summary="Library research and a chance meeting.",
    )
    entries = [entry1, entry2, entry3, entry4, entry5]
    db_session.add_all(entries)
    db_session.flush()

    # ---- Entry relationships ----
    entry1.people.extend([narrator, clara, majo])
    entry1.locations.extend([cafe, home])
    entry1.cities.append(city)
    entry2.people.extend([narrator])
    entry2.locations.extend([cafe])
    entry2.cities.append(city)
    entry3.people.extend([narrator, clara, sophie])
    entry3.locations.extend([park, metro])
    entry3.cities.append(city)
    entry4.people.extend([narrator, therapist])
    entry4.locations.extend([home])
    entry4.cities.append(city)
    entry5.people.extend([narrator, louis, bea])
    entry5.locations.extend([library])
    entry5.cities.append(city)

    # ---- Tags (need 2+ entries for page generation) ----
    tag_loneliness = Tag(name="loneliness")
    tag_writing = Tag(name="writing")
    tag_walking = Tag(name="walking")
    tag_winter = Tag(name="winter")
    tag_therapy = Tag(name="therapy")
    tags = [tag_loneliness, tag_writing, tag_walking, tag_winter, tag_therapy]
    db_session.add_all(tags)
    db_session.flush()

    entry1.tags.extend([tag_loneliness, tag_writing])
    entry2.tags.extend([tag_writing])
    entry3.tags.extend([tag_walking, tag_loneliness])
    entry4.tags.extend([tag_winter, tag_therapy])
    entry5.tags.extend([tag_writing, tag_winter])

    # ---- Themes (need 2+ entries for page generation) ----
    theme_identity = Theme(name="identity")
    theme_memory = Theme(name="memory")
    theme_distance = Theme(name="distance")
    themes = [theme_identity, theme_memory, theme_distance]
    db_session.add_all(themes)
    db_session.flush()

    # Theme instances (ThemeInstance with descriptions)
    from dev.database.models import ThemeInstance

    theme_instances = [
        ThemeInstance(theme_id=theme_identity.id, entry_id=entry1.id, description="Exploring who she is through encounters."),
        ThemeInstance(theme_id=theme_distance.id, entry_id=entry1.id, description="The gap between closeness and solitude."),
        ThemeInstance(theme_id=theme_identity.id, entry_id=entry2.id, description="Writing as self-definition."),
        ThemeInstance(theme_id=theme_memory.id, entry_id=entry3.id, description="The park triggers old memories."),
        ThemeInstance(theme_id=theme_distance.id, entry_id=entry3.id, description="Walking away from what was familiar."),
        ThemeInstance(theme_id=theme_memory.id, entry_id=entry4.id, description="Therapy session revisiting the past."),
        ThemeInstance(theme_id=theme_identity.id, entry_id=entry5.id, description="A chance meeting redefines boundaries."),
        ThemeInstance(theme_id=theme_memory.id, entry_id=entry5.id, description="The library as archive of selves."),
    ]
    db_session.add_all(theme_instances)

    # ---- Scenes ----
    scene1 = Scene(
        name="Morning at the Café",
        description="A conversation over espresso.",
        entry_id=entry1.id,
    )
    scene2 = Scene(
        name="The Walk Home",
        description="Walking alone through Mile End.",
        entry_id=entry1.id,
    )
    scene3 = Scene(
        name="Writing Session",
        description="Drafting at the corner table.",
        entry_id=entry2.id,
    )
    scene4 = Scene(
        name="Parc La Fontaine at Dusk",
        description="The long walk and the geese.",
        entry_id=entry3.id,
    )
    scene5 = Scene(
        name="First Snow",
        description="Watching snow from the window.",
        entry_id=entry4.id,
    )
    scenes = [scene1, scene2, scene3, scene4, scene5]
    db_session.add_all(scenes)
    db_session.flush()

    scene1.people.extend([narrator, clara])
    scene1.locations.append(cafe)
    scene2.people.append(narrator)
    scene2.locations.append(home)
    scene3.people.append(narrator)
    scene3.locations.append(cafe)
    scene4.people.extend([narrator, clara, sophie])
    scene4.locations.append(park)
    scene5.people.extend([narrator, therapist])
    scene5.locations.append(home)

    # Scene dates
    for scene, dt in [
        (scene1, "2024-11-08"),
        (scene2, "2024-11-08"),
        (scene3, "2024-11-09"),
        (scene4, "2024-11-15"),
        (scene5, "2024-12-01"),
    ]:
        db_session.add(SceneDate(date=dt, scene_id=scene.id))

    # ---- Arcs ----
    arc1 = Arc(
        name="The Long Wanting",
        description="A story of longing and proximity.",
    )
    arc2 = Arc(
        name="The Writing Life",
        description="Craft, discipline, and doubt.",
    )
    db_session.add_all([arc1, arc2])
    db_session.flush()

    entry1.arcs.append(arc1)
    entry2.arcs.append(arc2)
    entry3.arcs.extend([arc1, arc2])
    entry5.arcs.append(arc2)

    # ---- Events ----
    event1 = Event(name="The Long November")
    event2 = Event(name="Café Drafts")
    event3 = Event(name="The First Snowfall")
    db_session.add_all([event1, event2, event3])
    db_session.flush()

    event1.entries.extend([entry1, entry3])
    event1.scenes.extend([scene1, scene4])
    event2.entries.extend([entry2, entry5])
    event2.scenes.append(scene3)
    event3.entries.append(entry4)
    event3.scenes.append(scene5)

    # ---- Poems ----
    poem1 = Poem(title="The Gray Fence")
    poem2 = Poem(title="November Nocturne")
    db_session.add_all([poem1, poem2])
    db_session.flush()

    pv1 = PoemVersion(
        poem_id=poem1.id, entry_id=entry1.id,
        content="The gray fence divides\nwhat was from what might have been",
    )
    pv2 = PoemVersion(
        poem_id=poem2.id, entry_id=entry3.id,
        content="November hums its nocturne low\nacross the frozen park",
    )
    db_session.add_all([pv1, pv2])

    # ---- Reference Sources + References ----
    ref_source1 = ReferenceSource(
        title="The Waves", author="Virginia Woolf",
        type=ReferenceType.BOOK,
    )
    ref_source2 = ReferenceSource(
        title="Paterson", author="Jim Jarmusch",
        type=ReferenceType.FILM,
    )
    db_session.add_all([ref_source1, ref_source2])
    db_session.flush()

    ref1 = Reference(
        source_id=ref_source1.id, entry_id=entry1.id,
        mode=ReferenceMode.THEMATIC,
        content="The waves broke on the shore.",
    )
    ref2 = Reference(
        source_id=ref_source2.id, entry_id=entry2.id,
        mode=ReferenceMode.VISUAL,
        description="The quiet rhythm of daily life.",
    )
    db_session.add_all([ref1, ref2])

    # ---- Motif ----
    motif = Motif(name="The Loop")
    db_session.add(motif)
    db_session.flush()

    mi1 = MotifInstance(
        description="The recurring phone check.",
        motif_id=motif.id, entry_id=entry1.id,
    )
    mi2 = MotifInstance(
        description="Circling the same block.",
        motif_id=motif.id, entry_id=entry3.id,
    )
    db_session.add_all([mi1, mi2])

    # ---- Manuscript: Part ----
    part = Part(number=1, title="The Archive")
    db_session.add(part)
    db_session.flush()

    # ---- Manuscript: Chapters ----
    chapter1 = Chapter(
        title="Espresso and Silence",
        number=1,
        part_id=part.id,
        type=ChapterType.PROSE,
        status=ChapterStatus.DRAFT,
    )
    chapter2 = Chapter(
        title="November Nocturne",
        number=2,
        part_id=part.id,
        type=ChapterType.POEM,
        status=ChapterStatus.REVISED,
    )
    db_session.add_all([chapter1, chapter2])
    db_session.flush()

    chapter1.arcs.append(arc1)
    chapter1.poems.append(poem1)
    chapter2.poems.append(poem2)

    # ---- Manuscript: Characters ----
    char_sofia = Character(
        name="Valeria",
        description="The narrator, restless and observant.",
        role="Protagonist",
        is_narrator=True,
    )
    char_clara = Character(
        name="Lena",
        description="Quiet intensity, always leaving.",
        role="Love Interest",
    )
    db_session.add_all([char_sofia, char_clara])
    db_session.flush()

    chapter1.characters.extend([char_sofia, char_clara])
    chapter2.characters.append(char_sofia)

    # Person-Character mappings
    pcm1 = PersonCharacterMap(
        person_id=narrator.id, character_id=char_sofia.id,
        contribution=ContributionType.PRIMARY,
    )
    pcm2 = PersonCharacterMap(
        person_id=clara.id, character_id=char_clara.id,
        contribution=ContributionType.PRIMARY,
    )
    db_session.add_all([pcm1, pcm2])

    # ---- Manuscript: Scenes ----
    ms_scene1 = ManuscriptScene(
        name="The Espresso Pause",
        description="Valeria watches Lena across the table.",
        chapter_id=chapter1.id,
        origin=SceneOrigin.JOURNALED,
        status=SceneStatus.DRAFT,
    )
    ms_scene2 = ManuscriptScene(
        name="Nocturne Walk",
        description="Alone in the park after dark.",
        chapter_id=chapter2.id,
        origin=SceneOrigin.COMPOSITE,
        status=SceneStatus.INCLUDED,
    )
    db_session.add_all([ms_scene1, ms_scene2])
    db_session.flush()

    # Manuscript sources
    ms_src1 = ManuscriptSource(
        manuscript_scene_id=ms_scene1.id,
        source_type=SourceType.SCENE,
        scene_id=scene1.id,
    )
    ms_src2 = ManuscriptSource(
        manuscript_scene_id=ms_scene1.id,
        source_type=SourceType.ENTRY,
        entry_id=entry1.id,
    )
    ms_src3 = ManuscriptSource(
        manuscript_scene_id=ms_scene2.id,
        source_type=SourceType.SCENE,
        scene_id=scene4.id,
    )
    db_session.add_all([ms_src1, ms_src2, ms_src3])

    # Manuscript reference
    ms_ref = ManuscriptReference(
        chapter_id=chapter1.id,
        source_id=ref_source1.id,
        mode=ReferenceMode.THEMATIC,
        content="The rhythm of waves, the rhythm of talk.",
    )
    db_session.add(ms_ref)

    db_session.commit()
    return db_session
