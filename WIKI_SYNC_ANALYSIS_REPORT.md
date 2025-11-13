# Analysis Report: MD2Wiki and Database-to-Vimwiki Synchronization

**Date:** 2025-11-13
**Objective:** Analyze the current state and design the "second two-way arm" for bidirectional synchronization between the SQL metadata database and Vimwiki entity files.

---

## Executive Summary

The Palimpsest project currently has a **fully functional bidirectional sync** between Markdown journal entries and the SQL database (`yaml2sql.py` ↔ `sql2yaml.py`). This report analyzes the requirements for creating a **parallel bidirectional sync system** for Vimwiki entity files (people, themes, tags, references, poems, vignettes) and the database.

**Current State:**
- ✅ Journal entries: Markdown (YAML) ↔ Database (complete)
- ⚠️ Vimwiki entities: Partial scaffolding exists but incomplete
- ⚠️ md2wiki.py: Partially implemented, needs completion

**Goal:**
Create the "second two-way arm" that enables:
- **sql2wiki**: Export database metadata → Vimwiki entity pages
- **wiki2sql**: Parse Vimwiki entity pages → Update database

---

## 1. Current Architecture Analysis

### 1.1 Existing Data Flow

```
┌─────────────────────┐
│  Markdown Entries   │
│  (journal/md/)      │
│  YAML frontmatter   │
└──────────┬──────────┘
           │
           │ yaml2sql.py ✓
           │ (fully functional)
           ↓
┌─────────────────────┐
│   SQL Database      │
│   (metadata.db)     │
│   - entries         │
│   - people          │
│   - locations       │
│   - events          │
│   - tags            │
│   - poems           │
│   - references      │
└──────────┬──────────┘
           │
           │ sql2yaml.py ✓
           │ (fully functional)
           ↓
┌─────────────────────┐
│  Markdown Entries   │
│  (regenerated)      │
└─────────────────────┘
```

### 1.2 Target Architecture

```
┌─────────────────────┐          ┌─────────────────────┐
│  Markdown Entries   │          │   Vimwiki Entities  │
│  (journal/md/)      │          │   (vimwiki/)        │
└──────────┬──────────┘          └──────────┬──────────┘
           │                                 │
           │ yaml2sql ✓                      │ wiki2sql ✗
           │                                 │ (TO BE BUILT)
           ↓                                 ↓
┌──────────────────────────────────────────────────────┐
│               SQL Database (metadata.db)              │
│  - entries  - people   - locations  - events         │
│  - tags     - poems    - references - dates          │
└──────────┬───────────────────────────────┬───────────┘
           │                               │
           │ sql2yaml ✓                    │ sql2wiki ✗
           │                               │ (TO BE BUILT)
           ↓                               ↓
┌─────────────────────┐          ┌─────────────────────┐
│  Markdown Entries   │          │   Vimwiki Entities  │
│  (regenerated)      │          │   (regenerated)     │
└─────────────────────┘          └─────────────────────┘
```

---

## 2. Component Inventory

### 2.1 Database Layer (Complete ✓)

**File:** `dev/database/models.py`

**Complete ORM Models:**
- `Entry` - Journal entries with relationships
- `Person` - People with soft-delete, aliases, appearances
- `Location` - Venues with city hierarchy
- `MentionedDate` - Referenced dates with context
- `Event` - Narrative events spanning entries
- `Poem` / `PoemVersion` - Poetry with revision tracking
- `Reference` / `ReferenceSource` - External citations
- `Tag` - Keyword tags
- `Alias` - Alternative names for people
- `City` - Geographic cities

**Association Tables:**
- `entry_people`, `entry_locations`, `entry_dates`
- `entry_events`, `entry_tags`, `entry_related`
- `people_dates`, `location_dates`
- `event_people`, `entry_aliases`

