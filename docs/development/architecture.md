# Palimpsest Modular Architecture

**Last Updated**: 2025-11-29

---

## Overview

The Palimpsest codebase uses a modular architecture with clear separation of concerns. This document describes the module organization, design patterns, and how to work with the codebase.

### Core Principles

1. **Single Responsibility** - Each module has one clear purpose
2. **Backward Compatibility** - All existing APIs remain unchanged
3. **Domain Organization** - Modules grouped by functional domain
4. **Clear Dependencies** - Minimal coupling between modules
5. **Testability** - Each module can be tested independently

---

## Module Organization

### 1. Database CLI (`dev/database/cli/`)

**Purpose**: Database management commands organized by functional area

**Structure**:
```
dev/database/cli/
├── __init__.py          # Main CLI group, shared context
├── setup.py             # init, reset commands
├── migration.py         # Alembic migration commands
├── backup.py            # Backup and restore operations
├── query.py             # Data query commands
├── maintenance.py       # Cleanup, optimize, validate
├── export.py            # CSV/JSON export commands
├── tombstone.py         # Tombstone management
└── sync.py              # Sync state management
```

**Key Pattern**: Shared context via Click's `@click.pass_context`
- Database instance initialized once in `__init__.py`
- All subcommands access via `ctx.obj["db"]`
- Lazy loading of managers to reduce startup time

**Entry Point**: `metadb` → `dev.database.cli:cli`

**Example Usage**:
```bash
metadb init                    # Initialize database
metadb migration upgrade       # Run migrations
metadb backup                  # Create backup
metadb query show 2024-01-15   # Query entry
metadb tombstone list          # List tombstones
```

---

### 2. Database Models (`dev/database/models/`)

**Purpose**: SQLAlchemy ORM models organized by domain

**Structure**:
```
dev/database/models/
├── __init__.py          # Re-exports all models (backward compatibility)
├── base.py              # Base class, SoftDeleteMixin
├── associations.py      # Many-to-many relationship tables
├── enums.py             # Enumeration types
├── core.py              # SchemaInfo, Entry (central model)
├── geography.py         # MentionedDate, City, Location
├── entities.py          # Person, Alias, Tag
├── creative.py          # Reference, ReferenceSource, Event, Poem
└── sync.py              # AssociationTombstone, SyncState, EntitySnapshot
```

**Key Patterns**:
- **Base Module**: Shared infrastructure (Base, SoftDeleteMixin)
- **Associations Module**: All many-to-many tables in one place
- **Domain Grouping**: Related models together (geography, entities, creative)
- **Backward Compatibility**: `__init__.py` re-exports everything

**Import Examples**:
```python
# All imports still work unchanged
from dev.database.models import Entry, Person, Tag
from dev.database.models import Base, SoftDeleteMixin
from dev.database.models import ReferenceMode, ReferenceType

# Can also import from specific modules
from dev.database.models.core import Entry
from dev.database.models.entities import Person, Tag
from dev.database.models.enums import ReferenceMode
```

**Model Organization**:
- **base.py**: Foundation classes used by all models
- **enums.py**: Shared enumeration types
- **associations.py**: Pure association tables (no additional logic)
- **core.py**: Entry model (most important, most relationships)
- **geography.py**: Location-related models with temporal tracking
- **entities.py**: People and tags with soft delete support
- **creative.py**: References, events, poems with versioning
- **sync.py**: Multi-machine synchronization support

---

### 3. Pipeline CLI (`dev/pipeline/cli/`)

**Purpose**: Data pipeline commands organized by flow direction

**Structure**:
```
dev/pipeline/cli/
├── __init__.py          # Main pipeline CLI group
├── yaml2sql.py          # YAML → SQL (inbox, convert, sync-db)
├── sql2wiki.py          # SQL → Wiki (export-db, export-wiki, build-pdf)
├── wiki2sql.py          # Wiki → SQL (import-wiki)
└── maintenance.py       # Backup, status, validation
```

**Key Pattern**: Data flow organization
- Commands grouped by source → destination
- Clear pipeline directionality
- Shared configuration in main `__init__.py`

**Entry Point**: `plm` → `dev.pipeline.cli:cli`

**Example Usage**:
```bash
plm inbox                      # Process 750words inbox
plm sync-db                    # Sync YAML → Database
plm export-wiki                # Export entities to wiki
plm export-db --year 2024      # Export entries to markdown
plm build-pdf 2024             # Build PDF for year
plm import-wiki                # Import wiki → Database
```

---

### 4. Wiki Pages Builder (`dev/builders/wiki_pages/`)

