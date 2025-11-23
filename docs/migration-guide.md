# Migration Guide: Tombstone Pattern Implementation

## Overview

This guide walks you through migrating your existing Palimpsest database to the new tombstone pattern implementation for multi-machine synchronization.

**Target Audience**: Palimpsest users upgrading from a version without tombstone support

**Prerequisites**:
- Existing Palimpsest installation
- Database with journal entries
- Git repository initialized
- Python environment with dependencies installed

**Time Estimate**: 15-30 minutes

---

## Migration Overview

### What's Being Added

**New Database Tables**:
1. `association_tombstones` - Track deleted associations
2. `sync_states` - Track sync state and conflicts
3. `entity_snapshots` - Store entity snapshots (Phase 5, not currently used)

**Modified Tables**:
1. `entries` - Add soft delete columns (`deleted_at`, `deleted_by`, `deletion_reason`)

**New Features**:
- Soft delete for entries
- Tombstone tracking for association deletions
- Conflict detection for concurrent edits
- CLI commands for management

### What's NOT Changing

**Existing Data**:
- All existing entries preserved
- All existing relationships preserved
- No data loss during migration
- Backward compatible (can downgrade)

**Workflow**:
- YAML → SQL sync still works
- Wiki → SQL sync still works
- Daily workflow mostly unchanged

---

## Pre-Migration Checklist

### 1. Backup Your Data

**Critical**: Always backup before schema changes.

```bash
# Full backup (recommended)
python -m dev.pipeline.cli backup-full --suffix pre-tombstone-migration

# Verify backup created
python -m dev.pipeline.cli backup-list-full

# Output:
# Available backups:
#   palimpsest_backup_pre-tombstone-migration_20241123_160000.db
```

**Manual Backup**:
```bash
# Copy database file
cp data/palimpsest.db data/palimpsest.db.backup-$(date +%Y%m%d)

# Copy entire data directory
cp -r data data.backup-$(date +%Y%m%d)
```

### 2. Verify Current State

**Check Database Integrity**:
```bash
# Validate database
validate db integrity

# Output should be:
# ✅ Database integrity check passed
```

**Check Current Schema Version**:
```bash
# Check Alembic revision
cd ~/Documents/palimpsest
alembic current

# Output (example):
# abc123def456 (head)
```

**Record Current Statistics**:
```bash
# Count entries
sqlite3 data/palimpsest.db "SELECT COUNT(*) FROM entries;"

# Count relationships
sqlite3 data/palimpsest.db "
SELECT
  (SELECT COUNT(*) FROM entry_people) as people,
  (SELECT COUNT(*) FROM entry_tags) as tags,
  (SELECT COUNT(*) FROM entry_events) as events;
"
```

Save these numbers to verify after migration.

### 3. Commit Current State

```bash
# Ensure clean git state
git status

# If uncommitted changes, commit them
git add .
git commit -m "Pre-migration checkpoint"

# Tag this version for easy rollback
git tag pre-tombstone-migration
git push origin pre-tombstone-migration
```

### 4. Update Code

**Pull Latest Code**:
```bash
cd ~/Documents/palimpsest
git pull origin main
```

**Verify New Code**:
```bash
# Check new migration exists
ls dev/migrations/versions/*tombstone*

# Output should include:
# dev/migrations/versions/20251122_add_tombstone_and_sync_tracking.py
```

### 5. Review Changes

**Read Documentation**:
- `docs/multi-machine-sync.md` - User guide
- `docs/tombstone-guide.md` - Technical details
- `docs/conflict-resolution.md` - Conflict handling

**Review Migration File**:
```bash
# View migration
cat dev/migrations/versions/20251122_add_tombstone_and_sync_tracking.py
```

---

## Migration Steps

### Step 1: Run Alembic Migration

**Apply Migration**:
```bash
cd ~/Documents/palimpsest

# Run migration
alembic upgrade head
```

**Expected Output**:
```
INFO  [alembic.runtime.migration] Context impl SQLiteImpl.
INFO  [alembic.runtime.migration] Will assume non-transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade <prev_rev> -> 20251122_add_tombstone_and_sync_tracking, Add tombstone and synchronization tracking
```

