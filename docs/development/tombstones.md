# Tombstone Pattern Technical Guide

## Overview

This document provides technical details about the **tombstone pattern** implementation in Palimpsest for tracking deletions in many-to-many relationships.

**Audience**: Developers and advanced users who want to understand the internals of the deletion tracking system.

**Related Documents**:
- User guide: `../../user-guides/multi-machine-sync.md`
- Conflict resolution: `conflict-resolution.md`
- Migration guide: `migration-guide.md`

---

## What Are Tombstones?

A **tombstone** is a database record that marks when an association between two entities has been deleted.

### The Problem Tombstones Solve

In a multi-machine synchronization scenario, accurately propagating deletions is a complex challenge. Consider this timeline without tombstones:

**Without Tombstones**:
```
T0: Machine A - Entry has people: [Alice, Bob] (Both machines are in sync)
T1: Machine A - User removes Bob from the entry's YAML file → people: [Alice]
T2: Machine A - Pushes its changes (updated YAML and DB) to the central Git repository.
T3: Machine B - Pulls changes from Git (gets the updated YAML with Bob removed).
T4: Machine B - Performs a sync from its local YAML files to its database → Sees people: [Alice] in the YAML.
                                   → At this point, Machine B's database *still* has Bob associated with the entry (from T0).
                                   → The critical question arises: Should Machine B's sync logic re-add Bob to the database because the YAML no longer explicitly states his removal? 🤔
```

**The Ambiguity of Deletions**: When Machine B syncs and sees `people: [Alice]` in the YAML, it faces a fundamental ambiguity:
- Option 1: **Overwrite** its database state entirely based on the incoming YAML. If it does this, and another machine (or a wiki sync) had added "Bob" independently to Machine B's database *without* it being in the YAML, that change would be lost.
- Option 2: **Merge** its current database state with the incoming YAML. This would mean keeping "Bob" in the database, effectively ignoring Machine A's deletion. This leads to deletion propagation failure and inconsistent data.

