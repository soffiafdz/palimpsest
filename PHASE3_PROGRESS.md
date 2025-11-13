# Phase 3: wiki2sql — Progress Report

**Status:** 🚧 IN PROGRESS (Foundation Complete)
**Started:** 2025-01-13
**Phase 3.1 Complete:** 2025-01-13

## Overview

Phase 3 implements bidirectional sync by enabling wiki files to be parsed and imported back into the database. This completes the sync loop:

- **Phase 2:** Database → Wiki (sql2wiki) ✅ COMPLETE
- **Phase 3:** Wiki → Database (wiki2sql) 🚧 IN PROGRESS

## Phase 3.1: Foundation ✅ COMPLETE

### Implemented (Commit: cbbd2fd)

**1. Wiki Parser Utilities** (`dev/utils/wiki_parser.py`, 280 lines)

Core parsing functions for extracting data from vimwiki markdown:

```python
# Main parsing functions
parse_wiki_file()          # Extract sections from wiki file
extract_section()          # Get content under specific header
extract_notes()            # Extract Notes section (handles placeholders)
extract_vignette()         # Extract Vignette section (Person only)
extract_category()         # Extract category from metadata
extract_metadata_field()   # Extract any metadata field
parse_wiki_links()         # Parse [[link|text]] format
is_placeholder()           # Detect placeholder text
```

**Features:**
- Section-based parsing (splits by `###` headers)
- Placeholder detection (`[Add notes...]` → returns None)
- Wiki link parsing (`[[path|text]]`)
- Metadata field extraction
- Robust error handling

**2. WikiEntity.from_file() Implementations**

Implemented for 3 core entities:

**WikiTheme.from_file()** - Parses:
- `notes` - User notes
- `description` - Theme description

**WikiTag.from_file()** - Parses:
- `notes` - User notes

**WikiEntry.from_file()** - Parses:
- `notes` - User notes about entry

**Pattern:**
```python
@classmethod
def from_file(cls, path: Path) -> Optional["Entity"]:
    """Parse wiki file and extract editable fields only."""
    sections = parse_wiki_file(path)
    notes = extract_notes(sections)
    # Extract name from filename
    # Return instance with only editable fields populated
```

**3. Design Document** (`PHASE3_DESIGN.md`)

Comprehensive design covering:
- Field ownership strategy (read-only vs editable)
- Architecture (parser, from_file, import functions, sync)
- Implementation plan (phased approach)
- Testing strategy
- Estimated effort: ~1,750 lines total

### How It Works

The foundation enables **manual wiki edits to be preserved** when regenerating wiki files:

**Current Flow:**
1. User runs `sql2wiki export people`
2. `WikiPerson.from_database()` is called
3. It checks if wiki file already exists
4. If yes, calls `WikiPerson.from_file()` to extract manual edits
5. Preserves `notes`, `vignette`, `category` from wiki
6. Merges with fresh database data
7. Writes updated wiki file **preserving manual edits**

**This already works for:**
- ✅ Person (already had from_file implemented)
- ✅ Theme (newly implemented)
- ✅ Tag (newly implemented)
- ✅ Entry (newly implemented)

### Testing

Manual test verified:
1. Export entity to wiki
2. Manually edit Notes section in wiki file
3. Re-export from database
4. **Manual edits preserved** ✅

## Phase 3.2: Remaining Entities (PENDING)

Need to implement `from_file()` for:

**Remaining Phase 2 Entities:**
- ❌ Poem - needs notes parsing
- ❌ Reference - needs notes parsing

**Phase 2 Extended Entities:**
- ❌ Location - needs notes parsing
- ❌ City - needs notes parsing
- ❌ Event - needs notes parsing

**Estimated:** ~250 lines (5 entities × ~50 lines each)

**Pattern to follow:**
```python
@classmethod
def from_file(cls, path: Path) -> Optional["Entity"]:
    if not path.exists():
        return None

    try:
        from dev.utils.wiki_parser import parse_wiki_file, extract_notes
        sections = parse_wiki_file(path)
        name = path.stem.replace("_", " ")
        notes = extract_notes(sections)

        return cls(
            path=path,
            name=name,
            notes=notes,
        )
    except Exception as e:
        sys.stderr.write(f"Error parsing {path}: {e}\n")
        return None
```

## Phase 3.3: Import Pipeline (PENDING)

Create `dev/pipeline/wiki2sql.py` for batch import:

**Functions needed:**
```python
def import_person(wiki_file: Path, db: PalimpsestDB) -> str
def import_people(wiki_dir: Path, db: PalimpsestDB) -> ImportStats
# ... similar for other entities
```

**Flow:**
1. Find all wiki files for entity type
2. For each file:
   - Parse with `from_file()`
   - Find corresponding database record
   - Update only editable fields
   - Save to database
3. Return statistics

**Estimated:** ~600 lines

## Phase 3.4: Sync Detection (PENDING)

Add timestamp-based conflict detection:

```python
def needs_sync(wiki_file: Path, db_entity: Any) -> bool:
    """Compare file mtime with db updated_at."""
    pass

def detect_conflict(wiki_file: Path, db_entity: Any) -> bool:
    """Detect if both changed since last sync."""
    pass
```

**Estimated:** ~150 lines

## Phase 3.5: CLI & Testing (PENDING)

Complete CLI interface:

```bash
# Import from wiki to database
python -m dev.pipeline.wiki2sql import people
python -m dev.pipeline.wiki2sql import entries
python -m dev.pipeline.wiki2sql import all

# Sync with conflict detection
python -m dev.pipeline.wiki2sql sync all --handle-conflicts
```

**Estimated:** ~200 lines CLI + ~300 lines tests = ~500 lines

## Summary

### Completed (Phase 3.1)
- ✅ Wiki parser utilities (280 lines)
- ✅ Design document (comprehensive)
- ✅ from_file() for Theme, Tag, Entry
- ✅ Manual edits preservation working
- **Total: ~700 lines**

### Remaining Work
- ⏳ from_file() for 5 more entities (~250 lines)
- ⏳ Import pipeline (wiki2sql.py, ~600 lines)
- ⏳ Sync detection (~150 lines)
- ⏳ CLI & testing (~500 lines)
- **Total: ~1,500 lines**

### Overall Progress
- **Phase 3 Total:** ~2,200 lines estimated
- **Completed:** ~700 lines (32%)
- **Remaining:** ~1,500 lines (68%)

## Next Steps

**Option A: Complete Phase 3.2 (Remaining Entities)**
- Quick win: 5 similar implementations
- ~30 minutes of work
- Makes foundation more complete

**Option B: Jump to Phase 3.3 (Import Pipeline)**
- More impactful: actual wiki→database import
- Demonstrates full bidirectional sync
- Can test with existing entities (Theme, Tag, Entry)

**Option C: Focus on Testing/Documentation**
- Validate Phase 3.1 foundation
- Create usage examples
- Document the bidirectional workflow

**Recommendation:** Option B - Create import pipeline to demonstrate working bidirectional sync with the 3 entities we have. This provides immediate value and can be extended to other entities later.

## Benefits of Phase 3.1

Even with just the foundation, the system now:

1. **Preserves manual edits** when regenerating wiki files
2. **Enables iterative workflow:** Edit wiki → regenerate → edits preserved
3. **Provides parsing infrastructure** for full import pipeline
4. **Documents clear path forward** with design doc

The foundation is solid and ready for expansion!

**Status: Phase 3.1 COMPLETE, ready for Phase 3.2+** ✅