**Computed Properties:**
- Entry: `age_in_days`, `date_formatted`, `reading_time_display`
- Person: `display_name`, `all_names`, `first_appearance_date`, `mention_timeline`
- Location: `visit_count`, `visit_timeline`, `visit_frequency`
- Tag: `usage_count`, `chronological_entries`

### 2.2 Wiki Dataclasses (Partial ⚠️)

**Location:** `dev/dataclasses/wiki_*.py`

**Abstract Base:** `WikiEntity`
- Requires: `from_file()`, `to_wiki()`, `write_to_file()`

**Implemented Classes:**
- `WikiPerson` (dev/dataclasses/wiki_person.py)
  - ✓ from_file() - Complete with parsing helpers
  - ✓ to_wiki() - Complete with formatting
  - ✓ Properties: mentions, first_appearance, last_appearance
  - ✓ Helper methods: _parse_name(), _parse_category(), _parse_alias(), etc.

- `WikiEntry` (dev/dataclasses/wiki_entry.py)
  - ⚠️ Basic dataclass structure only
  - ✗ from_file() - Not implemented
  - ✗ to_wiki() - Not implemented

- `WikiPoem` (dev/dataclasses/wiki_poem.py)
  - ⚠️ Dataclass structure defined
  - ⚠️ to_wiki() - Partially implemented
  - ✗ from_file() - Not implemented

- `WikiVignette` (dev/dataclasses/wiki_vignette.py)
  - ⚠️ Basic structure only (docstrings)

- `WikiTheme` (dev/dataclasses/wiki_theme.py)
  - ⚠️ Basic structure only (docstrings)

- `WikiTag` (dev/dataclasses/wiki_tag.py)
  - ⚠️ Basic structure only (docstrings)

- `WikiReference` (dev/dataclasses/wiki_reference.py)
  - ⚠️ Dataclass structure defined
  - ⚠️ to_wiki() - Partially implemented
  - ✗ from_file() - Not implemented

### 2.3 MD2Wiki Pipeline (Incomplete ⚠️)

**File:** `dev/pipeline/md2wiki.py`

**Current State:**
- Contains a `Person` class with extensive methods (appears to be legacy/duplicate)
- Has rendering functions for inventory
- TODOs throughout indicating incomplete work
- Main sections:
  - ✓ Inventory rendering (mostly complete)
  - ⚠️ People rendering (partial)
  - ✗ Themes rendering (not implemented)
  - ✗ Tags rendering (not implemented)
  - ✗ Notes rendering (not implemented)

**Key Functions:**
- `parse_current_inventory()` - Reads existing wiki files
- `render_inventory()` - Generates fresh inventory pages
- `build_dashboards()` - Orchestrates rendering (incomplete)
- `_write_if_changed()` - Writes only if content changed (✓)

**Issues Identified:**
1. Duplicate `Person` class definition (conflicts with `wiki_person.py`)
2. Entry class not imported from dataclasses
3. Missing implementations for themes, tags, notes
4. No database integration
5. Hard-coded paths need updating

### 2.4 Lua Integration (Basic Setup ✓)

**Files:** `dev/lua/palimpsest/`

**Current Capabilities:**
- `vimwiki.lua` - Vimwiki instance setup
- `templates.lua` - Template insertion system
- `config.lua` - Path and configuration management
- `keymaps.lua` - Keybindings
- `autocmds.lua` - Auto-commands

**No Implementation Yet:**
- Parsing vimwiki entity files
- Calling Python pipelines from Lua
- Real-time sync triggers
- Entity creation/update commands

---

## 3. Inferred Design Intentions

### 3.1 Vimwiki File Structure (from md2wiki.py comments)

```
vimwiki/
├── inventory.md           # Main entry index (2024-2025 inline)
├── inventory/
│   └── YYYY.md           # Archive years
├── people.md             # People index by category
├── people/
│   └── person.md         # Individual person pages
├── themes.md             # Themes index
├── themes/
│   └── theme.md          # Individual theme pages
├── tags.md               # Tags index
├── notes.md              # Notes index
├── notes/
│   └── YYYY.md           # Notes by year
├── references.md         # References index
├── references/
│   └── source.md         # References grouped by source
└── poems.md              # Poems index
```

