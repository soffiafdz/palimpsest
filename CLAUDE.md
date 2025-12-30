# Palimpsest Project Instructions

This file contains project-specific instructions for Claude Code that persist across sessions.

## Git Commits

See global `~/.claude/CLAUDE.md` for general git practices. Project-specific note:
- The `data/` directory is a git submodule — commit changes there separately before updating the submodule reference in the main repo

## Code Style Requirements

### Docstrings

All functions and methods must have detailed docstrings following the existing codebase pattern:

```python
def example_function(self, param1: str, param2: Optional[int] = None) -> bool:
    """
    Brief one-line description of what this function does.

    More detailed explanation if needed, covering the purpose,
    behavior, and any important notes about usage.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter (optional)

    Returns:
        Description of what is returned

    Raises:
        ValidationError: When validation fails
        DatabaseError: When database operation fails

    Notes:
        - Additional implementation notes
        - Edge cases or special behaviors
    """
```

### Module Headers

All Python files must have a detailed introductory docstring:

```python
#!/usr/bin/env python3
"""
module_name.py
--------------
Brief description of the module's purpose.

Detailed explanation of what this module provides, including:
- Key features and capabilities
- How it fits into the larger system
- Important design decisions or patterns used

Key Features:
    - Feature 1 with brief description
    - Feature 2 with brief description
    - Feature 3 with brief description

Usage:
    # Example usage code
    instance = ModuleClass(param1, param2)
    result = instance.method()

Dependencies:
    - List any notable dependencies if relevant
"""
```

### Type Annotations

- All function parameters must have type annotations
- All return types must be annotated
- Use `Optional[T]` for nullable types
- Use `List[T]`, `Dict[K, V]` for collections
- Import typing constructs: `from typing import Any, Dict, List, Optional, Type`

## Workplan Reference

The project workplan is at `docs/unified_simplification_workplan.md`. Check this file for:
- Current priorities (P0-P35)
- Completion status of tasks
- Dependencies between tasks

## Project Structure

Key directories:
- `dev/database/managers/` - Entity managers (being consolidated in P3)
- `dev/wiki/` - Jinja2 template-based wiki renderer (P26 complete)
- `dev/pipeline/` - Data conversion pipelines
- `tests/` - Pytest test suite

## No Compatibility Aliases

When making breaking changes:
- Propagate changes to all call sites
- Do NOT add compatibility aliases or backward-compatible shims
- Delete unused code completely

## Database Manager Patterns

### Using BaseManager Helpers

Always use the inherited helpers from `BaseManager`:
- `_exists(model, field, value)` - Check existence
- `_get_by_id(model, id)` - Get by ID with soft-delete support
- `_get_by_field(model, field, value)` - Get by field value
- `_get_all(model, order_by=None)` - Get all with ordering
- `_update_scalar_fields(entity, metadata, field_configs)` - Update fields
- `_update_relationships(entity, metadata, relationship_configs)` - Update M2M
- `_resolve_parent(spec, model, get_method)` - Resolve parent entities

### Database Operations

Use the DatabaseOperation context manager for all database methods:
```python
from dev.database.decorators import DatabaseOperation
from dev.core.validators import DataValidator

def method(self, metadata):
    DataValidator.validate_required_fields(metadata, ["required_field"])
    with DatabaseOperation(self.logger, "operation_name"):
        # actual database logic here
```

### Custom Exceptions

- `ValidationError` - For validation failures (user input errors)
- `DatabaseError` - For database operation failures (internal errors)

## Import Ordering

Follow this import order with blank lines between sections:

```python
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import ValidationError, DatabaseError
from dev.core.validators import DataValidator
from dev.database.decorators import handle_db_errors
```

## Testing Requirements

- Minimum coverage: 15% (enforced by CI)
- Test files: `tests/unit/` and `tests/integration/`
- Run tests with: `python -m pytest tests/ -q`
- Use fixtures from `conftest.py`

### Mandatory Testing for All Changes

**Every code addition or modification MUST include:**

1. **Unit tests** for new functions/methods
2. **Integration tests** if the change affects multiple modules
3. **Test coverage** for edge cases and error conditions

Place tests in the corresponding location:
- `dev/module/file.py` → `tests/unit/module/test_file.py`

## Development Workflow

When making any code changes, follow these steps:

### 1. Documentation First

Before writing code:
- Understand the existing patterns in the codebase
- Plan the module header and key docstrings

### 2. Implementation

Code must include:
- **Module header**: Script purpose, features, usage examples, dependencies
- **Type annotations**: All parameters and return types
- **Detailed docstrings**: Args, Returns, Raises, Notes sections

### 3. Testing

Create tests before considering a feature complete:
- Test happy paths
- Test edge cases
- Test error conditions

### 4. Documentation Update

Update relevant docs:
- `CLAUDE.md` for persistent instructions
- `docs/unified_simplification_workplan.md` for task status
- Module docstrings for usage guidance

## Avoid Over-Engineering

- Only make changes directly requested
- Don't add features, refactoring, or "improvements" beyond the task
- Three lines of similar code is better than a premature abstraction
- Don't add error handling for scenarios that can't happen
- Don't add docstrings/comments to code you didn't change

## Enum Values

Important enum references:
- `ManuscriptStatus`: unspecified, reference, quote, fragments, source
- `ReferenceType`: book, article, film, etc.
- `ReferenceMode`: direct, indirect, paraphrase
- `RelationType`: family, friend, romantic, colleague, etc.

## Running Common Commands

```bash
# Run tests
python -m pytest tests/ -q

# Check linting
ruff check dev/

# Database migrations
alembic upgrade head

# CLI commands
python -m dev.pipeline.cli [command]
```
