# Palimpsest Testing Implementation Guide

**Date:** 2025-11-13
**Current Status:** Phase 3 Complete, 774 Tests Passing
**Coverage:** 23% (Target: 80%+)

---

## Executive Summary

This guide provides detailed implementation instructions for completing the Palimpsest testing suite. We've completed Phases 1-3 with 774 passing tests covering core utilities, dataclasses, and database managers. The remaining work focuses on integration testing, pipeline E2E testing, edge cases, and improving code coverage.

### Current State

✅ **Complete:**
- Phase 1: Foundation (Core utilities, test infrastructure)
- Phase 2: Dataclasses (MdEntry, TxtEntry)
- Phase 3: Database Managers (All 9 managers)
- Basic integration tests (YAML→DB, date context parsing)

⏳ **Remaining:**
- Phase 4: Advanced Integration Tests (Manager interactions)
- Phase 5: Pipeline E2E Tests (Round-trip validation)
- Phase 6: Edge Cases & Error Handling
- Phase 7: Performance & Optimization
- Coverage Improvement: 23% → 80%+

---

## Phase 4: Advanced Integration Tests

**Goal:** Test complex interactions between multiple managers and validate data consistency.

**Priority:** HIGH
**Estimated Tests:** 40-60
**Estimated Time:** 1-2 weeks

### 4.1 What This Phase Entails

Integration tests verify that managers work correctly **together**, not just in isolation. While unit tests verify individual manager methods work, integration tests verify:

1. **Cross-manager workflows** - Entry creation triggers person/location/tag creation
2. **Relationship consistency** - Bidirectional relationships stay in sync
3. **Transaction handling** - Multiple operations succeed or fail atomically
4. **Database constraints** - Foreign keys, unique constraints enforced
5. **Cascade behavior** - Deletions propagate correctly

### 4.2 Test Categories

#### Category A: Multi-Entity Entry Creation

**What to test:** Creating an entry with all relationship types simultaneously.

**Why it matters:** The most common operation in the system - importing a journal entry creates entries, people, locations, events, tags, references, poems, and dates all at once.

**Implementation:**

