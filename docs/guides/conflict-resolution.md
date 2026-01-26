# Conflict Resolution Guide

## Overview

This guide explains how Palimpsest detects and resolves conflicts when the same journal entry is modified on multiple machines.

**Audience**: Users working on Palimpsest across multiple machines (laptop, desktop, etc.)

**Related Documents**:
- Synchronization guide: `synchronization.md`
- Tombstones technical guide: `../development/tombstones.md`

---

## What Is a Conflict?

A **conflict** occurs when:
1. An entry is synced on Machine A (baseline established)
2. The same entry is modified on Machine B (creates divergent state)
3. Machine B pulls changes from Machine A (conflict detected)

**Key Insight**: Conflicts are about **concurrent edits**, not deletions (deletions are handled by tombstones).

---

## Understanding Conflict Detection

### How It Works

Palimpsest uses **hash-based conflict detection**:

1. **Baseline**: When syncing, compute MD5 hash of file content
2. **Store**: Save hash in `sync_states` table
3. **Compare**: On next sync, compare new hash with stored hash
4. **Detect**: If hashes differ, conflict detected

### Example Timeline

```
Machine A                          Machine B
---------                          ---------
T0: Sync entry 2024-11-01
    → Hash: abc123
    → Store in sync_states

T1: Edit entry                     (No changes yet)
    → Change mood: good → great
    → Hash: def456

T2: Sync entry                     (No changes yet)
    → Compare: def456 ≠ abc123
    → Update hash: def456
    → No conflict (same machine)

T3: Push to git                    Pull from git
    → YAML + database              → Get hash: def456

T4:                                Edit SAME entry (unaware of T1)
                                   → Change rating: 4 → 5
                                   → Hash: ghi789

T5:                                Sync entry
                                   → Compare: ghi789 ≠ def456
                                   → CONFLICT DETECTED! ⚠️
```

### What Gets Checked

**File Hash Includes**:
- Entire YAML frontmatter
- All metadata fields (people, tags, mood, rating, etc.)
- Does NOT include markdown body content

**Why**: Metadata is what syncs to database, so that's what we track for conflicts.

---

## Types of Conflicts

### 1. Metadata Conflict (Most Common)

**Scenario**: Both machines edit metadata of same entry.

**Example**:
```yaml
# Machine A changes:
mood: good → great

# Machine B changes (before pulling):
rating: 4 → 5

# Result: Both changes should be preserved
```

**Resolution**: Last-write-wins (YAML overwrites database), but conflict logged for review.

### 2. Relationship Conflict

**Scenario**: Both machines add/remove people, tags, etc.

**Example**:
```yaml
# Machine A:
people: [Alice, Bob] → [Alice, Bob, Charlie]

# Machine B (before pulling):
people: [Alice, Bob] → [Alice, Bob, Dave]

# Result: Need to merge → [Alice, Bob, Charlie, Dave]
```

**Resolution**: Git merge handles YAML file merge, then sync applies merged result.

### 3. Git Merge Conflict

**Scenario**: Git cannot auto-merge YAML files.

**Example**:
```yaml
# Machine A:
<<<<<<< HEAD
mood: great
rating: 5
=======
mood: good
rating: 4
>>>>>>> origin/main
```

**Resolution**: User manually resolves Git conflict, then syncs merged file.

### 4. Wiki vs YAML Conflict

**Scenario**: Wiki sync and YAML sync edit overlapping fields.

**Example**:
```yaml
# YAML controls: people, tags, mood, rating
# Wiki controls: editorial_note, title, summary

# No conflict - different fields
```

**Current Implementation**: Wiki and YAML have separate sync states, no conflicts between them.

---

## Conflict Detection System

### SyncState Table

**Schema**:
```python
class SyncState(Base):
    """Track synchronization state for entities."""
    entity_type: str       # "Entry", "Event", etc.
    entity_id: int         # 123
    last_synced_at: datetime
    sync_source: str       # "yaml" or "wiki"
    sync_hash: str         # MD5 hash of file content
    conflict_detected: bool
    conflict_resolved: bool
    machine_id: str        # hostname
```

### Hash Computation

