# Palimpsest v2: Complete Rewrite Workplan

## Executive Summary

**Current state**: 147 Python files, 41,500+ lines of code
**Proposed state**: ~15 Python files, ~3,500 lines of code
**Reduction**: ~92% code reduction

The current implementation is massively over-engineered for what is fundamentally a personal journaling tool. This document proposes a complete rewrite that preserves data compatibility while eliminating unnecessary complexity.

---

## Analysis: What's Wrong With the Current Code

### 1. Enterprise Patterns for a Personal Tool

| Feature | Lines | Purpose | Needed? |
|---------|-------|---------|---------|
| Health Monitor | 793 | Database health checks | No |
| Query Analytics | 586 | Query performance tracking | No |
| Query Optimizer | 668 | Query optimization | No |
| Sync State Manager | 445 | Multi-machine sync state | Overkill |
| Tombstone Manager | 424 | Deletion tracking | Overkill |
| **Total** | **2,916** | | |

### 2. Manager Class Explosion

| Manager | Lines | Could Be |
|---------|-------|----------|
| entry_manager.py | 1,310 | ~200 lines in db.py |
| simple_manager.py | 969 | ~100 lines in db.py |
| person_manager.py | 850 | ~80 lines in db.py |
| location_manager.py | 687 | ~60 lines in db.py |
| poem_manager.py | 633 | ~50 lines in db.py |
| reference_manager.py | 628 | ~50 lines in db.py |
| manuscript_manager.py | 613 | ~50 lines in db.py |
| base_manager.py | 256 | Unnecessary |
| **Total** | **6,278** | **~600 lines** |

### 3. Validation Layers

| Validator | Lines | Purpose |
|-----------|-------|---------|
| frontmatter.py | 1,076 | YAML validation |
| consistency.py | 610 | Cross-system checks |
| md.py | 590 | Markdown validation |
| db.py | 414 | Database integrity |
| wiki.py | 327 | Wiki link validation |
| schema.py | 313 | Schema validation |
| **Total** | **3,369** | One 300-line validator would suffice |

### 4. Unnecessary Abstractions

- **BaseManager → SimpleManager → EntityManager** hierarchy
- **Separate CLI modules** with context passing
- **Separate wiki dataclasses** for each entity type
- **Multiple parsing formats** for names, dates, locations

---

## What the System Actually Needs to Do

### Core Operations (Priority Order)

1. **Parse** YAML frontmatter from markdown files
2. **Store** entities in SQLite (entries, people, locations, tags, etc.)
3. **Generate** wiki pages from the database
4. **Search** entries by various criteria
5. **Import** wiki notes back to database
6. **Validate** YAML frontmatter for errors

### What It Doesn't Need

- Soft delete with tombstones (just delete)
- Multi-machine conflict resolution (use git)
- Health monitoring (if it breaks, fix it)
- Query analytics (not a production service)
- Multiple manager classes (one db module)
- Separate validation layers (one validator)

---

## Proposed v2 Architecture

### Directory Structure

```
palimpsest/
├── data/                    # UNTOUCHED - user data
├── dev/
│   ├── __init__.py
│   ├── models.py           # ~400 lines - All SQLAlchemy models
│   ├── db.py               # ~600 lines - All database operations
│   ├── parser.py           # ~500 lines - YAML frontmatter parsing
│   ├── wiki.py             # ~600 lines - Wiki generation/import
│   ├── search.py           # ~200 lines - Search functionality
│   ├── cli.py              # ~400 lines - All CLI commands
│   ├── validators.py       # ~300 lines - Frontmatter validation
│   ├── config.py           # ~100 lines - Configuration
│   └── utils.py            # ~200 lines - Shared utilities
├── tests/
│   ├── test_parser.py
│   ├── test_db.py
│   ├── test_wiki.py
│   ├── test_search.py
│   └── conftest.py
└── docs/
```

**Total: ~3,500 lines** (down from 41,500)

### Module Responsibilities

#### `models.py` (~400 lines)