### 3.2 Person Page Structure (from wiki_person.py)

```markdown
# Palimpsest — People

## [Name]

### Category
[Main|Secondary|Archive|Unsorted]

### Alias
- [alias1]
- [alias2]

### Presence
- Appearance: YYYY-MM-DD
  OR
- Range: YYYY-MM-DD -> YYYY-MM-DD
- Mentions: N entries
- First: [[../../journal/md/YYYY/YYYY-MM-DD.md|YYYY-MM-DD]] — note
- Last: [[../../journal/md/YYYY/YYYY-MM-DD.md|YYYY-MM-DD]] — note

### Themes
- theme1
- theme2

### Vignettes
- [[vignette.md|Title]] — note

### Notes
[Free-form notes]
```

### 3.3 Intended Workflow

**For Adding New People (Manual):**
1. User edits journal entry, adds person to YAML frontmatter
2. `yaml2sql` processes entry, creates/updates Person in database
3. `sql2wiki` exports person data → `vimwiki/people/person.md`
4. User can manually edit person.md (add notes, vignettes, etc.)
5. `wiki2sql` reads person.md changes → updates database

**For Reviewing People (Automated):**
1. Database accumulates person mentions from entries
2. `sql2wiki people` regenerates all person pages with updated stats
3. User browses vimwiki to see relationships, patterns
4. User adds vignettes or notes directly in vimwiki
5. `wiki2sql people` syncs manual edits back to database

---

## 4. Implementation Requirements

### 4.1 SQL2Wiki Pipeline (Database → Vimwiki)

**Purpose:** Export database entities to human-readable vimwiki pages

**Modules to Create:**

#### A. `sql2wiki.py` - Main Pipeline
```python
#!/usr/bin/env python3
"""
sql2wiki.py
-----------
Export database entities to Vimwiki pages.

Similar to sql2yaml.py but for wiki entities instead of entries.
Generates index pages and individual entity pages.
"""

# Commands:
# - export people [--force]
# - export themes [--force]
# - export tags [--force]
# - export poems [--force]
# - export references [--force]
# - export all [--force]
```

**Core Functions:**

1. **`export_people(db, wiki_dir, force=False)`**
   - Query all `Person` records from database
   - For each person:
     - Load relationships (entries, dates, themes)
     - Create WikiPerson dataclass
     - Generate markdown via `WikiPerson.to_wiki()`
     - Write to `vimwiki/people/{name}.md`
   - Generate index: `vimwiki/people.md`
     - Group by category (Main, Secondary, Archive, Unsorted)
     - Sort by mention frequency
     - Create links to individual pages

2. **`export_themes(db, wiki_dir, force=False)`**
   - Query all themes from entries/manuscript
   - Aggregate entries per theme
   - Create WikiTheme objects
   - Generate `vimwiki/themes.md` index
   - Create `vimwiki/themes/{theme}.md` pages

3. **`export_tags(db, wiki_dir, force=False)`**
   - Query `Tag` model
   - For each tag:
     - Get related entries
     - Generate tag page with chronology
   - Create index with usage statistics

4. **`export_poems(db, wiki_dir, force=False)`**
   - Query `Poem` and `PoemVersion` models
   - Group versions by poem title
   - Show revision history
   - Link to entries where poems appear

5. **`export_references(db, wiki_dir, force=False)`**
   - Query `Reference` and `ReferenceSource` models
   - Group by source
   - Show all citations with context
   - Link to entries

6. **`export_inventory(db, wiki_dir, force=False)`**
   - Use existing md2wiki.py logic
   - Query all entries with metadata
   - Generate inventory pages with inline/archive split