**Code**: `dev/utils/fs.py:get_file_hash()`

```python
import hashlib

def get_file_hash(file_path: Path) -> str:
    """Compute MD5 hash of file content."""
    hasher = hashlib.md5()

    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)

    return hasher.hexdigest()
```

**Properties**:
- Fast: ~1ms for typical journal entry
- Deterministic: Same file → same hash
- Sensitive: Any change → different hash

### Conflict Check

**Code**: `dev/database/sync_state_manager.py:check_conflict()`

```python
def check_conflict(
    self,
    entity_type: str,
    entity_id: int,
    new_hash: str,
) -> bool:
    """Check if entity has conflict (hash mismatch)."""
    sync_state = self.get(entity_type, entity_id)

    # No baseline - no conflict
    if not sync_state or not sync_state.sync_hash:
        return False

    # Hash mismatch - conflict!
    if sync_state.sync_hash != new_hash:
        sync_state.conflict_detected = True
        self.session.flush()

        self.logger.log_warning(
            f"Conflict detected for {entity_type} {entity_id}",
            {"old_hash": sync_state.sync_hash, "new_hash": new_hash}
        )

        return True

    # Hash match - no conflict
    return False
```

---

## Resolution Strategies

### Current Strategy: Last-Write-Wins

**How It Works**:
1. Conflict detected (hash mismatch)
2. Warning logged
3. YAML file overwrites database (proceeds with sync)
4. Conflict marked for user review
5. User manually verifies changes

*Design Rationale*: This strategy was chosen for its balance of simplicity and effectiveness in a single-user, multi-machine environment. It prioritizes forward progress, ensuring that synchronization never blocks due to conflicts. The explicit logging and requirement for user review acknowledge the potential for data loss while empowering the user to be the ultimate arbiter of truth.

**Advantages**:
- ✅ **Simple to implement**: Reduces development overhead and introduces fewer potential bugs.
- ✅ **Always makes progress (no blocking)**: Ensures the system remains operational even in the presence of conflicts, preventing deadlocks or stalled synchronization.
- ✅ **Works well for single-user multi-machine**: In a single-user context, the "lost" changes are usually from the same user, making manual review manageable.
- ✅ **Predictable behavior**: The outcome of a conflict (YAML overwrites DB) is clear and consistent.

**Disadvantages**:
- ❌ **May lose changes from one machine**: If concurrent edits are not carefully managed, one set of changes might be implicitly overwritten.
- ❌ **Requires manual review**: Places the burden of resolution on the user, which can be tedious for frequent conflicts.
- ❌ **No automatic merging**: Lacks intelligent merging capabilities, requiring the user to manually reconcile differing values.

### Example: Last-Write-Wins

```
T0: Entry has mood: good, rating: 4

Machine A (T1):
  - Edit: mood: good → great
  - Sync: Hash abc123 → def456
  - Push to git

Machine B (T2, before pulling):
  - Edit: rating: 4 → 5
  - Sync: Hash abc123 → ghi789
  - Stored hash: ghi789

Machine B (T3, after pulling):
  - Pull from git
  - File now has: mood: great, rating: 4 (from Machine A)
  - Hash: def456
  - Compare: ghi789 ≠ def456 → CONFLICT
  - Sync proceeds: YAML overwrites database
  - Result: mood: great, rating: 4
  - LOST: rating: 5 change from Machine B ❌
```

**Recovery**: User must manually review conflict and re-apply lost change.

### Alternative Strategy: Three-Way Merge

**Not currently implemented.** Would require a robust snapshot system to record previous states and enable a three-way comparison.

**How It Would Work**:
1. **Baseline**: The last known synchronized state of the entry.
2. **Current**: The current state of the entry in the database.
3. **Incoming**: The state of the entry from the incoming YAML file.
4. **Compare all three**: The system would intelligently compare these three versions to:
   - Identify changes unique to the current database state (local changes).
   - Identify changes unique to the incoming YAML file (remote changes).
   - Identify conflicting changes where both current and incoming modified the same field differently.
