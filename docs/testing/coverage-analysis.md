# Test Coverage Analysis Report

**Date:** 2025-11-13
**Total Coverage:** 44% (4,563 / 10,317 statements)
**Test Results:** 807 passed, 24 failed, 14 skipped
**Execution Time:** 4 minutes 4 seconds

---

## Executive Summary

The Palimpsest project has a **44% test coverage** across all tests (unit + integration). While this is below the configured 80% threshold, the coverage is unevenly distributed with some modules well-tested and others completely untested.

### Key Findings:

✅ **Well-Tested Modules (90%+ coverage):**
- `dev/core/validators.py` - 98%
- `dev/core/paths.py` - 92%
- `dev/core/exceptions.py` - 100%
- `dev/database/managers/date_manager.py` - 94%
- `dev/database/managers/event_manager.py` - 90%
- `dev/database/managers/manuscript_manager.py` - 89%
- `dev/database/decorators.py` - 92%
- `dev/utils/fs.py` - 100%
- `dev/utils/md.py` - 98%
- `dev/utils/parsers.py` - 100%
- `dev/utils/txt.py` - 100%
- `dev/dataclasses/txt_entry.py` - 92%

⚠️ **Moderately Tested (40-80% coverage):**
- `dev/database/manager.py` - 38%
- `dev/database/models.py` - 61%
- `dev/database/models_manuscript.py` - 65%
- `dev/database/search.py` - 68%
- `dev/database/search_index.py` - 85%
- `dev/database/managers/person_manager.py` - 63%
- `dev/database/managers/location_manager.py` - 68%
- `dev/dataclasses/md_entry.py` - 47%
- `dev/dataclasses/wiki_person.py` - 47%

❌ **Untested/Low Coverage (0-20% coverage):**
- All NLP modules (0-38%)
- All builder modules (0%)
- All CLI modules (0%)
- Most wiki dataclasses (0-26%)
- Pipeline export/import (13-42%)

---

## Coverage Breakdown by Component

### 1. Core Modules (Excellent: 60-100%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **validators.py** | 98% | 3 lines | Low |
| **exceptions.py** | 100% | 0 lines | N/A |
| **paths.py** | 92% | 3 lines | Low |
| **cli_stats.py** | 46% | 36 lines | Medium |
| **cli_utils.py** | 50% | 3 lines | Low |
| **logging_manager.py** | 23% | 63 lines | High |
| **backup_manager.py** | 16% | 137 lines | High |
| **temporal_files.py** | 19% | 54 lines | High |

**Analysis:**
- Data validation and utilities are well-tested
- Backup, logging, and temporal file management need tests
- CLI utilities partially covered

### 2. Database Core (Variable: 13-92%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **manager.py** | 38% | 261 lines | **CRITICAL** |
| **models.py** | 61% | 229 lines | High |
| **models_manuscript.py** | 65% | 76 lines | Medium |
| **decorators.py** | 92% | 4 lines | Low |
| **search.py** | 68% | 62 lines | Medium |
| **search_index.py** | 85% | 13 lines | Low |
| **query_analytics.py** | 29% | 126 lines | High |
| **query_optimizer.py** | 56% | 37 lines | Medium |
| **cli.py** | 0% | 473 lines | High |
| **export_manager.py** | 14% | 225 lines | **CRITICAL** |
| **health_monitor.py** | 13% | 234 lines | **CRITICAL** |
| **cleanup_manager.py** | 0% | 22 lines | High |
| **refactor_manager.py** | 0% | 49 lines | High |

**Analysis:**
- Database manager (manager.py) is partially tested but missing critical paths
- CLI commands completely untested (0%)
- Export, health monitoring, and cleanup are severely undertested
- Models have reasonable coverage but property accessors are often untested

### 3. Database Managers (Good: 58-94%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **base_manager.py** | 69% | 18 lines | Medium |
| **date_manager.py** | 94% | 10 lines | **LOW** ✅ |
| **entry_manager.py** | 58% | 160 lines | High |
| **event_manager.py** | 90% | 22 lines | **LOW** ✅ |
| **location_manager.py** | 68% | 82 lines | Medium |
| **manuscript_manager.py** | 89% | 28 lines | **LOW** ✅ |
| **person_manager.py** | 63% | 112 lines | Medium |
| **poem_manager.py** | 69% | 73 lines | Medium |
| **reference_manager.py** | 78% | 47 lines | Low |
| **tag_manager.py** | 74% | 33 lines | Low |

**Analysis:**
- Most managers are well-tested (60-94%)
- Date, event, and manuscript managers excellent (90%+)
- Entry manager needs more coverage (58%)
- Person and location managers need edge case testing

