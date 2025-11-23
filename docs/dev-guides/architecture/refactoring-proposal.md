# Palimpsest Codebase Refactoring Proposal

**Date**: 2025-11-23
**Status**: Proposed (Not Started)
**Context**: Seven Python files have grown beyond 1,000 lines and need refactoring for maintainability

---

## Executive Summary

This document outlines a comprehensive refactoring plan for large Python modules in the Palimpsest project. The goal is to improve code organization, readability, maintainability, and testability by splitting monolithic files into focused, single-responsibility modules.

### Files Analyzed

1. `dev/database/cli.py` - 1,228 lines (HIGH PRIORITY)
2. `dev/database/manager.py` - 1,150 lines (MEDIUM PRIORITY)
3. `dev/builders/wiki_pages.py` - 1,155 lines (MEDIUM PRIORITY)
4. `dev/pipeline/cli.py` - ~1,000 lines (MEDIUM-HIGH PRIORITY)
5. `dev/database/models.py` - ~800 lines (LOW PRIORITY)
6. `dev/validators/cli.py` - ~600 lines (LOW PRIORITY)
7. `dev/dataclasses/md_entry.py` - ~400 lines (NO ACTION NEEDED)

---

## Detailed Refactoring Plans

### 1. dev/database/cli.py (1,228 lines)

**Priority**: HIGH
**Effort**: 4-6 hours
**Risk**: Low

#### Current Issues

- Single massive file with 8 command groups and 30+ commands
- Repetitive database context setup (`get_db()`)
- Hard-coded paths repeated across commands
- Mixed concerns (backup, migration, tombstone, sync, query, export)
- Difficult to navigate and maintain

#### Proposed Structure

```
dev/database/cli/
├── __init__.py          # Main CLI group + shared context setup
├── setup.py             # init, reset commands
├── migration.py         # create, upgrade, downgrade, status, history
├── backup.py            # backup, backups, restore
├── query.py             # show, years, months, batches
├── maintenance.py       # cleanup, optimize, validate, analyze
├── export.py            # export csv, export json
├── tombstone.py         # tombstone list/stats/cleanup/remove
└── sync.py              # sync conflicts/resolve/stats/status
```

#### Shared Context Pattern

```python
# dev/database/cli/__init__.py
import click
from pathlib import Path
from dev.database.manager import PalimpsestDB

# Shared options decorator
def common_db_options(f):
    """Common database options for all commands"""
    @click.option("--db-path", type=click.Path(), default=str(DB_PATH))
    @click.option("--alembic-dir", type=click.Path(), default=str(ALEMBIC_DIR))
    @click.option("--log-dir", type=click.Path(), default=str(LOG_DIR))
    @click.option("--backup-dir", type=click.Path(), default=str(BACKUP_DIR))
    @click.option("--verbose", is_flag=True)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return f(ctx, *args, **kwargs)
    return wrapper

def get_db(ctx) -> PalimpsestDB:
    """Get or create database instance from context"""
    if "db" not in ctx.obj:
        ctx.obj["db"] = PalimpsestDB(...)
    return ctx.obj["db"]

@click.group()
@common_db_options
def cli(ctx, db_path, alembic_dir, log_dir, backup_dir, verbose):
    """Palimpsest Database Management CLI"""
    ctx.ensure_object(dict)
    ctx.obj.update({
        "db_path": Path(db_path),
        "alembic_dir": Path(alembic_dir),
        "log_dir": Path(log_dir),
        "backup_dir": Path(backup_dir),
        "verbose": verbose,
    })

# Import and register command groups
from .setup import setup_group
from .migration import migration_group
from .backup import backup_group
from .query import query_group
from .maintenance import maintenance_group
from .export import export_group
from .tombstone import tombstone_group
from .sync import sync_group

cli.add_command(setup_group)
cli.add_command(migration_group)
# ... etc
```

#### Example Module: migration.py

```python
# dev/database/cli/migration.py
import click
from . import get_db

@click.group(name="migration")
def migration_group():
    """Database migration commands"""
    pass

@migration_group.command(name="create")
@click.argument("message")
@click.pass_context
def create_migration(ctx, message):
    """Create a new database migration"""
    db = get_db(ctx)
    # ... implementation

@migration_group.command(name="upgrade")
@click.option("--revision", default="head")
@click.pass_context
def upgrade_migration(ctx, revision):
    """Upgrade database to a revision"""
    db = get_db(ctx)
    # ... implementation

# ... other migration commands
```