5. **Auto-resolve non-conflicting fields**: Automatically merge changes that do not directly conflict.
6. **User resolves conflicting fields**: Present only the truly conflicting changes to the user for manual resolution.

**Advantage**: Significantly reduces the likelihood of lost changes and minimizes the manual effort required for conflict resolution by automating non-conflicting merges.

**Disadvantage**: Substantially more complex to implement, requiring sophisticated change tracking, a historical snapshot system, and a more interactive resolution UI.

---

## Handling Conflicts: User Workflow

### Step 1: Detect Conflicts

**Daily Check**:
```bash
# Check for conflicts
metadb sync conflicts

# Output if conflicts exist:
# ⚠️  Unresolved Conflicts (2)
#
# Entry ID: 123
#   Last synced: 2024-11-23T14:30:00+00:00
#   Sync source: yaml
#   Machine: laptop
#   Hash: abc123def456...
#
# Entry ID: 124
#   Last synced: 2024-11-23T15:00:00+00:00
#   Sync source: yaml
#   Machine: desktop
#   Hash: 789ghi012jkl...
```

**No Conflicts**:
```bash
# Output:
# ✅ No unresolved conflicts found
```

### Step 2: Review Conflicted Entry

**View Entry Details**:
```bash
# Show full entry
metadb show 123 --full

# Output:
# Entry: 2024-11-01
#   ID: 123
#   Mood: great
#   Rating: 4
#   People: Alice, Bob, Charlie
#   Tags: work, meeting
#   ...
```

**Check Git History**:
```bash
# View recent changes to entry
git log --follow -- journal/md/2024/2024-11-01.md

# View diff
git diff HEAD~1 HEAD -- journal/md/2024/2024-11-01.md
```

### Step 3: Verify Changes

**Questions to Ask**:
1. Do the current values look correct?
2. Did I intend to make these changes?
3. Is anything missing that I expected?
4. Are there any unexpected values?

**If Changes Look Good**:
- Proceed to Step 4 (mark resolved)

**If Changes Look Wrong**:
- Edit YAML file to correct values
- Re-sync: `plm sync-db --file journal/md/2024/2024-11-01.md`
- Commit and push corrected version

### Step 4: Mark Conflict Resolved

**Command**:
```bash
# Mark conflict as resolved
metadb sync resolve Entry 123

# Output:
# ✅ Marked conflict as resolved for Entry 123
```

**Effect**:
- Sets `conflict_resolved = True` in sync_states
- Removes from conflict list
- Next sync will update baseline hash

### Step 5: Verify Resolution

**Check Conflicts Again**:
```bash
metadb sync conflicts

# Output:
# ✅ No unresolved conflicts found
```

**Sync Entry Again**:
```bash
# Update sync state with new baseline
plm sync-db --file journal/md/2024/2024-11-01.md

# Output:
# Processing: journal/md/2024/2024-11-01.md
# Updated entry 2024-11-01
```

---

## Common Conflict Scenarios

### Scenario 1: Forgot to Pull Before Editing

**Timeline**:
```
Machine A:
  1. Edit entry
  2. Sync and push

Machine B (you):
  1. Edit SAME entry (forgot to pull!)
  2. Sync → Conflict detected (local edit)
  3. Pull → Git merge conflict in YAML
  4. Resolve Git conflict manually
  5. Sync merged file
  6. Mark conflict resolved
```

**Prevention**: Always `git pull` before starting work session.

### Scenario 2: Both Machines Add Different People

**Timeline**:
```
T0: Entry has people: [Alice, Bob]

Machine A:
  - Add Charlie → people: [Alice, Bob, Charlie]
  - Push

Machine B (before pulling):
  - Add Dave → people: [Alice, Bob, Dave]
  - Sync → Hash stored

Machine B (after pulling):
  - Git auto-merges → people: [Alice, Bob, Charlie, Dave] ✅
  - Sync → Conflict detected (hash mismatch)
  - Review → Looks good (all four people)
  - Mark resolved
```

**Resolution**: Git merge + manual verification.

### Scenario 3: One Machine Changes Multiple Fields

