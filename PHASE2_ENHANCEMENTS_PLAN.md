# Phase 2 Enhancements — Plan

**Goal:** Enhance the wiki export with homepage, search, validation, and better nvim integration.

## Current State

### Existing Wiki Structure
```
data/wiki/
├── index.md              # ❌ MISSING (need to create)
├── entries.md            # ✅ Index of all entries
├── entries/              # ✅ Entry pages
├── people.md             # ✅ Index of all people
├── people/               # ✅ People pages
├── themes.md            # ⚠️  Empty (no data)
├── tags.md              # ✅ Index of tags
├── tags/                # ✅ Tag pages
├── poems.md             # ✅ Index of poems
├── poems/               # ✅ Poem pages
├── timeline.md          # ✅ Calendar view
└── references.md        # ⚠️  Empty (no data)
```

### Existing Nvim Integration
- ✅ `dev/lua/palimpsest/` package
- ✅ Vimwiki setup with keymaps
- ✅ Integration with which-key
- ✅ Diary/log functionality

## Proposed Enhancements

### 1. Wiki Homepage / Navigation (HIGH PRIORITY)

**Create `index.md` as wiki homepage with:**
- Welcome message and overview
- Navigation to all entity indexes
- Quick statistics summary
- Recent activity
- Links to key pages (timeline, etc.)

**Implementation:**
- Add `export_index()` function to sql2wiki.py
- Auto-generate from database statistics
- Include in "export all" command

**Template:**
```markdown
# Palimpsest — Metadata Wiki

Welcome to the Palimpsest metadata wiki for manuscript development.

## Quick Navigation

### Content
- [[entries.md|Journal Entries]] — 4 entries spanning 295 days
- [[timeline.md|Timeline]] — Calendar view by year/month

### People & Places
- [[people.md|People]] — 2 people across 2 categories
- [[locations.md|Locations]] — Geographic venues (empty)
- [[cities.md|Cities]] — Regions visited (empty)

### Narrative Elements
- [[events.md|Events]] — Narrative arcs (empty)
- [[themes.md|Themes]] — Conceptual threads (empty)
- [[tags.md|Tags]] — 2 tags

### Creative Work
- [[poems.md|Poems]] — 1 poem
- [[references.md|References]] — Source material (empty)

## Statistics

- **Total Entries:** 4
- **Date Range:** 2024-01-15 to 2024-11-05
- **Total Words:** 1,100
- **People Mentioned:** 2
- **Active Tags:** 2

## Recent Activity

### Latest Entries
- 2024-11-05 — 600 words
- 2024-11-01 — 500 words

### Most Mentioned People
- Alice Johnson (2 mentions)
- Bob (1 mention)
```

**Estimated:** ~150 lines

### 2. Statistics Dashboard (MEDIUM PRIORITY)

**Create `stats.md` with comprehensive analytics:**

**Sections:**
- Writing statistics (words, frequency, streak)
- People network (mentions, relationships)
- Geographic coverage (locations, cities)
- Thematic analysis (themes, tags)
- Timeline analysis (entry frequency over time)
- Manuscript readiness (entities with manuscript metadata)

**Visualizations (ASCII):**
- Bar charts for entry frequency
- Timeline heatmap
- Category breakdowns

**Implementation:**
- Add `export_stats_dashboard()` to sql2wiki.py
- Query database for aggregate statistics
- Generate markdown with ASCII visualizations

**Example Output:**
```markdown
# Palimpsest — Statistics Dashboard

## Writing Activity

**Entry Frequency (Last 12 Months)**
```
Jan ██ (2)
Feb ░░ (0)
Mar ░░ (0)
Apr █ (1)
...
Nov ███ (2)
```

**Word Count by Month**
Total: 1,100 words | Average: 275 words/entry

## People Network

**Most Mentioned**
1. Alice Johnson — 2 mentions (Friend)
2. Bob — 1 mention (Colleague)

**Relationship Distribution**
Friend: ████████ 50%
Colleague: ████ 50%
```

**Estimated:** ~400 lines

### 3. Search Functionality (LOW PRIORITY - Rely on Vimwiki)

**Approach:** Don't reinvent the wheel. Vimwiki + telescope/fzf already provides:
- `:VimwikiSearch` - Search all wiki files
- Telescope integration for fuzzy finding
- Tag search via `:VimwikiSearchTags`