```python
# tests/integration/test_multi_entity_creation.py

import pytest
from datetime import date
from dev.database.manager import PalimpsestDB

class TestMultiEntityCreation:
    """Test creation of entries with multiple related entities."""

    def test_create_entry_with_all_relationships(self, test_db, tmp_path):
        """
        Verify that creating a complex entry properly creates and links:
        - Entry
        - People (with aliases)
        - Cities
        - Locations (with parent cities)
        - Events
        - Tags
        - MentionedDates (with people/locations)
        - References (with sources)
        - Poems (with versions)
        """
        db = test_db

        with db.session_scope() as session:
            # Create complex entry
            entry = db.entries.create({
                "date": date(2024, 1, 15),
                "file_path": str(tmp_path / "2024-01-15.md"),
                "file_hash": "abc123",
                "word_count": 500,

                # People with various formats
                "people": [
                    "Alice",  # Simple name
                    {"name": "Bob", "full_name": "Robert Smith"},  # With full name
                    "@Charlie",  # With @ prefix (should be cleaned)
                ],

                # Locations with parent cities
                "cities": ["Montreal", "Toronto"],
                "locations": [
                    {"name": "Cafe X", "city": "Montreal"},
                    {"name": "Library", "city": "Montreal", "expansion": "McGill Library"},
                    "Park",  # No city specified - should use default
                ],

                # Events and tags
                "events": ["thesis-defense", "birthday-party"],
                "tags": ["writing", "research", "personal"],

                # Dates with context, people, and locations
                "dates": [
                    {
                        "date": "2024-06-01",
                        "context": "Thesis exam at McGill",
                        "people": ["Alice", "Bob"],
                        "locations": ["Library"]
                    },
                    {
                        "date": "2024-08-15",
                        "context": "Coffee with Charlie",
                        "people": ["Charlie"],
                        "locations": ["Cafe X"]
                    }
                ],

                # References with sources
                "references": [
                    {
                        "content": "Important quote here",
                        "speaker": "Famous Scholar",
                        "source": {
                            "title": "Research Paper",
                            "type": "article",
                            "author": "Scholar Name",
                            "year": 2023
                        }
                    }
                ],

                # Poems with versions
                "poems": [
                    {
                        "title": "Winter Thoughts",
                        "content": "Roses are red\nViolets are blue",
                        "revision_date": date(2024, 1, 15),
                        "notes": "First draft"
                    }
                ]
            })

            session.flush()
            entry_id = entry.id

        # Verify in new session (ensures data persisted)
        with db.session_scope() as session:
            entry = db.entries.get_for_display(entry_date=date(2024, 1, 15))

            # Verify entry created
            assert entry is not None
            assert entry.word_count == 500

            # Verify people created and linked
            assert len(entry.people) == 3
            people_names = {p.name for p in entry.people}
            assert people_names == {"Alice", "Bob", "Charlie"}

            # Verify Bob has full_name
            bob = next(p for p in entry.people if p.name == "Bob")
            assert bob.full_name == "Robert Smith"

            # Verify cities created
            assert len(entry.cities) == 2
            city_names = {c.city for c in entry.cities}
            assert city_names == {"Montreal", "Toronto"}

            # Verify locations created with correct parents
            assert len(entry.locations) == 3
            cafe = next(loc for loc in entry.locations if loc.name == "Cafe X")
            assert cafe.city.city == "Montreal"

            library = next(loc for loc in entry.locations if loc.name == "Library")
            assert library.city.city == "Montreal"
            assert library.expansion == "McGill Library"

            # Verify events created
            assert len(entry.events) == 2
            event_names = {e.event for e in entry.events}
            assert event_names == {"thesis-defense", "birthday-party"}

            # Verify tags created
            assert len(entry.tags) == 3
            tag_names = {t.tag for t in entry.tags}
            assert tag_names == {"writing", "research", "personal"}

            # Verify mentioned dates with nested entities
            assert len(entry.dates) == 2

            thesis_date = next(d for d in entry.dates if d.date == date(2024, 6, 1))
            assert thesis_date.context == "Thesis exam at McGill"
            assert len(thesis_date.people) == 2
            assert len(thesis_date.locations) == 1

            coffee_date = next(d for d in entry.dates if d.date == date(2024, 8, 15))
            assert coffee_date.context == "Coffee with Charlie"
            assert len(coffee_date.people) == 1
            assert len(coffee_date.locations) == 1

            # Verify references with sources
            assert len(entry.references) == 1
            ref = entry.references[0]
            assert ref.content == "Important quote here"
            assert ref.speaker == "Famous Scholar"
            assert ref.source.title == "Research Paper"
            assert ref.source.type.value == "article"
            assert ref.source.year == 2023

            # Verify poems with versions
            assert len(entry.poems) == 1
            poem_version = entry.poems[0]
            assert poem_version.poem.title == "Winter Thoughts"
            assert "Roses are red" in poem_version.content
            assert poem_version.notes == "First draft"


    def test_entity_reuse_across_entries(self, test_db, tmp_path):
        """
        Verify that creating multiple entries reuses entities correctly.

        People, events, tags, cities should be reused (not duplicated).
        Locations should be reused if same name+city.
        Poems should create new versions if content changes.
        """
        db = test_db

        with db.session_scope() as session:
            # Create first entry
            entry1 = db.entries.create({
                "date": date(2024, 1, 15),
                "file_path": str(tmp_path / "2024-01-15.md"),
                "file_hash": "hash1",
                "people": ["Alice", "Bob"],
                "cities": ["Montreal"],
                "locations": [{"name": "Cafe X", "city": "Montreal"}],
                "tags": ["writing"],
                "events": ["thesis-defense"]
            })

            # Create second entry with overlapping entities
            entry2 = db.entries.create({
                "date": date(2024, 1, 16),
                "file_path": str(tmp_path / "2024-01-16.md"),
                "file_hash": "hash2",
                "people": ["Alice", "Charlie"],  # Alice reused, Charlie new
                "cities": ["Montreal", "Toronto"],  # Montreal reused, Toronto new
                "locations": [
                    {"name": "Cafe X", "city": "Montreal"},  # Should reuse
                    {"name": "Library", "city": "Montreal"}  # New location
                ],
                "tags": ["writing", "research"],  # writing reused, research new
                "events": ["thesis-defense", "conference"]  # thesis-defense reused
            })

            session.flush()

        with db.session_scope() as session:
            # Count entities
            alice_count = session.query(Person).filter_by(name="Alice").count()
            assert alice_count == 1, "Alice should exist once"

            montreal_count = session.query(City).filter_by(city="Montreal").count()
            assert montreal_count == 1, "Montreal should exist once"

            cafe_count = session.query(Location).filter_by(name="Cafe X").count()
            assert cafe_count == 1, "Cafe X should exist once"

            writing_tag = session.query(Tag).filter_by(tag="writing").first()
            assert len(writing_tag.entries) == 2, "Writing tag should link to 2 entries"

            thesis_event = session.query(Event).filter_by(event="thesis-defense").first()
            assert len(thesis_event.entries) == 2, "Thesis event should link to 2 entries"

            # Verify Alice appears in 2 entries
            alice = session.query(Person).filter_by(name="Alice").first()
            assert len(alice.entries) == 2
```

#### Category B: Incremental vs Full Updates

**What to test:** Entry updates in incremental mode (add to existing) vs full mode (replace all).

**Why it matters:** The YAML→SQL pipeline supports both update modes. Incremental mode adds new entities, full mode replaces them.

**Implementation:**

