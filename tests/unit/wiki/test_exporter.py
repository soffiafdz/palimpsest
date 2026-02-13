#!/usr/bin/env python3
"""
test_exporter.py
----------------
Tests for WikiExporter orchestration.

Integration tests that verify the exporter generates files
correctly using actual DB fixtures and templates.
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
from dev.database.models.entities import Person, Tag, Theme
from dev.database.models.enums import RelationType
from dev.database.models.geography import City, Location
from dev.database.models.metadata import Motif, MotifInstance
from dev.wiki.exporter import WikiExporter


# ==================== Fixtures ====================

@pytest.fixture
def wiki_output(tmp_path):
    """Temporary wiki output directory."""
    return tmp_path / "wiki"


@pytest.fixture
def populated_db(db_session):
    """
    Create a minimal but complete set of test entities.

    Returns the session with entities already flushed.
    """
    # City + Locations
    city = City(name="Montreal", country="Canada")
    db_session.add(city)
    db_session.flush()

    cafe = Location(name="Café Olimpico", city_id=city.id)
    home = Location(name="Home", city_id=city.id)
    db_session.add_all([cafe, home])
    db_session.flush()

    # People
    narrator = Person(
        name="Sofia", lastname="Fernandez",
        slug="sofia_fernandez", relation_type=RelationType.SELF,
    )
    clara = Person(
        name="Clara", lastname="Dupont",
        slug="clara_dupont", relation_type=RelationType.ROMANTIC,
    )
    db_session.add_all([narrator, clara])
    db_session.flush()

    # Entry
    entry = Entry(
        date=date(2024, 11, 8),
        file_path="2024/2024-11-08.md",
        word_count=1247,
        reading_time=6.2,
        summary="A day of encounters.",
        rating=4.0,
        rating_justification="Rich narrative detail.",
    )
    db_session.add(entry)
    db_session.flush()

    entry.people.extend([narrator, clara])
    entry.locations.extend([cafe, home])
    entry.cities.append(city)

    # Second entry for tag page generation
    entry2 = Entry(
        date=date(2024, 11, 9),
        file_path="2024/2024-11-09.md",
        word_count=800,
    )
    db_session.add(entry2)
    db_session.flush()

    # Tags (need 2+ entries for page generation)
    tag = Tag(name="loneliness")
    db_session.add(tag)
    db_session.flush()
    entry.tags.append(tag)
    entry2.tags.append(tag)

    # Theme
    theme = Theme(name="identity")
    db_session.add(theme)
    db_session.flush()
    entry.themes.append(theme)
    entry2.themes.append(theme)

    # Scene
    scene = Scene(
        name="Morning at the Cafe",
        description="A conversation over espresso.",
        entry_id=entry.id,
    )
    db_session.add(scene)
    db_session.flush()
    scene.people.append(clara)
    scene.locations.append(cafe)
    sd = SceneDate(date="2024-11-08", scene_id=scene.id)
    db_session.add(sd)

    # Arc
    arc = Arc(name="The Long Wanting", description="A story of longing.")
    db_session.add(arc)
    db_session.flush()
    entry.arcs.append(arc)

    # Event
    event = Event(name="The Long November")
    db_session.add(event)
    db_session.flush()
    event.entries.append(entry)
    event.scenes.append(scene)

    # Motif
    motif = Motif(name="The Loop")
    db_session.add(motif)
    db_session.flush()
    mi = MotifInstance(
        description="The recurring phone check.",
        motif_id=motif.id, entry_id=entry.id,
    )
    db_session.add(mi)

    db_session.commit()
    return db_session


# ==================== Exporter Tests ====================

class TestWikiExporterInit:
    """Tests for WikiExporter initialization."""

    def test_default_output_dir(self, test_db):
        """Default output dir is data/wiki."""
        exporter = WikiExporter(test_db)
        assert "wiki" in str(exporter.output_dir)

    def test_custom_output_dir(self, test_db, tmp_path):
        """Custom output dir is respected."""
        custom = tmp_path / "custom_wiki"
        exporter = WikiExporter(test_db, output_dir=custom)
        assert exporter.output_dir == custom


class TestWikiExporterGeneration:
    """Integration tests for wiki page generation."""

    def test_generate_creates_entry_pages(
        self, test_db, populated_db, wiki_output
    ):
        """generate_all creates entry wiki pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        # Check entry page exists
        entry_page = (
            wiki_output / "journal" / "entries" / "2024" / "2024-11-08.md"
        )
        assert entry_page.exists()
        content = entry_page.read_text()
        assert "November 8, 2024" in content

    def test_generate_creates_rating_subpage(
        self, test_db, populated_db, wiki_output
    ):
        """Entries with rating_justification get subpages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        rating_page = (
            wiki_output / "journal" / "entries" / "2024"
            / "2024-11-08-rating.md"
        )
        assert rating_page.exists()
        content = rating_page.read_text()
        assert "Rich narrative detail" in content

    def test_generate_creates_person_pages(
        self, test_db, populated_db, wiki_output
    ):
        """generate_all creates person wiki pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        person_page = (
            wiki_output / "journal" / "people" / "clara_dupont.md"
        )
        assert person_page.exists()

    def test_generate_creates_location_pages(
        self, test_db, populated_db, wiki_output
    ):
        """generate_all creates location wiki pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        loc_page = (
            wiki_output / "journal" / "locations" / "montreal"
            / "cafe-olimpico.md"
        )
        assert loc_page.exists()

    def test_generate_creates_tag_pages(
        self, test_db, populated_db, wiki_output
    ):
        """Tags with 2+ entries get pages."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        tag_page = wiki_output / "journal" / "tags" / "loneliness.md"
        assert tag_page.exists()

    def test_generate_type_filter(
        self, test_db, populated_db, wiki_output
    ):
        """entity_type filter generates only that type."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal", entity_type="people")

        # People pages should exist
        person_page = (
            wiki_output / "journal" / "people" / "clara_dupont.md"
        )
        assert person_page.exists()

        # But not tag pages (different type)
        tag_page = wiki_output / "journal" / "tags" / "loneliness.md"
        assert not tag_page.exists()

    def test_generate_stats(self, test_db, populated_db, wiki_output):
        """Stats are tracked during generation."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        assert "entries" in exporter.stats
        assert exporter.stats["entries"] >= 1

    def test_change_detection(self, test_db, populated_db, wiki_output):
        """Second generation reports no changes for unchanged content."""
        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all(section="journal")

        # Second run
        exporter2 = WikiExporter(test_db, output_dir=wiki_output)
        exporter2.generate_all(section="journal")

        # Changed count should be 0 on second run
        assert exporter2.stats.get("entries_changed", 0) == 0


