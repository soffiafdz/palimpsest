# Unified Simplification Workplan

**Created:** 2025-12-19
**Based on:** Claude Opus 4.5 Audit + Gemini 3 Audit + Existing Workplan + Comprehensive Method Analysis
**Goal:** Reduce codebase from ~42,000 to ~29,300 lines (~30% reduction) while preserving all features

---

## Executive Summary: Audit Comparison

### Areas of Agreement

Both audits agree on these key problems:

| Issue | Claude Assessment | Gemini Assessment | Verdict |
|-------|-------------------|-------------------|---------|
| Entity Manager Boilerplate | ~70% redundant, 9→4 managers | "God Methods", need simplification | **FIX** |
| Health/Analytics Over-complexity | 2,047→600 lines | "Over-engineered reporting" | **FIX** |
| EntryManager Size | 1,310 lines, split needed | "700+ line behemoth", shrink | **FIX** |
| Slug Pattern Duplication | 40+ copy-paste instances | Not mentioned | **FIX** |
| Parser Data Corruption | P0.5 critical bug | Not mentioned | **FIX** |

### Areas of Disagreement (Resolved)

| Component | Claude | Gemini | Resolution |
|-----------|--------|--------|------------|
| **Tombstones** | KEEP (documented multi-machine sync) | DELETE ("unnecessary complexity") | **KEEP** — Real use case documented |
| **Sync State** | KEEP (conflict detection) | DELETE (make DB "read-only slave") | **KEEP** — Essential for Git-based sync |
| **wiki2sql.py** | KEEP (notes sync) | DELETE ("WET pipeline") | **KEEP** — Used for notes/vignettes |
| **Bidirectional Sync** | KEEP (limited to notes) | DELETE (make Markdown master) | **KEEP** — Architecture is sound |
| **Manuscript Subsystem** | KEEP (intentional feature) | Not mentioned | **KEEP** — Documented use case |
| **EntityImporter** | Not mentioned | DELETE | **SIMPLIFY** — Keep core, remove meta-programming |
| **WikiEntry.from_database** | Keep | DELETE/simplify | **SIMPLIFY** — Reduce marshalling code |

### Resolution Rationale

Gemini's audit misses that this system is designed for **multi-machine synchronization via Git**. The "complexity" in tombstones, sync state, and bidirectional sync exists because:

1. **Two machines editing the same journal** — Conflicts must be detected
2. **Deletions must propagate** — Tombstones prevent resurrection
3. **Notes are wiki-only metadata** — wiki2sql imports user annotations

Removing these would break documented workflows described in `docs/guides/synchronization.md` and `docs/development/tombstones.md`.

---

## What This Workplan Will NOT Do

To preserve functionality and usability, we will NOT:

1. ❌ Remove multi-machine sync capabilities
2. ❌ Make the database "read-only" (breaks design)
3. ❌ Delete the manuscript subsystem
4. ❌ Remove bidirectional wiki sync
5. ❌ Delete tombstone/sync state tracking
6. ❌ Modify any files in `data/` directory

---

## Unified Priority List (Dependency-Ordered)

This list is organized by dependency tiers. Complete tasks in order to avoid rework.

### ✅ Completed

| Priority | Task | Lines Saved | Status |
|----------|------|-------------|--------|
| **P0** | Delete NLP module | ~2,500 | ✅ Complete |
| **P0.5** | Fix `spaces_to_hyphenated()` data corruption | ~30 | ✅ Complete |
| **P1** | Remove duplicate CLI in validators/wiki.py | ~84 | ✅ Complete |
| **P2** | Add `slugify()` utility + consolidate parsers | ~65 | ✅ Complete |
| **P3.1** | Consolidate CRUD patterns (exists/get/get_or_create) | -550 | ✅ Complete |
| **P3.2** | Generic relationship updater (_update_relationships) | -150 | ✅ Complete |
| **P3.3** | Delete wrapper methods (get_for_entry, etc.) | ~100 | ✅ Complete |
| **P25** | Moment model schema (MentionedDate → Moment, M2M events) | ~50 cleaner | ✅ Complete |

### Tier 1: Foundation (Core Changes - Do First)

Schema and architecture changes that other tasks depend on.

| Priority | Task | Lines Impact | Risk | Depends On |
|----------|------|--------------|------|------------|
| **P3** | Consolidate entity managers (9→4) | -3,000 | Medium | — |
| **P4** | Simplify health/analytics (2,047→600) | -1,400 | Low | — |
| **P4.1** | Consolidate integrity check methods | -100 | Low | P4 |

### Tier 2: Wiki System Rewrite

Replaces the current wiki dataclass system with Jinja templates.

| Priority | Task | Lines Impact | Risk | Depends On |
|----------|------|--------------|------|------------|
| **P26** | Template-based wiki renderer | -2,750 | Medium | P25 |
| **P8** | Generic wiki index builder | -280 | Low | P26 (or merged into P26) |

**Note:** P5, P5.1, P5.2, P20 (wiki dataclass cleanup) become **obsolete** with P26. Skip these if P26 is planned.

### Tier 3: Wiki Enhancements

Improvements to the wiki system after the rewrite.

| Priority | Task | Lines Impact | Risk | Depends On |
|----------|------|--------------|------|------------|
| **P27** | Main wiki dashboards | +200 | Low | P26 |
| **P34** | Neovim plugin fixes + enhancements | +300 Lua | Low | — (can be done anytime) |

### Tier 4: Manuscript System

Full manuscript curation workflow.

| Priority | Task | Lines Impact | Risk | Depends On |
|----------|------|--------------|------|------------|
| **P28** | Manuscript database schema | +150 SQL | Medium | P25, P26 |
| **P29** | Manuscript YAML parsing | +100 | Low | P28 |
| **P30** | Manuscript wiki structure | +300 templates | Medium | P26, P28 |
| **P31** | Bidirectional sync config | +150 | Medium | P28, P30 |

### Tier 5: Manuscript Integration

Final manuscript tooling.

| Priority | Task | Lines Impact | Risk | Depends On |
|----------|------|--------------|------|------------|
| **P32** | Neovim manuscript commands | +200 Lua | Low | P28-P31 |
| **P33** | Stats materialized views | +100 SQL | Low | P25, P28 |

### Tier 6: Final Cleanup

Do after major architectural changes are complete.

| Priority | Task | Lines Impact | Risk | Depends On |
|----------|------|--------------|------|------------|
| **P35** | Code reorganization | ~0 | Medium | P4, P26 |

### Low Priority (Anytime)

Independent cleanup tasks. Do as convenient or skip if superseded.

| Priority | Task | Lines Saved | Risk | Notes |
|----------|------|-------------|------|-------|
| **P6** | Consolidate backup/stats CLI commands | ~100 | Low | |
| **P7** | Remove meta-programming in pipeline | ~300 | Medium | |
| **P7.1** | Delete unused import_* wrappers | ~250 | Low | |
| **P7.2** | Merge EntityExporter classes | ~350 | Medium | May be part of P26 |
| **P9** | Validator method consolidation | ~160 | Low | |
| **P10** | Replace decorator boilerplate with context managers | ~300 | Medium | |
| **P11** | Utils module consolidation | ~180 | Low | |
| **P12** | Pipeline file writing helpers | ~40 | Low | |
| **P13** | Use existing `safe_logger()` codebase-wide | ~70 | Low | |
| **P14** | PDF builder consolidation | ~98 | Medium | |
| **P15** | Extract sync state helper | ~125 | Medium | |
| **P16** | Extract field update helper | ~100 | Medium | |
| **P17** | Delete unused single-entity imports | ~230 | Low | |
| **P18** | Wiki stats collector | ~30 | Low | May be part of P26 |
| **P19** | Generic wiki index grouping | ~80 | Medium | Part of P26/P8 |
| **P21** | Search module consolidation | ~160 | Low | |
| **P22** | Core module cleanup | ~90 | Low | |
| **P23** | Database model mixins | ~100 | Very Low | |
| **P24** | Wiki pages utils cleanup | ~20 | Very Low | |

### Skip If P26 Is Implemented

These become obsolete when wiki dataclasses are replaced with templates:

| Priority | Task | Reason to Skip |
|----------|------|----------------|
| **P5** | Simplify wiki dataclasses | Replaced by templates |
| **P5.1** | Generic from_database helpers | Replaced by templates |
| **P5.2** | Generic section generators | Replaced by templates |
| **P20** | Dataclass consolidation | Replaced by templates |

### Critical Path Summary

```
P25 (Moment) ─┬─→ P26 (Templates) ─┬─→ P27 (Dashboards)
              │                    │
P3 (Managers) │                    ├─→ P28-31 (Manuscript) ─→ P32-33 (Integration)
      ↓       │                    │
P4 (Health) ──┴────────────────────┴─→ P35 (Reorg)
```

---

## Phase 0: Critical Bug Fix ✅ COMPLETE

### P0.5: Data Corruption in `parsers.py` — FIXED

**Location:** `dev/utils/parsers.py`

**Problem:** Two functions existed for the same operation, but one corrupted data.

**Solution Applied:**
1. Merged `spaces_to_hyphenated_smart()` logic into `spaces_to_hyphenated()`
2. Deleted the redundant `spaces_to_hyphenated_smart()` function
3. Updated all call sites:
   - `parsers.py:format_location_ref()` — now uses unified function
   - `md.py:yaml_list()` — removed `smart_hyphenation` parameter
   - `md_entry.py` — updated to use `hyphenated=True`
4. Added regression tests for hyphen preservation

**Current Behavior:**
```python
spaces_to_hyphenated("María José") == "María-José"       # No hyphens: use hyphens
spaces_to_hyphenated("Jean-Pierre Martin") == "Jean-Pierre_Martin"  # Has hyphens: use underscores
```

**Files Modified:**
- `dev/utils/parsers.py` — unified function
- `dev/utils/md.py` — simplified `yaml_list()`
- `dev/dataclasses/md_entry.py` — updated call site
- `tests/unit/test_parsers.py` — added new tests

---

## Phase 1: Utility Consolidation

### P2: Add `slugify()` + Consolidate String Operations ✅ COMPLETE

**Status:** All patterns consolidated

**Completed:**
1. Added `slugify()`, `entity_filename()`, `entity_path()` to `dev/utils/wiki.py`
2. Added exports to `dev/utils/__init__.py`
3. Created tests in `tests/unit/test_wiki_utils.py` (14 tests)
4. Consolidated all 32 duplicate patterns:
   - Wiki dataclasses: `wiki_person.py`, `wiki_entry.py`, `wiki_event.py`, `wiki_location.py`, `wiki_city.py`, `wiki_tag.py`, `wiki_theme.py`, `wiki_poem.py`, `wiki_reference.py`
   - Manuscript dataclasses: `manuscript_arc.py`, `manuscript_character.py`, `manuscript_event.py`, `manuscript_theme.py`
   - Builders: `wiki_pages/analysis.py`