```python
# tests/integration/test_update_modes.py

class TestUpdateModes:
    """Test incremental vs full replacement update modes."""

    def test_incremental_update_adds_entities(self, test_db, tmp_path):
        """Incremental updates should add new entities without removing old ones."""
        db = test_db

        with db.session_scope() as session:
            # Create initial entry
            entry = db.entries.create({
                "date": date(2024, 1, 15),
                "file_path": str(tmp_path / "2024-01-15.md"),
                "file_hash": "hash1",
                "people": ["Alice"],
                "tags": ["writing"],
                "events": ["thesis-defense"]
            })
            session.flush()
            entry_id = entry.id

        with db.session_scope() as session:
            entry = session.query(Entry).get(entry_id)

            # Incremental update - add new entities
            entry = db.entries.update(entry, {
                "people": ["Bob"],  # Add Bob, keep Alice
                "tags": ["research"],  # Add research, keep writing
                "events": ["conference"]  # Add conference, keep thesis-defense
            }, incremental=True)

            session.flush()

        with db.session_scope() as session:
            entry = session.query(Entry).get(entry_id)

            # Verify old + new entities present
            assert len(entry.people) == 2
            people_names = {p.name for p in entry.people}
            assert people_names == {"Alice", "Bob"}

            assert len(entry.tags) == 2
            tag_names = {t.tag for t in entry.tags}
            assert tag_names == {"writing", "research"}

            assert len(entry.events) == 2
            event_names = {e.event for e in entry.events}
            assert event_names == {"thesis-defense", "conference"}


    def test_full_update_replaces_entities(self, test_db, tmp_path):
        """Full updates should replace all entities of updated types."""
        db = test_db

        with db.session_scope() as session:
            # Create initial entry
            entry = db.entries.create({
                "date": date(2024, 1, 15),
                "file_path": str(tmp_path / "2024-01-15.md"),
                "file_hash": "hash1",
                "people": ["Alice", "Bob"],
                "tags": ["writing", "personal"],
                "events": ["thesis-defense"]
            })
            session.flush()
            entry_id = entry.id

        with db.session_scope() as session:
            entry = session.query(Entry).get(entry_id)

            # Full update - replace entities
            entry = db.entries.update(entry, {
                "people": ["Charlie"],  # Replace Alice & Bob with Charlie
                "tags": ["research"],  # Replace all tags with research
                "events": ["conference", "seminar"]  # Replace thesis-defense
            }, incremental=False)

            session.flush()

        with db.session_scope() as session:
            entry = session.query(Entry).get(entry_id)

            # Verify only new entities present
            assert len(entry.people) == 1
            assert entry.people[0].name == "Charlie"

            assert len(entry.tags) == 1
            assert entry.tags[0].tag == "research"

            assert len(entry.events) == 2
            event_names = {e.event for e in entry.events}
            assert event_names == {"conference", "seminar"}
```

#### Category C: Database Consistency Tests

**What to test:** Database constraints, cascade behavior, orphan prevention.

**Implementation:**

```python
# tests/integration/test_database_consistency.py

class TestDatabaseConsistency:
    """Test database constraints and referential integrity."""

    def test_cascade_delete_entry_removes_relationships(self, test_db, tmp_path):
        """Deleting an entry should remove entry-specific relationships."""
        db = test_db

        with db.session_scope() as session:
            # Create entry with various relationships
            entry = db.entries.create({
                "date": date(2024, 1, 15),
                "file_path": str(tmp_path / "2024-01-15.md"),
                "file_hash": "hash1",
                "people": ["Alice"],
                "tags": ["writing"],
                "dates": [{"date": "2024-06-01", "context": "exam"}],
                "poems": [{
                    "title": "Test Poem",
                    "content": "Test content",
                    "revision_date": date(2024, 1, 15)
                }],
                "references": [{
                    "content": "Quote",
                    "source": {"title": "Book", "type": "book"}
                }]
            })
            session.flush()
            entry_id = entry.id

            # Get counts before deletion
            mentioned_date_id = entry.dates[0].id
            poem_version_id = entry.poems[0].id
            reference_id = entry.references[0].id
            person_id = entry.people[0].id
            tag_id = entry.tags[0].id

        with db.session_scope() as session:
            entry = session.query(Entry).get(entry_id)
            db.entries.delete(entry)
            session.flush()

        with db.session_scope() as session:
            # Verify entry deleted
            entry = session.query(Entry).get(entry_id)
            assert entry is None

            # Verify entry-specific relationships deleted (cascade)
            assert session.query(MentionedDate).get(mentioned_date_id) is None
            assert session.query(PoemVersion).get(poem_version_id) is None
            assert session.query(Reference).get(reference_id) is None

            # Verify shared entities still exist (no cascade)
            assert session.query(Person).get(person_id) is not None
            assert session.query(Tag).get(tag_id) is not None


    def test_unique_constraints_enforced(self, test_db):
        """Test that unique constraints prevent duplicates."""
        db = test_db

        with db.session_scope() as session:
            # Create person
            person1 = db.people.create({"name": "Alice"})
            session.flush()

            # Attempt to create duplicate person - should raise error
            with pytest.raises(Exception):  # DatabaseError or IntegrityError
                person2 = db.people.create({"name": "Alice"})
                session.flush()


    def test_foreign_key_constraints_enforced(self, test_db):
        """Test that foreign key constraints prevent orphans."""
        db = test_db

        with db.session_scope() as session:
            # Attempt to create location without city - should fail
            with pytest.raises(Exception):
                location = Location(name="Test Loc", city_id=99999)  # Invalid city_id
                session.add(location)
                session.flush()
```

#### Category D: Person Relationship Tracking

**What to test:** Person appears in multiple entries, events, manuscripts.

```python
# tests/integration/test_person_tracking.py

class TestPersonTracking:
    """Test person tracking across entries, events, and manuscripts."""

    def test_person_entry_count_tracking(self, test_db, tmp_path):
        """Verify person.entry_count updates correctly."""
        db = test_db

        with db.session_scope() as session:
            # Create 3 entries mentioning Alice
            for i in range(3):
                db.entries.create({
                    "date": date(2024, 1, 15 + i),
                    "file_path": str(tmp_path / f"2024-01-{15+i}.md"),
                    "file_hash": f"hash{i}",
                    "people": ["Alice"]
                })
            session.flush()

        with db.session_scope() as session:
            alice = session.query(Person).filter_by(name="Alice").first()

            # Verify entry_count
            assert alice.entry_count == 3

            # Verify appearance dates
            assert alice.first_appearance_date == date(2024, 1, 15)
            assert alice.last_appearance_date == date(2024, 1, 17)


    def test_person_in_events_and_manuscripts(self, test_db, tmp_path):
        """Test person linking to events and manuscript character data."""
        db = test_db

        with db.session_scope() as session:
            # Create person
            person = db.people.create({"name": "Alice"})

            # Create event with person
            event = db.events.create({
                "event": "thesis-defense",
                "people": ["Alice"]
            })

            # Create manuscript person (character adaptation)
            ms_person = db.manuscripts.create_person({
                "person_id": person.id,
                "character": "Alicia"  # Fictionalized name
            })

            session.flush()
            person_id = person.id

        with db.session_scope() as session:
            person = session.query(Person).get(person_id)

            # Verify event linking
            assert len(person.events) == 1
            assert person.events[0].event == "thesis-defense"

            # Verify manuscript linking
            assert person.manuscript is not None
            assert person.manuscript.character == "Alicia"
```

