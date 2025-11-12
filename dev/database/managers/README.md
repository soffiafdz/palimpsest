# Modular Database Managers

## Overview

This package contains the refactored database layer for Palimpsest, decomposing the monolithic `PalimpsestDB` class into focused, single-responsibility entity managers following SOLID principles.

## Architecture

### Before (Monolithic)
```
manager.py (3,163 lines)
└── PalimpsestDB class
    ├── Session management
    ├── Entry CRUD (300+ lines)
    ├── Person CRUD (200+ lines)
    ├── Event CRUD (150+ lines)
    ├── Tag operations
    ├── Location management
    ├── Reference handling
    ├── Poem versioning
    ├── Manuscript tracking
    ├── Date processing
    ├── Relationship updates (500+ lines)
    └── Utilities and helpers
```

### After (Modular)
```
managers/
├── base_manager.py           # Common utilities (273 lines) ✅
├── tag_manager.py            # Tag operations (463 lines) ✅
├── event_manager.py          # Event operations (629 lines) ✅
├── date_manager.py           # Date operations (506 lines) ✅
├── location_manager.py       # City + Location (685 lines) ✅
├── reference_manager.py      # Reference handling (602 lines) ✅
├── poem_manager.py           # Poem versioning (664 lines) ✅
├── person_manager.py         # TODO: Person management
├── manuscript_manager.py     # TODO: Manuscript tracking
├── entry_relationship_handler.py  # TODO: Complex entry relationships
└── entry_manager.py          # TODO: Entry CRUD
```

## Current Status

### ✅ Completed (7/9 managers - 78%)

#### BaseManager
- Abstract base class providing common utilities
- Retry logic for database locks (`_execute_with_retry`)
- Get-or-create helper (`_get_or_create`)
- Object resolution (`_resolve_object`)
- Shared session and logger management
- **273 lines** of reusable infrastructure

#### TagManager
- Full CRUD for Tag entities
- Link/unlink tags to/from entries
- Usage statistics and queries
- Demonstrates simplest manager pattern
- **463 lines** (was scattered across manager.py)

#### EventManager
- Full CRUD for Event entities with soft delete
- M2M relationships (entries, people)
- Link/unlink operations
- Chronological queries
- Date range filtering
- **629 lines** (extracted from manager.py:2466-2604)

#### DateManager
- Full CRUD for MentionedDate entities
- M2M relationships (entries, locations, people)
- Context tracking for date mentions
- Temporal analysis queries
- Get-or-create semantics
- **506 lines** (extracted from manager.py:1088-1697)

#### LocationManager
- Full CRUD for City and Location entities (parent-child)
- City: city (unique), state_province, country
- Location: name (unique), city_id (FK)
- M2M: both with entries, Location with MentionedDate
- Get-or-create city helper
- Query locations by city
- **685 lines** (extracted from manager.py:2221-2465)

#### ReferenceManager
- Full CRUD for ReferenceSource and Reference entities (parent-child)
- ReferenceType enum: book, article, film, poem, song, etc.
- ReferenceMode enum: direct, indirect, paraphrase, visual
- Reference requires content OR description
- Optional source linking for references
- Author validation for certain source types
- **602 lines** (extracted from manager.py:2606-2873)

#### PoemManager
- Full CRUD for Poem and PoemVersion entities (parent-child)
- Hash-based version deduplication using MD5
- Auto-generates version_hash from content
- Auto-regenerates hash when content changes
- Prevents duplicate versions (same poem_id + version_hash)
- Version timeline and chronological queries
- Poem titles NOT unique (same title can have multiple poems)
- **664 lines** (extracted from manager.py:2606-2997)

### 🔄 TODO (2/9 managers - 22%)

#### PersonManager (TODO)
- Manage Person and Alias entities
- Name disambiguation (name_fellow logic)
- Soft delete support
- M2M with events, entries, dates
- **Complexity**: High
- **Reference**: manager.py:1699-2220

#### ManuscriptManager (TODO)
- Manage manuscript-specific entities
  - ManuscriptEntry, ManuscriptPerson, ManuscriptEvent
  - Arc and Theme entities
- Complex 1-1 relationships with core entities
- **Complexity**: High
- **Reference**: manager.py:2998-3160

### 🔄 TODO (Complex Handlers)

#### EntryRelationshipHandler (TODO)
- Extract complex relationship update logic
- Coordinate updates across multiple entities
- Methods to extract:
  - `_update_entry_relationships()`
  - `_process_entry_aliases()`
  - `_process_mentioned_dates()`
  - `_update_entry_locations()`
  - `_update_entry_tags()`
  - `_process_related_entries()`
  - `_process_references()`
  - `_process_poems()`
- **Complexity**: Very High
- **Reference**: manager.py:705-1190

#### EntryManager (TODO)
- Core entry CRUD operations
- Delegate relationship updates to handler
- Bulk operations support
- File hash management
- **Complexity**: Very High
- **Reference**: manager.py:619-1143, 1208-1400

## Design Principles

### 1. Single Responsibility
Each manager handles exactly one entity type (or closely related pair like Poem/PoemVersion)

### 2. Consistent Interface
All managers implement:
- `exists(**kwargs) -> bool` - Check without exceptions
- `get(**kwargs) -> Optional[T]` - Flexible retrieval
- `create(metadata) -> T` - Create with validation
- `update(entity, metadata) -> T` - Update with relationships
- `delete(entity, **kwargs)` - Soft or hard delete