**Neither naive option is correct** because they fail to capture the *intent* of a deletion. We need a mechanism to distinguish between:
- "Bob was never associated with this entry" (Machine A never had Bob, so don't add him).
- "Bob was explicitly removed from this entry" (Machine A intentionally removed Bob, so ensure he stays removed).
- "Bob was added elsewhere" (another system added Bob, so keep him if no explicit deletion signal is present).

**Solution**: Tombstones explicitly record "Bob was associated with this entry, but has been deliberately removed." This provides the necessary historical context to correctly interpret changes in distributed systems.

### With Tombstones

```
T0: Machine A - Entry has people: [Alice, Bob]
T1: Machine A - User removes Bob
                → people: [Alice]
                → CREATE TOMBSTONE(entry_id=123, person_id=456, table='entry_people')
T2: Machine A - Push to git (YAML + database)
T3: Machine B - Pull from git
T4: Machine B - Sync from YAML
                → Sees people: [Alice]
                → Checks tombstone table
                → Tombstone exists for Bob
                → Does NOT re-add Bob ✅
```

---

## Database Schema

### AssociationTombstone Table

**File**: `dev/database/models.py`

```python
class AssociationTombstone(Base):
    """Tombstone records for deleted many-to-many associations."""
    __tablename__ = "association_tombstones"

    __table_args__ = (
        UniqueConstraint('table_name', 'left_id', 'right_id',
                         name='uq_tombstone_association'),
    )

    # Primary key
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Association identifier
    table_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    left_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    right_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Deletion metadata
    removed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),
                                                  nullable=False, index=True)
    removed_by: Mapped[Optional[str]] = mapped_column(String(255))
    removal_reason: Mapped[Optional[str]] = mapped_column(Text)

    # Synchronization tracking
    sync_source: Mapped[str] = mapped_column(String(50), nullable=False)

    # Time-to-live
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True),
                                                            nullable=True, index=True)
```

### Fields Explained

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `id` | Integer | Primary key | 123 |
| `table_name` | String(100) | Which association table | "entry_people" |
| `left_id` | Integer | Entry ID (left side) | 456 (entry) |
| `right_id` | Integer | Associated entity ID | 789 (person) |
| `removed_at` | DateTime (UTC) | When removed | 2024-11-23T14:30:00+00:00 |
| `removed_by` | String(255) | Who removed it | "yaml2sql" |
| `removal_reason` | Text | Why removed | "removed_from_source" |
| `sync_source` | String(50) | Source of sync | "yaml" or "wiki" |
| `expires_at` | DateTime (UTC) | When tombstone expires | 2025-02-21T14:30:00+00:00 |

### Indexes

**Performance optimization for lookups**:

1. `idx_tombstones_table_name` - Filter by association table
2. `idx_tombstones_left_id` - Filter by entry
3. `idx_tombstones_right_id` - Filter by associated entity
4. `idx_tombstones_removed_at` - Sort by deletion time
5. `idx_tombstones_expires_at` - Cleanup expired tombstones
6. `uq_tombstone_association` - Unique constraint prevents duplicates

### Which Tables Use Tombstones?

Tombstones track deletions in these many-to-many association tables:

| Association Table | Left Entity | Right Entity | Tombstone Example |
|-------------------|-------------|--------------|-------------------|
| `entry_people` | Entry | Person | Remove "Alice" from 2024-11-01 |
| `entry_tags` | Entry | Tag | Remove "work" tag from entry |
| `entry_events` | Entry | Event | Remove "Conference" from entry |
| `entry_cities` | Entry | City | Remove "Toronto" from entry |

---

## Tombstone Lifecycle

### 1. Creation

**When**: Association removed from entry (e.g., person removed from YAML)

**Where**: `dev/database/managers/entry_manager.py:update_relationships()`

**Code**:
```python
def update_relationships(
    self,
    entry: Entry,
    metadata: Dict[str, Any],
    incremental: bool = True,
    sync_source: str = "manual",
    removed_by: str = "system",
) -> None:
    """Update relationships with tombstone support."""

    # Process people
    people = metadata.get("people", [])
    current_people = {p.name for p in entry.people}
    new_people = set(people) if people else set()

    # Calculate removals
    remove_people = current_people - new_people

    # Remove people and create tombstones
    for person_name in remove_people:
        person = next(p for p in entry.people if p.name == person_name)

        # CREATE TOMBSTONE FIRST
        self.tombstones.create(
            table_name="entry_people",
            left_id=entry.id,
            right_id=person.id,
            removed_by=removed_by,
            sync_source=sync_source,
            reason="removed_from_source",
            ttl_days=90,  # Expire in 90 days
        )

        # THEN REMOVE
        entry.people.remove(person)
```

**Manager Method**: `TombstoneManager.create()`

```python
def create(
    self,
    table_name: str,
    left_id: int,
    right_id: int,
    removed_by: str,
    sync_source: str,
    reason: Optional[str] = None,
    ttl_days: Optional[int] = 90,
) -> AssociationTombstone:
    """Create tombstone (idempotent)."""

    # Check for existing tombstone
    existing = self.session.query(AssociationTombstone).filter_by(
        table_name=table_name,
        left_id=left_id,
        right_id=right_id,
    ).first()

    if existing:
        self.logger.log_debug(
            "Tombstone already exists",
            {"table": table_name, "left_id": left_id, "right_id": right_id}
        )
        return existing  # Idempotent!

    # Create new tombstone
    expires_at = None
    if ttl_days is not None:
        expires_at = datetime.now(timezone.utc) + timedelta(days=ttl_days)

    tombstone = AssociationTombstone(
        table_name=table_name,
        left_id=left_id,
        right_id=right_id,
        removed_by=removed_by,
        removal_reason=reason,
        sync_source=sync_source,
        removed_at=datetime.now(timezone.utc),
        expires_at=expires_at,
    )

    self.session.add(tombstone)
    self.session.flush()

    self.logger.log_info(
        "Created association tombstone",
        {"table": table_name, "left_id": left_id, "right_id": right_id}
    )

    return tombstone
```

**Key Properties**:
- **Idempotent**: Calling `create()` multiple times returns existing tombstone
- **Timestamped**: Records exact time of removal
- **Traceable**: Records who removed it and why
- **Expirable**: Optional TTL (default 90 days)

### 2. Checking

**When**: Before adding association (e.g., person found in YAML)

**Where**: `dev/database/managers/entry_manager.py:update_relationships()`

**Code**:
```python
# Add new people
for person_name in add_people:
    person = self._resolve_or_create(person_name, Person)

    if person and person not in entry.people:
        # CHECK TOMBSTONE BEFORE ADDING
        tombstone_exists = self.tombstones.exists(
            table_name="entry_people",
            left_id=entry.id,
            right_id=person.id,
        )

        if tombstone_exists:
            # Tombstone exists - skip re-adding
            self.logger.log_debug(
                f"Skipping re-add of {person_name} - tombstone exists",
                {"entry": entry.date, "person": person_name}
            )
            continue  # DO NOT ADD

        # No tombstone - safe to add
        entry.people.append(person)
```

**Manager Method**: `TombstoneManager.exists()`

```python
def exists(self, table_name: str, left_id: int, right_id: int) -> bool:
    """Check if tombstone exists for association."""

    tombstone = self.session.query(AssociationTombstone).filter_by(
        table_name=table_name,
        left_id=left_id,
        right_id=right_id,
    ).first()

    return tombstone is not None
```

**Performance**: O(1) lookup using unique constraint index

### 3. Removal (Explicit Re-add)

**When**: User explicitly re-adds previously removed association

**Where**: `dev/database/managers/entry_manager.py:update_relationships()`

**Code**:
```python
# User explicitly re-adds "Bob" to entry
# YAML now has: people: [Alice, Bob]

# Before adding Bob back
if person not in entry.people:
    # Remove tombstone if it exists
    tombstone_removed = self.tombstones.remove_tombstone(
        table_name="entry_people",
        left_id=entry.id,
        right_id=person.id,
    )

    if tombstone_removed:
        self.logger.log_info(
            f"Removed tombstone for {person_name} (explicit re-add)",
            {"entry": entry.date, "person": person_name}
        )

    # Now safe to add
    entry.people.append(person)
```

**Manager Method**: `TombstoneManager.remove_tombstone()`

```python
def remove_tombstone(
    self,
    table_name: str,
    left_id: int,
    right_id: int,
) -> bool:
    """Remove tombstone (when association explicitly re-added)."""

    tombstone = self.session.query(AssociationTombstone).filter_by(
        table_name=table_name,
        left_id=left_id,
        right_id=right_id,
    ).first()

    if tombstone:
        self.session.delete(tombstone)
        self.session.flush()

        self.logger.log_info(
            "Removed tombstone",
            {"table": table_name, "left_id": left_id, "right_id": right_id}
        )
        return True

    return False
```

**Rationale**: If user explicitly re-adds an association, they've changed their mind about the deletion.

### 4. Expiration

**When**: After TTL expires (default: 90 days)

**Why**: Old tombstones can be safely removed:
- After 90 days, unlikely to matter if association re-added
- Prevents unbounded table growth
- Reduces storage and query overhead

**Expiration Logic**:
```python
# When tombstone created with ttl_days=90:
expires_at = datetime.now(timezone.utc) + timedelta(days=90)

# 90 days later, cleanup can remove it
```

**Manual Cleanup**: `metadb tombstone cleanup`

### 5. Cleanup

**When**: Monthly maintenance (or on-demand)

**Where**: `TombstoneManager.cleanup_expired()`

**Code**:
```python
def cleanup_expired(self, dry_run: bool = False) -> int:
    """Remove expired tombstones."""

    now = datetime.now(timezone.utc)

    # Find expired tombstones
    query = self.session.query(AssociationTombstone).filter(
        AssociationTombstone.expires_at.isnot(None),
        AssociationTombstone.expires_at <= now,
    )

    count = query.count()

    if dry_run:
        self.logger.log_info(
            f"Dry run: Would delete {count} expired tombstones"
        )
        return count

    # Actually delete
    query.delete(synchronize_session=False)
    self.session.flush()

    self.logger.log_info(
        f"Cleaned up {count} expired tombstones"
    )

    return count
```

**CLI Usage**:
```bash
# Preview what would be deleted
metadb tombstone cleanup --dry-run

# Actually delete expired tombstones
metadb tombstone cleanup
```

---

## Sync Source Tracking

Tombstones track which sync source created them to handle parallel sync paths.

### Sync Sources

| Source | Meaning | Created By |
|--------|---------|------------|
| `yaml` | YAML frontmatter | `yaml2sql` pipeline |
| `wiki` | Wiki markdown | `wiki2sql` pipeline |
| `manual` | Direct database edit | User via CLI |

### Why Track Sync Source?

Tracking the `sync_source` is critical because Palimpsest is designed with **multiple, independent data synchronization paths**, each potentially modifying different aspects of the same underlying data.

Palimpsest's primary sync paths are:
1. **YAML → SQL**: This path processes structured metadata from daily journal Markdown files (e.g., people, events, tags, dates, manuscript status). Changes here are typically structural or data-driven.
2. **Wiki → SQL**: This path imports editorial notes and specific manuscript-related fields from human-curated wiki pages. Changes here are typically qualitative, annotation-based, and limited to specific editable fields.

While these paths often modify distinct sets of fields, there can be overlaps or interdependencies. For example, a person might be removed via a YAML edit, but then referenced in a wiki note that is subsequently imported. Without `sync_source` information, a tombstone created by the YAML path might not be respected by the Wiki path, leading to inconsistencies.

**Implications of `sync_source`**:
- **Cross-Source Deletion Enforcement**: A tombstone created by one sync source (e.g., YAML) needs to be respected by *all* other sync sources (e.g., Wiki) that might attempt to re-introduce the deleted association. This ensures that a deliberate deletion, regardless of its origin, is universally enforced.
- **Auditing and Debugging**: Knowing the source of a deletion or a conflict can be invaluable for understanding data provenance and debugging complex synchronization issues.
- **Future Flexibility**: As new data ingestion or modification pathways are introduced, the `sync_source` mechanism provides a robust way to integrate them into the existing tombstone logic.

**Example**:
```
Machine A:
  - YAML removes person "Bob" from entry.
  - A tombstone is created with `sync_source="yaml"`.

Machine B:
  - Updates an editorial note in a wiki page that happens to reference "Bob".
  - Syncs via the `wiki2sql` path (`sync_source="wiki"`).
  - The `yaml` tombstone for Bob *still applies*, preventing the wiki import from inadvertently re-associating Bob with the entry (unless explicitly overridden).
```
Tombstones are therefore **cross-source enforced**, ensuring that a deletion signal from any authoritative source is respected throughout the system.

---

## TTL (Time-to-Live) Policy

### Default TTL: 90 Days

**Rationale**: The 90-day default TTL strikes a balance between preventing indefinite database growth and accommodating typical user workflows.
- **Prevents unbounded growth**: Ensures that deleted association records are eventually pruned from the database, maintaining performance and reducing storage footprint.
- **Covers typical sync delays**: A 90-day window is generally sufficient to account for periods of inactivity on a secondary machine (e.g., a laptop used less frequently, or during a vacation), ensuring deletions are propagated correctly even if a machine goes offline for an extended period.
- **Offers flexibility**: While default, the `ttl_days` parameter can be adjusted during tombstone creation for specific needs, or overridden to `None` for permanent deletions.

### Permanent Tombstones

Some tombstones never expire (`expires_at = NULL`):

**When to use**:
- Important deletions (e.g., removing incorrect person)
- Deletions with compliance reasons
- User explicitly requests permanent tombstone

**How to create**:
```python
# Pass ttl_days=None for permanent tombstone
self.tombstones.create(
    table_name="entry_people",
    left_id=entry.id,
    right_id=person.id,
    removed_by="user",
    sync_source="yaml",
    reason="incorrect_association",
    ttl_days=None,  # Permanent!
)
```

**Current Implementation**: All tombstones have 90-day TTL (no permanent tombstones created automatically).

### Adjusting TTL

**Not currently user-configurable** (hardcoded in code).

**Future Enhancement**: Could add configuration:
```yaml
# config.yaml (future)
tombstone:
  default_ttl_days: 90
  permanent_for:
    - incorrect_association
    - privacy_request
```

---

## Managing Tombstones

### CLI Commands

All tombstone management happens via `metadb tombstone` command group.

#### List Tombstones

```bash
# List all tombstones (limited to 100)
metadb tombstone list

# Filter by table
metadb tombstone list --table entry_people

# Increase limit
metadb tombstone list --limit 500
```

**Output**:
```
📋 Association Tombstones (3)

Table: entry_people
  Left ID: 123
  Right ID: 456
  Removed: 2024-11-23T14:30:00+00:00
  Removed by: yaml2sql
  Reason: removed_from_source
  Sync source: yaml
  Expires: 2025-02-21T14:30:00+00:00

Table: entry_tags
  Left ID: 124
  Right ID: 789
  ...
```

#### View Statistics

```bash
metadb tombstone stats
```

**Output**:
```
📊 Tombstone Statistics

Total tombstones: 45
Expired tombstones: 5

By table:
  entry_people: 35
  entry_tags: 8
  entry_events: 2

By sync source:
  yaml: 40
  wiki: 5

By removed_by:
  yaml2sql: 42
  wiki2sql: 3
```

#### Cleanup Expired

```bash
# Preview (dry run)
metadb tombstone cleanup --dry-run

# Output:
# 🔍 Dry run: Would delete 5 expired tombstones

# Actually delete
metadb tombstone cleanup

# Output:
# ✅ Cleaned up 5 expired tombstones
```

#### Remove Specific Tombstone

```bash
# Remove tombstone by table and IDs
metadb tombstone remove entry_people 123 456

# Output:
# ✅ Removed tombstone for entry_people (123, 456)
```

**Use Case**: When you want to allow re-adding before expiration.

### Programmatic Access

**Python API**:

```python
from dev.database import PalimpsestDB
from dev.database.tombstone_manager import TombstoneManager

db = PalimpsestDB("data/palimpsest.db")

with db.session_scope() as session:
    tombstone_mgr = TombstoneManager(session, db.logger)

    # Create tombstone
    tombstone_mgr.create(
        table_name="entry_people",
        left_id=123,
        right_id=456,
        removed_by="script",
        sync_source="yaml",
        reason="data_cleanup",
        ttl_days=90,
    )

    # Check if exists
    exists = tombstone_mgr.exists("entry_people", 123, 456)

    # Get tombstone
    tombstone = tombstone_mgr.get("entry_people", 123, 456)

    # List all
    tombstones = tombstone_mgr.list_all(table_name="entry_people", limit=100)

    # Statistics
    stats = tombstone_mgr.get_statistics()

    # Cleanup
    count = tombstone_mgr.cleanup_expired(dry_run=False)
```

---

## Implementation Details

### Idempotency

**All tombstone operations are idempotent**:

```python
# Calling create() multiple times is safe
tombstone1 = mgr.create("entry_people", 123, 456, "user", "yaml")
tombstone2 = mgr.create("entry_people", 123, 456, "user", "yaml")

# Returns same tombstone
assert tombstone1.id == tombstone2.id
```

**Why**: Multi-machine sync may attempt to create same tombstone on different machines.

### Unique Constraint

**Database enforces uniqueness**:

```python
__table_args__ = (
    UniqueConstraint('table_name', 'left_id', 'right_id',
                     name='uq_tombstone_association'),
)
```

**Prevents**:
- Duplicate tombstones for same association
- Race conditions in multi-machine sync

**Behavior**: Attempting to insert duplicate raises `IntegrityError` (caught and handled by `create()`).

### Transaction Safety

All tombstone operations use SQLAlchemy sessions:

```python
with db.session_scope() as session:
    tombstone_mgr = TombstoneManager(session, logger)

    # Create tombstone
    tombstone_mgr.create(...)

    # Remove association
    entry.people.remove(person)

    # Both commit together or rollback together
```

**Guarantee**: Tombstone and association removal are atomic.

### Performance

**Typical Operations**:

| Operation | Complexity | Performance |
|-----------|------------|-------------|
| `create()` | O(1) | ~1ms (index lookup + insert) |
| `exists()` | O(1) | ~0.5ms (index lookup) |
| `get()` | O(1) | ~0.5ms (index lookup) |
| `remove_tombstone()` | O(1) | ~1ms (index lookup + delete) |
| `list_all()` | O(n) | ~10ms for 1000 tombstones |
| `cleanup_expired()` | O(n) | ~50ms for 1000 expired |

**Index Usage**: All lookups use indexes (table_name, left_id, right_id).

**Storage**: ~100 bytes per tombstone (negligible).

---

## Edge Cases and Considerations

### 1. Concurrent Removal on Multiple Machines

**Scenario**: Both machines remove same person at same time.

**Timeline**:
```
T0: Both machines have: Entry 123 → Person 456
T1: Machine A removes Person 456 (creates tombstone)
T2: Machine B removes Person 456 (creates tombstone)
T3: Both push to git
T4: Git merge (database conflict!)
```

**Resolution**:
- Git merges database file
- Whichever tombstone was created first wins
- Idempotency ensures no duplicate tombstones

**Result**: ✅ Works correctly (one tombstone exists)

### 2. Remove Then Re-add on Same Machine

**Scenario**: User removes person, syncs, then immediately re-adds.

**Steps**:
```
1. Remove Bob → Tombstone created
2. Re-add Bob → Tombstone removed, association added
3. Sync again → No tombstone, association exists
```

**Result**: ✅ Works correctly (tombstone lifecycle handles this)

### 3. Remove on Machine A, Add New on Machine B

**Scenario**: Machine A removes "Bob Smith", Machine B adds "Bob Smith" (new person).

**Timeline**:
```
T0: Machine A - Entry has Person#456 (Bob Smith)
T1: Machine A - Remove Person#456 → Tombstone(left=123, right=456)
T2: Machine B - Add NEW Person#789 (Bob Smith) → No tombstone check (different ID!)
T3: Merge → Entry has Person#789 (Bob Smith)
           → Tombstone still exists for Person#456
```

**Result**: ✅ Works correctly (tombstones track IDs, not names)

### 4. Tombstone Expires, Then Sync

**Scenario**: Tombstone expires, then Machine B syncs old YAML.

**Timeline**:
```
T0: Tombstone created for Person#456
T90: Tombstone expires (cleanup removes it)
T91: Machine B syncs with old YAML (has Person#456)
     → No tombstone → Person re-added!
```

**Risk**: ⚠️ Deletion lost after 90 days

**Mitigation**: 90 days is long enough for typical sync cycles. If needed, use permanent tombstones.

### 5. Database Corruption or Manual Deletion

**Scenario**: User manually deletes tombstone from database.

**Risk**: Association may be re-added during sync.

**Prevention**: Don't manually modify database. Use CLI commands.

**Recovery**: If tombstone accidentally deleted, re-remove the association to recreate tombstone.

---

## Relationship to Other Components

### Soft Delete (Entry)

**Different Purpose**:
- **Soft Delete**: Marks entire entry as deleted (entry.deleted_at)
- **Tombstones**: Track deletion of associations within entry

**Example**:
```python
# Soft delete entry
entry.soft_delete(deleted_by="user", reason="duplicate")
# Entry still in database, but marked deleted

# Tombstone for association
tombstone_mgr.create("entry_people", entry_id, person_id, ...)
# Association removed, tombstone tracks deletion
```

**Can coexist**: A soft-deleted entry can still have tombstones.

### Sync State

**Different Purpose**:
- **Sync State**: Tracks when entity was last synced, detects conflicts
- **Tombstones**: Track deletion of associations

**Example**:
```python
# Update sync state (for entry)
sync_mgr.update_or_create("Entry", entry_id, ...)

# Create tombstone (for association within entry)
tombstone_mgr.create("entry_people", entry_id, person_id, ...)
```

**Used together**: Both used during yaml2sql sync:
1. Check sync state for conflicts
2. Update relationships (may create tombstones)
3. Update sync state with new hash

---

## Developer Guide

### Adding Tombstone Support to New Association

**Scenario**: You add a new many-to-many relationship (e.g., `entry_locations`).

**Steps**:

1. **Update EntryManager.update_relationships()**:

```python
def update_relationships(self, entry, metadata, incremental, sync_source, removed_by):
    # ... existing code for people, tags, events, cities ...

    # Add locations support
    locations = metadata.get("locations", [])
    current_locations = {loc.name for loc in entry.locations}
    new_locations = set(locations) if locations else set()

    # Calculate changes
    remove_locations = current_locations - new_locations if not incremental else set()
    add_locations = new_locations - current_locations

    # Remove with tombstones
    for location_name in remove_locations:
        location = next(loc for loc in entry.locations if loc.name == location_name)

        # Create tombstone
        self.tombstones.create(
            table_name="entry_locations",  # New table name
            left_id=entry.id,
            right_id=location.id,
            removed_by=removed_by,
            sync_source=sync_source,
            reason="removed_from_source",
            ttl_days=90,
        )

        # Remove
        entry.locations.remove(location)

    # Add with tombstone check
    for location_name in add_locations:
        location = self._resolve_or_create(location_name, Location)

        if location and location not in entry.locations:
            # Check tombstone
            if self.tombstones.exists("entry_locations", entry.id, location.id):
                self.logger.log_debug(f"Skipping re-add - tombstone exists")
                continue

            # Remove tombstone if re-adding
            self.tombstones.remove_tombstone("entry_locations", entry.id, location.id)

            # Add
            entry.locations.append(location)
```

2. **Done!** No changes needed to:
   - TombstoneManager (generic)
   - Database schema (generic table)
   - CLI commands (generic)

### Testing Tombstone Behavior

**Example Test**:

```python
def test_tombstone_prevents_readd():
    """Test that tombstone prevents re-adding deleted person."""
    db = PalimpsestDB(":memory:")

    with db.session_scope() as session:
        # Create entry with person
        entry = db.entries.create({"date": "2024-11-23", "people": ["Alice"]})
        alice = session.query(Person).filter_by(name="Alice").first()

        # Remove person (creates tombstone)
        db.entries.update(
            entry,
            {"date": "2024-11-23", "people": []},
            sync_source="yaml",
            removed_by="test"
        )

        # Verify tombstone exists
        assert db.entries.tombstones.exists("entry_people", entry.id, alice.id)

        # Try to re-add (should be blocked by tombstone)
        db.entries.update(
            entry,
            {"date": "2024-11-23", "people": ["Alice"]},
            sync_source="yaml",
            removed_by="test"
        )

        # Verify person NOT re-added
        session.refresh(entry)
        assert alice not in entry.people

        # Verify tombstone still exists
        assert db.entries.tombstones.exists("entry_people", entry.id, alice.id)
```

---

## Monitoring and Debugging

### Logging

All tombstone operations are logged:

```python
# Creation
logger.log_info("Created association tombstone", {
    "table": "entry_people",
    "left_id": 123,
    "right_id": 456,
})

# Skipping re-add
logger.log_debug("Skipping re-add of Alice - tombstone exists", {
    "entry": "2024-11-23",
    "person": "Alice",
})

# Removal
logger.log_info("Removed tombstone", {
    "table": "entry_people",
    "left_id": 123,
    "right_id": 456,
})
```

### Checking Tombstone State

**SQL Query**:

```sql
-- Find all tombstones for an entry
SELECT *
FROM association_tombstones
WHERE table_name = 'entry_people'
  AND left_id = 123;

-- Find expired tombstones
SELECT *
FROM association_tombstones
WHERE expires_at IS NOT NULL
  AND expires_at <= datetime('now');

-- Count by table
SELECT table_name, COUNT(*) as count
FROM association_tombstones
GROUP BY table_name;
```

**CLI**:

```bash
# View all tombstones for entry 123
metadb tombstone list | grep "Left ID: 123"

# Count tombstones
metadb tombstone stats
```

---

## Future Enhancements

### 1. Configurable TTL

**Current**: Hardcoded 90 days
**Future**: User-configurable per tombstone or globally

```yaml
# config.yaml (future)
tombstone:
  default_ttl_days: 90
  ttl_by_reason:
    incorrect_association: null  # Permanent
    removed_from_source: 90
    privacy_request: null  # Permanent
```

### 2. Tombstone Archiving

**Current**: Expired tombstones deleted permanently
**Future**: Archive to separate table for audit trail

```python
class ArchivedTombstone(Base):
    """Archive of expired tombstones."""
    # Same schema as AssociationTombstone
    # Plus: archived_at, archived_by
```

### 3. Bulk Operations

**Current**: Create tombstones one at a time
**Future**: Batch create for performance

```python
tombstone_mgr.create_bulk([
    ("entry_people", 123, 456),
    ("entry_people", 123, 457),
    ("entry_tags", 124, 789),
])
```

### 4. Tombstone Export/Import

**Use Case**: Migrate tombstones between databases

```bash
# Export
metadb tombstone export tombstones.json

# Import
metadb tombstone import tombstones.json
```

---

## References

### Code Files

- **Models**: `dev/database/models.py` (AssociationTombstone class)
- **Manager**: `dev/database/tombstone_manager.py` (TombstoneManager class)
- **Entry Manager**: `dev/database/managers/entry_manager.py` (tombstone integration)
- **Migration**: `dev/migrations/versions/20251122_add_tombstone_and_sync_tracking.py`
- **CLI**: `dev/database/cli.py` (tombstone command group)

### Documentation

- **User Guide**: `docs/multi-machine-sync.md`
- **Conflict Resolution**: `docs/conflict-resolution.md`
- **Migration Guide**: `docs/migration-guide.md`

### Related Concepts

- **Soft Delete**: Marking records as deleted without removing
- **Tombstone Pattern**: Industry-standard pattern for distributed systems
- **Multi-Machine Sync**: Synchronizing data across multiple machines
- **Last-Write-Wins**: Simple conflict resolution strategy

---

## Summary

**Tombstones solve the multi-machine deletion problem**:
- Track when associations are deleted
- Prevent deleted associations from being re-added during sync
- Expire after 90 days (configurable)
- Managed via CLI and Python API
- Minimal performance overhead
- Transaction-safe and idempotent

**Key Insight**: Without tombstones, there's no way to distinguish "never existed" from "was deleted." Tombstones make deletions explicit and propagatable across machines.
