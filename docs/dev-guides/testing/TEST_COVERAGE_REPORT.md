# Test Coverage Report
**Generated**: 2025-11-27
**Total Coverage**: 44.6% (6,784 / 15,212 lines)
**Target**: 80%
**Gap**: 35.4% (~5,428 lines)

## Executive Summary

### Current Test Status ✅
- **Total Tests**: 897 passed, 14 skipped, 0 failed
- **Test Quality**: All existing tests passing, no flaky tests
- **Coverage Trend**: Up from 21% → 44.6% (after recent fixes)

### Critical Findings ⚠️

1. **NEW Untested Code**: ~1,800 lines of modular CLI code (0% coverage)
2. **Wiki Dataclasses**: Core export functionality at 20-30% coverage
3. **Database Manager**: Critical operations at 46% coverage
4. **Validators**: Entire validation system at 0-36% coverage

### Immediate Action Required

**Before Next Commit**:
- [ ] Add integration tests for new CLI modules
- [ ] Test database migration and backup operations
- [ ] Add wiki dataclass round-trip tests

**Path to 80% Coverage**: 5 phases, ~40-60 hours estimated

---

## Coverage by Category

### 🟢 Excellent Coverage (80-100%)

Well-tested core functionality that can serve as examples:

#### Core Utilities (95%+ average)
| Module | Coverage | Lines | Notes |
|--------|----------|-------|-------|
| `dev/utils/fs.py` | 100% | 42/42 | File system operations |
| `dev/utils/parsers.py` | 100% | 56/56 | Date/time parsing |
| `dev/utils/txt.py` | 100% | 41/41 | Text file handling |
| `dev/core/exceptions.py` | 100% | 30/30 | Custom exceptions |
| `dev/core/paths.py` | 92% | 36/39 | Path management |

#### Database Components (85%+ average)
| Module | Coverage | Lines | Notes |
|--------|----------|-------|-------|
| `dev/database/decorators.py` | 98% | 48/49 | Error handling decorators |
| `dev/database/models/sync.py` | 100% | 42/42 | Sync state models |
| `dev/database/models/associations.py` | 100% | 13/13 | Relationship tables |
| `dev/database/configs/integrity_check_configs.py` | 95% | 42/44 | Integrity checks |

#### Database Managers (85%+ average)
| Module | Coverage | Lines | Notes |
|--------|----------|-------|-------|
| `dev/database/managers/date_manager.py` | 94% | 155/165 | Date operations - **Good model** |
| `dev/database/managers/event_manager.py` | 90% | 198/220 | Event operations - **Good model** |
| `dev/database/managers/manuscript_manager.py` | 89% | 224/252 | Manuscript operations - **Good model** |

#### Other Well-Tested Modules
| Module | Coverage | Lines | Notes |
|--------|----------|-------|-------|
| `dev/dataclasses/txt_entry.py` | 92% | 132/144 | Text entry parsing |
| `dev/dataclasses/manuscript_entry.py` | 82% | 98/120 | Manuscript entries |
| `dev/search/search_index.py` | 85% | 71/84 | Search indexing |
| `dev/utils/templates.py` | 92% | 22/24 | Template system |
| `dev/pipeline/entity_importer.py` | 80% | 66/83 | Generic importer |

---

### 🟡 Good Coverage (60-79%)

Needs targeted testing in specific areas:

#### Database Managers (60-79%)
| Module | Coverage | Missing | Priority | Key Gaps |
|--------|----------|---------|----------|----------|
| `dev/database/managers/reference_manager.py` | 78% | 47/210 | Medium | Source validation, citation formatting |
| `dev/database/managers/tag_manager.py` | 74% | 33/127 | Medium | Bulk operations, merge logic |
| `dev/database/managers/base_manager.py` | 69% | 18/58 | **High** | Generic CRUD error paths |
| `dev/database/managers/poem_manager.py` | 69% | 73/237 | Medium | Version tracking, content hashing |
| `dev/database/managers/location_manager.py` | 68% | 82/254 | Medium | Coordinate parsing, city relationships |

#### Database Models (60-79%)
| Module | Coverage | Missing | Priority | Key Gaps |
|--------|----------|---------|----------|----------|
| `dev/database/models_manuscript.py` | 65% | 76/216 | Medium | Property getters, relationship helpers |
| `dev/database/models/core.py` | 66% | 31/91 | **High** | Entry model properties |
| `dev/database/models/creative.py` | 68% | 43/136 | Medium | Poem/reference model methods |