### 4.3 Implementation Steps

**Step 1:** Create test file structure
```bash
tests/integration/
├── test_multi_entity_creation.py       # Complex entry creation
├── test_update_modes.py                # Incremental vs full updates
├── test_database_consistency.py        # Constraints and cascades
├── test_person_tracking.py             # Person across entities
├── test_location_hierarchies.py        # City→Location relationships
├── test_event_timelines.py             # Event across entries
└── test_manuscript_curation.py         # Manuscript status tracking
```

**Step 2:** Implement one category at a time
1. Start with multi-entity creation (most critical)
2. Add update mode tests
3. Add consistency tests
4. Add specialized tracking tests

**Step 3:** Run and iterate
```bash
# Run integration tests only
pytest tests/integration/ -v

# Run with coverage
pytest tests/integration/ --cov=dev/database/managers --cov-report=term
```

### 4.4 Success Criteria

✅ All manager interactions tested
✅ Complex multi-entity operations work
✅ Database constraints enforced
✅ No orphaned records
✅ Relationship bidirectionality verified
✅ Coverage of managers/ directory > 85%

---

## Phase 5: Pipeline E2E Tests

**Goal:** Test complete data flow from YAML files to database and back.

**Priority:** CRITICAL
**Estimated Tests:** 40-60
**Estimated Time:** 2-3 weeks

### 5.1 What This Phase Entails

E2E (end-to-end) tests verify the **entire pipeline** works correctly:

1. **yaml2sql**: Markdown → Database import
2. **sql2yaml**: Database → Markdown export
3. **Round-trip**: Markdown → DB → Markdown (lossless)
4. **Hash-based change detection**
5. **Batch processing**
6. **Error handling in pipeline**

These tests use **real files** and the **actual pipeline scripts**, not just manager methods.

### 5.2 Test Categories

#### Category A: yaml2sql Pipeline Tests

**What to test:** Importing markdown files creates correct database entries.

```python
# tests/e2e/test_yaml2sql_pipeline.py

import pytest
from pathlib import Path
from datetime import date
from dev.pipeline.yaml2sql import process_single_file, process_directory
from dev.database.manager import PalimpsestDB

class TestYaml2SqlPipeline:
    """Test YAML→SQL import pipeline."""

    def test_import_minimal_entry(self, test_db, tmp_path):
        """Import entry with only required fields."""
        # Create markdown file
        md_file = tmp_path / "2024-01-15.md"
        md_file.write_text("""---
date: 2024-01-15
---

# Monday, January 15, 2024

This is a minimal test entry.
""")

        # Process file
        result = process_single_file(md_file, test_db)

        # Verify result
        assert result.status == "created"
        assert result.entry_date == date(2024, 1, 15)

        # Verify database
        with test_db.session_scope() as session:
            entry = test_db.entries.get(entry_date=date(2024, 1, 15))
            assert entry is not None
            assert entry.file_path == str(md_file)
            assert entry.word_count > 0


    def test_import_complex_entry(self, test_db, tmp_path):
        """Import entry with all metadata fields."""
        md_file = tmp_path / "2024-01-15.md"
        md_file.write_text("""---
date: 2024-01-15
word_count: 850
reading_time: 4.2

city: Montreal
locations:
  - Cafe X
  - Library (McGill Library)

people:
  - Alice
  - Bob (Robert Smith)

tags:
  - writing
  - research

events:
  - thesis-defense

dates:
  - 2024-06-01 (thesis exam)

references:
  - content: "Important quote"
    source:
      title: Research Paper
      type: article

poems:
  - title: Winter Thoughts
    content: |
      Roses are red
      Violets are blue
    revision_date: 2024-01-15
---

# Entry Content

Complex entry with all fields.
""")

        # Process file
        result = process_single_file(md_file, test_db)
        assert result.status == "created"

        # Verify all relationships created
        with test_db.session_scope() as session:
            entry = test_db.entries.get_for_display(entry_date=date(2024, 1, 15))

            assert len(entry.people) == 2
            assert len(entry.cities) == 1
            assert len(entry.locations) == 2
            assert len(entry.tags) == 2
            assert len(entry.events) == 1
            assert len(entry.dates) == 1
            assert len(entry.references) == 1
            assert len(entry.poems) == 1


    def test_hash_based_skip(self, test_db, tmp_path):
        """Unchanged files should be skipped on re-import."""
        md_file = tmp_path / "2024-01-15.md"
        md_file.write_text("""---
date: 2024-01-15
---

Test entry.
""")

        # First import
        result1 = process_single_file(md_file, test_db)
        assert result1.status == "created"

        # Second import without changes - should skip
        result2 = process_single_file(md_file, test_db, force=False)
        assert result2.status == "skipped"


    def test_update_changed_file(self, test_db, tmp_path):
        """Changed files should trigger update."""
        md_file = tmp_path / "2024-01-15.md"

        # Initial content
        md_file.write_text("""---
date: 2024-01-15
tags:
  - writing
---

Original content.
""")

        # First import
        result1 = process_single_file(md_file, test_db)
        assert result1.status == "created"

        # Modify content
        md_file.write_text("""---
date: 2024-01-15
tags:
  - writing
  - research
---

Updated content.
""")

        # Second import - should update
        result2 = process_single_file(md_file, test_db)
        assert result2.status == "updated"

        # Verify update
        with test_db.session_scope() as session:
            entry = test_db.entries.get(entry_date=date(2024, 1, 15))
            tag_names = {t.tag for t in entry.tags}
            assert tag_names == {"writing", "research"}


    def test_batch_import(self, test_db, tmp_path):
        """Test importing multiple files."""
        # Create 10 files
        for i in range(1, 11):
            md_file = tmp_path / f"2024-01-{i:02d}.md"
            md_file.write_text(f"""---
date: 2024-01-{i:02d}
---

Entry {i}.
""")

        # Process directory
        results = process_directory(tmp_path, test_db)

        # Verify all processed
        assert len(results) == 10
        assert all(r.status == "created" for r in results)

        # Verify all in database
        with test_db.session_scope() as session:
            entries = session.query(Entry).filter(
                Entry.date >= date(2024, 1, 1),
                Entry.date <= date(2024, 1, 10)
            ).all()
            assert len(entries) == 10
```