**Design Patterns (from sql2yaml.py):**
- Use `_write_if_changed()` to avoid unnecessary writes
- Support `--force` flag to regenerate all
- Use database session management
- Log operations for debugging
- Return statistics (created/updated/skipped)

#### B. Complete Wiki Dataclasses

**Files to Complete:**

1. **`wiki_theme.py`**
```python
@dataclass
class Theme(WikiEntity):
    path: Path
    name: str
    description: Optional[str]
    entries: List[Dict[str, Any]]  # {date, link, note}
    people: Set[str]
    related_themes: Set[str]
    notes: Optional[str]

    @classmethod
    def from_database(cls, theme_name: str, db_entries, path: Path) -> Theme:
        """Construct from database query results."""
        pass

    def to_wiki(self) -> List[str]:
        """Generate vimwiki markdown."""
        pass
```

2. **`wiki_tag.py`**
```python
@dataclass
class Tag(WikiEntity):
    path: Path
    tag: str
    description: Optional[str]
    entries: List[Dict[str, Any]]
    first_used: date
    last_used: date
    usage_count: int

    @classmethod
    def from_database(cls, db_tag: models.Tag, path: Path) -> Tag:
        pass

    def to_wiki(self) -> List[str]:
        pass
```

3. **Complete `wiki_poem.py`**
   - Add `from_database()` method
   - Enhance `to_wiki()` with version history

4. **Complete `wiki_reference.py`**
   - Add `from_database()` method
   - Format with proper citations

### 4.2 Wiki2SQL Pipeline (Vimwiki → Database)

**Purpose:** Parse manually edited vimwiki pages and update database

**Module to Create:**

#### `wiki2sql.py` - Parsing Pipeline
```python
#!/usr/bin/env python3
"""
wiki2sql.py
-----------
Parse Vimwiki entity pages and update database.

Reads human edits from vimwiki (notes, vignettes, categories)
and syncs them back to the database.

Key Difference from yaml2sql:
- yaml2sql is the PRIMARY source (entries define people)
- wiki2sql handles SECONDARY edits (manual curation)
- Only updates fields that are wiki-managed
"""

# Commands:
# - sync people [--dry-run]
# - sync themes [--dry-run]
# - sync tags [--dry-run]
# - sync all [--dry-run]
```

**Core Functions:**

1. **`sync_people(wiki_dir, db, dry_run=False)`**
   - Parse `vimwiki/people/*.md` files
   - For each person file:
     - Use `WikiPerson.from_file()`
     - Compare with database `Person` record
     - Update ONLY curated fields:
       - category
       - notes
       - vignettes (store in separate table?)
   - DO NOT update computed fields:
     - mentions, appearances, themes (these come from entries)

2. **`sync_themes(wiki_dir, db, dry_run=False)`**
   - Parse theme pages
   - Update theme descriptions and notes
   - Preserve entry relationships (from yaml2sql)

3. **Field Ownership Strategy:**

**Entry-Owned (yaml2sql only):**
- Person mentions → determined by entry YAML
- Person appearances → computed from entry dates
- Person themes → derived from entry themes
- Tag usage → from entry YAML

**Wiki-Owned (wiki2sql editable):**
- Person category
- Person notes
- Person vignettes
- Theme descriptions
- Tag descriptions

**Two-Way Sync:**
- Aliases could be managed from either side

### 4.3 MD2Wiki Refactoring

**File:** `dev/pipeline/md2wiki.py`

**Required Changes:**

1. **Remove Duplicate Code:**
   - Delete the inline `Person` class
   - Import from `dev.dataclasses.wiki_person`

2. **Add Database Integration:**
   - Import `PalimpsestDB`
   - Query entries from database instead of parsing files
   - Use ORM relationships

