#!/usr/bin/env python3
"""
test_rename.py
--------------
Tests for the format-preserving entity rename engine.

Covers all rename scenarios including list merge/rename, no-op
detection, person structured merge, per-entity file operations,
curation slug handling, dry-run mode, city cascade, and format
preservation with ruamel.yaml round-trip.

Usage:
    python -m pytest tests/unit/wiki/test_rename.py -v
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from textwrap import dedent

# --- Third-party imports ---
import pytest
from ruamel.yaml import YAML

# --- Local imports ---
from dev.wiki.rename import EntityRenamer, RenameReport


# ==================== Fixtures ====================

@pytest.fixture
def yaml_rt():
    """Provide a ruamel.yaml round-trip instance for writing test files."""
    y = YAML()
    y.preserve_quotes = True
    return y


@pytest.fixture
def metadata_dir(tmp_path):
    """Create a temporary metadata directory structure."""
    md = tmp_path / "metadata"
    md.mkdir(exist_ok=True)
    return md


@pytest.fixture
def journal_dir(metadata_dir):
    """Create a temporary journal directory structure."""
    jd = metadata_dir / "journal" / "2022"
    jd.mkdir(parents=True)
    return jd.parent


@pytest.fixture
def renamer(metadata_dir, journal_dir):
    """Create an EntityRenamer instance with temp directories."""
    return EntityRenamer(
        metadata_dir=metadata_dir,
        journal_dir=journal_dir,
    )


def write_yaml(path: Path, content: str) -> None:
    """Write raw YAML string to a file, creating parent dirs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(content), encoding="utf-8")


def read_yaml(path: Path) -> dict:
    """Read a YAML file and return parsed data."""
    y = YAML()
    with open(path, encoding="utf-8") as f:
        return y.load(f)


# ==================== List Merge/Rename Tests ====================

