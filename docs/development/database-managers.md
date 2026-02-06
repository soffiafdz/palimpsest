# Database Manager System

## Overview

The Palimpsest database layer uses a modular architecture with specialized entity managers. Each manager handles operations for a specific entity type (or closely related entity pair), following the Single Responsibility Principle.

## Why Modular Managers?

The database layer is organized into focused managers rather than a monolithic class because:

1. **Testability** - Each manager can be tested independently with clear inputs/outputs
2. **Maintainability** - Changes to one entity type don't affect others
3. **Reusability** - Common patterns are shared via BaseManager
4. **Type Safety** - Full type hints enable IDE support and compile-time checks
5. **Clarity** - Each manager has a single, well-defined purpose

## Manager Architecture

```
dev/database/managers/
├── base_manager.py           # Common utilities and patterns
├── tag_manager.py            # Tag operations
├── event_manager.py          # Event operations with soft delete
├── location_manager.py       # City + Location (parent-child)
├── reference_manager.py      # ReferenceSource + Reference (parent-child)
├── poem_manager.py           # Poem + PoemVersion (versioning)
├── person_manager.py         # Person + Alias (name disambiguation)
├── manuscript_manager.py     # Manuscript entities
└── entry_manager.py          # Entry CRUD with relationships
```

## Manager Capabilities

### BaseManager

Abstract base class providing shared infrastructure:

- `_execute_with_retry()` - Retry logic for database locks
- `_get_or_create()` - Get-or-create helper for lookups
- `_resolve_object()` - Converts names/dicts to model instances
- Shared session and logger management

### TagManager

Manages Tag entities with many-to-many relationships to entries.

**Key Features:**
- Full CRUD operations
- Link/unlink tags to/from entries
- Usage statistics queries
- Get-or-create semantics

**Example:**
```python
tags = TagManager(session, logger)
tag = tags.get_or_create("python")
tags.link_to_entry(entry, "python")
popular_tags = tags.get_by_usage(min_count=10)
```

### EventManager

Manages Event entities with soft delete support.

**Key Features:**
- Full CRUD with soft delete (deleted_at, deleted_by, deletion_reason)
- M2M relationships with entries and people
- Chronological queries and date range filtering
- Restore capabilities

**Example:**
```python
events = EventManager(session, logger)
event = events.create({
    "event": "pycon_2023",
    "title": "PyCon 2023",
    "description": "Python conference"
})
events.delete(event, deleted_by="admin", reason="Duplicate")
events.restore(event)
```

### LocationManager

Manages City and Location entities (parent-child relationship).

**Key Features:**
- City: city name (unique), state/province, country
- Location: name (unique), city_id (foreign key)
- M2M relationships with entries
- Location-Date associations
- Get-or-create helper for cities

**Example:**
```python
locations = LocationManager(session, logger)
city = locations.get_or_create_city("Montreal", "QC", "Canada")
location = locations.create({
    "name": "Parc Jarry",
    "city_id": city.id
})
```

### ReferenceManager

Manages ReferenceSource and Reference entities (parent-child).

**Key Features:**
- ReferenceSource: book, article, film, song, etc.
- Reference: specific quote/mention with mode (direct, indirect, paraphrase, visual)
- Validation: references require content OR description
- Author validation for certain source types

**Example:**
```python
references = ReferenceManager(session, logger)
source = references.create_source({
    "type": "book",
    "title": "Infinite Jest",
    "author": "David Foster Wallace"
})
reference = references.create({
    "source_id": source.id,
    "mode": "direct",
    "content": "I am in here."
})
```

### PoemManager

Manages Poem and PoemVersion entities with content versioning.

**Key Features:**
- Poem: title (not unique - multiple poems can share a title)
- PoemVersion: content tracking with revision dates
- Version timeline queries

**Example:**
```python
poems = PoemManager(session, logger)
poem = poems.create({
    "title": "Untitled",
    "content": "first version"
})
# Updating content creates new version
poems.update(poem, {"content": "second version"})
versions = poems.get_versions(poem)
```

### PersonManager

Manages Person and Alias entities with name disambiguation.

**Key Features:**
- Person: display_name, optional full_name for disambiguation
- Alias: alternative names for the same person
- Soft delete support
- M2M relationships with events, entries, and dates
- Name_fellow logic: multiple people with same display_name require full_name

**Example:**
```python
people = PersonManager(session, logger)
person = people.create({
    "display_name": "Alex",
    "full_name": "Alex Johnson",  # Required if another "Alex" exists
    "relation_type": "friend"
})
alias = people.create_alias(person, "AJ")
people.delete(person, deleted_by="user", reason="Privacy")
people.restore(person)
```

### ManuscriptManager

Manages manuscript-related entities for creative writing projects.

**Key Features:**
- ManuscriptEntry: links Entry to manuscript (status, editing notes)
- ManuscriptPerson: links Person to character mapping
- ManuscriptEvent: links Event to story arc assignment
- Arc: story arc groupings
- Theme: thematic elements with M2M to entries

**Status Values:** unspecified, draft, reviewed, included, excluded, final