#### Pipeline Configs (60-79%)
| Module | Coverage | Missing | Priority | Key Gaps |
|--------|----------|---------|----------|----------|
| `dev/pipeline/configs/entity_import_configs.py` | 76% | 22/92 | Medium | Custom updater error paths |
| `dev/pipeline/configs/manuscript_entity_import_configs.py` | 63% | 38/102 | Medium | Manuscript import edge cases |

#### Other Good Coverage
| Module | Coverage | Missing | Priority | Key Gaps |
|--------|----------|---------|----------|----------|
| `dev/dataclasses/wiki_entry.py` | 68% | 75/235 | Medium | Navigation links, metadata parsing |
| `dev/search/search_engine.py` | 70% | 58/194 | High | Complex query parsing |
| `dev/utils/md.py` | 61% | 57/145 | Medium | Markdown edge cases |

---

### 🟠 Poor Coverage (40-59%)

Significant testing gaps requiring attention:

#### Database Core (40-59%)
| Module | Coverage | Missing | Priority | Critical Gaps |
|--------|----------|---------|----------|---------------|
| `dev/database/manager.py` | 46% | 214/395 | **CRITICAL** | Migrations (460-497), Backups (522-593), Health checks (604-634), Transactions (743-763) |
| `dev/database/managers/entry_manager.py` | 58% | 174/412 | **CRITICAL** | Bulk operations (771-993), Complex queries (651-670), Relationship updates |
| `dev/database/managers/person_manager.py` | 63% | 112/301 | High | Alias handling (344-351), Theme associations (550-576), Relationship merging (594-620) |

#### Database Models (40-59%)
| Module | Coverage | Missing | Priority | Critical Gaps |
|--------|----------|---------|----------|---------------|
| `dev/database/models/entities.py` | 57% | 62/145 | High | Person properties (156-182), Tag methods (226-227), Event relationships |
| `dev/database/models/geography.py` | 51% | 66/136 | Medium | City methods (206-223), Location properties (305-331), Coordinate parsing |

#### Pipeline (40-59%)
| Module | Coverage | Missing | Priority | Critical Gaps |
|--------|----------|---------|----------|---------------|
| `dev/pipeline/wiki2sql.py` | 60% | 136/343 | High | Error recovery (157-179), Batch processing (677-758), Duplicate detection |
| `dev/pipeline/yaml2sql.py` | 51% | 162/205 | Medium | YAML parsing edge cases (210-333, 356-402) |
| `dev/pipeline/sql2yaml.py` | 42% | 103/178 | Medium | Export formatting (275-312, 339-381) |

#### Query & Optimization (40-59%)
| Module | Coverage | Missing | Priority | Critical Gaps |
|--------|----------|---------|----------|---------------|
| `dev/database/query_analytics.py` | 49% | 91/177 | Medium | Analytics queries (234-259), Aggregations (381-411), Temporal analysis (430-450) |
| `dev/database/query_optimizer.py` | 56% | 37/85 | Medium | Query rewriting (494-501), Index suggestions (519-527), Performance tuning |

#### Dataclasses (40-59%)
| Module | Coverage | Missing | Priority | Critical Gaps |
|--------|----------|---------|----------|---------------|
| `dev/dataclasses/md_entry.py` | 47% | 377/711 | High | Markdown parsing (1014-1111), Frontmatter extraction (1158-1227), Content validation |
| `dev/dataclasses/manuscript_character.py` | 49% | 48/94 | Medium | from_database (88-101), to_wiki template rendering (124-208) |

#### Validators (40-59%)
| Module | Coverage | Missing | Priority | Critical Gaps |
|--------|----------|---------|----------|---------------|
| `dev/validators/wiki.py` | 56% | 86/196 | Medium | Link validation (214-257), Structure checks (268-292) |
| `dev/validators/db.py` | 36% | 103/161 | High | Referential integrity (182-226), Constraint validation (240-278) |

---

### 🔴 Critical Gaps (0-39%)

**URGENT**: These modules need immediate testing attention:

#### Completely Untested Modules (0% coverage)

##### NEW Modular CLI Code (~1,800 lines) ⚠️ HIGHEST PRIORITY
**Status**: Brand new code from refactoring, completely untested