class TestListMerge:
    """Tests for flat list merge/rename semantics."""

    def test_tag_rename_only_old_present(self, renamer, journal_dir):
        """When only old name exists in list, it is replaced."""
        entry_path = journal_dir / "2022" / "2022-01-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-01-01
            tags:
              - Depression
              - Self Image
              - Waiting
        """)

        report = renamer.rename("tag", "Self Image", "Self-Image", dry_run=False)

        data = read_yaml(entry_path)
        assert "Self-Image" in data["tags"]
        assert "Self Image" not in data["tags"]
        assert len(data["tags"]) == 3
        assert len(report.entry_changes) == 1
        assert report.entry_changes[0].action == "renamed"

    def test_tag_merge_both_present(self, renamer, journal_dir):
        """When both old and new exist in same list, old is removed."""
        entry_path = journal_dir / "2022" / "2022-01-02.yaml"
        write_yaml(entry_path, """\
            date: 2022-01-02
            tags:
              - Depression
              - Self Image
              - Self-Image
              - Waiting
        """)

        report = renamer.rename("tag", "Self Image", "Self-Image", dry_run=False)

        data = read_yaml(entry_path)
        assert data["tags"].count("Self-Image") == 1
        assert "Self Image" not in data["tags"]
        assert len(data["tags"]) == 3
        assert report.entry_changes[0].action == "merged"

    def test_no_op_name_absent(self, renamer, journal_dir):
        """When old name is absent, file is not changed."""
        entry_path = journal_dir / "2022" / "2022-01-03.yaml"
        write_yaml(entry_path, """\
            date: 2022-01-03
            tags:
              - Depression
              - Waiting
        """)

        report = renamer.rename("tag", "Self Image", "Self-Image", dry_run=False)

        assert len(report.entry_changes) == 0

    def test_theme_rename(self, renamer, journal_dir):
        """Theme rename works on themes list."""
        entry_path = journal_dir / "2022" / "2022-01-04.yaml"
        write_yaml(entry_path, """\
            date: 2022-01-04
            themes:
              - Loneliness
              - Desire
        """)

        report = renamer.rename(
            "theme", "Loneliness", "Solitude", dry_run=False
        )

        data = read_yaml(entry_path)
        assert "Solitude" in data["themes"]
        assert "Loneliness" not in data["themes"]

    def test_arc_rename_in_entry(self, renamer, journal_dir):
        """Arc rename works on arcs list in entry."""
        entry_path = journal_dir / "2022" / "2022-01-05.yaml"
        write_yaml(entry_path, """\
            date: 2022-01-05
            arcs:
              - The Long Wanting
              - The Therapy Journey
        """)

        report = renamer.rename(
            "arc", "The Long Wanting", "The Longing", dry_run=False
        )

        data = read_yaml(entry_path)
        assert "The Longing" in data["arcs"]
        assert "The Long Wanting" not in data["arcs"]


# ==================== Location Tests ====================

class TestLocationRename:
    """Tests for location rename across scenes and threads."""

    def test_location_rename_in_scene(self, renamer, journal_dir):
        """Location rename works in scenes[].locations."""
        entry_path = journal_dir / "2022" / "2022-02-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-02-01
            scenes:
              - name: Morning Walk
                locations:
                  - Home
                  - Park
              - name: Evening
                locations:
                  - Home
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["scenes"][0]["locations"] == [
            "Apartment - Jarry", "Park"
        ]
        assert data["scenes"][1]["locations"] == ["Apartment - Jarry"]
        assert len(report.entry_changes) == 1

    def test_location_merge_in_scene(self, renamer, journal_dir):
        """When both names exist in same scene, old is removed."""
        entry_path = journal_dir / "2022" / "2022-02-02.yaml"
        write_yaml(entry_path, """\
            date: 2022-02-02
            scenes:
              - name: Long Day
                locations:
                  - Home
                  - Apartment - Jarry
                  - Café
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["scenes"][0]["locations"] == [
            "Apartment - Jarry", "Café"
        ]

    def test_location_different_outcomes_per_scene(
        self, renamer, journal_dir
    ):
        """Same file can have rename in one scene and merge in another."""
        entry_path = journal_dir / "2022" / "2022-02-03.yaml"
        write_yaml(entry_path, """\
            date: 2022-02-03
            scenes:
              - name: Scene A
                locations:
                  - Home
              - name: Scene B
                locations:
                  - Home
                  - Apartment - Jarry
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["scenes"][0]["locations"] == ["Apartment - Jarry"]
        assert data["scenes"][1]["locations"] == ["Apartment - Jarry"]
        assert len(report.entry_changes) == 1

    def test_location_in_threads(self, renamer, journal_dir):
        """Location rename works in threads[].locations."""
        entry_path = journal_dir / "2022" / "2022-02-04.yaml"
        write_yaml(entry_path, """\
            date: 2022-02-04
            threads:
              - name: Thread One
                locations:
                  - Home
                  - Bar
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["threads"][0]["locations"] == [
            "Apartment - Jarry", "Bar"
        ]


# ==================== Person Tests ====================

class TestPersonRename:
    """Tests for person rename across structured and flat lists."""

    def test_person_rename_in_people_section(self, renamer, journal_dir):
        """Person rename updates people[].name field."""
        entry_path = journal_dir / "2022" / "2022-03-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-03-01
            people:
              - name: Kate
                disambiguator: The obsession
              - name: Johanna
                lastname: Ell
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["people"][0]["name"] == "Katherine"
        assert data["people"][0]["disambiguator"] == "The obsession"
        assert data["people"][1]["name"] == "Johanna"

    def test_person_merge_in_people_section(self, renamer, journal_dir):
        """When both people exist, old person dict is removed."""
        entry_path = journal_dir / "2022" / "2022-03-02.yaml"
        write_yaml(entry_path, """\
            date: 2022-03-02
            people:
              - name: Kate
                disambiguator: The obsession
              - name: Katherine
                lastname: Smith
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        data = read_yaml(entry_path)
        assert len(data["people"]) == 1
        assert data["people"][0]["name"] == "Katherine"

    def test_person_rename_in_scene_people(self, renamer, journal_dir):
        """Person rename in scenes[].people flat list."""
        entry_path = journal_dir / "2022" / "2022-03-03.yaml"
        write_yaml(entry_path, """\
            date: 2022-03-03
            people:
              - name: Kate
                disambiguator: The obsession
            scenes:
              - name: The Talk
                people:
                  - Kate
                  - Johanna
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["people"][0]["name"] == "Katherine"
        assert data["scenes"][0]["people"] == ["Katherine", "Johanna"]

    def test_person_rename_in_thread_people(self, renamer, journal_dir):
        """Person rename in threads[].people flat list."""
        entry_path = journal_dir / "2022" / "2022-03-04.yaml"
        write_yaml(entry_path, """\
            date: 2022-03-04
            threads:
              - name: Memory Thread
                people:
                  - Kate
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["threads"][0]["people"] == ["Katherine"]

    def test_person_all_three_updated_together(self, renamer, journal_dir):
        """People section, scene people, and thread people all updated."""
        entry_path = journal_dir / "2022" / "2022-03-05.yaml"
        write_yaml(entry_path, """\
            date: 2022-03-05
            people:
              - name: Kate
                disambiguator: The obsession
            scenes:
              - name: Scene One
                people:
                  - Kate
            threads:
              - name: Thread One
                people:
                  - Kate
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["people"][0]["name"] == "Katherine"
        assert data["scenes"][0]["people"] == ["Katherine"]
        assert data["threads"][0]["people"] == ["Katherine"]
        assert len(report.entry_changes) == 1


# ==================== Motif / Event Tests ====================

class TestMotifEventRename:
    """Tests for motif and event rename (nested name dicts)."""

    def test_motif_rename(self, renamer, journal_dir):
        """Motif rename updates motifs[].name."""
        entry_path = journal_dir / "2022" / "2022-04-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-04-01
            motifs:
              - name: The Mirror
                description: Self-reflection
              - name: The Door
                description: Opportunity
        """)

        report = renamer.rename(
            "motif", "The Mirror", "The Reflection", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["motifs"][0]["name"] == "The Reflection"
        assert data["motifs"][0]["description"] == "Self-reflection"

    def test_event_rename(self, renamer, journal_dir):
        """Event rename updates events[].name."""
        entry_path = journal_dir / "2022" / "2022-04-02.yaml"
        write_yaml(entry_path, """\
            date: 2022-04-02
            events:
              - name: The Breakup
                scenes:
                  - Scene One
        """)

        report = renamer.rename(
            "event", "The Breakup", "The Separation", dry_run=False
        )

        data = read_yaml(entry_path)
        assert data["events"][0]["name"] == "The Separation"
        assert data["events"][0]["scenes"] == ["Scene One"]

    def test_motif_merge(self, renamer, journal_dir):
        """When both motifs exist, old is removed."""
        entry_path = journal_dir / "2022" / "2022-04-03.yaml"
        write_yaml(entry_path, """\
            date: 2022-04-03
            motifs:
              - name: The Mirror
                description: Old desc
              - name: The Reflection
                description: New desc
        """)

        report = renamer.rename(
            "motif", "The Mirror", "The Reflection", dry_run=False
        )

        data = read_yaml(entry_path)
        assert len(data["motifs"]) == 1
        assert data["motifs"][0]["name"] == "The Reflection"


# ==================== Per-Entity File Tests ====================

class TestPerEntityFile:
    """Tests for per-entity YAML file rename/merge/delete."""

    def test_location_file_rename(self, renamer, metadata_dir):
        """When target file doesn't exist, old file is moved."""
        loc_dir = metadata_dir / "locations" / "montreal"
        loc_dir.mkdir(parents=True)
        write_yaml(loc_dir / "home.yaml", """\
            name: Home
            city: Montréal
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry",
            city="Montréal", dry_run=False,
        )

        assert not (loc_dir / "home.yaml").exists()
        new_path = loc_dir / "apartment-jarry.yaml"
        assert new_path.exists()
        data = read_yaml(new_path)
        assert data["name"] == "Apartment - Jarry"
        assert len(report.file_changes) == 1
        assert report.file_changes[0].action == "moved"

    def test_location_file_delete_on_merge(self, renamer, metadata_dir):
        """When target file exists, old file is deleted."""
        loc_dir = metadata_dir / "locations" / "montreal"
        loc_dir.mkdir(parents=True)
        write_yaml(loc_dir / "home.yaml", """\
            name: Home
            city: Montréal
        """)
        write_yaml(loc_dir / "apartment-jarry.yaml", """\
            name: Apartment - Jarry
            city: Montréal
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry",
            city="Montréal", dry_run=False,
        )

        assert not (loc_dir / "home.yaml").exists()
        assert (loc_dir / "apartment-jarry.yaml").exists()
        assert report.file_changes[0].action == "deleted"

    def test_location_file_auto_city_detection(self, renamer, metadata_dir):
        """When no city specified, finds file in any city subdir."""
        loc_dir = metadata_dir / "locations" / "montreal"
        loc_dir.mkdir(parents=True)
        write_yaml(loc_dir / "home.yaml", """\
            name: Home
            city: Montréal
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        assert not (loc_dir / "home.yaml").exists()
        assert (loc_dir / "apartment-jarry.yaml").exists()

    def test_person_file_rename(self, renamer, metadata_dir):
        """Person per-entity file is renamed with slug update."""
        people_dir = metadata_dir / "people"
        people_dir.mkdir(parents=True)
        write_yaml(people_dir / "kate.yaml", """\
            name: Kate
            slug: kate
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        assert not (people_dir / "kate.yaml").exists()
        new_path = people_dir / "katherine.yaml"
        assert new_path.exists()
        data = read_yaml(new_path)
        assert data["name"] == "Katherine"
        assert data["slug"] == "katherine"

    def test_person_file_merge(self, renamer, metadata_dir):
        """When target person file exists, old file is deleted."""
        people_dir = metadata_dir / "people"
        people_dir.mkdir(parents=True)
        write_yaml(people_dir / "kate.yaml", """\
            name: Kate
            slug: kate
        """)
        write_yaml(people_dir / "katherine.yaml", """\
            name: Katherine
            lastname: Smith
            slug: katherine
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        assert not (people_dir / "kate.yaml").exists()
        assert (people_dir / "katherine.yaml").exists()
        assert report.file_changes[0].action == "deleted"


# ==================== Arc File Tests ====================

class TestArcFile:
    """Tests for arc rename in arcs.yaml single file."""

    def test_arc_rename_in_arcs_yaml(self, renamer, metadata_dir):
        """Arc name is updated in arcs.yaml."""
        write_yaml(metadata_dir / "arcs.yaml", """\
            - name: The Long Wanting
              description: null
            - name: The Therapy Journey
              description: null
        """)

        report = renamer.rename(
            "arc", "The Long Wanting", "The Longing", dry_run=False
        )

        data = read_yaml(metadata_dir / "arcs.yaml")
        names = [a["name"] for a in data]
        assert "The Longing" in names
        assert "The Long Wanting" not in names
        assert report.file_changes[0].action == "updated"

    def test_arc_merge_in_arcs_yaml(self, renamer, metadata_dir):
        """When target arc exists, old arc entry is removed."""
        write_yaml(metadata_dir / "arcs.yaml", """\
            - name: The Long Wanting
              description: old desc
            - name: The Longing
              description: new desc
        """)

        report = renamer.rename(
            "arc", "The Long Wanting", "The Longing", dry_run=False
        )

        data = read_yaml(metadata_dir / "arcs.yaml")
        assert len(data) == 1
        assert data[0]["name"] == "The Longing"
        assert report.file_changes[0].action == "deleted"


# ==================== Curation File Tests ====================

class TestCurationFile:
    """Tests for curation YAML file slug key updates."""

    def test_neighborhoods_key_rename(self, renamer, metadata_dir):
        """Location slug key is renamed in neighborhoods.yaml."""
        write_yaml(metadata_dir / "neighborhoods.yaml", """\
            montreal:
              home: null
              park: Mile End
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry",
            city="Montréal", dry_run=False,
        )

        data = read_yaml(metadata_dir / "neighborhoods.yaml")
        assert "apartment-jarry" in data["montreal"]
        assert "home" not in data["montreal"]
        assert len(report.curation_changes) == 1
        assert report.curation_changes[0].action == "key_renamed"

    def test_neighborhoods_key_merge(self, renamer, metadata_dir):
        """When target slug exists, old slug is removed."""
        write_yaml(metadata_dir / "neighborhoods.yaml", """\
            montreal:
              home: Plateau
              apartment-jarry: null
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry",
            city="Montréal", dry_run=False,
        )

        data = read_yaml(metadata_dir / "neighborhoods.yaml")
        assert "home" not in data["montreal"]
        # Old value was "Plateau" and new was null, so new gets old value
        assert data["montreal"]["apartment-jarry"] == "Plateau"
        assert report.curation_changes[0].action == "key_merged"

    def test_neighborhoods_merge_keeps_new_value(self, renamer, metadata_dir):
        """When merging, new value is kept if it's not null."""
        write_yaml(metadata_dir / "neighborhoods.yaml", """\
            montreal:
              home: Plateau
              apartment-jarry: Villeray
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry",
            city="Montréal", dry_run=False,
        )

        data = read_yaml(metadata_dir / "neighborhoods.yaml")
        assert data["montreal"]["apartment-jarry"] == "Villeray"

    def test_relation_types_key_rename(self, renamer, metadata_dir):
        """Person slug key is renamed in relation_types.yaml."""
        write_yaml(metadata_dir / "relation_types.yaml", """\
            kate: romantic
            johanna: friend
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        data = read_yaml(metadata_dir / "relation_types.yaml")
        assert "katherine" in data
        assert "kate" not in data
        assert data["katherine"] == "romantic"

    def test_relation_types_key_merge(self, renamer, metadata_dir):
        """When target person slug exists, old slug is removed."""
        write_yaml(metadata_dir / "relation_types.yaml", """\
            kate: romantic
            katherine: null
        """)

        report = renamer.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        data = read_yaml(metadata_dir / "relation_types.yaml")
        assert "kate" not in data
        assert data["katherine"] == "romantic"


# ==================== Dry Run Tests ====================

class TestDryRun:
    """Tests for dry-run mode (no file modifications)."""

    def test_dry_run_no_entry_changes(self, renamer, journal_dir):
        """Dry-run generates report but doesn't modify entry files."""
        entry_path = journal_dir / "2022" / "2022-05-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-05-01
            tags:
              - Self Image
              - Depression
        """)
        original = entry_path.read_text(encoding="utf-8")

        report = renamer.rename("tag", "Self Image", "Self-Image", dry_run=True)

        assert len(report.entry_changes) == 1
        assert entry_path.read_text(encoding="utf-8") == original

    def test_dry_run_no_file_changes(self, renamer, metadata_dir):
        """Dry-run doesn't rename/delete per-entity files."""
        people_dir = metadata_dir / "people"
        people_dir.mkdir(parents=True)
        write_yaml(people_dir / "kate.yaml", """\
            name: Kate
            slug: kate
        """)

        report = renamer.rename("person", "Kate", "Katherine", dry_run=True)

        assert (people_dir / "kate.yaml").exists()
        assert not (people_dir / "katherine.yaml").exists()
        assert len(report.file_changes) == 1

    def test_dry_run_no_curation_changes(self, renamer, metadata_dir):
        """Dry-run doesn't modify curation files."""
        write_yaml(metadata_dir / "relation_types.yaml", """\
            kate: romantic
        """)
        original = (metadata_dir / "relation_types.yaml").read_text(
            encoding="utf-8"
        )

        report = renamer.rename("person", "Kate", "Katherine", dry_run=True)

        assert (metadata_dir / "relation_types.yaml").read_text(
            encoding="utf-8"
        ) == original
        assert len(report.curation_changes) == 1


# ==================== City Cascade Tests ====================

class TestCityCascade:
    """Tests for city rename cascading to downstream files."""

    def test_city_rename_in_cities_yaml(self, renamer, metadata_dir):
        """City name is updated in cities.yaml."""
        write_yaml(metadata_dir / "cities.yaml", """\
            - name: Montréal
              country: null
            - name: Tijuana
              country: null
        """)

        report = renamer.rename(
            "city", "Montréal", "Montreal", dry_run=False
        )

        data = read_yaml(metadata_dir / "cities.yaml")
        names = [c["name"] for c in data]
        assert "Montreal" in names
        assert "Montréal" not in names

    def test_city_rename_updates_location_yaml(self, renamer, metadata_dir):
        """Location YAML city fields are updated."""
        loc_dir = metadata_dir / "locations" / "montreal"
        loc_dir.mkdir(parents=True)
        write_yaml(loc_dir / "cafe.yaml", """\
            name: Café
            city: Montréal
        """)

        report = renamer.rename(
            "city", "Montréal", "Montreal", dry_run=False
        )

        # Slug doesn't change (montreal → montreal), so file stays put
        data = read_yaml(metadata_dir / "locations" / "montreal" / "cafe.yaml")
        assert data["city"] == "Montreal"

    def test_city_rename_directory(self, renamer, metadata_dir):
        """Location directory is renamed for new city slug."""
        old_dir = metadata_dir / "locations" / "montreal"
        old_dir.mkdir(parents=True)
        write_yaml(old_dir / "cafe.yaml", """\
            name: Café
            city: Montréal
        """)

        report = renamer.rename(
            "city", "Montréal", "Mtl", dry_run=False
        )

        assert not old_dir.exists()
        new_dir = metadata_dir / "locations" / "mtl"
        assert new_dir.exists()
        assert (new_dir / "cafe.yaml").exists()

    def test_city_rename_neighborhoods(self, renamer, metadata_dir):
        """neighborhoods.yaml section key is renamed."""
        write_yaml(metadata_dir / "neighborhoods.yaml", """\
            montreal:
              cafe: Plateau
            tijuana:
              bar: Centro
        """)

        report = renamer.rename(
            "city", "Montréal", "Mtl", dry_run=False
        )

        data = read_yaml(metadata_dir / "neighborhoods.yaml")
        assert "mtl" in data
        assert "montreal" not in data
        assert data["mtl"]["cafe"] == "Plateau"

    def test_city_rename_all_cascade(self, renamer, metadata_dir):
        """Full city rename cascades to all downstream files."""
        # cities.yaml
        write_yaml(metadata_dir / "cities.yaml", """\
            - name: Montréal
              country: Canada
        """)

        # Location files
        loc_dir = metadata_dir / "locations" / "montreal"
        loc_dir.mkdir(parents=True)
        write_yaml(loc_dir / "cafe.yaml", """\
            name: Café
            city: Montréal
        """)

        # neighborhoods.yaml
        write_yaml(metadata_dir / "neighborhoods.yaml", """\
            montreal:
              cafe: Plateau
        """)

        report = renamer.rename(
            "city", "Montréal", "Mtl", dry_run=False
        )

        # Verify all cascaded
        cities = read_yaml(metadata_dir / "cities.yaml")
        assert cities[0]["name"] == "Mtl"

        new_dir = metadata_dir / "locations" / "mtl"
        loc = read_yaml(new_dir / "cafe.yaml")
        assert loc["city"] == "Mtl"

        neighborhoods = read_yaml(metadata_dir / "neighborhoods.yaml")
        assert "mtl" in neighborhoods


# ==================== Format Preservation Tests ====================

class TestFormatPreservation:
    """Tests for YAML format preservation through round-trip."""

    def test_folded_strings_preserved(self, renamer, journal_dir):
        """
        Folded block strings (>-) survive round-trip.

        Entry YAMLs use >- for multi-line descriptions. ruamel.yaml
        must preserve this formatting.
        """
        entry_path = journal_dir / "2022" / "2022-06-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-06-01
            summary: >-
              A long summary that spans
              multiple lines and uses folded style.
            tags:
              - Self Image
              - Depression
        """)

        renamer.rename("tag", "Self Image", "Self-Image", dry_run=False)

        content = entry_path.read_text(encoding="utf-8")
        assert ">-" in content or ">" in content

    def test_quoted_strings_preserved(self, renamer, journal_dir):
        """Quoted strings in YAML survive round-trip."""
        entry_path = journal_dir / "2022" / "2022-06-02.yaml"
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        # Write raw content with explicit quoting
        entry_path.write_text(
            'date: 2022-06-02\n'
            'tags:\n'
            '  - "Self Image"\n'
            '  - Depression\n',
            encoding="utf-8",
        )

        renamer.rename("tag", "Self Image", "Self-Image", dry_run=False)

        content = entry_path.read_text(encoding="utf-8")
        data = read_yaml(entry_path)
        assert "Self-Image" in data["tags"]


# ==================== Validation Tests ====================

class TestValidation:
    """Tests for input validation."""

    def test_invalid_entity_type(self, renamer):
        """Unknown entity type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown entity type"):
            renamer.rename("invalid", "old", "new")

    def test_same_name_raises(self, renamer):
        """Identical old and new names raises ValueError."""
        with pytest.raises(ValueError, match="identical"):
            renamer.rename("tag", "Same", "Same")


# ==================== Report Tests ====================

class TestReport:
    """Tests for RenameReport summary output."""

    def test_empty_report_summary(self):
        """Report with no changes shows appropriate message."""
        report = RenameReport(
            entity_type="tag",
            old_name="old",
            new_name="new",
        )
        summary = report.summary()
        assert "No changes needed" in summary

    def test_report_summary_with_changes(self, renamer, journal_dir):
        """Report summary includes file counts and details."""
        entry_path = journal_dir / "2022" / "2022-07-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-07-01
            tags:
              - Self Image
        """)

        report = renamer.rename("tag", "Self Image", "Self-Image")
        summary = report.summary()

        assert "Self Image" in summary
        assert "Self-Image" in summary
        assert "Entry YAMLs" in summary
        assert "1 file(s) affected" in summary


# ==================== Multiple Files Tests ====================

class TestMultipleFiles:
    """Tests for operations across multiple entry files."""

    def test_rename_across_multiple_entries(self, renamer, journal_dir):
        """Rename applies to all matching entry files."""
        for day in ["01", "02", "03"]:
            path = journal_dir / "2022" / f"2022-08-{day}.yaml"
            write_yaml(path, f"""\
                date: 2022-08-{day}
                tags:
                  - Self Image
                  - Depression
            """)

        report = renamer.rename("tag", "Self Image", "Self-Image", dry_run=False)

        assert len(report.entry_changes) == 3
        for day in ["01", "02", "03"]:
            path = journal_dir / "2022" / f"2022-08-{day}.yaml"
            data = read_yaml(path)
            assert "Self-Image" in data["tags"]
            assert "Self Image" not in data["tags"]

    def test_mixed_rename_and_noop(self, renamer, journal_dir):
        """Only files containing the old name are reported."""
        path1 = journal_dir / "2022" / "2022-09-01.yaml"
        path2 = journal_dir / "2022" / "2022-09-02.yaml"
        write_yaml(path1, """\
            date: 2022-09-01
            tags:
              - Self Image
        """)
        write_yaml(path2, """\
            date: 2022-09-02
            tags:
              - Depression
        """)

        report = renamer.rename("tag", "Self Image", "Self-Image", dry_run=False)

        assert len(report.entry_changes) == 1


# ==================== MD Frontmatter Tests ====================

def write_md(path: Path, frontmatter: str, content: str = "") -> None:
    """Write an MD file with YAML frontmatter and content."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = content if content else "\nSome journal content here.\n"
    path.write_text(
        f"---\n{dedent(frontmatter)}---{body}",
        encoding="utf-8",
    )


@pytest.fixture
def md_dir(tmp_path):
    """Create a temporary MD directory with year subdirectories."""
    md = tmp_path / "md"
    (md / "2022").mkdir(parents=True)
    (md / "2024").mkdir(parents=True)
    return md


@pytest.fixture
def renamer_with_md(metadata_dir, journal_dir, md_dir):
    """Create an EntityRenamer with md_dir set."""
    return EntityRenamer(
        metadata_dir=metadata_dir,
        journal_dir=journal_dir,
        md_dir=md_dir,
    )


class TestMdFrontmatterLocation:
    """Tests for location rename in MD frontmatter."""

    def test_location_rename_in_frontmatter(self, renamer_with_md, md_dir):
        """Location name is updated in frontmatter locations dict."""
        md_path = md_dir / "2022" / "2022-01-01.md"
        write_md(md_path, """\
            date: 2022-01-01
            word_count: 500
            locations:
              Montréal:
              - Home
              - Café
        """)

        report = renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        assert "Apartment - Jarry" in data["locations"]["Montréal"]
        assert "Home" not in data["locations"]["Montréal"]
        assert len(report.md_changes) == 1
        assert report.md_changes[0].action == "renamed"

    def test_location_merge_in_frontmatter(self, renamer_with_md, md_dir):
        """When both old and new location exist, old is removed."""
        md_path = md_dir / "2022" / "2022-01-02.md"
        write_md(md_path, """\
            date: 2022-01-02
            word_count: 500
            locations:
              Montréal:
              - Home
              - Apartment - Jarry
              - Café
        """)

        report = renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        locs = data["locations"]["Montréal"]
        assert locs.count("Apartment - Jarry") == 1
        assert "Home" not in locs
        assert len(locs) == 2
        assert report.md_changes[0].action == "merged"

    def test_location_multi_city(self, renamer_with_md, md_dir):
        """Rename works across multiple city sections."""
        md_path = md_dir / "2024" / "2024-06-15.md"
        write_md(md_path, """\
            date: 2024-06-15
            word_count: 800
            locations:
              Montréal:
              - Home
              - Bar
              Tijuana:
              - Home
              - Beach
        """)

        report = renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        assert "Apartment - Jarry" in data["locations"]["Montréal"]
        assert "Apartment - Jarry" in data["locations"]["Tijuana"]
        assert len(report.md_changes) == 1


class TestMdFrontmatterSubstring:
    """Tests for substring safety in MD frontmatter renames."""

    def test_rename_no_substring_match_block(self, renamer_with_md, md_dir):
        """Rename 'Home' must not match inside 'Bar Home' (block style)."""
        md_path = md_dir / "2022" / "2022-01-10.md"
        write_md(md_path, """\
            date: 2022-01-10
            word_count: 500
            locations:
              Montréal:
              - Bar Home
              - Home
        """)

        renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        locs = data["locations"]["Montréal"]
        assert "Bar Home" in locs
        assert "Apartment - Jarry" in locs
        assert "Home" not in locs

    def test_rename_no_substring_match_flow(self, renamer_with_md, md_dir):
        """Rename 'Home' must not match inside 'Bar Home' (flow style)."""
        md_path = md_dir / "2022" / "2022-01-11.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(
            "---\ndate: 2022-01-11\nword_count: 500\n"
            "locations:\n"
            "  Montréal: [Bar Home, Home, Café]\n"
            "---\n\nContent.\n",
            encoding="utf-8",
        )

        renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        locs = data["locations"]["Montréal"]
        assert "Bar Home" in locs
        assert "Apartment - Jarry" in locs
        assert "Home" not in locs

    def test_merge_no_substring_match_flow(self, renamer_with_md, md_dir):
        """Merge 'Darling' must not affect 'Bar Darling' (flow style)."""
        md_path = md_dir / "2022" / "2022-01-12.md"
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(
            "---\ndate: 2022-01-12\nword_count: 500\n"
            "locations:\n"
            "  Montréal: [Bar Darling, Darling, Home]\n"
            "---\n\nContent.\n",
            encoding="utf-8",
        )

        renamer_with_md.rename(
            "location", "Darling", "Bar Darling", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        locs = data["locations"]["Montréal"]
        assert "Bar Darling" in locs
        assert "Darling" not in locs
        assert "Home" in locs


class TestMdFrontmatterPerson:
    """Tests for person rename in MD frontmatter."""

    def test_person_rename_in_frontmatter(self, renamer_with_md, md_dir):
        """Person name is updated in frontmatter people list."""
        md_path = md_dir / "2022" / "2022-02-01.md"
        write_md(md_path, """\
            date: 2022-02-01
            word_count: 500
            people:
            - Kate
            - Johanna
        """)

        report = renamer_with_md.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        assert "Katherine" in data["people"]
        assert "Kate" not in data["people"]
        assert len(report.md_changes) == 1

    def test_person_merge_in_frontmatter(self, renamer_with_md, md_dir):
        """When both old and new person exist, old is removed."""
        md_path = md_dir / "2022" / "2022-02-02.md"
        write_md(md_path, """\
            date: 2022-02-02
            word_count: 500
            people: [Kate, Katherine, Johanna]
        """)

        report = renamer_with_md.rename(
            "person", "Kate", "Katherine", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        parts = raw.split("---", 2)
        y = YAML()
        data = y.load(parts[1])
        assert data["people"].count("Katherine") == 1
        assert "Kate" not in data["people"]


class TestMdFrontmatterContentPreservation:
    """Tests ensuring markdown content is never modified."""

    def test_content_preserved_byte_for_byte(self, renamer_with_md, md_dir):
        """Markdown content below frontmatter is preserved exactly."""
        content_text = (
            "\n# My Journal Entry\n\n"
            "Today I went to **Home** and had coffee.\n\n"
            "- Item 1\n- Item 2\n\n"
            "## Special chars: àéîöü — «quotes» & ampersands\n"
        )
        md_path = md_dir / "2022" / "2022-03-01.md"
        write_md(md_path, """\
            date: 2022-03-01
            word_count: 500
            locations:
              Montréal:
              - Home
        """, content=content_text)

        renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        raw = md_path.read_text(encoding="utf-8")
        # Content after second --- must be preserved exactly
        parts = raw.split("---", 2)
        assert parts[2] == content_text

    def test_tag_rename_no_md_changes(self, renamer_with_md, md_dir):
        """Entity types without MD frontmatter field produce no MD changes."""
        md_path = md_dir / "2022" / "2022-03-02.md"
        write_md(md_path, """\
            date: 2022-03-02
            word_count: 500
            people: [Kate]
        """)
        original = md_path.read_text(encoding="utf-8")

        report = renamer_with_md.rename(
            "tag", "Self Image", "Self-Image", dry_run=False
        )

        assert len(report.md_changes) == 0
        assert md_path.read_text(encoding="utf-8") == original


class TestMdFrontmatterDateFilter:
    """Tests for pre-2020 file filtering."""

    def test_pre2020_files_skipped(self, renamer_with_md, md_dir):
        """Files in year directories before 2020 are not processed."""
        pre2020_dir = md_dir / "2019"
        pre2020_dir.mkdir()
        md_path = pre2020_dir / "2019-06-15.md"
        write_md(md_path, """\
            date: 2019-06-15
            word_count: 500
            locations:
              Montréal:
              - Home
        """)
        original = md_path.read_text(encoding="utf-8")

        report = renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        assert len(report.md_changes) == 0
        assert md_path.read_text(encoding="utf-8") == original

    def test_2020_files_processed(self, renamer_with_md, md_dir):
        """Files in 2020 directory ARE processed."""
        y2020_dir = md_dir / "2020"
        y2020_dir.mkdir()
        md_path = y2020_dir / "2020-01-15.md"
        write_md(md_path, """\
            date: 2020-01-15
            word_count: 500
            locations:
              Montréal:
              - Home
        """)

        report = renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        assert len(report.md_changes) == 1


class TestMdFrontmatterDryRun:
    """Tests for dry-run mode with MD frontmatter."""

    def test_dry_run_no_md_changes(self, renamer_with_md, md_dir):
        """Dry-run reports MD changes but doesn't modify files."""
        md_path = md_dir / "2022" / "2022-04-01.md"
        write_md(md_path, """\
            date: 2022-04-01
            word_count: 500
            locations:
              Montréal:
              - Home
        """)
        original = md_path.read_text(encoding="utf-8")

        report = renamer_with_md.rename(
            "location", "Home", "Apartment - Jarry", dry_run=True
        )

        assert len(report.md_changes) == 1
        assert md_path.read_text(encoding="utf-8") == original


class TestMdFrontmatterNoMdDir:
    """Tests for renamer without md_dir (backward compatibility)."""

    def test_no_md_dir_no_md_changes(self, renamer, journal_dir):
        """When md_dir is None, no MD changes are produced."""
        entry_path = journal_dir / "2022" / "2022-05-01.yaml"
        write_yaml(entry_path, """\
            date: 2022-05-01
            scenes:
              - name: Morning
                locations:
                  - Home
        """)

        report = renamer.rename(
            "location", "Home", "Apartment - Jarry", dry_run=False
        )

        assert len(report.md_changes) == 0
        assert len(report.entry_changes) == 1
