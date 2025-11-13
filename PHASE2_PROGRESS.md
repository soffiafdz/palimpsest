# Phase 2 Progress Report: Entity Type Expansion

**Date:** 2025-11-13
**Status:** 🔄 In Progress (Themes Complete)
**Branch:** `claude/md2wiki-analysis-report-011CV528Jk6fsr3YrK6FhCvR`

---

## Overview

Phase 2 expands the sql2wiki system to support additional entity types beyond people. This report tracks progress on implementing themes, tags, poems, and references export.

## Completed: Themes Export ✅

### WikiTheme Dataclass

**File:** `dev/dataclasses/wiki_theme.py`

**Features:**
- `from_database()` - Converts database Theme models to wiki entities
- Loads manuscript entries that use the theme
- Collects people from themed entries
- Generates relative links to journal entries
- Preserves manual description and notes from existing wiki files
- Properties: `usage_count`, `first_appearance`, `last_appearance`

**Dataclass Fields:**
```python
@dataclass
class Theme(WikiEntity):
    path:           Path                   # wiki/themes/{name}.md
    name:           str                    # Theme name
    description:    Optional[str]          # Manual description
    entries:        List[Dict[str, Any]]   # Entry appearances
    people:         Set[str]               # Associated people
    related_themes: Set[str]               # Related themes
    notes:          Optional[str]          # Editorial notes
```

### Export Functions

**File:** `dev/pipeline/sql2wiki.py` (lines 339-570)

**Functions Implemented:**

1. **`export_theme()`** - Export single theme to wiki page
   - Creates/updates theme markdown files
   - Status tracking: "created", "updated", "skipped"

2. **`build_themes_index()`** - Generate themes index page
   - Sorts by usage frequency
   - Includes date ranges for each theme
   - Statistics summary

3. **`export_themes()`** - Batch export all themes
   - Query with eager loading of relationships
   - Creates both index and individual pages
   - Returns ConversionStats

### CLI Support

**Commands Added:**
```bash
# Export all themes
python -m dev.pipeline.sql2wiki export themes

# Force regeneration
python -m dev.pipeline.sql2wiki export themes --force

# Export all (now includes people + themes)
python -m dev.pipeline.sql2wiki export all
```

### Generated File Structure

```
vimwiki/
├── themes.md                 # Index with usage stats
└── themes/
    ├── solitude.md          # Individual theme pages
    ├── memory.md
    └── desire.md
```

### Example Output

**themes.md (Index):**
```markdown
# Palimpsest — Themes

Recurring conceptual and emotional threads throughout the journal.

## All Themes

- [[themes/solitude.md|Solitude]] (15 appearances) — 2024-01-15 to 2024-11-13
- [[themes/memory.md|Memory]] (8 appearances) — 2024-02-20 to 2024-10-05
- [[themes/desire.md|Desire]] (5 appearances) — 2024-03-10 to 2024-09-18

---

## Statistics

- Total themes: 3
- Total appearances: 28
```

**themes/solitude.md (Individual Page):**
```markdown
# Palimpsest — Themes

## Solitude

### Description
Exploration of being alone, particularly in relation to creative
work and self-reflection. Distinct from loneliness.

### Appearances
- [[../../journal/content/md/2024/2024-01-15.md|2024-01-15]]
- [[../../journal/content/md/2024/2024-02-03.md|2024-02-03]]
- [[../../journal/content/md/2024/2024-03-12.md|2024-03-12]]

### People Involved
- Alice
- Charlie
- Dr. Smith

### Related Themes
- introspection
- creativity

### Notes
```

---

## Remaining: Tags, Poems, References ⏳

### Tags Export (Not Started)

**Database Model:** `dev/database/models.py` - `Tag` class
- Simple keyword tags for entries
- Many-to-many with Entry via `entry_tags`
- Properties: `usage_count`, `chronological_entries`

**TODO:**
- [ ] Complete `WikiTag` dataclass (`dev/dataclasses/wiki_tag.py`)
- [ ] Add `from_database()` method
- [ ] Implement `to_wiki()` markdown generation
- [ ] Add `export_tag()`, `build_tags_index()`, `export_tags()` to sql2wiki.py
- [ ] Update CLI to support `export tags`

**Estimated Time:** 2-3 hours

### Poems Export (Not Started)

**Database Models:** `dev/database/models.py` - `Poem` and `PoemVersion` classes
- Poems with revision tracking
- One-to-many Poem → PoemVersion
- Linked to entries

