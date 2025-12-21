# Production Transition Guide

This guide walks you through transitioning the refactored Palimpsest codebase into daily production use.

---

## Pre-Transition Status

**Current State (as of validation run):**
- 384 journal entries total
- 360 clean entries (94%)
- 24 entries with issues (20 errors, 4 warnings)
- 1 pending database migration

---

## Step 1: Backup Everything

Before making any changes, create complete backups:

```bash
# Create full data backup
plm backup-full

# Create database backup
metadb backup --type manual --suffix pre-transition

# Verify backups exist
plm backup-list-full
metadb backups
```

---

## Step 2: Apply Database Migration

The database has one pending migration that renames internal tables (MentionedDate → Moment). This is a **database-only change** that does NOT affect your YAML frontmatter syntax.

```bash
# Check current migration status
alembic current
# Expected: b8e4f0c2a3d5

# View pending migration details
alembic history --verbose | head -20

# Apply the migration
metadb migration upgrade

# Verify migration applied
alembic current
# Expected: 9e7f2a2a244e (head)

# Confirm schema is now correct
validate db schema
```

**What this migration does:**
- Renames `dates` table → `moments` (internal only)
- Renames association tables (`entry_dates` → `entry_moments`, etc.)
- Creates new `moment_events` relationship table
- **Your YAML `dates:` field name stays the same** - no frontmatter changes needed for this

---

## Step 3: Fix Frontmatter Errors

Run validation to see current issues:

```bash
validate frontmatter --md-dir data/journal/content/md all
```

### Error Categories and Fixes

#### 3.1 Unclosed Parentheses in Dates (7 files)

**Files:** 2025-03-31.md, 2025-06-30.md, 2025-07-06.md, 2025-09-11.md, 2025-10-11.md, 2025-10-23.md

**Problem:** Context strings have unclosed `(` parentheses.

**Example error:**
```yaml
# Wrong
dates:
  - "2025-01-10 (I gave @Clara the anklet)."
```

**Fix:** Close the parenthesis before any trailing punctuation:
```yaml
# Correct
dates:
  - "2025-01-10 (I gave @Clara the anklet.)"
```

Or if the period is intentional after the parenthesis, ensure matching:
```yaml
dates:
  - "2025-01-10 (I gave @Clara the anklet)"
```

---

#### 3.2 Invalid Date Values with "." (2 files)

**Files:** 2025-04-30.md, 2025-06-08.md

**Problem:** Using `.` (entry date shorthand) incorrectly with inline context.

**Example error:**
```yaml
# Wrong - mixing shorthand with inline format
dates:
  - ". (New date for thesis seminar.)"
```

**Fix:** Use dict format for entry date with context:
```yaml
# Correct
dates:
  - date: .
    context: "New date for thesis seminar."
```

---

#### 3.3 Flat Locations with Multiple Cities (6 files)

**Files:** 2025-03-02.md, 2025-06-10.md, 2025-06-12.md, 2025-06-24.md, 2025-06-25.md, 2025-06-29.md

**Problem:** Using flat location list when entry spans multiple cities.

**Example error:**
```yaml
# Wrong - ambiguous which location belongs to which city
city: [Montréal, Toronto]
locations: [Café Olimpico, CN Tower, Mount Royal]
```

**Fix:** Use nested dict to associate locations with cities:
```yaml
# Correct
cities:
  - name: Montréal
    locations: [Café Olimpico, Mount Royal]
  - name: Toronto
    locations: [CN Tower]
```

---

#### 3.4 People in Dates Not in Main Field (3 files)

**Files:** 2025-03-15.md, 2025-07-23.md, 2025-10-02.md

**Problem:** People referenced in `dates[].people` must also appear in main `people` field.

**Example error:**
```yaml
# Wrong - Max only in dates, not in people
people: [Alice, Bob]
dates:
  - date: 2025-03-15
    people: Max  # Error: Max not in main people field
```

**Fix:** Add the person to the main `people` field:
```yaml
# Correct
people: [Alice, Bob, Max]
dates:
  - date: 2025-03-15
    people: Max
```

---

#### 3.5 Malformed Person/Alias Format (1 file)

**File:** 2025-03-31.md

**Problem:** Incomplete parentheses in alias definition.

**Example error:**
```yaml
# Wrong
people:
  - "@Majo (María"  # Missing closing paren
```

**Fix:**
```yaml
# Correct
people:
  - "@Majo (María José)"
```

---

#### 3.6 Multiple Aliases for Same Person (2 files)

**Files:** 2024-12-04.md, 2025-02-09.md

**Problem:** Same person has multiple alias entries instead of combined.

**Example error:**
```yaml
# Wrong - two entries for same person
people:
  - "@Majo (María José)"
  - "@MJ (María José)"
```

**Fix:** Combine into single entry with alias list:
```yaml
# Correct
people:
  - name: María José
    alias: [Majo, MJ]
```

---

#### 3.7 Poem Structure Errors (2 files)

**Files:** 2024-11-27.md, 2025-04-30.md

**Problem:** Missing required poem fields or wrong structure.

**Fixes:**
```yaml
# Correct poem structure
poems:
  - title: "Poem Title"
    content: |
      Line 1 of poem
      Line 2 of poem
    revision_date: 2024-11-27  # Optional, defaults to entry date
    notes: "Optional notes"    # Optional
```

---

#### 3.8 Unknown Date Field (Warnings - 2 files)

**Files:** 2025-01-12.md, 2025-06-02.md

**Problem:** Using `location` (singular) instead of `locations` (plural).

