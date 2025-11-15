# Testing Improvements: Action Plan

**Created:** 2025-11-13
**Current Coverage:** 44%
**Target Coverage:** 80%
**Status:** 24 tests failing, 807 passing

---

## Immediate Actions Required

### 🔴 CRITICAL: Fix Failing Tests (Week 1)

**24 tests are currently failing** due to bugs in the codebase. These must be fixed before proceeding with new tests.

#### Bug 1: Missing Database Columns

**Issue:** Several models are missing `notes` columns that tests expect

**Affected Models:**
- `Person` model - missing `notes` column (5 test failures)
- `ManuscriptEntry` model - missing `notes` column (2 test failures)
- `ManuscriptPerson` model - missing `character_description` column (1 test failure)

**Fix:**
Create Alembic migration to add missing columns:

```python
# alembic/versions/xxxx_add_notes_fields.py
def upgrade():
    # Add notes to Person
    op.add_column('people',
        sa.Column('notes', sa.Text(), nullable=True)
    )

    # Add notes to ManuscriptEntry
    op.add_column('manuscript_entries',
        sa.Column('notes', sa.Text(), nullable=True)
    )

    # Add character_description to ManuscriptPerson
    op.add_column('manuscript_people',
        sa.Column('character_description', sa.Text(), nullable=True)
    )
```

**Tests affected:**
- `tests/integration/test_sql_to_wiki.py::TestEditableFields::test_placeholder_for_empty_notes`
- `tests/integration/test_wiki_to_sql.py::TestPersonImport::test_import_person_notes`
- `tests/integration/test_wiki_to_sql.py::TestPersonImport::test_import_preserves_other_fields`
- `tests/integration/test_wiki_to_sql.py::TestRoundTrip::test_round_trip_person_notes`
- `tests/integration/test_wiki_to_sql.py::TestManuscriptImport::test_import_manuscript_entry_notes`
- `tests/integration/test_wiki_to_sql.py::TestManuscriptImport::test_import_manuscript_character`
- `tests/integration/test_wiki_to_sql.py::TestRoundTrip::test_round_trip_manuscript_notes`
- `tests/integration/test_sql_to_wiki.py::TestPersonExport::test_export_minimal_person`

**Priority:** 🔴 CRITICAL
**Effort:** 2 hours

---

#### Bug 2: Method Signature Mismatch

**Issue:** `Person.from_database()` missing required `journal_dir` argument

**Location:** `dev/dataclasses/wiki_person.py`

**Fix:**
Either add `journal_dir` parameter to method signature, or update test calls.

Check the method signature:
```python
# Current (assumed broken):
@classmethod
def from_database(cls, db_person: DBPerson, wiki_dir: Path):
    ...

# Should be:
@classmethod
def from_database(cls, db_person: DBPerson, wiki_dir: Path, journal_dir: Path):
    ...
```

**Tests affected:**
- `tests/integration/test_sql_to_wiki.py::TestPersonExport::test_export_minimal_person`
- `tests/integration/test_sql_to_wiki.py::TestPersonExport::test_export_person_with_full_name`
- `tests/integration/test_sql_to_wiki.py::TestWikiFormatting::test_breadcrumbs`
- `tests/integration/test_sql_to_wiki.py::TestEditableFields::test_notes_section_present`

**Priority:** 🔴 CRITICAL
**Effort:** 1 hour

---

#### Bug 3: Test Fixture Issues

**Issue:** UNIQUE constraint violations due to duplicate file paths in tests

**Location:** Multiple test files

**Fix:**
Ensure each test uses unique file paths or properly cleans up:

```python
# Before (broken):
entry = Entry(file_path="/tmp/pytest-*/entry1.md", ...)

# After (fixed):
import uuid
unique_id = uuid.uuid4()
entry = Entry(file_path=f"/tmp/pytest-{unique_id}/entry1.md", ...)

# OR use proper fixtures:
@pytest.fixture
def unique_file_path(tmp_path):
    return tmp_path / f"entry_{uuid.uuid4()}.md"
```

**Tests affected:**
- `tests/integration/test_search.py::TestSearchEngine::test_word_count_filter`
- `tests/integration/test_search.py::TestSearchEngine::test_manuscript_filter`
- `tests/integration/test_search.py::TestSearchEngine::test_sorting`
- `tests/integration/test_sql_to_wiki.py::TestPersonExport::test_export_person_with_entries`
- `tests/integration/test_sql_to_wiki.py::TestEntryExport::test_export_entry_with_navigation`

**Priority:** 🔴 CRITICAL
**Effort:** 2 hours

---

#### Bug 4: Event.display_name Read-Only Property

**Issue:** Code tries to set read-only property `display_name`

