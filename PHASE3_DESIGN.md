# Phase 3: wiki2sql — Design Document

**Goal:** Enable bidirectional sync by parsing wiki files and updating the database with manual edits.

## Overview

Phase 3 implements the reverse direction of the sql2wiki pipeline:
- **Phase 2:** Database → Wiki (sql2wiki)
- **Phase 3:** Wiki → Database (wiki2sql)

This enables writers to manually edit wiki pages and have those changes flow back into the database, completing the bidirectional sync loop.

## Field Ownership Strategy

### Database-Computed Fields (READ ONLY from wiki)
These are calculated by the database and should NOT be imported from wiki:
- Mention counts, entry counts, visit counts
- Word counts, reading time
- Dates (first appearance, last appearance, etc.)
- Relationship lists (people, locations, events, etc.)
- Statistics and aggregates

### Wiki-Editable Fields (WRITABLE to database)
These can be manually edited in wiki and imported back:

**Person:**
- `notes` - User notes for manuscript use
- `vignette` - Character description for manuscript
- `category` - Relationship category (if changed)

**Entry:**
- `notes` - User notes about the entry
- `manuscript_status` - Status override (if exists)

**Theme:**
- `notes` - Thematic analysis notes

**Tag:**
- `notes` - Tag usage notes

**Poem:**
- `notes` - Poem analysis notes

**Reference:**
- `notes` - Reference notes

**Location:**
- `notes` - Location description notes

**City:**
- `notes` - City context notes

**Event:**
- `notes` - Event narrative notes

## Architecture

### 1. Wiki Parser (`dev/utils/wiki_parser.py`)

Utility functions for parsing vimwiki markdown:

```python
def parse_wiki_file(file_path: Path) -> Dict[str, Any]:
    """Parse wiki file into sections."""
    sections = extract_sections(content)
    return sections

def extract_section(content: str, header: str) -> Optional[str]:
    """Extract content under a specific header."""
    pass

def extract_editable_field(content: str, field_name: str) -> Optional[str]:
    """Extract a specific editable field value."""
    pass
```

### 2. WikiEntity.from_file() Implementation

Each WikiEntity dataclass needs `from_file()` implemented:

```python
@classmethod
def from_file(cls, file_path: Path) -> "WikiEntity":
    """
    Parse wiki file and extract editable fields.

    Returns a partial WikiEntity with only editable fields populated.
    This is merged with database data during sync.
    """
    sections = parse_wiki_file(file_path)

    return cls(
        path=file_path,
        notes=extract_section(sections, "Notes"),
        vignette=extract_section(sections, "Vignette"),  # Person only
        # Other computed fields left empty
    )
```

### 3. wiki2sql Pipeline (`dev/pipeline/wiki2sql.py`)

Main pipeline for importing wiki edits:

```python
def import_person(wiki_file: Path, db: PalimpsestDB, logger) -> str:
    """
    Import person wiki edits to database.

    1. Parse wiki file with from_file()
    2. Find corresponding database record
    3. Update only editable fields
    4. Save to database

    Returns: "updated" or "skipped"
    """
    pass

def import_people(wiki_dir: Path, db: PalimpsestDB, logger) -> ImportStats:
    """Batch import all people from wiki."""
    pass
```

### 4. Sync Detection

Compare timestamps to detect changes:

```python
def needs_sync(wiki_file: Path, db_entity: Any) -> bool:
    """
    Check if wiki file is newer than database record.

    Compare file mtime with db_entity.updated_at
    """
    file_mtime = wiki_file.stat().st_mtime
    db_updated = db_entity.updated_at.timestamp()
    return file_mtime > db_updated

def detect_conflict(wiki_file: Path, db_entity: Any, last_sync: datetime) -> bool:
    """
    Detect if both wiki and database changed since last sync.

    Returns True if conflict exists.
    """
    pass
```

### 5. CLI Structure

