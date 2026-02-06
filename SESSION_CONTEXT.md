# Session Context: Codebase Audit and EntryManager Rebuild

## Original Prompt

User asked to implement the workplan from the plan file (`robust-growing-wand.md`):
- WP-1: Delete dead code and artifacts
- WP-2: Fix stale wiki references in Python code
- WP-3: Fix broken code (EntryRelationshipHelper disconnect + Location Manager API mismatch)
- WP-4: Documentation overhaul (banners for not-yet-implemented wiki features, fix stale refs)
- WP-5: Update PLAN.md phase statuses

After WP-1 through WP-5 were completed, user pointed out that WP-3 was done superficially: I deleted `entry_helpers.py` instead of fixing the real issue — EntryManager has 6+ relationship processors commented out as TODOs that do nothing.

User then asked for a **deep audit** of whether the schema and managers actually work, not just whether the docs are tidy. Two audit agents were launched:
1. **Database Models Audit**: PLAN.md schema vs actual code models
2. **Metadata Import Pipeline Audit**: What the importer actually does

---

## Completed Work (Uncommitted)

All changes are staged but **not committed**. 28 files changed, 115 insertions, 459 deletions.

### WP-1: Dead Code Cleanup
- Deleted `dev/builders/wiki_pages/` (orphaned `__pycache__` only)
- Deleted orphaned `.pyc` files for wiki, narrative, wiki_pages, wiki_indexes
- Deleted `dev/bin/__pycache__/` (orphaned bytecodes from deleted scripts)

### WP-2: Fixed Stale Wiki References in Python
- `dev/validators/consistency.py` — Removed `wiki_dir` parameter, `_get_wiki_dates`, wiki checks from `check_entry_existence`
- `dev/validators/cli/consistency.py` — Removed `wiki_dir` CLI parameter and all references
- `dev/database/managers/entry_manager.py` — Updated `yaml2sql` → `import-metadata` in docstring
- `dev/pipeline/configs/vocabulary.py` — Updated stale `dev/wiki/` reference
- `dev/utils/md.py` — Updated workflow reference from `md2wiki, sql2wiki` to `metadata import`
- `dev/builders/__init__.py` — Updated stale `dev/wiki/exporter.py` reference
- `dev/database/models/entities.py` — Updated slug description from "wiki filenames" to generic
- `tests/unit/validators/test_consistency_validator.py` — Removed wiki-related tests and fixtures

### WP-3: Code Fixes (Partial)
- **Deleted** `dev/database/managers/entry_helpers.py` (disconnected, unused)
- **Fixed** Location Manager API mismatch: `create_city()` now validates `"name"` key (matching EntityManager config)
- **Fixed** `poem_manager.py` unused `md` import
- **NOT DONE**: Rebuilding EntryManager's commented-out relationship processors

### WP-4: Documentation Overhaul
- Added "not yet implemented" banners to wiki docs: `wiki-fields.md`, `synchronization.md`, `manuscript-features.md`
- Fixed stale field references: `metadata-field-reference.md` (removed `speaker`), `database-managers.md` (removed `version_hash`, fixed MentionedDate→NarratedDate), `entity_curation_workflow.md`, `review_workflow.md`
- Updated: `architecture.md`, `commands.md`, `validation_guide.md`, `getting-started.md`, `full-setup.md`, `testing.md`, `neovim.md`, `neovim-plugin-dev.md`, `type-checking.md`

### WP-5: PLAN.md Updated
- Phase 14a: marked COMPLETE
- Phase 14b: marked COMPLETE
- Phase 14b-2: marked COMPLETE
- Phase 14b-3: marked DEFERRED (JSON export pipeline used instead)
- Phase 14c/14d: marked DEFERRED (wiki rebuild after YAML→DB→JSON pipeline complete)

---

## Audit Results

### 1. Database Models Audit (PLAN.md vs Code)

**Key Findings:**

| Model | Status | Notable Differences |
|-------|--------|---------------------|
| Entry | MOSTLY MATCH | Extra fields in code: `metadata_hash`, `summary`, `rating`, `rating_justification`. `SoftDeleteMixin` not in plan. Events is M2M in code but O2M in plan. `poems` vs `poem_versions` naming. Missing `manuscript_sources` relationship. |
| City | FULL MATCH | — |
| Location | FULL MATCH | — |
| Person | FULL MATCH | — |
| Event | MATCH | Slight naming difference in relationship attribute |
| Tag | FULL MATCH | — |
| Theme | FULL MATCH | — |
| NarratedDate | FULL MATCH | — |
| Scene | FULL MATCH | — |
| Thread | FULL MATCH | — |
| Arc | FULL MATCH | — |
| Motif/MotifInstance | FULL MATCH | — |
| Reference/ReferenceSource | FULL MATCH | — |
| Poem/PoemVersion | MINOR | `version_hash` removed from code (was in original plan) |