class TestWikiExporterCleanup:
    """Tests for orphan file cleanup."""

    def test_orphan_removal(self, test_db, populated_db, wiki_output):
        """Orphaned .md files are removed during generation."""
        # Create an orphan file
        orphan = wiki_output / "journal" / "people" / "ghost.md"
        orphan.parent.mkdir(parents=True, exist_ok=True)
        orphan.write_text("ghost page")

        exporter = WikiExporter(test_db, output_dir=wiki_output)
        exporter.generate_all()

        assert not orphan.exists()
        assert exporter.stats.get("orphans_removed", 0) >= 1


class TestWikiExporterIndexes:
    """Tests for index context builders."""

    def test_main_index_context(self, test_db, populated_db):
        """Main index context includes entity counts."""
        exporter = WikiExporter(test_db)
        with test_db.session_scope() as session:
            ctx = exporter._build_main_index_context(session)
            assert ctx["entry_count"] >= 1
            assert ctx["person_count"] >= 1

    def test_people_index_context(self, test_db, populated_db):
        """People index groups by relation type."""
        exporter = WikiExporter(test_db)
        with test_db.session_scope() as session:
            ctx = exporter._build_people_index_context(session)
            assert "groups" in ctx
            assert "total" in ctx

    def test_tags_themes_index_context(self, test_db, populated_db):
        """Tags & themes index includes frequency-sorted lists."""
        exporter = WikiExporter(test_db)
        with test_db.session_scope() as session:
            ctx = exporter._build_tags_themes_index_context(session)
            assert "tags" in ctx
            assert "themes" in ctx