**Functions Added:**
```python
def slugify(name: str) -> str:
    """Convert name to wiki-safe filename slug."""
    return name.lower().replace(" ", "_").replace("/", "-")

def entity_filename(name: str) -> str:
    """Generate wiki markdown filename for an entity."""
    return f"{slugify(name)}.md"

def entity_path(wiki_dir: Path, subdir: str, name: str) -> Path:
    """Generate standard entity path within wiki directory."""
    return wiki_dir / subdir / entity_filename(name)
```

**Lines saved:** ~65 lines (32 patterns consolidated)

---

## Phase 2: Entity Manager Consolidation

### P3: Reduce 9 Managers to 4

**Current Structure (6,918 lines):**
```
dev/database/managers/
├── base_manager.py        256 lines  (KEEP)
├── entry_helpers.py       282 lines  (MERGE)
├── tag_manager.py         432 lines  → SimpleManager
├── date_manager.py        524 lines  → SimpleManager
├── event_manager.py       640 lines  → SimpleManager
├── location_manager.py    687 lines  → EntityManager
├── reference_manager.py   628 lines  → EntityManager
├── poem_manager.py        633 lines  → EntityManager
├── person_manager.py      850 lines  → EntityManager
├── manuscript_manager.py  613 lines  (KEEP - distinct)
└── entry_manager.py     1,310 lines  (KEEP - simplify)
```

**Target Structure (~2,500 lines):**
```
dev/database/managers/
├── base_manager.py        300 lines  (enhanced)
├── simple_manager.py      400 lines  (Tag, Date, Event - config-driven)
├── entity_manager.py      800 lines  (Person, Location, Reference, Poem)
├── entry_manager.py       800 lines  (simplified)
├── manuscript_manager.py  400 lines  (simplified)
└── __init__.py            100 lines  (compatibility exports)
```

### Implementation

**Step 1: Create `SimpleManager`** for Tag/Date/Event
- Config-driven: `{model_class, name_field, display_name}`
- Generic CRUD operations
- ~400 lines replaces ~1,600 lines

**Step 2: Create unified `EntityManager`** for Person/Location/Reference/Poem
- Shared validation decorators
- Common query patterns
- Entity-specific methods via strategy pattern

**Step 3: Simplify `EntryManager`**
- Extract relationship updates to helper methods
- Remove over-documented internals
- Target: 1,310 → 800 lines

**Step 4: Update `PalimpsestDB` facade**
- Maintain backward compatibility
- Property-based access: `db.tags`, `db.people`, etc.

**Files to delete after consolidation:**
```
dev/database/managers/tag_manager.py
dev/database/managers/date_manager.py
dev/database/managers/event_manager.py
dev/database/managers/entry_helpers.py
```

**Estimated reduction:** ~3,000 lines

---

## Phase 3: Health/Analytics Simplification

### P4: Merge and Reduce Health Modules

**Current Structure (2,047 lines):**
```
dev/database/
├── health_monitor.py      793 lines
├── query_optimizer.py     668 lines
├── query_analytics.py     586 lines
```

**Target Structure (~600 lines):**
```
dev/database/
├── health.py              300 lines  (merged health + basic analytics)
├── query_optimizer.py     300 lines  (essential queries only)
```

### What to Keep

| Function | Purpose | Used By |
|----------|---------|---------|
| `health_check()` | Connectivity + integrity | CLI |
| `check_orphaned_records()` | Orphan detection | cleanup command |
| `optimize_database()` | VACUUM + ANALYZE | optimize command |
| `get_database_stats()` | Basic counts | stats command |
| `QueryOptimizer.for_display()` | Entry loading | entry_manager |
| `QueryOptimizer.for_export()` | Batch export | export_manager |

### What to Remove

- Elaborate reporting structures (unused)
- `HierarchicalBatcher` class (over-engineered)
- Manuscript-specific analytics (move to manuscript_manager if needed)
- Recommendation system (generates but nothing acts on it)
- Performance metrics collection (unused)

**Files to delete:**
```
dev/database/health_monitor.py  (replaced by health.py)
dev/database/query_analytics.py (merged into health.py)
```

**Estimated reduction:** ~1,400 lines

---

## Phase 4: Wiki Dataclass Simplification

### P5: Enhance Base Class, Reduce Duplication

**Current Structure (3,045 lines, 11 files):**
```
dev/dataclasses/
├── wiki_entity.py       121 lines  (base - enhance)
├── wiki_tag.py          231 lines
├── wiki_theme.py        237 lines
├── wiki_poem.py         238 lines
├── wiki_reference.py    252 lines
├── wiki_location.py     296 lines
├── wiki_city.py         300 lines
├── wiki_event.py        318 lines
├── wiki_person.py       478 lines
├── wiki_entry.py        542 lines
└── wiki_vignette.py      32 lines
```

**Target Structure (~1,500 lines):**

Move to `WikiEntity` base class:
- `compute_path()` - standard path generation
- `generate_breadcrumb()` - navigation links
- `generate_header()` - wiki header format
- `_sanitize_filename()` - uses `slugify()`

Each subclass keeps only:
- Entity-specific fields
- Entity-specific `from_database()` logic
- Entity-specific `to_wiki()` sections

### Enhanced WikiEntity Base

```python
class WikiEntity:
    _subdir: str = ""  # Override: "people", "locations", etc.
    _name_field: str = "name"

    @classmethod
    def compute_path(cls, wiki_dir: Path, name: str) -> Path:
        return wiki_dir / cls._subdir / f"{slugify(name)}.md"

    def generate_breadcrumb(self) -> str:
        return f"*[[../index.md|Home]] > [[index.md|{self._subdir.title()}]] > {self.name}*"

    def generate_header(self) -> List[str]:
        return [f"# Palimpsest — {self.name}", "", self.generate_breadcrumb(), ""]
```

**Estimated reduction:** ~1,500 lines

---

## Phase 5: CLI Consolidation

### P6: Merge Duplicate Commands

**Backup Commands (consolidate):**
- `plm backup-full` → `metadb backup --full`
- `plm backup-list-full` → `metadb backup --list`

**Stats Commands (consolidate):**
- `plm status` + `metadb stats` → `metadb stats`
- `validate wiki stats` → keep (different purpose)

**Estimated reduction:** ~100 lines

---

## Phase 6: Pipeline Simplification (From Gemini Audit)

### P7: Reduce Meta-Programming

Gemini correctly identifies over-abstraction in the pipeline:

**Current Issues:**
- `ENTITY_REGISTRY` in `sql2wiki.py` obscures control flow
- `EntityImporter` base class adds indirection without benefit
- Dynamic configuration makes code hard to trace

**Action:**
Keep the registry pattern but:
1. Inline small entity handlers (< 50 lines)
2. Add explicit `export_people()`, `export_locations()` functions
3. Remove unused `EntityConfig` fields

**Files to simplify:**
- `dev/pipeline/sql2wiki.py`
- `dev/builders/wiki.py`

**Estimated reduction:** ~300 lines

---

## What NOT to Change (Gemini Recommendations Rejected)

| Gemini Recommendation | Reason for Rejection |
|-----------------------|---------------------|
| "Make DB read-only slave" | Breaks bidirectional sync design |
| "Delete wiki2sql.py entirely" | Needed for notes/vignettes import |
| "Remove conflict detection" | Required for multi-machine sync |
| "Remove tombstones" | Required for deletion propagation |
| "Pass DB objects directly to templates" | Would couple Jinja to SQLAlchemy |

---

## Verification Checklist

After each phase, verify:

### Tests Pass
```bash
python -m pytest tests/ -v
```

### CLI Commands Work
```bash
# Database
metadb stats
metadb health
metadb maintenance validate

# Pipeline
plm sync-db
plm export-wiki

# Search
jsearch index status
jsearch query "test"

# Validators
validate frontmatter check data/journal/content/2024/
validate consistency check
```

### Import Compatibility
```bash
python -c "from dev.database.manager import PalimpsestDB; print('OK')"
python -c "from dev.database.managers import TagManager, PersonManager; print('OK')"
```

---

## Summary

### Lines Removed (Completed)

| Phase | Task | Lines Removed |
|-------|------|---------------|
| P0 | NLP module deletion | ~2,500 |
| P0.5 | Parser bug fix | ~30 |
| P1 | Wiki CLI dedup | ~84 |
| P2 | Slugify utility | ~65 |
| P3.3 | Remove wrapper methods | ~100 |
| **Completed Total** | | **~2,779** |

### Critical Path (In Priority Order)

| Tier | Tasks | Net Lines Impact |
|------|-------|------------------|
| **Tier 1** | P25, P3, P3.1-3.2, P4, P4.1 | -5,200 |
| **Tier 2** | P26, P8 | -3,030 |
| **Tier 3** | P27, P34 | +500 |
| **Tier 4** | P28-P31 | +700 |
| **Tier 5** | P32-P33 | +300 |
| **Tier 6** | P35 | ~0 |
| **Low Priority** | P6-P24 (various) | -2,000 |

**Notes:**
- P5, P5.1-5.2, P20 (~2,050 lines) become **obsolete** if P26 is implemented
- Many Low Priority tasks (P7.2, P18, P19) are absorbed into P26

**Final target:** ~29,000 lines (from ~42,150) — **~31% reduction**

---

## Deep Dive: Method-Level Redundancy Analysis

This section documents the specific method-level over-engineering and redundancy identified through forensic code analysis.

### Quantitative Evidence

| Pattern | Occurrences | Files Affected |
|---------|-------------|----------------|
| CRUD method definitions (`get_`, `exists`, `create`, etc.) | 167 | 26 |
| Slug pattern `.lower().replace(" ", "_")` | 33 | 14 |
| `@handle_db_errors` decorator | 161 | 14 |
| `@log_database_operation` decorator | 160 | 14 |

**Analysis:** The codebase has ~160 decorated database methods, each with 2-3 decorators. This represents massive boilerplate overhead.

---

### A. Database Managers: Redundant CRUD Patterns

#### A.1: Duplicate `exists()` Implementations (7 managers)

Every manager reimplements the same pattern with inconsistent signatures:

| Manager | Signature | Lines |
|---------|-----------|-------|
| `person_manager.py` | `exists(person_name, person_full_name, include_deleted)` | 78-115 |
| `event_manager.py` | `exists(event_name, include_deleted)` | 71-93 |
| `tag_manager.py` | `exists(tag_name)` | 60-76 |
| `date_manager.py` | `exists(target_date)` | 61-76 |
| `location_manager.py` | `exists(city_name)` | ~70-90 |
| `reference_manager.py` | `exists(source_name)` | ~65-85 |
| `poem_manager.py` | `exists(poem_title)` | ~60-80 |

**Problem:** All follow identical logic: normalize → query → return boolean. 7 implementations × ~20 lines = **~140 lines of duplication**.

**Solution:** Single generic method in `BaseManager`:
```python
def exists(self, model_class: Type, lookup_field: str, value: Any) -> bool:
    normalized = self._normalize(value)
    return self.session.query(model_class).filter(
        getattr(model_class, lookup_field) == normalized
    ).first() is not None
```

#### A.2: Duplicate `get()` Implementations (8 managers, 400+ lines)

Each manager has 30-50 line `get()` methods with different parameter combinations:

| Manager | Parameters | Complexity |
|---------|------------|------------|
| `person_manager.py:119-190` | 4 optional params | 47 lines with name disambiguation |
| `event_manager.py:96-119` | 3 optional params | 24 lines |
| `location_manager.py:88-140` | 4 optional params | 52 lines |
| `date_manager.py:80-104` | 2 optional params | 25 lines |

**Problem:** Inconsistent APIs — callers must know which parameter to use. Total: **~400 lines of similar code**.

**Solution:** Generic lookup pattern:
```python
def get(self, id: Optional[int] = None, **filters) -> Optional[T]:
    if id is not None:
        return self.session.get(self.model_class, id)
    return self.session.query(self.model_class).filter_by(**filters).first()
```

#### A.3: Duplicate `get_or_create()` Pattern (10+ methods, 150+ lines)

**Locations:**
- `tag_manager.py:178`
- `person_manager.py:317`
- `date_manager.py:262`
- `event_manager.py:~200`
- `location_manager.py:~250`
- `reference_manager.py:~200`
- `poem_manager.py:~200`

**Problem:** `BaseManager` already has `_get_or_create()` at line 135-187. These methods just wrap it with entity-specific normalization.

#### A.4: Duplicate `_update_relationships()` (4 managers, 200+ lines)

**Locations:**
- `person_manager.py:530-577` (48 lines)
- `event_manager.py:384-435` (52 lines)
- `date_manager.py:300-355` (56 lines)
- `location_manager.py:600-650` (50 lines)

All have identical structure:
```python
def _update_relationships(self, entity, metadata, incremental=True):
    if "related_field" in metadata:
        collection = getattr(entity, "relationship_attr")
        for item in metadata["related_field"]:
            resolved = self._resolve(item)
            if resolved not in collection:
                collection.append(resolved)
```

**Solution:** Generic M2M updater in `BaseManager`:
```python
def update_relationships(self, entity, metadata, config: List[Tuple[str, str, Type]]):
    for attr_name, meta_key, model_class in config:
        if meta_key not in metadata:
            continue
        collection = getattr(entity, attr_name)
        for item in metadata[meta_key]:
            resolved = self._resolve(item, model_class)
            if resolved and resolved not in collection:
                collection.append(resolved)
```

---

### B. Wrapper Methods That Just Access Relationships (~60 lines)

These methods provide no value — callers should use the relationship directly:

| Method | Location | Does |
|--------|----------|------|
| `get_for_entry()` | `tag_manager.py:418-432` | `return sorted(entry.tags, key=...)` |
| `get_for_entry()` | `date_manager.py:486-496` | `return sorted(entry.dates, key=...)` |
| `get_aliases_for_person()` | `person_manager.py:747-757` | `return sorted(person.aliases, key=...)` |
| `get_entries_for_tag()` | `tag_manager.py:~440` | `return sorted(tag.entries, key=...)` |
| `get_entries_for_person()` | `person_manager.py:~780` | `return sorted(person.entries, key=...)` |

**Problem:** No database operation, just sorting. Caller could do `sorted(entry.tags, key=...)` directly.

**Action:** Delete these methods, update callers.

---

### C. Decorator Boilerplate (~1000 lines overhead)

Every CRUD method uses 2-3 decorators:
```python
@handle_db_errors          # 30 lines in decorators.py
@log_database_operation("create_person")  # 58 lines in decorators.py
@validate_metadata(["name"])  # 25 lines in decorators.py
def create(self, metadata):
    ...
```

**Impact:**
- 160 methods × 3 decorators = 480 decorator applications
- Each `@log_database_operation` generates operation_id, logs start/end/duration
- Massive logging overhead for simple operations

**Solution:** Replace with context manager:
```python
def create(self, metadata):
    with DatabaseOperation(self.logger, "create_person"):
        # actual logic - errors handled by context manager
```

This would remove ~300 lines of decorator code and make methods cleaner.

---

### D. Health Monitor Redundancy (~150 lines)

#### D.1: Identical Integrity Check Methods (lines 361-411)

```python
def _check_reference_integrity(self):
    return self._run_integrity_check_group(session, REFERENCE_INTEGRITY_CHECKS)

def _check_poem_integrity(self):
    return self._run_integrity_check_group(session, POEM_INTEGRITY_CHECKS)

def _check_manuscript_integrity(self):
    return self._run_integrity_check_group(session, MANUSCRIPT_INTEGRITY_CHECKS)

def _check_mentioned_date_integrity(self):
    return self._run_integrity_check_group(session, MENTIONED_DATE_INTEGRITY_CHECKS)
```

**Problem:** 4 one-liner methods that just call the same function with different config. 38 lines of boilerplate.

**Solution:**
```python
INTEGRITY_CHECKS = [
    ("reference", REFERENCE_INTEGRITY_CHECKS),
    ("poem", POEM_INTEGRITY_CHECKS),
    ("manuscript", MANUSCRIPT_INTEGRITY_CHECKS),
    ("mentioned_date", MENTIONED_DATE_INTEGRITY_CHECKS),
]

def check_all_integrity(self, session):
    return {name: self._run_integrity_check_group(session, config)
            for name, config in INTEGRITY_CHECKS}
```

#### D.2: Duplicate Cleanup Logic (lines 677-793, ~114 lines)

Two methods for orphan cleanup with different patterns:
- `cleanup_orphaned_records()` — loop-based deletion (slow)
- `bulk_cleanup_unused()` — bulk delete (fast)

**Problem:** Same goal, different implementations. Delete loop version, keep bulk.

---

### E. Pipeline Redundancy (~600 lines)

#### E.1: Five Identical Import Wrapper Functions (wiki2sql.py, 250+ lines)

**Locations:**
- `import_person()` lines 78-124
- `import_theme()` lines 144-171
- `import_tag()` lines 181-208
- `import_entry()` lines 218-285
- `import_event()` lines 295-362

All follow identical template:
1. Try to parse wiki file with `WikiClass.from_file()`
2. Check if result is None → skip
3. Query database for matching entity
4. Return "skipped" status
5. Catch exceptions and log error

**Problem:** These wrapper functions are unused — the batch functions call `EntityImporter` directly.

**Action:** Delete these 5 wrapper functions.

#### E.2: Three Nearly-Identical Entity Processor Classes (600+ lines)

| Class | Location | Purpose |
|-------|----------|---------|
| `EntityExporter` | `entity_exporter.py:56-299` | DB → Wiki |
| `GenericEntityExporter` | `wiki.py:102-385` | DB → Wiki (slightly different) |
| `EntityImporter` | `entity_importer.py:59-231` | Wiki → DB |

All have:
- Identical logging wrapper methods
- Identical stats updating logic
- Identical batch processing patterns

**Action:** Merge `EntityExporter` into `GenericEntityExporter`, keep only one class.

---

### F. Wiki Index Builders: 5 Identical Functions (350+ lines)

**Location:** `dev/builders/wiki_indexes.py`

| Function | Lines | Pattern |
|----------|-------|---------|
| `build_people_index()` | 36-105 | Group by category, write index |
| `build_entries_index()` | 107-177 | Group by year, write index |
| `build_locations_index()` | 179-262 | Group by country, write index |
| `build_cities_index()` | 264-339 | Group by country/region, write index |
| `build_events_index()` | 341-415 | Group by type, write index |

All follow identical template:
1. Create grouping dict
2. Build header lines
3. Loop through groups, add formatted links
4. Add statistics section
5. Write file

**Specific duplication:**
- Mention string: `f"{x.mentions} mention" + ("s" if x.mentions != 1 else "")` — 5 times
- Statistics section: 11 identical lines × 5 functions

**Solution:** Single `build_generic_index()` with configuration:
```python
def build_generic_index(
    items: List,
    wiki_dir: Path,
    entity_type: str,
    grouping_fn: Callable,
    item_formatter: Callable,
    statistics_builder: Callable,
) -> str:
```

---

### G. Wiki Dataclass Marshalling (500+ lines)

#### G.1: Massive `from_database()` Methods

| Class | Lines | Issue |
|-------|-------|-------|
| `WikiEntry.from_database` | 104-307 | 203 lines, 15 relationship loops |
| `WikiPerson.from_database` | 108-214 | 106 lines, similar pattern |
| `WikiLocation.from_database` | 45-139 | 94 lines, similar pattern |

**The Pattern (repeated 15+ times in WikiEntry alone):**
```python
for entity in sorted(db_entry.related_entities, ...):
    slug = entity.name.lower().replace(" ", "_")
    path = wiki_dir / "entity_type" / f"{slug}.md"
    link = relative_link(from_path, path)
    result.append({"name": entity.name, "link": link, ...})
```

**Solution:** Extract to helper:
```python
def _marshal_relationships(self, entities, entity_type, name_field, **extras):
    return [self._create_entity_link(e, name_field, entity_type, **extras)
            for e in entities]
```

#### G.2: Duplicate Section Generators (60+ lines)

`wiki_entry.py` lines 388-450:
```python
def _generate_people_section(self) -> str:
    if not self.people: return ""
    lines = [f"**People ({len(self.people)})**", ""]
    for person in self.people:
        lines.append(f"- [[{person['link']}|{person['name']}]] ({person['relation']})")
    return "\n".join(lines)

def _generate_locations_section(self) -> str:  # Nearly identical
def _generate_events_section(self) -> str:     # Nearly identical
def _generate_tags_section(self) -> str:       # Nearly identical
```

**Solution:** Single generic method:
```python
def _generate_section(self, title: str, items: List, format_str: str) -> str:
    if not items: return ""
    lines = [f"**{title} ({len(items)})**", ""]
    lines.extend(f"- [[{i['link']}|{format_str.format(**i)}]]" for i in items)
    return "\n".join(lines)
```

---

### H. Validator Redundancy (~160 lines)

#### H.1: Identical Enum Validators (schema.py, 60+ lines)

Three methods with identical structure:
- `validate_reference_mode()` lines 85-107
- `validate_reference_type()` lines 109-131
- `validate_manuscript_status()` lines 133-155

All do: `if value not in valid_values: return SchemaIssue(...)`

**Solution:** Single `_validate_enum_field()` method.

#### H.2: Consistency Check Patterns (consistency.py, 100+ lines)

Three methods with identical structure:
- `_check_people_consistency()` lines 447-474
- `_check_locations_consistency()` lines 476-508
- `_check_tags_consistency()` lines 510-537

All do: get from MD, get from DB, compare counts, create issue.

**Solution:** Single `_check_field_consistency()` with config.

---

### Summary: Additional Lines to Remove

| Category | Issue | Lines Saved |
|----------|-------|-------------|
| Manager CRUD duplication | exists/get/get_or_create | ~400 |
| Manager relationship updates | _update_relationships | ~150 |
| Wrapper methods | get_for_entry, etc. | ~60 |
| Decorator boilerplate | Replace with context managers | ~300 |
| Health monitor methods | Integrity check consolidation | ~100 |
| Pipeline wrappers | Delete unused import_* functions | ~250 |
| Entity processor classes | Merge duplicates | ~350 |
| Wiki index builders | Generic function | ~280 |
| Dataclass marshalling | from_database helpers | ~300 |
| Dataclass sections | Generic section generator | ~50 |
| Validator redundancy | Generic enum/consistency | ~160 |
| **Additional Total** | | **~2,400** |

