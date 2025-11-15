# Palimpsest Testing Strategy

**Date:** 2025-11-12
**Version:** 1.0
**Status:** Planning Phase

---

## Executive Summary

This document outlines a comprehensive, modular testing strategy for the Palimpsest project. The approach follows a **bottom-up architecture** - starting with unit tests for foundational components and building up to integration and end-to-end tests.

### Goals:
- ✅ **Ensure correctness** of all database operations
- ✅ **Validate bidirectional pipeline** (YAML ↔ SQL round-trip)
- ✅ **Prevent regressions** in refactored code
- ✅ **Document expected behavior** through tests
- ✅ **Enable confident refactoring** for future changes

### Target Coverage:
- **Unit Tests:** 90%+ coverage of core logic
- **Integration Tests:** All manager interactions validated
- **Pipeline Tests:** Complete YAML ↔ SQL round-trip validated
- **Edge Cases:** All known edge cases tested

---

## Testing Architecture

### Test Pyramid Structure

```
                    ┌─────────────────┐
                    │   E2E Tests     │  ← 5% (Full pipeline workflows)
                    │   (10-20 tests) │
                ┌───┴─────────────────┴───┐
                │  Integration Tests      │  ← 20% (Manager interactions)
                │  (50-100 tests)         │
            ┌───┴─────────────────────────┴───┐
            │   Unit Tests                    │  ← 75% (Individual functions)
            │   (200-400 tests)               │
            └─────────────────────────────────┘
```

### Test Organization

```
tests/
├── conftest.py                    # Shared fixtures
├── fixtures/                      # Test data
│   ├── sample_entries/           # Sample markdown files
│   ├── expected_yaml/            # Expected YAML outputs
│   └── database_fixtures.py      # Database test data
├── unit/                         # Unit tests
│   ├── test_validators.py
│   ├── test_parsers.py
│   ├── test_md_utils.py
│   ├── test_fs_utils.py
│   ├── dataclasses/
│   │   ├── test_md_entry.py
│   │   └── test_txt_entry.py
│   └── database/
│       ├── managers/
│       │   ├── test_base_manager.py
│       │   ├── test_tag_manager.py
│       │   ├── test_person_manager.py
│       │   ├── test_event_manager.py
│       │   ├── test_date_manager.py
│       │   ├── test_location_manager.py
│       │   ├── test_reference_manager.py
│       │   ├── test_poem_manager.py
│       │   ├── test_manuscript_manager.py
│       │   └── test_entry_manager.py
│       ├── test_relationship_manager.py
│       ├── test_health_monitor.py
│       └── test_export_manager.py
├── integration/                  # Integration tests
│   ├── test_manager_interactions.py
│   ├── test_entry_creation_flow.py
│   ├── test_relationship_updates.py
│   └── test_database_consistency.py
└── e2e/                         # End-to-end tests
    ├── test_yaml2sql_pipeline.py
    ├── test_sql2yaml_pipeline.py
    ├── test_round_trip.py
    └── test_complete_workflow.py
```

---

## Test Phases (Implementation Order)

### Phase 1: Foundation (Week 1-2)
**Priority: CRITICAL**
**Estimated Tests: 80-100**

Build test infrastructure and validate core utilities.

#### 1.1 Test Infrastructure Setup
- [ ] Configure pytest with coverage
- [ ] Set up test database fixtures
- [ ] Create sample markdown files (10-15 diverse examples)
- [ ] Set up CI/CD integration (optional)
- [ ] Configure test database cleanup

#### 1.2 Core Utilities Testing
**Files to test:**
- `dev/core/validators.py`
- `dev/core/exceptions.py`
- `dev/utils/parsers.py`
- `dev/utils/md.py`
- `dev/utils/fs.py`

**Test Examples:**
```python
# test_validators.py
def test_normalize_date_with_string():
    assert DataValidator.normalize_date("2024-01-15") == date(2024, 1, 15)

def test_normalize_date_with_invalid_string():
    assert DataValidator.normalize_date("invalid") is None

def test_validate_required_fields_missing():
    with pytest.raises(ValidationError):
        DataValidator.validate_required_fields({}, ["name"])

# test_parsers.py
def test_extract_name_and_expansion():
    name, expansion = extract_name_and_expansion("Mtl (Montreal)")
    assert name == "Mtl"
    assert expansion == "Montreal"

def test_extract_context_refs_with_people():
    result = extract_context_refs("Dinner with @Alice at #Cafe")
    assert "Alice" in result["people"]
    assert "Cafe" in result["locations"]
```

