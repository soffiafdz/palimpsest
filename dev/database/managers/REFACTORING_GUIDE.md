# PalimpsestDB Refactoring Guide

## Overview

This guide documents the ongoing refactoring of the monolithic `PalimpsestDB` class (3000+ lines) into a modular architecture using specialized entity managers following SOLID principles.

## Architecture

### Core Components

```
dev/database/managers/
├── base_manager.py          # Abstract base class with common utilities
├── tag_manager.py           # ✅ COMPLETE - Simple M2M relationships
├── event_manager.py         # ✅ COMPLETE - Soft delete + M2M relationships
├── date_manager.py          # ✅ COMPLETE - M2M with entries/locations/people
├── location_manager.py      # ✅ COMPLETE - City + Location (parent-child)
├── reference_manager.py     # ✅ COMPLETE - ReferenceSource + Reference (parent-child)
├── poem_manager.py          # ✅ COMPLETE - Poem + PoemVersion (versioning)
├── person_manager.py        # ✅ COMPLETE - Person + Alias (name disambiguation)
├── manuscript_manager.py    # ✅ COMPLETE - Multiple manuscript entities
└── entry_manager.py         # ✅ COMPLETE - Entry CRUD (most complex)
```

### BaseManager Pattern

All managers inherit from `BaseManager` which provides:

```python
class BaseManager(ABC):
    """Common utilities for all entity managers."""

    def __init__(self, session: Session, logger: Optional[PalimpsestLogger] = None):
        self.session = session
        self.logger = logger

    # Core helpers
    def _execute_with_retry(self, operation, max_retries=3, retry_delay=0.1) -> Any
    def _get_or_create(self, model_class, lookup_fields, extra_fields) -> T
    def _resolve_object(self, item, model_class) -> T
```

## Design Patterns

### 1. Consistent CRUD Methods

Every manager implements these standardized methods:

```python
def exists(self, **kwargs) -> bool:
    """Check existence without exceptions."""

def get(self, **kwargs) -> Optional[T]:
    """Retrieve single entity with flexible lookup."""

def get_all(self, **kwargs) -> List[T]:
    """Retrieve multiple entities."""

def create(self, metadata: Dict[str, Any]) -> T:
    """Create new entity with relationships."""

def update(self, entity: T, metadata: Dict[str, Any]) -> T:
    """Update entity and relationships."""

def delete(self, entity: T, **kwargs) -> None:
    """Delete entity (soft or hard)."""
```

### 2. Decorator Stack

All public methods use consistent decorators:

```python
@handle_db_errors
@log_database_operation("operation_name")
@validate_metadata(["required_field"])  # Optional, for create/update only
def create(self, metadata: Dict[str, Any]) -> T:
    ...
```

### 3. Relationship Management

Use `RelationshipManager` for generic M2M relationships:

```python
def _update_relationships(self, entity, metadata, incremental=True):
    """Update all relationships for an entity."""
    many_to_many_configs = [
        ("entries", "entries", Entry),
        ("people", "people", Person),
    ]

    for rel_name, meta_key, model_class in many_to_many_configs:
        if meta_key in metadata:
            RelationshipManager.update_many_to_many(
                session=self.session,
                parent_obj=entity,
                relationship_name=rel_name,
                items=metadata[meta_key],
                model_class=model_class,
                incremental=incremental,
                remove_items=metadata.get(f"remove_{meta_key}", []),
            )
```

### 4. Input Normalization

Always use `DataValidator` for input normalization:

```python
from dev.core.validators import DataValidator

# Normalize strings (strip whitespace, handle None)
name = DataValidator.normalize_string(metadata.get("name"))

# Normalize dates
entry_date = DataValidator.normalize_date(metadata.get("date"))

# Normalize enums
mode = DataValidator.normalize_reference_mode(metadata.get("mode"))
```

### 5. Logging Pattern

All operations should log with context:

```python
if self.logger:
    self.logger.log_debug(
        f"Created entity: {entity.name}",
        {"entity_id": entity.id, "extra_context": value}
    )
```

## Implementation Checklist

When implementing a new manager, ensure:

- [ ] Inherits from `BaseManager`
- [ ] Constructor takes `(session, logger)` and calls `super().__init__()`
- [ ] All public methods use `@handle_db_errors`
- [ ] All public methods use `@log_database_operation()`
- [ ] Create/update methods use `@validate_metadata()` where appropriate
- [ ] Implements `exists()`, `get()`, `create()`, `update()`, `delete()`
- [ ] Uses `DataValidator` for all input normalization
- [ ] Uses `RelationshipManager` for M2M relationships
- [ ] Implements `_update_relationships()` if entity has relationships
- [ ] Includes comprehensive docstrings with Args, Returns, Raises
- [ ] Type hints on all methods
- [ ] Logs all significant operations with context

## Examples

### Simple Manager (Tag)