**Timeline**:
```
Machine A:
  - Change: mood: good → great
  - Change: rating: 4 → 5
  - Change: Add tag "productive"
  - Push

Machine B (before pulling):
  - Change: Add person "Dave"
  - Sync → Hash stored

Machine B (after pulling):
  - Git auto-merges:
    mood: great
    rating: 5
    tags: [..., productive]
    people: [..., Dave]
  - Sync → Conflict detected
  - Review → All changes preserved ✅
  - Mark resolved
```

**Resolution**: Git merge handled it correctly.

### Scenario 4: Conflicting Edits to Same Field

**Timeline**:
```
Machine A:
  - Change: mood: good → great
  - Push

Machine B (before pulling):
  - Change: mood: good → excellent
  - Sync → Hash stored

Machine B (after pulling):
  - Git merge conflict:
    <<<<<<< HEAD
    mood: excellent
    =======
    mood: great
    >>>>>>> origin/main
  - Manual resolution needed!
```

**Resolution**:
```bash
# Option 1: Keep your change
vim journal/md/2024/2024-11-01.md
# Choose: mood: excellent
git add journal/md/2024/2024-11-01.md
git commit -m "Merge: keep 'excellent' mood"

# Option 2: Accept incoming change
# Choose: mood: great

# Option 3: Choose different value
# Choose: mood: amazing

# Then sync and resolve
plm sync-db --file journal/md/2024/2024-11-01.md
metadb sync resolve Entry 123
git push
```

---

## Monitoring Conflict Health

### Daily Status Check

```bash
# Quick health check
metadb sync status

# Output:
# 📊 Sync Status Summary
# Total entities tracked: 1250
# Active conflicts: 0
# Last sync: 2024-11-23T16:00:00+00:00
```

### Weekly Conflict Review

```bash
# Detailed statistics
metadb sync stats

# Output:
# 📊 Sync State Statistics
#
# Total entities tracked: 1250
# Conflicts (unresolved): 0
# Conflicts (resolved): 12
#
# By entity type:
#   Entry: 1200
#   Event: 35
#   Person: 15
#
# By sync source:
#   yaml: 1200
#   wiki: 50
#
# By machine:
#   desktop: 600
#   laptop: 650
#
# Recent activity (last 7 days):
#   Syncs: 45
#   Conflicts detected: 2
#   Conflicts resolved: 2
```

### Conflict Trends

**Healthy Pattern**:
- ✅ Occasional conflicts (1-2 per week)
- ✅ All conflicts resolved within 24 hours
- ✅ No accumulation of unresolved conflicts

**Unhealthy Pattern**:
- ⚠️ Many conflicts (daily)
- ⚠️ Conflicts unresolved for days
- 🚨 Accumulating unresolved conflicts (5+)

**Action If Unhealthy**:
1. Review workflow (pulling before editing?)
2. Coordinate machine usage (avoid concurrent edits)
3. Investigate if same entries being edited repeatedly

---

## Best Practices for Avoiding Conflicts

### 1. Always Pull Before Editing

**Workflow**:
```bash
# START of work session
cd ~/Documents/palimpsest
git pull
plm sync-db --input journal/md/

# NOW safe to edit
vim journal/md/2024/2024-11-23.md
```

**Why**: Ensures you're working on latest version.

### 2. Sync Before Pushing

**Workflow**:
```bash
# AFTER editing
plm sync-db --input journal/md/

# Check for conflicts
metadb sync conflicts

# If no conflicts, push
git add .
git commit -m "Update journal entries"
git push
```

**Why**: Catches conflicts before pushing.

### 3. Use One Machine at a Time

**Strategy**:
- Work on laptop during day
- Work on desktop at night
- Don't edit on both simultaneously

**Why**: Minimizes concurrent edits.

### 4. Coordinate If Multi-User

**Current System**: Single-user multi-machine

**Future Multi-User**:
- Would need better conflict resolution
- Consider implementing three-way merge
- Add user attribution to changes

### 5. Resolve Conflicts Promptly

**Timeline**:
- Detect: Same day as sync
- Review: Within 24 hours
- Resolve: Within 48 hours

**Why**: Prevents accumulation and confusion.

### 6. Use Meaningful Commit Messages