**Database CLI** (9 files, ~700 lines):
```
dev/database/cli/__init__.py         46 lines   - Command routing
dev/database/cli/backup.py           52 lines   - Backup operations
dev/database/cli/export.py           35 lines   - Export commands
dev/database/cli/maintenance.py     164 lines   - Maintenance tasks
dev/database/cli/migration.py        75 lines   - Schema migrations
dev/database/cli/query.py           118 lines   - Query interface
dev/database/cli/setup.py            48 lines   - Database setup
dev/database/cli/sync.py            [unknown]   - Sync operations
dev/database/cli/tombstone.py        93 lines   - Soft delete management
```

**Pipeline CLI** (5 files, ~400 lines):
```
dev/pipeline/cli/__init__.py         30 lines   - Command routing
dev/pipeline/cli/maintenance.py     135 lines   - Pipeline maintenance
dev/pipeline/cli/sql2wiki.py        138 lines   - Database export
dev/pipeline/cli/wiki2sql.py         56 lines   - Wiki import
dev/pipeline/cli/yaml2sql.py        102 lines   - YAML import
```

**Validators CLI** (5 files, ~500 lines):
```
dev/validators/cli/__init__.py       14 lines   - Command routing
dev/validators/cli/consistency.py   123 lines   - Consistency checks
dev/validators/cli/database.py      106 lines   - DB validation
dev/validators/cli/markdown.py       74 lines   - Markdown validation
dev/validators/cli/metadata.py      161 lines   - Metadata validation
dev/validators/cli/wiki.py           39 lines   - Wiki validation
```

**Wiki Pages Builders** (5+ files, ~700 lines):
```
dev/builders/wiki_pages/__init__.py    6 lines   - Module setup
dev/builders/wiki_pages/analysis.py  146 lines   - Analysis pages
dev/builders/wiki_pages/entries.py    61 lines   - Entry pages
dev/builders/wiki_pages/index.py     119 lines   - Index pages
dev/builders/wiki_pages/stats.py     143 lines   - Statistics pages
dev/builders/wiki_pages/timeline.py   60 lines   - Timeline pages
dev/builders/wiki_pages/utils/*       [~165 lines] - Utility functions
```

**Testing Strategy for CLI Modules**:
```python
# Template for CLI integration tests
class TestDatabaseCLI:
    def test_backup_create(self):
        """Test database backup creation."""
        result = runner.invoke(cli, ['backup', 'create'])
        assert result.exit_code == 0
        assert "Backup created" in result.output

    def test_migration_status(self):
        """Test migration status display."""
        result = runner.invoke(cli, ['migration', 'status'])
        assert result.exit_code == 0
```

##### Validator Core Modules (~740 lines) ⚠️ HIGH PRIORITY
**Status**: Core validation logic completely untested

```
dev/validators/consistency.py       273 lines   - Cross-reference validation
dev/validators/md.py                208 lines   - Markdown format validation
dev/validators/metadata.py          263 lines   - Frontmatter validation
```

**Key Missing Tests**:
- Inconsistency detection (orphaned references, broken links)
- Markdown linting (frontmatter, structure, formatting)
- Metadata schema validation

##### Search Modules (~206 lines) - Low Priority
**Status**: Likely deprecated or optional

```
dev/search/search.py                100 lines   - Old search implementation
dev/search/cli.py                   106 lines   - Search CLI (deprecated?)
```

**Note**: `search_engine.py` has 70% coverage, suggesting these are older modules.

##### NLP Modules (~1,000+ lines) - Intentionally Skipped
**Status**: Optional dependencies, tests skipped by design

```
All dev/nlp/*.py                     1000+ lines - NLP features (transformers, spacy, etc.)
```

**Note**: 14 tests intentionally skipped when NLP dependencies not installed. This is correct behavior.

##### Builder Modules (~1,000+ lines) - Low Priority
**Status**: PDF/text builders, less critical

```
dev/builders/base.py                 29 lines
dev/builders/pdfbuilder.py          213 lines
dev/builders/txtbuilder.py          205 lines
dev/builders/wiki.py                123 lines
dev/builders/wiki_indexes.py        142 lines
```

#### Wiki Dataclasses (20-38% coverage) ⚠️ HIGH PRIORITY

**Critical**: Core wiki export functionality poorly tested