3. **Complete Build Functions:**
```python
def build_dashboards(db: PalimpsestDB, wiki_dir: Path):
    """
    Generate all vimwiki dashboards from database.

    Calls:
    - build_inventory(db, wiki_dir)
    - build_people(db, wiki_dir)
    - build_themes(db, wiki_dir)
    - build_tags(db, wiki_dir)
    - build_notes(db, wiki_dir)
    """
    pass
```

4. **Refactor as sql2wiki:**
   - Rename md2wiki.py → sql2wiki.py
   - Remove Markdown parsing (use database)
   - Follow sql2yaml.py patterns

### 4.4 Lua Integration

**Purpose:** Trigger sync from Neovim

**Files to Create/Modify:**

1. **`dev/lua/palimpsest/sync.lua`**
```lua
local M = {}
local Job = require('plenary.job')

function M.sync_people()
  -- Call: python -m dev.pipeline.sql2wiki export people
  -- Show results in notification
end

function M.sync_all_wiki()
  -- Call: python -m dev.pipeline.sql2wiki export all
end

function M.refresh_current_person()
  -- Parse current file path
  -- If in people/*.md, sync just that person
end

function M.parse_wiki_edits()
  -- Call: python -m dev.pipeline.wiki2sql sync all
end

return M
```

2. **`dev/lua/palimpsest/keymaps.lua` additions**
```lua
-- In vimwiki files:
vim.keymap.set('n', '<leader>ws', '<cmd>lua require("palimpsest.sync").sync_all_wiki()<CR>')
vim.keymap.set('n', '<leader>wp', '<cmd>lua require("palimpsest.sync").parse_wiki_edits()<CR>')
```

3. **Auto-sync on save:**
```lua
-- In autocmds.lua
vim.api.nvim_create_autocmd('BufWritePost', {
  pattern = {'*/vimwiki/people/*.md', '*/vimwiki/themes/*.md'},
  callback = function()
    require('palimpsest.sync').parse_wiki_edits()
  end
})
```

---

## 5. Implementation Plan

### Phase 1: Foundation (Week 1)

**Goal:** Get basic sql2wiki working for one entity type

**Tasks:**
1. ✅ Complete `WikiPerson.from_database()` method
2. ✅ Test `WikiPerson.to_wiki()` with database data
3. ✅ Create `sql2wiki.py` module with CLI structure
4. ✅ Implement `export_people()` function
5. ✅ Test: Export all people from database to vimwiki

**Success Criteria:**
- `python -m dev.pipeline.sql2wiki export people` works
- Generates `vimwiki/people.md` index
- Generates `vimwiki/people/*.md` individual pages
- Pages match expected format

### Phase 2: Expand Entity Types (Week 2)

**Goal:** Support all major entity types

**Tasks:**
1. Complete `WikiTheme` dataclass
2. Complete `WikiTag` dataclass
3. Complete `WikiPoem` from_database()
4. Complete `WikiReference` from_database()
5. Implement export functions for each type
6. Test comprehensive export

**Success Criteria:**
- `python -m dev.pipeline.sql2wiki export all` works
- All entity types have index pages
- All entity types have individual pages

### Phase 3: Reverse Sync (Week 3)

**Goal:** Parse wiki edits back to database

**Tasks:**
1. Design field ownership strategy (document in WIKI_SYNC_STRATEGY.md)
2. Implement `wiki2sql.py` module
3. Implement `sync_people()` with conflict detection
4. Add dry-run mode for safety
5. Test round-trip: database → wiki → edit → database

**Success Criteria:**
- Manual edits to `vimwiki/people/*.md` sync to database
- Computed fields remain untouched
- Conflict warnings if structure changed

### Phase 4: Lua Integration (Week 4)

**Goal:** Seamless Neovim workflow

**Tasks:**
1. Create `sync.lua` module
2. Add keymaps for common operations
3. Implement auto-sync on save (optional, with config flag)
4. Add status notifications
5. Test in daily workflow