```python
# All SQLAlchemy models in one file
# Simple, no soft-delete mixins, no complex inheritance

class Entry(Base):
    __tablename__ = "entries"
    date = Column(Date, primary_key=True)
    word_count = Column(Integer)
    reading_time = Column(Float)
    epigraph = Column(Text)
    epigraph_attribution = Column(String)
    notes = Column(Text)
    body = Column(Text)
    file_path = Column(String)
    content_hash = Column(String)  # For change detection

    # Relationships
    people = relationship("Person", secondary=entry_people)
    locations = relationship("Location", secondary=entry_locations)
    # ... etc

class Person(Base):
    __tablename__ = "people"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    full_name = Column(String)
    notes = Column(Text)

# ... City, Location, Tag, Event, Reference, Poem
```

#### `db.py` (~600 lines)

```python
# All database operations - no manager classes

class Database:
    def __init__(self, path: Path):
        self.engine = create_engine(f"sqlite:///{path}")
        self.Session = sessionmaker(bind=self.engine)

    # Entry operations
    def get_entry(self, date: date) -> Optional[Entry]: ...
    def save_entry(self, entry: Entry) -> None: ...
    def delete_entry(self, date: date) -> None: ...

    # Person operations
    def get_or_create_person(self, name: str, full_name: str = None) -> Person: ...

    # Location operations
    def get_or_create_location(self, name: str, city: str) -> Location: ...

    # ... all other operations

    # Bulk operations
    def sync_from_yaml(self, entries: List[ParsedEntry]) -> SyncResult: ...
```

#### `parser.py` (~500 lines)

```python
# Parse YAML frontmatter - one consistent format

@dataclass
class ParsedEntry:
    date: date
    body: str
    word_count: int
    reading_time: float
    city: Optional[str] = None
    locations: List[str] = field(default_factory=list)
    people: List[ParsedPerson] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    events: List[str] = field(default_factory=list)
    dates: List[ParsedDate] = field(default_factory=list)
    references: List[ParsedReference] = field(default_factory=list)
    poems: List[ParsedPoem] = field(default_factory=list)
    epigraph: Optional[str] = None
    epigraph_attribution: Optional[str] = None
    notes: Optional[str] = None

def parse_file(path: Path) -> ParsedEntry:
    """Parse a markdown file with YAML frontmatter."""
    ...

def parse_people(raw: List) -> List[ParsedPerson]:
    """Parse people field with all format variations."""
    ...
```

#### `wiki.py` (~600 lines)

```python
# Wiki generation and import

def export_wiki(db: Database, wiki_dir: Path) -> None:
    """Generate all wiki pages from database."""
    export_entries(db, wiki_dir)
    export_people(db, wiki_dir)
    export_locations(db, wiki_dir)
    export_tags(db, wiki_dir)
    export_events(db, wiki_dir)
    export_index(db, wiki_dir)

def import_wiki_notes(db: Database, wiki_dir: Path) -> None:
    """Import wiki notes back to database."""
    ...

def generate_person_page(person: Person, entries: List[Entry]) -> str:
    """Generate markdown for a person's wiki page."""
    ...
```

#### `search.py` (~200 lines)

```python
# Simple search functionality

@dataclass
class SearchResult:
    date: date
    snippet: str
    matches: Dict[str, List[str]]

def search(
    db: Database,
    query: str = None,
    person: str = None,
    tag: str = None,
    city: str = None,
    date_from: date = None,
    date_to: date = None,
) -> List[SearchResult]:
    """Search entries with filters."""
    ...
```

#### `cli.py` (~400 lines)

```python
# All commands in one file

@click.group()
def cli():
    """Palimpsest - structured journaling."""
    pass

@cli.command()
def sync():
    """Sync YAML files to database."""
    ...

@cli.command()
def wiki():
    """Generate wiki from database."""
    ...

@cli.command()
@click.argument("query", required=False)
@click.option("--person", "-p")
@click.option("--tag", "-t")
def search(query, person, tag):
    """Search entries."""
    ...

@cli.command()
def validate():
    """Validate YAML frontmatter."""
    ...

@cli.command()
def stats():
    """Show database statistics."""
    ...
```

#### `validators.py` (~300 lines)

```python
# Single validation module

@dataclass
class ValidationError:
    file: Path
    line: int
    field: str
    message: str
    severity: str  # "error" or "warning"

def validate_file(path: Path) -> List[ValidationError]:
    """Validate a single markdown file."""
    ...

def validate_all(data_dir: Path) -> List[ValidationError]:
    """Validate all markdown files."""
    ...
```

---

## Implementation Phases

### Phase 1: Core Foundation (Week 1)

**Goal**: Working sync and search