**Success Criteria:**
- ✅ 90%+ coverage of validators
- ✅ All parsing edge cases tested
- ✅ All exceptions properly raised

---

### Phase 2: Dataclasses (Week 2-3)
**Priority: HIGH**
**Estimated Tests: 60-80**

Validate data structure transformations.

#### 2.1 MdEntry Testing
**File:** `dev/dataclasses/md_entry.py`

**Critical Tests:**
- YAML frontmatter parsing (all supported fields)
- Database metadata conversion
- Round-trip: YAML → MdEntry → Database → MdEntry → YAML
- Edge cases:
  - Missing optional fields
  - Empty metadata
  - Malformed dates
  - Complex people names (hyphens, aliases, full_name)
  - Nested locations with cities
  - Poems with/without revision_date

**Test Examples:**
```python
# test_md_entry.py
def test_from_file_basic(sample_md_file):
    entry = MdEntry.from_file(sample_md_file)
    assert entry.date == date(2024, 1, 15)
    assert entry.word_count > 0

def test_to_database_metadata_with_people():
    entry = MdEntry(
        date=date(2024, 1, 15),
        people=["Alice", "Bob (Robert Smith)"],
        # ...
    )
    metadata = entry.to_database_metadata()
    assert len(metadata["people"]) == 2
    assert metadata["people"][0]["name"] == "Alice"
    assert metadata["people"][1]["full_name"] == "Robert Smith"

def test_round_trip_preserves_data():
    # YAML → MdEntry → Database metadata → MdEntry → YAML
    original = MdEntry.from_file("sample.md")
    db_meta = original.to_database_metadata()
    reconstructed = MdEntry.from_database_metadata(db_meta)
    assert original == reconstructed
```

#### 2.2 TxtEntry Testing
**File:** `dev/dataclasses/txt_entry.py`

**Tests:**
- Parse 750words format
- Extract date, word_count, reading_time
- Handle legacy body offset
- Convert to minimal markdown

**Success Criteria:**
- ✅ All YAML field parsing tested
- ✅ Complex nested structures validated
- ✅ Round-trip consistency verified

---

### Phase 3: Database Managers (Week 3-5)
**Priority: CRITICAL**
**Estimated Tests: 150-200**

Test all CRUD operations and relationship management.

#### 3.1 Base Manager Testing
**File:** `dev/database/managers/base_manager.py`

**Tests:**
- `_get_or_create()` logic
- `_resolve_object()` with various types
- `_execute_with_retry()` retry logic
- Session and logger handling

#### 3.2 Individual Manager Testing
**Order:** Simple → Complex

**TagManager (Simplest)**
```python
# test_tag_manager.py
def test_create_tag(session):
    mgr = TagManager(session, None)
    tag = mgr.create({"tag": "python"})
    assert tag.tag == "python"
    assert tag.id is not None

def test_get_or_create_existing(session, tag):
    mgr = TagManager(session, None)
    tag2 = mgr.get_or_create("python")
    assert tag2.id == tag.id

def test_link_to_entry(session, tag, entry):
    mgr = TagManager(session, None)
    mgr.link_to_entry(tag, entry)
    assert tag in entry.tags

def test_duplicate_tag_raises_error(session):
    mgr = TagManager(session, None)
    mgr.create({"tag": "python"})
    with pytest.raises(DatabaseError):
        mgr.create({"tag": "python"})
```

**EventManager**
- Create, read, update, delete events
- Soft delete behavior
- Link/unlink entries and people
- Date range queries

**DateManager**
- MentionedDate CRUD
- Context parsing and storage
- Link to entries, locations, people
- Temporal queries

**LocationManager (Parent-Child)**
- City CRUD
- Location CRUD with parent city
- Get-or-create city helper
- Unique constraint validation

**PersonManager (Complex)**
- Person CRUD with soft delete
- Alias management
- name_fellow disambiguation
- Full_name handling
- Restore deleted persons

**ReferenceManager (Parent-Child)**
- ReferenceSource CRUD
- Reference CRUD with source
- ReferenceType and ReferenceMode enums
- Author validation

**PoemManager (Versioning)**
- Poem CRUD (titles not unique!)
- PoemVersion CRUD
- Hash-based deduplication
- Version timeline queries
- Content change detection

**ManuscriptManager (Complex)**
- ManuscriptEntry, ManuscriptPerson, ManuscriptEvent
- Arc and Theme management
- Status enum handling
- Query helpers (get_ready_entries, etc.)