#### Migration Steps

1. Create `dev/database/cli/` directory
2. Create `__init__.py` with shared context and CLI group
3. Move commands one group at a time:
   - Start with `setup.py` (simplest, 2 commands)
   - Then `migration.py`, `backup.py`, etc.
   - Test after each module
4. Update `pyproject.toml` entry point:
   ```toml
   [project.scripts]
   metadb = "dev.database.cli:cli"
   ```
5. Run full test suite after each module migration
6. Delete original `cli.py` when all commands migrated
7. Update documentation references

#### Benefits

- **Improved Manageability**: Each file reduced to ~100-200 lines, making them easier to read, understand, and manage.
- **Enhanced Testability**: Isolated concerns mean each command group can be tested independently, reducing test complexity and improving reliability.
- **Clearer Code Organization**: Provides clearer ownership of commands and improves navigation for developers, reducing cognitive load when working on specific CLI functionalities.
- **Increased Reusability**: Centralized command utilities in `__init__.py` promote code reuse and consistency across the CLI.
- **Future Scalability**: Simplifies the process of adding new command groups or modifying existing ones without impacting other functionalities.
- **Better Developer Experience**: Improved IDE navigation and autocompletion due to modular structure.

---

### 2. dev/builders/wiki_pages.py (1,155 lines)

**Priority**: MEDIUM
**Effort**: 3-4 hours
**Risk**: Low

#### Current Issues

- Four large special page builders (index, stats, timeline, analysis)
- Each function is 200-400 lines with repetitive patterns
- Shared visualization logic (ASCII bar charts) duplicated across functions
- Database queries embedded in presentation logic
- Hard to test individual components

#### Proposed Structure

```
dev/builders/wiki_pages/
├── __init__.py          # Public exports for backward compatibility
├── index.py             # export_index() (~200 lines)
├── stats.py             # export_stats() (~300 lines)
├── timeline.py          # export_timeline() (~150 lines)
├── analysis.py          # export_analysis_report() (~300 lines)
├── entries.py           # export_entries_with_navigation() (~150 lines)
└── utils/
    ├── __init__.py
    ├── charts.py        # ASCII bar/heatmap generators
    ├── queries.py       # Database query helpers
    └── formatters.py    # Link/date formatting utilities
```

#### Extract Shared Utilities

**charts.py** - Reusable visualization generators:
```python
# dev/builders/wiki_pages/utils/charts.py
from typing import Dict, List

def ascii_bar_chart(
    data: Dict[str, int],
    max_width: int = 20,
    empty_char: str = "░",
    fill_char: str = "█"
) -> List[str]:
    """
    Generate ASCII bar chart lines from data.

    Args:
        data: Dictionary of label -> count
        max_width: Maximum bar width in characters
        empty_char: Character for empty space
        fill_char: Character for filled space

    Returns:
        List of formatted chart lines
    """
    max_count = max(data.values()) if data else 1
    lines = []

    for label, count in data.items():
        bar_length = int((count / max_count) * max_width) if max_count > 0 else 0
        bar = fill_char * bar_length if bar_length > 0 else empty_char
        lines.append(f"{label:12s} {bar:20s} ({count})")

    return lines

def monthly_heatmap(entries_by_month: Dict[str, int], months: int = 12) -> List[str]:
    """Generate monthly activity heatmap"""
    # ... implementation
```

**queries.py** - Centralized database queries:
```python
# dev/builders/wiki_pages/utils/queries.py
from sqlalchemy import select, func
from typing import List, Dict
from dev.database.models import Entry, Person, Tag

def get_entry_statistics(session) -> Dict[str, int]:
    """Get comprehensive entry statistics"""
    entries = session.execute(select(Entry).order_by(Entry.date)).scalars().all()

    return {
        "total_entries": len(entries),
        "total_words": sum(e.word_count or 0 for e in entries),
        "first_date": entries[0].date if entries else None,
        "last_date": entries[-1].date if entries else None,
    }

def get_top_people(session, limit: int = 10) -> List[tuple]:
    """Get top N most mentioned people with counts"""
    people = session.execute(select(Person)).scalars().all()
    people_with_counts = [(p, len(p.entries)) for p in people]
    people_with_counts.sort(key=lambda x: (-x[1], x[0].name))
    return people_with_counts[:limit]
```

