# Validator Refactoring Proposal

**Status:** Proposal
**Created:** 2025-12-07
**Author:** Analysis by Claude
**Priority:** High - Design Flaw

---

## Executive Summary

The current validator architecture contains significant design flaws:

1. **Duplicate logic** across `metadata.py` and `md.py` validators
2. **Inconsistent validation** - neither validator is currently up-to-date
3. **Hardcoded enum values** instead of importing from authoritative source
4. **Overlapping jurisdiction** causing confusion about which validator to use

**Immediate fix applied:**
- Added `website` reference type to both validators (was missing)

**Long-term solution needed:**
- Refactor validators to eliminate duplication and establish clear separation of concerns

---

## Problem Analysis

### 1. Current Validator Structure

```
dev/validators/
├── md.py           # Markdown + YAML frontmatter validation
├── metadata.py     # YAML metadata structure validation
├── wiki.py         # Wiki link validation
├── db.py           # Database-level validation
└── consistency.py  # Cross-entry consistency checks
```

### 2. Identified Issues

#### Issue #1: Duplicate Enum Values

**Location:** Both `md.py` and `metadata.py`

**Current State:**
```python
# In md.py (lines 128-143)
VALID_REFERENCE_MODES = ["direct", "indirect", "paraphrase", "visual"]
VALID_REFERENCE_TYPES = [
    "book", "poem", "article", "film", "song",
    "podcast", "interview", "speech", "tv_show",
    "video", "other"  # ← Missing "website"!
]

# In metadata.py (lines 106-121)
VALID_REFERENCE_MODES = ["direct", "indirect", "paraphrase", "visual"]
VALID_REFERENCE_TYPES = [
    "book", "poem", "article", "film", "song",
    "podcast", "interview", "speech", "tv_show",
    "video", "other"  # ← Missing "website"!
]
```

**Authoritative Source:**
```python
# dev/database/models/enums.py (THE source of truth)
class ReferenceType(str, Enum):
    BOOK = "book"
    POEM = "poem"
    # ... etc
    WEBSITE = "website"  # ← Already exists in enum!
    OTHER = "other"
```

**Problem:** When enum is updated (as with `website`), both validators must be manually updated, leading to:
- Human error (forgetting to update)
- Inconsistent validation
- False negatives (valid data marked as invalid)

#### Issue #2: Overlapping Validation Logic

**Both validators check:**
- YAML syntax
- Frontmatter structure
- Required fields (`date`)
- Field types (list vs dict vs string)
- Reference structure (mode, type, source)
- Manuscript status values
- Date formats

**md.py additional checks:**
- Markdown body content
- Internal wiki links
- File naming conventions
- Orphaned files

**metadata.py additional checks:**
- Deeper structural validation
- Cross-field dependencies (city ↔ locations)
- Nested structure formats (dates with people/locations)
- Parser compatibility

**Confusion:** Users don't know which validator to run. Documentation suggests both, but they overlap 70%.

#### Issue #3: Inconsistent Validation Depth

**Example: References**

`md.py` (lines 369-401):
```python
# Shallow validation
- Checks mode enum
- Checks source type enum
- Checks dates list structure
```

`metadata.py` (lines 583-697):
```python
# Deep validation
- Checks dict structure
- Validates content OR description requirement
- Validates source substructure
- Cross-validates title + type
- Checks empty strings
- Validates nested fields
```

**Problem:** `md.py` will pass files that `metadata.py` will fail, and vice versa.

#### Issue #4: Manuscript Status Duplication

```python
# In md.py (lines 117-125)
VALID_MANUSCRIPT_STATUS = [
    "source", "draft", "reviewed", "included",
    "adapted", "excluded", "final"
]

# In metadata.py (lines 96-103)
VALID_MANUSCRIPT_STATUS = [
    "unspecified", "draft", "reviewed", "included",
    "adapted", "excluded", "final"
]
```