**Location:** `dev/database/models.py` or export code

**Fix:**
Make property writable or fix export code to not set it:

```python
# Option 1: Make property writable
@hybrid_property
def display_name(self):
    return self._display_name or self.name

@display_name.setter
def display_name(self, value):
    self._display_name = value

# Option 2: Fix export code to skip read-only properties
```

**Tests affected:**
- `tests/integration/test_db_to_yaml.py::TestRelationshipExport::test_export_entry_with_events_and_tags`

**Priority:** 🟡 HIGH
**Effort:** 1 hour

---

#### Bug 5: Data Preservation Issues

**Issue:** Word count not preserved during round-trip export/import

**Location:** `dev/pipeline/sql2yaml.py`

**Fix:**
Ensure updated values are exported correctly:

```python
# Check that export uses current database values, not original YAML values
```

**Tests affected:**
- `tests/integration/test_db_to_yaml.py::TestContentPreservation::test_preserve_existing_body`
- `tests/integration/test_db_to_yaml.py::TestRoundTrip::test_round_trip_basic_entry`

**Priority:** 🟡 HIGH
**Effort:** 2 hours

---

#### Bug 6: AI Test Dependencies

**Issue:** Tests failing when NumPy/AI dependencies unavailable

**Location:** `tests/integration/test_ai_extraction.py`

**Fix:**
Improve dependency checking and skip properly:

```python
import pytest
import sys

HAS_NUMPY = "numpy" in sys.modules
HAS_SPACY = "spacy" in sys.modules

@pytest.mark.skipif(not HAS_NUMPY, reason="NumPy not available")
def test_ai_feature():
    ...
```

**Tests affected:**
- `tests/integration/test_ai_extraction.py::TestDependencyChecks::test_check_extractor_dependencies`
- `tests/integration/test_ai_extraction.py::TestDependencyChecks::test_check_semantic_dependencies`
- `tests/integration/test_ai_extraction.py::TestCostEstimation::test_estimate_cost_haiku`
- `tests/integration/test_ai_extraction.py::TestCostEstimation::test_estimate_cost_sonnet`

**Priority:** 🟢 MEDIUM
**Effort:** 1 hour

---

### 📊 Expected Result After Phase 1

```
Before: 807 passed, 24 failed
After:  831 passed, 0 failed ✅
Coverage: 44% (unchanged)
```

**Total Effort:** 8-10 hours

---

## High-Priority Test Gaps (Weeks 2-4)

### 1. Wiki Bidirectional Sync Testing

**Current Coverage:** 13% (wiki2sql.py), 42% (sql2yaml.py)
**Target Coverage:** 80%
**Priority:** 🔴 CRITICAL

**Missing Tests:**
- Wiki → SQL import for all entity types (cities, events, locations, tags, themes)
- Field ownership rules enforcement
- Note preservation across sync cycles
- Navigation generation
- Index page generation
- Breadcrumb creation

**Test Files to Create:**
```
tests/integration/test_wiki_sync_comprehensive.py
tests/integration/test_wiki_field_ownership.py
tests/integration/test_wiki_navigation.py
```

**Estimated Tests:** 50-80 new tests
**Effort:** 12-16 hours

---

### 2. Database Manager Core Testing

**Current Coverage:** 38%
**Target Coverage:** 80%
**Priority:** 🔴 CRITICAL

**Missing Tests:**
- Session management and lifecycle
- Transaction handling and rollback
- Migration operations
- Database initialization
- Connection pooling
- Error recovery

**Test Files to Create:**
```
tests/unit/database/test_manager_core.py
tests/integration/test_database_lifecycle.py
tests/integration/test_database_migrations.py
```

**Estimated Tests:** 40-60 new tests
**Effort:** 10-14 hours

---

### 3. Export Manager Testing

**Current Coverage:** 14%
**Target Coverage:** 60%
**Priority:** 🔴 CRITICAL

**Missing Tests:**
- CSV export for all entity types
- JSON export with proper formatting
- Analytics report generation
- Full data backup
- Incremental export
- Export with filters

**Test Files to Create:**
```
tests/integration/test_csv_export.py
tests/integration/test_json_export.py
tests/integration/test_analytics_export.py
```

**Estimated Tests:** 30-50 new tests
**Effort:** 8-12 hours

---

### 4. Health Monitoring Testing

**Current Coverage:** 13%
**Target Coverage:** 60%
**Priority:** 🟡 HIGH

**Missing Tests:**
- Database health checks
- Integrity validation
- Orphan detection
- Relationship verification
- Fix operations
- Health report generation

**Test Files to Create:**
```
tests/integration/test_health_monitor.py
tests/integration/test_integrity_checks.py
```

