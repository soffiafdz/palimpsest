# Export JSON Implementation Status

**Date:** 2024-02-01
**Phase:** 14b-3 (Export Canonical JSON Files)

## Critical Fixes Completed

### 1. ✅ Slugification System
**File:** `dev/utils/slugify.py`

Implemented complete slugification system per design spec:
- `slugify()` - Core slug generation (lowercase, strip accents, remove special chars)
- `generate_person_filename()` - People: `{first}_{last|disambig}.json`
  - **Validates** lastname OR disambiguator requirement
  - Fallback to `person-{id}.json` for >250 char names
- `generate_location_path()` - Locations: `{city}/{location}.json`
- `generate_scene_path()` - Scenes: `{YYYY-MM-DD}/{scene-name}.json`
- `generate_entry_path()` - Entries: `{YYYY}/{YYYY-MM-DD}.json`

**Impact:** Files now use human-readable slugs instead of IDs

### 2. ✅ Proper File Path Generation
**File:** `dev/pipeline/export_json.py` - `_write_exports()` method

Completely rewrote file writing to follow design spec:
- `_write_entries()` - entries/YYYY/YYYY-MM-DD.json
- `_write_people()` - people/first_last.json with validation
- `_write_locations()` - locations/city/location.json with city lookup
- `_write_scenes()` - scenes/YYYY-MM-DD/scene-name.json with entry lookup
- `_write_simple_entities()` - Generic slug-based writer for arcs/threads/etc.

**Impact:** Correct directory structure and filenames per design

### 3. ✅ Validation Added
**File:** `dev/utils/slugify.py` - `generate_person_filename()`

- Raises `ValueError` if person has neither lastname nor disambiguator
- Logged as warning in `_write_people()` instead of crashing
- Skips invalid people with clear error message

**Impact:** Catches design violations early with helpful errors

## Remaining TODOs

### High Priority (Breaks Functionality)

**4. ❌ Load Existing Exports**
**File:** `dev/pipeline/export_json.py` - `_load_existing_exports()`

Currently returns empty dict. Needs to:
- Scan data/exports/journal/ for existing JSON files
- Parse and load into same structure as `_export_all_entities()`
- Handle missing/corrupted files gracefully

**Impact:** Can't detect changes without this (README will be useless)

**5. ❌ Generate Change Descriptions**
**File:** `dev/pipeline/export_json.py` - `_generate_changes()`

Currently just appends timestamp. Needs to:
- Compare old vs new exports
- Detect added/modified/deleted entities
- Generate human-readable descriptions per design:
  - `+ person clara_dubois (42)`
  - `~ entry 2024-12-03: +person_id 42, ~rating 4.0 → 4.5`
  - `- location old-place (99)`

**Impact:** README changelog is currently useless

**6. ❌ Proper README Generation**
**File:** `dev/pipeline/export_json.py` - `_write_readme()`

Currently minimal. Needs to:
- Show entity counts
- List all changes with +/~/- prefixes
- Map IDs to slugs for readability
- Group by entity type

**Impact:** Git diffs lack human context

**7. ❌ Fix Git Commit**
**File:** `dev/pipeline/export_json.py` - `_git_commit()`

Currently fails on second run (no changes). Needs to:
- Check `git status` before committing
- Skip commit if no changes
- Report "no changes" to user clearly
- Better error messages

**Impact:** Silent failures, confusing UX

### Medium Priority (Code Quality)

**8. ❌ Progress Reporting**
Add progress bar or status updates:
- "Exporting entries... (384 found)"
- "Writing people... (156 files)"
- "Generating README..."

**Impact:** User doesn't know if it's working or frozen

**9. ❌ Better Error Handling**
- Wrap file writes in try/catch
- Rollback on failure (delete partial files?)
- Report which entity failed
- Continue on non-fatal errors

**Impact:** Better debugging, more robust

**10. ❌ DRY Up Export Methods**
All `_export_X()` methods follow same pattern. Could extract to generic:
```python
def _export_entity_type(self, model, additional_fields=None):
    entities = session.query(model).all()
    ...
```

**Impact:** Less code duplication

### Low Priority (Nice to Have)

**11. ❌ Batch Processing**
For large datasets (1000+ entries), load and process in batches

**12. ❌ Dry Run Mode**
Preview what would be exported without writing files

**13. ❌ Full Test Coverage**
Unit tests for all export methods and slugification

**14. ❌ Comprehensive Docstrings**
Add detailed docstrings to all helper methods

## Design Compliance

| Aspect | Status | Notes |
|--------|--------|-------|
| File naming (people) | ✅ FIXED | Uses first_last.json with slugs |
| File naming (locations) | ✅ FIXED | Uses city/location.json |
| File naming (scenes) | ✅ FIXED | Uses entry-date/scene.json |
| File naming (entries) | ✅ FIXED | Uses YYYY/YYYY-MM-DD.json |
| Slugification | ✅ FIXED | Lowercase, no accents, special chars handled |
| Validation | ✅ FIXED | Person lastname/disambiguator checked |
| ID-based relationships | ✅ WORKING | Using IDs not slugs in JSON |
| Unidirectional storage | ✅ WORKING | Entry owns relationships |
| README changelog | ❌ BROKEN | Only shows timestamp |
| Git commit | ❌ BROKEN | Fails on no-changes |
| Change detection | ❌ NOT IMPLEMENTED | Can't diff old vs new |

## Testing Needed

Before marking as complete:

1. **Manual test:** Run `plm export-json` and verify:
   - [ ] Directory structure matches design
   - [ ] Filenames use slugs not IDs
   - [ ] People files validate lastname/disambiguator
   - [ ] All entities exported

2. **Git workflow test:**
   - [ ] First export creates files and commits
   - [ ] Second export (no changes) doesn't crash
   - [ ] Modify DB, export again shows changes in README
   - [ ] Git history is clean

3. **Edge cases:**
   - [ ] Person with very long name → fallback to person-{id}.json
   - [ ] Person missing lastname AND disambiguator → skip with warning
   - [ ] Scene references unknown entry → handle gracefully
   - [ ] Special characters in names → slugified correctly

## Next Steps

**Immediate (to make it functional):**
1. Implement `_load_existing_exports()` - read JSON files from disk
2. Implement `_generate_changes()` - compare old vs new
3. Enhance `_write_readme()` - proper changelog format
4. Fix `_git_commit()` - handle no-changes case

**After that (code quality):**
5. Add progress reporting
6. Better error handling
7. DRY up export methods

**Later (polish):**
8. Dry run mode
9. Test coverage
10. Docstrings

## Code Quality Notes

**What's Good:**
- Proper separation of concerns (slugify utility vs export logic)
- Type hints throughout
- Validation built in
- Follows design spec for file paths

**What's Still Bad:**
- TODOs in critical path
- Export methods are repetitive
- No tests
- Minimal docstrings on helpers
- No progress feedback

**Estimated Completion:**
- Core functionality (items 4-7): 2-3 hours
- Code quality improvements (items 8-10): 1-2 hours
- Polish (items 11-14): Variable

---

**Status:** 30% complete → 60% complete after critical fixes
**Blocker:** Change detection and README generation still TODO
