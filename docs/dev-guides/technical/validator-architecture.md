# Validator Architecture

**Last Updated:** 2025-12-07

---

## Overview

The Palimpsest validation system uses a 3-layer architecture to ensure data quality and consistency across markdown files, metadata structures, and database entries.

## Architecture Layers

```
┌─────────────────────────────────────────────────────────────┐
│                     Layer 1: Schema                         │
│                  (dev/validators/schema.py)                 │
│                                                             │
│  • Authoritative enum imports from models/enums.py          │
│  • Type and format validation (dates, enums, structures)    │
│  • Reusable validation methods                              │
│  • Single source of truth for all validators                │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
                    ┌─────────┴─────────┐
                    │                   │
┌───────────────────▼─────┐   ┌─────────▼──────────────────┐
│     Layer 2: Format     │   │   Layer 2: Structure       │
│  (dev/validators/md.py) │   │ (dev/validators/metadata.py)│
│                         │   │                            │
│  • Markdown syntax      │   │  • YAML structure          │
│  • Frontmatter format   │   │  • Parser compatibility    │
│  • Body content rules   │   │  • Cross-field dependencies│
│  • Internal links       │   │  • Field presence/absence  │
└─────────────────────────┘   └────────────────────────────┘
                    │                   │
                    └─────────┬─────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Layer 3: Database                         │
│             (dev/validators/db.py)                          │
│             (dev/validators/consistency.py)                 │
│                                                             │
│  • Foreign key integrity                                    │
│  • Cross-entry consistency                                  │
│  • Referential integrity                                    │
│  • Database constraint validation                           │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 1: Schema Validator

**File:** `dev/validators/schema.py`

**Purpose:** Centralized validation using authoritative enum sources

### Key Principles

1. **Single Source of Truth** - All enum values imported from `models/enums.py`
2. **Type Safety** - Validates field types against expected schemas
3. **Reusability** - Used by both md.py and metadata.py validators
4. **Maintainability** - When enums change, validators automatically stay in sync

### Enum Providers

```python
@staticmethod
def get_valid_reference_types() -> List[str]:
    """Get valid reference types from authoritative enum."""
    return ReferenceType.choices()

@staticmethod
def get_valid_reference_modes() -> List[str]:
    """Get valid reference modes from authoritative enum."""
    return ReferenceMode.choices()
```

### Field Validators

```python
validate_reference_mode(mode, field_path) → Optional[SchemaIssue]
validate_reference_type(ref_type, field_path) → Optional[SchemaIssue]
validate_manuscript_status(status, field_path) → Optional[SchemaIssue]
validate_date_format(date_value, field_path) → Optional[SchemaIssue]
```

### Complex Structure Validators

```python
validate_reference_structure(reference, index) → List[SchemaIssue]
validate_references_schema(references_list) → List[SchemaIssue]
validate_manuscript_schema(manuscript) → List[SchemaIssue]
```

### Usage Example

```python
from dev.validators.schema import SchemaValidator

validator = SchemaValidator()

# Validate a single enum value
issue = validator.validate_reference_type("website", "source.type")
if issue:
    print(f"Error: {issue.message}")

# Validate complex structure
references = [
    {"content": "Quote", "mode": "direct"},
    {"description": "Summary", "source": {"title": "Book", "type": "book"}}
]
issues = validator.validate_references_schema(references)
```

---

## Layer 2a: Markdown Validator

**File:** `dev/validators/md.py`

**Purpose:** Validate markdown file format and frontmatter syntax

### What It Validates

1. **Required Fields** - Ensures `date` field is present
2. **YAML Syntax** - Frontmatter is valid YAML
3. **Date Format** - Entry date follows YYYY-MM-DD format
4. **Field Types** - word_count is int, reading_time is int, etc.
5. **Unknown Fields** - Warns about unexpected frontmatter fields
6. **Body Content** - Checks for empty body, placeholder text (TODO, FIXME)
7. **Internal Links** - Validates markdown links to other files
8. **Enum Values** - Uses schema validator for reference modes/types, manuscript status

### Usage

```python
from dev.validators.md import MarkdownValidator

validator = MarkdownValidator(md_dir=Path("data/wiki"))
issues = validator.validate_file(Path("data/wiki/2024-01-01.md"))

for issue in issues:
    print(f"{issue.severity}: {issue.message}")