| Module | Coverage | Missing | Critical Gaps |
|--------|----------|---------|---------------|
| `dev/dataclasses/wiki_person.py` | 20% | 158/198 | `to_wiki()` template rendering (224-288), `from_file()` parsing (315-392) |
| `dev/dataclasses/wiki_city.py` | 23% | 104/135 | Template rendering (68-125), File parsing (144-235) |
| `dev/dataclasses/wiki_location.py` | 24% | 94/123 | Template rendering (64-131), Coordinate parsing (148-222) |
| `dev/dataclasses/wiki_poem.py` | 25% | 76/101 | Version tracking (113-153), Content parsing (163-216) |
| `dev/dataclasses/wiki_reference.py` | 26% | 77/104 | Citation formatting (120-157), Source linking (169-228) |
| `dev/dataclasses/wiki_tag.py` | 29% | 65/91 | Entry counts (117-154), Tag lists (165-211) |
| `dev/dataclasses/wiki_event.py` | 30% | 96/138 | Timeline generation (165-246), People aggregation (76-142) |
| `dev/dataclasses/wiki_theme.py` | 30% | 64/92 | Theme rendering (132-175), Entry lists (188-217) |
| `dev/dataclasses/manuscript_event.py` | 38% | 57/92 | Template rendering (87-132), Arc relationships (153-225) |

**Manuscript Dataclasses (0% coverage)** ⚠️ CRITICAL:
```
dev/dataclasses/manuscript_arc.py      103 lines  - Completely untested
dev/dataclasses/manuscript_theme.py     78 lines  - Completely untested
dev/dataclasses/wiki_vignette.py         2 lines  - Stub class
```

**Testing Strategy for Wiki Dataclasses**:
```python
def test_person_roundtrip(db, wiki_dir):
    """Test Person: DB → wiki file → DB maintains data integrity."""
    # Export from database
    person = db.people.get(name="Alice")
    wiki_person = Person.from_database(person, wiki_dir)

    # Write to wiki
    wiki_person.write_to_file()

    # Re-parse from wiki
    parsed = Person.from_file(wiki_person.path)

    # Verify editable fields preserved
    assert parsed.notes == wiki_person.notes
    assert parsed.category == wiki_person.category
```

#### Database Critical Systems (24-37% coverage)

| Module | Coverage | Missing | Critical Gaps |
|--------|----------|---------|---------------|
| `dev/database/export_manager.py` | 24% | 118/156 | JSON export (213-235), Custom serializers (273-323), Nested exports (351-412) |
| `dev/database/tombstone_manager.py` | 31% | 46/67 | Soft delete (120-161), Restore (184-190), Purge (282-290) |
| `dev/database/sync_state_manager.py` | 35% | 55/84 | Conflict detection (111-119), Merge strategies (214-236), Sync state tracking (259-307) |
| `dev/database/health_monitor.py` | 37% | 160/254 | Health checks (200-212), Performance monitoring (329-343), Alert system (428-450) |

---

## Testing Strategy & Roadmap

### Phase 1: Critical Infrastructure (Target: +15% → 60%)
**Duration**: 2-3 weeks
**Priority**: CRITICAL - Required before commit

#### 1.1 Database Manager Core
**Files**: `dev/database/manager.py`
**Missing**: 214 lines (46% coverage)
**Tests to Add**: ~30 test cases

**Key Test Cases**:
```python
# Migration system
def test_upgrade_to_latest_revision()
def test_downgrade_to_specific_revision()
def test_migration_failure_rollback()

# Backup/restore
def test_create_backup_with_metadata()
def test_restore_from_backup()
def test_backup_rotation()

# Transaction handling
def test_transaction_commit_success()
def test_transaction_rollback_on_error()
def test_nested_transaction_savepoints()

# Health monitoring
def test_database_health_check()
def test_connection_pool_status()
def test_query_performance_tracking()
```

**Estimated Coverage Gain**: +100 lines → 52% total

#### 1.2 Entry Manager
**Files**: `dev/database/managers/entry_manager.py`
**Missing**: 174 lines (58% coverage)
**Tests to Add**: ~25 test cases

**Key Test Cases**:
```python
# Bulk operations
def test_bulk_create_entries()
def test_bulk_update_with_validation()
def test_bulk_delete_with_cascade()

# Complex queries
def test_entry_search_with_filters()
def test_entry_date_range_queries()
def test_entry_relationship_eager_loading()

# Relationship management
def test_add_remove_tags()
def test_link_unlink_people()
def test_update_references()
```

**Estimated Coverage Gain**: +80 lines → 53% total

#### 1.3 Export/Import Pipelines
**Files**: `dev/database/export_manager.py`, `dev/pipeline/wiki2sql.py`
**Missing**: 254 lines combined
**Tests to Add**: ~20 test cases