**Success Criteria:**
- `<leader>ws` regenerates all wiki pages from database
- `<leader>wp` syncs manual edits back to database
- Notifications show success/failure
- No performance issues

### Phase 5: Polish & Documentation (Week 5)

**Goal:** Production-ready system

**Tasks:**
1. Add comprehensive error handling
2. Write user documentation (VIMWIKI_USAGE.md)
3. Add tests for all pipelines
4. Optimize database queries (eager loading)
5. Add diff viewer for conflicts
6. Create backup/restore functionality

**Success Criteria:**
- All pipelines have test coverage
- Documentation is complete
- Error messages are helpful
- Performance is acceptable (<2s for full export)

---

## 6. Data Flow Examples

### Example 1: New Person Workflow

**Initial State:** Database has no person "Alice"

1. **User edits entry:**
```yaml
---
date: 2024-11-13
people:
  - Alice
---
```

2. **Run yaml2sql:**
```bash
python -m dev.pipeline.yaml2sql update journal/md/2024/2024-11-13.md
```
→ Creates `Person(name='Alice')` in database

3. **Export to vimwiki:**
```bash
python -m dev.pipeline.sql2wiki export people
```
→ Creates `vimwiki/people/alice.md`:
```markdown
# Palimpsest — People

## Alice

### Category
Unsorted

### Presence
- Appearance: 2024-11-13
- Mentions: 1 entry
- Entry: [[../../journal/md/2024/2024-11-13.md|2024-11-13]] —

### Themes
-

### Notes

```

4. **User manually edits in Neovim:**
```markdown
### Category
Friend

### Notes
Met at conference. Discussed project ideas.
```

5. **Save triggers sync:**
→ Calls `wiki2sql sync people`
→ Updates database:
  - `Person.relation_type = 'friend'`
  - `Person.notes = "Met at conference..."`

### Example 2: Theme Evolution Workflow

**Scenario:** User notices recurring theme across entries

1. **Multiple entries mention "solitude":**
```yaml
# 2024-01-15.md
themes: [solitude, introspection]

# 2024-02-20.md
themes: [solitude, nature]

# 2024-03-10.md
themes: [solitude, creativity]
```

2. **After yaml2sql processing:**
   - Database has 3 entries with theme "solitude"

3. **Export themes:**
```bash
python -m dev.pipeline.sql2wiki export themes
```
→ Creates `vimwiki/themes/solitude.md`:
```markdown
# Palimpsest — Themes

## Solitude

### Description


### Appearances
- [[../../journal/md/2024/2024-01-15.md|2024-01-15]]
- [[../../journal/md/2024/2024-02-20.md|2024-02-20]]
- [[../../journal/md/2024/2024-03-10.md|2024-03-10]]

### Related Themes
- introspection
- nature
- creativity

### People Involved


### Notes

```

4. **User adds description:**
```markdown
### Description
Exploration of being alone, particularly in relation to creative
work and self-reflection. Distinct from loneliness.
```

5. **Sync back:**
→ Creates/updates `Theme` table or stores in JSON field

---

## 7. Technical Considerations

### 7.1 Performance

**Database Queries:**
- Use eager loading for relationships: `.options(joinedload(Person.entries))`
- Batch queries where possible
- Profile with `EXPLAIN` for slow queries

**File I/O:**
- Use `_write_if_changed()` to minimize writes
- Consider caching parsed files
- Optimize Markdown parsing

### 7.2 Conflict Resolution

**Scenarios:**

1. **Person renamed in database but wiki file exists:**
   - Strategy: Create new file, leave old file (manual merge)

2. **Person deleted in database but wiki file edited:**
   - Strategy: Warn user, skip sync (or mark as orphaned)

3. **Mention count changed but notes edited:**
   - Strategy: Update computed fields, preserve notes

**Solution:** Implement change detection and warnings

### 7.3 Data Validation

**Before writing to database:**
- Validate dates are parseable
- Check required fields exist
- Verify links resolve
- Validate enum values (relation_type, etc.)