### 4. Dataclasses (Mixed: 0-92%)

#### Text/Markdown Entry Classes (Good)
| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **txt_entry.py** | 92% | 12 lines | Low |
| **md_entry.py** | 47% | 377 lines | High |

#### Wiki Entity Classes (Poor: 0-66%)
| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **wiki_entity.py** | 66% | 13 lines | Medium |
| **wiki_entry.py** | 54% | 118 lines | High |
| **wiki_person.py** | 47% | 101 lines | High |
| **wiki_character.py** | 44% | 52 lines | High |
| **wiki_city.py** | 22% | 110 lines | **CRITICAL** |
| **wiki_event.py** | 24% | 110 lines | **CRITICAL** |
| **wiki_location.py** | 24% | 91 lines | **CRITICAL** |
| **wiki_poem.py** | 26% | 73 lines | High |
| **wiki_reference.py** | 26% | 76 lines | High |
| **wiki_tag.py** | 28% | 67 lines | High |
| **wiki_theme.py** | 26% | 79 lines | High |

#### Manuscript Classes (Poor: 0-81%)
| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **manuscript_entry.py** | 81% | 23 lines | Low |
| **manuscript_character.py** | 44% | 52 lines | High |
| **manuscript_arc.py** | 0% | 103 lines | **CRITICAL** |
| **manuscript_event.py** | 0% | 90 lines | **CRITICAL** |
| **manuscript_theme.py** | 0% | 78 lines | **CRITICAL** |

**Analysis:**
- txt_entry well-tested, md_entry needs more coverage
- Wiki dataclasses have very low coverage (22-54%)
- Manuscript dataclasses mostly untested (0-44%)
- These classes handle critical data transformation logic

### 5. Pipeline Modules (Poor: 0-42%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **sql2yaml.py** | 42% | 103 lines | High |
| **wiki2sql.py** | 13% | 373 lines | **CRITICAL** |

**Analysis:**
- Export to YAML partially tested
- Import from Wiki severely undertested (13%)
- Critical for bidirectional sync functionality

### 6. NLP Modules (Poor: 0-38%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **extractors.py** | 38% | 81 lines | Medium |
| **semantic_search.py** | 18% | 130 lines | High |
| **claude_assistant.py** | 0% | 108 lines | Low |
| **openai_assistant.py** | 0% | 96 lines | Low |

**Analysis:**
- NLP features are optional but largely untested
- Extractors have some coverage (38%)
- LLM assistants completely untested (require API keys)
- Semantic search needs more coverage

### 7. Builders (Critical: 0%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **pdfbuilder.py** | 0% | 213 lines | **CRITICAL** |
| **txtbuilder.py** | 0% | 205 lines | **CRITICAL** |
| **base.py** | 0% | 29 lines | High |

**Analysis:**
- PDF and text builders completely untested
- These are core features for the project
- Requires pandoc and other system dependencies

### 8. Utils (Excellent: 41-100%)

| Module | Coverage | Missing Lines | Priority |
|--------|----------|---------------|----------|
| **fs.py** | 100% | 0 lines | N/A ✅ |
| **md.py** | 98% | 1 line | Low |
| **parsers.py** | 100% | 0 lines | N/A ✅ |
| **txt.py** | 100% | 0 lines | N/A ✅ |
| **wiki.py** | 41% | 58 lines | High |
| **wiki_parser.py** | 42% | 54 lines | High |

**Analysis:**
- File system, markdown, and text utilities excellently tested
- Wiki utilities need more coverage

---

## Test Failures Analysis

**24 tests failed** during execution, indicating bugs or test issues:

### 1. Database Model Issues (High Priority)

**Issue:** `Person` model missing `notes` field
- **Affected Tests:** 5 failures
- **Files:** `test_sql_to_wiki.py`, `test_wiki_to_sql.py`
- **Error:** `TypeError: 'notes' is an invalid keyword argument for Person`
- **Fix Required:** Add `notes` column to Person model or update tests

**Issue:** `ManuscriptEntry` model missing `notes` field
- **Affected Tests:** 2 failures
- **Files:** `test_wiki_to_sql.py`
- **Error:** `assert None == 'Expected notes'`
- **Fix Required:** Add `notes` column to ManuscriptEntry model

**Issue:** `ManuscriptPerson` model missing `character_description` field
- **Affected Tests:** 1 failure
- **Files:** `test_wiki_to_sql.py`
- **Fix Required:** Add `character_description` column or update tests

