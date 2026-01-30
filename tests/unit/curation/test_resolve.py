#!/usr/bin/env python3
"""
test_resolve.py
---------------
Unit tests for dev.curation.resolve module.

Tests the EntityResolver class for loading curation files and resolving
raw entity names to canonical database representations. Covers:
- Loading per-year curation files
- Person resolution (single and multi-person)
- Location resolution
- City creation
- Caching behavior
- same_as chain resolution

Target Coverage: 95%+
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from pathlib import Path
from typing import Any, Dict

# --- Third-party imports ---
import pytest
import yaml

# --- Local imports ---
from dev.curation.resolve import EntityResolver
from dev.database.models import City, Location, Person, PersonAlias


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def curation_dir(tmp_dir):
    """Create temporary curation directory."""
    curation_dir = tmp_dir / "curation"
    curation_dir.mkdir(parents=True, exist_ok=True)
    return curation_dir


def create_people_file(curation_dir: Path, year: str, data: Dict[str, Any]) -> Path:
    """Helper to create a people curation file."""
    file_path = curation_dir / f"{year}_people_curation.yaml"
    file_path.write_text(yaml.dump(data))
    return file_path


def create_locations_file(curation_dir: Path, year: str, data: Dict[str, Any]) -> Path:
    """Helper to create a locations curation file."""
    file_path = curation_dir / f"{year}_locations_curation.yaml"
    file_path.write_text(yaml.dump(data))
    return file_path


# =============================================================================
# EntityResolver.load() Tests
# =============================================================================

class TestEntityResolverLoad:
    """Test EntityResolver.load() class method."""

    def test_load_missing_people_files(self, curation_dir, monkeypatch):
        """Test loading fails when no people curation files exist."""
        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        with pytest.raises(FileNotFoundError) as exc_info:
            EntityResolver.load()

        assert "No people curation files found" in str(exc_info.value)

    def test_load_malformed_people_entry_not_dict(self, curation_dir, monkeypatch):
        """Test that non-dict entries in people curation are skipped."""
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None}
            },
            "Invalid": "not a dict"  # Should be skipped
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Should only have Alice
        assert "alice" in resolver.people_map
        assert "invalid" not in resolver.people_map

    def test_load_malformed_location_city_not_dict(self, curation_dir, monkeypatch):
        """Test that non-dict city entries in locations curation are skipped."""
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop"}
            },
            "InvalidCity": "not a dict"  # Should be skipped
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Should only have Montreal locations
        assert "cafe" in resolver.locations_map
        assert len(resolver.locations_map) == 1

    def test_load_malformed_location_entry_not_dict(self, curation_dir, monkeypatch):
        """Test that non-dict location entries are skipped."""
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop"},
                "Invalid": "not a dict"  # Should be skipped
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Should only have Cafe
        assert "cafe" in resolver.locations_map
        assert "invalid" not in resolver.locations_map

    def test_load_missing_locations_files(self, curation_dir, monkeypatch):
        """Test loading fails when no locations curation files exist."""
        # Create people file but no locations file
        create_people_file(curation_dir, "2024", {
            "Alice": {"canonical": {"name": "Alice", "lastname": None, "alias": None}}
        })

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        with pytest.raises(FileNotFoundError) as exc_info:
            EntityResolver.load()

        assert "No locations curation files found" in str(exc_info.value)

    def test_load_single_year_people(self, curation_dir, monkeypatch):
        """Test loading single year people curation file."""
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": "Al"},
                "dates": ["2024-01-15"]
            },
            "Bob": {
                "canonical": {"name": None, "lastname": None, "alias": None},
                "dates": ["2024-01-16"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Check people map
        assert "alice" in resolver.people_map
        assert "bob" in resolver.people_map
        assert resolver.people_map["alice"][0]["name"] == "Alice"
        assert resolver.people_map["alice"][0]["lastname"] == "Smith"
        assert resolver.people_map["alice"][0]["alias"] == "Al"
        # All-null convention: name defaults to raw key
        assert resolver.people_map["bob"][0]["name"] == "Bob"

    def test_load_multiple_years_people(self, curation_dir, monkeypatch):
        """Test loading multiple years of people curation files."""
        people_2023 = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                "dates": ["2023-01-15"]
            }
        }
        people_2024 = {
            "Bob": {
                "canonical": {"name": "Bob", "lastname": None, "alias": None},
                "dates": ["2024-01-15"]
            }
        }
        create_people_file(curation_dir, "2023", people_2023)
        create_people_file(curation_dir, "2024", people_2024)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "alice" in resolver.people_map
        assert "bob" in resolver.people_map

    def test_load_skip_entries(self, curation_dir, monkeypatch):
        """Test that skip entries are excluded."""
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": ["2024-01-15"]
            },
            "Spammer": {
                "skip": True,
                "dates": ["2024-01-15"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "alice" in resolver.people_map
        assert "spammer" not in resolver.people_map

    def test_load_self_entries(self, curation_dir, monkeypatch):
        """Test that self entries are excluded."""
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None},
                "dates": ["2024-01-15"]
            },
            "Sofia": {
                "self": True,
                "dates": ["2024-01-15"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "alice" in resolver.people_map
        assert "sofia" not in resolver.people_map

    def test_load_same_as_simple(self, curation_dir, monkeypatch):
        """Test simple same_as reference resolution."""
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                "dates": ["2024-01-15"]
            },
            "Alicia": {
                "same_as": "Alice",
                "dates": ["2024-01-16"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Both should resolve to same canonical
        assert "alice" in resolver.people_map
        assert "alicia" in resolver.people_map
        assert resolver.people_map["alice"][0]["name"] == "Alice"
        assert resolver.people_map["alicia"][0]["name"] == "Alice"
        assert resolver.people_map["alice"] == resolver.people_map["alicia"]

    def test_load_same_as_chain(self, curation_dir, monkeypatch):
        """Test same_as chain resolution (A -> B -> C)."""
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                "dates": ["2024-01-15"]
            },
            "Alicia": {
                "same_as": "Alice",
                "dates": ["2024-01-16"]
            },
            "Ali": {
                "same_as": "Alicia",
                "dates": ["2024-01-17"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # All should resolve to Alice's canonical
        assert resolver.people_map["alice"][0]["name"] == "Alice"
        assert resolver.people_map["alicia"][0]["name"] == "Alice"
        assert resolver.people_map["ali"][0]["name"] == "Alice"

    def test_load_same_as_circular(self, curation_dir, monkeypatch):
        """Test circular same_as reference is handled."""
        people_data = {
            "Alice": {"same_as": "Bob"},
            "Bob": {"same_as": "Charlie"},
            "Charlie": {"same_as": "Alice"}
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Circular references should not be in the map
        assert "alice" not in resolver.people_map
        assert "bob" not in resolver.people_map
        assert "charlie" not in resolver.people_map

    def test_load_multi_person_entry(self, curation_dir, monkeypatch):
        """Test multi-person entry (list of canonicals)."""
        people_data = {
            "Parents": {
                "canonical": [
                    {"name": "Mom", "lastname": None, "alias": None},
                    {"name": "Dad", "lastname": None, "alias": None}
                ],
                "dates": ["2024-01-15"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "parents" in resolver.people_map
        assert len(resolver.people_map["parents"]) == 2
        assert resolver.people_map["parents"][0]["name"] == "Mom"
        assert resolver.people_map["parents"][1]["name"] == "Dad"

    def test_load_multi_person_invalid_entries(self, curation_dir, monkeypatch):
        """Test multi-person entry with invalid elements are filtered."""
        people_data = {
            "Parents": {
                "canonical": [
                    {"name": "Mom", "lastname": None, "alias": None},
                    "not a dict",  # Invalid
                    {"lastname": "Smith"},  # Missing name
                    {"name": "Dad", "lastname": None, "alias": None}
                ],
                "dates": ["2024-01-15"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Should only include valid entries with names
        assert "parents" in resolver.people_map
        assert len(resolver.people_map["parents"]) == 2
        assert resolver.people_map["parents"][0]["name"] == "Mom"
        assert resolver.people_map["parents"][1]["name"] == "Dad"

    def test_load_single_year_locations(self, curation_dir, monkeypatch):
        """Test loading single year locations curation file."""
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                "Home": {"canonical": None, "dates": ["2024-01-16"]}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "cafe" in resolver.locations_map
        assert resolver.locations_map["cafe"]["name"] == "Coffee Shop"
        assert resolver.locations_map["cafe"]["city"] == "Montreal"
        # canonical: null convention -> canonical = raw key
        assert resolver.locations_map["home"]["name"] == "Home"
        assert resolver.locations_map["home"]["city"] == "Montreal"

    def test_load_multiple_years_locations(self, curation_dir, monkeypatch):
        """Test loading multiple years of locations curation files."""
        locations_2023 = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2023-01-15"]}
            }
        }
        locations_2024 = {
            "Toronto": {
                "Library": {"canonical": None, "dates": ["2024-01-15"]}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2023", locations_2023)
        create_locations_file(curation_dir, "2024", locations_2024)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "cafe" in resolver.locations_map
        assert resolver.locations_map["cafe"]["city"] == "Montreal"
        assert "library" in resolver.locations_map
        assert resolver.locations_map["library"]["city"] == "Toronto"

    def test_load_locations_skip_entries(self, curation_dir, monkeypatch):
        """Test that skip location entries are excluded."""
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                "Generic": {"skip": True, "dates": ["2024-01-15"]}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "cafe" in resolver.locations_map
        assert "generic" not in resolver.locations_map

    def test_load_locations_same_as_simple(self, curation_dir, monkeypatch):
        """Test simple same_as reference for locations."""
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                "Coffee": {"same_as": "Cafe", "dates": ["2024-01-16"]}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Both should resolve to same canonical
        assert "cafe" in resolver.locations_map
        assert "coffee" in resolver.locations_map
        assert resolver.locations_map["cafe"]["name"] == "Coffee Shop"
        assert resolver.locations_map["coffee"]["name"] == "Coffee Shop"

    def test_load_locations_same_as_chain(self, curation_dir, monkeypatch):
        """Test same_as chain for locations."""
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                "Coffee": {"same_as": "Cafe", "dates": ["2024-01-16"]},
                "Shop": {"same_as": "Coffee", "dates": ["2024-01-17"]}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # All should resolve to Coffee Shop
        assert resolver.locations_map["cafe"]["name"] == "Coffee Shop"
        assert resolver.locations_map["coffee"]["name"] == "Coffee Shop"
        assert resolver.locations_map["shop"]["name"] == "Coffee Shop"

    def test_load_locations_same_as_circular(self, curation_dir, monkeypatch):
        """Test circular same_as reference for locations is handled."""
        locations_data = {
            "Montreal": {
                "Cafe": {"same_as": "Coffee"},
                "Coffee": {"same_as": "Shop"},
                "Shop": {"same_as": "Cafe"}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Circular references should not be in the map
        assert "cafe" not in resolver.locations_map
        assert "coffee" not in resolver.locations_map
        assert "shop" not in resolver.locations_map

    def test_load_locations_skip_unassigned(self, curation_dir, monkeypatch):
        """Test that _unassigned city is skipped."""
        locations_data = {
            "_unassigned": {
                "Unknown": {"canonical": None, "dates": ["2024-01-15"]}
            },
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-16"]}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert "cafe" in resolver.locations_map
        assert "unknown" not in resolver.locations_map

    def test_load_empty_curation_files(self, curation_dir, monkeypatch):
        """Test loading empty curation files."""
        create_people_file(curation_dir, "2024", {})
        create_locations_file(curation_dir, "2024", {})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        assert len(resolver.people_map) == 0
        assert len(resolver.locations_map) == 0

    def test_load_case_insensitive_keys(self, curation_dir, monkeypatch):
        """Test that lookup keys are lowercased."""
        people_data = {
            "ALICE": {
                "canonical": {"name": "Alice", "lastname": None, "alias": None}
            }
        }
        locations_data = {
            "Montreal": {
                "CAFE": {"canonical": "Coffee Shop"}
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Keys should be lowercased
        assert "alice" in resolver.people_map
        assert "ALICE" not in resolver.people_map
        assert "cafe" in resolver.locations_map
        assert "CAFE" not in resolver.locations_map


# =============================================================================
# _resolve_single_person() Tests
# =============================================================================

class TestResolveSinglePerson:
    """Test EntityResolver._resolve_single_person() method."""

    def test_resolve_person_simple(self, db_session):
        """Test resolving a simple person canonical."""
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": "Smith", "alias": None}

        person = resolver._resolve_single_person(canonical, db_session)

        assert person is not None
        assert person.name == "Alice"
        assert person.lastname == "Smith"
        assert person.disambiguator is None

    def test_resolve_person_with_alias(self, db_session):
        """Test resolving person with alias."""
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": None, "alias": "Al"}

        person = resolver._resolve_single_person(canonical, db_session)
        db_session.flush()

        assert person is not None
        assert person.name == "Alice"
        assert len(person.aliases) == 1
        assert person.aliases[0].alias == "Al"

    def test_resolve_person_with_multiple_aliases(self, db_session):
        """Test resolving person with multiple aliases."""
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": None, "alias": ["Al", "Ali"]}

        person = resolver._resolve_single_person(canonical, db_session)
        db_session.flush()

        assert person is not None
        assert len(person.aliases) == 2
        assert {a.alias for a in person.aliases} == {"Al", "Ali"}

    def test_resolve_person_with_disambiguator(self, db_session):
        """Test resolving person with disambiguator."""
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": None, "alias": None, "disambiguator": "coworker"}

        person = resolver._resolve_single_person(canonical, db_session)

        assert person is not None
        assert person.name == "Alice"
        assert person.disambiguator == "coworker"

    def test_resolve_person_missing_name(self, db_session):
        """Test resolving person without name returns None."""
        resolver = EntityResolver()
        canonical = {"lastname": "Smith", "alias": None}

        person = resolver._resolve_single_person(canonical, db_session)

        assert person is None

    def test_resolve_person_empty_name(self, db_session):
        """Test resolving person with empty name returns None."""
        resolver = EntityResolver()
        canonical = {"name": "", "lastname": "Smith", "alias": None}

        person = resolver._resolve_single_person(canonical, db_session)

        assert person is None

    def test_resolve_person_uses_cache(self, db_session):
        """Test that cache is used for duplicate resolutions."""
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": "Smith", "alias": None}

        person1 = resolver._resolve_single_person(canonical, db_session)
        person2 = resolver._resolve_single_person(canonical, db_session)

        # Should return same cached instance
        assert person1 is person2
        assert len(resolver.created_people) == 1

    def test_resolve_person_finds_existing_by_alias(self, db_session):
        """Test finding existing person by alias."""
        # Create existing person with alias
        person_existing = Person(name="Alice", lastname="Smith")
        db_session.add(person_existing)
        db_session.flush()

        alias = PersonAlias(person_id=person_existing.id, alias="Al")
        db_session.add(alias)
        db_session.flush()

        # Try to resolve same person
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": "Smith", "alias": "Al"}

        person = resolver._resolve_single_person(canonical, db_session)

        # Should find existing person
        assert person is not None
        assert person.id == person_existing.id

    def test_resolve_person_finds_existing_by_name_lastname(self, db_session):
        """Test finding existing person by name and lastname."""
        # Create existing person
        person_existing = Person(name="Alice", lastname="Smith")
        db_session.add(person_existing)
        db_session.flush()

        # Try to resolve same person
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": "Smith", "alias": None}

        person = resolver._resolve_single_person(canonical, db_session)

        # Should find existing person
        assert person is not None
        assert person.id == person_existing.id

    def test_resolve_person_finds_existing_by_name_disambiguator(self, db_session):
        """Test finding existing person by name and disambiguator."""
        # Create existing person
        person_existing = Person(name="Alice", disambiguator="coworker")
        db_session.add(person_existing)
        db_session.flush()

        # Try to resolve same person
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": None, "alias": None, "disambiguator": "coworker"}

        person = resolver._resolve_single_person(canonical, db_session)

        # Should find existing person
        assert person is not None
        assert person.id == person_existing.id

    def test_resolve_person_finds_existing_by_name_only(self, db_session):
        """Test finding existing person by name only (no lastname)."""
        # Create existing person
        person_existing = Person(name="Alice")
        db_session.add(person_existing)
        db_session.flush()

        # Try to resolve same person
        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": None, "alias": None}

        person = resolver._resolve_single_person(canonical, db_session)

        # Should find existing person
        assert person is not None
        assert person.id == person_existing.id

    def test_resolve_person_caches_found_person(self, db_session):
        """Test that found existing person is cached."""
        # Create existing person
        person_existing = Person(name="Alice", lastname="Smith")
        db_session.add(person_existing)
        db_session.flush()

        resolver = EntityResolver()
        canonical = {"name": "Alice", "lastname": "Smith", "alias": None}

        person1 = resolver._resolve_single_person(canonical, db_session)
        person2 = resolver._resolve_single_person(canonical, db_session)

        # Should use cache on second call
        assert person1 is person2
        assert len(resolver.created_people) == 1


# =============================================================================
# resolve_people() Tests
# =============================================================================

class TestResolvePeople:
    """Test EntityResolver.resolve_people() method."""

    def test_resolve_people_simple(self, db_session):
        """Test resolving a simple person."""
        resolver = EntityResolver()
        resolver.people_map = {
            "alice": [{"name": "Alice", "lastname": "Smith", "alias": None}]
        }

        people = resolver.resolve_people("Alice", db_session)

        assert len(people) == 1
        assert people[0].name == "Alice"
        assert people[0].lastname == "Smith"

    def test_resolve_people_case_insensitive(self, db_session):
        """Test that resolution is case-insensitive."""
        resolver = EntityResolver()
        resolver.people_map = {
            "alice": [{"name": "Alice", "lastname": None, "alias": None}]
        }

        people = resolver.resolve_people("ALICE", db_session)

        assert len(people) == 1
        assert people[0].name == "Alice"

    def test_resolve_people_not_in_map(self, db_session):
        """Test resolving person not in map returns empty list."""
        resolver = EntityResolver()
        resolver.people_map = {}

        people = resolver.resolve_people("Unknown", db_session)

        assert len(people) == 0

    def test_resolve_people_multi_person(self, db_session):
        """Test resolving multi-person entry."""
        resolver = EntityResolver()
        resolver.people_map = {
            "parents": [
                {"name": "Mom", "lastname": None, "alias": None},
                {"name": "Dad", "lastname": None, "alias": None}
            ]
        }

        people = resolver.resolve_people("Parents", db_session)

        assert len(people) == 2
        assert {p.name for p in people} == {"Mom", "Dad"}

    def test_resolve_people_filters_invalid(self, db_session):
        """Test that invalid canonicals are filtered out."""
        resolver = EntityResolver()
        resolver.people_map = {
            "test": [
                {"name": "Alice", "lastname": None, "alias": None},
                {"lastname": "Smith"},  # Missing name
                {"name": "Bob", "lastname": None, "alias": None}
            ]
        }

        people = resolver.resolve_people("Test", db_session)

        # Should only resolve valid entries
        assert len(people) == 2
        assert {p.name for p in people} == {"Alice", "Bob"}


# =============================================================================
# resolve_location() Tests
# =============================================================================

class TestResolveLocation:
    """Test EntityResolver.resolve_location() method."""

    def test_resolve_location_simple(self, db_session):
        """Test resolving a simple location."""
        resolver = EntityResolver()
        resolver.locations_map = {
            "cafe": {"name": "Coffee Shop", "city": "Montreal"}
        }

        location = resolver.resolve_location("Cafe", db_session)

        assert location is not None
        assert location.name == "Coffee Shop"
        assert location.city.name == "Montreal"

    def test_resolve_location_case_insensitive(self, db_session):
        """Test that resolution is case-insensitive."""
        resolver = EntityResolver()
        resolver.locations_map = {
            "cafe": {"name": "Coffee Shop", "city": "Montreal"}
        }

        location = resolver.resolve_location("CAFE", db_session)

        assert location is not None
        assert location.name == "Coffee Shop"

    def test_resolve_location_not_in_map(self, db_session):
        """Test resolving location not in map returns None."""
        resolver = EntityResolver()
        resolver.locations_map = {}

        location = resolver.resolve_location("Unknown", db_session)

        assert location is None

    def test_resolve_location_missing_name(self, db_session):
        """Test resolving location with missing name returns None."""
        resolver = EntityResolver()
        resolver.locations_map = {
            "cafe": {"name": "", "city": "Montreal"}
        }

        location = resolver.resolve_location("Cafe", db_session)

        assert location is None

    def test_resolve_location_missing_city(self, db_session):
        """Test resolving location with missing city returns None."""
        resolver = EntityResolver()
        resolver.locations_map = {
            "cafe": {"name": "Coffee Shop", "city": ""}
        }

        location = resolver.resolve_location("Cafe", db_session)

        assert location is None

    def test_resolve_location_uses_cache(self, db_session):
        """Test that cache is used for duplicate resolutions."""
        resolver = EntityResolver()
        resolver.locations_map = {
            "cafe": {"name": "Coffee Shop", "city": "Montreal"}
        }

        location1 = resolver.resolve_location("Cafe", db_session)
        location2 = resolver.resolve_location("Cafe", db_session)

        # Should return same cached instance
        assert location1 is location2
        assert len(resolver.created_locations) == 1

    def test_resolve_location_finds_existing(self, db_session):
        """Test finding existing location."""
        # Create existing city and location
        city = City(name="Montreal")
        db_session.add(city)
        db_session.flush()

        location_existing = Location(name="Coffee Shop", city_id=city.id)
        db_session.add(location_existing)
        db_session.flush()

        # Try to resolve same location
        resolver = EntityResolver()
        resolver.locations_map = {
            "cafe": {"name": "Coffee Shop", "city": "Montreal"}
        }

        location = resolver.resolve_location("Cafe", db_session)

        # Should find existing location
        assert location is not None
        assert location.id == location_existing.id

    def test_resolve_location_caches_found_location(self, db_session):
        """Test that found existing location is cached."""
        # Create existing city and location
        city = City(name="Montreal")
        db_session.add(city)
        db_session.flush()

        location_existing = Location(name="Coffee Shop", city_id=city.id)
        db_session.add(location_existing)
        db_session.flush()

        resolver = EntityResolver()
        resolver.locations_map = {
            "cafe": {"name": "Coffee Shop", "city": "Montreal"}
        }

        location1 = resolver.resolve_location("Cafe", db_session)
        location2 = resolver.resolve_location("Cafe", db_session)

        # Should use cache on second call
        assert location1 is location2
        assert len(resolver.created_locations) == 1


# =============================================================================
# _get_or_create_city() Tests
# =============================================================================

class TestGetOrCreateCity:
    """Test EntityResolver._get_or_create_city() method."""

    def test_create_new_city(self, db_session):
        """Test creating a new city."""
        resolver = EntityResolver()

        city = resolver._get_or_create_city("Montreal", db_session)

        assert city is not None
        assert city.name == "Montreal"

    def test_get_existing_city(self, db_session):
        """Test getting an existing city."""
        # Create existing city
        city_existing = City(name="Montreal")
        db_session.add(city_existing)
        db_session.flush()

        resolver = EntityResolver()

        city = resolver._get_or_create_city("Montreal", db_session)

        # Should return existing city
        assert city is not None
        assert city.id == city_existing.id

    def test_city_cache(self, db_session):
        """Test that city cache is used."""
        resolver = EntityResolver()

        city1 = resolver._get_or_create_city("Montreal", db_session)
        city2 = resolver._get_or_create_city("Montreal", db_session)

        # Should return same cached instance
        assert city1 is city2
        assert len(resolver.created_cities) == 1

    def test_city_cache_case_insensitive(self, db_session):
        """Test that city cache is case-insensitive."""
        resolver = EntityResolver()

        city1 = resolver._get_or_create_city("Montreal", db_session)
        city2 = resolver._get_or_create_city("MONTREAL", db_session)

        # Cache is lowercased, but should still work
        assert len(resolver.created_cities) == 1

    def test_city_caches_found_city(self, db_session):
        """Test that found existing city is cached."""
        # Create existing city
        city_existing = City(name="Montreal")
        db_session.add(city_existing)
        db_session.flush()

        resolver = EntityResolver()

        city1 = resolver._get_or_create_city("Montreal", db_session)
        city2 = resolver._get_or_create_city("Montreal", db_session)

        # Should use cache on second call
        assert city1 is city2
        assert len(resolver.created_cities) == 1


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple features."""

    def test_full_workflow_people(self, curation_dir, db_session, monkeypatch):
        """Test full workflow: load curation, resolve people."""
        people_data = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": "Al"},
                "dates": ["2024-01-15"]
            },
            "Alicia": {
                "same_as": "Alice",
                "dates": ["2024-01-16"]
            },
            "Parents": {
                "canonical": [
                    {"name": "Mom", "lastname": None, "alias": None},
                    {"name": "Dad", "lastname": None, "alias": None}
                ],
                "dates": ["2024-01-17"]
            }
        }
        create_people_file(curation_dir, "2024", people_data)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Resolve Alice
        people_alice = resolver.resolve_people("Alice", db_session)
        assert len(people_alice) == 1
        assert people_alice[0].name == "Alice"

        # Resolve Alicia (same_as Alice)
        people_alicia = resolver.resolve_people("Alicia", db_session)
        assert len(people_alicia) == 1
        assert people_alicia[0].name == "Alice"

        # Should be same cached instance
        assert people_alice[0] is people_alicia[0]

        # Resolve Parents (multi-person)
        people_parents = resolver.resolve_people("Parents", db_session)
        assert len(people_parents) == 2

    def test_full_workflow_locations(self, curation_dir, db_session, monkeypatch):
        """Test full workflow: load curation, resolve locations."""
        locations_data = {
            "Montreal": {
                "Cafe": {"canonical": "Coffee Shop", "dates": ["2024-01-15"]},
                "Coffee": {"same_as": "Cafe", "dates": ["2024-01-16"]},
                "Home": {"canonical": None, "dates": ["2024-01-17"]}
            },
            "Toronto": {
                "Library": {"canonical": "Public Library", "dates": ["2024-01-18"]}
            }
        }
        create_people_file(curation_dir, "2024", {"Alice": {"skip": True}})
        create_locations_file(curation_dir, "2024", locations_data)

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Resolve Cafe
        location_cafe = resolver.resolve_location("Cafe", db_session)
        assert location_cafe is not None
        assert location_cafe.name == "Coffee Shop"
        assert location_cafe.city.name == "Montreal"

        # Resolve Coffee (same_as Cafe)
        location_coffee = resolver.resolve_location("Coffee", db_session)
        assert location_coffee is not None
        assert location_coffee.name == "Coffee Shop"

        # Should be same cached instance
        assert location_cafe is location_coffee

        # Resolve Home (canonical: null)
        location_home = resolver.resolve_location("Home", db_session)
        assert location_home is not None
        assert location_home.name == "Home"
        assert location_home.city.name == "Montreal"

        # Resolve Library (different city)
        location_library = resolver.resolve_location("Library", db_session)
        assert location_library is not None
        assert location_library.name == "Public Library"
        assert location_library.city.name == "Toronto"

        # Check that both cities exist
        assert len(resolver.created_cities) == 2

    def test_cross_year_resolution(self, curation_dir, db_session, monkeypatch):
        """Test resolution across multiple years."""
        people_2023 = {
            "Alice": {
                "canonical": {"name": "Alice", "lastname": "Smith", "alias": None},
                "dates": ["2023-01-15"]
            }
        }
        people_2024 = {
            "Alicia": {
                "same_as": "Alice",
                "dates": ["2024-01-15"]
            }
        }
        create_people_file(curation_dir, "2023", people_2023)
        create_people_file(curation_dir, "2024", people_2024)
        create_locations_file(curation_dir, "2024", {"Montreal": {}})

        monkeypatch.setattr("dev.curation.resolve.CURATION_DIR", curation_dir)

        resolver = EntityResolver.load()

        # Both should resolve to same canonical
        people_alice = resolver.resolve_people("Alice", db_session)
        people_alicia = resolver.resolve_people("Alicia", db_session)

        assert len(people_alice) == 1
        assert len(people_alicia) == 1
        assert people_alice[0].name == "Alice"
        assert people_alicia[0].name == "Alice"
