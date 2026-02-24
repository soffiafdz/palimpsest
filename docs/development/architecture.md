# Palimpsest Modular Architecture

**Last Updated**: 2026-02-13

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
```

---

### 2. Database Models (`dev/database/models/`)

**Purpose**: SQLAlchemy ORM models organized by domain

**Structure**:
```
dev/database/models/
├── __init__.py          # Re-exports all models
├── base.py              # Base class, SoftDeleteMixin
├── associations.py      # Many-to-many relationship tables
├── enums.py             # Enumeration types
├── core.py              # SchemaInfo, Entry (central model)
├── geography.py         # City, Location
├── entities.py          # Person, PersonAlias, Tag, Theme
├── creative.py          # Reference, ReferenceSource, Poem, PoemVersion
├── analysis.py          # Scene, SceneDate, Event, Arc, Thread
├── manuscript.py        # Chapter, PersonCharacterMap, etc.
└── metadata.py          # NarratedDate, Motif
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
- **manuscript.py**: Chapters, characters, scenes, sources, references for manuscript
- **sync.py**: Multi-machine synchronization support

---

### 3. Pipeline CLI (`dev/pipeline/cli/`)

**Purpose**: Data pipeline commands organized by flow direction

**Structure**:
```
dev/pipeline/cli/
├── __init__.py          # Main pipeline CLI group
├── inbox.py             # Process 750words exports
├── convert.py           # TXT → Markdown conversion
├── import_metadata.py   # Metadata YAML → SQL (import journal metadata)
├── export_json.py       # SQL → JSON export
├── build_pdf.py         # PDF generation
├── maintenance.py       # Backup, status, validation
├── wiki.py              # Wiki generation, linting, sync, publishing
└── metadata_yaml.py     # YAML metadata export, import, validation
```

**Key Pattern**: Data flow organization
- Initial conversion: Raw exports → TXT → Markdown
- Metadata import: Metadata YAML → Database (one-time)
- Export: Database → JSON (for version control)
- Database is LOCAL ONLY (not version controlled)

**Entry Point**: `plm` → `dev.pipeline.cli:cli`

**Example Usage**:
```bash
plm inbox                      # Process 750words inbox
plm convert                    # TXT → Markdown + skeleton metadata YAML
plm import-metadata            # Metadata YAML → Database
plm export-json                # Database → JSON export
plm build-pdf 2024             # Generate PDFs for a year
```

---

### 4. Validators CLI (`dev/validators/cli/`)

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
validate db schema             # Check database schema
validate db all                # All database checks
validate md frontmatter        # Validate YAML frontmatter
validate metadata people       # Validate people metadata
validate consistency all       # Cross-system consistency
```

---

### 5. Pipeline Dataclasses (`dev/dataclasses/`)

**Purpose**: Data structures for pipeline stages

**Structure**:
```
dev/dataclasses/
├── txt_entry.py         # TXT file conversion dataclass
└── metadata_entry.py    # Metadata YAML structures
```

**Key Components**:

1. **TxtEntry** (`txt_entry.py`):
   - Parses formatted text files
   - Extracts word count, reading time
   - Handles text-to-markdown conversion

2. **MetadataEntry** (`metadata_entry.py`):
   - Represents metadata YAML structure
   - Validates metadata fields
   - Prepares data for database import

**Import Examples**:
```python
# Core dataclasses
from dev.dataclasses.txt_entry import TxtEntry
from dev.dataclasses.metadata_entry import MetadataEntry

# Normal usage
txt_entry = TxtEntry.from_file(Path("2024-01-15.txt"))
metadata = MetadataEntry.from_yaml(Path("metadata/2024/2024-01-15.yaml"))
```

---

### 6. Wiki System (`dev/wiki/`)

**Purpose**: Wiki generation, linting, sync, and publishing for journal and manuscript pages

**Structure**:
```
dev/wiki/
├── __init__.py          # Public API
├── renderer.py          # Jinja2 template rendering engine
├── exporter.py          # Database → wiki page generation orchestrator
├── parser.py            # Wiki → database ingestion (manuscript)
├── validator.py         # Wiki page validation and linting
├── sync.py              # Bidirectional manuscript sync cycle
├── publisher.py         # Wiki → Quartz publishing with frontmatter injection
├── metadata.py          # YAML metadata export/import/validation
├── context.py           # Context builder for template rendering
├── configs.py           # Entity export configurations
├── filters.py           # Custom Jinja2 filters (wikilink, date, etc.)
├── mdit_wikilink.py     # markdown-it-py wikilink plugin
└── templates/           # Jinja2 templates for all entity types
    ├── journal/         # Entry, person, location, event, etc.
    ├── manuscript/      # Chapter, character, scene, part
    └── indexes/         # Main, people, locations, entries
```

**Key Pattern**: Template-based rendering with pre-computed context
- Context builders query DB and compute aggregates
- Templates are dumb renderers — no queries, no computation
- Custom Jinja2 filters handle wiki link formatting and date display
- Quartz frontmatter injected during publish, not during generation

**Entry Points**:
- `plm wiki` → `dev.pipeline.cli.wiki` (generate, lint, sync, publish)
- `plm metadata` → `dev.pipeline.cli.metadata_yaml` (export, import, validate, list-entities)

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

### Pattern 3: Template-Based Rendering

**Used in**: Wiki Export System

**Implementation**:
```python
# renderer.py - Jinja2 template rendering
class WikiRenderer:
    def __init__(self, template_dir: Path):
        self.env = Environment(loader=FileSystemLoader(template_dir))
        self.env.filters["wiki_link"] = format_wiki_link

    def render(self, template_name: str, context: dict) -> str:
        template = self.env.get_template(template_name)
        return template.render(**context)

# exporter.py - Uses renderer
class WikiExporter:
    def export_person(self, person: Person) -> None:
        content = self.renderer.render("person.jinja2", {"person": person})
        self._write_page(self.wiki_dir / "people" / f"{person.slug}.wiki", content)
```

**Benefits**:
- Separation of logic and presentation
- Non-programmers can edit templates
- Consistent formatting via shared filters
- Easy to add new entity types

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
Wiki System (dev/wiki/)  ←→  Jinja2 Templates
    ↓
Database Manager (dev/database/manager.py)
    ↓
Database Models (dev/database/models/)
    ↓
SQLAlchemy / Database
```

**Key Dependencies**:
- CLI modules depend on managers and wiki system
- Wiki system depends on managers and Jinja2
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

**Key Takeaway**: Modular architecture improves maintainability without sacrificing compatibility.

---

**Last Updated**: 2026-02-13
**Maintained By**: Palimpsest Development Team