**Enhancement:** Add lua commands for common searches:
```lua
-- dev/lua/palimpsest/search.lua
M.search_people = function()
  -- Search in people directory
end

M.search_by_date = function()
  -- Search entries by date range
end

M.search_by_tag = function()
  -- Search by tag
end
```

**Keymaps to add:**
- `<leader>psp` - Search people
- `<leader>pst` - Search by tag
- `<leader>psd` - Search by date

**Estimated:** ~200 lines lua

### 4. Cross-Reference Validation (MEDIUM PRIORITY)

**Create validation tool to check:**
- ✅ All wiki links point to existing files
- ✅ No broken references
- ✅ Orphaned pages (pages with no incoming links)
- ✅ Missing entity pages (referenced but not created)

**Implementation:**
- Create `dev/pipeline/validate_wiki.py`
- Parse all wiki files
- Extract all `[[links]]`
- Check if target files exist
- Report broken links

**CLI:**
```bash
python -m dev.pipeline.validate_wiki check
# Reports:
# ✅ 45 links validated
# ❌ 3 broken links:
#   - people/john.md → entries/2024-01-20.md (missing)
#   - events/trip.md → people/unknown.md (missing)

python -m dev.pipeline.validate_wiki fix --dry-run
# Shows what would be fixed

python -m dev.pipeline.validate_wiki orphans
# Lists pages with no incoming links
```

**Estimated:** ~300 lines

### 5. Nvim Integration Enhancements (MEDIUM PRIORITY)

**Add new lua commands:**

```lua
-- dev/lua/palimpsest/commands.lua
:PalimpsestExport [entity]    -- Export from database
:PalimpsestImport [entity]    -- Import to database (Phase 3)
:PalimpsestValidate          -- Run cross-reference validation
:PalimpsestStats             -- Open stats dashboard
:PalimpsestIndex             -- Go to wiki homepage
:PalimpsestSearch [type]     -- Search by type
```

**Keymaps to add:**
```lua
<leader>pe  -- Export from database
<leader>pi  -- Import to database
<leader>pv  -- Validate wiki
<leader>ps  -- Statistics
<leader>ph  -- Homepage
<leader>p/  -- Search menu
```

**Telescope picker for entities:**
```lua
:Telescope palimpsest people
:Telescope palimpsest entries
:Telescope palimpsest tags
```

**Estimated:** ~400 lines lua

## Implementation Priority

### Phase 2.1: Core Navigation (IMMEDIATE)
1. ✅ Wiki homepage (index.md)
2. ✅ Basic statistics in homepage
3. ✅ Update sql2wiki CLI

**Estimated:** ~200 lines, 30 minutes

### Phase 2.2: Validation & Stats (NEXT)
4. ✅ Cross-reference validation tool
5. ✅ Statistics dashboard (stats.md)

**Estimated:** ~700 lines, 2 hours

### Phase 2.3: Nvim Integration (LATER)
6. ✅ Enhanced lua commands
7. ✅ Telescope integration
8. ✅ Search enhancements

**Estimated:** ~600 lines lua, 2 hours

## Total Estimated Effort

| Component | Lines | Time |
|-----------|-------|------|
| Wiki homepage | ~200 | 30 min |
| Stats dashboard | ~400 | 1 hour |
| Search (lua) | ~200 | 30 min |
| Validation tool | ~300 | 1 hour |
| Nvim integration | ~400 | 1 hour |
| **Total** | **~1,500** | **~4 hours** |

## Benefits

### For Writing
- ✅ Quick navigation to any entity
- ✅ Statistics motivate writing
- ✅ Validation prevents broken links

### For Manuscript Development
- ✅ Overview of all metadata at a glance
- ✅ Track narrative arcs and character development
- ✅ Analyze thematic patterns

### For Nvim Users
- ✅ Seamless database integration
- ✅ Fast entity search and navigation
- ✅ Commands accessible via leader keys

## Next Step

**Recommendation:** Start with Phase 2.1 (Wiki Homepage)

This provides immediate value:
- Central navigation hub
- Quick statistics
- Professional appearance
- Foundation for other enhancements

**Implementation:**
1. Create `export_index()` function
2. Generate index.md with statistics
3. Test with current data
4. Integrate into "export all"

Would you like to proceed with this plan?