**Combined with previous estimate (~9,100), total potential reduction: ~11,500 lines (~27%)**

---

## I. Utils Module Redundancy (~180 lines)

### I.1: Duplicate Hash Functions

**Locations:**
- `dev/utils/md.py:475-492` — `get_text_hash(text)`
- `dev/utils/fs.py:37-57` — `get_file_hash(file_path)`

Both compute MD5 hashes with nearly identical logic.

**Solution:** Create unified `_compute_hash(data: bytes)` with thin wrappers.

### I.2: Duplicate `extract_section()` — NAME COLLISION

**Locations:**
- `dev/utils/md.py:234-276` — Takes `List[str]`, parses markdown
- `dev/utils/wiki.py:70-81` — Takes `Dict[str, str]`, just a dict lookup

**Problem:** Same function name, completely different behavior. Namespace collision.

**Solution:** Rename wiki.py's to `get_section()`.

### I.3: Placeholder Detection Triplication

**Location:** `dev/utils/wiki.py`

Three separate placeholder validation blocks:
- `extract_notes()` (lines 102-110) — checks 3 placeholders
- `extract_vignette()` (lines 133-141) — checks 3 different placeholders
- `is_placeholder()` (lines 217-227) — checks 5 placeholders

**Solution:** Single `_is_placeholder(text)` with unified prefix list.

### I.4: Parenthetical Parsing Duplication

**Location:** `dev/utils/parsers.py`

Two functions with byte-for-byte identical parsing logic:
- `extract_name_and_expansion()` (lines 41-46)
- `parse_date_context()` (lines 149-156)

Both do: `if "(" in text and text.endswith(")"): parts = text.split("(", 1)...`

**Solution:** Extract `_split_on_parenthetical(text)` helper.

### I.5: Over-Parameterized `yaml_list()`

**Location:** `dev/utils/md.py:155-200`

```python
def yaml_list(items, hyphenated=False, smart_hyphenation=False):
```

Two mutually exclusive boolean flags. What if both are True?

**Solution:** Use `HyphenationMode` enum instead.

### I.6: Triple Section Extraction Workflow

**Location:** `dev/utils/wiki.py` (lines 84-170)

Three functions (`extract_notes`, `extract_vignette`, `extract_category`) follow identical pattern:
1. Call `extract_section()`
2. Check if falsy → return None
3. Check for placeholders → return None
4. Return stripped result

**Solution:** Create `_extract_and_validate()` factory function.

### I.7: Redundant Hyphenation Functions

**Location:** `dev/utils/parsers.py:188-231`

`spaces_to_hyphenated()` is 10 lines, `spaces_to_hyphenated_smart()` is 30 lines with 20 lines of docstring for 1 line of actual logic difference.

**Estimated Savings:** ~180 lines

---

## J. Pipeline & Builders Redundancy (~424 lines)

### J.1: Duplicate File Writing Pattern (40+ lines)

**Locations:** 10+ files repeat this exact sequence:
```python
wiki_entity.path.parent.mkdir(parents=True, exist_ok=True)
content = "\n".join(wiki_entity.to_wiki())
status = write_if_changed(wiki_entity.path, content, force)
```

Files affected:
- `builders/wiki.py:159`
- `builders/wiki_pages/entries.py:112`
- `builders/wiki_indexes.py:104, 176, 261, 338, 414`
- `builders/wiki_pages/stats.py:348`
- `builders/wiki_pages/index.py:238`
- `pipeline/entity_exporter.py:225`

**Solution:** Create `WikiFileWriter.write_from_entity()` helper.

### J.2: Logging With Null Checks (70+ instances)

**Pattern repeated 70+ times:**
```python
if self.logger:
    self.logger.log_debug("message")
```

**Problem:** `BaseBuilder` already provides `_log_*()` methods that handle null checks, but they're NOT used in:
- `pdfbuilder.py` (40+ direct logger calls)
- `txtbuilder.py` (20+ direct logger calls)

**Solution:** Replace all `if self.logger: self.logger.log_*()` with `self._log_*()`.

### J.3: PDF Build Block Duplication (~98 lines)

**Location:** `dev/builders/pdfbuilder.py:446-543`

Clean PDF block (lines 446-493) and Notes PDF block (lines 496-543) are **95% identical**.
- Lines 461-476 ≈ Lines 506-521 (15 lines, 99% duplicate)
- Lines 477-493 ≈ Lines 528-543 (nearly identical)

**Solution:** Extract `_build_pdf_type(pdf_path, preamble, pdf_vars, notes=False)`.

### J.4: Stats Collection Repetition (~30 lines)

**Locations:**
- `wiki_pages/index.py:64-90`
- `wiki_pages/stats.py:66-100`
- `ms2wiki.py:279-299`

All repeat identical entity counting queries:
```python
all_entries = session.execute(entries_query).scalars().all()
total_entries = len(all_entries)
total_words = sum(e.word_count for e in all_entries)
# ... repeat for people, tags, locations
```

**Solution:** Create `WikiStatisticsCollector` class.

### J.5: Wiki Index Grouping Patterns (~80 lines)

**Location:** `dev/builders/wiki_indexes.py`

Five index functions with identical group-iterate-sort pattern:
- `build_people_index()` (lines 36-105)
- `build_entries_index()` (lines 107-177)
- `build_locations_index()` (lines 179-262)
- `build_cities_index()` (lines 264-339)
- `build_events_index()` (lines 341-415)

All repeat:
```python
by_category = defaultdict(list)
for item in items:
    by_category[key_extractor(item)].append(item)
for category in sorted(by_category.keys()):
    # ... build lines
```

**Solution:** Create `group_entities(*key_extractors)` utility.

### J.6: Boilerplate Export Wrappers (~96 lines)

**Location:** `dev/pipeline/ms2wiki.py:158-251`

Four functions (24 lines each) are identical boilerplate:
```python
def export_characters(db, wiki_dir, journal_dir, force=False, logger=None):
    exporter = EntityExporter(db, wiki_dir, journal_dir, logger)
    return exporter.export_entities(CHARACTER_EXPORT_CONFIG, force)
```

Repeated for: `export_events`, `export_arcs`, `export_themes`

**Solution:** Use `functools.partial`:
```python
export_characters = partial(export_entity_type, CHARACTER_EXPORT_CONFIG)
```

**Estimated Savings:** ~424 lines

---

## K. SQL/YAML Parsing Redundancy (~373 lines)

### K.1: Sync State Handling — 5× Duplication (~125 lines)

The exact same 25-line sync state pattern repeated 5 times:

**Locations:**
- `pipeline/yaml2sql.py:218-266` (Entry)
- `pipeline/wiki2sql.py:227-266` (Entry)
- `pipeline/wiki2sql.py:303-349` (Event)
- `pipeline/configs/entity_import_configs.py:45-105` (Entry)
- `pipeline/configs/entity_import_configs.py:108-169` (Event)

**Pattern:**
```python
file_hash = fs.get_file_hash(wiki_file)
machine_id = socket.gethostname()
sync_mgr = SyncStateManager(session, logger)
if sync_mgr.check_conflict("Entity", entity.id, file_hash):
    logger.log_warning(...)
sync_mgr.update_or_create(entity_type=..., entity_id=..., ...)
```

**Solution:** Extract `apply_sync_state(entity_type, entity_id, wiki_file, session)`.

### K.2: Field Update Pattern — 8× Duplication (~100 lines)

**Pattern repeated 8 times:**
```python
updated = False
if wiki_entry.notes and wiki_entry.notes != db_entry.notes:
    db_entry.notes = wiki_entry.notes
    updated = True

if updated:
    session.commit()
    return "updated"
else:
    return "skipped"
```

**Locations:**
- `wiki2sql.py:258-278, 335-356, 452-466, 514-536, 593-603`
- `entity_import_configs.py:79-100, 142-163`
- `manuscript_entity_import_configs.py:67-83, 116-140`

**Solution:** Extract `check_and_update_field(wiki_value, db_value, setter)`.

### K.3: Import Function Pairs — Dual Path Redundancy (~90 lines)

**Location:** `dev/pipeline/wiki2sql.py`

Five single-entity functions exist alongside batch functions:
| Single | Lines | Batch | Lines |
|--------|-------|-------|-------|
| `import_person()` | 42 | `import_people()` | 6 (calls EntityImporter) |
| `import_theme()` | 27 | `import_themes()` | 6 |
| `import_tag()` | 27 | `import_tags()` | 6 |
| `import_entry()` | 67 | `import_entries()` | 6 |
| `import_event()` | 67 | `import_events()` | 6 |

**Problem:** Single-entity functions are never called; batch functions use EntityImporter.

**Solution:** Delete single-entity functions.

### K.4: Internal Import Statements (4×)

**Location:** `dev/dataclasses/parsers/yaml_to_db.py`

Same import statement appears 4 times inside functions:
- Line 98: `from dev.utils.parsers import split_hyphenated_to_spaces`
- Line 200: (same)
- Line 214: (same)
- Line 399: (same)

**Solution:** Move to module-level import.

### K.5: Conflict Checking — 5× Duplication (~30 lines)

**Pattern repeated 5 times:**
```python
if sync_mgr.check_conflict("EntityType", entity.id, file_hash):
    if logger:
        logger.log_warning(f"Conflict detected...")
```

**Solution:** Include in `apply_sync_state()` helper.

### K.6: Inconsistent Export — Locations Not Rehyphenated

**Problem:** In `db_to_yaml.py`:
- People names are rehyphenated (lines 120-138)
- Location names are NOT rehyphenated (lines 75-85)

This is a **consistency bug**, not just redundancy.

**Estimated Savings:** ~373 lines

---

## L. Dataclass Method Patterns (Additional ~200 lines)

### L.1: 15 Identical `from_database()` Structures

Each of the 15 wiki dataclass files has a `from_database()` method following the same template:
1. Extract wiki_dir and path
2. Loop through relationships
3. Create slug with `.lower().replace(" ", "_")`
4. Build relative link
5. Append to list

**Files:** wiki_entry.py, wiki_person.py, wiki_location.py, wiki_city.py, wiki_event.py, wiki_tag.py, wiki_theme.py, wiki_poem.py, wiki_reference.py, manuscript_entry.py, manuscript_character.py, manuscript_event.py, manuscript_theme.py, manuscript_arc.py

### L.2: 56 `relative_link()` Calls

The function `relative_link()` is called 56 times across 21 files. Each call follows the same pattern:
```python
slug = entity.name.lower().replace(" ", "_")
path = wiki_dir / "entity_type" / f"{slug}.md"
link = relative_link(from_path, path)
```

**Solution:** Create `_create_entity_link(entity, entity_type)` helper.

### L.3: 15 Identical `to_wiki()` Structures

Each dataclass has a `to_wiki()` method that:
1. Generates header with breadcrumb
2. Adds metadata section
3. Adds relationship sections
4. Returns `List[str]`

