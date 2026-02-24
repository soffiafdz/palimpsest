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
├── entity_manager.py         # Config-driven base for complex entities
├── simple_manager.py         # Config-driven manager for Tag, Theme, Arc
├── event_manager.py          # Event stub (events handled by EntryManager)
├── location_manager.py       # City + Location (parent-child)
├── reference_manager.py      # ReferenceSource + Reference (parent-child)
├── poem_manager.py           # Poem + PoemVersion (versioning)
├── person_manager.py         # Person with slug-based lookup
└── entry_manager.py          # Entry CRUD with 14 relationship processors
```

## Manager Capabilities

### BaseManager

Abstract base class providing shared infrastructure:

- `_execute_with_retry()` - Retry logic with exponential backoff for database locks
- `_get_or_create()` - Generic get-or-create for any model with race condition handling
- `_resolve_object()` - Resolve ORM instances or integer IDs to model objects
- `_exists()` - Generic existence check with soft-delete awareness
- `_get_by_id()` - Get by ID with soft-delete filtering
- `_get_by_field()` - Get by arbitrary field value
- `_get_all()` - Get all with optional ordering and filtering
- `_count()` - Count entities with optional filtering
- `_update_collection()` - Update M2M relationship collections
- `_update_relationships()` - Batch update multiple M2M relationships from metadata
- `_update_scalar_fields()` - Update scalar fields with normalizers
- `_resolve_parent()` - Resolve parent entity from object, ID, or name string
- Shared session and logger management

### SimpleManager (Tag, Theme, Arc)

Config-driven manager for simple lookup entities. Each entity type is defined by a `SimpleManagerConfig` specifying the model class, lookup field, normalizer, and relationships.

**Covers:** Tag, Theme, Arc

**Key Features:**
- Get-or-create semantics
- Link/unlink to entries
- Usage statistics queries
- Config-driven (no per-entity subclass needed)

**Example:**
```python
tag_mgr = SimpleManager.for_tags(session, logger)
tag = tag_mgr.get_or_create("python")
tag_mgr.link_to_entry(tag, entry)

theme_mgr = SimpleManager.for_themes(session, logger)
theme = theme_mgr.get_or_create("identity")

arc_mgr = SimpleManager.for_arcs(session, logger)
arc = arc_mgr.get_or_create("The Long Wanting")
```

### EventManager (Stub)

Minimal stub to satisfy imports. Event get-or-create and scene linking are handled directly by `EntryManager._process_events()` and `EntryManager._get_or_create_event()`.

### LocationManager

Manages City and Location entities (parent-child relationship).

**Key Features:**
- City: city name (unique), state/province, country
- Location: name (unique), city_id (foreign key)
- M2M relationships with entries
- Get-or-create helpers for both cities and locations

**Example:**
```python
locations = LocationManager(session, logger)
city = locations.get_or_create_city("Montreal", "QC", "Canada")
location = locations.get_or_create_location("Parc Jarry", "Montreal")
```

### ReferenceManager

Manages ReferenceSource and Reference entities (parent-child).

**Key Features:**
- ReferenceSource: book, article, film, song, etc.
- Reference: specific quote/mention with mode (direct, indirect, paraphrase, visual, thematic)
- Validation: references require content OR description
- Source linking (optional)

**Example:**
```python
ref_mgr = ReferenceManager(session, logger)
source = ref_mgr.create({
    "type": "book",
    "title": "The Great Gatsby",
    "author": "F. Scott Fitzgerald"
})
reference = ref_mgr.create_reference({
    "content": "So we beat on, boats against the current...",
    "mode": "direct",
    "entry": entry,
    "source": source
})
```

### PoemManager

Manages Poem and PoemVersion entities with content versioning and deduplication.

**Key Features:**
- Poem: title (not unique — multiple poems can share a title)
- PoemVersion: content tracking with hash-based deduplication
- `create_version()` handles parent Poem get-or-create automatically
- Duplicate content detection via MD5 hashing

**Example:**
```python
poems = PoemManager(session, logger)
version = poems.create_version({
    "title": "Autumn Reverie",
    "content": "Leaves fall softly...",
    "entry": entry
})
# Same content won't create a duplicate version
version2 = poems.create_version({
    "title": "Autumn Reverie",
    "content": "Leaves fall softly...",
    "poem": version.poem
})  # Returns existing version
```

### PersonManager

Manages Person entities with slug-based lookup and soft delete support.

**Key Features:**
- Person: name, lastname, slug (unique identifier)
- Slug-based disambiguation for people with the same name
- Soft delete support (deleted_at, deleted_by, deletion_reason)
- M2M relationships with entries, scenes, and threads
- Alias support via PersonAlias model

**Example:**
```python
people = PersonManager(session, logger)
person = people.get_or_create("Lucia Elena", lastname="Castro")
majo = people.get(slug="maria-jose-castro")

