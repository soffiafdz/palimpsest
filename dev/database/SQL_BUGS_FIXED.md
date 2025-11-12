# SQL Database Bugs Fixed

**Date:** 2025-11-12
**Status:** ✅ COMPLETE

---

## Summary

Fixed **2 critical bugs** in the SQL database implementation:

1. **Location uniqueness constraint** - Data model flaw
2. **Missing epigraph_attribution** - Data loss bug in entry operations

---

## Bug #1: Location Uniqueness Constraint ✅ FIXED

### Problem
Location names were globally unique, preventing the same location name in different cities.

**Example:** Could not have "Central Park" in both NYC and San Francisco.

### Root Cause
```python
# BEFORE (models.py:985-986)
name: Mapped[str] = mapped_column(
    String(255), unique=True, nullable=False, index=True  # ❌ Globally unique
)
```

### Fix
Changed to composite unique constraint on `(name, city_id)`:

```python
# AFTER (models.py:981-990)
__table_args__ = (
    CheckConstraint("name != ''", name="ck_location_non_empty_name"),
    UniqueConstraint("name", "city_id", name="uq_location_name_city"),  # ✅ Unique per city
)

name: Mapped[str] = mapped_column(
    String(255), nullable=False, index=True  # ✅ No global unique
)
```

### Migration
Created Alembic migration: `20251112_0620_fix_location_uniqueness.py`

**Upgrade:**
- Drops old global unique constraint on `name`
- Adds composite unique constraint on `(name, city_id)`

**Downgrade:**
- Reverts to global unique (may fail if duplicates exist)

### Impact
- ✅ Now supports same location names in different cities
- ✅ More realistic data model
- ✅ No breaking changes to existing unique locations

---

## Bug #2: Missing epigraph_attribution ✅ FIXED

### Problem
The `epigraph_attribution` field was defined in the Entry model but **not being saved** when creating or updating entries, causing **silent data loss**.

### Root Cause
Three entry operation methods were missing the field:

1. **create_entry()** - Line 899-912
2. **update_entry()** - Line 1461-1469
3. **bulk_create_entries()** - Line 1577-1595

**Evidence of the bug:**
- ✅ Column exists in Entry model: `models.py:589`
- ✅ Field exists in MdEntry dataclass: `md_entry.py:121`
- ✅ from_database() tries to export it: `md_entry.py:314-315`
- ❌ **create_entry() didn't set it** - DATA LOSS!
- ❌ **update_entry() didn't set it** - DATA LOSS!
- ❌ **bulk_create_entries() didn't set it** - DATA LOSS!

### Fix

**1. create_entry() - Line 907-910**
```python
# BEFORE
entry = Entry(
    ...
    epigraph=DataValidator.normalize_string(metadata.get("epigraph")),
    notes=DataValidator.normalize_string(metadata.get("notes")),
)

# AFTER
entry = Entry(
    ...
    epigraph=DataValidator.normalize_string(metadata.get("epigraph")),
    epigraph_attribution=DataValidator.normalize_string(
        metadata.get("epigraph_attribution")
    ),  # ✅ ADDED
    notes=DataValidator.normalize_string(metadata.get("notes")),
)
```

**2. update_entry() - Line 1461-1469**
```python
# BEFORE
field_updates = {
    ...
    "epigraph": DataValidator.normalize_string,
    "notes": DataValidator.normalize_string,
}

# AFTER
field_updates = {
    ...
    "epigraph": DataValidator.normalize_string,
    "epigraph_attribution": DataValidator.normalize_string,  # ✅ ADDED
    "notes": DataValidator.normalize_string,
}

# Also updated the None check (line 1477)
if value is not None or field in ["epigraph", "epigraph_attribution", "notes"]:  # ✅ ADDED
```

**3. bulk_create_entries() - Line 1591-1593**
```python
# BEFORE
mappings.append({
    ...
    "epigraph": DataValidator.normalize_string(metadata.get("epigraph")),
    "notes": DataValidator.normalize_string(metadata.get("notes")),
})

# AFTER
mappings.append({
    ...
    "epigraph": DataValidator.normalize_string(metadata.get("epigraph")),
    "epigraph_attribution": DataValidator.normalize_string(
        metadata.get("epigraph_attribution")
    ),  # ✅ ADDED
    "notes": DataValidator.normalize_string(metadata.get("notes")),
})
```

### Impact
- ✅ No more silent data loss for epigraph attributions
- ✅ All three entry creation paths now handle the field
- ✅ Data integrity restored
- ✅ Existing entries unaffected (field was optional)

---

## Commits

| Commit | Description |
|--------|-------------|
| `332862b` | FIX: Location uniqueness constraint - per-city not global |
| `08a6c7d` | FIX CRITICAL: Add missing epigraph_attribution to entry create/update |
| `f96a306` | FIX: Add epigraph_attribution to bulk_create_entries |

---

## Testing Recommendations

### Location Uniqueness
```python
# Should now work without errors
with db.session_scope() as session:
    nyc = db.locations.create({"city": "New York", ...})
    sf = db.locations.create({"city": "San Francisco", ...})

    # Same name, different cities - should work!
    central_park_nyc = db.locations.create_location("Central Park", nyc)
    central_park_sf = db.locations.create_location("Central Park", sf)

    assert central_park_nyc.id != central_park_sf.id  # Different locations
    assert central_park_nyc.name == central_park_sf.name  # Same name
```

### Epigraph Attribution
```python
# Should now save attribution correctly
with db.session_scope() as session:
    entry = db.create_entry(session, {
        "date": "2024-01-15",
        "file_path": "/test.md",
        "epigraph": "To be or not to be",
        "epigraph_attribution": "Shakespeare, Hamlet",  # ✅ Now saved!
    })

    # Verify it was saved
    assert entry.epigraph == "To be or not to be"
    assert entry.epigraph_attribution == "Shakespeare, Hamlet"

    # Verify it persists
    loaded = db.get_entry(session, "2024-01-15")
    assert loaded.epigraph_attribution == "Shakespeare, Hamlet"
```

---

## Migration Instructions

### For Existing Databases

1. **Run migration:**
   ```bash
   alembic upgrade head
   ```

2. **Verify Location constraint:**
   ```sql
   -- Should show uq_location_name_city constraint
   SELECT sql FROM sqlite_master WHERE type='table' AND name='locations';
   ```

3. **No action needed for epigraph_attribution:**
   - Column already existed
   - Fix was in application code, not schema
   - Existing NULL values are valid

### For New Databases

- Migrations will apply automatically
- Both fixes included from the start

---

## Status

✅ **COMPLETE** - Both bugs fixed and pushed to branch

**Branch:** `claude/refactor-palimpsestdb-modular-managers-011CV38PFJqEXiaQzrkEwjTk`

**Files Modified:**
- `dev/database/models.py` - Location model fix
- `dev/database/manager.py` - Entry operations fix (3 methods)
- `dev/migrations/versions/20251112_0620_fix_location_uniqueness.py` - Migration

**No Breaking Changes:** Both fixes are backward compatible with existing data.