**Solution:** Move common sections to `WikiEntity` base class.

**Estimated Savings:** ~200 lines

---

## Revised Summary

### Total Redundancy Identified

| Category | Lines | Severity |
|----------|-------|----------|
| **A-H: Database Managers** (previous) | ~2,400 | HIGH |
| **I: Utils Module** | ~180 | MEDIUM |
| **J: Pipeline & Builders** | ~424 | HIGH |
| **K: SQL/YAML Parsing** | ~373 | HIGH |
| **L: Dataclass Methods** | ~200 | MEDIUM |
| **Previous structural estimate** | ~9,100 | — |
| **Additional method-level** | ~3,577 | — |
| **GRAND TOTAL** | **~12,677** | — |

### Revised Target

**From ~42,000 lines to ~29,300 lines — 30% reduction**

---

## Appendix: Files by Priority

### Immediate (P0.5)
```
dev/utils/parsers.py
dev/dataclasses/parsers/db_to_yaml.py
```

### Phase 1-2 (P2-P3)
```
dev/utils/wiki.py
dev/dataclasses/wiki_*.py (10 files)
dev/database/managers/*.py (9 files → 5 files)
```

### Phase 3-4 (P4-P5)
```
dev/database/health_monitor.py → health.py
dev/database/query_analytics.py (delete)
dev/database/query_optimizer.py (simplify)
dev/dataclasses/wiki_entity.py (enhance)
```

### Phase 5-6 (P6-P7)
```
dev/pipeline/cli/maintenance.py
dev/database/cli/backup.py
dev/pipeline/sql2wiki.py
dev/builders/wiki.py
```

---

**Document Version:** 5.1
**Authors:** Claude Opus 4.5 + Gemini 3 (synthesized) + Comprehensive Method-Level Analysis + Frontmatter Review + Follow-Up Audit (Section N) + Schema Enhancement (Section O) + Priority Reorganization
**Last Updated:** 2025-12-20
**Next Actions (by priority):**

**Tier 1 - Foundation (start here):**
1. ✅ P25: Moment model schema change (COMPLETE)
2. P3 → P3.1 → P3.2: Manager consolidation (can parallel with P25)
3. P4 → P4.1: Health simplification (independent)

**Then Tier 2 - Wiki Rewrite:**
4. P26: Template-based wiki renderer (depends on P25)

**Manual cleanup (do anytime):**
- Fix `epigraph-attribution` typos in ~70 files (see O.7.1)

---

## Quick Reference: Highest-Impact Refactoring

### Top 5 Quick Wins (Low Risk, High Reward)
1. **P17:** Delete unused single-entity imports (~230 lines) — Just delete functions
2. **P11:** Utils module consolidation (~180 lines) — Extract helpers
3. **P13:** Enforce BaseBuilder logging methods (~70 lines) — Search/replace
4. **P15:** Extract sync state helper (~125 lines) — Single new function
5. **P16:** Extract field update helper (~100 lines) — Single new function

### Top 5 High-Impact (Medium Risk)
1. **P3:** Manager consolidation (~3,000 lines) — Architecture change
2. **P5:** Wiki dataclass cleanup (~1,500 lines) — Enhance base class
3. **P4:** Health simplification (~1,400 lines) — Merge modules
4. **P7.1-7.2:** Pipeline method cleanup (~600 lines) — Merge classes
5. **P10:** Decorator → context manager (~300 lines) — Pattern change

---

## N. Follow-Up Audit: Previously Unanalyzed Modules

**Audit Date:** 2025-12-19
**Auditor:** Claude Opus 4.5 (Secondary Review)

This section documents modules that were not covered in the original audit but contain potential redundancy.

### N.1: Documentation Path Corrections

**Issue:** The workplan references non-existent paths:
- ❌ `docs/design/synchronization.md` → ✓ `docs/guides/synchronization.md`
- ❌ `docs/design/tombstones.md` → ✓ `docs/development/tombstones.md`

**Action:** Documentation references corrected.

---

### N.2: Search Module Analysis (1,076 lines) — NOT in original audit

**Files:**
- `dev/search/cli.py` (350 lines)
- `dev/search/search_engine.py` (414 lines)
- `dev/search/search_index.py` (312 lines)

**Findings:**

| Pattern | Occurrences | Lines |
|---------|-------------|-------|
| Verbose CLI docstrings | 4 commands | ~100 |
| Repeated DB initialization | 4 times | ~32 |
| `if self.logger:` pattern | 6 times | ~12 |
| Non-table-driven filter parsing | 15 filters | ~30 |

**Redundancy Details:**

1. **DB Initialization Pattern (4×):**
   ```python
   db = PalimpsestDB(
       db_path=DB_PATH,
       alembic_dir=ALEMBIC_DIR,
       log_dir=LOG_DIR,
       backup_dir=BACKUP_DIR,
       enable_auto_backup=False,
   )
   ```
   Repeated at lines 118-125, 227-234, 283-290, 326-333.

2. **Filter Parsing (search_engine.py:105-211):**
   Each filter type uses ~5 lines of identical try/except logic. Could be table-driven.

**Estimated Savings:** ~160 lines

**Priority:** P21 (Low — Search module works correctly)

---

### N.3: Core Module Analysis (2,204 lines) — NOT in original audit

**Files:**
- `dev/core/validators.py` (419 lines) — Data validation utilities
- `dev/core/backup_manager.py` (475 lines) — Backup operations
- `dev/core/logging_manager.py` (371 lines) — Logging system
- `dev/core/exceptions.py` (345 lines) — Exception hierarchy
- `dev/core/cli.py` (279 lines) — CLI statistics classes
- `dev/core/paths.py` (128 lines) — Path constants
- `dev/core/temporal_files.py` (187 lines) — Temp file handling

**Key Finding: `safe_logger()` already exists!**

Location: `dev/core/logging_manager.py:353-371`

```python
def safe_logger(logger: Optional[PalimpsestLogger]) -> PalimpsestLogger:
    """Return the provided logger or a null logger if None."""
    return logger if logger is not None else _null_logger
```

**Impact on P13:**
- P13 originally stated "Enforce BaseBuilder logging methods (~70 lines)"
- The infrastructure already exists via `NullLogger` class and `safe_logger()` function
- P13 should be rephrased: "Replace `if self.logger:` with `safe_logger(self.logger)`"
- This affects ~70+ occurrences across the codebase

**Other Redundancy in Core:**

| File | Pattern | Lines |
|------|---------|-------|
| `backup_manager.py` | `if self.logger:` repeated 10× | ~20 |
| `cli.py` | Repeated `__post_init__` validation | ~40 |
| `validators.py` | Redundant enum normalizers (3 methods) | ~30 |

**Estimated Savings:** ~90 lines

**Priority:** P22 (Low — Core module is stable infrastructure)

---

### N.4: Database Models Analysis (2,929 lines) — NOT in original audit

**Files:**
- `dev/database/models/entities.py` (373 lines)
- `dev/database/models/geography.py` (373 lines)
- `dev/database/models/creative.py` (393 lines)
- `dev/database/models/core.py` (306 lines)
- `dev/database/models/sync.py` (257 lines)
- `dev/database/models/enums.py` (220 lines)
- `dev/database/models/associations.py` (187 lines)
- `dev/database/models/base.py` (85 lines)
- `dev/database/models_manuscript.py` (634 lines)

**Redundant Property Patterns:**

| Pattern | Occurrences | Example |
|---------|-------------|---------|
| `first_X` / `last_X` date properties | 12 | `min(dates) if dates else None` |
| `X_count` properties | 15+ | `return len(self.relationship)` |
| `__str__` singular/plural | 10 | `if count == 1: ... else:` |
| `X_frequency` year-month counters | 4 | Counter by `strftime("%Y-%m")` |
| Timeline builders | 3 | Identical loop structure |

**Example of Repeated Pattern:**
```python
# Appears 12 times across models
@property
def first_X(self) -> Optional[date]:
    if not self.items:
        return None
    return min(item.date for item in self.items)
```

**Potential Simplification:**
Create `DateRangeMixin` with:
- `_get_first_date(items, date_attr='date')`
- `_get_last_date(items, date_attr='date')`
- `_get_frequency(items, date_attr='date')`

**Estimated Savings:** ~100 lines

**Priority:** P23 (Very Low — Models are mostly field definitions)

---

### N.5: Wiki Pages Utils (703 lines) — Underanalyzed

**Files:**
- `dev/builders/wiki_pages/utils/queries.py` (224 lines)
- `dev/builders/wiki_pages/utils/formatters.py` (190 lines)
- `dev/builders/wiki_pages/utils/charts.py` (226 lines)

**Finding:** These files are well-structured with minimal redundancy.

The `get_top_entities()` function (queries.py:200-224) is a good generic helper that's already being reused.

**Estimated Savings:** ~20 lines (minor consolidation possible)

**Priority:** P24 (Very Low — Already well-factored)

---

### N.6: Validators Architecture Clarification

**Question:** Is there overlap between `core/validators.py` and `validators/`?

**Answer:** No — they serve different purposes:

| Module | Purpose | Used By |
|--------|---------|---------|
| `core/validators.py` | Low-level data normalization utilities | All modules |
| `validators/` | Domain-specific frontmatter/schema validation | CLI commands |

The relationship is hierarchical:
- `validators/schema.py` imports from `core/validators.py:DataValidator`
- This is good architecture, not duplication

---

### N.7: Summary of Follow-Up Audit

| Module | Lines | Redundancy Est. | Priority |
|--------|-------|-----------------|----------|
| Search | 1,076 | ~160 | P21 |
| Core | 2,204 | ~90 | P22 |
| Database Models | 2,929 | ~100 | P23 |
| Wiki Pages Utils | 703 | ~20 | P24 |
| **Total** | **6,912** | **~370** | — |

**Revised Grand Total:**
- Original estimate: ~12,677 lines
- Follow-up additions: ~370 lines
- **New Total: ~13,047 lines (~31% reduction)**

---

### N.8: Updated Priority Items

Add to Unified Priority List:

| Priority | Task | Lines Saved | Risk |
|----------|------|-------------|------|
| **P21** | Search module consolidation | ~160 | Low |
| **P22** | Core module cleanup | ~90 | Low |
| **P23** | Database model mixins | ~100 | Very Low |
| **P24** | Wiki pages utils cleanup | ~20 | Very Low |

**P13 Revision:**
- Old: "Enforce BaseBuilder logging methods (~70 lines)"
- New: "Use existing `safe_logger()` pattern codebase-wide (~70+ occurrences)"
- Implementation: Replace all `if self.logger:` with `safe_logger(self.logger).log_*()`

---

## M. Frontmatter Parsing Analysis (Critical Review)

This section documents a forensic analysis of the actual YAML frontmatter structure in journal entries compared to the parsing logic and database architecture.

### M.1: Real Frontmatter Patterns Observed

From analysis of the longest 2025 entries:

**Simple Fields:**
```yaml
date: 2025-10-27
word_count: 6041
reading_time: 23.2
city: Montréal
```