# Soft delete and restore
people.delete(person, deleted_by="admin", reason="Duplicate")
people.restore(person)
```

### EntryManager

Manages Entry entities with comprehensive relationship handling. This is the most complex manager, as Entry is the central entity connecting to all other types.

**Key Features:**
- Full CRUD with all 14 relationship types
- Delegates to specialized managers (PersonManager, LocationManager, PoemManager)
- 10 dedicated relationship processor methods
- File hash management for change detection
- Incremental (additive) vs. replacement update modes
- Bulk operations with batch processing
- Accent-insensitive name matching for scene/thread subset resolution

**Relationship Processors:**

| Processor | Type | Description |
|-----------|------|-------------|
| cities | M2M | Direct collection via `_resolve_or_create` |
| people | M2M | Direct collection via `_resolve_or_create` |
| `_process_locations` | M2M | Locations with city context (`{city: [locations]}`) |
| `_process_narrated_dates` | O2M | Date objects or ISO strings |
| `_process_scenes` | O2M | Scenes with dates, people, locations (subset matching) |
| `_process_events` | M2M | Events with scene linking |
| `_process_tags` | M2M | String-based tag get-or-create |
| `_process_arcs` | M2M | Arc get-or-create |
| `_process_themes` | M2M | Theme get-or-create |
| `_process_threads` | O2M | Temporal echoes with flexible date formats |
| `_process_motifs` | O2M | Motif get-or-create + MotifInstance |
| `_process_references` | O2M | ReferenceSource get-or-create + Reference |
| `_process_poems` | O2M | Delegates to PoemManager.create_version |

**Processing Order** (dependency-aware):
1. Cities + People (M2M loop) — resolved first for subset matching
2. Locations — needs cities
3. Narrated dates
4. Scenes — needs people + locations for subset matching
5. Events — needs scenes for linking
6. Tags, Arcs, Themes — independent
7. Threads — needs people + locations for subset matching
8. Motifs, References, Poems — independent

**Example:**
```python
entries = EntryManager(session, logger)
entry = entries.create({
    "date": date(2024, 1, 1),
    "file_path": "/path/to/entry.md",
    "word_count": 500,
    "people": ["Alice", {"name": "Bob", "full_name": "Robert Smith"}],
    "cities": ["Montreal"],
    "locations": {"Montreal": ["Café X", "Library"]},
    "tags": ["reflection", "coding"],
    "scenes": [
        {
            "name": "Morning Coffee",
            "description": "A quiet start at the café",
            "date": "2024-01-01",
            "people": ["Alice"],
            "locations": ["Café X"]
        }
    ],
    "events": [
        {"name": "New Year's Day", "scenes": ["Morning Coffee"]}
    ],
    "threads": [
        {
            "name": "The Recurring Dream",
            "from": "2024-01-01",
            "to": "2023-06",
            "content": "The morning ritual echoes last summer's routine"
        }
    ]
})

# Replacement update (clears and re-adds all relationships)
entries.update(entry, {
    "people": ["Charlie"]  # Alice and Bob removed
})
```

## Common Patterns

### Consistent Interface

All managers implement these core methods (where applicable):

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

### DatabaseOperation Context Manager

All public methods wrap their logic in a `DatabaseOperation` context manager that handles logging, timing, and error conversion:

```python
from dev.database.decorators import DatabaseOperation
from dev.core.validators import DataValidator

def create(self, metadata):
    DataValidator.validate_required_fields(metadata, ["name"])
    with DatabaseOperation(self.logger, "create_person"):
        person = Person(name=metadata["name"])
        self.session.add(person)
        self.session.flush()
        return person
```

### Dependency Injection

Managers receive dependencies via constructor:

```python
manager = PersonManager(session, logger)
```

This enables:
- **Testability**: Mock dependencies for unit tests
- **Flexibility**: Use shared or isolated sessions
- **Consistency**: Centralized logging

### Manager Delegation

EntryManager delegates to specialized managers for complex entity resolution:

```python
class EntryManager(BaseManager):
    def __init__(self, session, logger):
        super().__init__(session, logger)
        self._person_mgr = PersonManager(session, logger)
        self._location_mgr = LocationManager(session, logger)
        self._event_mgr = EventManager(session, logger)
        self._poem_mgr = PoemManager(session, logger)
```

### Accent-Insensitive Name Matching

EntryManager uses `unicodedata` normalization for matching people and locations in scenes and threads against entry-level collections:

```python
# Matches: Sofía == Sofia, Lucía-Elena == Lucia Elena
person = self._find_person_in_entry("Sofia", entry)  # Finds "Sofía"
```

## Usage in PalimpsestDB

The main `PalimpsestDB` class initializes managers per session:

```python
class PalimpsestDB:
    def session_scope(self):
        session = self.Session()
        # Managers initialized per session
        self._tag_manager = TagManager(session, self.logger)
        self._person_manager = PersonManager(session, self.logger)
        self._event_manager = EventManager(session, self.logger)
        self._location_manager = LocationManager(session, self.logger)
        self._reference_manager = ReferenceManager(session, self.logger)
        self._poem_manager = PoemManager(session, self.logger)
        self._entry_manager = EntryManager(session, self.logger)
```

## Testing Managers

Each manager should have tests covering:

**Basic CRUD:**
```python
def test_create_tag(tag_manager):
    tag = tag_manager.get_or_create("test")
    assert tag.name == "test"
    assert tag.id is not None
```

**Relationships:**
```python
def test_link_unlink(tag_manager, entry):
    tag = tag_manager.get_or_create("python")
    tag_manager.link_to_entry(tag, entry)
    assert tag in entry.tags
    tag_manager.unlink_from_entry(tag, entry)
    assert tag not in entry.tags
```

**Error Handling:**
```python
def test_error_handling(tag_manager):
    with pytest.raises(ValidationError):
        tag_manager.create({"name": ""})  # Empty name
```

**Soft Delete** (for managers supporting it):
```python
def test_soft_delete_restore(person_manager):
    person = person_manager.get_or_create("Alice", lastname="Smith")
    person_manager.delete(person, deleted_by="admin", reason="Test")
    assert person.deleted_at is not None
    person_manager.restore(person)
    assert person.deleted_at is None
```

## See Also

- `dev/database/manager.py` - Main PalimpsestDB class
- `dev/database/decorators.py` - DatabaseOperation context manager
- `dev/database/models/` - SQLAlchemy model definitions
- `dev/database/managers/base_manager.py` - BaseManager with shared utilities
- `dev/database/managers/entity_manager.py` - Config-driven EntityManager base