```

### Integration with Schema Validator

```python
class MarkdownValidator:
    schema_validator = SchemaValidator()

    def _validate_frontmatter(self, file_path, frontmatter_text):
        # ...
        # Validate references using schema validator
        schema_issues = self.schema_validator.validate_references_schema(
            frontmatter["references"]
        )
        for schema_issue in schema_issues:
            issues.append(MarkdownIssue(...))
```

---

## Layer 2b: Metadata Validator

**File:** `dev/validators/metadata.py`

**Purpose:** Validate metadata structure for parser compatibility

### What It Validates

1. **People Field** - Name formats, aliases, parentheses, duplicates
2. **Locations Field** - Flat list vs nested dict, city dependencies
3. **Dates Field** - ISO format, context, people/locations sub-fields
4. **References Field** - content/description, mode, source structure
5. **Poems Field** - title, content, revision_date format
6. **Manuscript Field** - status enum, edited boolean, themes list
7. **Cross-Field Dependencies** - e.g., flat locations requires exactly 1 city
8. **Enum Values** - Uses schema validator for all enum validation

### Usage

```python
from dev.validators.metadata import MetadataValidator

validator = MetadataValidator(md_dir=Path("data/wiki"))
report = validator.validate_all()

print(f"Files checked: {report.files_checked}")
print(f"Total errors: {report.total_errors}")
```

### Integration with Schema Validator

```python
class MetadataValidator:
    schema_validator = SchemaValidator()

    def validate_references_field(self, file_path, references_data):
        # ...
        # Check mode enum using schema validator
        if "mode" in ref:
            mode_issue = self.schema_validator.validate_reference_mode(
                ref["mode"], f"references[{idx}].mode"
            )
            if mode_issue:
                issues.append(MetadataIssue(...))
```

---

## Layer 3: Database Validators

**Files:**
- `dev/validators/db.py` - Database integrity validation
- `dev/validators/consistency.py` - Cross-entry consistency validation

### Database Validator

**Purpose:** Validate database integrity and referential constraints

**What It Validates:**
- Foreign key integrity
- Orphaned records
- Duplicate entries
- Database constraint violations
- Table relationships

### Consistency Validator

**Purpose:** Validate cross-entry consistency

**What It Validates:**
- Person names match across entries
- Location names are consistent
- Date references are valid
- Tag usage is consistent
- Reference sources are properly linked

---

## When to Use Which Validator

### Use `md.py` when:
- ✅ Validating markdown file format
- ✅ Checking frontmatter YAML syntax
- ✅ Verifying required fields exist
- ✅ Checking internal links
- ✅ Linting markdown files before commit

### Use `metadata.py` when:
- ✅ Validating metadata structure for parser compatibility
- ✅ Checking complex field formats (people, locations, dates)
- ✅ Verifying cross-field dependencies (city-locations)
- ✅ Ensuring YAML structure matches parser expectations

### Use `schema.py` when:
- ✅ Validating individual enum values
- ✅ Checking field types (dates, enums, etc.)
- ✅ Building custom validators
- ✅ Need reusable validation logic

### Use `db.py` / `consistency.py` when:
- ✅ Validating database integrity after import
- ✅ Checking for orphaned records
- ✅ Verifying cross-entry consistency
- ✅ Running database health checks

---

## CLI Commands

### Validate Markdown Files

```bash
# Validate all markdown files
python -m dev.validators.cli.markdown all

# Validate specific file
python -m dev.validators.cli.markdown file data/wiki/2024-01-01.md

# Check internal links
python -m dev.validators.cli.markdown links
```

### Validate Metadata Structure

```bash
# Validate all metadata
python -m dev.validators.cli.metadata all

# Validate specific field type
python -m dev.validators.cli.metadata people
python -m dev.validators.cli.metadata locations
python -m dev.validators.cli.metadata references
```

### Validate Database

```bash
# Check database integrity
python -m dev.validators.cli.database integrity

# Check for orphaned records
python -m dev.validators.cli.database orphans