**Fix:**
```yaml
# Wrong
dates:
  - date: 2025-01-12
    location: Café Olimpico  # Wrong field name

# Correct
dates:
  - date: 2025-01-12
    locations: [Café Olimpico]
```

---

#### 3.9 City Name Typo (Warning - 1 file)

**File:** 2025-12-05.md

**Problem:** Typo in city name (`Mont-Sain-Hilaire` vs `Mont-Saint-Hilaire`).

**Fix:** Correct the typo in the city field.

---

## Step 4: Re-validate After Fixes

After fixing all errors:

```bash
# Run full validation
validate frontmatter --md-dir data/journal/content/md all

# Expected output:
# Files Checked: 384
# Clean Files: 384
# Files with Errors: 0
```

---

## Step 5: Sync and Verify

Once validation passes:

```bash
# Sync markdown to database
plm sync-db

# Check database health
metadb health

# Verify entry counts
metadb stats

# Run consistency check
validate consistency --md-dir data/journal/content/md all
```

---

## Step 6: Export Wiki

Generate the wiki pages from the database:

```bash
# Export wiki
plm export-wiki

# Validate wiki integrity
validate wiki
```

---

## Step 7: Test Full Pipeline

Run the complete pipeline to verify everything works:

```bash
# Full pipeline run
plm run-all

# Check status
plm status
```

---

## Daily Workflow (Post-Transition)

Once transitioned, your daily workflow is:

```bash
# 1. Process new inbox entries (if using 750words or similar)
plm inbox

# 2. Sync to database
plm sync-db

# 3. Export wiki (for browsing in vim)
plm export-wiki

# Or run all at once:
plm run-all
```

---

## Neovim Integration

After the pipeline is working, the Neovim plugin should work with:

1. Wiki browsing via vimwiki
2. Entry navigation
3. Search via `jsearch` command

Test with:
```bash
# Test search
jsearch index status
jsearch query "therapy"
```

If search index doesn't exist:
```bash
jsearch index create
```

---

## Troubleshooting

### Migration Fails
```bash
# Check current state
alembic current

# View history
alembic history

# If needed, stamp to specific revision (use with caution)
# alembic stamp <revision>
```

### Validation Still Fails After Fixes
```bash
# Run specific validators for detailed errors
validate frontmatter dates --md-dir data/journal/content/md
validate frontmatter people --md-dir data/journal/content/md
validate frontmatter locations --md-dir data/journal/content/md
```

### Database Sync Issues
```bash
# Check database health
metadb health

# View sync state
metadb sync status

# If needed, rebuild from YAML
metadb reset --keep-backups
plm sync-db
```

---

## Quick Reference: Field Syntax

### People
```yaml
# Simple
people: [Alice, Bob]

# With alias
people:
  - "@Ali (Alice Johnson)"
  - Bob

# Multiple aliases
people:
  - name: María José
    alias: [Majo, MJ]
```

### Locations
```yaml
# Single city
city: Montréal
locations: [Café Olimpico, Mount Royal]

# Multiple cities
cities:
  - name: Montréal
    locations: [Café Olimpico]
  - name: Toronto
    locations: [CN Tower]
```

### Dates
```yaml
# Simple
dates:
  - "2025-01-15"
  - "2025-01-20 (birthday party)"

# Entry date shorthand
dates:
  - date: .
    context: "Today's context"

# With associations
dates:
  - date: 2025-01-15
    context: "Meeting at cafe"
    people: [Alice]
    locations: [Café Olimpico]

# Exclude entry date from dates list
dates:
  - "~"  # Opt-out marker
  - "2025-01-20"
```

### Poems
```yaml
poems:
  - title: "Poem Title"
    content: |
      First line
      Second line
    revision_date: 2025-01-15  # Optional
    notes: "Draft notes"       # Optional
```

---

## Checklist

- [ ] Create full backup (`plm backup-full`)
- [ ] Create database backup (`metadb backup`)
- [ ] Apply migration (`metadb migration upgrade`)
- [ ] Fix 2024-11-27.md (poems)
- [ ] Fix 2024-12-04.md (multiple aliases)
- [ ] Fix 2025-01-12.md (location→locations)
- [ ] Fix 2025-02-09.md (multiple aliases)
- [ ] Fix 2025-03-02.md (flat locations)
- [ ] Fix 2025-03-15.md (people not in main field)
- [ ] Fix 2025-03-31.md (malformed alias, unclosed paren)
- [ ] Fix 2025-04-30.md (invalid date, poems structure)
- [ ] Fix 2025-06-02.md (location→locations)
- [ ] Fix 2025-06-08.md (invalid date)
- [ ] Fix 2025-06-10.md (flat locations)
- [ ] Fix 2025-06-12.md (flat locations)
- [ ] Fix 2025-06-24.md (flat locations)
- [ ] Fix 2025-06-25.md (flat locations)
- [ ] Fix 2025-06-29.md (flat locations)
- [ ] Fix 2025-06-30.md (unclosed paren)
- [ ] Fix 2025-07-06.md (unclosed paren)
- [ ] Fix 2025-07-23.md (people not in main field)
- [ ] Fix 2025-09-11.md (unclosed paren)
- [ ] Fix 2025-10-02.md (people not in main field)
- [ ] Fix 2025-10-11.md (unclosed paren)
- [ ] Fix 2025-10-23.md (unclosed paren)
- [ ] Fix 2025-12-05.md (city typo)
- [ ] Run validation (all pass)
- [ ] Sync database (`plm sync-db`)
- [ ] Export wiki (`plm export-wiki`)
- [ ] Test search index (`jsearch index create`)
- [ ] Test full pipeline (`plm run-all`)