**EntryManager (Most Complex)**
- Entry CRUD
- File hash management
- All relationship processing
- Incremental vs full updates
- Bulk create operations
- Optimized loading

**Test Pattern for All Managers:**
```python
class TestXManager:
    def test_create(self, session):
        """Test basic creation."""

    def test_get_by_id(self, session, entity):
        """Test retrieval by ID."""

    def test_get_by_attribute(self, session, entity):
        """Test retrieval by attribute."""

    def test_update(self, session, entity):
        """Test update operations."""

    def test_delete(self, session, entity):
        """Test deletion."""

    def test_relationships(self, session, entity):
        """Test M2M and 1-M relationships."""

    def test_validation_errors(self, session):
        """Test validation failures."""

    def test_edge_cases(self, session):
        """Test edge cases specific to this manager."""
```

**Success Criteria:**
- ✅ All CRUD operations tested
- ✅ All relationships validated
- ✅ Validation errors properly raised
- ✅ Edge cases handled

---

### Phase 4: Integration Tests (Week 5-6)
**Priority: HIGH**
**Estimated Tests: 50-70**

Test interactions between managers.

#### 4.1 Manager Interaction Tests
**File:** `tests/integration/test_manager_interactions.py`

**Scenarios:**
```python
def test_entry_with_all_relationships(db):
    """Create entry with people, locations, events, dates, references, poems."""
    with db.session_scope() as session:
        # Create entry with complex metadata
        entry = db.entries.create({
            "date": date(2024, 1, 15),
            "file_path": "/path/to/file.md",
            "people": [{"name": "Alice"}, {"name": "Bob", "full_name": "Robert Smith"}],
            "cities": ["Montreal"],
            "locations": [{"name": "Cafe X", "city": "Montreal"}],
            "events": ["thesis-defense"],
            "tags": ["writing", "research"],
            "dates": [{"date": "2024-06-01", "context": "Thesis exam"}],
            "references": [{
                "content": "Quote here",
                "source": {"title": "Book", "type": "book", "author": "Author"}
            }],
            "poems": [{
                "title": "My Poem",
                "content": "Roses are red...",
                "revision_date": date(2024, 1, 15)
            }],
        })

        # Verify all relationships created
        assert len(entry.people) == 2
        assert len(entry.locations) == 1
        assert len(entry.events) == 1
        assert len(entry.tags) == 2
        assert len(entry.dates) == 1
        assert len(entry.references) == 1
        assert len(entry.poems) == 1

def test_incremental_vs_full_update(db, entry):
    """Test incremental and full replacement update modes."""
    with db.session_scope() as session:
        # Incremental: add tags
        entry = db.entries.update(entry, {"tags": ["new-tag"]}, incremental=True)
        assert "new-tag" in [t.tag for t in entry.tags]
        assert len(entry.tags) == 3  # Original 2 + 1 new

        # Full: replace all tags
        entry = db.entries.update(entry, {"tags": ["only-tag"]}, incremental=False)
        assert len(entry.tags) == 1
        assert entry.tags[0].tag == "only-tag"

def test_person_with_multiple_entries_and_events(db):
    """Test person linked to multiple entries and events."""
    # Create person, link to 3 entries and 2 events
    # Verify bidirectional relationships
```

#### 4.2 Database Consistency Tests
**File:** `tests/integration/test_database_consistency.py`

**Tests:**
- Cascade deletes work correctly
- Orphaned records prevented
- Foreign key constraints enforced
- Unique constraints enforced
- Check constraints validated

**Success Criteria:**
- ✅ All manager interactions validated
- ✅ Complex multi-entity operations work
- ✅ Database constraints enforced

---

### Phase 5: Pipeline Tests (Week 6-7)
**Priority: CRITICAL**
**Estimated Tests: 40-60**

Test the complete YAML ↔ SQL bidirectional pipeline.

#### 5.1 yaml2sql Pipeline Tests
**File:** `tests/e2e/test_yaml2sql_pipeline.py`