#### Migration Steps

1. Create directory structure
2. Extract utilities first (`utils/charts.py`, `utils/queries.py`, `utils/formatters.py`)
3. Move page builders one at a time, updating to use utilities:
   - `entries.py` (custom export function)
   - `index.py` (homepage)
   - `stats.py` (statistics dashboard)
   - `timeline.py` (timeline view)
   - `analysis.py` (analysis report)
4. Create `__init__.py` with public API:
   ```python
   # dev/builders/wiki_pages/__init__.py
   from .entries import export_entries_with_navigation
   from .index import export_index
   from .stats import export_stats
   from .timeline import export_timeline
   from .analysis import export_analysis_report

   __all__ = [
       "export_entries_with_navigation",
       "export_index",
       "export_stats",
       "export_timeline",
       "export_analysis_report",
   ]
   ```
5. Update imports in `dev/pipeline/sql2wiki.py`
6. Test each special page export
7. Delete original `wiki_pages.py`

#### Benefits

- **Modular Design**: Each page builder resides in an isolated, focused file, significantly improving readability and maintainability.
- **Enhanced Reusability**: Common functionalities like chart/visualization utilities can be reused across all wiki pages, reducing code duplication and ensuring consistency.
- **Simplified Extension**: Adding new special wiki pages becomes much easier, requiring only the creation of a new module rather than modifying a monolithic file.
- **Improved Testability**: Database query logic is decoupled from presentation logic, allowing for independent testing and more robust unit tests.
- **Clear Separation of Concerns**: Clearly separates data retrieval, business logic, and presentation, making the codebase easier to understand and evolve.
- **Higher Test Coverage**: The modular structure naturally encourages and facilitates better unit test coverage for individual components.

---

### 3. dev/database/manager.py (1,150 lines)

**Priority**: MEDIUM
**Effort**: 6-8 hours
**Risk**: Medium (session management complexity)

#### Current Issues

- Large `PalimpsestDB` class orchestrating multiple concerns
- Service components (BackupManager, HealthMonitor, ExportManager, QueryAnalytics) embedded
- Mix of database management + service coordination
- Static helper methods could be separate utilities
- Difficult to test individual services in isolation

#### Proposed Structure

```
dev/database/
├── core/
│   ├── __init__.py
│   ├── manager.py       # Core PalimpsestDB class (~300 lines)
│   ├── session.py       # Session management + context manager
│   └── entity_loaders.py # Lazy-load manager properties
├── services/
│   ├── __init__.py
│   ├── backup.py        # BackupManager
│   ├── health.py        # HealthMonitor
│   ├── export.py        # ExportManager
│   └── analytics.py     # QueryAnalytics
├── helpers/
│   ├── __init__.py
│   └── entry_callbacks.py # Static Entry helper methods
└── manager.py           # Backward compatibility re-export
```

#### Refactored Core Manager

```python
# dev/database/core/manager.py
from typing import Optional
from sqlalchemy import create_engine
from pathlib import Path

from .session import SessionManager
from .entity_loaders import EntityManagerLoader
from dev.database.services import (
    BackupManager,
    HealthMonitor,
    ExportManager,
    QueryAnalytics,
)

class PalimpsestDB:
    """
    Core database manager for Palimpsest journal system.

    Coordinates entity managers, services, and database operations.
    Simplified to focus on database connection and manager coordination.
    """

    def __init__(
        self,
        db_path: Path,
        alembic_dir: Path,
        log_dir: Path,
        backup_dir: Path,
        enable_auto_backup: bool = True,
    ):
        self.db_path = Path(db_path)
        self.alembic_dir = Path(alembic_dir)

        # Initialize core components
        self.logger = PalimpsestLogger(log_dir, "palimpsest_db")
        self.engine = create_engine(f"sqlite:///{self.db_path}")

        # Initialize services
        self.backup_manager = BackupManager(db_path, backup_dir, self.logger)
        self.health_monitor = HealthMonitor(self.engine, self.logger)
        self.export_manager = ExportManager(self.logger)
        self.query_analytics = QueryAnalytics(self.logger)

        # Session and entity manager coordination
        self._session_manager = SessionManager(self.engine)
        self._entity_loader = EntityManagerLoader(self.logger)

        # Auto-backup
        if enable_auto_backup:
            self.backup_manager.auto_backup()

    def session_scope(self):
        """Delegate to SessionManager"""
        return self._session_manager.session_scope(self._entity_loader)

    # Properties for entity managers (delegated to loader)
    @property
    def tags(self):
        return self._entity_loader.tags

    @property
    def people(self):
        return self._entity_loader.people

    # ... other manager properties
```