### 2. Database Constraint Issues (Medium Priority)

**Issue:** UNIQUE constraint failures in search tests
- **Affected Tests:** 4 failures
- **Files:** `test_search.py`, `test_sql_to_wiki.py`
- **Error:** `UNIQUE constraint failed: entries.file_path`
- **Fix Required:** Use unique file paths in test fixtures or cleanup between tests

### 3. API/Method Signature Issues (High Priority)

**Issue:** `Person.from_database()` missing `journal_dir` argument
- **Affected Tests:** 4 failures
- **Files:** `test_sql_to_wiki.py`
- **Error:** `TypeError: Person.from_database() missing 1 required positional argument`
- **Fix Required:** Update method signature or fix test calls

**Issue:** `Event` model has read-only `display_name` property
- **Affected Tests:** 1 failure
- **Files:** `test_db_to_yaml.py`
- **Error:** `property 'display_name' of 'Event' object has no setter`
- **Fix Required:** Make property writable or change export logic

### 4. NLP Test Dependencies (Low Priority)

**Issue:** NumPy/NLP dependencies not available
- **Affected Tests:** 4 failures
- **Files:** `test_ai_extraction.py`
- **Error:** `AttributeError: 'NoneType' object has no attribute 'ndarray'`
- **Fix Required:** Skip tests when NLP dependencies unavailable (already partially done)

### 5. Data Consistency Issues (Medium Priority)

**Issue:** Word count not preserved during export
- **Affected Tests:** 1 failure
- **Files:** `test_db_to_yaml.py`
- **Error:** `assert 'word_count: 200' in exported_content`
- **Fix Required:** Fix export logic to preserve updated word counts

**Issue:** Reading time rounding differences
- **Affected Tests:** 1 failure
- **Files:** `test_db_to_yaml.py`
- **Error:** `assert 0.8 == 0.75`
- **Fix Required:** Handle floating point precision in round-trip tests

---

## Missing Test Features

Based on codebase analysis, the following features have **no or minimal test coverage**:

### Critical Missing Tests

1. **PDF Generation Pipeline** (0% coverage)
   - PDF building with LaTeX
   - Annotated PDF generation
   - Font handling
   - Year-based PDF compilation

2. **CLI Commands** (0% coverage)
   - `journal` CLI (inbox, convert, sync, pdf, etc.)
   - `metadb` CLI (init, backup, stats, health, etc.)
   - `palimpsest` search CLI
   - `palimpsest` NLP CLI

3. **Wiki Bidirectional Sync** (13-42% coverage)
   - Wiki → SQL import for most entity types
   - Field ownership rules
   - Note preservation
   - Navigation generation

4. **Export Managers** (13-14% coverage)
   - CSV export
   - JSON export
   - Analytics export
   - Full data backups

5. **Health Monitoring** (13% coverage)
   - Database health checks
   - Integrity validation
   - Orphan detection
   - Fix operations

### High Priority Missing Tests

6. **Backup System** (16% coverage)
   - Database backups
   - Full data backups
   - Backup restoration
   - Backup listing and management

7. **Logging System** (23% coverage)
   - Log initialization
   - Multi-handler logging
   - Log level management
   - Context managers

8. **Database Manager Core** (38% coverage)
   - Session management
   - Transaction handling
   - Migration operations
   - Database initialization

9. **Manuscript Dataclasses** (0-44% coverage)
   - Arc dataclass
   - Event dataclass
   - Theme dataclass
   - Character dataclass (44%)

10. **NLP Semantic Search** (18% coverage)
    - Similarity search
    - Theme clustering
    - Embedding caching
    - FAISS integration

### Medium Priority Missing Tests

11. **Wiki Entity Export** (22-54% coverage)
    - City wiki pages
    - Event wiki pages
    - Location wiki pages
    - Poem wiki pages
    - Reference wiki pages
    - Tag wiki pages
    - Theme wiki pages

12. **Markdown Entry Processing** (47% coverage)
    - YAML frontmatter parsing
    - Complex metadata extraction
    - Reference parsing
    - Poem parsing

13. **Query Analytics** (29% coverage)
    - Entry statistics
    - Relationship analytics
    - Temporal analytics
    - Theme analytics

14. **Person Manager** (63% coverage)
    - Alias handling
    - Full name extraction
    - Relationship management
    - Merge operations

15. **Entry Manager** (58% coverage)
    - Complex relationship creation
    - Bulk operations
    - Entry updates
    - Orphan handling

### Low Priority Missing Tests

16. **LLM Assistants** (0% coverage)
    - Claude API integration (requires API key)
    - OpenAI API integration (requires API key)
    - Cost estimation
    - Error handling