**Before writing to wiki:**
- Ensure paths exist
- Check filename conventions
- Validate Markdown structure

### 7.4 Extensibility

**Future Entity Types:**
- Locations (venues with visit history)
- Events (narrative arcs)
- Vignettes (curated excerpts)

**Plugin System:**
- Allow custom entity types
- Support custom renderers
- Enable schema extensions

---

## 8. Key Design Decisions

### 8.1 Field Ownership

**Principle:** Clear separation of concerns

| Field | Owner | Rationale |
|-------|-------|-----------|
| Person.name | yaml2sql | Comes from entry mentions |
| Person.mentions | computed | Derived from entry_people table |
| Person.first_appearance | computed | Min date from related entries |
| Person.category | wiki2sql | Manual curation |
| Person.notes | wiki2sql | Manual curation |
| Theme.name | yaml2sql | From entry frontmatter |
| Theme.description | wiki2sql | Manual curation |
| Tag.tag | yaml2sql | From entry frontmatter |
| Tag.description | wiki2sql | Manual curation |

### 8.2 Sync Direction Priority

**Conflict Resolution:**
- If both sides changed: **wiki wins** for curated fields
- If database changed: **database wins** for computed fields
- If structure invalid: **reject wiki changes**, log error

### 8.3 Incremental vs Full Sync

**sql2wiki:**
- Default: Full regeneration (fast enough for <10K entities)
- Option: `--incremental` based on updated_at timestamps

**wiki2sql:**
- Default: Incremental (only parse modified files)
- Option: `--full` to rescan all files

---

## 9. Testing Strategy

### 9.1 Unit Tests

**Test Coverage:**
- WikiPerson.from_database() with various Person records
- WikiPerson.to_wiki() output format
- WikiTheme.from_database() with entry aggregation
- Conflict detection logic
- Field ownership enforcement

### 9.2 Integration Tests

**Scenarios:**
1. Full cycle: entry → database → wiki → edit → database
2. Multiple people in one entry
3. Person with many appearances
4. Theme across many entries
5. Deleted person handling

### 9.3 End-to-End Tests

**Workflow Tests:**
1. New project setup (empty database)
2. Import 100 entries
3. Export all entities
4. Edit 10 people
5. Sync back
6. Verify database state

---

## 10. Documentation Needs

### 10.1 User Documentation

**Files to Create:**
1. `docs/VIMWIKI_USAGE.md` - How to use vimwiki features
2. `docs/WIKI_SYNC_GUIDE.md` - Sync workflows and commands
3. `docs/ENTITY_REFERENCE.md` - Entity page structure reference

### 10.2 Developer Documentation

**Files to Create:**
1. `docs/WIKI_ARCHITECTURE.md` - System design overview
2. `docs/PIPELINE_API.md` - Pipeline module API reference
3. `docs/EXTENDING_ENTITIES.md` - How to add new entity types

---

## 11. Conclusion

The implementation of the "second two-way arm" for Palimpsest's metadata system requires:

1. **Completing wiki dataclasses** - Add from_database() methods and enhance to_wiki()
2. **Creating sql2wiki pipeline** - Export database entities to vimwiki pages
3. **Creating wiki2sql pipeline** - Parse wiki edits back to database
4. **Integrating with Lua** - Seamless Neovim workflow
5. **Defining ownership** - Clear rules for field management

The architecture mirrors the successful yaml2sql/sql2yaml pattern, ensuring consistency and maintainability. The phased implementation plan provides a clear path from basic functionality to production-ready system.

**Estimated Effort:** 4-5 weeks for complete implementation with testing and documentation

**Key Success Metric:** Daily workflow enables seamless movement between:
- Writing entries (Markdown with YAML)
- Reviewing metadata (Vimwiki dashboards)
- Curating knowledge (Wiki page edits)
- All changes reflected in database (single source of truth)