**Estimated Tests:** 25-40 new tests
**Effort:** 8-10 hours

---

### 5. Backup System Testing

**Current Coverage:** 16%
**Target Coverage:** 70%
**Priority:** 🔴 CRITICAL

**Missing Tests:**
- Database backup creation
- Full data backup
- Backup restoration
- Backup listing
- Backup cleanup
- Incremental backups

**Test Files to Create:**
```
tests/integration/test_backup_system.py
tests/integration/test_backup_restore.py
```

**Estimated Tests:** 20-35 new tests
**Effort:** 6-10 hours

---

### 📊 Expected Result After Phase 2

```
Coverage: 44% → 60%
New Tests: ~200-300
Total Tests: ~1,100
```

**Total Effort:** 50-62 hours

---

## Medium-Priority Test Gaps (Weeks 5-7)

### 6. PDF Builder Testing

**Current Coverage:** 0%
**Target Coverage:** 60%
**Priority:** 🟡 HIGH

**Challenges:**
- Requires pandoc (system dependency)
- Requires LaTeX/Tectonic
- Requires fonts
- Large output files

**Strategy:**
- Mock pandoc calls for unit tests
- Integration tests with actual pandoc (CI may skip)
- Test LaTeX template generation
- Test annotation generation
- Validate PDF metadata

**Test Files to Create:**
```
tests/unit/builders/test_pdfbuilder_unit.py
tests/integration/test_pdfbuilder_integration.py  # May skip in CI
```

**Estimated Tests:** 25-40 new tests
**Effort:** 10-14 hours

---

### 7. TXT Builder Testing

**Current Coverage:** 0%
**Target Coverage:** 60%
**Priority:** 🟡 HIGH

**Missing Tests:**
- Text building from markdown
- Formatting options
- Year-based compilation
- Metadata inclusion

**Test Files to Create:**
```
tests/unit/builders/test_txtbuilder.py
tests/integration/test_txtbuilder_integration.py
```

**Estimated Tests:** 15-25 new tests
**Effort:** 6-8 hours

---

### 8. CLI Command Testing

**Current Coverage:** 0%
**Target Coverage:** 50%
**Priority:** 🟡 HIGH

**Missing Tests:**
- journal CLI commands
- metadb CLI commands
- palimpsest search CLI
- palimpsest AI CLI
- Exit codes
- Error messages
- Help text

**Strategy:**
- Use Click's CliRunner for testing
- Mock file system operations
- Mock database operations
- Capture output and validate

**Test Files to Create:**
```
tests/integration/test_journal_cli.py
tests/integration/test_metadb_cli.py
tests/integration/test_search_cli.py
tests/integration/test_ai_cli.py
```

**Estimated Tests:** 60-100 new tests
**Effort:** 12-18 hours

---

### 📊 Expected Result After Phase 3

```
Coverage: 60% → 70%
New Tests: ~100-165
Total Tests: ~1,300
```

**Total Effort:** 28-40 hours

---

## Lower-Priority Test Gaps (Weeks 8-10)

### 9. Wiki Dataclass Testing

**Current Coverage:** 22-54%
**Target Coverage:** 70%
**Priority:** 🟢 MEDIUM

**Missing Tests:**
- from_file() methods for all entity types
- to_wiki() methods for all entity types
- from_database() methods for all entity types
- Field validation
- Format preservation

**Estimated Tests:** 80-120 new tests
**Effort:** 12-16 hours

---

### 10. Manuscript Dataclass Testing

**Current Coverage:** 0-44%
**Target Coverage:** 70%
**Priority:** 🟢 MEDIUM

**Missing Tests:**
- Arc dataclass (0%)
- Event dataclass (0%)
- Theme dataclass (0%)
- Character dataclass (44%)
- Entry dataclass (81% - good!)

**Estimated Tests:** 40-60 new tests
**Effort:** 8-12 hours

---

### 11. MD Entry Dataclass Testing

**Current Coverage:** 47%
**Target Coverage:** 75%
**Priority:** 🟢 MEDIUM

**Missing Tests:**
- Complex YAML parsing
- All metadata types
- Validation rules
- Edge cases

**Estimated Tests:** 30-50 new tests
**Effort:** 6-10 hours

---

### 📊 Expected Result After Phase 4

```
Coverage: 70% → 78%
New Tests: ~150-230
Total Tests: ~1,550
```

**Total Effort:** 26-38 hours

---

## Optional Test Coverage (Future)

### 12. AI Feature Testing

**Current Coverage:** 0-38%
**Target Coverage:** 50%
**Priority:** 🟢 LOW (optional features)