#### Category B: sql2yaml Pipeline Tests

**What to test:** Exporting database entries creates correct markdown files.

```python
# tests/e2e/test_sql2yaml_pipeline.py

from dev.pipeline.sql2yaml import export_entry_to_markdown, export_all_entries

class TestSql2YamlPipeline:
    """Test SQL→YAML export pipeline."""

    def test_export_minimal_entry(self, test_db, tmp_path):
        """Export entry with minimal metadata."""
        # Create entry in database
        with test_db.session_scope() as session:
            entry = test_db.entries.create({
                "date": date(2024, 1, 15),
                "file_path": str(tmp_path / "original.md"),
                "file_hash": "hash1",
                "word_count": 100
            })
            session.flush()

        # Export
        export_dir = tmp_path / "export"
        export_entry_to_markdown(
            test_db,
            date(2024, 1, 15),
            export_dir,
            body_text="Test entry content."
        )

        # Verify file created
        exported_file = export_dir / "2024" / "2024-01-15.md"
        assert exported_file.exists()

        # Parse exported YAML
        from dev.utils.md import split_frontmatter
        import yaml

        content = exported_file.read_text()
        yaml_text, body = split_frontmatter(content)
        metadata = yaml.safe_load(yaml_text)

        # Verify metadata
        assert metadata["date"] == "2024-01-15"
        assert "word_count" in metadata
        assert body.strip() == "Test entry content."


    def test_export_complex_entry(self, test_db, tmp_path):
        """Export entry with all relationships."""
        # Create complex entry
        with test_db.session_scope() as session:
            entry = test_db.entries.create({
                "date": date(2024, 1, 15),
                "file_path": str(tmp_path / "original.md"),
                "file_hash": "hash1",
                "people": ["Alice", {"name": "Bob", "full_name": "Robert Smith"}],
                "cities": ["Montreal"],
                "locations": [{"name": "Cafe X", "city": "Montreal"}],
                "tags": ["writing", "research"],
                "events": ["thesis-defense"],
                "dates": [{"date": "2024-06-01", "context": "exam"}],
                "references": [{
                    "content": "Quote",
                    "source": {"title": "Book", "type": "book"}
                }],
                "poems": [{
                    "title": "Test",
                    "content": "Content",
                    "revision_date": date(2024, 1, 15)
                }]
            })
            session.flush()

        # Export
        export_dir = tmp_path / "export"
        export_entry_to_markdown(
            test_db,
            date(2024, 1, 15),
            export_dir,
            body_text="Entry body."
        )

        # Parse exported file
        exported_file = export_dir / "2024" / "2024-01-15.md"
        content = exported_file.read_text()
        yaml_text, _ = split_frontmatter(content)
        metadata = yaml.safe_load(yaml_text)

        # Verify all fields exported
        assert len(metadata["people"]) == 2
        assert metadata["city"] == "Montreal"
        assert len(metadata["locations"]) == 1
        assert len(metadata["tags"]) == 2
        assert len(metadata["events"]) == 1
        assert len(metadata["dates"]) == 1
        assert len(metadata["references"]) == 1
        assert len(metadata["poems"]) == 1

        # Verify complex person export
        bob_data = next(p for p in metadata["people"] if isinstance(p, dict))
        assert bob_data["full_name"] == "Robert Smith"
```

#### Category C: Round-Trip Tests (CRITICAL)

**What to test:** YAML → DB → YAML preserves all data.