17. **Temporal Files** (19% coverage)
    - Temporary file management
    - Cleanup operations
    - Context managers

18. **Query Optimizer** (56% coverage)
    - Query optimization strategies
    - Performance improvements
    - Eager loading

---

## Recommendations

### Phase 1: Fix Failing Tests (Immediate)

**Priority: CRITICAL**
**Time: 4-8 hours**

1. **Fix Database Model Issues**
   - Add `notes` column to Person model
   - Add `notes` column to ManuscriptEntry model
   - Add `character_description` to ManuscriptPerson model
   - OR update tests to match current schema

2. **Fix Test Fixtures**
   - Ensure unique file paths in test fixtures
   - Add proper test cleanup/isolation
   - Fix Person.from_database() calls

3. **Skip NLP Tests Properly**
   - Improve dependency checking
   - Skip tests when NumPy/NLP deps unavailable
   - Add clear skip messages

**Deliverable:** All tests passing (807 passed → 831 passed)

### Phase 2: Core Feature Testing (High Priority)

**Priority: HIGH**
**Time: 16-24 hours**

1. **Wiki Bidirectional Sync (13-42% → 80%+)**
   - Test wiki → SQL import for all entity types
   - Test field ownership rules
   - Test note preservation
   - Test navigation generation
   - **Impact:** Critical for data integrity

2. **Database Manager Core (38% → 80%+)**
   - Test session management
   - Test transaction handling
   - Test migration operations
   - Test initialization
   - **Impact:** Critical for all database operations

3. **Export Managers (13-14% → 60%+)**
   - Test CSV export
   - Test JSON export
   - Test analytics
   - **Impact:** High for data portability

4. **Health Monitoring (13% → 60%+)**
   - Test health checks
   - Test integrity validation
   - Test orphan detection
   - **Impact:** High for maintenance

5. **Backup System (16% → 70%+)**
   - Test database backups
   - Test restoration
   - Test backup listing
   - **Impact:** Critical for data safety

**Deliverable:** Coverage 44% → 60%

### Phase 3: Builder and CLI Testing (High Priority)

**Priority: HIGH**
**Time: 12-20 hours**

1. **PDF Builder (0% → 60%+)**
   - Test PDF generation (may need mocking)
   - Test LaTeX processing
   - Test annotation generation
   - **Impact:** Core feature

2. **TXT Builder (0% → 60%+)**
   - Test text building
   - Test formatting
   - **Impact:** Core feature

3. **CLI Commands (0% → 50%+)**
   - Test journal CLI commands
   - Test metadb CLI commands
   - Test search CLI
   - Test NLP CLI
   - **Impact:** High for usability

**Deliverable:** Coverage 60% → 70%

### Phase 4: Dataclass Coverage (Medium Priority)

**Priority: MEDIUM**
**Time: 12-16 hours**

1. **Wiki Dataclasses (22-54% → 70%+)**
   - Test all wiki entity classes
   - Test from_file() methods
   - Test to_wiki() methods
   - Test from_database() methods
   - **Impact:** Medium (tested via integration)

2. **Manuscript Dataclasses (0-44% → 70%+)**
   - Test arc dataclass
   - Test event dataclass
   - Test theme dataclass
   - Test character dataclass
   - **Impact:** Medium (manuscriptfeature)

3. **MD Entry (47% → 75%+)**
   - Test complex YAML parsing
   - Test all metadata types
   - Test validation
   - **Impact:** Medium

**Deliverable:** Coverage 70% → 78%

### Phase 5: Optional Features (Low Priority)

**Priority: LOW**
**Time: 8-12 hours**

1. **NLP Features (0-38% → 50%+)**
   - Test extractors thoroughly
   - Test semantic search
   - Mock LLM assistants
   - **Impact:** Low (optional features)

2. **Logging & Utilities (23-50% → 80%+)**
   - Test logging system
   - Test temporal files
   - Test CLI stats
   - **Impact:** Low

**Deliverable:** Coverage 78% → 82%

---

## Test Coverage Goals

### Current State
```
Total Coverage: 44%
- Excellent (90%+): 12 modules
- Good (70-89%): 6 modules
- Medium (40-69%): 20 modules
- Poor (20-39%): 10 modules
- Untested (0-19%): 27 modules
```

### Target State (80% threshold)
```
Phase 1: Fix tests → 44% (831 tests passing)
Phase 2: Core features → 60% (1,200+ tests)
Phase 3: Builders & CLI → 70% (1,400+ tests)
Phase 4: Dataclasses → 78% (1,600+ tests)
Phase 5: Optional → 82% (1,700+ tests)
```