**Test Cases:**
```python
def test_process_minimal_entry(db, tmp_path):
    """Test entry with only required fields."""
    md_file = tmp_path / "2024-01-15.md"
    md_file.write_text("""---
date: 2024-01-15
---
# Entry content
""")

    # Process file
    process_single_file(md_file, db)

    # Verify database
    entry = db.entries.get(entry_date=date(2024, 1, 15))
    assert entry is not None
    assert entry.file_path == str(md_file)

def test_process_complex_entry(db, tmp_path):
    """Test entry with all metadata fields."""
    md_file = create_complex_entry_file(tmp_path)  # Fixture

    # Process file
    process_single_file(md_file, db)

    # Verify all relationships created
    entry = db.entries.get(entry_date=...)
    assert len(entry.people) == 3
    assert len(entry.locations) == 2
    # ... verify all fields

def test_hash_based_skip(db, sample_entry_file):
    """Test that unchanged files are skipped."""
    # Process file first time
    process_single_file(sample_entry_file, db)

    # Process again without changes
    result = process_single_file(sample_entry_file, db, force=False)
    assert result.status == "skipped"

def test_update_existing_entry(db, sample_entry_file):
    """Test updating existing entry with changes."""
    # Process file
    process_single_file(sample_entry_file, db)

    # Modify file
    modify_entry_add_tag(sample_entry_file, "new-tag")

    # Process again
    process_single_file(sample_entry_file, db)

    # Verify update
    entry = db.entries.get(entry_date=...)
    assert "new-tag" in [t.tag for t in entry.tags]

def test_poem_content_field_bug_fixed(db, tmp_path):
    """Regression test for poem content field bug."""
    md_file = tmp_path / "2024-01-15.md"
    md_file.write_text("""---
date: 2024-01-15
poems:
  - title: Test Poem
    content: "Roses are red\\nViolets are blue"
    revision_date: 2024-01-15
---
# Entry
""")

    # Should not crash
    process_single_file(md_file, db)

    # Verify poem created
    entry = db.entries.get(entry_date=date(2024, 1, 15))
    assert len(entry.poems) == 1
    assert "Roses are red" in entry.poems[0].content
```

#### 5.2 sql2yaml Pipeline Tests
**File:** `tests/e2e/test_sql2yaml_pipeline.py`

**Test Cases:**
```python
def test_export_minimal_entry(db, tmp_path):
    """Test export of minimal entry."""
    # Create entry in database
    entry = create_minimal_entry(db)

    # Export
    export_entry_to_markdown(entry, tmp_path)

    # Verify file created
    md_file = tmp_path / "2024" / "2024-01-15.md"
    assert md_file.exists()

    # Parse YAML
    frontmatter, body = split_frontmatter(md_file.read_text())
    assert frontmatter["date"] == "2024-01-15"

def test_export_complex_entry(db, tmp_path):
    """Test export of entry with all relationships."""
    # Create complex entry
    entry = create_complex_entry_with_all_relations(db)

    # Export
    export_entry_to_markdown(entry, tmp_path)

    # Parse and verify all fields
    frontmatter, body = split_frontmatter(...)
    assert len(frontmatter["people"]) == 3
    assert frontmatter["city"] == "Montreal"
    # ... verify all fields

def test_preserve_body_content(db, tmp_path, existing_file):
    """Test that body content is preserved on export."""
    # Export should preserve existing body
    entry = db.entries.get(...)
    export_entry_to_markdown(entry, tmp_path, preserve_body=True)

    # Verify body unchanged
    new_content = (tmp_path / "2024" / "2024-01-15.md").read_text()
    assert "original body text" in new_content
```

#### 5.3 Round-Trip Tests (CRITICAL)
**File:** `tests/e2e/test_round_trip.py`

**Test Cases:**
```python
def test_round_trip_lossless(tmp_path):
    """Test that YAML → SQL → YAML is lossless."""
    # Create original markdown file
    original_file = create_sample_entry(tmp_path, "original.md")

    # Process to database
    db = create_test_db()
    process_single_file(original_file, db)

    # Export back to markdown
    export_dir = tmp_path / "export"
    entry = db.entries.get(entry_date=...)
    export_entry_to_markdown(entry, export_dir)

    # Compare frontmatter (ignore body)
    original_fm, _ = split_frontmatter(original_file.read_text())
    exported_fm, _ = split_frontmatter(...)

    # Should be semantically equivalent
    assert_frontmatter_equivalent(original_fm, exported_fm)

def test_round_trip_all_field_types(tmp_path):
    """Test round-trip with every supported field type."""
    # Create entry with ALL fields
    original = create_entry_with_all_fields(tmp_path)

    # YAML → SQL → YAML
    db = create_test_db()
    process_single_file(original, db)
    entry = db.entries.get(...)
    exported = export_entry_to_markdown(entry, tmp_path / "export")

    # Parse both
    original_data = MdEntry.from_file(original)
    exported_data = MdEntry.from_file(exported)

    # Compare all fields
    assert original_data.date == exported_data.date
    assert original_data.people == exported_data.people
    assert original_data.locations == exported_data.locations
    # ... compare all fields

def test_round_trip_batch(tmp_path):
    """Test round-trip with batch of entries."""
    # Create 50 diverse entries
    entries = create_diverse_entry_set(tmp_path, count=50)

    # Process all to database
    db = create_test_db()
    for entry_file in entries:
        process_single_file(entry_file, db)

    # Export all
    export_dir = tmp_path / "export"
    export_all_entries(db, export_dir)

    # Verify all exported
    assert len(list(export_dir.rglob("*.md"))) == 50

    # Sample check on 10 random entries
    for entry_file in random.sample(entries, 10):
        verify_round_trip_consistency(entry_file, export_dir)
```