#### Session Management Module

```python
# dev/database/core/session.py
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker, Session

class SessionManager:
    """Manages database sessions and lifecycle"""

    def __init__(self, engine):
        self.engine = engine
        self.SessionLocal = sessionmaker(bind=engine)

    @contextmanager
    def session_scope(self, entity_loader):
        """
        Provide a transactional scope around database operations.

        Initializes entity managers for the session and handles
        commit/rollback automatically.
        """
        session = self.SessionLocal()
        try:
            # Initialize entity managers for this session
            entity_loader.initialize_managers(session)
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise
        finally:
            entity_loader.clear_managers()
            session.close()
```

#### Migration Steps

1. **Phase 1: Extract services** (2-3 hours)
   - Create `dev/database/services/` directory
   - Move BackupManager, HealthMonitor, ExportManager, QueryAnalytics
   - Update imports in manager.py
   - Test service functionality

2. **Phase 2: Extract session management** (2 hours)
   - Create `dev/database/core/session.py`
   - Move session_scope logic
   - Test session lifecycle

3. **Phase 3: Extract entity loader** (1-2 hours)
   - Create `dev/database/core/entity_loaders.py`
   - Move lazy-load manager properties
   - Test manager initialization

4. **Phase 4: Simplify core manager** (1-2 hours)
   - Move simplified PalimpsestDB to `core/manager.py`
   - Create backward-compatible `manager.py` re-export
   - Update all imports across codebase

5. **Phase 5: Extract helpers** (1 hour)
   - Move static Entry callback methods to `helpers/entry_callbacks.py`
   - Update references in EntryManager

6. **Testing and validation** (1 hour)
   - Full integration test suite
   - Verify all CLI commands still work
   - Check yaml2sql, sql2wiki pipelines

#### Benefits

- **Reduced Complexity**: The main `PalimpsestDB` class is significantly reduced (~300 lines), focusing solely on core coordination rather than monolithic functionality, improving its comprehensibility.
- **Improved Testability & Reusability**: Service components become independently testable units, leading to more robust tests and easier reuse across different parts of the application.
- **Clear Separation of Concerns**: Enforces a distinct separation between data access, business logic, and utility functions, making the codebase more organized and easier to navigate.
- **Isolated Session Management**: Database session management is decoupled into its own module, simplifying debugging of transaction-related issues.
- **Independent Evolution**: Services can evolve and be updated independently without affecting the core database manager, promoting agile development.
- **Enhanced Testability with DI**: Facilitates better dependency injection, making it easier to mock services during testing and improving overall test coverage.

---

### 4. dev/pipeline/cli.py (~1,000 lines)

**Priority**: MEDIUM-HIGH
**Effort**: 3-4 hours
**Risk**: Low

#### Current Issues

- Multiple pipeline commands (yaml2sql, sql2wiki, wiki2sql, etc.)
- Repetitive setup/teardown patterns
- Shared configuration across commands
- Mixed concerns (different data flow directions)

#### Proposed Structure

```
dev/pipeline/cli/
├── __init__.py          # Main CLI group + shared context
├── yaml2sql.py          # YAML → SQL commands (sync, update)
├── sql2wiki.py          # SQL → Wiki commands (export entities, special pages)
├── wiki2sql.py          # Wiki → SQL commands (import entries, notes)
├── backup.py            # Backup/restore commands
└── common.py            # Shared options, validators, utilities
```

#### Shared Utilities