**If Error Occurs**:
```bash
# Check Alembic history
alembic history

# Check current revision
alembic current

# If migration failed mid-way, see Troubleshooting section below
```

### Step 2: Verify Schema Changes

**Check New Tables Created**:
```bash
sqlite3 data/palimpsest.db "
SELECT name FROM sqlite_master
WHERE type='table'
ORDER BY name;
"
```

**Expected Output** (should include):
```
association_tombstones
entries
entity_snapshots
sync_states
...
```

**Check New Columns on Entries**:
```bash
sqlite3 data/palimpsest.db "PRAGMA table_info(entries);"
```

**Expected Output** (should include):
```
...
deleted_at|DATETIME|0||0
deleted_by|VARCHAR|0||0
deletion_reason|TEXT|0||0
...
```

**Check Indexes Created**:
```bash
sqlite3 data/palimpsest.db "
SELECT name FROM sqlite_master
WHERE type='index'
  AND (name LIKE '%tombstone%' OR name LIKE '%sync%')
ORDER BY name;
"
```

**Expected Output**:
```
idx_entries_deleted_at
idx_sync_states_conflict_detected
idx_sync_states_entity_type
idx_tombstones_expires_at
idx_tombstones_left_id
idx_tombstones_removed_at
idx_tombstones_right_id
idx_tombstones_table_name
uq_sync_state_entity
uq_tombstone_association
```

### Step 3: Verify Data Preserved

**Count Entries**:
```bash
sqlite3 data/palimpsest.db "SELECT COUNT(*) FROM entries;"
```

**Should match** pre-migration count.

**Count Relationships**:
```bash
sqlite3 data/palimpsest.db "
SELECT
  (SELECT COUNT(*) FROM entry_people) as people,
  (SELECT COUNT(*) FROM entry_tags) as tags,
  (SELECT COUNT(*) FROM entry_events) as events;
"
```

**Should match** pre-migration counts.

**Verify No Soft Deletes**:
```bash
sqlite3 data/palimpsest.db "
SELECT COUNT(*) FROM entries WHERE deleted_at IS NOT NULL;
"
```

**Should be**: `0` (no entries soft-deleted yet)

### Step 4: Initialize Sync States

**Perform Initial Sync**:
```bash
# Sync all entries from YAML
python -m dev.pipeline.yaml2sql sync journal/md/

# This will:
# 1. Process all YAML files
# 2. Create sync_states records
# 3. Compute and store file hashes
# 4. Establish baseline for conflict detection
```

**Expected Output**:
```
Processing entries from journal/md/...
Processed 1200 entries
Created 1200 sync states
```

**Verify Sync States Created**:
```bash
sqlite3 data/palimpsest.db "SELECT COUNT(*) FROM sync_states;"
```

**Should be**: Number of journal entries (e.g., 1200)

**Check Sync State Sample**:
```bash
sqlite3 data/palimpsest.db "
SELECT entity_type, entity_id, sync_source, sync_hash
FROM sync_states
LIMIT 5;
"
```

**Expected Output**:
```
Entry|123|yaml|abc123def456...
Entry|124|yaml|def456ghi789...
Entry|125|yaml|ghi789jkl012...
...
```

### Step 5: Verify CLI Commands

**Test Tombstone Commands**:
```bash
# Should show no tombstones (none created yet)
metadb tombstone list

# Output:
# 📋 Association Tombstones (0)

# Should show zero statistics
metadb tombstone stats

# Output:
# 📊 Tombstone Statistics
# Total tombstones: 0
```

**Test Sync Commands**:
```bash
# Should show no conflicts (fresh baseline)
metadb sync conflicts

# Output:
# ✅ No unresolved conflicts found

# Should show statistics
metadb sync stats

# Output:
# 📊 Sync State Statistics
# Total entities tracked: 1200
# Conflicts (unresolved): 0
# ...
```

### Step 6: Test Tombstone Creation

**Create Test Tombstone**:
```bash
# Edit an entry to remove a person
vim journal/md/2024/2024-11-01.md

# Before:
# people: [Alice, Bob, Charlie]

# After (remove Bob):
# people: [Alice, Charlie]

# Save and sync
python -m dev.pipeline.yaml2sql update journal/md/2024/2024-11-01.md

# Output should include:
# Created association tombstone for entry_people
```