**People Formats (6+ variations in use):**
```yaml
# Simple array
people: [Clara]

# Hyphenated with expansion
people: [Dr-Franck (Robert Franck)]

# Alias format with @
people:
  - "@Majo (María-José)"
  - "@The-pianist (Emma)"
  - Alda
  - Sarah
```

**Dates Formats (4+ variations in use):**
```yaml
dates:
  - "~"                                    # Opt-out marker
  - ". (I see @Clara's story...)"         # Entry date + inline context
  - "2025-07-22 (Video from Tirez...)"    # Date + inline context
  - date: 2025-07-12                       # Nested object form
    context: Kayaking with new lab
    people: [Sylvia, Beri, Alfonso]
    locations: [Station Bonaveture, Douglas Mental Hospital]
```

**References (nested structure):**
```yaml
references:
  - description: I shared a reel about the movie
    content: Charlie, la seule chose...
    source:
      title: Tirez sur le pianist
      author: François Truffaut
      type: film
```

**Poems (nested with multiline):**
```yaml
poems:
  - title: ICARUS
    content: |
      like icarus
      i meant to fly
```

---

### M.2: Critical Issues Found

#### Issue 1: Hyphenation Convention Works But Is Under-documented

**Location:** `dev/utils/parsers.py:159-231`

**The Convention (works correctly):**
- `-` in YAML = space in database (compound names: `María-José` → "María José")
- `_` in YAML = space, preserving real hyphens (`Rue_St-Hubert` → "Rue St-Hubert")

**Round-trip for compound names:**
1. YAML: `María-José` (indicates compound first name)
2. Import: → "María José" ✓
3. Export: → "María-José" ✓

**Round-trip for real hyphens:**
1. YAML: `Rue_St-Hubert` (underscore for space, hyphen preserved)
2. Import: → "Rue St-Hubert" ✓
3. Export: → "Rue_St-Hubert" ✓

**Issue:** The comment in `db_to_yaml.py:127-138` suggests confusion about this:
```python
# Actually, we need to be smarter: we stored it as "first_name last_name"
# But we don't know where the boundary is anymore...
```

**Real Problems:**
1. Convention is not documented for users
2. Export uses `spaces_to_hyphenated()` for people but NOT for locations (inconsistency)
3. Easy to use wrong convention by mistake

**Fix:** Document the convention clearly, ensure consistent export for all entity types.

#### Issue 2: People Parsing is Over-Engineered (114 lines)

**Location:** `dev/dataclasses/parsers/yaml_to_db.py:124-238`

**Problem:** Handles 7+ formats through inference:
```python
parts = person_str.split()
if len(parts) > 1:
    # Multiple words → infers full_name
else:
    # Single word → infers just name
```

**Why It Fails:**
- `"Dr Franck"` → 2 words → infers full_name (WRONG, "Dr" is title)
- `"María-José"` → 1 word → infers just name (already hyphenated)

**Fix:** Use explicit, unambiguous format:
```yaml
people:
  - name: Clara
  - full_name: Robert Franck
  - alias: Majo
    resolves_to: María-José
```

#### Issue 3: `name_fellow` Flag Logic is Implicit

**Location:** `dev/database/models/entities.py:60`

**Problem:** `name_fellow` (disambiguation flag) is set based on YAML format, not database state:
```python
if len(parts) > 1:
    result["people"].append({"name": first_name, "full_name": full_name})
```

**Fix:** Let database manager determine `name_fellow` based on actual collisions.

#### Issue 4: Dates Field Has Too Many Special Cases (140 lines)

**Location:** `dev/dataclasses/parsers/yaml_to_db.py:297-436`

**Handles:**
- `"~"` — opt-out marker
- `"."` — entry date shorthand
- Inline strings with context and `@`/`#` references
- Nested objects with locations/people

**Specific Problem:** Inline reference parsing:
```yaml
". (I see @Clara's story in the darkroom)"
```
Requires parsing `@Clara` from context string, looking up in `people_parsed`.

**Fix:** Require explicit structure, eliminate inline parsing:
```yaml
dates:
  - date: "."
    context: I see Clara's story
    people: [Clara]
```

#### Issue 5: Export/Import Asymmetry for Locations

**Import (`yaml_to_db.py:107-108`):**
```python
split_hyphenated_to_spaces(str(loc).strip())  # Dehyphenate
```

**Export (`db_to_yaml.py:76`):**
```python
return [loc.name for loc in entry.locations]  # NO rehyphenation
```

**Result:** Round-trip changes format:
- Input: `[Café-Pista]` → Stored: `"Café Pista"` → Output: `[Café Pista]`

Inconsistent with people handling (which does rehyphenate).

#### Issue 6: Entry Date Auto-Inclusion Logic is Fragile (35 lines)

**Location:** `dev/dataclasses/md_entry.py:463-498`

**Decision Tree:**
1. Check if `~` was present
2. Check if entry date in parsed_dates
3. Check if dates field exists
4. Conditionally add locations/people

**Fix:** Always require explicit entry date if using dates field.

#### Issue 7: Inline Reference Parsing (`@`/`#`) Adds Complexity

**Location:** `dev/utils/parsers.py:51-111`

**Problem:** `extract_context_refs()` scans for `@person` and `#location`:
```python
if word.startswith("@"):
    person = word[1:].strip(".,;:!?")
    if person.endswith("'s"):
        person = person[:-2]
```

This handles possessives, punctuation, etc. — 60 lines for a feature that could be explicit.

**Fix:** Remove inline parsing, require explicit lists.

---

### M.3: Recommended Simplifications

#### Simplification 1: Explicit People Format

**Current:**
```yaml
people: ["@Majo (María-José)", "Dr-Franck (Robert Franck)", Clara]
```

**Proposed:**
```yaml
people:
  - Clara
  - name: Robert Franck
    display: Dr. Franck
  - alias: Majo
    person: María-José
```

#### Simplification 2: Single Dates Format

**Current (4 formats):**
```yaml
dates:
  - "~"
  - ". (context with @refs)"
  - "2025-07-22 (context)"
  - date: 2025-07-12
    context: explicit
```

**Proposed (1 format):**
```yaml
dates:
  - date: 2025-10-27
  - date: 2025-07-22
    context: Video from movie
exclude_entry_date: true  # Replaces "~"
```

#### Simplification 3: Store Original Format

Don't transform hyphens/spaces. Store YAML string as-is. Only normalize for lookups.

#### Simplification 4: Remove Inline Reference Parsing

Require explicit `people:` and `locations:` lists instead of parsing from context.

---

### M.4: Summary of Frontmatter Issues

| Issue | Severity | Lines Affected |
|-------|----------|----------------|
| Hyphenation convention undocumented | LOW | Documentation only |
| People parsing complexity | HIGH | ~114 |
| name_fellow implicit logic | MEDIUM | ~30 |
| Dates special cases | HIGH | ~140 |
| Location export asymmetry | MEDIUM | ~20 |
| Entry date auto-logic | MEDIUM | ~35 |
| Inline reference parsing | MEDIUM | ~60 |

**Total complexity that could be simplified:** ~400 lines

**Priority:** The hyphenation convention works correctly but needs documentation. Focus on simplifying the parsing complexity (people, dates, inline references).

---

## O. Schema Enhancement: Moment Model

**Priority:** P25 (Schema change - requires migration)
**Risk:** Medium (data migration required)
**Benefit:** Cleaner semantics, better wiki generation, richer queries

### O.1: The Problem

The current `MentionedDate` model conflates two concepts:
1. A date that was mentioned in an entry
2. A moment in time with people, locations, and context

Additionally, `Event` has no connection to locations, making queries like "Where was the conference?" impossible.

### O.2: Current Schema

```
MentionedDate (dates table)
├─ date, context
├─ people_dates → [Person, ...]
└─ location_dates → [Location, ...]

Event (events table)
├─ event, title, description
├─ entry_events → [Entry, ...]
└─ event_people → [Person, ...]
   ❌ NO locations!
   ❌ NO specific dates!
```

### O.3: Proposed Schema: Moment Model

Rename `MentionedDate` → `Moment` with clearer semantics:

```sql
-- Moments: What happened when (semantic rename of dates table)
CREATE TABLE moments (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    context TEXT,

    -- Which entry mentions this moment
    entry_id INTEGER NOT NULL REFERENCES entries(id),

    UNIQUE(date, entry_id)
);

-- Who was at each moment (rename people_dates)
CREATE TABLE moment_people (
    moment_id INTEGER REFERENCES moments(id) ON DELETE CASCADE,
    person_id INTEGER REFERENCES people(id) ON DELETE CASCADE,
    PRIMARY KEY (moment_id, person_id)
);

-- Where each moment happened (rename location_dates)
CREATE TABLE moment_locations (
    moment_id INTEGER REFERENCES moments(id) ON DELETE CASCADE,
    location_id INTEGER REFERENCES locations(id) ON DELETE CASCADE,
    PRIMARY KEY (moment_id, location_id)
);

-- Which events a moment belongs to (NEW M2M - one moment can be part of multiple events)
CREATE TABLE moment_events (
    moment_id INTEGER REFERENCES moments(id) ON DELETE CASCADE,
    event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
    PRIMARY KEY (moment_id, event_id)
);
```

**Key Change:** Events are now linked TO moments, not to entries. This means:
- Events have dates (computed from their moments)
- Events have locations (computed from their moments)
- Events have people (computed from their moments)

### O.4: What This Enables

**Query: "Who was with me at the conference?"**
```sql
SELECT DISTINCT p.name
FROM people p
JOIN moment_people mp ON p.id = mp.person_id
JOIN moments m ON mp.moment_id = m.id
WHERE m.event_id = (SELECT id FROM events WHERE name = 'Conference Trip');
```

**Query: "All locations I visited in July 2024"**
```sql
SELECT DISTINCT l.name, m.date, m.context
FROM locations l
JOIN moment_locations ml ON l.id = ml.location_id
JOIN moments m ON ml.moment_id = m.id
WHERE m.date BETWEEN '2024-07-01' AND '2024-07-31'
ORDER BY m.date;
```

**Query: "Timeline of interactions with María"**
```sql
SELECT m.date, m.context, e.date as wrote_about_it,
       GROUP_CONCAT(l.name) as locations
FROM moments m
JOIN moment_people mp ON m.id = mp.moment_id
JOIN people p ON mp.person_id = p.id
JOIN entries e ON m.entry_id = e.id
LEFT JOIN moment_locations ml ON m.id = ml.moment_id
LEFT JOIN locations l ON ml.location_id = l.id
WHERE p.name = 'María'
GROUP BY m.id
ORDER BY m.date;
```

### O.5: Wiki Generation Benefits

**Person Page** can now show:
```markdown
## Moments Together
| Date | Context | Location | Event |
|------|---------|----------|-------|
| 2024-07-04 | July 4th party | Central Park | Independence Day |
| 2024-06-15 | Coffee catch-up | Café Olimpico | — |
```

**Location Page** can now show:
```markdown
## Visit History
| Date | Context | With | Event |
|------|---------|------|-------|
| 2024-07-04 | July 4th party | María, John | Independence Day |
```