**Key Test Cases**:
```python
# Export manager
def test_export_all_entities_to_json()
def test_export_with_custom_serializers()
def test_export_nested_relationships()

# Import pipeline
def test_batch_import_with_errors()
def test_import_duplicate_detection()
def test_import_relationship_resolution()

# Round-trip integrity
def test_export_import_preserves_data()
```

**Estimated Coverage Gain**: +120 lines → 54% total

**Phase 1 Total**: ~300 lines → **54% coverage**

---

### Phase 2: Modular CLI (Target: +12% → 66%)
**Duration**: 1-2 weeks
**Priority**: HIGH - New code must be tested

#### 2.1 Database CLI Commands
**Files**: `dev/database/cli/*.py`
**Missing**: 700 lines (0% coverage)
**Tests to Add**: ~50 test cases

**Testing Approach**: Integration tests using Click's CliRunner

```python
from click.testing import CliRunner
from dev.database.cli import cli

def test_backup_create_command():
    runner = CliRunner()
    result = runner.invoke(cli, ['backup', 'create', '--message', 'test'])
    assert result.exit_code == 0
    assert 'Backup created' in result.output

def test_migration_status_command():
    runner = CliRunner()
    result = runner.invoke(cli, ['migration', 'status'])
    assert result.exit_code == 0
    assert 'Current revision' in result.output

def test_export_json_command(tmp_path):
    runner = CliRunner()
    output = tmp_path / "export.json"
    result = runner.invoke(cli, ['export', 'json', '-o', str(output)])
    assert result.exit_code == 0
    assert output.exists()
```

**Test File**: `tests/integration/test_cli_database.py`
**Estimated Coverage Gain**: +300 lines → 56% total

#### 2.2 Pipeline CLI Commands
**Files**: `dev/pipeline/cli/*.py`
**Missing**: 400 lines (0% coverage)
**Tests to Add**: ~30 test cases

```python
def test_sql2wiki_export_all():
    runner = CliRunner()
    result = runner.invoke(cli, ['sql2wiki', 'all'])
    assert result.exit_code == 0

def test_wiki2sql_import_people():
    runner = CliRunner()
    result = runner.invoke(cli, ['wiki2sql', 'people'])
    assert result.exit_code == 0
```

**Test File**: `tests/integration/test_cli_pipeline.py`
**Estimated Coverage Gain**: +100 lines → 57% total

**Phase 2 Total**: ~400 lines → **57% coverage**

---

### Phase 3: Wiki Dataclasses (Target: +15% → 72%)
**Duration**: 2-3 weeks
**Priority**: HIGH - Core functionality

#### 3.1 Round-Trip Tests for All Entity Types
**Files**: All `dev/dataclasses/wiki_*.py`
**Missing**: ~900 lines (20-30% avg coverage)
**Tests to Add**: ~80 test cases (8 per entity type)

**Test Pattern** (repeat for each entity type):
```python
class TestPersonRoundTrip:
    def test_export_from_database(self, db_person, wiki_dir):
        """Test Person.from_database() creates correct wiki object."""
        wiki_person = Person.from_database(db_person, wiki_dir)
        assert wiki_person.name == db_person.name
        assert wiki_person.category == db_person.relation_type

    def test_render_to_wiki_file(self, wiki_person):
        """Test to_wiki() generates valid markdown."""
        lines = wiki_person.to_wiki()
        content = "\n".join(lines)
        assert "# Palimpsest — Person" in content
        assert wiki_person.name in content

    def test_parse_from_wiki_file(self, wiki_file):
        """Test from_file() parses wiki correctly."""
        person = Person.from_file(wiki_file)
        assert person is not None
        assert person.notes is not None

    def test_full_roundtrip_preserves_editable_fields(self, db, wiki_dir):
        """Test DB → wiki → DB preserves user-editable fields."""
        # Create in DB
        person = db.people.create({"name": "Alice", "relation_type": "friend"})
        person.notes = "Test notes"

        # Export to wiki
        wiki_person = Person.from_database(person, wiki_dir)
        wiki_person.write_to_file()

        # Parse from wiki
        parsed = Person.from_file(wiki_person.path)

        # Verify editable fields preserved
        assert parsed.notes == "Test notes"
        assert parsed.category == "friend"
```

**Entity Types to Test** (10 total):
1. Person
2. Event
3. Location
4. City
5. Poem
6. Reference
7. Tag
8. Theme
9. Entry
10. Manuscript Entry