```python
# tests/e2e/test_round_trip.py

class TestRoundTrip:
    """Test lossless round-trip: YAML → DB → YAML."""

    def test_round_trip_lossless(self, test_db, tmp_path):
        """Verify round-trip preserves all metadata."""
        # Create original file
        original_dir = tmp_path / "original"
        original_dir.mkdir()
        original_file = original_dir / "2024-01-15.md"

        original_content = """---
date: 2024-01-15
word_count: 500

city: Montreal
locations:
  - Cafe X
  - Library (McGill Library)

people:
  - Alice
  - Bob (Robert Smith)

tags:
  - writing
  - research

events:
  - thesis-defense

dates:
  - 2024-06-01 (thesis exam)

references:
  - content: "Important quote"
    speaker: Scholar
    source:
      title: Research Paper
      type: article
      author: Author Name
      year: 2023

poems:
  - title: Winter
    content: |
      Line one
      Line two
    revision_date: 2024-01-15
    notes: First draft

epigraph: "Opening quote"
epigraph_attribution: Philosopher

manuscript:
  status: draft
  edited: false
  themes:
    - identity
    - memory
---

# Entry Body

This is the entry content that should be preserved.

Multiple paragraphs and formatting should remain intact.
"""
        original_file.write_text(original_content)

        # Step 1: Import to database
        result = process_single_file(original_file, test_db)
        assert result.status == "created"

        # Step 2: Export from database
        export_dir = tmp_path / "export"
        # Need to preserve body - read from original
        from dev.utils.md import split_frontmatter
        _, body = split_frontmatter(original_content)

        export_entry_to_markdown(
            test_db,
            date(2024, 1, 15),
            export_dir,
            body_text=body
        )

        # Step 3: Compare
        exported_file = export_dir / "2024" / "2024-01-15.md"
        assert exported_file.exists()

        # Parse both
        original_yaml, original_body = split_frontmatter(original_content)
        exported_yaml, exported_body = split_frontmatter(exported_file.read_text())

        import yaml
        original_meta = yaml.safe_load(original_yaml)
        exported_meta = yaml.safe_load(exported_yaml)

        # Verify metadata equivalence
        assert original_meta["date"] == exported_meta["date"]
        assert original_meta["city"] == exported_meta["city"]
        assert set(original_meta["tags"]) == set(exported_meta["tags"])
        assert set(original_meta["events"]) == set(exported_meta["events"])

        # Verify complex structures
        assert len(original_meta["people"]) == len(exported_meta["people"])
        assert len(original_meta["references"]) == len(exported_meta["references"])
        assert len(original_meta["poems"]) == len(exported_meta["poems"])

        # Verify body preserved
        assert original_body.strip() == exported_body.strip()


    def test_round_trip_batch(self, test_db, tmp_path):
        """Test round-trip with multiple files."""
        # Create 20 diverse files
        original_dir = tmp_path / "original"
        original_dir.mkdir()

        for i in range(1, 21):
            md_file = original_dir / f"2024-01-{i:02d}.md"
            md_file.write_text(f"""---
date: 2024-01-{i:02d}
people:
  - Person{i}
tags:
  - tag{i}
---

Entry {i} content.
""")

        # Import all
        results = process_directory(original_dir, test_db)
        assert len(results) == 20

        # Export all
        export_dir = tmp_path / "export"
        export_all_entries(test_db, export_dir)

        # Verify all exported
        exported_files = list(export_dir.rglob("*.md"))
        assert len(exported_files) == 20

        # Sample check: verify 5 random files
        import random
        for i in random.sample(range(1, 21), 5):
            original = original_dir / f"2024-01-{i:02d}.md"
            exported = export_dir / "2024" / f"2024-01-{i:02d}.md"

            # Compare metadata
            from dev.utils.md import split_frontmatter
            import yaml

            orig_yaml, _ = split_frontmatter(original.read_text())
            exp_yaml, _ = split_frontmatter(exported.read_text())

            orig_meta = yaml.safe_load(orig_yaml)
            exp_meta = yaml.safe_load(exp_yaml)

            assert orig_meta["date"] == exp_meta["date"]
            assert orig_meta["people"] == exp_meta["people"]
            assert orig_meta["tags"] == exp_meta["tags"]
```

### 5.3 Implementation Steps

**Step 1:** Create E2E test structure
```bash
tests/e2e/
├── test_yaml2sql_pipeline.py      # Import tests
├── test_sql2yaml_pipeline.py      # Export tests
├── test_round_trip.py             # Round-trip tests
└── test_pipeline_errors.py        # Error handling
```

**Step 2:** Implement pipeline tests
1. Start with yaml2sql (import is more critical)
2. Add sql2yaml (export)
3. Add round-trip (combines both)
4. Add error handling tests

**Step 3:** Run and validate
```bash
# Run E2E tests
pytest tests/e2e/ -v -s

# Run with real data (if available)
pytest tests/e2e/ --real-data
```

### 5.4 Success Criteria

✅ All YAML fields correctly imported
✅ All database fields correctly exported
✅ Round-trip is lossless (semantic equivalence)
✅ Hash-based change detection works
✅ Batch processing handles errors gracefully
✅ Coverage of pipeline/ directory > 80%

---

## Phase 6: Edge Cases & Error Handling

**Goal:** Test unusual inputs, boundary conditions, and error scenarios.

**Priority:** MEDIUM
**Estimated Tests:** 40-50
**Estimated Time:** 1 week

### 6.1 What This Phase Entails

Edge case tests verify the system handles:
1. **Boundary conditions** - Empty values, very large values
2. **Invalid inputs** - Malformed YAML, invalid dates
3. **Data anomalies** - Duplicate names, circular references
4. **Error recovery** - Transaction rollback, partial failures

### 6.2 Test Categories

#### Category A: Data Edge Cases