**Purpose**: Wiki page generation with shared utilities

**Structure**:
```
dev/builders/wiki_pages/
├── __init__.py          # Public API exports
├── entries.py           # Entry pages with navigation
├── index.py             # Wiki homepage
├── stats.py             # Statistics dashboard
├── timeline.py          # Chronological timeline
├── analysis.py          # Entity relationship analysis
└── utils/
    ├── charts.py        # ASCII visualization functions
    ├── queries.py       # Database query helpers
    └── formatters.py    # Text/link formatting
```

**Key Patterns**:
- **Utility Extraction**: Common functions in `utils/` package
- **DRY Principle**: Reusable ASCII charts, formatters
- **Clear Public API**: Only page builders exported from `__init__.py`
- **Database Separation**: Queries isolated in `utils/queries.py`

**Import Examples**:
```python
# Public API - only page builders
from dev.builders.wiki_pages import (
    export_entries_with_navigation,
    export_index,
    export_stats,
    export_timeline,
    export_analysis_report
)

# Internal utilities (not exposed in public API)
from dev.builders.wiki_pages.utils.charts import ascii_bar_chart
from dev.builders.wiki_pages.utils.queries import get_entry_statistics
```

**Utility Functions**:
- **charts.py**: `ascii_bar_chart()`, `monthly_heatmap()`
- **queries.py**: `get_entry_statistics()`, `get_top_people()`, `get_tag_cloud()`
- **formatters.py**: `format_entity_link()`, `format_date_link()`, `format_count()`

---

### 5. Validators CLI (`dev/validators/cli/`)

**Purpose**: Validation commands organized by validation domain

**Structure**:
```
dev/validators/cli/
├── __init__.py          # Main validation CLI group
├── wiki.py              # Wiki link validation (check, orphans, stats)
├── database.py          # Database integrity (schema, migrations, constraints)
├── markdown.py          # Markdown file validation (frontmatter, links)
├── metadata.py          # Metadata parser compatibility (people, locations, dates)
└── consistency.py       # Cross-system consistency (existence, metadata, integrity)
```

**Key Pattern**: Domain-based validation
- Each validator focuses on one aspect of the system
- Comprehensive `all` command in each module
- Consistent error reporting across all validators

**Entry Point**: `validate` → `dev.validators.cli:cli`

**Example Usage**:
```bash
validate wiki check            # Check wiki links
validate wiki orphans          # Find orphaned pages
validate db schema             # Check database schema
validate db all                # All database checks
validate md frontmatter        # Validate YAML frontmatter
validate metadata people       # Validate people metadata
validate consistency all       # Cross-system consistency
```

---

### 6. MdEntry Dataclass Parsers (`dev/dataclasses/`)

**Purpose**: Separated parsing, export, and validation logic for journal entries

**Structure**:
```
dev/dataclasses/
├── md_entry.py              # Core dataclass (787 lines, down from 1,581)
├── md_entry_validator.py    # Validation logic
└── parsers/
    ├── __init__.py          # Parser exports
    ├── yaml_to_db.py        # YAML frontmatter → Database format
    └── db_to_yaml.py        # Database → YAML frontmatter export
```

**Key Components**:

1. **YamlToDbParser** (`yaml_to_db.py`):
   - Parses YAML frontmatter to database-compatible format
   - Handles complex field parsing (people, locations, dates, references, poems)
   - Supports alias resolution, name parsing, date context extraction
   - Methods: `parse_city_field()`, `parse_people_field()`, `parse_dates_field()`, etc.

2. **DbToYamlExporter** (`db_to_yaml.py`):
   - Exports database Entry ORM objects to YAML frontmatter format
   - Builds human-readable metadata from normalized database structures
   - Methods: `build_people_metadata()`, `build_dates_metadata()`, `build_references_metadata()`, etc.

3. **MdEntryValidator** (`md_entry_validator.py`):
   - Validates MdEntry structure and metadata
   - Checks required fields, date formats, word counts
   - Independent validation logic for testability

**Key Patterns**:
- **Parser Delegation**: `MdEntry` delegates to `YamlToDbParser` for YAML→DB conversion
- **Exporter Delegation**: `MdEntry.from_database()` uses `DbToYamlExporter`
- **Stateless Validators**: Validation logic separated from dataclass
- **Entry Date Context**: Parsers receive entry date for defaulting revision dates

