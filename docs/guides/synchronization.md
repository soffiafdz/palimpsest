# Synchronization Guide

Complete guide to Palimpsest's bidirectional synchronization system and multi-machine workflows.

---

## Navigation

- [Quick Start](#daily-workflow) - Get started with multi-machine sync (5 min)
- [Common Scenarios](#common-scenarios) - Real-world examples (10 min)
- [Understanding the Architecture](#understanding-the-architecture) - How it all works (20 min)
- [Conflict Detection](#conflict-detection-and-resolution) - Handling concurrent edits
- [Monitoring](#monitoring-sync-health) - Health checks and statistics
- [Troubleshooting](#troubleshooting) - Common issues and solutions

**Related Documentation:**
- [Conflict Resolution](conflict-resolution.md) - Deep dive into conflict handling
- [Command Reference](../reference/commands.md) - CLI commands
- [Getting Started](../getting-started.md) - New user onboarding

---

## Overview

Palimpsest supports reliable multi-machine synchronization using:

1. **Tombstones**: Track deletions across machines
2. **Hash-based conflict detection**: Identify concurrent edits
3. **Soft delete**: Mark entries as deleted instead of removing
4. **Three-layer bidirectional sync**: YAML ↔ SQL ↔ Wiki

### How It Works

```
Machine A                          Git Repository                    Machine B
---------                          --------------                    ---------
Edit YAML
  ↓
yaml2sql (creates tombstones)
  ↓
Commit & Push            →         Database & YAML files      →     Pull
                                                                     ↓
                                                              yaml2sql (respects tombstones)
                                                                     ↓
                                                              Changes applied
```

---

## Daily Workflow

### Starting Work Session

```bash
# 1. Pull latest changes from git
cd ~/Documents/palimpsest
git pull

# 2. Sync from YAML to database
plm sync-db

# 3. Check for conflicts (optional but recommended)
metadb sync conflicts
```

### Making Changes

```bash
# Edit journal entries as normal
vim journal/md/2024/2024-11-23.md

# Add/remove people, tags, events, etc.
# The system will track all changes
```

### Ending Work Session

```bash
# 1. Sync changes to database
plm sync-db

# 2. Commit changes to git
git add journal/md/
git add data/palimpsest.db  # Include database changes
git commit -m "Update journal entries"

# 3. Push to remote
git push
```

---

## Common Scenarios

### Scenario 1: Removing a Person from an Entry

This is the most common use case that tombstones handle.

**Machine A (Laptop)**:
```bash
# Edit entry YAML
vim journal/md/2024/2024-11-01.md

# Before:
# people: [Alice, Bob, Charlie]

# After (removed Bob):
# people: [Alice, Charlie]

# Sync to database
plm sync-db --file journal/md/2024/2024-11-01.md

# What happens:
# - Tombstone created for Bob
# - Bob removed from database
# - Sync state updated

# Commit and push
git add journal/md/2024/2024-11-01.md data/palimpsest.db
git commit -m "Remove Bob from 2024-11-01 entry"
git push
```

**Machine B (Desktop)**:
```bash
# Pull changes
git pull

# Sync from YAML
plm sync-db

# What happens:
# - Tombstone prevents Bob from being re-added
# - Bob correctly remains removed
# - Database matches Machine A
```

**Result**: ✅ Deletion propagated successfully across machines

---

### Scenario 2: Adding New Entries

**Machine A**:
```bash
# Create new entry
echo "---
date: 2024-11-25
people: [Alice]
---
New entry content" > journal/md/2024/2024-11-25.md

# Sync
plm sync-db --file journal/md/2024/2024-11-25.md

# Push
git add journal/md/2024/2024-11-25.md data/palimpsest.db
git commit -m "Add 2024-11-25 entry"
git push
```

**Machine B**:
```bash
# Pull
git pull

# Sync
plm sync-db

# Entry now exists on Machine B
```

**Result**: ✅ New entries sync seamlessly

---

### Scenario 3: Concurrent Edits (Conflict!)

This happens when both machines edit the same entry before syncing.

**Timeline**:
- T0: Both machines have same state
- T1: Machine A edits entry, syncs, pushes
- T2: Machine B edits **same entry** (before pulling)
- T3: Machine B pulls (conflict detected!)

**Machine A (Laptop) - T1**:
```bash
# Edit entry
vim journal/md/2024/2024-11-01.md
# Add person: people: [Alice, Bob, Charlie]

# Sync and push
plm sync-db --file journal/md/2024/2024-11-01.md
git add journal/md/2024/2024-11-01.md data/palimpsest.db
git commit -m "Add Charlie to 2024-11-01"
git push
```

**Machine B (Desktop) - T2** (before pulling):
```bash
# Edit SAME entry (unaware of Machine A's change)
vim journal/md/2024/2024-11-01.md
# Add different person: people: [Alice, Bob, Dave]

# Sync
plm sync-db --file journal/md/2024/2024-11-01.md
# Sync state: hash_b stored

# Commit
git add journal/md/2024/2024-11-01.md data/palimpsest.db
git commit -m "Add Dave to 2024-11-01"
```

**Machine B - T3** (pull from Machine A):
```bash
# Pull changes
git pull

# Git merge conflict in YAML file!
# Resolve YAML conflict manually (choose version or merge)
vim journal/md/2024/2024-11-01.md
# Result: people: [Alice, Bob, Charlie, Dave]  (merged both changes)

# Sync again
plm sync-db --file journal/md/2024/2024-11-01.md

# WARNING logged:
# "Conflict detected for entry 2024-11-01"
# (hash_b != hash_a from Machine A)

# Check conflicts
metadb sync conflicts
# Shows: Entry 2024-11-01 has unresolved conflict

# Verify merge looks good
metadb show 2024-11-01 --full

# Mark conflict as resolved
metadb sync resolve Entry 123

# Push merged version
git add journal/md/2024/2024-11-01.md data/palimpsest.db
git commit -m "Merge concurrent edits to 2024-11-01"
git push
```

**Result**: ⚠️ Conflict detected and resolved manually

---

### Scenario 4: Editing Wiki Notes

Wiki notes are synced separately from YAML metadata.

**Machine A**:
```bash
# Edit wiki entry
vim wiki/entries/2024/2024-11-01.md
# Add editorial notes

# Import from wiki
plm import-wiki

# Push
git add wiki/entries/2024/2024-11-01.md data/palimpsest.db
git commit -m "Add notes to wiki entry"
git push
```

**Machine B**:
```bash
# Pull
git pull

# Import from wiki
plm import-wiki

# Notes synced
```

**Result**: ✅ Wiki edits sync independently from YAML

---

## Understanding the Architecture

### Three-Layer Bidirectional Synchronization

Palimpsest implements three-layer sync between Journal files, SQL database, and Wiki pages:

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  Journal Files   │ ←────→  │   SQL Database   │ ←────→  │   Wiki Pages     │
│  (Markdown)      │         │   (SQLite)       │         │   (Vimwiki)      │
│                  │         │                  │         │                  │
│  YAML metadata   │         │  Normalized      │         │  Human-readable  │
│  Entry content   │         │  Relationships   │         │  Entity pages    │
└──────────────────┘         └──────────────────┘         └──────────────────┘
     Primary                      Central                     Navigation
   Source Material              Source of Truth             & Exploration
```

### Data Flow Principles

1. **Journal → Database**: Single source of truth for life events
   - Journal entries (Markdown with YAML frontmatter) are the primary record
   - Database is a derived, structured representation
   - Ensures human-readability and version control (Git)

2. **Database → Wiki**: Auto-generated navigation & exploration
   - Wiki is a browsable, interlinked interface
   - Auto-generated to reflect current database state
   - One-way generation prevents conflicting sources

3. **Wiki → Database**: Editable notes only (not structural data)
   - Wiki is workspace for editorial notes and annotations
   - Only specific "notes" fields sync back to database
   - Core structural metadata stays in Journal YAML

### Three Synchronization Paths

#### Path 1: YAML ↔ SQL (Journal Entries)

- **Purpose**: Capture and persist journal metadata
- **Direction**: Fully bidirectional
  - YAML → SQL: Daily journaling (primary flow)
  - SQL → YAML: Export/backup (reverse flow)
- **Use Cases**:
  - Write new entries in Markdown
  - Sync metadata to database
  - Export database back to Markdown for backup

**Example Flow**:
```bash
# Write journal entry with YAML frontmatter
vim journal/md/2024/2024-11-01.md

# Import to database (YAML → SQL)
plm sync-db --file journal/md/2024/2024-11-01.md

# Export back to Markdown (SQL → YAML)
plm export-db --date 2024-11-01 --output backup/
```

**What syncs**:
- Core fields (date, word_count, reading_time)
- Geographic fields (city, locations)
- People, events, tags
- References, poems
- Manuscript flags (status, edited)

#### Path 2: SQL → Wiki (Entity Export)

- **Purpose**: Generate navigable wiki for exploration
- **Direction**: One-way (SQL → Wiki)
- **Update Mode**: Regenerate from database

**Example Flow**:
```bash
# Export all entities to wiki
plm export-wiki all

# Export specific entity type
plm export-wiki people
plm export-wiki entries
```

**What gets exported**:
- Entity pages (entries, people, locations, cities, events, tags, etc.)
- Timeline views
- Statistics dashboards
- Manuscript subwiki (separate workspace)

**Design rationale**: Wiki always reflects database state, preventing conflicts.

#### Path 3: Wiki → SQL (Entity Import)

- **Purpose**: Sync user edits back to database
- **Direction**: One-way (Wiki → SQL)
- **Update Mode**: Import only editable fields

**Example Flow**:
```bash
# Edit notes in wiki
vim wiki/people/alice.md

# Import changes to database
plm import-wiki people
```

**What syncs**:
- Entry notes
- Person notes
- Event notes
- Manuscript-specific fields (character notes, adaptation notes, etc.)

**What does NOT sync** (structural data):
- Dates
- Relationships
- Names
- Core metadata

**Design rationale**: Limits wiki-to-database sync to designated editable fields, preserving database as structural authority.

### Complete Data Flow

```
    ┌─────────────────────────────────────────────────────────────┐
    │                  PALIMPSEST DATA FLOW                        │
    └─────────────────────────────────────────────────────────────┘

┌─────────────┐
│   Journal   │  Write new entry
│   (*.md)    │  with YAML metadata
└──────┬──────┘
       │
       │ yaml2sql (import)
       ↓
┌─────────────────────────────────────────────────────┐
│                   SQL Database                      │
│                                                     │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐            │
│  │ Entries  │  │ People  │  │ Events   │            │
│  └────┬─────┘  └────┬────┘  └────┬─────┘            │
│       │             │            │                  │
│       └─────────────┴────────────┘                  │
│              Relationships                          │
└───────────┬─────────────────────┬───────────────────┘
            │                     │
            │ sql2wiki            │
            │ (export)            │
            ↓                     ↓
┌─────────────────────┐  ┌─────────────────────┐
│   Main Wiki         │  │ Manuscript Subwiki  │
│   wiki/             │  │ wiki/manuscript     │
│  - entries/         │  │  - entries/         │
│  - people/          │  │  - characters/      │
│  - events/          │  │  - events/          │
│  - locations/       │  │  - arcs/            │
│  - cities/          │  │  - themes/          │
└──────┬──────────────┘  └──────┬──────────────┘
       │                        │
       │ wiki2sql               │
       │ (import notes)         │
       ↓                        ↓
┌─────────────────────────────────────────────────────┐
│         Database (Notes Updated)                    │
│  Entry.notes ← wiki edits                           │
│  Person.notes ← wiki edits                          │
│  ManuscriptEntry.notes ← manuscript wiki edits      │
└─────────────────────────────────────────────────────┘
```

### Field Ownership Strategy

**Database Fields** (never in wiki):
- Primary keys (`id`)
- Foreign keys (`entry_id`, `person_id`)
- Timestamps (`created_at`, `updated_at`)
- File metadata (`file_path`, `file_hash`)
- Computed properties (word count, relationships)

**Wiki-Editable Fields** (user can modify):
- `notes` - Editorial/manuscript planning notes
- `character_notes` - Character development
- `character_description` - Character descriptions
- `character_arc` - Character arc notes
- `voice_notes`, `appearance_notes` - Manuscript-specific

**YAML-Owned Fields** (structural):
- date, people, locations, cities, events, tags
- references, poems
- Manuscript flags (status, edited)

---

## Conflict Detection and Resolution

### Understanding Conflicts

A **conflict** occurs when:
1. File synced on Machine A (hash stored)
2. Same file modified on Machine B (different hash stored)
3. Machine B pulls and syncs again (hash mismatch detected)

### Conflict Detection

The system automatically detects conflicts by comparing file hashes:

```bash
# Check for conflicts
metadb sync conflicts

# Output:
# ⚠️  Unresolved Conflicts (1)
# Entry ID: 123
#   Last synced: 2024-11-23T14:30:00+00:00
#   Sync source: yaml
#   Machine: laptop
#   Hash: abc123...
```

### Resolution Process

1. **Automatic resolution**: System uses "last-write-wins" (YAML overwrites database)
2. **Detection**: Conflict logged for user review
3. **Manual review**: User examines changes
4. **Mark resolved**: Clear from conflict list

```bash
# Step 1: List conflicts
metadb sync conflicts

# Step 2: View entry details
metadb show 123 --full

# Step 3: If changes look correct, mark as resolved
metadb sync resolve Entry 123

# Step 4: Verify
metadb sync conflicts
# Should show: No unresolved conflicts found
```

### When to Worry About Conflicts

- ✅ **Normal**: Occasional conflicts (1-2 per month)
- ⚠️ **Attention needed**: Frequent conflicts (multiple per week)
- 🚨 **Problem**: Many unresolved conflicts accumulating

### Preventing Conflicts

**Best Practices**:
1. **Always pull before editing**: `git pull` at start of session
2. **Sync before pushing**: Ensure database updated
3. **Don't edit on both machines simultaneously**
4. **Review conflicts promptly**: Don't let them accumulate
5. **Use meaningful commit messages**: Helps identify changes

---

## Monitoring Sync Health

### Daily Health Check

```bash
# Quick status
metadb sync status

# Output:
# 📊 Sync Status Summary
# Total entities tracked: 1250
# Active conflicts: 0
```

### Weekly Statistics

```bash
# Detailed stats
metadb sync stats

# Output:
# 📊 Sync State Statistics
# Total entities tracked: 1250
# Conflicts (unresolved): 0
# Conflicts (resolved): 5
#
# By entity type:
#   Entry: 1200
#   Event: 35
#
# By sync source:
#   yaml: 1200
#   wiki: 50
#
# By machine:
#   desktop: 600
#   laptop: 650
```

### Tombstone Monitoring

```bash
# View recent tombstones
metadb tombstone list --limit 20

# Statistics
metadb tombstone stats

# Output:
# 📊 Tombstone Statistics
# Total tombstones: 45
# Expired tombstones: 5
#
# By table:
#   entry_people: 35
#   entry_tags: 10
```

---

## Maintenance

### Monthly Cleanup

Remove expired tombstones (default: 90-day expiration):

```bash
# Preview what would be deleted
metadb tombstone cleanup --dry-run

# Output:
# 🔍 Dry run: Would delete 5 expired tombstones

# Actually delete
metadb tombstone cleanup

# Output:
# ✅ Cleaned up 5 expired tombstones
```

**Cron Job** (optional):
```cron
# Run on first day of month at 2am
0 2 1 * * cd ~/Documents/palimpsest && metadb tombstone cleanup
```

### Backup Strategy

Since the database is in git, you have automatic backups. But consider:

```bash
# Full data backup (monthly)
plm backup-full --suffix monthly

# List backups
plm backup-list-full
```

---

## Troubleshooting

### Problem: Person keeps reappearing after deletion

**Symptoms**: You remove "Bob" from an entry, push to git, but on another machine Bob is still there.

**Diagnosis**:
```bash
# Check if tombstone exists
metadb tombstone list --table entry_people | grep "Bob"

# Check sync state
metadb sync status Entry 123
```

**Solution**:
1. Tombstone missing → Re-sync on original machine
2. Sync state outdated → Pull and sync again
3. Git not pushed → Push database changes

### Problem: Many unresolved conflicts

**Symptoms**: `metadb sync conflicts` shows many entries.

**Diagnosis**:
```bash
# List all conflicts
metadb sync conflicts

# Check by machine
metadb sync stats
```

**Solution**:
1. Review each conflict individually
2. Verify database state matches desired state
3. Mark all as resolved: `metadb sync resolve Entry <ID>`
4. Investigate why conflicts are frequent

### Problem: Sync state shows conflict but file looks correct

**Symptoms**: Conflict detected but you reviewed and changes are fine.

**Solution**:
```bash
# Just mark as resolved
metadb sync resolve Entry 123

# Next sync will update baseline hash
plm sync-db --file journal/md/2024/2024-11-23.md
```

### Problem: Wiki import doesn't update other fields

**This is correct behavior!** Wiki import only updates `notes` fields. All other metadata must be edited in the database or journal YAML.

**Fields that wiki import updates**:
- Main wiki: `notes` only
- Manuscript wiki: `notes`, `character_notes`, `character_description`, etc.

**To edit structural data**: Edit journal YAML and re-import:
```bash
# Edit journal file's YAML frontmatter
vim journal/md/2024/2024-11-01.md

# Re-import to database
plm sync-db --file journal/md/2024/2024-11-01.md
```

---

## Advanced Topics

### Understanding Last-Write-Wins

The current implementation uses **last-write-wins** for conflict resolution:
- When conflict detected, YAML file overwrites database
- Most recent sync wins
- Simple but effective for single-user multi-machine workflow

**Limitation**: Concurrent edits on both machines may lose changes from one machine.

**Workaround**: Coordinate edits or manually merge YAML files before syncing.

### Tombstone Expiration

Tombstones have a TTL (time-to-live) of **90 days** by default:
- After 90 days, tombstone expires
- Cleanup command removes expired tombstones
- After removal, association can be re-added

### Sync Sources

The system tracks two sync sources separately:
- **yaml**: From YAML frontmatter (primary metadata)
- **wiki**: From wiki files (editorial notes)

Each has independent sync state and conflict detection.

---

## Best Practices Summary

### Do's ✅
- Pull before editing
- Sync to database after editing
- Push database changes with YAML changes
- Review conflicts promptly
- Run monthly cleanup
- Monitor sync stats weekly
- Use wiki for editorial notes
- Use YAML for structural changes

### Don'ts ❌
- Don't edit on multiple machines simultaneously
- Don't skip pulling before editing
- Don't ignore conflict warnings
- Don't manually edit database without syncing
- Don't remove tombstones unless you understand implications
- Don't edit structural data in wiki (use YAML)

---

## Quick Reference

### Daily Workflow Commands

```bash
# Start session
git pull
plm sync-db

# ... make edits ...

# End session
plm sync-db
git add . && git commit -m "Update journal"
git push
```

### Conflict Management

```bash
metadb sync conflicts              # List conflicts
metadb sync resolve Entry 123      # Resolve conflict
metadb sync stats                  # View statistics
```

### Tombstone Management

```bash
metadb tombstone list              # View tombstones
metadb tombstone stats             # View statistics
metadb tombstone cleanup --dry-run # Preview cleanup
metadb tombstone cleanup           # Clean expired
```

### Wiki Sync

```bash
# Export to wiki
plm export-wiki all
plm export-wiki people

# Import from wiki
plm import-wiki all
plm import-wiki people
```

---

## Summary

The Palimpsest synchronization system provides:
- ✅ Three-layer bidirectional sync (YAML ↔ SQL ↔ Wiki)
- ✅ Reliable deletion propagation via tombstones
- ✅ Conflict detection via hash comparison
- ✅ Soft delete with restore capability
- ✅ Field ownership separation (YAML/Database/Wiki)
- ✅ Full CLI for monitoring and management

By following this guide and best practices, you can work seamlessly across multiple machines while maintaining data consistency.

Happy journaling! 📔
