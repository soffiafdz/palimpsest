# Fix People Data Quality - Workflow

## Problem

89 people in the database have NULL for both `lastname` AND `disambiguator`, which prevents them from being exported (filename uniqueness requirement).

## Solution

Update the **metadata YAML files** to add missing lastname or disambiguator fields. When the database is re-imported, the people will have the correct data.

## Categories

### 1. Critical (Name Conflicts) - 7 People

These people have duplicate names in the database. **MUST add `disambiguator` field** to differentiate them.

**Document:** `people_critical_yaml_updates.md`

**People:**
- Mónica (ID 10) - 3 people with this name
- Sofía (ID 16) - 2 people with this name
- Patricia (ID 31) - 2 people with this name
- Iván (ID 61) - 2 people with this name
- Paola (ID 72) - **4 people with this name!**
- Chloé (ID 133) - 2 people with this name
- Emily (ID 210) - 2 people with this name

### 2. Non-Conflicting - 82 People

These people have unique first names. Can add `lastname` field.

**Document:** `people_non_conflicting_yaml_updates.md`

**Note:** Some of these (like "mother" ID 75, "father" ID 229) might be better with disambiguators instead of fake lastnames.

## Workflow

### Step 1: Review Documents

1. Open `people_critical_yaml_updates.md`
2. For each person, read the entry summaries to understand who they are
3. Decide what disambiguator to use (e.g., "work friend", "ex-partner", "neighbor")

### Step 2: Update YAML Files

For each person, update the YAML files listed in the document.

**Example - Adding disambiguator:**
```yaml
people:
  - name: Mónica
    disambiguator: "work colleague"  # Add this line
```

**Example - Adding lastname:**
```yaml
people:
  - name: Fernando
    lastname: "García"  # Add this line
```

### Step 3: Re-import to Database

After updating YAML files:

```bash
# Re-import metadata to database
plm import-metadata --all

# Or for specific years if you want to be incremental
plm import-metadata --years 2021-2025
```

### Step 4: Test Export Again

```bash
plm export-json
```

Should now export all 320 people (previously only 230 were exported, 90 were skipped).

## Files Created

- `people_critical_yaml_updates.md` - 7 people with name conflicts (MUST add disambiguator)
- `people_non_conflicting_yaml_updates.md` - 82 people (can add lastname)
- `people_missing_lastname.txt` - Raw list of all 89 people
- `EXPORT_TEST_ISSUES.md` - Full test results and issues found
- `FIX_PEOPLE_DATA_WORKFLOW.md` - This file

## Notes

- **Don't edit the database directly** - it will be recreated from YAML files
- **Disambiguator examples**: "work friend", "neighbor", "ex-partner", "family", "roommate", "colleague"
- **Lastname**: Use actual lastnames if known, or consider disambiguator for single-name people
- **Special cases**: "mother", "father", "mom" should probably use disambiguator "family"

## After Fixing

Once all people are fixed and re-imported:

1. Export should work completely (320 people instead of 230)
2. No more validation warnings
3. All person files will be created with proper slugified filenames
4. Can proceed with testing other export features (git commit, change detection)