**Verify Tombstone Created**:
```bash
metadb tombstone list

# Output:
# 📋 Association Tombstones (1)
#
# Table: entry_people
#   Left ID: <entry_id>
#   Right ID: <person_id>
#   Removed: 2024-11-23T...
#   Removed by: yaml2sql
#   Reason: removed_from_source
```

**Verify Tombstone Prevents Re-add**:
```bash
# Try re-adding Bob
vim journal/md/2024/2024-11-01.md
# Change: people: [Alice, Charlie] → people: [Alice, Bob, Charlie]

# Sync again
python -m dev.pipeline.yaml2sql update journal/md/2024/2024-11-01.md

# Bob should NOT be re-added (tombstone prevents it)
# To verify:
metadb show <entry_id> --full

# People should still be: [Alice, Charlie]
```

**Remove Test Tombstone**:
```bash
# If you want to actually re-add Bob:
metadb tombstone remove entry_people <entry_id> <person_id>

# Then re-sync
python -m dev.pipeline.yaml2sql update journal/md/2024/2024-11-01.md

# Now Bob will be re-added
```

### Step 7: Commit Migration

**Commit Database Changes**:
```bash
cd ~/Documents/palimpsest

# Add database changes
git add data/palimpsest.db

# Commit
git commit -m "Apply tombstone pattern migration

- Run Alembic migration: add_tombstone_and_sync_tracking
- Initialize sync states for all entries
- Verified data integrity
- All entries and relationships preserved"

# Push to remote
git push origin main
```

**Tag Migration Point**:
```bash
git tag tombstone-migration-complete
git push origin tombstone-migration-complete
```

---

## Post-Migration Checklist

### 1. Verify All Systems

**Database Validation**:
```bash
validate db all
```

**Expected Output**:
```
✅ Database schema valid
✅ Database integrity check passed
✅ Database migrations current
✅ Database constraints valid
```

**YAML Validation**:
```bash
validate md frontmatter journal/md/ --limit 10
```

**Expected Output**:
```
✅ All frontmatter valid
```

### 2. Test Multi-Machine Sync (If Applicable)

**On Second Machine**:
```bash
# Pull changes
cd ~/Documents/palimpsest
git pull origin main

# Run migration (should be already applied via git)
alembic current

# Sync from YAML
python -m dev.pipeline.yaml2sql sync journal/md/

# Should create sync states on this machine
metadb sync stats

# Verify tombstones synced
metadb tombstone list
```

### 3. Update Workflow

**New Daily Workflow**:
```bash
# START of session
git pull
python -m dev.pipeline.yaml2sql sync journal/md/
metadb sync conflicts  # Check for conflicts

# ... edit files ...

# END of session
python -m dev.pipeline.yaml2sql sync journal/md/
metadb sync conflicts  # Check again
git add . && git commit -m "..." && git push
```

**Optional**: Create shell aliases:
```bash
# Add to ~/.bashrc or ~/.zshrc
alias journal-start="cd ~/Documents/palimpsest && git pull && python -m dev.pipeline.yaml2sql sync journal/md/ && metadb sync conflicts"
alias journal-end="cd ~/Documents/palimpsest && python -m dev.pipeline.yaml2sql sync journal/md/ && metadb sync conflicts"
```

### 4. Set Up Maintenance

**Monthly Tombstone Cleanup** (optional):
```bash
# Add to crontab
crontab -e

# Add line (runs on 1st of month at 2am):
0 2 1 * * cd ~/Documents/palimpsest && metadb tombstone cleanup
```

### 5. Monitor Health

**First Week** (check daily):
```bash
metadb sync conflicts
metadb tombstone stats
```

**After First Week** (check weekly):
```bash
metadb sync stats
```

---

## Rollback Plan

If you encounter issues and need to rollback:

### Option 1: Rollback via Alembic

**Downgrade Database**:
```bash
# Get previous revision ID
alembic history

# Downgrade to previous version
alembic downgrade <previous_revision_id>
```

**Restore Code**:
```bash
# Revert to previous git tag
git checkout pre-tombstone-migration

# Or revert specific files
git checkout pre-tombstone-migration -- dev/database/
git checkout pre-tombstone-migration -- dev/pipeline/
```

