# Type Checking with Pyright

This project uses [Pyright](https://github.com/microsoft/pyright) for static type checking to catch type errors early and improve code quality.

## Quick Start

```bash
# Check entire codebase
pyright

# Check specific directory
pyright dev/database

# Check specific file
pyright dev/database/manager.py
```

## Configuration

The project's Pyright configuration is in `pyrightconfig.json` at the project root.

### Key Settings

- **Python Version**: 3.10
- **Type Checking Mode**: `basic` (balanced between strictness and pragmatism)
- **Includes**: `dev/`, `tests/`
- **Excludes**: `node_modules`, `__pycache__`, `.git`, virtual environments

## Execution Environments

The configuration uses **execution environments** to apply different rules to different parts of the codebase.

### dev/nlp Module (Special Treatment)

The `dev/nlp` module has relaxed rules because it uses **optional dependencies** (spaCy, transformers, OpenAI, etc.) that aren't required for core functionality:

```json
{
  "root": "dev/nlp",
  "reportMissingImports": "none",
  "reportOptionalMemberAccess": "none",
  "reportOptionalCall": "none",
  "reportInvalidTypeForm": "none",
  "reportConstantRedefinition": "none",
  "reportUnusedImport": "none"
}
```

**Why these suppressions?**

1. **reportMissingImports: none** - NLP libraries (spacy, sentence-transformers, etc.) are optional
2. **reportOptionalMemberAccess: none** - Code gracefully handles missing dependencies
3. **reportOptionalCall: none** - Methods on optional objects are checked at runtime
4. **reportConstantRedefinition: none** - Pattern for feature flags (e.g., `SPACY_AVAILABLE = True`)
5. **reportUnusedImport: none** - Type hints from optional packages

## Error Levels

The configuration uses three severity levels:

- **error** - Critical issues that will fail CI/CD
- **warning** - Important but not blocking
- **none** - Disabled

### Errors (Strict)

These checks are enforced as errors:

- `reportUndefinedVariable` - Using variables before definition
- `reportUnboundVariable` - Variables that might not be bound
- `reportReturnType` - Return type mismatches
- `reportAttributeAccessIssue` - Invalid attribute access
- `reportIncompatibleMethodOverride` - Method signature mismatches
- `reportConstantRedefinition` - Redefining constants (except in dev/nlp)
- `reportOptionalSubscript` - Subscripting optional types without checks

### Warnings (Informational)

These checks provide helpful feedback but don't block:

- `reportUnusedImport` - Unused imports
- `reportUnusedVariable` - Unused variables
- `reportUnusedFunction` - Unused functions
- `reportUnnecessaryIsInstance` - Redundant type checks
- `reportPrivateUsage` - Accessing private members

### Disabled Checks

Some checks are disabled for pragmatic reasons:

- `reportUnknownParameterType` - Would require extensive type annotations
- `reportMissingTypeStubs` - Many third-party libraries lack stubs
- `reportUntypedFunctionDecorator` - SQLAlchemy decorators lack stubs

## Common Patterns

### Optional Dependencies

```python
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False
    spacy = None  # type: ignore
```

This pattern is used extensively in `dev/nlp/` and suppressed by the execution environment.

### Type Hints with Optional Imports

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from anthropic import Anthropic

def get_client() -> "Anthropic | None":
    if ANTHROPIC_AVAILABLE:
        from anthropic import Anthropic
        return Anthropic()
    return None
```

### Database Session Management

```python
# ❌ Bad - db.session doesn't exist
entry = db.session.query(Entry).first()

# ✅ Good - use get_session()
session = db.get_session()
entry = session.query(Entry).first()
```

## CI/CD Integration

Pyright should be integrated into CI/CD pipelines:

```yaml
# .github/workflows/type-check.yml
- name: Type check with Pyright
  run: pyright
```

## Incremental Adoption

The current configuration is **pragmatic** rather than **strict**:

1. Focuses on catching real bugs (attribute errors, type mismatches)
2. Allows gradual type hint adoption (doesn't require full annotation)
3. Recognizes optional dependencies pattern

To increase strictness over time:

1. Change `typeCheckingMode` from `"basic"` to `"standard"` or `"strict"`
2. Enable more checks at the error level
3. Add type stubs for untyped dependencies

## Troubleshooting

### "Cannot access attribute" Errors

If you see errors like `Cannot access attribute "x" for class "Y"`, verify:

1. The attribute actually exists in the class
2. You're not accessing a method of an optional dependency
3. The class is properly imported

### Missing Import Errors in dev/nlp

These should be suppressed automatically. If not:

1. Check that `pyrightconfig.json` exists
2. Verify the execution environment includes the file
3. Ensure Pyright is using the config: `pyright --verbose`

### False Positives

If Pyright reports errors that aren't real issues:

1. Add `# type: ignore` comment (last resort)
2. Adjust the configuration for that specific check
3. Create an execution environment with relaxed rules

## References

- [Pyright Documentation](https://github.com/microsoft/pyright/blob/main/docs/configuration.md)
- [Pyright Type Checking Modes](https://github.com/microsoft/pyright/blob/main/docs/configuration.md#type-checking-rule-overrides)
- [Python Type Hints (PEP 484)](https://peps.python.org/pep-0484/)