**Good**:
```bash
git commit -m "Add notes from team meeting on 2024-11-23"
```

**Bad**:
```bash
git commit -m "update"
```

**Why**: Helps identify what changed during conflict review.

---

## Advanced Topics

### Conflict Resolution Without Git Merge

**Scenario**: You want to manually resolve without Git merge.

**Steps**:
```bash
# Pull (conflict detected in Git)
git pull

# Abort Git merge
git merge --abort

# Manually edit file to desired state
vim journal/md/2024/2024-11-01.md

# Sync with manual version
plm sync-db --file journal/md/2024/2024-11-01.md

# Mark conflict resolved
metadb sync resolve Entry 123

# Commit your manual resolution
git add journal/md/2024/2024-11-01.md
git commit -m "Manual conflict resolution for 2024-11-01"
git push
```

### Viewing Conflict History

**SQL Query**:
```sql
-- Show all conflicts (including resolved)
SELECT *
FROM sync_states
WHERE conflict_detected = 1
ORDER BY last_synced_at DESC;

-- Show only unresolved
SELECT *
FROM sync_states
WHERE conflict_detected = 1
  AND conflict_resolved = 0;
```

**CLI**:
```bash
# Show resolved conflicts
metadb sync conflicts --resolved

# Output:
# ✅ Resolved Conflicts (12)
# Entry ID: 120 (resolved 2024-11-20)
# Entry ID: 118 (resolved 2024-11-18)
# ...
```

### Resetting Sync State

**Use Case**: Sync state corrupted, want to re-establish baseline.

**WARNING**: This loses conflict detection history.

**SQL**:
```sql
-- Delete sync state for entry
DELETE FROM sync_states
WHERE entity_type = 'Entry' AND entity_id = 123;
```

**Effect**: Next sync creates fresh baseline (no conflict check).

### Bulk Conflict Resolution

**Scenario**: Many conflicts, all verified as correct.

**SQL**:
```sql
-- Mark all conflicts as resolved
UPDATE sync_states
SET conflict_resolved = 1
WHERE conflict_detected = 1
  AND conflict_resolved = 0;
```

**CLI Workaround**:
```bash
# List all unresolved conflicts
metadb sync conflicts

# Manually resolve each one
for id in 123 124 125; do
    metadb sync resolve Entry $id
done
```

**Future Enhancement**: Add `metadb sync resolve-all` command.

---

## Troubleshooting

### Problem: Conflict Not Detected

**Symptoms**: You know file changed, but no conflict logged.

**Diagnosis**:
```bash
# Check sync state exists
metadb sync status Entry 123

# Output should show:
# Entity: Entry 123
# Last synced: ...
# Hash: ...
```

**Causes**:
1. No baseline hash stored (first sync)
2. Sync state deleted
3. Hash computation failed

**Solution**:
```bash
# Re-sync to establish baseline
plm sync-db --file journal/md/2024/2024-11-01.md

# Verify hash stored
metadb sync status Entry 123
```

### Problem: False Positive Conflict

**Symptoms**: Conflict detected but you didn't edit file.

**Diagnosis**:
```bash
# Check if file actually changed
git diff journal/md/2024/2024-11-01.md

# Compare hashes
metadb sync status Entry 123
# Note hash value

# Recompute hash
# Recompute hash (for advanced debugging/development)
python -c "
from dev.utils import fs
from pathlib import Path
print(fs.get_file_hash(Path('journal/md/2024/2024-11-01.md')))
"
# Compare with stored hash
```

**Causes**:
1. File metadata changed (timestamp, permissions)
2. Whitespace changes
3. Line ending changes (CRLF vs LF)

**Solution**:
```bash
# If no actual changes, mark resolved
metadb sync resolve Entry 123

# Re-sync to update baseline
plm sync-db --file journal/md/2024/2024-11-01.md
```

### Problem: Conflict Resolved But Still Listed

**Symptoms**: Marked conflict as resolved, but still appears in conflict list.

**Diagnosis**:
```bash
# Check resolved status
sqlite3 data/palimpsest.db "
SELECT conflict_detected, conflict_resolved
FROM sync_states
WHERE entity_type = 'Entry' AND entity_id = 123;
"
```