```bash
# Import specific entity type
python -m dev.pipeline.wiki2sql import people
python -m dev.pipeline.wiki2sql import entries

# Import all entities
python -m dev.pipeline.wiki2sql import all

# Sync with conflict detection
python -m dev.pipeline.wiki2sql sync people --handle-conflicts
```

## Implementation Plan

### Phase 3.1: Foundation (Person entity)
1. Create `dev/utils/wiki_parser.py` with parsing utilities
2. Implement `WikiPerson.from_file()`
3. Create basic `wiki2sql.py` with `import_person()`
4. Test: Edit person wiki → import → verify database

### Phase 3.2: Remaining Entities
5. Implement `from_file()` for all other entities
6. Add import functions for each entity
7. Test each entity type

### Phase 3.3: Sync Detection
8. Implement timestamp comparison
9. Add conflict detection
10. Create merge strategies

### Phase 3.4: CLI & Testing
11. Complete CLI with all commands
12. Comprehensive testing
13. Documentation

## Parsing Strategy

### Section Headers to Parse

**Person:**
```markdown
### Notes
[User editable content]

### Vignette
[User editable character description]
```

**All Entities:**
```markdown
### Notes
[User editable content]
```

### Parsing Algorithm

1. Read file content
2. Split by `###` headers
3. Extract section content
4. Trim whitespace
5. Handle special markers (e.g., `[Add notes...]`)

## Error Handling

### Missing Files
- Skip with warning
- Continue with other files

### Parse Errors
- Log error
- Skip file
- Continue processing

### Database Errors
- Rollback transaction
- Log error
- Return error status

### Conflicts
- Option 1: Database wins (default)
- Option 2: Wiki wins (with --force)
- Option 3: Manual merge (future)

## Testing Strategy

### Unit Tests
- Test wiki parser with sample files
- Test from_file() with various inputs
- Test import functions

### Integration Tests
1. Export entity to wiki
2. Manually edit wiki file
3. Import back to database
4. Verify changes persisted
5. Verify computed fields unchanged

### Edge Cases
- Empty notes
- Missing sections
- Malformed wiki syntax
- Non-existent database records
- Deleted entities

## Success Criteria

✅ All WikiEntity.from_file() methods implemented
✅ Wiki parser handles all entity types
✅ Import functions work for all entities
✅ Editable fields sync correctly
✅ Read-only fields remain unchanged
✅ Conflicts detected and handled
✅ CLI provides good UX
✅ Comprehensive testing
✅ Documentation complete

## Estimated Effort

- Wiki parser: ~200 lines
- from_file() implementations: ~500 lines (9 entities × ~55 lines each)
- Import functions: ~400 lines
- Sync detection: ~150 lines
- CLI: ~200 lines
- Tests: ~300 lines
- **Total: ~1,750 lines**

## Files to Create/Modify

**New files:**
- `dev/utils/wiki_parser.py` (~200 lines)
- `dev/pipeline/wiki2sql.py` (~600 lines)

**Modified files:**
- `dev/dataclasses/wiki_person.py` (add from_file)
- `dev/dataclasses/wiki_theme.py` (add from_file)
- `dev/dataclasses/wiki_tag.py` (add from_file)
- `dev/dataclasses/wiki_poem.py` (add from_file)
- `dev/dataclasses/wiki_reference.py` (add from_file)
- `dev/dataclasses/wiki_entry.py` (add from_file)
- `dev/dataclasses/wiki_location.py` (add from_file)
- `dev/dataclasses/wiki_city.py` (add from_file)
- `dev/dataclasses/wiki_event.py` (add from_file)

**Total modifications:** ~900 lines across 9 dataclass files

## Next Steps

1. Create wiki parser utilities
2. Implement WikiPerson.from_file()
3. Create basic wiki2sql.py
4. Test person import
5. Expand to other entities
6. Add sync detection
7. Complete CLI
8. Full testing
9. Documentation