```python
# dev/pipeline/cli/common.py
import click
from pathlib import Path

def common_pipeline_options(f):
    """Common options for pipeline commands"""
    @click.option("--db-path", type=click.Path(), default=str(DB_PATH))
    @click.option("--wiki-dir", type=click.Path(), default=str(WIKI_DIR))
    @click.option("--journal-dir", type=click.Path(), default=str(JOURNAL_DIR))
    @click.option("--force", is_flag=True, help="Force overwrite")
    @click.option("--verbose", is_flag=True)
    @click.pass_context
    def wrapper(ctx, *args, **kwargs):
        return f(ctx, *args, **kwargs)
    return wrapper

def validate_paths(ctx):
    """Validate required paths exist"""
    # Common validation logic
    pass
```

#### Migration Steps

1. Create `dev/pipeline/cli/` directory
2. Create `common.py` with shared utilities
3. Create `__init__.py` with main CLI group
4. Move commands by direction:
   - `yaml2sql.py` - YAML to database sync
   - `sql2wiki.py` - Database to wiki export
   - `wiki2sql.py` - Wiki to database import
   - `backup.py` - Backup operations
5. Update entry point in `pyproject.toml`
6. Test each pipeline direction
7. Delete original `cli.py`

#### Benefits

- **Clearer Structure**: Commands are separated by data flow direction (YAML → SQL, SQL → Wiki, etc.), making the pipeline's logic more intuitive and easier to follow.
- **Reduced Duplication**: Shared utilities centralized in `common.py` eliminate repetitive code, improving maintainability and consistency.
- **Improved Readability**: Each command file is kept concise (~150-250 lines), enhancing readability and reducing cognitive overhead.
- **Simplified Maintenance**: Modularization makes it easier to understand, debug, and update specific parts of the pipeline without affecting others.
- **Increased Extensibility**: New pipeline directions or commands can be added easily by creating new modules, promoting a scalable architecture.

---

### 5. dev/database/models.py (~800 lines)

**Priority**: LOW
**Effort**: 2-3 hours
**Risk**: Very Low

#### Current Issues

- Many SQLAlchemy model classes in one file
- Models from different domains (journal vs. manuscript vs. sync)
- Still manageable but growing

#### Proposed Structure

```
dev/database/models/
├── __init__.py          # Import all models for backward compatibility
├── base.py              # Base declarative class
├── core.py              # Entry (central model)
├── entities.py          # Person, Tag, Event
├── geography.py         # Location, City
├── creative.py          # Poem, ReferenceSource
├── manuscript.py        # Re-export from models_manuscript
└── sync.py              # Tombstone, SyncState
```

#### Backward Compatibility

```python
# dev/database/models/__init__.py
"""
SQLAlchemy ORM models for Palimpsest.

All models re-exported from this module for backward compatibility.
"""
from .base import Base
from .core import Entry
from .entities import Person, Tag, Event
from .geography import Location, City
from .creative import Poem, ReferenceSource
from .sync import Tombstone, SyncState

# Re-export everything for "from dev.database.models import *"
__all__ = [
    "Base",
    "Entry",
    "Person",
    "Tag",
    "Event",
    "Location",
    "City",
    "Poem",
    "ReferenceSource",
    "Tombstone",
    "SyncState",
]
```

#### Migration Steps

1. Create `dev/database/models/` directory
2. Create `base.py` with Base class
3. Split models by domain into separate files
4. Create `__init__.py` with all re-exports
5. Update any direct file imports across codebase
6. Test all database operations
7. Verify Alembic migrations still work
8. Rename original `models.py` to `models_old.py` (keep as reference)
9. After validation, delete `models_old.py`

#### Benefits

- **Logical Organization**: Models are grouped logically by domain (core, entities, geography, creative, manuscript, sync), making the schema easier to understand and navigate.
- **Backward Compatibility**: A single import point in `__init__.py` ensures existing code can continue to function without immediate breaking changes, allowing for a phased migration.
- **Improved Discoverability**: Developers can more easily locate specific models within the codebase, reducing search time and improving development efficiency.
- **Stable API**: The refactoring is designed to introduce no breaking changes to the public API, ensuring a smooth transition for dependent modules.
- **Clear Separation of Concerns**: Enforces better modularity by separating distinct sets of models, preventing a monolithic model definition file.

---

### 6. dev/validators/cli.py (~600 lines)

**Priority**: LOW (Future Planning)
**Effort**: 2-3 hours
**Risk**: Low

#### Current Status