**Test Files**:
- `tests/unit/dataclasses/test_wiki_person.py`
- `tests/unit/dataclasses/test_wiki_event.py`
- `tests/unit/dataclasses/test_wiki_location.py`
- ... (8 more)

**Estimated Coverage Gain**: +600 lines → **61% total**

#### 3.2 Template Rendering Edge Cases
**Tests to Add**: ~20 test cases

```python
def test_template_with_empty_optional_fields():
    """Test templates handle None values gracefully."""
    person = Person(name="Alice", notes=None)
    lines = person.to_wiki()
    # Should not crash, should render empty section

def test_template_with_special_characters():
    """Test templates escape markdown special chars."""
    person = Person(name="Alice", notes="**bold** _italic_")
    lines = person.to_wiki()
    # Verify proper escaping

def test_template_with_very_long_content():
    """Test templates handle large content blocks."""
    person = Person(name="Alice", notes="x" * 10000)
    lines = person.to_wiki()
    assert len(lines) > 0
```

**Estimated Coverage Gain**: +50 lines → **61.5% total**

**Phase 3 Total**: ~650 lines → **61.5% coverage**

---

### Phase 4: Validators & Utilities (Target: +8% → 69%)
**Duration**: 1-2 weeks
**Priority**: MEDIUM

#### 4.1 Validator Test Suite
**Files**: `dev/validators/*.py`
**Missing**: 740 lines (0% coverage)
**Tests to Add**: ~60 test cases

```python
# Consistency validators
def test_detect_orphaned_references():
    """Test finding references with no source."""

def test_detect_broken_wiki_links():
    """Test finding [[broken]] links."""

def test_detect_duplicate_entries():
    """Test finding duplicate journal entries."""

# Markdown validators
def test_validate_frontmatter_schema():
    """Test frontmatter has required fields."""

def test_validate_markdown_structure():
    """Test proper heading hierarchy."""

# Metadata validators
def test_validate_date_formats():
    """Test date fields use correct format."""

def test_validate_enum_values():
    """Test enum fields have valid values."""
```

**Test Files**:
- `tests/unit/validators/test_consistency.py`
- `tests/unit/validators/test_markdown.py`
- `tests/unit/validators/test_metadata.py`

**Estimated Coverage Gain**: +400 lines → **64% total**

#### 4.2 Validator CLI Commands
**Files**: `dev/validators/cli/*.py`
**Missing**: 500 lines (0% coverage)
**Tests to Add**: ~30 test cases

```python
def test_validate_consistency_command():
    runner = CliRunner()
    result = runner.invoke(cli, ['validate', 'consistency'])
    assert result.exit_code == 0

def test_validate_markdown_command():
    runner = CliRunner()
    result = runner.invoke(cli, ['validate', 'markdown', '--fix'])
    assert result.exit_code == 0
```

**Test File**: `tests/integration/test_cli_validators.py`
**Estimated Coverage Gain**: +150 lines → **65% total**

**Phase 4 Total**: ~550 lines → **65% coverage**

---

### Phase 5: Fill Remaining Gaps (Target: 80%)
**Duration**: 3-4 weeks
**Priority**: MEDIUM-LOW

#### 5.1 Person & Location Manager Edge Cases
**Files**: `dev/database/managers/person_manager.py`, `location_manager.py`
**Missing**: 194 lines combined
**Tests to Add**: ~40 test cases

```python
# Person manager
def test_merge_duplicate_people()
def test_handle_complex_alias_chains()
def test_theme_association_edge_cases()

# Location manager
def test_coordinate_validation()
def test_city_hierarchy_updates()
def test_location_merge_with_entries()
```

**Estimated Coverage Gain**: +150 lines → 66% total

#### 5.2 Query Analytics & Optimization
**Files**: `dev/database/query_analytics.py`, `query_optimizer.py`
**Missing**: 128 lines combined
**Tests to Add**: ~25 test cases

```python
def test_analytics_temporal_patterns()
def test_analytics_relationship_graphs()
def test_optimizer_query_rewriting()
def test_optimizer_index_suggestions()
```

**Estimated Coverage Gain**: +80 lines → 66.5% total

#### 5.3 Health Monitoring & Sync State
**Files**: `dev/database/health_monitor.py`, `sync_state_manager.py`
**Missing**: 215 lines combined
**Tests to Add**: ~30 test cases

```python
def test_health_check_all_systems()
def test_performance_monitoring()
def test_sync_conflict_detection()
def test_sync_merge_strategies()
```