**Import Examples**:
```python
# Core dataclass
from dev.dataclasses.md_entry import MdEntry

# Use parsers directly (advanced usage)
from dev.dataclasses.parsers import YamlToDbParser, DbToYamlExporter
from dev.dataclasses.md_entry_validator import MdEntryValidator

# Normal usage - parsers called internally
entry = MdEntry.from_file(Path("2024-01-15.md"))
db_meta = entry.to_database_metadata()  # Uses YamlToDbParser internally
```

**Benefits**:
- Reduced complexity in core dataclass
- Easier to test parsing logic independently
- Clear separation between YAML and database concerns
- Simplified validation testing
- Better code organization and navigation

**Module Structure**:
```
dev/dataclasses/
├── md_entry.py              # Core dataclass
├── md_entry_validator.py    # Validation logic
└── parsers/
    ├── yaml_to_db.py        # YAML→DB parsing logic
    └── db_to_yaml.py        # DB→YAML export logic
```

---

## Architecture Patterns

### Pattern 1: CLI Command Groups with Shared Context

**Used in**: Database CLI, Pipeline CLI, Validators CLI

**Implementation**:
```python
# __init__.py - Main CLI group
@click.group()
@click.option("--db-path", default=str(DB_PATH))
@click.pass_context
def cli(ctx, db_path):
    """Main CLI group"""
    ctx.ensure_object(dict)
    ctx.obj["db_path"] = Path(db_path)
    # Initialize shared resources
    ctx.obj["db"] = PalimpsestDB(...)

# Import and register subcommands
from .submodule import subcommand_group
cli.add_command(subcommand_group)

# submodule.py - Subcommand group
@click.group()
def subcommand_group():
    """Subcommand group"""
    pass

@subcommand_group.command()
@click.pass_context
def specific_command(ctx):
    """Use shared context"""
    db = ctx.obj["db"]
    # ... implementation
```

**Benefits**:
- Shared resources initialized once
- Consistent configuration across commands
- Easy testing with mock context

---

### Pattern 2: Domain-Organized Models

**Used in**: Database Models

**Implementation**:
```python
# models/__init__.py - Backward compatibility layer
from .base import Base, SoftDeleteMixin
from .core import Entry, SchemaInfo
from .entities import Person, Alias, Tag
# ... all other imports

__all__ = [
    "Base", "SoftDeleteMixin",
    "Entry", "SchemaInfo",
    "Person", "Alias", "Tag",
    # ... all other exports
]

# Existing code continues to work:
from dev.database.models import Entry, Person  # ✓ Works
```

**Benefits**:
- Logical organization by domain
- No breaking changes to existing code
- Clear module boundaries
- Easier navigation in large codebases

---

### Pattern 3: Utility Module Extraction

**Used in**: Wiki Pages Builder

**Implementation**:
```python
# utils/charts.py - Reusable utilities
def ascii_bar_chart(data: Dict[str, int], max_width: int = 20) -> List[str]:
    """Generate ASCII bar chart from data"""
    # ... implementation

# stats.py - Uses utility
from .utils.charts import ascii_bar_chart

def export_stats(session, wiki_dir):
    data = get_statistics(session)
    chart_lines = ascii_bar_chart(data["people_by_month"])
    # ... use chart_lines
```

**Benefits**:
- Eliminates code duplication
- Consistent formatting across pages
- Testable in isolation
- Clear separation: data logic vs. presentation

---

### Pattern 4: Entry Point Configuration

**Used in**: All CLI modules

**Configuration** (`pyproject.toml`):
```toml
[project.scripts]
metadb = "dev.database.cli:cli"
plm = "dev.pipeline.cli:cli"
validate = "dev.validators.cli:cli"
```

**Benefits**:
- Standard Python entry points
- Works with pip install
- Consistent command names
- Easy to discover commands

---

## Dependency Graph

```
Entry Points (metadb, plm, validate)
    ↓
CLI Modules (dev/*/cli/)
    ↓
Database Manager (dev/database/manager.py)
    ↓
Database Models (dev/database/models/)
    ↓
SQLAlchemy / Database
```

**Key Dependencies**:
- CLI modules depend on managers
- Managers depend on models
- Models depend on SQLAlchemy
- Minimal circular dependencies

---

## Design Decisions

### Decision 1: Backward Compatibility Over Perfect Design

**Rationale**:
- Large codebase with many import statements
- Changing imports would require touching many files
- Risk of breaking existing functionality

**Implementation**:
- `__init__.py` re-exports everything from submodules
- Old imports like `from dev.database.models import Entry` still work
- New code can use specific imports if desired

**Trade-off**:
- Slightly larger `__init__.py` files
- But: Zero breaking changes, smooth migration

---

### Decision 2: Functional vs. Type-Based Organization

**Chosen**: Functional organization (by what commands do)

