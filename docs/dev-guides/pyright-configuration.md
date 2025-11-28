# Pyright Configuration and Warning Management

## Overview

This document explains how Pyright type checking is configured for the Palimpsest project, particularly regarding defensive coding practices and warning suppression.

## Configuration File

Configuration is in `pyrightconfig.json` at the project root.

## Defensive Coding Warnings (Suppressed)

These warnings were suppressed because they flag intentional defensive coding practices:

### 1. `reportUnnecessaryIsInstance` (set to "none")

**Why suppressed**: These isinstance checks validate runtime data from untrusted sources (YAML parsing, user input, API calls).

**Example**:
```python
# YAML parsing - metadata could be malformed
if isinstance(date_item, dict) and "date" in date_item:
    # Safe to access dict keys
    date_obj = date.fromisoformat(date_item["date"])
```

Even though type hints say `date_item: Dict[str, Any]`, runtime validation ensures YAML didn't produce unexpected types.

**Another example**:
```python
# Enum validation - accepts both string and enum
def get_by_status(self, status: Union[ManuscriptStatus, str]):
    if isinstance(status, str):  # Pyright says unnecessary
        status = ManuscriptStatus[status.upper()]
    # ... use status as enum
```

This allows flexible API usage while maintaining type safety.

### 2. `reportUnnecessaryComparison` (set to "none")

**Why suppressed**: These comparisons check for None on SQLAlchemy model attributes that might not be persisted yet.

**Example**:
```python
# SQLAlchemy model - id is None before commit
if entry.id is None:  # Pyright says always False
    # But it CAN be None before session.flush()
    raise ValueError("Entry not persisted")
```

SQLAlchemy mapped columns are typed as `Mapped[int]`, but before database persistence, `id` is actually `None`. These defensive checks prevent bugs.

### 3. `reportImportCycles` (set to "none")

**Why suppressed**: Import cycles exist due to architectural constraints in the module system. They work fine at runtime due to Python's import system but Pyright flags them.

**Typical pattern**:
```
dev/database/__init__.py imports dev/database/manager.py
dev/database/manager.py imports dev/database/models/__init__.py
dev/database/models/__init__.py imports dev/database/__init__.py (for exceptions)
```

These cycles are managed through careful module initialization order and don't cause runtime issues.

## Active Warnings (Not Suppressed)

These warnings remain active as they catch real issues:

- `reportUnusedImport`: Catches dead code
- `reportUnusedVariable`: Catches unused assignments
- `reportOptionalMemberAccess`: Catches potential AttributeError
- `reportPrivateUsage`: Prevents using private/protected methods incorrectly
- `reportUnnecessaryCast`: Catches redundant type casts

## Alternative Approach: Inline Comments

Instead of suppressing at config level, you can suppress individual lines:

```python
# Suppress specific warning with explanation
if isinstance(data, dict):  # type: ignore[reportUnnecessaryIsInstance]  # Runtime validation of YAML
    process_dict(data)
```

**Pros**: More explicit, documents why each check exists
**Cons**: Clutters code with many comments

For this project, we chose config-level suppression since the patterns are consistent across the codebase.

## Resolving Import Cycles (Future Work)

Import cycles could be resolved by:

1. **Dependency Inversion**: Move shared types/exceptions to a separate `dev/database/types.py` module
2. **Lazy Imports**: Use `TYPE_CHECKING` for type hints only:
   ```python
   from typing import TYPE_CHECKING
   if TYPE_CHECKING:
       from dev.database import PalimpsestDB
   ```
3. **Restructuring**: Split large `__init__.py` files to reduce interdependencies

These require significant refactoring and aren't critical since the cycles don't cause runtime issues.

## Summary

The current configuration balances strict type checking (errors on real issues) with pragmatic suppression of warnings that flag intentional defensive coding. This gives you clean Pyright output while maintaining runtime safety.
