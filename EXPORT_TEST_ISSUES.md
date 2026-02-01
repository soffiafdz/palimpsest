# Export JSON Test Issues

**Date:** 2026-02-01
**Test Run:** First real database export

## Critical Issues

### 1. ❌ 90 People Missing Lastname AND Disambiguator

**Problem:** Export skips 90 people because they have `NULL` for both lastname and disambiguator fields.

**Examples:**
- Person ID 10: Mónica (NULL, NULL)
- Person ID 16: Sofía (NULL, NULL)
- Person ID 17: Nymi (NULL, NULL)
- Person ID 22: Karen (NULL, NULL)
- ... and 86 more

**Root cause:** Data quality issue - these people were imported without lastname/disambiguator.

**Design requirement:** Every person must have lastname OR disambiguator for filename uniqueness.

**Fix needed:**
- Query all people with `lastname IS NULL AND disambiguator IS NULL`
- Review each person and add appropriate lastname or disambiguator
- Re-run export to verify all people export successfully

**Query to find them:**
```sql
SELECT id, name, lastname, disambiguator
FROM persons
WHERE lastname IS NULL AND disambiguator IS NULL;
```

### 2. ❌ Git Commit Doesn't Work with Submodules

**Problem:** `_git_commit()` method runs git commands with `cwd=ROOT` (main repo), but export files are written to `data/exports/` which is a git submodule. Git operations in the main repo can't see files in the submodule.

**Impact:** Automatic git commits fail silently. Files are written but not committed.

**Workaround:** Manually commit in data submodule:
```bash
cd data
git add exports/
git commit -m "DB export - [timestamp]"
cd ..
git add data
git commit -m "Update data submodule: [export description]"
```

**Fix needed:**
- Detect if output directory is in a git submodule
- If yes, run git commands in the submodule directory
- Update main repo submodule reference after submodule commit
- Or: add configuration option to specify git working directory

**Code location:** `dev/pipeline/export_json.py` line 903-956 (`_git_commit()`)

### 3. ❌ Change Detection Shows False Positives

**Problem:** Second export with no database changes shows "141 added, 0 modified, 0 deleted" instead of "No changes".

**Expected behavior:** If entity data hasn't changed, changes should be empty.

**Observed behavior:** README shows 141 entities as "added" on second run.

**Hypothesis:**
- `_load_existing_exports()` might not be loading all files correctly
- Or: comparison logic has a bug
- Or: people entity type is special because 90 are skipped, so counts don't match

**Fix needed:**
- Debug `_load_existing_exports()` to verify it loads all 10,505 files
- Check if skipped people are causing the false positives
- Verify entity comparison logic in `_generate_changes()`

**Code location:**
- `dev/pipeline/export_json.py` line 494-578 (`_load_existing_exports()`)
- `dev/pipeline/export_json.py` line 580-603 (`_generate_changes()`)

### 4. ❌ README Regenerates with Timestamp Even When No Changes

**Problem:** README.md updates timestamp on every export, even when entity data hasn't changed. This creates a modified file requiring a commit.

**Expected behavior:** If no entity changes detected, README should not be modified at all.

**Impact:** Unnecessary commits on every export run.

**Fix needed:**
- Only write README if `len(self.changes) > 0`
- Or: skip timestamp update if no changes
- Or: don't include timestamp (just show entity counts and changes)

**Code location:** `dev/pipeline/export_json.py` line 825-901 (`_write_readme()`)

## Minor Issues

### 5. ⚠️ Entity Type Singular Form

**Issue:** README shows "entrie" instead of "entry" (line 25 in README).

**Fix:** Update `_get_entity_slug()` to properly singularize entity types.

**Code location:** `dev/pipeline/export_json.py` line 605-636 (`_get_entity_slug()`)

## What Worked Correctly

✅ Directory structure (entries/YYYY/, people/, locations/city/, scenes/YYYY-MM-DD/)
✅ File naming with slugification (firstname_lastname.json)
✅ JSON format with proper fields and ID relationships
✅ Progress feedback for large datasets
✅ Validation warnings for people missing lastname/disambiguator
✅ 10,505 files exported successfully

## Priority

1. **HIGH**: Fix 90 people missing lastname/disambiguator (blocks complete export)
2. **HIGH**: Fix git commit for submodules (breaks automation)
3. **MEDIUM**: Fix change detection false positives (confusing, but workaround exists)
4. **MEDIUM**: Fix README unnecessary updates (creates noise)
5. **LOW**: Fix singular form in entity names (cosmetic)

## Next Steps

1. Query database for all people with NULL lastname AND disambiguator
2. Review each person and determine appropriate lastname or disambiguator
3. Update database
4. Re-run export to verify
5. Then tackle git submodule issue