**Expected**: `conflict_detected=1, conflict_resolved=1`

**Solution**:
```bash
# If still showing conflict_resolved=0, manually update
metadb sync resolve Entry 123

# Or SQL:
sqlite3 data/palimpsest.db "
UPDATE sync_states
SET conflict_resolved = 1
WHERE entity_type = 'Entry' AND entity_id = 123;
"
```

### Problem: Many Unresolved Conflicts Accumulating

**Symptoms**: Conflict list growing, hard to manage.

**Diagnosis**:
```bash
# Check conflict stats
metadb sync stats

# Identify pattern
metadb sync conflicts
```

**Causes**:
1. Not pulling before editing
2. Working on both machines simultaneously
3. Not resolving conflicts promptly

**Solution**:
```bash
# Review each conflict
for id in $(metadb sync conflicts | grep "ID:" | awk '{print $3}'); do
    echo "Reviewing Entry $id"
    metadb show $id --full
    read -p "Looks correct? (y/n) " yn
    if [ "$yn" = "y" ]; then
        metadb sync resolve Entry $id
    fi
done
```

---

## CLI Command Reference

### List Conflicts

```bash
# List unresolved conflicts (default)
metadb sync conflicts

# List resolved conflicts
metadb sync conflicts --resolved

# Show all conflicts
metadb sync conflicts --all
```

### Resolve Conflict

```bash
# Resolve specific entry
metadb sync resolve Entry 123

# Resolve specific event
metadb sync resolve Event 456
```

### View Sync State

```bash
# View sync state for entry
metadb sync status Entry 123

# Output:
# Entity: Entry 123
#   Last synced: 2024-11-23T16:00:00+00:00
#   Sync source: yaml
#   Sync hash: abc123def456...
#   Conflict detected: True
#   Conflict resolved: False
#   Machine: laptop
```

### Sync Statistics

```bash
# Overall statistics
metadb sync stats

# Filtered by entity type
metadb sync stats --type Entry

# Filtered by machine
metadb sync stats --machine laptop
```

---

## Future Enhancements

### 1. Three-Way Merge

**Current**: Last-write-wins
**Potential Enhancement**: Smart merging with baseline comparison

**Would Enable**:
- Auto-resolve non-conflicting fields
- Show only truly conflicting fields
- Better change preservation

### 2. Conflict Visualization

**Current**: Text-based CLI
**Future**: Visual diff tool

```bash
# Show side-by-side comparison
metadb sync diff Entry 123

# Output:
# ┌─────────────────┬─────────────────┬─────────────────┐
# │ Baseline        │ Database        │ File            │
# ├─────────────────┼─────────────────┼─────────────────┤
# │ mood: good      │ mood: great     │ mood: excellent │
# │ rating: 4       │ rating: 4       │ rating: 5       │
# └─────────────────┴─────────────────┴─────────────────┘
```

### 3. Auto-Resolution Policies

**Current**: Manual resolution required
**Future**: Configurable auto-resolution

```yaml
# config.yaml (future)
conflict_resolution:
  strategy: last_write_wins  # or three_way_merge
  auto_resolve:
    - non_conflicting_fields
    - append_lists  # e.g., merge people lists
```

### 4. Conflict Notifications

**Current**: User must check manually
**Future**: Notifications on conflict detection

```bash
# Email notification
# Slack notification
# Desktop notification
```

---

## Summary

**Key Takeaways**:

1. **Conflicts are normal** in multi-machine workflows
2. **Hash-based detection** catches concurrent edits
3. **Last-write-wins** is simple but may lose changes
4. **Manual review** is required for verification
5. **Best prevention** is pulling before editing

**Workflow**:
```bash
# Daily routine
git pull
plm sync-db --input journal/md/
metadb sync conflicts  # Check for conflicts
# ... edit files ...
plm sync-db --input journal/md/
metadb sync conflicts  # Check again
# If conflicts, review and resolve
git add . && git commit -m "..." && git push
```

**Remember**: Conflicts are detection, not failure. The system alerts you to concurrent edits so you can verify changes are correct.