**Estimated Coverage Gain**: +150 lines → 67.5% total

#### 5.4 Remaining Dataclasses & Utils
**Files**: Various small gaps
**Missing**: ~500 lines scattered
**Tests to Add**: ~50 test cases

```python
def test_md_entry_frontmatter_edge_cases()
def test_utils_markdown_parsing()
def test_builders_wiki_indexes()
```

**Estimated Coverage Gain**: +250 lines → 69% total

#### 5.5 Final Push - Edge Cases
**Missing**: ~1,600 lines to reach 80%
**Tests to Add**: ~150 test cases

Focus on:
- Error handling paths
- Transaction rollback scenarios
- Complex relationship cascades
- Rare edge cases in parsers
- Performance optimization paths

**Estimated Coverage Gain**: +1,600 lines → **80% TARGET** ✅

**Phase 5 Total**: ~2,230 lines → **80% coverage**

---

## Implementation Priority Matrix

### Must Have (Before Next Commit)
**Impact**: CRITICAL | **Effort**: HIGH | **Timeline**: 2-3 weeks

1. ✅ Fix remaining 2 test failures (get_all_themes/arcs) - **DONE**
2. Database Manager core tests (migrations, backups, transactions)
3. Modular CLI integration tests (database + pipeline commands)
4. Wiki dataclass round-trip tests (at least Person, Event, Entry)

**Deliverable**: 60% coverage minimum

### Should Have (Near Term)
**Impact**: HIGH | **Effort**: MEDIUM | **Timeline**: 3-4 weeks

5. Remaining wiki dataclass tests (all 10 entity types)
6. Entry manager complex operations
7. Export/import pipeline edge cases
8. Validator test suite (consistency, markdown, metadata)

**Deliverable**: 70% coverage

### Nice to Have (Future)
**Impact**: MEDIUM | **Effort**: MEDIUM-HIGH | **Timeline**: 4-6 weeks

9. Person/Location manager edge cases
10. Query analytics and optimization
11. Health monitoring and sync state
12. Remaining edge cases and error paths

**Deliverable**: 80% coverage target

---

## Test File Structure

### Proposed New Test Files

```
tests/
├── integration/
│   ├── test_cli_database.py          # NEW - Database CLI commands
│   ├── test_cli_pipeline.py          # NEW - Pipeline CLI commands
│   ├── test_cli_validators.py        # NEW - Validator CLI commands
│   ├── test_export_import_roundtrip.py  # NEW - Full round-trip tests
│   ├── test_migrations.py            # NEW - Schema migrations
│   └── test_backups.py                # NEW - Backup/restore
│
├── unit/
│   ├── dataclasses/
│   │   ├── test_wiki_person.py       # NEW - Person round-trip
│   │   ├── test_wiki_event.py        # NEW - Event round-trip
│   │   ├── test_wiki_location.py     # NEW - Location round-trip
│   │   ├── test_wiki_city.py         # NEW - City round-trip
│   │   ├── test_wiki_poem.py         # NEW - Poem round-trip
│   │   ├── test_wiki_reference.py    # NEW - Reference round-trip
│   │   ├── test_wiki_tag.py          # NEW - Tag round-trip
│   │   ├── test_wiki_theme.py        # NEW - Theme round-trip
│   │   ├── test_wiki_entry.py        # EXPAND - Entry tests
│   │   └── test_manuscript_*.py      # NEW - Manuscript dataclasses
│   │
│   ├── validators/
│   │   ├── test_consistency.py       # NEW - Consistency checks
│   │   ├── test_markdown.py          # NEW - Markdown validation
│   │   └── test_metadata.py          # NEW - Metadata validation
│   │
│   └── managers/
│       ├── test_person_manager.py    # EXPAND - More edge cases
│       ├── test_entry_manager.py     # EXPAND - Bulk operations
│       └── test_database_manager.py  # NEW - Core DB operations
│
└── fixtures/
    ├── sample_wiki_files/             # NEW - Wiki file examples
    └── test_databases/                # NEW - Test DB snapshots
```

### Estimated Test Code Volume

| Phase | New Test Files | Test Cases | Lines of Code |
|-------|----------------|------------|---------------|
| Phase 1 | 3 files | ~75 | ~1,500 |
| Phase 2 | 2 files | ~80 | ~1,200 |
| Phase 3 | 10 files | ~100 | ~2,000 |
| Phase 4 | 4 files | ~90 | ~1,400 |
| Phase 5 | 5 files | ~200 | ~3,000 |
| **TOTAL** | **24 files** | **~545** | **~9,100** |