1. **Create `models.py`**
   - Define all SQLAlchemy models
   - Simple relationships, no mixins
   - Alembic migration from current schema

2. **Create `db.py`**
   - Basic CRUD operations
   - `sync_from_yaml()` for bulk import
   - Transaction management

3. **Create `parser.py`**
   - Parse YAML frontmatter
   - Handle all current format variations
   - Return dataclasses

4. **Create basic `cli.py`**
   - `plm sync` command
   - `plm stats` command

**Deliverable**: Can sync existing YAML files to new database

### Phase 2: Wiki Generation (Week 2)

**Goal**: Full wiki export

1. **Create `wiki.py`**
   - Export all entity types
   - Generate index page
   - Import wiki notes

2. **Extend `cli.py`**
   - `plm wiki export` command
   - `plm wiki import` command

**Deliverable**: Can generate wiki from database

### Phase 3: Search and Validation (Week 3)

**Goal**: Complete functionality

1. **Create `search.py`**
   - Full-text search
   - Filter by person, tag, date, etc.

2. **Create `validators.py`**
   - Frontmatter validation
   - Relationship validation

3. **Extend `cli.py`**
   - `plm search` command
   - `plm validate` command

**Deliverable**: Feature-complete CLI

### Phase 4: Testing and Polish (Week 4)

**Goal**: Production-ready

1. **Write tests**
   - Parser tests
   - Database tests
   - Wiki tests
   - CLI integration tests

2. **Documentation**
   - Update all docs
   - Remove obsolete docs

3. **Migration script**
   - Migrate existing database
   - Preserve all data

**Deliverable**: Production-ready v2

---

## What Gets Deleted

### Entire Directories

```
dev/database/managers/       # 6,278 lines → replaced by db.py
dev/database/cli/            # ~1,500 lines → replaced by cli.py
dev/validators/              # 3,369 lines → replaced by validators.py
dev/validators/cli/          # ~500 lines → replaced by cli.py
dev/builders/wiki_pages/     # ~1,500 lines → replaced by wiki.py
dev/dataclasses/             # ~2,500 lines → replaced by parser.py
dev/pipeline/                # ~2,500 lines → replaced by cli.py
dev/core/                    # ~1,500 lines → simplified
```

### Individual Files

```
dev/database/health_monitor.py      # 793 lines - DELETE
dev/database/query_analytics.py     # 586 lines - DELETE
dev/database/query_optimizer.py     # 668 lines - DELETE
dev/database/sync_state_manager.py  # 445 lines - DELETE
dev/database/tombstone_manager.py   # 424 lines - DELETE
dev/database/export_manager.py      # 692 lines - SIMPLIFY
dev/database/manager.py             # 723 lines - REPLACE with db.py
dev/database/models_manuscript.py   # 634 lines - MERGE into models.py
dev/builders/pdfbuilder.py          # 568 lines - KEEP if needed, else DELETE
dev/builders/txtbuilder.py          # 518 lines - KEEP if needed, else DELETE
```

---

## Data Compatibility

### Preserved

- **YAML frontmatter schema** - All existing files will parse correctly
- **Database schema** - Migration script will preserve data
- **Wiki structure** - Same directories and file naming

### Changed

- **CLI commands** - Simplified interface
- **Internal APIs** - Complete rewrite

---

## Risk Assessment

### Low Risk

- Parser rewrite - well-defined input format
- Wiki generation - straightforward templating
- Search - simple SQL queries

### Medium Risk

- Database migration - need careful testing
- Complex YAML formats - edge cases in parsing

### Mitigations

1. **Comprehensive test suite** for parser
2. **Migration script** tested on copy of data
3. **Rollback plan** - keep v1 code until v2 stable

---

## Success Criteria

1. All existing YAML files parse correctly
2. All existing data preserved in database
3. Wiki generation produces same output
4. Search returns same results
5. 90%+ code reduction achieved
6. Test coverage > 80%

---

## Questions for Discussion

1. **PDF/TXT builders** - Are these used? Keep or delete?
2. **Manuscript features** - Keep full support or simplify?
3. **Sync state/tombstones** - Any actual multi-machine use case?
4. **Neovim plugin** - Keep as-is or simplify?

---

## Next Steps

1. Review and approve this plan
2. Create feature branch for v2
3. Begin Phase 1 implementation
4. Regular check-ins at phase boundaries