```python
# tests/integration/test_edge_cases.py

class TestEdgeCases:
    """Test unusual but valid data scenarios."""

    def test_empty_optional_fields(self, test_db, tmp_path):
        """Entry with all optional fields empty."""
        entry = db.entries.create({
            "date": date(2024, 1, 15),
            "file_path": str(tmp_path / "test.md"),
            "file_hash": "hash1",
            # All optional fields omitted
        })

        assert entry.people == []
        assert entry.tags == []
        assert entry.word_count is None


    def test_very_long_content(self, test_db, tmp_path):
        """Entry with 10,000+ word content."""
        long_text = " ".join(["word"] * 10000)

        md_file = tmp_path / "long.md"
        md_file.write_text(f"""---
date: 2024-01-15
---

{long_text}
""")

        result = process_single_file(md_file, test_db)
        assert result.status == "created"

        entry = db.entries.get(entry_date=date(2024, 1, 15))
        assert entry.word_count >= 10000


    def test_special_characters_in_names(self, test_db):
        """Names with unicode, accents, apostrophes."""
        entry = db.entries.create({
            "date": date(2024, 1, 15),
            "file_path": "/test.md",
            "file_hash": "hash1",
            "people": [
                "José García",  # Accents
                "O'Brien",  # Apostrophe
                "François-René",  # Hyphen
                "北京"  # Unicode
            ]
        })

        assert len(entry.people) == 4


    def test_poem_without_revision_date(self, test_db, tmp_path):
        """Poem missing revision_date should default to entry date."""
        entry = db.entries.create({
            "date": date(2024, 1, 15),
            "file_path": str(tmp_path / "test.md"),
            "file_hash": "hash1",
            "poems": [{
                "title": "Untitled",
                "content": "Poem content"
                # revision_date omitted
            }]
        })

        poem_version = entry.poems[0]
        assert poem_version.revision_date == date(2024, 1, 15)


    def test_circular_related_entries(self, test_db, tmp_path):
        """Entries referencing each other."""
        entry1 = db.entries.create({
            "date": date(2024, 1, 15),
            "file_path": str(tmp_path / "1.md"),
            "file_hash": "hash1"
        })

        entry2 = db.entries.create({
            "date": date(2024, 1, 16),
            "file_path": str(tmp_path / "2.md"),
            "file_hash": "hash2",
            "related_entries": [date(2024, 1, 15)]
        })

        # Add circular reference
        db.entries.update(entry1, {
            "related_entries": [date(2024, 1, 16)]
        })

        # Verify both directions
        assert entry2 in entry1.related_entries
        assert entry1 in entry2.related_entries
```

#### Category B: Error Handling

```python
# tests/integration/test_error_handling.py

class TestErrorHandling:
    """Test error scenarios and recovery."""

    def test_invalid_yaml_syntax(self, test_db, tmp_path):
        """Malformed YAML should raise clear error."""
        md_file = tmp_path / "bad.md"
        md_file.write_text("""---
date: 2024-01-15
tags:
  - writing
  - [malformed
---

Content.
""")

        with pytest.raises(yaml.YAMLError):
            process_single_file(md_file, test_db)


    def test_invalid_date_format(self, test_db, tmp_path):
        """Invalid date should raise ValidationError."""
        md_file = tmp_path / "bad.md"
        md_file.write_text("""---
date: 2024-13-45
---

Content.
""")

        with pytest.raises(ValidationError):
            process_single_file(md_file, test_db)


    def test_transaction_rollback_on_error(self, test_db, tmp_path):
        """Error during entry creation should rollback transaction."""
        # Create entry
        entry = db.entries.create({
            "date": date(2024, 1, 15),
            "file_path": str(tmp_path / "test.md"),
            "file_hash": "hash1",
            "people": ["Alice"]
        })

        # Attempt update that will fail
        try:
            with db.session_scope() as session:
                entry = session.query(Entry).filter_by(
                    date=date(2024, 1, 15)
                ).first()

                # Cause an error
                entry.date = None  # Violates NOT NULL
                session.flush()
        except Exception:
            pass

        # Verify entry unchanged
        entry = db.entries.get(entry_date=date(2024, 1, 15))
        assert entry.date == date(2024, 1, 15)
        assert len(entry.people) == 1
```

### 6.3 Success Criteria

✅ All edge cases handled gracefully
✅ Errors don't corrupt database
✅ Helpful error messages provided
✅ Transaction rollback works correctly

---

## Phase 7: Performance & Optimization (Optional)

**Goal:** Ensure system performs well with large datasets.

**Priority:** LOW
**Estimated Tests:** 10-20
**Estimated Time:** 3-5 days

### 7.1 What This Phase Entails

Performance tests verify:
1. **Batch operations** scale linearly
2. **Query optimization** eliminates N+1 problems
3. **Large datasets** export successfully
4. **Memory usage** stays reasonable

### 7.2 Test Examples