**Success Criteria:**
- ✅ All YAML fields correctly processed to database
- ✅ All database fields correctly exported to YAML
- ✅ Round-trip is lossless (semantic equivalence)
- ✅ Hash-based change detection works
- ✅ Batch processing handles errors gracefully

---

### Phase 6: Edge Cases & Error Handling (Week 7-8)
**Priority: MEDIUM**
**Estimated Tests: 40-50**

Test error conditions and edge cases.

#### 6.1 Edge Case Tests
```python
def test_empty_optional_fields(db):
    """Test entry with all optional fields empty."""

def test_special_characters_in_names(db):
    """Test names with unicode, accents, special chars."""

def test_very_long_content(db):
    """Test entry with very long text (10,000+ words)."""

def test_malformed_dates(db):
    """Test various malformed date formats."""

def test_duplicate_relationships(db):
    """Test adding same relationship twice."""

def test_circular_related_entries(db):
    """Test entries referencing each other."""

def test_poem_without_revision_date(db):
    """Test poem missing revision_date (should default)."""

def test_location_without_city(db):
    """Test location string without city context."""

def test_name_fellow_disambiguation(db):
    """Test two people with same name (full_name required)."""
```

#### 6.2 Error Handling Tests
```python
def test_database_connection_failure():
    """Test graceful handling of DB connection failure."""

def test_file_not_found_error():
    """Test handling of missing source file."""

def test_invalid_yaml_syntax():
    """Test handling of malformed YAML."""

def test_transaction_rollback():
    """Test that errors trigger rollback."""

def test_concurrent_modifications():
    """Test handling of concurrent entry updates."""
```

**Success Criteria:**
- ✅ All edge cases handled gracefully
- ✅ Errors don't corrupt database
- ✅ Helpful error messages provided

---

### Phase 7: Performance & Optimization (Week 8+)
**Priority: LOW**
**Estimated Tests: 10-20**

Test performance with large datasets.

#### 7.1 Performance Tests
```python
def test_batch_import_performance(benchmark):
    """Test import of 1000 entries."""

def test_query_optimization_n_plus_one(db):
    """Verify no N+1 query problems in eager loading."""

def test_export_large_dataset(db):
    """Test export of 5000+ entries."""
```

**Success Criteria:**
- ✅ Batch operations performant
- ✅ No N+1 query problems
- ✅ Large exports complete successfully

---

## Test Fixtures & Sample Data

### Essential Fixtures

#### conftest.py
```python
import pytest
from pathlib import Path
from datetime import date
from dev.database.manager import PalimpsestDB

@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory):
    """Create temporary test database."""
    return tmp_path_factory.mktemp("test_db") / "test.db"

@pytest.fixture
def db(test_db_path):
    """Create fresh database for each test."""
    db = PalimpsestDB(
        db_path=test_db_path,
        alembic_dir=Path("alembic"),
        log_dir=Path("logs"),
        backup_dir=Path("backups")
    )
    # Initialize schema
    db.init_database()

    yield db

    # Cleanup
    db.close()
    if test_db_path.exists():
        test_db_path.unlink()

@pytest.fixture
def session(db):
    """Provide database session."""
    with db.session_scope() as sess:
        yield sess

@pytest.fixture
def sample_entry_minimal(tmp_path):
    """Create minimal sample entry."""
    md_file = tmp_path / "2024-01-15.md"
    md_file.write_text("""---
date: 2024-01-15
---
# Monday, January 15, 2024

This is a minimal entry.
""")
    return md_file

@pytest.fixture
def sample_entry_complex(tmp_path):
    """Create complex sample entry with all fields."""
    md_file = tmp_path / "2024-01-15.md"
    md_file.write_text("""---
date: 2024-01-15
word_count: 850
reading_time: 4.2

city: Montreal
locations:
  - Cafe X
  - Library

people:
  - Alice
  - "@Bob (Robert Smith)"

tags:
  - writing
  - research

events:
  - thesis-defense

dates:
  - 2024-06-01 (thesis exam)

references:
  - content: "Quote here"
    speaker: Famous Person
    source:
      title: Important Book
      type: book
      author: Author Name

poems:
  - title: My Poem
    content: |
      Roses are red
      Violets are blue
    revision_date: 2024-01-15

epigraph: "Opening quote"
epigraph_attribution: Philosopher

manuscript:
  status: draft
  edited: false
  themes:
    - identity
    - memory
---
# Monday, January 15, 2024

Complex entry content here.
""")
    return md_file
```