---

## Metrics & Tracking

### Current Metrics (2025-11-27)
- Total Lines: 15,212
- Tested Lines: 6,784
- Untested Lines: 8,428
- Coverage: 44.6%
- Tests Passing: 897
- Tests Failing: 0
- Tests Skipped: 14 (NLP dependencies)

### Target Metrics (End of Phase 5)
- Total Lines: ~15,500 (modest growth)
- Tested Lines: 12,400
- Untested Lines: 3,100
- Coverage: 80%
- Tests Passing: ~1,450
- Tests Failing: 0
- Tests Skipped: 14 (same)

### Weekly Goals

**Week 1-2** (Phase 1 Part 1):
- [ ] Database manager tests
- [ ] Entry manager tests
- Target: 50% coverage

**Week 3-4** (Phase 1 Part 2 + Phase 2):
- [ ] Export/import pipeline tests
- [ ] Database CLI tests
- Target: 57% coverage

**Week 5-7** (Phase 3):
- [ ] Wiki dataclass round-trip tests (all 10)
- Target: 65% coverage

**Week 8-9** (Phase 4):
- [ ] Validator test suite
- [ ] Validator CLI tests
- Target: 69% coverage

**Week 10-14** (Phase 5):
- [ ] Fill remaining gaps
- [ ] Edge cases and error paths
- Target: 80% coverage ✅

---

## Quality Standards

### Test Requirements

All new tests must:
1. **Follow AAA Pattern**: Arrange, Act, Assert
2. **Be Independent**: No test depends on another
3. **Be Deterministic**: Same input → same output
4. **Clean Up**: Use fixtures, teardown properly
5. **Document Intent**: Clear docstrings
6. **Fast Execution**: <1s per test (unit), <5s (integration)

### Example Test Template

```python
def test_specific_behavior_under_certain_conditions():
    """
    Test that [component] does [expected behavior] when [conditions].

    This ensures that [why this matters].
    """
    # Arrange: Set up test data and preconditions
    db = create_test_database()
    person = db.people.create({"name": "Alice"})

    # Act: Execute the behavior being tested
    result = person.update_notes("New notes")

    # Assert: Verify expected outcomes
    assert result.notes == "New notes"
    assert result.updated_at is not None

    # Cleanup (if needed - usually handled by fixtures)
    db.cleanup()
```

---

## Success Criteria

### Definition of Done (80% Coverage)

- [ ] All critical paths have tests (database, export/import)
- [ ] All new modular CLI code tested (database, pipeline, validators)
- [ ] All wiki dataclasses have round-trip tests
- [ ] All validator modules have test suites
- [ ] Coverage reports show 80%+ across all modules
- [ ] No failing tests in CI/CD
- [ ] Test execution time <5 minutes total
- [ ] Documentation updated with testing guidelines

### Continuous Monitoring

**After Each PR**:
- Run: `pytest --cov=dev --cov-report=term-missing`
- Verify: Coverage does not decrease
- Update: This document if structure changes

**Monthly Review**:
- Analyze: Which modules dropped in coverage
- Prioritize: Add tests for regression areas
- Refactor: Improve test quality and speed

---

## Appendix: Coverage Analysis Commands

### Generate Full Report
```bash
# HTML report with line-by-line highlighting
pytest --cov=dev --cov-report=html

# Open in browser
open htmlcov/index.html
```

### Check Specific Module
```bash
# Coverage for specific file
pytest --cov=dev/database/manager.py --cov-report=term-missing

# Coverage for specific package
pytest --cov=dev/dataclasses --cov-report=term-missing
```

### Find Untested Code
```bash
# Show only files below 50% coverage
pytest --cov=dev --cov-report=term-missing --cov-fail-under=50

# Generate JSON for programmatic analysis
pytest --cov=dev --cov-report=json
cat coverage.json | jq '.files | to_entries[] | select(.value.summary.percent_covered < 50)'
```

### Integration with CI/CD
```yaml
# .github/workflows/tests.yml
- name: Run tests with coverage
  run: pytest --cov=dev --cov-report=xml --cov-fail-under=80

- name: Upload coverage to Codecov
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

---

## Contact & Maintenance

**Report Owner**: Development Team
**Last Updated**: 2025-11-27
**Next Review**: 2025-12-27

**Questions or Updates**: Open an issue in the repository with label `testing`

---

**End of Report**