- Currently manageable size (~600 lines)
- Has distinct command groups (wiki, db, md)
- Well organized internally

#### When to Refactor

Refactor when file exceeds 1,000 lines or when adding significant new validator types.

#### Proposed Future Structure

```
dev/validators/cli/
├── __init__.py          # Main CLI group
├── wiki.py              # Wiki validation commands
├── database.py          # Database validation commands
├── markdown.py          # Markdown validation commands
└── common.py            # Shared validation utilities
```

#### Action

- Monitor file size
- Consider refactoring if/when it grows beyond 1K lines
- **No immediate action needed**

---

### 7. dev/dataclasses/md_entry.py (~400 lines)

**Priority**: N/A
**Status**: No Action Needed

#### Assessment

- Well-sized for a dataclass module (~400 lines)
- Single responsibility (markdown entry representation)
- Clear structure and organization
- **No refactoring needed**

---

## Implementation Roadmap

### Phase 1: High-Impact, Low-Risk (Week 1)

**Goal**: Improve most user-facing code with minimal risk

1. **`dev/database/cli.py` → CLI modules** (4-6 hours)
   - Immediate user experience improvement
   - Clear command organization
   - Low risk (command groups already logical)

2. **Testing and validation** (2 hours)
   - Test all CLI commands
   - Update documentation
   - User acceptance testing

**Deliverables**:
- Split CLI with 8 focused command modules
- Updated documentation
- All tests passing

---

### Phase 2: Medium-Impact Refactoring (Week 2-3)

**Goal**: Improve builder and pipeline organization

3. **`dev/builders/wiki_pages.py` → Page builders + utils** (3-4 hours)
   - Extract reusable utilities
   - Split page builders
   - Enable easier additions

4. **`dev/pipeline/cli.py` → Pipeline direction modules** (3-4 hours)
   - Clear data flow organization
   - Reduce duplication
   - Improve maintainability

5. **Testing and validation** (2 hours)
   - Test all wiki page exports
   - Test all pipeline commands
   - Integration testing

**Deliverables**:
- Modular wiki page builders with shared utilities
- Pipeline CLI split by data flow direction
- Comprehensive test coverage

---

### Phase 3: Architectural Improvement (Week 4-5)

**Goal**: Improve core architecture and service separation

6. **`dev/database/manager.py` → Services layer** (6-8 hours)
   - Extract service components
   - Simplify core manager
   - Improve testability
   - **Higher risk - requires careful session management**

7. **Testing and validation** (3-4 hours)
   - Unit test each service independently
   - Integration tests for manager
   - Full pipeline testing
   - Performance validation

**Deliverables**:
- Service-oriented database architecture
- Core manager reduced to ~300 lines
- Independent service testing
- Maintained backward compatibility

---

### Phase 4: Maintenance and Future-Proofing (Week 6)

**Goal**: Address remaining files and document patterns

8. **`dev/database/models.py` → Domain models** (2-3 hours)
   - Split by domain
   - Maintain backward compatibility
   - Clean organization

9. **Documentation and patterns** (3-4 hours)
   - Document refactoring patterns
   - Create developer guide for adding new modules
   - Update architecture documentation
   - Code review and cleanup

**Deliverables**:
- Domain-organized models
- Refactoring pattern documentation
- Developer contribution guide
- Clean, maintainable codebase

---

## Testing Strategy

### Unit Testing

Each refactored module must have:
- Independent unit tests
- Mocked dependencies
- Edge case coverage

### Integration Testing

After each phase:
- Full pipeline testing (yaml2sql, sql2wiki, wiki2sql)
- CLI command testing (all commands, all options)
- Database operation testing
- Multi-machine sync validation

### Regression Testing

Before merging each phase:
- Run existing test suite
- Manual testing of common workflows
- Performance benchmarking
- Backward compatibility validation

---

## Success Criteria

### Quantitative Metrics

- ✅ No file exceeds 500 lines (target: <400 lines per file)
- ✅ Test coverage maintained or improved (>80%)
- ✅ No breaking changes to public APIs
- ✅ All existing tests pass
- ✅ Documentation updated for all changes

### Qualitative Metrics

- ✅ Easier to navigate codebase
- ✅ Clear separation of concerns
- ✅ Reduced code duplication
- ✅ Improved developer experience
- ✅ Faster onboarding for new contributors