TagManager demonstrates the simplest case:
- Single table (no parent-child relationships)
- Simple M2M with entries
- Get-or-create semantics
- Basic CRUD + link/unlink methods

See: `tag_manager.py:1-463`

### Manager with Soft Delete (Event)

EventManager adds soft delete support:
- Inherits from model with `SoftDeleteMixin`
- `delete()` method handles both soft and hard delete
- `restore()` method for undeleting
- All queries filter out deleted by default (with `include_deleted` flag)

See: `event_manager.py:1-629`

### Manager with Multiple Relationships (Date)

DateManager shows complex M2M handling:
- Relationships with entries, locations, AND people
- Context field for additional metadata
- Get-or-create by date value
- Query methods for each relationship type

See: `date_manager.py:1-506`

## Migration Strategy

### Phase 1: Create Managers ✅ COMPLETE
1. Create `BaseManager` with common utilities ✅
2. Implement individual entity managers following patterns ✅ (9/9 complete)
3. Test managers independently ✅

### Phase 2: Integrate with PalimpsestDB ✅ COMPLETE
```python
class PalimpsestDB:
    """Slim database manager that delegates to entity managers."""

    def __init__(self, db_path, alembic_dir, log_dir=None, backup_dir=None):
        self._setup_engine()
        self._init_managers()

    def _init_managers(self):
        """Initialize all entity managers with shared session."""
        session = self.get_session()
        self.tags = TagManager(session, self.logger)
        self.events = EventManager(session, self.logger)
        self.dates = DateManager(session, self.logger)
        self.locations = LocationManager(session, self.logger)
        self.references = ReferenceManager(session, self.logger)
        self.poems = PoemManager(session, self.logger)
        self.people = PersonManager(session, self.logger)
        self.manuscripts = ManuscriptManager(session, self.logger)
        self.entries = EntryManager(session, self.logger)
```

### Phase 3: Update Calling Code ✅ COMPLETE
**Before:**
```python
db = PalimpsestDB(...)
with db.session_scope() as session:
    person = db.create_person(session, metadata)
```

**After:**
```python
db = PalimpsestDB(...)
person = db.people.create(metadata)
```

### Phase 4: Remove Legacy Code ✅ COMPLETE
Legacy backward compatibility methods have been removed. The new modular
API (db.entries, db.people, db.events, etc.) is now the standard interface.

## Completed Work

### ✅ LocationManager
- Manages both `City` and `Location` entities
- Parent-child relationship (Location belongs to City)
- M2M with entries and mentioned dates
- Reference implementation in `manager.py:2221-2465`

### ✅ ReferenceManager
- Manages `ReferenceSource` and `Reference` entities
- Parent-child relationship (Reference belongs to ReferenceSource)
- Handles `ReferenceMode` and `ReferenceType` enums
- Implementation: `reference_manager.py`

### ✅ PoemManager
- Manages `Poem` and `PoemVersion` entities
- Parent-child relationship (PoemVersion belongs to Poem)
- Version deduplication via hash
- Implementation: `poem_manager.py`

### ✅ PersonManager
- Manages `Person` and `Alias` entities (one-to-many)
- Complex: name disambiguation with `name_fellow` field
- Soft delete support
- M2M with events, entries, and mentioned dates
- Implementation: `person_manager.py`

### ✅ ManuscriptManager
- Manages multiple entities: `ManuscriptEntry`, `ManuscriptPerson`, `ManuscriptEvent`
- Manages `Arc` and `Theme` entities
- Complex one-to-one relationships with core entities
- Implementation: `manuscript_manager.py`

### ✅ EntryManager
- Most complex manager - handles all entry CRUD operations
- Manages entry relationships via integrated methods
- Bulk operations support
- File hash management
- String resolution for YAML imports (people, events, cities as strings)
- Implementation: `entry_manager.py`

## Testing Strategy

For each manager, create tests for:
1. Basic CRUD operations
2. Relationship management (link/unlink)
3. Error conditions (missing required fields, duplicates)
4. Soft delete and restore (where applicable)
5. Query methods (filtering, ordering)
6. Edge cases (empty lists, None values)

## Benefits of Refactored Architecture

✅ **Single Responsibility**: Each manager handles one entity type
✅ **Testability**: Managers can be tested in isolation
✅ **Maintainability**: Clear organization, easy to locate code
✅ **Consistency**: All managers follow same patterns
✅ **Type Safety**: Full type hints enable IDE support
✅ **Reusability**: BaseManager utilities shared across all managers
✅ **Extensibility**: Easy to add new entity types

## Reference Implementation

See existing managers for examples:
- **Simple**: `tag_manager.py` - Basic CRUD with M2M
- **Medium**: `event_manager.py` - Adds soft delete
- **Complex**: `date_manager.py` - Multiple M2M relationships

Follow these patterns when implementing remaining managers.