**Event Page** can now show:
```markdown
## Conference Trip
**Dates:** 2024-07-04 to 2024-07-08
**Locations:** Convention Center, Hotel Marriott, Restaurant X
**People:** John, Dr. Franck, María
```

### O.6: Migration Steps

1. **Alembic migration:**
   - Rename `dates` → `moments`
   - Rename `people_dates` → `moment_people`
   - Rename `location_dates` → `moment_locations`
   - Rename `entry_dates` → `entry_moments`
   - Add `event_id` column to `moments` table

2. **Update models:**
   - Rename `MentionedDate` → `Moment`
   - Add `event` relationship to `Moment`
   - Update `Event` to compute dates/locations/people from moments

3. **Update managers:**
   - Rename `DateManager` → `MomentManager`
   - Update relationship handling

4. **Update wiki dataclasses:**
   - Update WikiPerson to show moment timeline
   - Update WikiLocation to show visit history
   - Update WikiEvent to show computed data

5. **Update YAML parsing:**
   - `dates:` field parsing creates `Moment` objects
   - Optional `events:` field on date items links to Events (M2M)

### O.7: YAML Schema Update

The `dates` field now supports an optional `events` subfield to link moments to specific events:

```yaml
# Current behavior: events at entry level propagate to ALL moments
events: [Dating-Clara]
dates:
  - date: 2024-07-04
    context: July 4th party

# NEW: events within dates link only to THAT moment
dates:
  - date: 2024-07-04
    context: July 4th party
    people: [María, John]
    locations: [Central Park]
    events: [Dating-Clara, Summer-Trip]  # M2M: multiple events per moment
```

**Parsing behavior:**
- If `events` at entry level only → propagate to all moments (backward compatible)
- If `events` within a date item → link only to that specific moment
- Both can coexist (entry-level for default, date-level for overrides)

### O.7.1: YAML Typos to Fix Manually

The frontmatter review discovered `epigraph-attribution` (hyphen) used in ~70 files instead of `epigraph_attribution` (underscore). The parser expects underscores. These need manual correction:

```bash
# Find all files with hyphenated key
grep -r "epigraph-attribution" data/journal/content/md/2025/

# Fix with sed (or manually)
sed -i 's/epigraph-attribution/epigraph_attribution/g' data/journal/content/md/2025/*.md
```

### O.8: Future Enhancement - Moment Type Distinction

**Status:** Design consideration for future work

The current schema conflates two semantically different uses of dates:

