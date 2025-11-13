# Palimpsest Bidirectional Sync Guide

**Complete implementation guide for all bidirectional data synchronization paths**

Date: 2025-11-13
Status: Complete ✅

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [YAML ↔ SQL Pipeline](#yaml--sql-pipeline)
4. [SQL ↔ Wiki Pipeline](#sql--wiki-pipeline)
5. [Field Ownership Strategy](#field-ownership-strategy)
6. [Testing Guide](#testing-guide)
7. [Troubleshooting](#troubleshooting)

---

## Overview

Palimpsest implements **three-layer bidirectional synchronization**:

```
┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
│  Journal Files   │ ←────→  │   SQL Database   │ ←────→  │   Wiki Pages     │
│  (Markdown)      │         │   (SQLite)       │         │   (Vimwiki)      │
│                  │         │                  │         │                  │
│  YAML metadata   │         │  Normalized      │         │  Human-readable  │
│  Entry content   │         │  Relationships   │         │  Entity pages    │
└──────────────────┘         └──────────────────┘         └──────────────────┘
     Primary                      Central                     Navigation
   Source Material              Source of Truth             & Exploration
```

### Data Flow Principles

1. **Journal → Database**: Single source of truth for life events
2. **Database → Wiki**: Auto-generated navigation & exploration
3. **Wiki → Database**: Editable notes only (not structural data)

---

## Architecture

### Three Synchronization Paths

#### Path 1: YAML ↔ SQL (Journal Entries)
- **Purpose**: Capture and persist journal metadata
- **Direction**: Fully bidirectional
- **Primary Flow**: YAML → SQL (journaling workflow)
- **Reverse Flow**: SQL → YAML (export/backup)

#### Path 2: SQL → Wiki (Entity Export)
- **Purpose**: Generate navigable wiki for exploration
- **Direction**: One-way (SQL → Wiki)
- **Update Mode**: Regenerate from database

#### Path 3: Wiki → SQL (Entity Import)
- **Purpose**: Sync user edits back to database
- **Direction**: One-way (Wiki → SQL)
- **Update Mode**: Import only editable fields

### Complete Data Flow

```
    ┌─────────────────────────────────────────────────────────────┐
    │                  PALIMPSEST DATA FLOW                        │
    └─────────────────────────────────────────────────────────────┘

┌─────────────┐
│   Journal   │  Write new entry
│   (*.md)    │  with YAML metadata
└──────┬──────┘
       │
       │ yaml2sql.py
       │ (import)
       ↓
┌─────────────────────────────────────────────────────┐
│                   SQL Database                      │
│                                                     │
│  ┌──────────┐  ┌─────────┐  ┌──────────┐          │
│  │ Entries  │  │ People  │  │ Events   │          │
│  └────┬─────┘  └────┬────┘  └────┬─────┘          │
│       │             │            │                 │
│       └─────────────┴────────────┘                 │
│              Relationships                         │
│                                                     │
│  ┌──────────────────────────────────────┐          │
│  │  Manuscript Tables (Subwiki)         │          │
│  │  - ManuscriptEntry                   │          │
│  │  - ManuscriptPerson (Characters)     │          │
│  │  - ManuscriptEvent (Plot points)     │          │
│  └──────────────────────────────────────┘          │
└───────────┬─────────────────────┬───────────────────┘
            │                     │
            │ sql2wiki            │ manuscript2wiki
            │ (export)            │ (export)
            ↓                     ↓
┌─────────────────────┐  ┌─────────────────────┐
│   Main Wiki         │  │ Manuscript Subwiki  │
│   data/wiki/        │  │ data/wiki/manuscript│
│                     │  │                     │
│  - entries/         │  │  - entries/         │
│  - people/          │  │  - characters/      │
│  - events/          │  │  - events/          │
│  - locations/       │  │  - arcs/            │
│  - cities/          │  │  - themes/          │
│  - themes/          │  │                     │
│  - tags/            │  │                     │
│  - poems/           │  │                     │
│  - references/      │  │                     │
│  - timeline.md      │  │  - index.md         │
│  - stats.md         │  │                     │
│  - analysis.md      │  │                     │
└──────┬──────────────┘  └──────┬──────────────┘
       │                        │
       │ wiki2sql               │ wiki2sql
       │ (import notes)         │ (import manuscript-*)
       ↓                        ↓
┌─────────────────────────────────────────────────────┐
│         Database (Notes Updated)                    │
│                                                     │
│  Entry.notes ← wiki edits                          │
│  Person.notes ← wiki edits                         │
│  ManuscriptEntry.notes ← manuscript wiki edits     │
│  ManuscriptEntry.character_notes ← manuscript wiki │
└─────────────────────────────────────────────────────┘
```

---

## YAML ↔ SQL Pipeline

### Overview

**Purpose**: Bidirectional sync between journal markdown files and database

**Files**:
- `dev/pipeline/yaml2sql.py` - Import journal → database
- `dev/pipeline/sql2yaml.py` - Export database → journal
- `dev/dataclasses/md_entry.py` - Intermediary dataclass

### YAML → SQL (Primary Flow)

#### Use Case
You write a journal entry with YAML frontmatter and import it to the database.

#### Process

1. **Write Journal Entry**
   ```yaml
   # journal/md/2024/2024-11-01.md
   ---
   date: 2024-11-01
   word_count: 500
   reading_time: 2.5
   city: Montreal
   locations: [Café Olimpico, Parc Jarry]
   people:
     - Alice
     - Bob
   events: [therapy-session, madrid-trip-2024]
   tags: [reflection, growth]
   manuscript:
     status: source
     edited: true
   ---

   Today was transformative. Met Alice at Café Olimpico...
   ```

2. **Import to Database**
   ```bash
   python -m dev.pipeline.yaml2sql update journal/md/2024/2024-11-01.md
   ```

3. **What Happens**
   - `MdEntry.from_file()` parses YAML frontmatter
   - `MdEntry.to_database_metadata()` converts to DB format
   - `EntryManager.create()` or `.update()` processes entry
   - Relationships auto-created:
     - People: Creates `Person(name="Alice")` if doesn't exist
     - Cities: Creates `City(city="Montreal")` if doesn't exist
     - Locations: Creates `Location(name="Café Olimpico", city=montreal)`
     - Events: Creates `Event(event="therapy-session")` if doesn't exist
     - Tags: Creates `Tag(tag="reflection")` if doesn't exist
   - Manuscript metadata:
     - Creates/updates `ManuscriptEntry(status="source", edited=True)`

4. **Change Detection**
   - Computes MD5 hash of file content
   - Stores in `Entry.file_hash`
   - Skips import if hash unchanged (unless `--force`)

#### Supported YAML Fields

**Core Fields** (always synced):
```yaml
date: 2024-11-01              # Required
word_count: 500               # Required
reading_time: 2.5             # Required
epigraph: "Quote text"        # Optional
epigraph_attribution: "Author" # Optional
notes: "Editorial notes"      # Optional
```

**Geographic Fields**:
```yaml
# Single city
city: Montreal

# Multiple cities
city: [Montreal, Toronto]

# Flat locations (single city context)
locations: [Café A, Park B]

# Nested locations (multiple cities)
locations:
  Montreal: [Café Olimpico, Parc Jarry]
  Toronto: [Trinity Bellwoods, Queen St]
```

**People Fields**:
```yaml
# Simple list
people: [Alice, Bob, Dr-Martinez]

# With full names
people:
  - name: Alice
    full_name: Alice Johnson
  - Bob

# With aliases
people:
  - alias: @alex
    full_name: Alexandra Smith
  - alias: [@dr-m, @martinez]
    name: Dr-Martinez
```

**Relationship Fields**:
```yaml
events: [therapy-session, conference-2024]
tags: [reflection, milestone]
related_entries: [2024-01-15, 2024-02-20]

dates:
  - "2024-11-01"
  - "2024-12-25 (Christmas)"
  - date: 2024-06-15
    context: "Alice's wedding"
    locations: [Central Park]
    people: [Alice, Bob]
```

**Complex Fields**:
```yaml
references:
  - content: "To be or not to be"
    source:
      title: Hamlet
      type: book
      author: William Shakespeare
    mode: direct

poems:
  - title: "Morning Light"
    content: |
      First line
      Second line
    revision_date: 2024-11-01
    notes: "Experimental form"
```

**Manuscript Fields** (minimal in YAML):
```yaml
manuscript:
  status: source      # Flag for inclusion
  edited: true        # Editing state
```

**NOT in YAML** (manuscript wiki only):
- `entry_type` - Use manuscript wiki
- `character_notes` - Use manuscript wiki
- `narrative_arc` - Use manuscript wiki
- `themes` - Use manuscript wiki

### SQL → YAML (Reverse Flow)

#### Use Case
Export database back to markdown files (backup, sharing, editing).

#### Process

1. **Export from Database**
   ```bash
   # Single entry
   python -m dev.pipeline.sql2yaml export 2024-11-01 -o output/

   # Date range
   python -m dev.pipeline.sql2yaml range 2024-01-01 2024-12-31 -o output/

   # All entries
   python -m dev.pipeline.sql2yaml all -o output/
   ```

2. **What Happens**
   - Queries `Entry` with all relationships loaded
   - `MdEntry.from_database()` converts DB → dataclass
   - `MdEntry._generate_yaml_frontmatter()` generates YAML
   - `MdEntry.to_markdown()` combines frontmatter + body
   - Writes to file with UTF-8 encoding

3. **Content Preservation Strategies**

   **Strategy 1**: Preserve existing body (default)
   ```python
   export_entry_to_markdown(entry, output_dir, preserve_body=True)
   ```
   - Reads existing markdown file
   - Extracts body content (after frontmatter)
   - Combines with NEW frontmatter from database
   - Use case: Database edits, preserve text

   **Strategy 2**: Use source file
   ```python
   # If entry.file_path exists
   ```
   - Reads body from original journal file
   - Use case: Initial export from database

   **Strategy 3**: Generate placeholder
   ```python
   # If no existing content
   ```
   - Creates minimal body: "Entry for {date}"
   - Use case: New entries without source

#### Generated YAML Format

The export generates human-readable, properly formatted YAML:

```yaml
---
date: 2024-11-01
word_count: 500
reading_time: 2.5

city: Montreal

locations:
  Montreal: [Café Olimpico, Parc Jarry]

people:
  - Alice
  - Bob
  - "@alex (Alexandra Smith)"

events: [therapy-session, madrid-trip-2024]

tags: [reflection, growth]

dates:
  - "2024-11-01"
  - date: 2024-12-25
    context: "Christmas celebration"
    locations: [Home]
    people: [Family]

related_entries: [2024-10-15]

references:
  - content: "Quote content"
    source:
      title: Book Title
      type: book
      author: Author Name

poems:
  - title: "Poem Title"
    content: |
      Line 1
      Line 2
    revision_date: 2024-11-01

manuscript:
  status: source
  edited: true

notes: |
  Editorial notes
  Multiple lines
---

Entry body content...
```

### Implementation Details

#### Change Detection

**File Hash Strategy**:
```python
def should_skip_file(file_path: Path, stored_hash: str, force: bool) -> bool:
    """Check if file needs processing."""
    if force:
        return False

    current_hash = compute_md5_hash(file_path)
    return current_hash == stored_hash
```

**Hash Storage**:
- Field: `Entry.file_hash`
- Type: MD5 hex string
- Updated: On every import
- Usage: Skip unchanged files in incremental sync

#### Error Handling

**yaml2sql**:
- Validation errors logged with context
- Parsing failures don't stop batch processing
- Transaction rollback on database errors
- Comprehensive error statistics

**sql2yaml**:
- Missing source files handled gracefully
- Invalid paths logged as warnings
- Relationship loading errors caught
- File write failures don't crash process

---

## SQL ↔ Wiki Pipeline

### Overview

**Purpose**: Generate navigable wiki and sync user edits

**Files**:
- `dev/pipeline/sql2wiki.py` - Export database → wiki
- `dev/pipeline/wiki2sql.py` - Import wiki notes → database
- `dev/pipeline/manuscript2wiki.py` - Export manuscript subwiki
- `dev/dataclasses/wiki_*.py` - Wiki entity dataclasses

### SQL → Wiki (Export Flow)

#### Use Case
Generate or update vimwiki pages from database for browsing.

#### Process

1. **Export Entities**
   ```bash
   # Single entity type
   python -m dev.pipeline.sql2wiki export people
   python -m dev.pipeline.sql2wiki export entries

   # Special pages
   python -m dev.pipeline.sql2wiki export timeline
   python -m dev.pipeline.sql2wiki export stats
   python -m dev.pipeline.sql2wiki export analysis

   # Everything
   python -m dev.pipeline.sql2wiki export all
   ```

2. **What Gets Exported**

   **Main Wiki** (`data/wiki/`):
   - `entries/YYYY/YYYY-MM-DD.md` - Entry pages with navigation
   - `people/person_name.md` - Person pages with entries
   - `locations/city/location_name.md` - Location pages
   - `cities/city_name.md` - City pages
   - `events/event_name.md` - Event pages
   - `themes/theme_name.md` - Theme pages
   - `tags/tag_name.md` - Tag pages
   - `poems/poem_title.md` - Poem pages
   - `references/source_title.md` - Reference pages
   - `timeline.md` - Calendar view
   - `stats.md` - Statistics dashboard
   - `analysis.md` - Analysis with visualizations
   - `index.md` - Homepage

   **Manuscript Subwiki** (`data/wiki/manuscript/`):
   - `entries/YYYY/YYYY-MM-DD.md` - Manuscript entry pages
   - `characters/character_name.md` - Character pages (from People)
   - `events/event_name.md` - Manuscript event pages
   - `arcs/arc_name.md` - Story arc pages
   - `themes/theme_name.md` - Theme pages
   - `index.md` - Manuscript homepage

3. **Export Process**

   **For each entity**:
   - Query database with relationships
   - Convert to WikiEntity dataclass
   - Generate markdown with `to_wiki()`
   - Compute content hash
   - Write if changed (or forced)

4. **Entity Example: Person Page**

   **Database Query**:
   ```python
   person = session.query(Person).options(
       joinedload(Person.entries),
       joinedload(Person.dates),
   ).filter_by(name="Alice").first()
   ```

   **Conversion**:
   ```python
   wiki_person = WikiPerson.from_database(
       db_person=person,
       wiki_dir=wiki_dir,
   )
   ```

   **Generated Wiki** (`data/wiki/people/alice.md`):
   ```markdown
   # Palimpsest — Person

   *[[../index.md|Home]] > [[../people.md|People]] > Alice*

   ## Alice

   **Full Name:** Alice Johnson
   **Relation:** friend

   ### Appearances (2 entries)

   - [[../entries/2024/2024-11-01.md|2024-11-01]] — 500 words
   - [[../entries/2024/2024-11-05.md|2024-11-05]] — 600 words

   ### Associated Dates

   - 2024-11-01 — Coffee meetup
   - 2024-12-25 — Holiday celebration

   ### Notes

   [Add your notes about Alice for manuscript use]
   ```

5. **Manuscript Subwiki Export**

   ```bash
   # Export manuscript entities
   python -m dev.pipeline.manuscript2wiki export all

   # Specific entities
   python -m dev.pipeline.manuscript2wiki export entries
   python -m dev.pipeline.manuscript2wiki export characters
   ```

   **Manuscript Entry Page** (`data/wiki/manuscript/entries/2024/2024-11-01.md`):
   ```markdown
   # Palimpsest — Manuscript Entry

   ## 2024-11-01

   **Original Entry:** [[../../../entries/2024/2024-11-01.md|View Main Wiki]]
   **Source:** [[../../../../../../journal/md/2024/2024-11-01.md|Read Full Entry]]

   ### Manuscript Metadata

   **Status:** source
   **Entry Type:** vignette
   **Narrative Arc:** paris_discovery

   ### Characters

   - **Alice** → Alexandra (Real: [[../../../people/alice.md|Alice]])
   - **Bob** → Robert (Real: [[../../../people/bob.md|Bob]])

   ### Adaptation Notes

   Transform the coffee shop scene into a turning point...

   ### Character Notes

   Alice becomes Alexandra - soften her directness, add introspection.
   Bob as Robert - maintain wit but add vulnerability.

   ### Navigation

   **Previous:** [[2024-04-05.md|2024-04-05]]
   **Next:** [[2024-11-05.md|2024-11-05]]
   ```

### Wiki → SQL (Import Flow)

#### Use Case
You edit notes in wiki pages, sync changes back to database.

#### Process

1. **Edit Wiki Notes**

   Edit the `### Notes` section in any wiki page:

   ```markdown
   # data/wiki/people/alice.md

   ### Notes

   Alice is a childhood friend. Met in elementary school.
   Key characteristic: extremely organized, planner personality.
   For manuscript: Could become the "voice of reason" character.
   ```

2. **Import Changes**
   ```bash
   # Import single entity type
   python -m dev.pipeline.wiki2sql import people
   python -m dev.pipeline.wiki2sql import entries

   # Import all main wiki
   python -m dev.pipeline.wiki2sql import all

   # Import manuscript wiki
   python -m dev.pipeline.wiki2sql import manuscript-entries
   python -m dev.pipeline.wiki2sql import manuscript-characters
   python -m dev.pipeline.wiki2sql import manuscript-all
   ```

3. **What Gets Imported**

   **Main Wiki**:
   - `Entry.notes` ← from entry wiki pages
   - `Person.notes` ← from people wiki pages
   - `Event.notes` ← from event wiki pages
   - `Theme.notes` ← from theme wiki pages
   - `Tag.notes` ← from tag wiki pages

   **Manuscript Subwiki**:
   - `ManuscriptEntry.notes` ← adaptation notes
   - `ManuscriptEntry.character_notes` ← character notes
   - `ManuscriptPerson.character_description` ← character description
   - `ManuscriptPerson.character_arc` ← character arc notes
   - `ManuscriptPerson.voice_notes` ← voice notes
   - `ManuscriptPerson.appearance_notes` ← appearance notes
   - `ManuscriptEvent.notes` ← event notes

4. **Import Process**

   **For each wiki file**:
   - Parse wiki file with `WikiEntity.from_file()`
   - Extract editable fields (notes only)
   - Find corresponding database record
   - Update only editable fields
   - Database-computed fields unchanged

5. **Example: Person Import**

   ```python
   # dev/pipeline/wiki2sql.py
   def import_person(wiki_file: Path, db: PalimpsestDB, logger) -> str:
       # Parse wiki file
       person = WikiPerson.from_file(wiki_file)

       # Find database record
       with db.session_scope() as session:
           db_person = session.query(Person).filter_by(
               name=person.name
           ).first()

           if not db_person:
               return "skipped"

           # Update ONLY editable field
           db_person.notes = person.notes

           session.commit()

       return "updated"
   ```

### Implementation Details

#### Generic Entity Exporter

**Configuration-Driven Design**:
```python
# dev/pipeline/entity_exporter.py

@dataclass
class EntityConfig:
    name: str              # "person"
    plural: str            # "people"
    db_model: Type         # Person
    wiki_class: Type       # WikiPerson
    output_subdir: str     # "people"
    index_filename: str    # "people.md"
    eager_loads: List[str] # ["entries", "dates"]
    index_builder: Optional[Callable]  # Custom or default
    sort_by: str           # Property for sorting
    order_by: str          # Database column

# Register entity
register_entity("people", EntityConfig(...))

# Use exporter
exporter = get_exporter("people")
stats = exporter.export_all(db, wiki_dir, journal_dir, force, logger)
```

**Benefits**:
- Reduced from ~2,600 to ~900 lines in sql2wiki.py
- Consistent export logic across entities
- Easy to add new entity types
- Centralized configuration

#### File Change Detection

**Content Hash Strategy**:
```python
def write_if_changed(file_path: Path, content: str, force: bool) -> str:
    """Write file only if content changed."""
    if not force and file_path.exists():
        existing_hash = compute_md5_hash_from_content(
            file_path.read_text()
        )
        new_hash = compute_md5_hash_from_content(content)

        if existing_hash == new_hash:
            return "skipped"

    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")

    return "updated" if file_path.exists() else "created"
```

**Benefits**:
- Minimal file system writes
- Preserves timestamps when unchanged
- Fast incremental updates

---

## Field Ownership Strategy

### Principle: Separate Concerns

**Database Fields** (never in wiki):
- Primary keys (`id`)
- Foreign keys (`entry_id`, `person_id`)
- Timestamps (`created_at`, `updated_at`)
- File metadata (`file_path`, `file_hash`)
- Computed properties (`age_display`, `word_count`)

**Wiki-Editable Fields** (user can modify):
- `notes` - Editorial/manuscript planning notes
- `character_notes` - Character development (manuscript entries)
- `character_description` - Character description (manuscript people)
- `character_arc` - Character arc notes (manuscript people)
- `voice_notes` - Voice notes (manuscript people)
- `appearance_notes` - Appearance notes (manuscript people)

**Database-Only Fields** (computed/derived):
- Relationship counts
- Statistics
- Navigation links
- Breadcrumbs

### Manuscript Field Ownership

**YAML Frontmatter** (minimal):
```yaml
manuscript:
  status: source    # Flag: Is this being used?
  edited: true      # Flag: Has it been edited?
```

**Database** (structural):
- `ManuscriptEntry.status` (enum)
- `ManuscriptEntry.edited` (boolean)
- `ManuscriptEntry.entry_type` (enum)
- `ManuscriptEntry.narrative_arc` (string)

**Manuscript Wiki** (detailed work):
- `ManuscriptEntry.notes` ← adaptation notes
- `ManuscriptEntry.character_notes` ← character notes
- `ManuscriptPerson.character_description` ← description
- `ManuscriptPerson.character_arc` ← arc notes
- `ManuscriptPerson.voice_notes` ← voice
- `ManuscriptPerson.appearance_notes` ← appearance

### Why This Design?

**Journal YAML**:
- Focuses on capturing life events
- Minimal manuscript metadata (just flags)
- Clean, readable, focused

**Database**:
- Central source of truth
- Enforces data integrity
- Efficient queries and relationships

**Manuscript Wiki**:
- Dedicated workspace for adaptation
- Separate from source material
- Rich editing environment for fiction planning

---

## Testing Guide

### Test Structure

```
tests/
├── conftest.py                    # Shared fixtures
├── unit/
│   ├── dataclasses/
│   │   ├── test_md_entry.py      # YAML parsing
│   │   └── test_txt_entry.py
│   └── managers/
│       ├── test_entry_manager.py
│       ├── test_person_manager.py
│       └── test_manuscript_manager.py
└── integration/
    ├── test_yaml_to_db.py        # YAML → SQL
    ├── test_db_to_yaml.py        # SQL → YAML
    ├── test_sql_to_wiki.py       # SQL → Wiki
    └── test_wiki_to_sql.py       # Wiki → SQL
```

### Running Tests

```bash
# All tests
pytest

# Specific path
pytest tests/integration/test_yaml_to_db.py

# With coverage
pytest --cov=dev.pipeline --cov-report=html

# Verbose
pytest -v

# Stop on first failure
pytest -x
```

### Writing Tests

**Example: Test YAML → SQL**:
```python
def test_entry_with_manuscript_metadata(entry_manager, test_db, tmp_path):
    """Test creating entry with manuscript metadata."""
    file_path = tmp_path / "2024-11-01.md"
    file_path.write_text("""---
date: 2024-11-01
manuscript:
  status: source
  edited: true
---
Entry content
""")

    # Parse and import
    md_entry = MdEntry.from_file(file_path)
    db_meta = md_entry.to_database_metadata()
    entry = entry_manager.create(db_meta)

    test_db.commit()
    test_db.refresh(entry)

    # Verify manuscript was created
    assert entry.manuscript is not None
    assert entry.manuscript.status == ManuscriptStatus.SOURCE
    assert entry.manuscript.edited is True
```

**Example: Test SQL → Wiki**:
```python
def test_export_person_to_wiki(test_db, tmp_path):
    """Test exporting person from database to wiki."""
    # Create test person
    person = Person(name="Alice", full_name="Alice Johnson")
    test_db.add(person)
    test_db.commit()

    # Export to wiki
    wiki_person = WikiPerson.from_database(person, tmp_path)
    wiki_content = wiki_person.to_wiki()

    # Verify content
    assert "# Palimpsest — Person" in wiki_content
    assert "Alice" in wiki_content
    assert "Alice Johnson" in wiki_content
```

---

## Troubleshooting

### Common Issues

#### 1. Import Fails with "Entry already exists"

**Cause**: Trying to create entry that already exists in database

**Solution**:
```bash
# Use update instead
python -m dev.pipeline.yaml2sql update journal/md/2024/2024-11-01.md

# Or use batch mode (handles both create/update)
python -m dev.pipeline.yaml2sql batch journal/md/2024/
```

#### 2. Wiki Export Skips All Files

**Cause**: Files haven't changed (content hash matches)

**Solution**:
```bash
# Force regeneration
python -m dev.pipeline.sql2wiki export all --force
```

#### 3. Manuscript Fields Not Appearing in YAML Export

**This is correct behavior!** Manuscript planning fields (`entry_type`, `character_notes`, `narrative_arc`) are intentionally NOT exported to YAML. They only appear in the manuscript wiki.

**If you need them in YAML**: See "Field Ownership Strategy" section - this is a design decision to keep journal YAML minimal.

#### 4. Wiki Import Doesn't Update Other Fields

**This is correct behavior!** Wiki import only updates `notes` fields. All other metadata must be edited in the database or journal YAML.

**Fields that wiki import updates**:
- Main wiki: `notes` only
- Manuscript wiki: `notes`, `character_notes`, `character_description`, etc.

#### 5. Database Shows Wrong Data After Wiki Import

**Cause**: You may have edited structural data in wiki (dates, names, relationships)

**Solution**: Wiki is read-only for structural data. Edit in journal YAML and re-import:
```bash
# Edit journal file's YAML frontmatter
vim journal/md/2024/2024-11-01.md

# Re-import to database
python -m dev.pipeline.yaml2sql update journal/md/2024/2024-11-01.md
```

### Debugging

**Enable verbose logging**:
```bash
# YAML pipeline
python -m dev.pipeline.yaml2sql update file.md --verbose

# Wiki pipeline
python -m dev.pipeline.sql2wiki export people --verbose
```

**Check database state**:
```bash
# SQLite CLI
sqlite3 data/metadata.db

sqlite> SELECT * FROM entries WHERE date = '2024-11-01';
sqlite> SELECT * FROM manuscript_entries;
sqlite> SELECT * FROM people;
```

**Inspect generated files**:
```bash
# View wiki file
cat data/wiki/people/alice.md

# View exported YAML
cat output/2024/2024-11-01.md
```

---

## Quick Reference

### Commands

**YAML → SQL**:
```bash
python -m dev.pipeline.yaml2sql update file.md
python -m dev.pipeline.yaml2sql batch journal/md/2024/
python -m dev.pipeline.yaml2sql sync journal/md/ --delete-missing
```

**SQL → YAML**:
```bash
python -m dev.pipeline.sql2yaml export 2024-11-01 -o output/
python -m dev.pipeline.sql2yaml range 2024-01-01 2024-12-31 -o output/
python -m dev.pipeline.sql2yaml all -o output/
```

**SQL → Wiki**:
```bash
python -m dev.pipeline.sql2wiki export people
python -m dev.pipeline.sql2wiki export entries
python -m dev.pipeline.sql2wiki export all --force
python -m dev.pipeline.manuscript2wiki export all
```

**Wiki → SQL**:
```bash
python -m dev.pipeline.wiki2sql import people
python -m dev.pipeline.wiki2sql import entries
python -m dev.pipeline.wiki2sql import all
python -m dev.pipeline.wiki2sql import manuscript-entries
python -m dev.pipeline.wiki2sql import manuscript-all
```

### Neovim Integration

**Commands**:
- `:PalimpsestExport` - Export all to wiki
- `:PalimpsestExport people` - Export specific entity
- `:PalimpsestImport` - Import wiki edits
- `:PalimpsestManuscriptExport` - Export manuscript wiki
- `:PalimpsestManuscriptImport` - Import manuscript edits
- `:PalimpsestStats` - Open statistics dashboard
- `:PalimpsestAnalysis` - Open analysis report
- `:PalimpsestIndex` - Open wiki homepage

**Keymaps**:
- `<leader>pe` - Export all to wiki
- `<leader>pi` - Import wiki edits
- `<leader>ps` - Statistics dashboard
- `<leader>pa` - Analysis report
- `<leader>ph` - Wiki homepage
- `<leader>pme` - Export manuscript
- `<leader>pmi` - Import manuscript edits

---

## Summary

### Data Flow Rules

1. **Journal YAML** = Primary source for life events
2. **Database** = Central source of truth for all data
3. **Main Wiki** = Read-only view with editable notes
4. **Manuscript Wiki** = Dedicated adaptation workspace

### Edit Where?

| What to Edit | Where | How to Sync |
|--------------|-------|-------------|
| Life events, relationships | Journal YAML | `yaml2sql update` |
| Editorial notes | Main wiki | `wiki2sql import` |
| Manuscript planning | Manuscript wiki | `wiki2sql import manuscript-*` |
| Structural changes | Journal YAML | `yaml2sql update` |

### Best Practices

1. **Journal First**: Always write new entries in journal markdown
2. **Database Truth**: Trust database for relationships and computed data
3. **Wiki Navigation**: Use wiki for browsing and exploration
4. **Manuscript Workspace**: Do all adaptation work in manuscript wiki
5. **Incremental Sync**: Run imports after editing sessions
6. **Regenerate Regularly**: Export wiki weekly to keep it fresh

---

**Documentation Version**: 1.0
**Last Updated**: 2025-11-13
**Status**: Complete and tested ✅