# Full consistency check
python -m dev.validators.cli.consistency all
```

---

## Adding New Enum Types

### Old Way (Before Refactoring)

1. Update `models/enums.py`
2. Update `validators/md.py` VALID_* lists
3. Update `validators/metadata.py` VALID_* lists
4. Update documentation
5. **Risk:** Forgetting a validator → validation fails

### New Way (After Refactoring)

1. Update `models/enums.py`
2. Add enum provider method to `schema.py` (if needed)
3. Done! ✅

**Example: Adding a new enum**

```python
# 1. Add to models/enums.py
class ManuscriptStatus(str, Enum):
    DRAFT = "draft"
    REVIEWED = "reviewed"
    FINAL = "final"
    NEW_STATUS = "new_status"  # ← Add new value

    @classmethod
    def choices(cls):
        return [e.value for e in cls]

# 2. Schema validator automatically imports new value
# No changes needed to md.py or metadata.py!
```

---

## Testing

### Schema Validator Tests

**File:** `tests/unit/validators/test_schema_validator.py`

**Coverage:**
- Enum provider methods
- Field validation methods
- Complex structure validation
- Edge cases (invalid values, wrong types)

```bash
python -m pytest tests/unit/validators/test_schema_validator.py -v
```

### Markdown Validator Tests

**File:** `tests/unit/validators/test_md_validator.py`

```bash
python -m pytest tests/unit/validators/test_md_validator.py -v
```

### Metadata Validator Tests

**File:** `tests/unit/validators/test_metadata_validator.py`

```bash
python -m pytest tests/unit/validators/test_metadata_validator.py -v
```

### Run All Validator Tests

```bash
python -m pytest tests/unit/validators/ -v
```

---

## Benefits of Current Architecture

### Maintainability

- **Single Source of Truth** - Enums defined once in `models/enums.py`
- **Automatic Propagation** - Changes to enums automatically affect all validators
- **No Duplication** - Eliminated 56+ lines of duplicated enum definitions

### Type Safety

- **Enum Imports** - Type-safe enum values, not hardcoded strings
- **Schema Validation** - Centralized type checking for all fields
- **Compile-Time Checks** - IDE can catch enum usage errors

### Extensibility

- **Easy to Add Validators** - Just import `SchemaValidator`
- **Reusable Methods** - Schema validation logic can be used anywhere
- **Modular Design** - Each layer has clear responsibilities

### Testing

- **Isolated Testing** - Schema validator tested separately
- **Comprehensive Coverage** - 51+ tests across all validators
- **No Regressions** - All existing tests still pass

---

## Migration History

### Before (Pre-2025-12-07)

```python
# dev/validators/md.py
VALID_REFERENCE_TYPES = [
    "book", "poem", "article", "film", "song",
    "podcast", "interview", "speech", "tv_show",
    "video", "other"  # ← Missing "website"!
]

# dev/validators/metadata.py
VALID_REFERENCE_TYPES = [
    "book", "poem", "article", "film", "song",
    "podcast", "interview", "speech", "tv_show",
    "video", "other"  # ← Missing "website"!
]

# This caused validation to fail for website references
```

### After (2025-12-07)

```python
# dev/validators/schema.py
@staticmethod
def get_valid_reference_types() -> List[str]:
    """Get valid reference types from authoritative enum."""
    return ReferenceType.choices()  # ← Imports from models/enums.py

# dev/validators/md.py
class MarkdownValidator:
    schema_validator = SchemaValidator()  # ← Uses schema validator

# dev/validators/metadata.py
class MetadataValidator:
    schema_validator = SchemaValidator()  # ← Uses schema validator

# Now all validators automatically support new enum values!
```

---

## Future Improvements

### Planned Enhancements

1. **Create ManuscriptStatus Enum** - Currently hardcoded in `schema.py`
2. **Add More Schema Validators** - For dates subfields, themes, etc.
3. **Performance Optimization** - Cache enum values for faster validation
4. **Better Error Messages** - More context-aware suggestions
5. **Validation Profiles** - Different strictness levels (strict, normal, lenient)

### Potential Extensions

- **Auto-Fix Mode** - Automatically fix common validation errors
- **Custom Validators** - Allow users to add custom validation rules
- **JSON Schema** - Generate JSON schemas from validation rules
- **Real-time Validation** - Integrate with editor for live feedback

---

## References

- [Validator Refactoring Proposal](../proposals/validator-refactoring-proposal.md)
- [Validator Refactoring Implementation Summary](../proposals/validator-refactoring-implementation-summary.md)
- [Metadata Quick Reference](../../user-guides/metadata-quick-reference.md)
- [Metadata YAML-SQL Guide](./metadata-yaml-sql-guide.md)