### 3. Dependency Injection
Managers receive `session` and `logger` via constructor, enabling:
- Testability (mock dependencies)
- Flexibility (shared or isolated sessions)
- Logging consistency

### 4. Decorator Pattern
Consistent cross-cutting concerns:
```python
@handle_db_errors           # Convert exceptions to DatabaseError
@log_database_operation()   # Log timing and context
@validate_metadata([...])   # Validate required fields
def create(self, metadata):
    ...
```

### 5. Relationship Delegation
Use `RelationshipManager` for generic M2M operations:
- Incremental vs replacement updates
- Type-safe object resolution
- Consistent API across all managers

## Usage Examples

### Basic CRUD

```python
from dev.database.managers import TagManager, EventManager

# Initialize managers with session
session = db.get_session()
tags = TagManager(session, logger)
events = EventManager(session, logger)

# Create entities
tag = tags.create({"tag": "python"})
event = events.create({
    "event": "pycon_2023",
    "title": "PyCon 2023",
    "description": "Python conference"
})

# Update with relationships
events.update(event, {
    "description": "Updated description",
    "entries": [entry1, entry2],
    "people": [person1, person2]
})

# Query
popular_tags = tags.get_by_usage(min_count=10)
recent_events = events.get_by_date_range(start_date, end_date)

# Soft delete and restore
events.delete(event, deleted_by="admin", reason="Duplicate")
events.restore(event)
```

### Relationship Management

```python
# Link entities
tags.link_to_entry(entry, "python")
events.link_to_person(event, person)
dates.link_to_location(mentioned_date, location)

# Unlink entities
tags.unlink_from_entry(entry, "old-tag")
events.unlink_from_person(event, person)

# Bulk update (incremental)
tags.update_entry_tags(entry, ["python", "coding", "web"], incremental=True)

# Bulk update (replacement)
tags.update_entry_tags(entry, ["python", "coding"], incremental=False)
```

### Get-or-Create Pattern

```python
# Tags
tag = tags.get_or_create("python")  # Returns existing or creates new

# Dates
mentioned_date = dates.get_or_create(
    date(2023, 6, 15),
    context="Birthday"
)

# Events
event = events.get(event_name="pycon_2023")
if not event:
    event = events.create({...})
```

## Migration Path

### Phase 1: Manager Implementation (Current)
✅ Create BaseManager
✅ Implement 3 managers (Tag, Event, Date)
🔄 Implement remaining 6 managers

### Phase 2: PalimpsestDB Integration (Next)
```python
class PalimpsestDB:
    def __init__(self, db_path, alembic_dir, ...):
        self._setup_engine()
        self._init_managers()

    def _init_managers(self):
        session = self.get_session()
        self.tags = TagManager(session, self.logger)
        self.events = EventManager(session, self.logger)
        self.dates = DateManager(session, self.logger)
        # ... rest of managers
```

### Phase 3: Update Calling Code
```python
# Before
with db.session_scope() as session:
    tag = db._get_or_create_lookup_item(session, Tag, {"tag": "python"})

# After
tag = db.tags.get_or_create("python")
```

### Phase 4: Deprecate Old Methods
```python
def create_event(self, session, metadata):
    """Deprecated: Use db.events.create() instead."""
    warnings.warn("Use db.events.create()", DeprecationWarning)
    return self.events.create(metadata)
```

## Testing Strategy

Each manager should have tests for:

```python
def test_create_tag():
    """Test basic tag creation."""
    tag = tag_mgr.create({"tag": "test"})
    assert tag.tag == "test"
    assert tag.id is not None

def test_link_unlink():
    """Test relationship management."""
    tag_mgr.link_to_entry(tag, entry)
    assert tag in entry.tags
    tag_mgr.unlink_from_entry(tag, entry)
    assert tag not in entry.tags

def test_error_handling():
    """Test validation and errors."""
    with pytest.raises(ValidationError):
        tag_mgr.create({"tag": ""})  # Empty tag
    with pytest.raises(DatabaseError):
        tag_mgr.create({"tag": "duplicate"})  # Duplicate
```

## Benefits Achieved

### Code Organization
- **Before**: 3,163 lines in one file
- **After**: ~300-600 lines per focused manager
- **Improvement**: 5-10x easier to navigate and understand

### Testability
- **Before**: Hard to test individual operations in isolation
- **After**: Each manager independently testable
- **Improvement**: Mocking, fixtures, unit tests all easier

### Maintainability
- **Before**: Changes risk breaking unrelated functionality
- **After**: Changes isolated to specific manager
- **Improvement**: Lower risk, faster development

### Reusability
- **Before**: Utilities scattered throughout monolith
- **After**: BaseManager provides shared infrastructure
- **Improvement**: Common patterns standardized

### Type Safety
- **Before**: Minimal type hints
- **After**: Full type hints on all methods
- **Improvement**: IDE support, compile-time checks

## Documentation

- **REFACTORING_GUIDE.md**: Detailed implementation patterns and checklists
- **Base manager source**: Comprehensive docstrings
- **Example managers**: Tag, Event, Date demonstrate increasing complexity

## Next Steps

1. Implement remaining managers following established patterns
2. Create test suite for all managers
3. Integrate managers into PalimpsestDB
4. Update calling code to use new API
5. Add deprecation warnings to old methods
6. Remove old implementation after migration complete

## Questions?

See `REFACTORING_GUIDE.md` for:
- Implementation checklist
- Code examples
- Pattern explanations
- Migration strategy
- Testing guidelines