### 2. Metadata Import Pipeline Audit

**Two completely separate import paths exist:**

1. **`sync-db` command** → Uses `yaml2sql.py` → old `MdEntry` dataclass + `PalimpsestDB` manager pipeline
2. **`import-metadata` command** → Uses `metadata_importer.py` → newer pipeline, **bypasses all managers**, does raw SQLAlchemy

**The `import-metadata` pipeline (metadata_importer.py) handles ALL relationships correctly:**

| Relationship | Method | Status |
|-------------|--------|--------|
| Entry scalar fields | `_create_entry()` | WORKS |
| People (M2M) | `_link_entry_people()` | WORKS |
| Locations (M2M) | `_link_entry_locations()` | WORKS |
| Cities (M2M) | `_link_entry_locations()` | WORKS |
| NarratedDates (O2M) | `_create_narrated_dates_from_frontmatter()` | WORKS |
| Scenes (O2M) | `_create_scenes()` | WORKS |
| Events (M2M) | `_create_events()` | WORKS |
| Threads (O2M) | `_create_threads()` | WORKS |
| Arcs (M2M) | `_link_arcs()` | WORKS |
| Tags (M2M) | `_link_tags()` | WORKS |
| Themes (M2M) | `_link_themes()` | WORKS |
| Motifs (O2M) | `_create_motif_instances()` | WORKS |
| References (O2M) | `_create_references()` | WORKS |
| Poems (O2M) | `_create_poems()` | WORKS |

**The EntryManager only handles 4 of these:**
- Cities (M2M) ✅
- People (M2M) ✅
- Events (M2M) ✅
- Tags (M2M) ✅

**EntryManager is missing 10 relationship processors:**
- Locations (M2M with city context) — commented out TODO
- NarratedDates (O2M) — commented out TODO
- Scenes (O2M) — not even listed
- Threads (O2M) — not even listed
- Arcs (M2M) — not even listed
- Themes (M2M) — not even listed
- Motifs/MotifInstances (O2M) — not even listed
- References (O2M with ReferenceSource) — commented out TODO
- Poems/PoemVersions (O2M) — commented out TODO
- Related entries — commented out TODO (relationship not in model)

---

## Pending Task: Rebuild EntryManager Relationship Processors

### The Core Question

The metadata_importer.py works for bulk import but bypasses all managers. EntryManager is the programmatic API that other code (sync-db, future wiki import, manual operations) would use. It needs to handle all the relationships the importer does.

### What Needs to Be Built

Each missing processor in `EntryManager.update_relationships()` (lines 699-737 in current code). Reference implementations exist in `metadata_importer.py`:

#### 1. Locations (M2M with city context)
- **Reference**: `metadata_importer.py:811-841` (`_link_entry_locations`)
- **Input**: `metadata["locations"]` — dict of `{city_name: [location_names]}` or list of `{"name": str, "city": str}` dicts
- **Action**: Get/create City, get/create Location(name, city), add to `entry.locations` and `entry.cities`
- **Note**: Uses `LocationManager.get_or_create_city()` and `get_or_create_location()`

#### 2. NarratedDates (O2M)
- **Reference**: `metadata_importer.py:843-871` (`_create_narrated_dates_from_frontmatter`)
- **Input**: `metadata["narrated_dates"]` — list of date strings or date objects
- **Action**: Create `NarratedDate(date=..., entry_id=entry.id)`
- **Model**: `dev/database/models/core.py:341` (`NarratedDate`)

#### 3. Scenes (O2M)
- **Reference**: `metadata_importer.py:1010-1062` (`_create_scenes`)
- **Input**: `metadata["scenes"]` — list of dicts with `name`, `description`, `date`, `people[]`, `locations[]`
- **Action**: Create Scene, add SceneDate records, link people/locations as M2M
- **Models**: `dev/database/models/analysis.py:62` (Scene), `:171` (SceneDate)

#### 4. Events (already handled as M2M, but needs scene linking)
- **Reference**: `metadata_importer.py:1090-1142` (`_create_events`)
- **Input**: `metadata["events"]` — list of dicts with `name`, `scenes[]`
- **Action**: Get/create Event, link scenes by name, link entry to event
- **Note**: Current M2M handler resolves events but doesn't handle scene linking

#### 5. Threads (O2M)
- **Reference**: `metadata_importer.py:1144-1210` (`_create_threads`)
- **Input**: `metadata["threads"]` — list of dicts with `name`, `from`, `to`, `entry`, `content`, `people[]`, `locations[]`
- **Action**: Create Thread with date fields, link people/locations
- **Model**: `dev/database/models/analysis.py:392` (Thread)