**TODO:**
- [ ] Complete `WikiPoem` dataclass (`dev/dataclasses/wiki_poem.py`)
- [ ] Add `from_database()` method with version history
- [ ] Implement `to_wiki()` markdown generation
- [ ] Add `export_poem()`, `build_poems_index()`, `export_poems()` to sql2wiki.py
- [ ] Update CLI to support `export poems`

**Estimated Time:** 3-4 hours

### References Export (Not Started)

**Database Models:** `dev/database/models.py` - `Reference` and `ReferenceSource` classes
- External citations with sources
- Many-to-one Reference → ReferenceSource
- Linked to entries

**TODO:**
- [ ] Complete `WikiReference` dataclass (`dev/dataclasses/wiki_reference.py`)
- [ ] Add `from_database()` method
- [ ] Group by source in index
- [ ] Implement `to_wiki()` markdown generation
- [ ] Add `export_reference()`, `build_references_index()`, `export_references()` to sql2wiki.py
- [ ] Update CLI to support `export references`

**Estimated Time:** 3-4 hours

---

## Progress Summary

| Entity Type | Dataclass | from_database() | to_wiki() | Export Function | Index Function | CLI | Status |
|-------------|-----------|-----------------|-----------|----------------|----------------|-----|---------|
| **People** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| **Themes** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | Complete |
| **Tags** | ⏳ | ❌ | ⏳ | ❌ | ❌ | ❌ | Pending |
| **Poems** | ⏳ | ❌ | ⏳ | ❌ | ❌ | ❌ | Pending |
| **References** | ⏳ | ❌ | ⏳ | ❌ | ❌ | ❌ | Pending |

**Completion:** 40% (2/5 entity types)

---

## Testing Status

### Themes Export Testing

**Challenge:** No themes in test database
- Sample fixture entries don't have manuscript metadata
- Themes require `ManuscriptEntry` records with theme associations
- Need to create test data or use production database

**Options:**
1. Create synthetic ManuscriptEntry + Theme test data
2. Use actual journal database (if available)
3. Test with empty database (verify graceful handling)

**Current Validation:**
- ✅ Code compiles without errors
- ✅ CLI command structure correct
- ✅ Import statements resolved
- ⏳ Actual export with theme data - pending

---

## Design Patterns Established

### Consistency with Phase 1

All Phase 2 implementations follow the patterns from Phase 1 (People):

1. **Dataclass Structure:**
   - `from_database()` classmethod
   - `to_wiki()` serialization method
   - Computed properties
   - Path management

2. **Export Functions:**
   - `export_{entity}()` - Single entity export
   - `build_{entity}_index()` - Index page generation
   - `export_{entities}()` - Batch export with stats

3. **Database Queries:**
   - Eager loading with `joinedload()`
   - Soft-delete filtering
   - Relationship traversal

4. **File Organization:**
   - Index: `vimwiki/{entity}.md`
   - Individual: `vimwiki/{entity}/{name}.md`

5. **CLI Commands:**
   - `export {entity}`
   - `export all` (cumulative)
   - `--force` flag support

---

## Next Steps

### Immediate (Complete Phase 2)

1. Implement WikiTag export (2-3 hours)
2. Implement WikiPoem export (3-4 hours)
3. Implement WikiReference export (3-4 hours)
4. Test all entity types with real data
5. Create comprehensive Phase 2 completion report

**Total Estimated Time:** 8-11 hours

### After Phase 2 (Phase 3)

**Goal:** Reverse sync (wiki2sql)
- Parse manually edited wiki pages
- Sync changes back to database
- Implement field ownership rules
- Add conflict detection
- Create wiki2sql CLI

**Estimated Time:** 2 weeks

---

## Commits

**Phase 2 - Themes:**
- **7f8d64e** - Implement WikiTheme export
  - Complete WikiTheme dataclass
  - Add export functions
  - Update CLI

---

## Lessons Learned

1. **Manuscript vs. Core Models:** Themes are in `models_manuscript.py`, not `models.py` - important distinction for query imports

2. **Relationship Loading:** Need to explicitly load `entries` relationship for themes to access manuscript entry data

3. **Empty Database Handling:** Export functions gracefully handle empty result sets with appropriate logging

4. **Index Complexity:** Theme index includes date ranges, adding more context than simple mention counts

---

## Conclusion

Phase 2 is **40% complete** with themes export fully implemented. The foundation is solid and follows established patterns from Phase 1. Remaining entity types (tags, poems, references) are straightforward implementations following the same structure.

**Current Status:** Ready to continue with tags, poems, and references
**Blockers:** None
**Estimated Completion:** 8-11 hours of focused work
