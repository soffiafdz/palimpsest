#!/usr/bin/env python3
"""
test_context.py
---------------
Tests for WikiContextBuilder.

Creates test entities with known relationships and verifies that
context builder methods produce correct template-ready dicts.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date

# --- Third-party imports ---
import pytest

# --- Local imports ---
from dev.database.models.analysis import Arc, Event, Scene, SceneDate, Thread
from dev.database.models.core import Entry
from dev.database.models.creative import Poem, PoemVersion, Reference, ReferenceSource
from dev.database.models.entities import Person, Tag, Theme
from dev.database.models.enums import (
    ReferenceMode,
    ReferenceType,
    RelationType,
)
from dev.database.models.geography import City, Location
from dev.database.models.manuscript import Part
from dev.database.models.metadata import Motif, MotifInstance
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
    loc = Location(name="Café Olimpico", city_id=montreal.id)
    db_session.add(loc)
    db_session.flush()
    return loc


@pytest.fixture
def home(db_session, montreal):
    """Create home location in Montreal."""
    loc = Location(name="Home", city_id=montreal.id)
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
def majo(db_session):
    """Create Majo (friend)."""
    p = Person(
        name="Majo", lastname="Rodriguez",
        slug="majo_rodriguez", relation_type=RelationType.FRIEND,
    )
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def entry_nov8(db_session, narrator, clara, montreal, cafe, home):
    """Create a sample entry with relationships."""
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

    entry.people.extend([narrator, clara])
    entry.locations.extend([cafe, home])
    entry.cities.append(montreal)
    db_session.flush()
    return entry


@pytest.fixture
def tag_loneliness(db_session, entry_nov8):
    """Create a tag linked to entry."""
    tag = Tag(name="loneliness")
    db_session.add(tag)
    db_session.flush()
    entry_nov8.tags.append(tag)
    db_session.flush()
    return tag


@pytest.fixture
def theme_identity(db_session, entry_nov8):
    """Create a theme linked to entry."""
    theme = Theme(name="identity")
    db_session.add(theme)
    db_session.flush()
    entry_nov8.themes.append(theme)
    db_session.flush()
    return theme


@pytest.fixture
def scene_cafe(db_session, entry_nov8, clara, cafe):
    """Create a scene at the cafe."""
    scene = Scene(
        name="Morning at the Cafe",
        description="A conversation over espresso.",
        entry_id=entry_nov8.id,
    )
    db_session.add(scene)
    db_session.flush()
    scene.people.append(clara)
    scene.locations.append(cafe)
    scene_date = SceneDate(date="2024-11-08", scene_id=scene.id)
    db_session.add(scene_date)
    db_session.flush()
    return scene


@pytest.fixture
def arc_wanting(db_session, entry_nov8):
    """Create an arc linked to entry."""
    arc = Arc(name="The Long Wanting", description="A story of longing.")
    db_session.add(arc)
    db_session.flush()
    entry_nov8.arcs.append(arc)
    db_session.flush()
    return arc


@pytest.fixture
def event_long_nov(db_session, entry_nov8, scene_cafe):
    """Create an event linked to entry and scene."""
    event = Event(name="The Long November")
    db_session.add(event)
    db_session.flush()
    event.entries.append(entry_nov8)
    event.scenes.append(scene_cafe)
    db_session.flush()
    return event


@pytest.fixture
def thread_kiss(db_session, entry_nov8, clara, cafe):
    """Create a thread on the entry."""
    thread = Thread(
        name="The Bookend Kiss",
        from_date="2024-11-08",
        to_date="2024-12",
        content="The greeting kiss bookends the goodbye.",
        entry_id=entry_nov8.id,
        referenced_entry_date=date(2024, 12, 15),
    )
    db_session.add(thread)
    db_session.flush()
    thread.people.append(clara)
    thread.locations.append(cafe)
    db_session.flush()
    return thread


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
def reference(db_session, entry_nov8, ref_source):
    """Create a reference on the entry."""
    ref = Reference(
        content="The body keeps the score",
        mode=ReferenceMode.DIRECT,
        entry_id=entry_nov8.id,
        source_id=ref_source.id,
    )
    db_session.add(ref)
    db_session.flush()
    return ref


@pytest.fixture
def poem(db_session):
    """Create a poem."""
    p = Poem(title="Untitled (November)")
    db_session.add(p)
    db_session.flush()
    return p


@pytest.fixture
def poem_version(db_session, poem, entry_nov8):
    """Create a poem version on the entry."""
    pv = PoemVersion(
        content="Lines of verse\nAbout November",
        poem_id=poem.id,
        entry_id=entry_nov8.id,
    )
    db_session.add(pv)
    db_session.flush()
    return pv


@pytest.fixture
def motif_loop(db_session):
    """Create a motif."""
    m = Motif(name="The Loop")
    db_session.add(m)
    db_session.flush()
    return m


@pytest.fixture
def motif_instance(db_session, motif_loop, entry_nov8):
    """Create a motif instance on the entry."""
    mi = MotifInstance(
        description="The recurring pattern of checking the phone.",
        motif_id=motif_loop.id,
        entry_id=entry_nov8.id,
    )
    db_session.add(mi)
    db_session.flush()
    return mi


# ==================== Entry Context ====================

class TestBuildEntryContext:
    """Tests for build_entry_context."""

    def test_basic_fields(self, builder, entry_nov8):
        """Entry context includes date, summary, rating, word count."""
        ctx = builder.build_entry_context(entry_nov8)
        assert ctx["entry_date"] == date(2024, 11, 8)
        assert ctx["date_str"] == "2024-11-08"
        assert ctx["summary"] == "A day of encounters."
        assert ctx["rating"] == 4.0
        assert ctx["word_count"] == 1247

    def test_people_groups_excludes_narrator(
        self, builder, entry_nov8, narrator, clara
    ):
        """Narrator excluded from people groups."""
        ctx = builder.build_entry_context(entry_nov8)
        all_names = []
        for group in ctx["people_groups"]:
            all_names.extend(group["names"])
        assert "Clara Dupont" in all_names
        assert "Sofia Fernandez" not in all_names

    def test_people_grouped_by_relation(
        self, builder, entry_nov8, narrator, clara
    ):
        """People with relation_type are grouped correctly."""
        ctx = builder.build_entry_context(entry_nov8)
        groups = ctx["people_groups"]
        assert len(groups) >= 1
        romantic_group = next(
            (g for g in groups if g["relation"] == "Romantic"), None
        )
        assert romantic_group is not None
        assert "Clara Dupont" in romantic_group["names"]

    def test_places_structure(self, builder, entry_nov8, montreal, cafe, home):
        """Places nested by city with location names."""
        ctx = builder.build_entry_context(entry_nov8)
        places = ctx["places"]
        assert len(places) == 1
        assert places[0]["name"] == "Montreal"
        assert "Café Olimpico" in places[0]["locations"]
        assert "Home" in places[0]["locations"]

    def test_events_with_arc(
        self, builder, entry_nov8, event_long_nov, arc_wanting, scene_cafe
    ):
        """Events include arc name."""
        ctx = builder.build_entry_context(entry_nov8)
        events = ctx["events"]
        assert len(events) == 1
        assert events[0]["name"] == "The Long November"
        assert events[0]["arc"] == "The Long Wanting"

    def test_events_without_arc(self, builder, entry_nov8, scene_cafe):
        """Events without arc show None."""
        event = Event(name="Random Event")
        self.session = builder.session
        self.session.add(event)
        self.session.flush()
        event.entries.append(entry_nov8)
        event.scenes.append(scene_cafe)
        self.session.flush()

        ctx = builder.build_entry_context(entry_nov8)
        random_ev = next(
            (e for e in ctx["events"] if e["name"] == "Random Event"), None
        )
        assert random_ev is not None
        assert random_ev["arc"] is None

    def test_threads(self, builder, entry_nov8, thread_kiss, clara, cafe):
        """Threads include full display data."""
        ctx = builder.build_entry_context(entry_nov8)
        threads = ctx["threads"]
        assert len(threads) == 1
        t = threads[0]
        assert t["name"] == "The Bookend Kiss"
        assert t["from_date"] == "2024-11-08"
        assert t["to_date"] == "2024-12"
        assert t["referenced_entry_date"] == "2024-12-15"
        assert "Clara Dupont" in t["people"]

    def test_tags_and_themes(
        self, builder, entry_nov8, tag_loneliness, theme_identity
    ):
        """Tags and themes as simple name lists."""
        ctx = builder.build_entry_context(entry_nov8)
        assert "loneliness" in ctx["tags"]
        assert "identity" in ctx["themes"]

    def test_references(self, builder, entry_nov8, reference, ref_source):
        """References include source title and mode."""
        ctx = builder.build_entry_context(entry_nov8)
        refs = ctx["references"]
        assert len(refs) == 1
        assert refs[0]["source_title"] == "The Body Keeps the Score"
        assert refs[0]["mode"] == "direct"

    def test_poems(self, builder, entry_nov8, poem_version, poem):
        """Poems include title and version number."""
        ctx = builder.build_entry_context(entry_nov8)
        poems = ctx["poems"]
        assert len(poems) == 1
        assert poems[0]["title"] == "Untitled (November)"
        assert poems[0]["version"] == 1

    def test_scenes(self, builder, entry_nov8, scene_cafe, clara):
        """Entry context includes scenes with people, locations, dates."""
        ctx = builder.build_entry_context(entry_nov8)
        scenes = ctx["scenes"]
        assert len(scenes) == 1
        s = scenes[0]
        assert s["name"] == "Morning at the Cafe"
        assert s["description"] == "A conversation over espresso."
        assert "Clara Dupont" in s["people"]
        assert len(s["locations"]) == 1
        assert s["locations"][0]["city"] == "Montreal"
        assert "Café Olimpico" in s["locations"][0]["names"]
        assert len(s["dates"]) == 1

    def test_scenes_empty(self, builder, db_session):
        """Entry with no scenes has empty scenes list."""
        entry = Entry(
            date=date(2024, 1, 1),
            file_path="2024/2024-01-01.md",
        )
        db_session.add(entry)
        db_session.flush()
        ctx = builder.build_entry_context(entry)
        assert ctx["scenes"] == []

    def test_empty_entry(self, builder, db_session):
        """Entry with no relationships produces empty sections."""
        entry = Entry(
            date=date(2024, 1, 1),
            file_path="2024/2024-01-01.md",
        )
        db_session.add(entry)
        db_session.flush()

        ctx = builder.build_entry_context(entry)
        assert ctx["people_groups"] == []
        assert ctx["places"] == []
        assert ctx["events"] == []
        assert ctx["threads"] == []


# ==================== Person Context ====================

class TestBuildPersonContext:
    """Tests for build_person_context."""

    def test_narrator_tier(self, builder, narrator, entry_nov8):
        """Narrator gets narrator tier with aggregates."""
        ctx = builder.build_person_context(narrator)
        assert ctx["tier"] == "narrator"
        assert ctx["display_name"] == "Sofia Fernandez"
        assert "top_companions" in ctx
        assert "top_places" in ctx

    def test_infrequent_tier(self, builder, clara, entry_nov8):
        """Person with <20 entries gets infrequent tier."""
        ctx = builder.build_person_context(clara)
        assert ctx["tier"] == "infrequent"
        assert "entries" in ctx
        assert "places" in ctx

    def test_frequent_tier(self, builder, db_session, clara, montreal, cafe):
        """Person with 20+ entries gets frequent tier."""
        # Create 20 entries for Clara
        for i in range(20):
            entry = Entry(
                date=date(2024, 1, i + 1),
                file_path=f"2024/2024-01-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.people.append(clara)

            scene = Scene(
                name=f"Scene {i}",
                description=f"Scene description {i}",
                entry_id=entry.id,
            )
            db_session.add(scene)
            db_session.flush()
            scene.people.append(clara)
            scene.locations.append(cafe)
        db_session.flush()

        ctx = builder.build_person_context(clara)
        assert ctx["tier"] == "frequent"
        assert "arc_event_spine" in ctx
        assert "companions" in ctx
        assert ctx["entry_count"] >= 20

    def test_aliases(self, builder, db_session, clara, entry_nov8):
        """Person context includes aliases."""
        from dev.database.models.entities import PersonAlias
        alias = PersonAlias(person_id=clara.id, alias="Clarita")
        db_session.add(alias)
        db_session.flush()

        ctx = builder.build_person_context(clara)
        assert "aliases" in ctx
        assert "Clarita" in ctx["aliases"]

    def test_no_aliases(self, builder, clara, entry_nov8):
        """Person without aliases has empty aliases list."""
        ctx = builder.build_person_context(clara)
        assert ctx["aliases"] == []

    def test_character_mappings(self, builder, clara, entry_nov8):
        """Character mappings included when present."""
        ctx = builder.build_person_context(clara)
        assert "characters" in ctx
        assert isinstance(ctx["characters"], list)


# ==================== Location Context ====================

class TestBuildLocationContext:
    """Tests for build_location_context."""

    def test_minimal_tier(self, builder, cafe, entry_nov8):
        """Location with 1-2 entries gets minimal tier."""
        ctx = builder.build_location_context(cafe)
        assert ctx["tier"] == "minimal"
        assert ctx["name"] == "Café Olimpico"
        assert ctx["city"] == "Montreal"
        assert "entries" in ctx

    def test_mid_tier(self, builder, db_session, cafe, montreal):
        """Location with 3-19 entries gets mid tier."""
        for i in range(5):
            entry = Entry(
                date=date(2024, 2, i + 1),
                file_path=f"2024/2024-02-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.locations.append(cafe)
            entry.cities.append(montreal)
        db_session.flush()

        ctx = builder.build_location_context(cafe)
        assert ctx["tier"] == "mid"
        assert "events_here" in ctx
        assert "frequent_people" in ctx


# ==================== City Context ====================

class TestBuildCityContext:
    """Tests for build_city_context."""

    def test_basic_city(self, builder, montreal, entry_nov8):
        """City context includes basic fields."""
        ctx = builder.build_city_context(montreal)
        assert ctx["name"] == "Montreal"
        assert ctx["country"] == "Canada"
        assert ctx["entry_count"] >= 1


# ==================== Event Context ====================

class TestBuildEventContext:
    """Tests for build_event_context."""

    def test_event_with_scenes(
        self, builder, event_long_nov, scene_cafe, arc_wanting, entry_nov8
    ):
        """Event context includes scene details."""
        ctx = builder.build_event_context(event_long_nov)
        assert ctx["name"] == "The Long November"
        assert ctx["scene_count"] == 1
        assert len(ctx["scenes"]) == 1
        assert ctx["scenes"][0]["name"] == "Morning at the Cafe"


# ==================== Arc Context ====================

class TestBuildArcContext:
    """Tests for build_arc_context."""

    def test_arc_basic(
        self, builder, arc_wanting, entry_nov8, event_long_nov, scene_cafe
    ):
        """Arc context includes events and entries."""
        ctx = builder.build_arc_context(arc_wanting)
        assert ctx["name"] == "The Long Wanting"
        assert ctx["description"] == "A story of longing."
        assert ctx["entry_count"] == 1

    def test_arc_chapters(self, builder, db_session, arc_wanting, entry_nov8):
        """Arc context includes chapters linked via chapter_arcs."""
        from dev.database.models.manuscript import Chapter
        from dev.database.models.enums import ChapterType, ChapterStatus
        ch = Chapter(
            title="Wanting Chapter", number=1,
            type=ChapterType.PROSE, status=ChapterStatus.DRAFT,
        )
        db_session.add(ch)
        db_session.flush()
        ch.arcs.append(arc_wanting)
        db_session.flush()

        ctx = builder.build_arc_context(arc_wanting)
        assert len(ctx["chapters"]) == 1
        assert ctx["chapters"][0]["title"] == "Wanting Chapter"
        assert ctx["chapters"][0]["type"] == "Prose"

    def test_arc_no_chapters(self, builder, arc_wanting, entry_nov8):
        """Arc without chapters has empty chapters list."""
        ctx = builder.build_arc_context(arc_wanting)
        assert ctx["chapters"] == []


# ==================== Tag Context ====================

class TestBuildTagContext:
    """Tests for build_tag_context."""

    def test_minimal_tag(self, builder, tag_loneliness, entry_nov8):
        """Tag with few entries gets minimal tier."""
        ctx = builder.build_tag_context(tag_loneliness)
        assert ctx["name"] == "loneliness"
        assert ctx["tier"] == "minimal"
        assert ctx["entry_count"] == 1

    def test_dashboard_tag(self, builder, db_session, tag_loneliness):
        """Tag with 5+ entries gets dashboard tier."""
        for i in range(5):
            entry = Entry(
                date=date(2024, 3, i + 1),
                file_path=f"2024/2024-03-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.tags.append(tag_loneliness)
        db_session.flush()

        ctx = builder.build_tag_context(tag_loneliness)
        assert ctx["tier"] == "dashboard"
        assert "timeline" in ctx
        assert "patterns" in ctx


# ==================== Theme Context ====================

class TestBuildThemeContext:
    """Tests for build_theme_context."""

    def test_minimal_theme(self, builder, theme_identity, entry_nov8):
        """Theme with few entries gets minimal tier."""
        ctx = builder.build_theme_context(theme_identity)
        assert ctx["name"] == "identity"
        assert ctx["tier"] == "minimal"


# ==================== Poem Context ====================

class TestBuildPoemContext:
    """Tests for build_poem_context."""

    def test_poem_with_versions(self, builder, poem, poem_version, entry_nov8):
        """Poem context includes version details."""
        ctx = builder.build_poem_context(poem)
        assert ctx["title"] == "Untitled (November)"
        assert ctx["version_count"] == 1
        assert len(ctx["versions"]) == 1
        assert ctx["versions"][0]["number"] == 1
        assert ctx["versions"][0]["entry_date"] == "2024-11-08"

    def test_poem_chapters(self, builder, db_session, poem):
        """Poem context includes chapters linked via chapter_poems."""
        from dev.database.models.manuscript import Chapter
        from dev.database.models.enums import ChapterType, ChapterStatus
        ch = Chapter(
            title="Poem Chapter", number=2,
            type=ChapterType.POEM, status=ChapterStatus.DRAFT,
        )
        db_session.add(ch)
        db_session.flush()
        ch.poems.append(poem)
        db_session.flush()

        ctx = builder.build_poem_context(poem)
        assert len(ctx["chapters"]) == 1
        assert ctx["chapters"][0]["title"] == "Poem Chapter"

    def test_poem_no_chapters(self, builder, poem):
        """Poem without chapters has empty chapters list."""
        ctx = builder.build_poem_context(poem)
        assert ctx["chapters"] == []


# ==================== Reference Source Context ====================

class TestBuildReferenceSourceContext:
    """Tests for build_reference_source_context."""

    def test_source_with_refs(
        self, builder, ref_source, reference, entry_nov8
    ):
        """Reference source context includes chronological references."""
        ctx = builder.build_reference_source_context(ref_source)
        assert ctx["title"] == "The Body Keeps the Score"
        assert ctx["author"] == "van der Kolk"
        assert ctx["reference_count"] == 1
        assert len(ctx["references"]) == 1


# ==================== Motif Context ====================

class TestBuildMotifContext:
    """Tests for build_motif_context."""

    def test_motif_with_instances(
        self, builder, motif_loop, motif_instance, entry_nov8
    ):
        """Motif context includes instances and timeline."""
        ctx = builder.build_motif_context(motif_loop)
        assert ctx["name"] == "The Loop"
        assert ctx["instance_count"] == 1
        assert len(ctx["instances"]) == 1
        assert ctx["instances"][0]["description"].startswith("The recurring")


# ==================== Entry Listing Helper ====================

class TestBuildEntryListing:
    """Tests for _build_entry_listing helper."""

    def test_empty_entries(self, builder):
        """Empty list returns empty listing."""
        result = builder._build_entry_listing([])
        assert result == []

    def test_single_entry(self, builder, entry_nov8):
        """Single entry produces correct year/month structure."""
        result = builder._build_entry_listing([entry_nov8])
        assert len(result) == 1
        assert result[0]["year"] == 2024
        assert result[0]["count"] == 1

    def test_week_grouping(self, builder, db_session):
        """Months with 8+ entries get week grouping."""
        entries = []
        for i in range(10):
            entry = Entry(
                date=date(2024, 6, i + 1),
                file_path=f"2024/2024-06-{i+1:02d}.md",
            )
            db_session.add(entry)
            entries.append(entry)
        db_session.flush()

        result = builder._build_entry_listing(
            sorted(entries, key=lambda e: e.date, reverse=True)
        )
        assert len(result) == 1
        june = result[0]["months"][0]
        assert june["name"] == "June"
        assert "weeks" in june


# ==================== Slug and Metadata Keys ====================

class TestContextSlugs:
    """Tests for slug/metadata_id keys in context builders."""

    def test_arc_has_slug(self, builder, arc_wanting, entry_nov8):
        """Arc context includes slug."""
        ctx = builder.build_arc_context(arc_wanting)
        assert ctx["slug"] == "the-long-wanting"

    def test_arc_has_entries_subpage(self, builder, arc_wanting, entry_nov8):
        """Arc context always has has_entries_subpage."""
        ctx = builder.build_arc_context(arc_wanting)
        assert ctx["has_entries_subpage"] is True

    def test_location_has_metadata_id(self, builder, cafe, entry_nov8):
        """Location context includes metadata_id."""
        ctx = builder.build_location_context(cafe)
        assert ctx["metadata_id"] == "montreal/cafe-olimpico"

    def test_location_has_slug(self, builder, cafe, entry_nov8):
        """Location context includes slug (loc_slug only)."""
        ctx = builder.build_location_context(cafe)
        assert ctx["slug"] == "cafe-olimpico"

    def test_tag_has_slug(self, builder, tag_loneliness, entry_nov8):
        """Tag context includes slug."""
        ctx = builder.build_tag_context(tag_loneliness)
        assert ctx["slug"] == "loneliness"

    def test_theme_has_slug(self, builder, theme_identity, entry_nov8):
        """Theme context includes slug."""
        ctx = builder.build_theme_context(theme_identity)
        assert ctx["slug"] == "identity"

    def test_frequent_person_has_subpage(
        self, builder, db_session, clara, montreal, cafe
    ):
        """Frequent person gets has_entries_subpage flag."""
        for i in range(20):
            entry = Entry(
                date=date(2024, 1, i + 1),
                file_path=f"2024/2024-01-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.people.append(clara)
            scene = Scene(
                name=f"Scene {i}",
                description=f"Scene {i}",
                entry_id=entry.id,
            )
            db_session.add(scene)
            db_session.flush()
            scene.people.append(clara)
            scene.locations.append(cafe)
        db_session.flush()

        ctx = builder.build_person_context(clara)
        assert ctx["has_entries_subpage"] is True

    def test_infrequent_person_no_subpage(
        self, builder, clara, entry_nov8
    ):
        """Infrequent person has no has_entries_subpage."""
        ctx = builder.build_person_context(clara)
        assert "has_entries_subpage" not in ctx

    def test_dashboard_tag_has_subpage(
        self, builder, db_session, tag_loneliness
    ):
        """Dashboard tag gets has_entries_subpage flag."""
        for i in range(5):
            entry = Entry(
                date=date(2024, 3, i + 1),
                file_path=f"2024/2024-03-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.tags.append(tag_loneliness)
        db_session.flush()

        ctx = builder.build_tag_context(tag_loneliness)
        assert ctx["has_entries_subpage"] is True

    def test_dashboard_tag_has_recent_dates(
        self, builder, db_session, tag_loneliness
    ):
        """Dashboard tag context includes recent_dates (up to 5)."""
        for i in range(7):
            entry = Entry(
                date=date(2024, 3, i + 1),
                file_path=f"2024/2024-03-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.tags.append(tag_loneliness)
        db_session.flush()

        ctx = builder.build_tag_context(tag_loneliness)
        assert "recent_dates" in ctx
        assert len(ctx["recent_dates"]) == 5

    def test_minimal_tag_no_recent_dates(
        self, builder, db_session, tag_loneliness
    ):
        """Minimal tag has no recent_dates key."""
        for i in range(3):
            entry = Entry(
                date=date(2024, 3, i + 1),
                file_path=f"2024/2024-03-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.tags.append(tag_loneliness)
        db_session.flush()

        ctx = builder.build_tag_context(tag_loneliness)
        assert "recent_dates" not in ctx


# ==================== Part Context Enrichment ====================

class TestPartContext:
    """Tests for Part context builder enrichments."""

    def test_part_has_slug(self, builder, db_session):
        """Part context includes slug from title."""
        part = Part(number=1, title="The Beginning")
        db_session.add(part)
        db_session.flush()

        ctx = builder.build_part_context(part)
        assert ctx["slug"] == "the-beginning"

    def test_part_slug_fallback(self, builder, db_session):
        """Part without title uses part-N slug."""
        part = Part(number=3)
        db_session.add(part)
        db_session.flush()

        ctx = builder.build_part_context(part)
        assert ctx["slug"] == "part-3"

    def test_part_scene_count(self, builder, db_session):
        """Part context includes scene_count from chapters."""
        part = Part(number=1, title="First")
        db_session.add(part)
        db_session.flush()

        ctx = builder.build_part_context(part)
        assert "scene_count" in ctx
        assert ctx["scene_count"] == 0


# ==================== Standalone Rename ====================

class TestStandaloneRename:
    """Tests that 'Unlinked' is replaced with 'Standalone'."""

    def test_arc_event_spine_standalone(
        self, builder, db_session, clara, montreal, cafe
    ):
        """Unlinked events in arc_event_spine labeled 'Standalone events'."""
        # Create entries and events for clara without arcs
        for i in range(20):
            entry = Entry(
                date=date(2024, 1, i + 1),
                file_path=f"2024/2024-01-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.people.append(clara)
            scene = Scene(
                name=f"Scene {i}",
                description=f"Scene {i}",
                entry_id=entry.id,
            )
            db_session.add(scene)
            db_session.flush()
            scene.people.append(clara)
            scene.locations.append(cafe)

        # Add an event without arc on first entry
        event = Event(name="Orphan Event")
        db_session.add(event)
        db_session.flush()
        first_entry = db_session.query(Entry).filter(
            Entry.date == date(2024, 1, 1)
        ).first()
        event.entries.append(first_entry)
        first_scene = first_entry.scenes[0]
        event.scenes.append(first_scene)
        db_session.flush()

        ctx = builder.build_person_context(clara)
        spine = ctx["arc_event_spine"]
        standalone = [
            g for g in spine if g["name"] == "Standalone events"
        ]
        assert len(standalone) == 1
        unlinked = [g for g in spine if "Unlinked" in g["name"]]
        assert len(unlinked) == 0

    def test_location_events_standalone(
        self, builder, db_session, cafe, montreal
    ):
        """Location events use 'Standalone events' for arcless events."""
        # Create entries at location
        for i in range(3):
            entry = Entry(
                date=date(2024, 2, i + 1),
                file_path=f"2024/2024-02-{i+1:02d}.md",
            )
            db_session.add(entry)
            db_session.flush()
            entry.locations.append(cafe)
            entry.cities.append(montreal)
            scene = Scene(
                name=f"Loc Scene {i}",
                description=f"Location scene {i}",
                entry_id=entry.id,
            )
            db_session.add(scene)
            db_session.flush()
            scene.locations.append(cafe)

        # Add arcless event
        event = Event(name="Loc Event")
        db_session.add(event)
        db_session.flush()
        first_entry = db_session.query(Entry).filter(
            Entry.date == date(2024, 2, 1)
        ).first()
        event.entries.append(first_entry)
        event.scenes.append(first_entry.scenes[0])
        db_session.flush()

        ctx = builder.build_location_context(cafe)
        events_here = ctx.get("events_here", [])
        standalone = [
            g for g in events_here if g["name"] == "Standalone events"
        ]
        assert len(standalone) == 1


# ==================== Event Chronological Sorting ====================

class TestEventSorting:
    """Tests for chronological event sorting."""

    def test_arc_events_sorted(
        self, builder, db_session, arc_wanting
    ):
        """Events in arc context are sorted by earliest entry date."""
        # Add entries to arc
        entry_early = Entry(
            date=date(2024, 1, 1),
            file_path="2024/2024-01-01.md",
        )
        entry_late = Entry(
            date=date(2024, 6, 15),
            file_path="2024/2024-06-15.md",
        )
        db_session.add_all([entry_early, entry_late])
        db_session.flush()
        entry_early.arcs.append(arc_wanting)
        entry_late.arcs.append(arc_wanting)

        # Create scenes
        scene_early = Scene(
            name="Early scene", description="Early",
            entry_id=entry_early.id,
        )
        scene_late = Scene(
            name="Late scene", description="Late",
            entry_id=entry_late.id,
        )
        db_session.add_all([scene_early, scene_late])
        db_session.flush()

        # Events — late event created first to ensure sorting is not insertion order
        event_late = Event(name="Late Event")
        event_early = Event(name="Early Event")
        db_session.add_all([event_late, event_early])
        db_session.flush()
        event_late.entries.append(entry_late)
        event_late.scenes.append(scene_late)
        event_early.entries.append(entry_early)
        event_early.scenes.append(scene_early)
        db_session.flush()

        ctx = builder.build_arc_context(arc_wanting)
        events = ctx["events"]
        assert len(events) >= 2
        # Verify chronological order
        event_names = [e["name"] for e in events]
        assert event_names.index("Early Event") < event_names.index("Late Event")