**Discrepancy:** `md.py` has "source", `metadata.py` has "unspecified". Which is correct?

---

## Root Cause

The validators were created at different times for different purposes, but evolved to overlap significantly without proper refactoring.

**Original Intent (inferred):**
- `md.py` → Quick YAML syntax + basic field checks
- `metadata.py` → Deep structural validation for parser compatibility

**Current Reality:**
- Both perform similar validations
- Neither imports from authoritative enum sources
- No clear guidance on which to use when

---

## Proposed Solution

### Architecture: Layer-Based Validation

```
┌─────────────────────────────────────────────────────────┐
│  Layer 1: Syntax Validation (md.py)                     │
│  - YAML parsing                                          │
│  - Markdown structure                                    │
│  - File naming                                           │
│  └─→ Fast, lightweight, editor-friendly                 │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 2: Schema Validation (NEW: schema.py)            │
│  - Field types                                           │
│  - Required/optional fields                              │
│  - Enum values (imported from models.enums)              │
│  └─→ Validates against schema, imports enums            │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 3: Structural Validation (metadata.py)           │
│  - Parser compatibility                                  │
│  - Cross-field dependencies                              │
│  - Complex nested structures                             │
│  └─→ Deep validation for data integrity                 │
└─────────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────┐
│  Layer 4: Semantic Validation (db.py + consistency.py)  │
│  - Database referential integrity                        │
│  - Cross-entry consistency                               │
│  └─→ Validates relationships and data consistency       │
└─────────────────────────────────────────────────────────┘
```

### Specific Changes

#### 1. Create `schema.py` - Centralized Schema Validation

```python
"""
schema.py
---------
Centralized schema validation using authoritative enum sources.
Eliminates hardcoded enum duplication.
"""
from dev.database.models.enums import ReferenceType, ReferenceMode, RelationType

class SchemaValidator:
    """Validates metadata against schema definition."""

    @staticmethod
    def get_valid_reference_types() -> list[str]:
        """Get valid reference types from authoritative enum."""
        return ReferenceType.choices()

    @staticmethod
    def get_valid_reference_modes() -> list[str]:
        """Get valid reference modes from authoritative enum."""
        return ReferenceMode.choices()

    # ... etc for all enums
```

#### 2. Refactor `md.py` - Syntax + Basic Checks Only

**Keep:**
- YAML parsing errors
- Markdown structure validation
- File naming validation
- Internal link validation
- Required field presence (`date`)

**Remove (delegate to schema.py):**
- Enum validation → Call `SchemaValidator.validate_enum()`
- Field type checking → Call `SchemaValidator.validate_types()`
- Deep structure validation → Leave for metadata.py

**After refactor:**
```python
from dev.validators.schema import SchemaValidator

class MarkdownValidator:
    def _validate_frontmatter(self, ...):
        # YAML syntax only
        frontmatter = yaml.safe_load(...)

        # Required fields
        if "date" not in frontmatter:
            # error

        # Delegate enum validation
        if "references" in frontmatter:
            SchemaValidator.validate_references_schema(frontmatter["references"])
```

#### 3. Refactor `metadata.py` - Parser Compatibility Only

**Keep:**
- Cross-field dependency validation (city ↔ locations)
- Nested structure validation (dates with people/locations)
- Parser-specific format requirements
- Content OR description requirement for references

**Remove (delegate to schema.py):**
- Enum validation → Use SchemaValidator
- Basic type checking → Use SchemaValidator

**After refactor:**
```python
from dev.validators.schema import SchemaValidator

class MetadataValidator:
    def validate_references_field(self, ...):
        # Schema validation first (types, enums)
        schema_issues = SchemaValidator.validate_references_schema(references_list)
        issues.extend(schema_issues)

        # Then parser-specific rules
        for ref in references_list:
            # content OR description requirement
            if not ref.get("content") and not ref.get("description"):
                # error
```

#### 4. Update Enum Source Imports