#### 6. Arcs (M2M)
- **Reference**: `metadata_importer.py:1212-1247` (`_link_arcs`)
- **Input**: `metadata["arcs"]` — list of arc name strings
- **Action**: Get/create Arc by name, add to `entry.arcs`
- **Model**: `dev/database/models/analysis.py:328` (Arc)

#### 7. Themes (M2M)
- **Reference**: `metadata_importer.py:1286-1321` (`_link_themes`)
- **Input**: `metadata["themes"]` — list of theme name strings
- **Action**: Get/create Theme by name, add to `entry.themes`
- **Model**: `dev/database/models/entities.py:334` (Theme)

#### 8. Motif Instances (O2M)
- **Reference**: `metadata_importer.py:1323-1371` (`_create_motif_instances`)
- **Input**: `metadata["motifs"]` — list of dicts with `name`, `description`
- **Action**: Get/create Motif, create MotifInstance linking entry to motif
- **Models**: `dev/database/models/metadata.py:71` (Motif), `:117` (MotifInstance)

#### 9. References (O2M with ReferenceSource)
- **Reference**: `metadata_importer.py:1373-1448` (`_create_references`)
- **Input**: `metadata["references"]` — list of dicts with `source: {title, author, type, url}`, `content`, `description`, `mode`
- **Action**: Get/create ReferenceSource, create Reference linking entry to source
- **Models**: `dev/database/models/creative.py:37` (ReferenceSource), `:116` (Reference)

#### 10. Poems (O2M)
- **Reference**: `metadata_importer.py:1450-1497` (`_create_poems`)
- **Input**: `metadata["poems"]` — list of dicts with `title`, `content`
- **Action**: Get/create Poem by title, create PoemVersion linking entry to poem
- **Models**: `dev/database/models/creative.py:200` (Poem), `:263` (PoemVersion)
- **Note**: `PoemManager` already handles this — could delegate to `PoemManager.create_version()`

### Architecture Decision Needed

**Option A: Build processors directly in EntryManager**
- Mirror metadata_importer.py logic but using existing managers where possible
- Simpler, no new files needed
- Risk of duplicating logic

**Option B: Rebuild EntryRelationshipHelper as a helper class**
- Factor common resolution/creation logic into a shared helper
- Both EntryManager and metadata_importer could use it
- Cleaner but requires refactoring metadata_importer too

**Option C: Have EntryManager delegate to metadata_importer's methods**
- Minimal new code
- But metadata_importer has batch-specific logic (stats tracking, error thresholds)

**Recommended: Option A** — Build directly in EntryManager using existing managers (PersonManager, LocationManager, EventManager, PoemManager). This keeps the API clean and the manager is the right place for this logic. The metadata_importer can stay as-is for bulk import.

---

## Other Pending Issues

### Test Suite
- **625 passed, 101 errors** when running full suite
- Errors are pre-existing test isolation issues (tests pass individually)
- This is an infrastructure issue, not a code bug

### sync-db vs import-metadata
- Two parallel import paths exist
- `sync-db` uses the old `yaml2sql.py` + `MdEntry` dataclass pipeline
- `import-metadata` uses the newer `metadata_importer.py` pipeline
- Consider deprecating `sync-db` once EntryManager is fully functional

### Tombstone System
- Commented-out tombstone calls in `update_relationships()` (lines 654-662, 669-671, etc.)
- Tombstone system exists in code but is not wired up
- Needed for multi-machine sync — revisit when sync is implemented

---

## Files of Interest

| File | Purpose |
|------|---------|
| `dev/database/managers/entry_manager.py` | Main file to modify — rebuild relationship processors |
| `dev/pipeline/metadata_importer.py` | Reference implementation for all relationship processing |
| `dev/database/managers/location_manager.py` | Has `get_or_create_city()`, `get_or_create_location()` |
| `dev/database/managers/poem_manager.py` | Has `create_version()` for poem+version creation |
| `dev/database/managers/event_manager.py` | Has `get_or_create()` for events |
| `dev/database/managers/person_manager.py` | Has `get_or_create()` for people |
| `dev/database/models/core.py` | Entry, NarratedDate models |
| `dev/database/models/analysis.py` | Scene, SceneDate, Thread, Arc models |
| `dev/database/models/creative.py` | ReferenceSource, Reference, Poem, PoemVersion models |
| `dev/database/models/metadata.py` | Motif, MotifInstance models |
| `dev/database/models/entities.py` | Person, Event, Tag, Theme models |
| `dev/database/models/geography.py` | City, Location models |