### Sample Data Sets

Create diverse test entries covering:
1. **Minimal entries** - Only required fields
2. **Complex entries** - All fields populated
3. **Edge case entries** - Special characters, long text, etc.
4. **Real-world examples** - Based on actual usage patterns
5. **Regression test entries** - For known bugs (poem content field)

---

## Tools & Configuration

### pytest Configuration
```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    --verbose
    --cov=dev
    --cov-report=html
    --cov-report=term-missing
    --cov-fail-under=80
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    slow: Slow-running tests
```

### Coverage Configuration
```ini
# .coveragerc
[run]
source = dev
omit =
    */tests/*
    */conftest.py
    */__pycache__/*

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
    if __name__ == .__main__.:
    if TYPE_CHECKING:
```

### Required Dependencies
```python
# requirements-test.txt
pytest>=7.4.0
pytest-cov>=4.1.0
pytest-mock>=3.11.0
pytest-benchmark>=4.0.0  # For performance tests
pytest-xdist>=3.3.0      # For parallel test execution
factory-boy>=3.3.0       # For test data factories
faker>=19.0.0            # For generating realistic test data
freezegun>=1.2.0         # For time-based tests
```

---

## Success Metrics

### Coverage Goals
- **Overall Coverage:** 85%+
- **Core Utilities:** 95%+
- **Dataclasses:** 90%+
- **Database Managers:** 90%+
- **Pipeline Scripts:** 85%+

### Quality Metrics
- All tests pass consistently
- No flaky tests
- Test execution < 5 minutes (unit + integration)
- E2E tests < 10 minutes
- Zero known bugs in tested code

### Documentation
- Each test has clear docstring
- Complex tests have comments explaining logic
- Test naming follows pattern: `test_<what>_<condition>_<expected>`

---

## Implementation Timeline

### Week 1-2: Foundation
- Set up test infrastructure
- Write core utility tests
- Achieve 90%+ coverage of validators, parsers, utils

### Week 3-5: Managers
- Test all 10 database managers
- Achieve 90%+ coverage of manager code
- Validate all CRUD operations

### Week 6-7: Pipelines
- Test yaml2sql and sql2yaml
- Test round-trip consistency
- Achieve 85%+ coverage of pipeline code

### Week 8: Refinement
- Edge cases and error handling
- Performance tests
- Documentation
- CI/CD integration

**Total Estimated Effort:** 6-8 weeks (part-time)
**Total Estimated Tests:** 300-500 tests

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
- Maintain 85%+ coverage threshold

---

## Appendix: Test Examples Reference

### Unit Test Template
```python
class TestComponentName:
    """Test suite for ComponentName."""

    def test_basic_operation(self, session):
        """Test basic operation succeeds."""
        # Arrange
        component = Component()

        # Act
        result = component.do_something()

        # Assert
        assert result == expected_value

    def test_edge_case(self, session):
        """Test edge case is handled."""
        # Test implementation

    def test_error_condition(self, session):
        """Test error is raised for invalid input."""
        with pytest.raises(ExpectedError):
            component.do_invalid_thing()
```

### Integration Test Template
```python
def test_multi_component_workflow(db):
    """Test workflow involving multiple components."""
    with db.session_scope() as session:
        # Create entities using multiple managers
        person = db.people.create({"name": "Alice"})
        event = db.events.create({"event": "conference"})

        # Link them
        db.events.link_to_person(event, person)

        # Verify relationships
        assert person in event.people
        assert event in person.events
```

---

**End of Testing Strategy Document**

*This is a living document and should be updated as testing progresses.*