**Example:**
```python
manuscript = ManuscriptManager(session, logger)
manuscript_entry = manuscript.create_entry({
    "entry_id": entry.id,
    "status": "draft",
    "editing_notes": "Needs revision"
})
arc = manuscript.create_arc({
    "arc": "childhood",
    "description": "Early years"
})
ready = manuscript.get_ready_entries()  # Status: reviewed or included
```

### EntryManager

Manages Entry entities with comprehensive relationship handling.

**Key Features:**
- Full CRUD with all relationship types
- Delegates to specialized managers (Person, Location, Date, Reference, Poem, Manuscript)
- File hash management for change detection
- Incremental vs. replacement update modes
- Optimized eager loading for queries
- Bulk operations

**Example:**
```python
entries = EntryManager(session, logger)
entry = entries.create({
    "date": date(2024, 1, 1),
    "file_path": "/path/to/entry.md",
    "word_count": 500,
    "people": ["Alice", "Bob"],
    "tags": ["reflection", "coding"],
    "locations": [{"name": "Home"}]
})

# Incremental update (adds new, keeps existing)
entries.update(entry, {
    "people": ["Charlie"]  # Alice and Bob remain
}, incremental=True)

# Replacement update (replaces all)
entries.update(entry, {
    "people": ["Charlie"]  # Alice and Bob removed
}, incremental=False)
```

## Common Patterns

### Consistent Interface

All managers implement these core methods:

```python
def exists(**kwargs) -> bool:
    """Check if entity exists without raising exceptions."""

def get(**kwargs) -> Optional[T]:
    """Retrieve single entity with flexible lookup."""

def create(metadata: Dict[str, Any]) -> T:
    """Create new entity with validation."""

def update(entity: T, metadata: Dict[str, Any]) -> T:
    """Update entity and relationships."""

def delete(entity: T, **kwargs) -> None:
    """Delete entity (soft or hard)."""
```

### Decorator Stack

All public methods use these decorators:

```python
@handle_db_errors              # Convert exceptions to DatabaseError
@log_database_operation()       # Log timing and context
@validate_metadata([fields])    # Validate required fields (create/update only)
def create(self, metadata):
    ...
```

### Dependency Injection

Managers receive dependencies via constructor:

```python
manager = TagManager(session, logger)
```

This enables:
- **Testability**: Mock dependencies for unit tests
- **Flexibility**: Use shared or isolated sessions
- **Consistency**: Centralized logging

### Relationship Management

Use `RelationshipManager` for M2M operations:

```python
from dev.database.relationship_manager import RelationshipManager

# In manager's update method
RelationshipManager.update_many_to_many(
    session=self.session,
    parent_obj=entry,
    relationship_name="tags",
    items=metadata["tags"],
    model_class=Tag,
    lookup_field="tag",
    incremental=True
)
```

## Usage in PalimpsestDB

The main `PalimpsestDB` class initializes all managers:

```python
class PalimpsestDB:
    def __init__(self, db_path, alembic_dir, ...):
        self._setup_engine()
        self._init_managers()

    def _init_managers(self):
        """Initialize all entity managers."""
        session = self.get_session()
        self.tags = TagManager(session, self.logger)
        self.events = EventManager(session, self.logger)
        self.dates = DateManager(session, self.logger)
        self.locations = LocationManager(session, self.logger)
        self.references = ReferenceManager(session, self.logger)
        self.poems = PoemManager(session, self.logger)
        self.people = PersonManager(session, self.logger)
        self.manuscript = ManuscriptManager(session, self.logger)
        self.entries = EntryManager(session, self.logger)
```

### Two Access Patterns

**Direct Manager Access** (recommended for new code):
```python
with db.session_scope() as session:
    tag = db.tags.get_or_create("python")
    entry = db.entries.create(metadata)
```

**Facade API** (legacy, used by existing pipeline code):
```python
with db.session_scope() as session:
    tag = db._get_or_create_lookup_item(session, Tag, {"tag": "python"})
    entry = db.create_entry(session, metadata)
```

Both approaches are supported for backward compatibility.

## Testing Managers

Each manager should have tests covering:

**Basic CRUD:**
```python
def test_create_tag():
    """Test basic tag creation."""
    tag = tag_mgr.create({"tag": "test"})
    assert tag.tag == "test"
    assert tag.id is not None
```

**Relationships:**
```python
def test_link_unlink():
    """Test relationship management."""
    tag_mgr.link_to_entry(tag, entry)
    assert tag in entry.tags
    tag_mgr.unlink_from_entry(tag, entry)
    assert tag not in entry.tags
```

**Error Handling:**
```python
def test_error_handling():
    """Test validation and errors."""
    with pytest.raises(ValidationError):
        tag_mgr.create({"tag": ""})  # Empty tag
    with pytest.raises(DatabaseError):
        tag_mgr.create({"tag": "duplicate"})  # Duplicate
```

**Soft Delete** (for managers supporting it):
```python
def test_soft_delete_restore():
    """Test soft delete and restore."""
    person_mgr.delete(person, deleted_by="admin", reason="Test")
    assert person.deleted_at is not None
    person_mgr.restore(person)
    assert person.deleted_at is None
```

## See Also

- `dev/database/manager.py` - Main PalimpsestDB class
- `dev/database/relationship_manager.py` - M2M relationship helpers
- `dev/database/decorators.py` - Error handling and logging decorators
- `dev/database/models/` - SQLAlchemy model definitions