### Realistic Target
```
With 60-80 hours of effort:
- Coverage: 70-78%
- Passing tests: 1,500+
- Critical features: 80%+ covered
- Optional features: 40-60% covered
```

---

## Test Infrastructure Improvements

### Current Strengths
- ✅ Comprehensive fixtures in conftest.py
- ✅ Pytest markers (unit, integration, e2e, slow)
- ✅ Coverage reporting configured
- ✅ Good database test helpers
- ✅ Well-structured test organization

### Recommended Improvements

1. **Add Test Helpers for Builders**
   - Mock pandoc/tectonic for PDF tests
   - Fixture for temporary PDF output
   - LaTeX validation helpers

2. **Add CLI Testing Utilities**
   - ClickTestRunner fixtures
   - CLI output capture helpers
   - Mock file system operations

3. **Add Wiki Test Fixtures**
   - Sample wiki pages for all entity types
   - Wiki navigation test data
   - Round-trip test helpers

4. **Add Integration Test Helpers**
   - Full pipeline test fixtures
   - Large dataset generators
   - Performance test utilities

5. **Improve Test Isolation**
   - Ensure unique file paths
   - Better database cleanup
   - Session management fixes

6. **Add Mocking Infrastructure**
   - Mock API clients (Claude, OpenAI)
   - Mock system commands (pandoc, tectonic)
   - Mock file operations

---

## Critical Bugs Found

Based on test failures, these bugs should be fixed:

### Database Schema Issues

1. **Person model missing `notes` column** (CRITICAL)
   - Multiple tests expect this field
   - Breaking bidirectional sync
   - Fix: Add migration for notes column

2. **ManuscriptEntry missing `notes` column** (CRITICAL)
   - Breaking manuscript wiki sync
   - Fix: Add migration for notes column

3. **ManuscriptPerson missing `character_description` column** (HIGH)
   - Breaking character curation
   - Fix: Add migration for character_description

### Code Issues

4. **Event.display_name read-only property** (MEDIUM)
   - Export code tries to set this property
   - Fix: Make property writable or fix export logic

5. **Person.from_database() signature mismatch** (HIGH)
   - Missing required journal_dir argument
   - Fix: Update method or fix calls

6. **Word count not preserved in round-trip** (MEDIUM)
   - Data loss during export/import
   - Fix: Ensure word_count preserved

---

## Codecov Integration

### Configuration Created

- `.codecov.yml` configured with:
  - 80% project target (2% threshold)
  - 70% patch target (5% threshold)
  - Component breakdown (core, database, pipeline, NLP, builders, dataclasses, utils)
  - Ignore patterns (tests, setup, bin, etc.)
  - Flags for unit vs integration tests

### Activation Steps

1. **Sign up for Codecov:**
   - Visit https://codecov.io
   - Sign in with GitHub
   - Enable for soffiafdz/palimpsest repository

2. **Get Codecov token:**
   - Repository Settings → Codecov Settings
   - Copy CODECOV_TOKEN

3. **Add GitHub Secret:**
   - Repository Settings → Secrets and variables → Actions
   - Add new secret: `CODECOV_TOKEN`
   - Paste token value

4. **Workflows already configured:**
   - test.yml uploads coverage after unit tests
   - integration.yml uploads coverage after integration tests
   - Badges in README will auto-update

---

## Summary

**Current Coverage:** 44% (4,563 / 10,317 lines)

**Critical Gaps:**
- 24 failing tests (bugs found)
- PDF/TXT builders: 0% (critical feature)
- CLI commands: 0% (usability)
- Wiki sync: 13-42% (data integrity)
- Export/health: 13-14% (maintenance)

**Recommendations:**
1. Fix 24 failing tests immediately (4-8 hours)
2. Test core features to 60% coverage (16-24 hours)
3. Test builders and CLI to 70% coverage (12-20 hours)
4. Test dataclasses to 78% coverage (12-16 hours)
5. Test optional features to 82% coverage (8-12 hours)

**Total Effort:** 60-80 hours to reach 70-82% coverage

**Priority Order:**
1. Fix bugs (Phase 1)
2. Wiki sync, DB manager, exports, health, backup (Phase 2)
3. Builders and CLI (Phase 3)
4. Dataclasses (Phase 4)
5. NLP and utilities (Phase 5)

**Codecov Integration:** Ready to activate (needs token)

---

*Analysis completed: 2025-11-13*
*Next action: Fix failing tests and critical bugs*