```python
# tests/performance/test_performance.py

class TestPerformance:
    """Performance benchmarks."""

    def test_batch_import_performance(self, test_db, tmp_path, benchmark):
        """Import 1000 entries within time limit."""
        # Create 1000 files
        files = []
        for i in range(1000):
            md_file = tmp_path / f"entry_{i}.md"
            md_file.write_text(f"""---
date: 2020-01-01
---
Entry {i}
""")
            files.append(md_file)

        # Benchmark import
        def import_all():
            process_directory(tmp_path, test_db)

        result = benchmark(import_all)

        # Should complete in < 60 seconds
        assert result.stats.mean < 60


    def test_no_n_plus_one_queries(self, test_db):
        """Verify optimized loading doesn't cause N+1 queries."""
        # Create 100 entries with people
        for i in range(100):
            db.entries.create({
                "date": date(2020, 1, 1) + timedelta(days=i),
                "file_path": f"/test_{i}.md",
                "file_hash": f"hash{i}",
                "people": [f"Person{i}"]
            })

        # Enable query logging
        import logging
        logging.basicConfig()
        logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)

        # Load entries with relationships
        from dev.database.query_optimizer import QueryOptimizer

        entry_ids = [i for i in range(1, 101)]
        entries = QueryOptimizer.for_export(session, entry_ids)

        # Access relationships (should not trigger new queries)
        for entry in entries:
            _ = entry.people
            _ = entry.tags

        # Verify query count (should be 1-2 queries, not 100+)
```

### 7.3 Success Criteria

✅ Batch operations performant
✅ No N+1 query problems
✅ Large exports complete successfully
✅ Memory usage reasonable

---

## Coverage Improvement Strategy

**Current:** 23%
**Target:** 80%+

### Step-by-Step Approach

**Step 1:** Identify low-coverage modules
```bash
pytest tests/ --cov=dev --cov-report=html
open htmlcov/index.html  # View coverage report
```

**Step 2:** Prioritize by importance
1. Database managers (highest priority)
2. Pipeline scripts
3. Core utilities
4. Dataclasses

**Step 3:** Add targeted tests
- Focus on uncovered branches
- Add tests for error paths
- Test edge cases in complex functions

**Step 4:** Iterate until target met
```bash
# Check coverage after each addition
pytest tests/ --cov=dev --cov-report=term-missing
```

---

## Testing Best Practices

### 1. Test Isolation

Each test should be independent:
```python
# Good - uses fixtures
def test_create_person(test_db):
    person = test_db.people.create({"name": "Alice"})
    assert person.name == "Alice"

# Bad - depends on other tests
def test_update_person():
    person = session.query(Person).first()  # Assumes person exists
    person.name = "Bob"
```

### 2. Descriptive Names

Test names should describe what they test:
```python
# Good
def test_incremental_update_adds_tags_without_removing_existing()

# Bad
def test_update()
```

### 3. Arrange-Act-Assert Pattern

Structure tests clearly:
```python
def test_person_entry_count(test_db):
    # Arrange - set up test data
    person = create_person("Alice")

    # Act - perform the action
    add_person_to_entries(person, 3)

    # Assert - verify result
    assert person.entry_count == 3
```

### 4. Use Fixtures

Share setup code via fixtures:
```python
@pytest.fixture
def complex_entry(test_db, tmp_path):
    """Fixture providing a complex test entry."""
    return test_db.entries.create({
        "date": date(2024, 1, 15),
        "file_path": str(tmp_path / "test.md"),
        "people": ["Alice", "Bob"],
        "tags": ["writing"],
        # ... more fields
    })

def test_with_complex_entry(complex_entry):
    assert len(complex_entry.people) == 2
```

### 5. Test Both Success and Failure

```python
def test_create_person_success(test_db):
    person = test_db.people.create({"name": "Alice"})
    assert person.name == "Alice"

def test_create_person_duplicate_fails(test_db):
    test_db.people.create({"name": "Alice"})

    with pytest.raises(DatabaseError):
        test_db.people.create({"name": "Alice"})
```

---

## Implementation Timeline

### Week 1-2: Phase 4 (Integration Tests)
- Days 1-3: Multi-entity creation tests
- Days 4-5: Update mode tests
- Days 6-7: Database consistency tests
- Days 8-10: Specialized tracking tests

### Week 3-4: Phase 5 (Pipeline E2E)
- Days 1-5: yaml2sql pipeline tests
- Days 6-10: sql2yaml pipeline tests
- Days 11-14: Round-trip tests

### Week 5: Phase 6 (Edge Cases)
- Days 1-2: Data edge cases
- Days 3-4: Error handling
- Day 5: Cleanup and documentation

### Week 6: Coverage Improvement
- Days 1-3: Identify and fill coverage gaps
- Days 4-5: Final validation and documentation

### Week 7: Phase 7 (Performance - Optional)
- Days 1-3: Performance benchmarks
- Days 4-5: Optimization if needed

**Total Estimated Time:** 6-7 weeks for complete test suite

---

## Maintenance Strategy

### Continuous Testing
- Run tests on every commit (pre-commit hook)
- Run full suite in CI/CD pipeline
- Weekly coverage reports

### Test Updates
- Update tests when adding features
- Add regression tests for bugs
- Keep test data current

### Test Review
- Include test coverage in PR reviews
- Require tests for new features
- Maintain 80%+ coverage threshold

---

## Summary

This guide provides a comprehensive roadmap for completing the Palimpsest testing suite. The key phases are:

1. **Phase 4:** Integration tests (manager interactions)
2. **Phase 5:** Pipeline E2E tests (round-trip validation)
3. **Phase 6:** Edge cases and error handling
4. **Phase 7:** Performance optimization (optional)
5. **Coverage:** Improve from 23% to 80%+

Follow the implementation steps, use the code examples as templates, and iterate until all success criteria are met. The result will be a robust, well-tested system that enables confident refactoring and feature development.

**Next Step:** Start with Phase 4, Category A (Multi-Entity Creation Tests).