**Alternatives Considered**:
- Type-based: `setup/`, `query/`, `export/` across all systems
- Functional: `database/`, `pipeline/`, `validators/` with internal groups

**Rationale**:
- Functional grouping matches user mental models
- Easier to find related commands
- Natural fit for Click command groups

---

### Decision 3: Utility Modules in Shared Package

**Chosen**: `utils/` package within relevant module

**Alternatives Considered**:
- Top-level `dev/utils/` for all utilities
- Inline functions in each module

**Rationale**:
- Keeps utilities close to usage
- Clear scope (only for this package)
- Reduces cross-package coupling

---

## Module Size Guidelines

Based on refactoring experience:

| Module Type | Target Size | Maximum Size |
|-------------|-------------|--------------|
| CLI command group | 100-200 lines | 300 lines |
| Model file | 150-250 lines | 400 lines |
| Utility module | 100-150 lines | 250 lines |
| Page builder | 150-300 lines | 400 lines |

**When to Split**:
- File exceeds 500 lines
- Module has multiple responsibilities
- Code duplication across functions
- Difficult to navigate/understand

---

## Testing Strategy

### Unit Testing

Each module should have corresponding test:
```
dev/database/cli/backup.py
tests/database/cli/test_backup.py
```

**Test Isolation**:
- Mock database connections
- Use Click's `CliRunner` for CLI tests
- Test each command independently

### Integration Testing

After refactoring:
- Verify all entry points work
- Test common workflows end-to-end
- Ensure backward compatibility

**Example**:
```python
def test_backward_compatible_imports():
    """Verify old imports still work"""
    from dev.database.models import Entry, Person
    assert Entry is not None
    assert Person is not None
```

---

## Migration Guide

### Adding New CLI Command

1. Identify appropriate command group module
2. Add command to that module
3. Command automatically registered via `cli.add_command()`

**Example**:
```python
# dev/database/cli/query.py
@query.command()
@click.argument("entry_id")
@click.pass_context
def details(ctx, entry_id):
    """Show entry details"""
    db = ctx.obj["db"]
    # ... implementation
```

### Adding New Model

1. Identify appropriate domain module
2. Add model class to that module
3. Add to `__init__.py` `__all__` list

**Example**:
```python
# dev/database/models/entities.py
class NewEntity(Base):
    __tablename__ = "new_entities"
    # ... fields

# dev/database/models/__init__.py
from .entities import Person, Alias, Tag, NewEntity

__all__ = [
    # ...
    "NewEntity",  # Add to exports
]
```

### Adding New Validator

1. Create new command in appropriate validator module
2. Follow existing validation patterns
3. Return consistent error format

**Example**:
```python
# dev/validators/cli/metadata.py
@metadata.command()
@click.pass_context
def events(ctx):
    """Validate events metadata"""
    # ... implementation
```

---

## Performance Considerations

### Import Time

**Lazy Imports**: Import heavy dependencies inside functions
```python
# Good - lazy import
@cli.command()
def export():
    from dev.builders.wiki_pages import export_stats
    export_stats()

# Avoid - eager import
from dev.builders.wiki_pages import export_stats  # Loaded immediately
```

### Module Loading

**Current Behavior**:
- Only loaded modules are imported
- `validate wiki` doesn't load database validator
- Entry point overhead: ~50-100ms

---

## Future Enhancements

### Potential Improvements

1. **Type Hints**: Add comprehensive type annotations
2. **Async Support**: For I/O-bound operations
3. **Plugin System**: Allow external command registration
4. **Better Error Messages**: Structured error reporting

### Anti-Patterns to Avoid

❌ **Don't**: Create circular dependencies between modules
❌ **Don't**: Put business logic in `__init__.py`
❌ **Don't**: Create utility modules with unrelated functions
❌ **Don't**: Break backward compatibility without deprecation

---

## Summary

The Palimpsest refactoring created a clean, modular architecture:

✅ **40+ focused modules** (average ~170 lines each)
✅ **Clear separation** of concerns
✅ **100% backward compatible**
✅ **Easy to extend** and maintain
✅ **Consistent patterns** across codebase

**Recent Improvements**:
- **2025-11-29**: MdEntry dataclass refactored (50% size reduction)
  - Extracted parsers: `YamlToDbParser`, `DbToYamlExporter`
  - Separated validation: `MdEntryValidator`
  - All 70 tests passing

**Key Takeaway**: Modular architecture improves maintainability without sacrificing compatibility.

---

**Last Updated**: 2025-11-29
**Maintained By**: Palimpsest Development Team