**Strategy:**
- Mock LLM APIs (don't use real API calls)
- Test extractors with sample data
- Test semantic search with small embeddings
- Skip when dependencies unavailable

**Effort:** 8-12 hours

---

### 13. Logging & Utilities

**Current Coverage:** 23-50%
**Target Coverage:** 80%
**Priority:** 🟢 LOW

**Effort:** 4-6 hours

---

## Test Infrastructure Improvements

### Needed Fixtures

1. **Builder Test Fixtures**
   ```python
   @pytest.fixture
   def mock_pandoc():
       """Mock pandoc command"""

   @pytest.fixture
   def sample_latex_template():
       """Sample LaTeX template"""
   ```

2. **CLI Test Fixtures**
   ```python
   @pytest.fixture
   def cli_runner():
       """Click test runner"""
       return CliRunner()

   @pytest.fixture
   def mock_db_path(tmp_path):
       """Temporary database for CLI tests"""
   ```

3. **Wiki Test Fixtures**
   ```python
   @pytest.fixture
   def sample_wiki_pages():
       """Complete set of sample wiki pages"""

   @pytest.fixture
   def wiki_navigation_data():
       """Data for navigation testing"""
   ```

4. **Integration Test Helpers**
   ```python
   @pytest.fixture
   def full_pipeline_data():
       """Complete pipeline test data"""

   @pytest.fixture
   def large_dataset():
       """Large dataset for performance tests"""
   ```

---

## Summary Timeline

### Week 1: Fix Bugs
- Fix 24 failing tests
- Add missing database columns
- Fix method signatures
- Fix test fixtures
- **Result:** 831 tests passing, 0 failing

### Weeks 2-4: Critical Coverage (Phase 2)
- Wiki sync testing (12-16 hours)
- Database manager testing (10-14 hours)
- Export manager testing (8-12 hours)
- Health monitor testing (8-10 hours)
- Backup system testing (6-10 hours)
- **Result:** 60% coverage

### Weeks 5-7: High-Priority Features (Phase 3)
- PDF builder testing (10-14 hours)
- TXT builder testing (6-8 hours)
- CLI command testing (12-18 hours)
- **Result:** 70% coverage

### Weeks 8-10: Dataclasses (Phase 4)
- Wiki dataclasses (12-16 hours)
- Manuscript dataclasses (8-12 hours)
- MD entry dataclass (6-10 hours)
- **Result:** 78% coverage

### Future: Optional Features
- AI features (8-12 hours)
- Logging & utilities (4-6 hours)
- **Result:** 82% coverage

---

## Recommended Approach

### Option A: Reach 80% Threshold (Recommended)
**Timeline:** 10-12 weeks
**Effort:** 120-150 hours
**Coverage:** 44% → 80%+
**Tests:** 831 → 2,000+

**Includes:**
- All bug fixes
- All critical features
- All high-priority features
- All dataclasses
- Some optional features

### Option B: Critical Only (Minimum Viable)
**Timeline:** 4-5 weeks
**Effort:** 60-72 hours
**Coverage:** 44% → 60%
**Tests:** 831 → 1,100

**Includes:**
- All bug fixes
- Wiki sync
- Database manager
- Export manager
- Health monitor
- Backup system

### Option C: Focus on Core Features
**Timeline:** 7-8 weeks
**Effort:** 88-112 hours
**Coverage:** 44% → 70%
**Tests:** 831 → 1,300

**Includes:**
- All bug fixes
- All Phase 2 (critical)
- All Phase 3 (builders & CLI)

---

## Next Steps

1. **Immediate (This Week):**
   - [ ] Fix 24 failing tests
   - [ ] Create database migration for missing columns
   - [ ] Fix method signatures
   - [ ] Improve test fixtures

2. **Short Term (Next 2-4 Weeks):**
   - [ ] Implement wiki sync tests
   - [ ] Implement database manager tests
   - [ ] Implement export/health/backup tests

3. **Medium Term (Next 5-10 Weeks):**
   - [ ] Implement builder tests
   - [ ] Implement CLI tests
   - [ ] Implement dataclass tests

4. **Long Term (Future):**
   - [ ] Implement AI feature tests
   - [ ] Implement optional utility tests
   - [ ] Continuous test maintenance

---

## Codecov Setup

Once tests are fixed and coverage improves:

1. **Sign up:** https://codecov.io (free for open source)
2. **Enable repository:** soffiafdz/palimpsest
3. **Get token:** Repository Settings → Codecov Settings
4. **Add secret:** GitHub Settings → Secrets → `CODECOV_TOKEN`
5. **Done:** Workflows already configured, badges will auto-update

---

**Created:** 2025-11-13
**Status:** Ready for implementation
**Recommended:** Start with Option A (80% threshold)