**All validators must import from:**
```python
from dev.database.models.enums import (
    ReferenceType,
    ReferenceMode,
    RelationType,
    ManuscriptStatus,  # If this enum exists
)
```

**Never hardcode enum values.**

---

## Implementation Plan

### Phase 1: Quick Fixes (Done)
- ✅ Add missing `website` type to both validators
- ✅ Document the issue

### Phase 2: Create Schema Validator (1-2 hours)
1. Create `dev/validators/schema.py`
2. Implement `SchemaValidator` class
3. Add enum import methods
4. Add schema validation methods for each field type
5. Write unit tests

### Phase 3: Refactor md.py (2-3 hours)
1. Remove enum hardcoding
2. Import from schema.py
3. Remove deep validation logic
4. Update tests
5. Update documentation

### Phase 4: Refactor metadata.py (2-3 hours)
1. Remove enum hardcoding
2. Import from schema.py
3. Focus on parser-specific rules only
4. Update tests
5. Update documentation

### Phase 5: Documentation (1 hour)
1. Update dev guides
2. Clarify when to use each validator
3. Add architecture diagram
4. Document validation layers

### Phase 6: Testing (1-2 hours)
1. Run full test suite
2. Test with real journal entries
3. Verify no regressions
4. Test edge cases

**Total estimated time:** 7-12 hours

---

## Benefits

### Immediate
- ✅ Fixes website type validation bug
- Prevents future enum sync issues
- Clearer separation of concerns

### Long-term
- **Maintainability:** Single source of truth for enums
- **Consistency:** All validators use same enum values
- **Clarity:** Clear understanding of which validator does what
- **Extensibility:** Easy to add new enum values (one place)
- **Performance:** Can run lightweight `md.py` in editor, full validation in CI
- **Testing:** Easier to test each layer independently

---

## Migration Path

### For Users

**Before:**
```bash
# Confusing - which one to use?
plm validate md all
plm validate metadata all
```

**After:**
```bash
# Clear purpose for each
plm validate syntax    # Fast, editor-friendly (md.py)
plm validate schema    # Schema compliance (schema.py)
plm validate structure # Parser compatibility (metadata.py)
plm validate all       # Run all layers
```

### Backward Compatibility

- Keep existing commands working
- `plm validate md all` → runs Layers 1-3
- `plm validate metadata all` → runs Layers 2-3
- Add deprecation warnings
- Remove old commands in future version

---

## Risks & Mitigation

### Risk 1: Breaking Changes
**Mitigation:** Extensive testing, backward compatibility layer

### Risk 2: Increased Complexity
**Mitigation:** Clear documentation, gradual rollout

### Risk 3: Migration Effort
**Mitigation:** Incremental refactoring, one layer at a time

---

## Conclusion

The current validator architecture has significant design flaws that lead to:
- Maintenance burden (duplicate code)
- Inconsistent validation (enums out of sync)
- User confusion (which validator to use?)

**Recommendation:** Proceed with phased refactoring.

**Priority:** High - This affects data integrity and user experience.

**Next Steps:**
1. Review and approve this proposal
2. Create GitHub issue/task
3. Begin Phase 2 (schema validator implementation)

---

## Appendix: Current Duplication Map

| Validation Concern | md.py | metadata.py | Authoritative Source |
|-------------------|-------|-------------|---------------------|
| Reference modes | Lines 128 | Lines 106 | `models/enums.py:ReferenceMode` |
| Reference types | Lines 131-143 | Lines 109-121 | `models/enums.py:ReferenceType` |
| Manuscript status | Lines 117-125 | Lines 96-103 | ??? (Discrepancy!) |
| Date format | Line 312 | Implied | `core/validators.py:DataValidator` |
| Required fields | Line 96 | Implied | Schema definition (nowhere!) |

**Total lines of duplicated enum definitions:** ~60 lines
**Total lines of duplicated validation logic:** ~400 lines (estimated)