1. **Occurred**: Something that happened on this date (during the entry's events)
   - Example: `2024-07-04 (July 4th party with María at Central Park)`

2. **Referenced**: A callback/reference to a past date
   - Example: `2025-01-11 (I gave Clara the negatives she forgot at my house)` with `type: reference`
   - Or use a different field: `references:` vs `dates:` in YAML
   - Note: Using `-` prefix would conflict with YAML list syntax

**Potential Enhancement:**
```python
class MomentType(Enum):
    OCCURRED = "occurred"     # Entry is about what happened on this date
    REFERENCED = "referenced"  # Entry references/mentions this past date

# Moment model gains:
moment_type: Mapped[MomentType] = mapped_column(
    SQLEnum(MomentType), default=MomentType.OCCURRED
)
```

**Wiki Benefits:**
- Person page could show "Moments Together" vs "References to [Person]"
- Entry page could distinguish "What happened" vs "Callbacks to past events"
- Timeline views could filter by type

**Note:** Current implementation maintains backward compatibility. The context field can implicitly capture this distinction. Consider adding `moment_type` in a future iteration if needed.

### O.9: Files to Modify

| File | Change |
|------|--------|
| `dev/database/models/geography.py` | Rename MentionedDate → Moment |
| `dev/database/models/associations.py` | Rename tables + add moment_events M2M |
| `dev/database/managers/date_manager.py` | Rename → moment_manager.py |
| `dev/dataclasses/parsers/yaml_to_db.py` | Update date parsing |
| `dev/dataclasses/wiki_*.py` | Update to use moments |
| `alembic/versions/xxx_moment_model.py` | Migration script |

### O.9: Estimated Effort

- Migration script: 2-3 hours
- Model/manager updates: 2-3 hours
- Wiki dataclass updates: 2-3 hours
- Testing: 2-3 hours
- **Total: ~1 day**

### O.10: Poem Simplification Note

Poems do NOT need a status field. They are single-date creations, not works in progress. The current Poem → PoemVersion → Entry structure is sufficient:

```python
class Poem(Base):
    id: int
    title: str
    # NO status field - poems are just documented, not tracked

class PoemVersion(Base):
    id: int
    poem_id: int
    entry_id: int  # Which entry contains this version
    content: str
    revision_date: date
    version_hash: str  # For deduplication
```

---

## P. Wiki System Rewrite: Template-Based Renderer

**Priority:** P26
**Risk:** Medium
**Benefit:** ~2,500 lines saved, cleaner architecture, easier to maintain

### P.1: The Problem

Currently there are 11 wiki dataclass files (~3,000 lines) with 70% duplicate code:
- `wiki_entry.py`, `wiki_person.py`, `wiki_location.py`, `wiki_city.py`
- `wiki_event.py`, `wiki_tag.py`, `wiki_theme.py`, `wiki_poem.py`
- `wiki_reference.py`, `wiki_entity.py`, `wiki_vignette.py`

Each has:
- `from_database()` method with similar loops
- `to_wiki()` method generating markdown
- Properties for statistics

### P.2: Proposed Solution

Replace with a single Jinja-based renderer + templates:

```
dev/wiki/
├── __init__.py
├── renderer.py           # Single Jinja-based renderer (~150 lines)
├── exporter.py           # SQL → Wiki export (~200 lines)
├── importer.py           # Wiki → SQL sync (~200 lines)
├── config.py             # Sync directions, paths (~100 lines)
└── templates/
    ├── base.jinja2
    ├── entry.jinja2
    ├── person.jinja2
    ├── location.jinja2
    ├── city.jinja2
    ├── event.jinja2
    ├── moment.jinja2
    ├── tag.jinja2
    ├── poem.jinja2
    ├── reference.jinja2
    └── indexes/
        ├── people.jinja2
        ├── locations.jinja2
        ├── timeline.jinja2
        └── entries_monthly.jinja2
```

### P.3: Renderer Design

```python
class WikiRenderer:
    def __init__(self, wiki_dir: Path, template_dir: Path):
        self.wiki_dir = wiki_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.env.filters['wikilink'] = self._wikilink
        self.env.filters['slugify'] = slugify

    def render_entity(self, entity_type: str, data: dict) -> str:
        template = self.env.get_template(f"{entity_type}.jinja2")
        return template.render(**data, wiki_dir=self.wiki_dir)

    def render_index(self, index_type: str, items: list) -> str:
        template = self.env.get_template(f"indexes/{index_type}.jinja2")
        return template.render(items=items)
```

### P.4: Files to Remove

```
dev/dataclasses/wiki_entry.py      (~542 lines)
dev/dataclasses/wiki_person.py     (~478 lines)
dev/dataclasses/wiki_location.py   (~296 lines)
dev/dataclasses/wiki_city.py       (~300 lines)
dev/dataclasses/wiki_event.py      (~318 lines)
dev/dataclasses/wiki_tag.py        (~231 lines)
dev/dataclasses/wiki_theme.py      (~237 lines)
dev/dataclasses/wiki_poem.py       (~238 lines)
dev/dataclasses/wiki_reference.py  (~252 lines)
dev/dataclasses/wiki_entity.py     (~121 lines)
dev/builders/wiki_indexes.py       (~400 lines)
```

**Total removed:** ~3,400 lines
**Total added:** ~650 lines (renderer + templates)
**Net reduction:** ~2,750 lines

---

## Q. Main Wiki Dashboards

**Priority:** P27
**Risk:** Low
**Benefit:** Better wiki navigation and insights

### Q.1: Dashboard Pages

Add these dashboard templates:

1. **Home Dashboard** (`wiki/index.md`):
   - Recent entries (last 7 days)
   - Most mentioned people this month
   - Quick stats (total entries, people, locations)
   - Links to all indexes

2. **Timeline Dashboard** (`wiki/timeline.md`):
   - All moments chronologically
   - Grouped by year/month
   - Shows who was there, where

3. **Statistics Dashboard** (`wiki/stats.md`):
   - Word count trends
   - Entry frequency by month
   - Tag usage over time
   - Geographic distribution

4. **Relationships Dashboard** (`wiki/relationships.md`):
   - People who appear together frequently
   - Locations associated with people

### Q.2: Templates Location

```
dev/wiki/templates/dashboards/
├── home.jinja2
├── timeline.jinja2
├── stats.jinja2
└── relationships.jinja2
```

---

## R. Manuscript System

**Priority:** P28-P30
**Risk:** Medium-High
**Benefit:** Complete manuscript curation workflow

### R.1: Design Principles

1. **YAML (minimal):** Just mark entries for inclusion
2. **Main Wiki:** Shows entries with manuscript status, links to manuscript wiki
3. **Manuscript Wiki:** THE workspace for curation
4. **Manuscript Drafts:** In `data/manuscript/` (outside wiki, like `data/journal/`)
5. **Many-to-many:** Characters ↔ People (not one-to-one)
6. **Manual linking:** Wiki edits in specific sections, parsed by importer

### R.2: YAML Schema (P29)

```yaml
# Simple status
manuscript: source

# Or with quote
manuscript:
  status: quote
  content: "The specific line I want to keep"
```

**Statuses:**
- `source` — Full entry to be edited/adapted
- `reference` — Keep in mind for story context
- `quote` — Specific content to extract

No chapter numbers. Absence of field = not in manuscript.

### R.3: Database Schema (P28)

```sql
-- Manuscript entry metadata
CREATE TABLE manuscript_entries (
    entry_id INTEGER PRIMARY KEY REFERENCES entries(id),
    status TEXT NOT NULL CHECK(status IN ('source', 'reference', 'quote')),
    notes TEXT,                    -- Wiki-editable
    sourced_in TEXT,               -- Wiki-editable: where used
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- For quote status
CREATE TABLE manuscript_quotes (
    id INTEGER PRIMARY KEY,
    entry_id INTEGER REFERENCES entries(id),
    content TEXT NOT NULL,         -- From YAML
    notes TEXT,                    -- Wiki-editable
    sourced_in TEXT                -- Wiki-editable
);

-- Characters (wiki-created, never real names)
CREATE TABLE manuscript_characters (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,            -- Always fictional
    description TEXT,
    arc TEXT,
    voice TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Many-to-many: characters ↔ people
CREATE TABLE manuscript_character_sources (
    character_id INTEGER REFERENCES manuscript_characters(id),
    person_id INTEGER REFERENCES people(id),
    notes TEXT,
    PRIMARY KEY (character_id, person_id)
);

-- Track which manuscript entries a character appears in
CREATE TABLE manuscript_character_entries (
    character_id INTEGER REFERENCES manuscript_characters(id),
    entry_id INTEGER REFERENCES manuscript_entries(entry_id),
    notes TEXT,
    PRIMARY KEY (character_id, entry_id)
);

-- Chapters (wiki-created, link to external drafts)
CREATE TABLE manuscript_chapters (
    id INTEGER PRIMARY KEY,
    number INTEGER,
    title TEXT,
    draft_path TEXT,               -- Path to draft in data/manuscript/
    summary TEXT,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Link chapters to source entries
CREATE TABLE manuscript_chapter_entries (
    chapter_id INTEGER REFERENCES manuscript_chapters(id),
    entry_id INTEGER REFERENCES manuscript_entries(entry_id),
    notes TEXT,
    PRIMARY KEY (chapter_id, entry_id)
);
```

### R.4: Wiki Structure (P30)

```
data/wiki/
├── entries/
│   └── 2024/
│       └── 2024-11-01.md     # Links to source markdown
├── people/
│   └── maria_jose.md         # Has "Used as Reference for Characters" section
└── manuscript/
    ├── index.md              # Dashboard: stats, recent activity
    ├── entries/
    │   └── 2024/
    │       ├── 2024-01.md    # Monthly index of manuscript entries
    │       ├── 2024-02.md
    │       └── ...
    ├── characters/
    │   ├── index.md          # All characters
    │   └── marie.md          # Character page with "Based On" section
    └── chapters/
        ├── index.md          # Chapter list with links to drafts
        └── 01.md             # Chapter wiki page (links to data/manuscript/01.md)

data/manuscript/              # Outside wiki, actual drafts
├── chapters/
│   ├── 01.md                 # Chapter 1 draft
│   ├── 02.md
│   └── ...
└── notes/
    └── themes.md             # General notes
```

### R.5: Bidirectional Sync (P31)

**From YAML → DB:**
- `manuscript` field → `manuscript_entries` table
- `manuscript.content` → `manuscript_quotes` table

**From Wiki → DB (wiki-editable fields):**

```python
MANUSCRIPT_SYNC = {
    "manuscript_entry": {
        "from_yaml": ["status"],
        "wiki_editable": ["notes", "sourced_in"],
    },
    "manuscript_character": {
        "from_yaml": [],  # All wiki-created
        "wiki_editable": ["name", "description", "arc", "voice", "notes"],
        "link_section": "## Based On",  # Parse links from this section
    },
    "person": {
        "link_section": "## Used as Reference for Characters",
    },
    "manuscript_chapter": {
        "from_yaml": [],
        "wiki_editable": ["title", "summary", "notes", "draft_path"],
    },
}
```

**Link parsing:** Importer looks for wikilinks in specific sections to create associations.

### R.6: Data Directory Change

Rename/repurpose `data/vignettes/` → `data/manuscript/`:
- `data/manuscript/chapters/` — Chapter drafts
- `data/manuscript/notes/` — General manuscript notes

These are standalone markdown files, linked from wiki but not part of it.

---

## S. Neovim Commands

**Priority:** P32
**Risk:** Low
**Benefit:** Reduced mental load for manuscript curation

### S.1: Proposed Commands

1. **`:PalimpsestCreateCharacter <name>`**
   - Creates `data/wiki/manuscript/characters/<slug>.md`
   - Pre-populates with template (empty "Based On" section)
   - Opens the new file

2. **`:PalimpsestLinkCharacter`** (on Person page)
   - Prompts for character name (autocomplete from existing)
   - Adds link under "## Used as Reference for Characters"
   - Adds reciprocal link on character page under "## Based On"

3. **`:PalimpsestCreateChapter <number>`**
   - Creates `data/wiki/manuscript/chapters/<number>.md` (wiki page)
   - Creates `data/manuscript/chapters/<number>.md` (draft file)
   - Links them together
   - Opens the draft file

4. **`:PalimpsestExportWiki`** / **`:PalimpsestImportWiki`**
   - Already exist, ensure they work with new structure

### S.2: Implementation

Location: `dev/lua/palimpsest/manuscript.lua`

---

## T. Statistics Materialized Views

**Priority:** P33
**Risk:** Low
**Benefit:** Fast dashboard queries

### T.1: Views to Create

```sql
CREATE VIEW person_stats AS
SELECT
    p.id, p.name,
    COUNT(DISTINCT ep.entry_id) as entry_count,
    COUNT(DISTINCT mp.moment_id) as moment_count,
    MIN(e.date) as first_mention,
    MAX(e.date) as last_mention
FROM people p
LEFT JOIN entry_people ep ON p.id = ep.people_id
LEFT JOIN entries e ON ep.entry_id = e.id
LEFT JOIN moment_people mp ON p.id = mp.person_id
GROUP BY p.id;

CREATE VIEW location_stats AS
SELECT
    l.id, l.name, c.city as city_name,
    COUNT(DISTINCT el.entry_id) as entry_count,
    COUNT(DISTINCT ml.moment_id) as visit_count
FROM locations l
JOIN cities c ON l.city_id = c.id
LEFT JOIN entry_locations el ON l.id = el.location_id
LEFT JOIN moment_locations ml ON l.id = ml.moment_id
GROUP BY l.id;

CREATE VIEW monthly_stats AS
SELECT
    strftime('%Y-%m', e.date) as month,
    COUNT(*) as entry_count,
    SUM(e.word_count) as total_words,
    COUNT(DISTINCT ep.people_id) as unique_people
FROM entries e
LEFT JOIN entry_people ep ON e.id = ep.entry_id
GROUP BY strftime('%Y-%m', e.date);

CREATE VIEW manuscript_stats AS
SELECT
    status,
    COUNT(*) as entry_count
FROM manuscript_entries
GROUP BY status;
```

---

## P25-P35 Quick Reference

See **[Unified Priority List (Dependency-Ordered)](#unified-priority-list-dependency-ordered)** at top of document for the canonical priority list with tiers and dependencies.

| Priority | Section | Description |
|----------|---------|-------------|
| P25 | Section O | Moment model schema |
| P26 | Section P | Template-based wiki |
| P27 | Section Q | Wiki dashboards |
| P28-P31 | Section R | Manuscript system |
| P32 | Section S | Neovim manuscript commands |
| P33 | Section T | Stats materialized views |
| P34 | Section V | Neovim plugin fixes |
| P35 | Section U | Code reorganization |

---

## U. Code Reorganization

**Priority:** P35 (After P4 and P26 are complete)
**Risk:** Medium (file moves, import changes)

### U.1: Rationale

After P4 (delete health/analytics) and P26 (template-based wiki), the codebase structure will naturally simplify. At that point, reorganization becomes practical without conflicting with ongoing work.

### U.2: Quick Wins (Do Now If Convenient)

| Change | Rationale |
|--------|-----------|
| Move `database/models_manuscript.py` → `database/models/manuscript.py` | Consistency with other models |
| Move `database/decorators.py` → `core/decorators.py` | It's core infrastructure |

### U.3: Post-P4/P26 Reorganization

| Current | Proposed | Rationale |
|---------|----------|-----------|
| CLI in `pipeline/cli/`, `database/cli/`, `validators/cli/` | Single `cli/` directory | One place for all commands |
| Wiki logic in 6 locations | Consolidated `wiki/` directory | All wiki logic together |
| `dataclasses/wiki_*.py` (11 files) | Replaced by `wiki/templates/` | Per P26 |

### U.4: Ideal Future Structure

```
dev/
├── core/              # Logging, exceptions, validators, decorators
├── models/            # All SQLAlchemy models (flat)
├── db/                # Database operations (rename from database/)
│   ├── managers/
│   └── sync/          # Tombstone + sync state
├── parse/             # YAML/MD parsing
├── wiki/              # All wiki logic consolidated
│   └── templates/     # Jinja templates (P26)
├── manuscript/        # All manuscript logic
├── build/             # PDF, TXT builders
├── cli/               # All CLI commands
├── migrations/
└── utils/
```

---

## V. Neovim Plugin Fixes and Enhancements

**Priority:** P34
**Risk:** Low
**Note:** Confirm detailed implementation with user before proceeding.

### V.1: Critical Bug Fixes

| Bug | Location | Fix |
|-----|----------|-----|
| Hardcoded root path | `config.lua:3-4` | Make configurable via `setup({root = "..."})` |
| Missing `/` in templates path | `config.lua:4` | `root .. "templates/wiki"` → `root .. "/templates/wiki"` |
| Missing `log.template` | `templates.lua:111` | Create template or remove reference |
| Wrong pipeline references | `commands.lua:205,111` | `manuscript2wiki` → `ms2wiki`, remove `validate_wiki` |
| Unchecked dependencies | `keymaps.lua:1,4` | Wrap `which-key` and `mini.icons` in pcall |

### V.2: Quick Enhancements

| Enhancement | Description |
|-------------|-------------|
| Add manuscript to FZF browse | Include `wiki/manuscript/` in entity paths |
| Add manuscript to FZF search | Search characters, arcs, themes |
| Add manuscript quick access | Add manuscript index pages to quick access |

### V.3: New Commands for Manuscript Workflow

**High Priority:**

| Command | Description |
|---------|-------------|
| `:PalimpsestCreateCharacter` | Create character wiki page, prompt for name, optionally link to Person |
| `:PalimpsestCreateChapter` | Create chapter draft in `data/manuscript/chapters/` |
| `:PalimpsestMarkForManuscript` | Add `manuscript: source` to current entry's YAML frontmatter |
| `:PalimpsestBrowseManuscript` | FZF for manuscript wiki (entries/characters/chapters) |
| `:PalimpsestInsertLink` | FZF picker → insert wiki link at cursor |

**Medium Priority:**

| Command | Description |
|---------|-------------|
| `:PalimpsestCreateEntity` | Generic: create Person/Location/Event/Tag using templates |
| `:PalimpsestJumpToSource` | From wiki page, jump to original journal entry |
| `:PalimpsestAddPerson` | Add person to current entry's YAML `people:` field |
| `:PalimpsestAddLocation` | Add location to current entry's YAML |
| `:PalimpsestAddTag` | Add tag to current entry's YAML |

### V.4: Future Advanced Features

| Feature | Description | Effort |
|---------|-------------|--------|
| nvim-cmp source | Autocomplete entity names in YAML frontmatter | High |
| LSP-like hover | Show entity info on hover over wiki links | High |
| Auto-sync on save | Option to auto-import wiki edits to DB | Medium |
| Manuscript dashboard | Floating window showing entry counts by status | Medium |

### V.5: Files to Modify

| File | Changes |
|------|---------|
| `config.lua` | Make root configurable, fix templates path |
| `commands.lua` | Add new commands, fix pipeline references |
| `fzf.lua` | Add manuscript entity paths |
| `keymaps.lua` | Wrap dependencies in pcall, add new keymaps |
| `templates.lua` | Add entity creation functions |
| `autocmds.lua` | Optional auto-sync hook |

### V.6: Implementation Note

**⚠️ Confirm detailed implementation approach with user before proceeding.** The specific UX for commands like `:PalimpsestCreateCharacter` (prompts, defaults, template format) should be discussed.