### Option 2: Restore from Backup

**Restore Database**:
```bash
# Copy backup back
cp data/palimpsest.db.backup-20241123 data/palimpsest.db

# Or restore from full backup
python -m dev.pipeline.cli restore-full data/palimpsest_backup_pre-tombstone-migration_20241123_160000.db
```

**Verify Restoration**:
```bash
# Check Alembic revision
alembic current

# Should show pre-migration revision

# Check tables
sqlite3 data/palimpsest.db ".tables"

# Should NOT include: association_tombstones, sync_states, entity_snapshots
```

### Option 3: Fresh Start

**If All Else Fails**:
```bash
# Delete database
rm data/palimpsest.db

# Rebuild from YAML
python -m dev.pipeline.yaml2sql sync journal/md/ --force

# This creates fresh database with all entries from YAML
```

---

## Troubleshooting

### Problem: Migration Fails with "Table Already Exists"

**Symptom**:
```
alembic.util.exc.CommandError: Target database is not up to date.
```

**Diagnosis**:
```bash
# Check current revision
alembic current

# Check if tables already exist
sqlite3 data/palimpsest.db ".tables"
```

**Solution 1** (tables don't exist):
```bash
# Stamp database with correct revision
alembic stamp head
```

**Solution 2** (tables already exist):
```bash
# Database already migrated, just stamp it
alembic stamp 20251122_add_tombstone_and_sync_tracking
```

### Problem: Migration Fails Mid-Way

**Symptom**: Some tables created, some not.

**Diagnosis**:
```bash
# Check what exists
sqlite3 data/palimpsest.db ".schema"
```

**Solution**:
```bash
# Rollback to backup
cp data/palimpsest.db.backup-20241123 data/palimpsest.db

# Try migration again
alembic upgrade head

# If still fails, check Alembic logs for specific error
```

### Problem: No Sync States Created

**Symptom**: After sync, `SELECT COUNT(*) FROM sync_states` returns 0.

**Diagnosis**:
```bash
# Check if sync actually ran
python -m dev.pipeline.yaml2sql sync journal/md/ --verbose

# Check for errors in output
```

**Solution**:
```bash
# Force full sync
python -m dev.pipeline.yaml2sql sync journal/md/ --force

# Verify sync states created
sqlite3 data/palimpsest.db "SELECT COUNT(*) FROM sync_states;"
```

### Problem: Tombstone Not Preventing Re-add

**Symptom**: Removed person, but re-added during sync.

**Diagnosis**:
```bash
# Check if tombstone exists
metadb tombstone list --table entry_people

# Check EntryManager code
grep -A 10 "tombstones.exists" dev/database/managers/entry_manager.py
```

**Solution**:
```bash
# Manually create tombstone
# (Requires Python session)
python
>>> from dev.database import PalimpsestDB
>>> db = PalimpsestDB("data/palimpsest.db")
>>> with db.session_scope() as session:
...     db.entries.tombstones.create(
...         table_name="entry_people",
...         left_id=<entry_id>,
...         right_id=<person_id>,
...         removed_by="manual",
...         sync_source="manual",
...         reason="migration_fix",
...     )

# Verify
metadb tombstone list
```

### Problem: Git Merge Conflicts After Migration

**Symptom**: `git pull` shows conflicts in database file.

**Diagnosis**:
```bash
git status

# Output:
# both modified: data/palimpsest.db
```

**Solution**:
```bash
# Accept incoming changes (from remote)
git checkout --theirs data/palimpsest.db
git add data/palimpsest.db

# OR accept local changes
git checkout --ours data/palimpsest.db
git add data/palimpsest.db

# OR use custom merge strategy
# See docs/multi-machine-sync.md for details

# Complete merge
git commit
```

### Problem: Performance Degradation

**Symptom**: Sync takes much longer than before.

**Diagnosis**:
```bash
# Check index usage
sqlite3 data/palimpsest.db "
EXPLAIN QUERY PLAN
SELECT * FROM sync_states
WHERE entity_type = 'Entry' AND entity_id = 123;
"
```

**Solution**:
```bash
# Rebuild indexes
sqlite3 data/palimpsest.db "REINDEX;"

# Analyze database
sqlite3 data/palimpsest.db "ANALYZE;"

# Vacuum database (reclaim space)
sqlite3 data/palimpsest.db "VACUUM;"
```

---

## Migration for Different Scenarios

### Scenario 1: Fresh Installation

**No migration needed!** Just initialize:

```bash
# Clone repository
git clone <repo_url>
cd palimpsest

# Initialize database
alembic upgrade head

# Sync from YAML
python -m dev.pipeline.yaml2sql sync journal/md/
```

### Scenario 2: Multi-Machine Setup

**Primary Machine** (run migration first):
```bash
# Follow standard migration steps above
alembic upgrade head
python -m dev.pipeline.yaml2sql sync journal/md/
git add data/palimpsest.db
git commit -m "Apply tombstone migration"
git push
```

**Secondary Machines** (pull migrated database):
```bash
# Pull changes
git pull

# Verify migration applied
alembic current

# Sync (creates sync states for this machine)
python -m dev.pipeline.yaml2sql sync journal/md/

# Verify
metadb sync stats
```

### Scenario 3: Large Database (10,000+ entries)

**Migration may take longer.**

**Optimize**:
```bash
# Before migration, compact database
sqlite3 data/palimpsest.db "VACUUM;"

# Run migration
alembic upgrade head

# Batch sync (process in chunks)
python -m dev.pipeline.yaml2sql sync journal/md/2024/ --verbose
python -m dev.pipeline.yaml2sql sync journal/md/2023/ --verbose
# ... etc

# Verify
metadb sync stats
```

---

## Validation Checklist

After migration, verify:

- [ ] Database schema includes new tables (tombstones, sync_states, snapshots)
- [ ] Entries table has soft delete columns
- [ ] All existing entries preserved (count matches)
- [ ] All relationships preserved (counts match)
- [ ] Sync states created for all entries
- [ ] No soft-deleted entries (`deleted_at IS NULL` for all)
- [ ] No conflicts detected initially
- [ ] CLI commands work (tombstone, sync)
- [ ] Test tombstone creation works
- [ ] Test tombstone prevents re-add
- [ ] Git commit successful
- [ ] Second machine syncs correctly (if applicable)
- [ ] No performance degradation
- [ ] Database validation passes

---

## Support and Help

### Documentation

- **User Guide**: `docs/multi-machine-sync.md`
- **Technical Guide**: `docs/tombstone-guide.md`
- **Conflict Resolution**: `docs/conflict-resolution.md`

### Validation Tools

```bash
# Full validation suite
validate db all
validate md frontmatter journal/md/
validate wiki stats
```

### Diagnostic Commands

```bash
# Database health
metadb sync stats
metadb tombstone stats

# Specific entry
metadb show <entry_id> --full
metadb sync status Entry <entry_id>

# Recent activity
metadb tombstone list --limit 20
```

### Getting Help

If you encounter issues not covered in this guide:

1. Check existing documentation
2. Run validation tools
3. Check git history for recent changes
4. Review Alembic migration logs
5. Restore from backup if needed

---

## Summary

**Migration Steps** (Quick Reference):

1. **Backup**: `python -m dev.pipeline.cli backup-full --suffix pre-tombstone-migration`
2. **Commit**: `git add . && git commit -m "Pre-migration checkpoint"`
3. **Migrate**: `alembic upgrade head`
4. **Verify Schema**: `sqlite3 data/palimpsest.db ".tables"`
5. **Initialize Sync**: `python -m dev.pipeline.yaml2sql sync journal/md/`
6. **Verify**: `metadb sync stats`
7. **Test**: Create test tombstone, verify behavior
8. **Commit**: `git add data/palimpsest.db && git commit && git push`
9. **Validate**: `validate db all`

**Rollback Steps** (If Needed):

1. `alembic downgrade <previous_revision>`
2. Or: `cp data/palimpsest.db.backup-20241123 data/palimpsest.db`
3. `git checkout pre-tombstone-migration`

**Post-Migration**:
- Use new daily workflow (pull, sync, check conflicts, edit, sync, push)
- Monitor conflicts weekly
- Run monthly tombstone cleanup
- Review documentation for advanced features

**Migration is complete!** You now have full multi-machine synchronization support with deletion tracking and conflict detection.