---

## Rollback Plan

Each phase should be:
- Implemented in a feature branch
- Merged via pull request after review
- Tagged with version number

If issues arise:
1. Identify problematic phase via git tags
2. Revert to previous stable tag
3. Analyze root cause
4. Fix and re-attempt with lessons learned

---

## Risk Mitigation

### High-Risk Areas

1. **Session Management in manager.py refactoring**
   - **Risk**: Breaking session lifecycle
   - **Mitigation**: Extensive integration tests, gradual migration

2. **Import Path Changes**
   - **Risk**: Breaking external dependencies
   - **Mitigation**: Maintain backward-compatible re-exports

3. **CLI Entry Points**
   - **Risk**: Breaking user workflows
   - **Mitigation**: Test all commands before/after, update docs

### Risk Management Strategy

- Keep backward-compatible imports during transition
- Maintain deprecation warnings for 1-2 releases
- Document all breaking changes
- Provide migration scripts if needed

---

## Post-Refactoring Maintenance

### New File Size Policy

- **Yellow Flag**: Files approaching 500 lines should be reviewed
- **Red Flag**: Files exceeding 700 lines should be refactored
- **Hard Limit**: No file should exceed 1,000 lines

### Code Review Checklist

When adding new features:
- [ ] Does this belong in the current module?
- [ ] Should this be a new module?
- [ ] Are we duplicating logic that should be extracted?
- [ ] Is the module growing beyond its single responsibility?

---

## Resources and References

### Related Documentation

- `../technical/tombstone-guide.md` - Tombstone pattern implementation
- `../../user-guides/multi-machine-sync.md` - Multi-machine sync workflow
- `../technical/migration-guide.md` - Database migration guide
- `../technical/conflict-resolution.md` - Conflict resolution process

### External References

- [Click Documentation](https://click.palletsprojects.com/) - CLI framework
- [SQLAlchemy Best Practices](https://docs.sqlalchemy.org/en/14/orm/tutorial.html)
- [Python Package Structure](https://docs.python-guide.org/writing/structure/)

---

## Appendix A: File Size History

| File | Original Size | Target Size | Reduction |
|------|--------------|-------------|-----------|
| `dev/database/cli.py` | 1,228 lines | ~150 lines/module × 8 | 10 files |
| `dev/database/manager.py` | 1,150 lines | ~300 lines core + services | 6 files |
| `dev/builders/wiki_pages.py` | 1,155 lines | ~200 lines/page × 5 | 8 files |
| `dev/pipeline/cli.py` | ~1,000 lines | ~200 lines/module × 4 | 5 files |
| `dev/database/models.py` | ~800 lines | ~100 lines/domain × 6 | 7 files |

**Total**: From 5 files (5,333 lines) to ~36 focused modules (avg ~150 lines each)

---

## Appendix B: Example Refactoring Commit Messages

```
refactor(database/cli): split CLI into command group modules

- Extract migration commands to cli/migration.py
- Extract backup commands to cli/backup.py
- Extract tombstone commands to cli/tombstone.py
- Extract sync commands to cli/sync.py
- Create shared context utilities in cli/__init__.py
- Maintain backward compatibility
- All tests passing

BREAKING CHANGE: None (backward compatible imports maintained)
Closes #XXX
```

---

## Appendix C: Quick Reference Commands

### Before Refactoring

```bash
# Save current state
git tag pre-refactor-snapshot
git push origin pre-refactor-snapshot

# Create feature branch
git checkout -b refactor/database-cli
```

### During Refactoring

```bash
# Test frequently
pytest tests/
python -m dev.database.cli --help

# Commit incrementally
git add dev/database/cli/
git commit -m "refactor(database/cli): extract migration commands"
```

### After Refactoring

```bash
# Full validation
pytest tests/
python -m dev.pipeline.cli --help
python -m dev.database.cli --help

# Update documentation
vim docs/refactoring-proposal.md

# Merge
git checkout main
git merge refactor/database-cli
git tag post-refactor-v1
git push origin main --tags
```

---

**END OF DOCUMENT**

Last Updated: 2025-11-23
Status: Ready for Implementation
Next Step: Begin Phase 1 with `dev/database/cli.py` refactoring
