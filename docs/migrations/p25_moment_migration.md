# P25 Migration: MentionedDate to Moment

## Overview

This migration renames the `MentionedDate` model to `Moment` throughout the codebase and database schema. This is a semantic improvement that better represents "a point in time referenced in journal entries."

## What Changed

### Model Rename
- `MentionedDate` class → `Moment` class

### Database Tables
| Old Name | New Name |
|----------|----------|
| `dates` | `moments` |
| `entry_dates` | `entry_moments` |
| `people_dates` | `moment_people` |
| `location_dates` | `moment_locations` |

### New Table
- `moment_events`: Links moments to events (M2M relationship)

### Column Renames
- `date_id` → `moment_id` in all association tables

## User Actions Required

### 1. Update Your Code

If you have custom code that imports or uses `MentionedDate`, update it:

```python
# Before
from dev.database.models import MentionedDate
mentioned_date = MentionedDate(date=date(2024, 1, 15))

# After
from dev.database.models import Moment
moment = Moment(date=date(2024, 1, 15))
```

### 2. Apply the Database Migration

```bash
# From the project root
cd dev
alembic upgrade head
```

The migration will:
- Rename tables (preserving all data)
- Rename columns in association tables
- Create the new `moment_events` table

### 3. No YAML Changes Required

The YAML frontmatter format remains unchanged. The `dates:` field in your markdown files will continue to work - only the internal database schema has changed.

```yaml
---
dates:
  - date: 2024-01-15
    context: "Met with Alice"
    people:
      - Alice
---
```

## Manager API Changes

### Old API (DateManager)
```python
db.dates.get(date(2024, 1, 15))
db.dates.create({"date": "2024-01-15"})
```

### New API (MomentManager)
```python
db.moments.get(date(2024, 1, 15))
db.moments.create({"date": "2024-01-15"})
```

## Rollback

If you need to rollback this migration:

```bash
cd dev
alembic downgrade b8e4f0c2a3d5
```

This will revert the schema to the previous state with `dates` tables.

## Technical Notes

- The migration uses SQLite's `ALTER TABLE ... RENAME TO` for table renames
- Column renames use Alembic's `batch_alter_table` for SQLite compatibility
- All data is preserved during the migration
- The migration is idempotent (safe to run multiple times)
