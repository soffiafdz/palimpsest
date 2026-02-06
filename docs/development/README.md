# Development Documentation

Welcome to the Palimpsest development documentation. This section contains technical guides for contributors and developers.

---

## Quick Links

- [Full Setup Guide](full-setup.md) - Complete setup from scratch
- [Architecture](architecture.md) - System design and modular organization
- [Database Managers](database-managers.md) - Entity manager patterns
- [Validators](validators.md) - Validation system architecture
- [Tombstones](tombstones.md) - Deletion tracking implementation
- [Type Checking](type-checking.md) - Pyright configuration and patterns
- [Testing](testing.md) - Comprehensive testing guide
- [Neovim Plugin Development](neovim-plugin-dev.md) - Extending the Neovim integration

---

## Getting Started with Development

### Prerequisites

- Python 3.10+
- Git
- SQLite
- Optional: Neovim (for editor integration testing)

### Development Setup

```bash
# Clone repository
git clone <repository-url>
cd palimpsest

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type check
pyright
```

---

## Architecture Overview

Palimpsest is organized into modular components:

```
dev/
├── database/           # Database layer (SQLAlchemy ORM)
│   ├── models/        # Entity models
│   ├── managers/      # CRUD operations
│   └── cli/           # Database CLI commands
├── dataclasses/       # Intermediary data structures
│   ├── txt_entry.py  # TXT file conversion
│   └── metadata_entry.py # Metadata YAML structures
├── pipeline/          # Data pipeline scripts
│   ├── src2txt.py    # Raw exports → formatted text
│   ├── txt2md.py     # TXT → Markdown conversion
│   ├── metadata_importer.py # Metadata → Database import
│   └── export_json.py # Database → JSON export
├── wiki/              # Wiki generation system
│   ├── exporter.py   # Wiki page exporter
│   ├── renderer.py   # Jinja2 template renderer
│   └── templates/    # Wiki page templates
├── search/            # Full-text search (FTS5)
├── validators/        # Validation tools
├── builders/          # PDF/TXT builders
└── utils/             # Shared utilities
```

**Core Principles**:
1. **Separation of Concerns**: Database, pipeline, and wiki layers are independent
2. **Unidirectional Import**: Metadata YAML → Database (one-time import)
3. **Type Safety**: Pyright type checking with defensive coding patterns
4. **Modular Design**: Easy to extend with new entity types

→ Learn more: [Architecture](architecture.md)

---

## Key Concepts

### Entity Managers

Palimpsest uses a manager pattern for database operations. Managers are initialized per session inside `PalimpsestDB.session_scope()`:

```python
from dev.database.manager import PalimpsestDB

db = PalimpsestDB("data/palimpsest.db", alembic_dir="alembic")

with db.session_scope() as session:
    entry = db._entry_manager.create(metadata)
    entry = db._entry_manager.get(entry_date="2024-01-15")
    db._entry_manager.update(entry, new_metadata)
    db._entry_manager.delete(entry)
```

Each entity type (Entry, Person, Location, etc.) has a dedicated manager with specialized methods.

→ Learn more: [Database Managers](database-managers.md)

### Validation System

Three-layer validation ensures data integrity:

1. **Schema Validation**: YAML structure and required fields
2. **Format Validation**: Data types and formats (dates, enums, etc.)
3. **Database Validation**: Referential integrity and constraints

→ Learn more: [Validators](validators.md)

### Tombstone Pattern

Deletions are tracked using tombstones to ensure proper propagation across machines:

```python
# When you remove "Bob" from an entry:
# 1. Tombstone created: entry_people(entry_id, person_id, deleted_at)
# 2. Association removed from database
# 3. On other machines: tombstone prevents re-adding Bob
```

→ Learn more: [Tombstones](tombstones.md)

---

## Development Workflow

### Adding a New Feature

1. **Plan**: Review [Architecture](architecture.md) to understand where the feature fits
2. **Implement**: Write code following existing patterns
3. **Test**: Add unit and integration tests (see [Testing](testing.md))
4. **Type Check**: Run `pyright` to catch type errors
5. **Document**: Update relevant documentation
6. **Submit**: Create pull request with clear description

### Testing

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/unit/test_entry_manager.py

# Run with coverage
pytest --cov=dev --cov-report=html

# Run type checking
pyright
```

→ Learn more: [Testing](testing.md)

### Code Style

- **Type Hints**: Use type hints for function signatures
- **Docstrings**: Document public APIs with docstrings
- **Naming**: Follow PEP 8 naming conventions
- **Imports**: Group stdlib, third-party, and local imports

---

## Documentation Philosophy

Documentation should explain:
- **What**: What does this feature/component do?
- **Why**: Why does it exist? What problem does it solve?
- **How**: How do you use it?

Documentation should NOT contain:
- Historical proposals or implementation reports
- Change logs or update summaries (use git history)

---

## Common Tasks

### Adding a New Entity Type

1. Create model in `dev/database/models/`
2. Create manager in `dev/database/managers/`
3. Add wiki dataclass in `dev/dataclasses/wiki_*.py`
4. Register in entity exporter configuration
5. Add tests

### Extending Validation

1. Add validator class in `dev/database/validators/`
2. Register in validation pipeline
3. Add error messages
4. Add tests

### Adding CLI Commands

1. Add command in `dev/pipeline/cli.py`
2. Update command reference documentation
3. Add tests for command

---

## Troubleshooting Development Issues

### Import Errors

If you get import errors:
1. Ensure you're in the virtual environment
2. Run `pip install -e ".[dev]"` to install in development mode
3. Check `PYTHONPATH` if using IDE

### Test Failures

If tests fail:
1. Check if you have all dependencies: `pip install -e ".[dev]"`
2. Ensure database migrations are up to date
3. Check test fixtures in `tests/conftest.py`

### Type Checking Errors

If Pyright reports unexpected errors:
1. Check `pyrightconfig.json` for execution environments
2. Review [Type Checking](type-checking.md) for common patterns
3. Use `# type: ignore` as last resort with comment explaining why

---

## Contributing

Contributions are welcome! Please:
1. Read the documentation in this section
2. Follow the development workflow above
3. Write tests for new features
4. Update documentation as needed
5. Submit pull requests with clear descriptions

---

## Resources

- [Full Setup Guide](full-setup.md) - Complete setup from scratch
- [Architecture](architecture.md) - System design
- [Database Managers](database-managers.md) - Entity patterns
- [Validators](validators.md) - Validation system
- [Tombstones](tombstones.md) - Deletion tracking
- [Type Checking](type-checking.md) - Type safety
- [Testing](testing.md) - Testing guide
- [Neovim Plugin Development](neovim-plugin-dev.md) - Plugin extension

**Main Documentation**:
- [Getting Started](../getting-started.md) - User onboarding
- [Reference](../reference/) - Field and command references
- [Guides](../guides/) - User guides and workflows
