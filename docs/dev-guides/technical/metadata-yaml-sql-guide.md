# Markdown-YAML ↔ SQL Metadata Guide

Complete guide for using Palimpsest's bidirectional Markdown-YAML and SQL database conversion system.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Core Fields Reference](#core-fields-reference)
4. [Geographic Fields](#geographic-fields)
5. [People and Relationships](#people-and-relationships)
6. [Dates and Timeline](#dates-and-timeline)
7. [Events and Tags](#events-and-tags)
8. [References and Citations](#references-and-citations)
9. [Poems and Creative Work](#poems-and-creative-work)
10. [Manuscript Metadata](#manuscript-metadata)
11. [Complete Examples](#complete-examples)
12. [Edge Cases and Gotchas](#edge-cases-and-gotchas)
13. [Command Reference](#command-reference)

---

## Overview

### What is the YAML↔SQL System?

Palimpsest stores journal entries in **two formats**:

1. **Markdown files** (`.md`) with YAML frontmatter - human-editable, version-controlled
2. **SQL database** - structured, queryable, relationship-aware

The conversion system keeps these in sync:

```
┌──────────────────┐         ┌──────────────────┐
│   Markdown-YAML  │ ◄─────► │   SQL Database   │
│   (md/*.md)      │         │   (palimpsest.db)│
└──────────────────┘         └──────────────────┘
     Human-friendly            Machine-queryable
     Easy editing              Fast searches
     Git-trackable             Relationship tracking
```

### Conversion Workflows

**YAML → SQL (Import):**
```bash
plm sync-db --input md/ --force
```
- Parses YAML frontmatter
- Creates/updates database entries
- Resolves relationships (people, locations, etc.)
- Change detection via file hash (skip unchanged files)

**SQL → YAML (Export):**
```bash
plm export-db --output md/ --force --preserve-body
```
- Exports database entries to Markdown
- Rebuilds YAML frontmatter from database
- Preserves existing body content
- Updates metadata while keeping text

---

## Quick Start

### Minimal Entry

The simplest valid entry:

```yaml
---
date: 2024-01-15
---

Entry content goes here.
```

**Result:** Creates database entry with:
- Date: 2024-01-15
- Word count: auto-calculated
- Reading time: auto-calculated
- Body: "Entry content goes here."

### Basic Entry with Metadata

```yaml
---
date: 2024-01-15
word_count: 342
reading_time: 1.7
epigraph: "The only way out is through."
epigraph_attribution: "Robert Frost"
city: Montreal
tags:
  - personal
  - reflection
---

Today I walked through Parc La Fontaine and thought about...
```

**Result:** Creates entry with location, tags, and epigraph.

---

## Core Fields Reference

### `date` (Required)

**Type:** String (ISO 8601 format: YYYY-MM-DD)
**Required:** ✅ YES
**SQL:** `entries.date` (Primary key)

**Format:**
```yaml
date: 2024-01-15
```

**Rules:**
- Must be valid date string
- Must be unique (one entry per date)
- Format: YYYY-MM-DD

**Examples:**
```yaml
# ✅ Valid
date: 2024-01-15
date: 2023-12-31
date: 2024-02-29  # Leap year

# ❌ Invalid
date: 01/15/2024  # Wrong format
date: 2024-1-15   # Missing zero padding
date: January 15, 2024  # Not ISO format
```

---

### `word_count`

**Type:** Integer
**Required:** No (auto-calculated if missing)
**SQL:** `entries.word_count`

**Format:**
```yaml
word_count: 1543
```

**Rules:**
- Must be integer ≥ 0
- Auto-calculated from body if not provided
- Counts words excluding punctuation

**Examples:**
```yaml
# Manual specification
word_count: 2150

# Omit to auto-calculate
# (No word_count field)
```

---

### `reading_time`

**Type:** Float
**Required:** No (auto-calculated if missing)
**SQL:** `entries.reading_time`

**Format:**
```yaml
reading_time: 7.5
```

**Rules:**
- Minutes to read entry
- Calculated at 260 words per minute
- Stored with 2 decimal precision (.2f)

**Examples:**
```yaml
# Manual specification
reading_time: 8.25

# Auto-calculated from word_count
# reading_time = word_count / 260
```

---

### `epigraph` and `epigraph_attribution`

**Type:** String
**Required:** No
**SQL:** `entries.epigraph`, `entries.epigraph_attribution`

**Format:**
```yaml
epigraph: "To be or not to be, that is the question"
epigraph_attribution: "Hamlet, Act III Scene I"
```

**Rules:**
- Use quotes for multi-line or special characters
- `epigraph_attribution` is optional
- Whitespace trimmed automatically

**Examples:**
```yaml
# With attribution
epigraph: "The unexamined life is not worth living."
epigraph_attribution: "Socrates"

# Without attribution
epigraph: "A quote without source"

# Multi-line (using YAML literal style)
epigraph: |
  Do I dare
  Disturb the universe?
epigraph_attribution: "T.S. Eliot, The Love Song of J. Alfred Prufrock"
```

---

### `notes`

**Type:** String
**Required:** No
**SQL:** `entries.notes`

**Format:**
```yaml
notes: "Important entry about thesis defense. Reference for Chapter 3."
```

**Rules:**
- Editorial notes for your own use
- Visible in wiki exports
- Can be multi-line

**Examples:**
```yaml
# Single line
notes: "Key entry for manuscript"

# Multi-line
notes: |
  This entry contains:
  - Important conversation with advisor
  - Breakthrough insight on research question
  - Reference for dissertation Chapter 3
```

---

## Geographic Fields

### `city` / `cities`

**Type:** String or List
**Required:** No
**SQL:** `cities` table, many-to-many via `entry_cities`

**Format 1 - Single City:**
```yaml
city: Montreal
```

**Format 2 - Multiple Cities:**
```yaml
city: [Montreal, Toronto, Paris]
```

**Rules:**
- Can use singular `city` or plural `cities` (interchangeable)
- Stored in `cities` table with country (if known)
- Creates City records if they don't exist

**Examples:**
```yaml
# Single city
city: Montreal

# Multiple cities (same day, traveled)
city: [Montreal, New York, Boston]

# Alternative format
cities:
  - Montreal
  - Toronto
```

**SQL Result:**
```sql
-- Creates/links to records in cities table:
INSERT INTO cities (city, country) VALUES
  ('Montreal', 'Canada'),
  ('Toronto', 'Canada'),
  ('Paris', 'France');

-- Links to entry via entry_cities:
INSERT INTO entry_cities (entry_id, city_id) VALUES
  (entry.id, montreal.id),
  (entry.id, toronto.id),
  (entry.id, paris.id);
```

---

### `locations`

**Type:** List or Dict
**Required:** No
**SQL:** `locations` table, many-to-many via `entry_locations`

**Format 1 - Flat List (Single City):**
```yaml
city: Montreal
locations:
  - Café Olimpico
  - Mont Royal
  - McGill Library
```

**Format 2 - Nested Dict (Multiple Cities):**
```yaml
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
    - Mont Royal
  Toronto:
    - Robarts Library
    - Trinity College
```

**Rules:**
- Flat list **requires exactly 1 city**
- Nested dict maps cities to their locations
- Locations are stored with their city relationship
- Quoted strings preserve special characters

**Examples:**
```yaml
# Single city with venues
city: Montreal
locations:
  - Café Olimpico
  - "Mom's apartment"
  - Parc La Fontaine

# Multiple cities (nested)
city: [Montreal, Paris]
locations:
  Montreal:
    - Café Olimpico
    - McGill campus
  Paris:
    - Café de Flore
    - Luxembourg Gardens

# Context inheritance (flat list, right-to-left)
city: Montreal
locations:
  - Café Central        # Venue (pending context)
  - Mile End           # Neighborhood (establishes context)
  - "Friend's house"   # Inherits Mile End context
```

**Gotcha:**
```yaml
# ❌ INVALID - Multiple cities with flat list
city: [Montreal, Toronto]
locations:
  - Café Olimpico  # Which city?? → Warning logged, locations skipped

# ✅ FIX - Use nested dict
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Robarts Library
```

**SQL Result:**
```sql
-- Creates Location records linked to City:
INSERT INTO locations (name, city_id) VALUES
  ('Café Olimpico', montreal_id),
  ('Mont Royal', montreal_id);

-- Links to entry:
INSERT INTO entry_locations (entry_id, location_id) VALUES
  (entry.id, cafe_olimpico.id),
  (entry.id, mont_royal.id);
```

---

## People and Relationships

### `people`

**Type:** List (multiple formats supported)
**Required:** No
**SQL:** `people`, `aliases` tables, many-to-many via `entry_people`, `entry_aliases`

### Format 1: Simple Names

```yaml
people:
  - John
  - Jane Smith
  - Ana Sofía
```

**Parsing Rules:**
- Single word → `name` field only
- Multiple words → `full_name` field only
- Hyphens in single words → converted to spaces

**Results:**
```sql
-- "John" (single word)
Person(name='John', full_name=NULL)

-- "Jane Smith" (multiple words)
Person(name=NULL, full_name='Jane Smith')

-- "Ana Sofía" (multiple words)
Person(name=NULL, full_name='Ana Sofía')
```

### Format 2: Hyphenated Names

```yaml
people:
  - Ana-Sofía
  - Jean-Paul
  - Dr-Martinez
```

**Parsing Rules:**
- Hyphens in **single words** → converted to spaces
- Stored with spaces, exported with hyphens (for readability)

**Results:**
```sql
-- Stored as:
Person(name='Ana Sofía')
Person(name='Jean Paul')
Person(name='Dr Martinez')
```

**Export (back to YAML):**
```yaml
people:
  - Ana-Sofía  # Space → hyphen for YAML readability
  - Jean-Paul
  - Dr-Martinez
```

### Format 3: Name with Expansion

```yaml
people:
  - John (John Smith)
  - Bob (Robert Johnson)
  - Sofi (Ana Sofía)
```

**Parsing Rules:**
- Pattern: `name (full_name)`
- Creates person with both fields

**Results:**
```sql
Person(name='John', full_name='John Smith')
Person(name='Bob', full_name='Robert Johnson')
Person(name='Sofi', full_name='Ana Sofía')
```

### Format 4: Alias Notation

```yaml
people:
  - "@Johnny"
  - "@Sofi (Ana-Sofía)"
  - "@J (John Smith)"
```

**Parsing Rules:**
- **Requires `@` prefix** to trigger alias parsing
- Creates `Alias` record linked to `Person`
- Pattern: `@alias (name)` or just `@alias`

**Results:**
```sql
-- "@Johnny"
Person(name='Johnny')
Alias(alias='Johnny', person_id=person.id)

-- "@Sofi (Ana-Sofía)"
Person(name='Ana Sofía')
Alias(alias='Sofi', person_id=person.id)

-- "@J (John Smith)"
Person(full_name='John Smith')
Alias(alias='J', person_id=person.id)
```

**Gotcha:**
```yaml
# ❌ Without @ → Creates Person, NOT Alias
people:
  - "Johnny"  # Creates Person(name='Johnny')

# ✅ With @ → Creates Alias
people:
  - "@Johnny"  # Creates Alias(alias='Johnny')
```

### Format 5: Explicit Dict

```yaml
people:
  - name: John
    full_name: John Smith

  - alias: Johnny
    name: John

  - alias: [Sofi, AS]
    full_name: Ana Sofía
```

**Rules:**
- Explicit dict with `name`, `full_name`, or `alias` keys
- `alias` can be string or list
- For multiple nicknames for the same person, use an alias array (NOT multiple entries)

**Results:**
```sql
Person(name='John', full_name='John Smith')

Person(name='John')
Alias(alias='Johnny', person_id=person.id)

Person(full_name='Ana Sofía')
Alias(alias='Sofi', person_id=person.id)
Alias(alias='AS', person_id=person.id)
```

**Important:**
```yaml
# ✅ CORRECT - One person with multiple nicknames
people:
  - name: Clara
    alias: [Clarabelais, Ari]

# ❌ WRONG - Don't add the same person twice
people:
  - "@Clarabelais (Clara)"
  - "@Ari (Clara)"  # Creates duplicate relationships!
```

### Complete People Examples

```yaml
# Mix of all formats
people:
  - John                      # Simple name
  - Jane Smith               # Full name
  - Ana-Sofía               # Hyphenated → "Ana Sofía"
  - Bob (Robert Johnson)     # Name + expansion
  - "@Johnny (John)"         # Alias
  - "@Sofi (Ana-Sofía)"     # Alias with hyphenated name
  - name: Alice
    full_name: Alice Anderson
    alias: [Al, Ally]
```

**SQL Mapping:**
```sql
-- People table
Person(name='John')
Person(full_name='Jane Smith')
Person(name='Ana Sofía')  -- Hyphen → space
Person(name='Bob', full_name='Robert Johnson')
Person(name='John')  -- For Johnny alias
Person(name='Ana Sofía')  -- For Sofi alias
Person(name='Alice', full_name='Alice Anderson')

-- Aliases table
Alias(alias='Johnny', person_id=john.id)
Alias(alias='Sofi', person_id=maria_jose.id)
Alias(alias='Al', person_id=alice.id)
Alias(alias='Ally', person_id=alice.id)

-- Entry relationships
INSERT INTO entry_people (entry_id, person_id) VALUES
  (entry.id, john.id),
  (entry.id, jane.id),
  (entry.id, maria_jose.id),
  ...;
```

---

## Dates and Timeline

### `dates`

**Type:** List (strings or dicts)
**Required:** No
**SQL:** `dates` table (`mentioned_dates`), many-to-many via `entry_dates`

**Purpose:** Track dates mentioned in entry (past events, future appointments, etc.)

### Format 1: Simple Date Strings

```yaml
dates:
  - "2024-01-15"
  - "2023-12-25"
  - "2024-06-01"
```

**Results:**
```sql
MentionedDate(date='2024-01-15', context=NULL)
MentionedDate(date='2023-12-25', context=NULL)
MentionedDate(date='2024-06-01', context=NULL)
```

### Format 2: Inline Context

```yaml
dates:
  - "2024-01-15 (thesis defense)"
  - "2023-06-01 (birthday party)"
  - "2024-03-20 (dentist appointment)"
```

**Results:**
```sql
MentionedDate(date='2024-01-15', context='thesis defense')
MentionedDate(date='2023-06-01', context='birthday party')
MentionedDate(date='2024-03-20', context='dentist appointment')
```

### Format 3: Context with References

**Special Syntax:**
- `#LocationName` → extracts location reference
- `@PersonName` → extracts person reference
- Hyphens in names → converted to spaces

```yaml
dates:
  - "2024-01-15 (meeting with @John at #Café-Olimpico)"
  - "2023-12-25 (dinner with @Ana-Sofía and @Bob at #Mom's-place)"
  - "2024-06-01 (@Alice's birthday at #Parc-La-Fontaine)"
```

**Parsing:**
```python
# "2024-01-15 (meeting with @John at #Café-Olimpico)"
{
    "date": "2024-01-15",
    "context": "meeting with John at Café Olimpico",  # Cleaned
    "people": ["John"],           # Extracted from @John
    "locations": ["Café Olimpico"]  # Extracted from #Café-Olimpico
}
```

**Results:**
```sql
-- MentionedDate record
MentionedDate(date='2024-01-15', context='meeting with John at Café Olimpico')

-- Relationships
INSERT INTO people_dates (person_id, date_id) VALUES
  (john.id, mentioned_date.id);

INSERT INTO location_dates (location_id, date_id) VALUES
  (cafe_olimpico.id, mentioned_date.id);
```

### Format 4: Explicit Dict

```yaml
dates:
  - date: "2024-01-15"
    context: "thesis defense"
    locations:
      - McGill University
    people:
      - Dr. Smith
      - Dr. Johnson
```

**Results:**
```sql
MentionedDate(date='2024-01-15', context='thesis defense')
-- Linked to McGill University location
-- Linked to Dr. Smith and Dr. Johnson people
```

### Entry Date Auto-Inclusion

**Important:** By default, the entry's own date is automatically added to `mentioned_dates`.

```yaml
---
date: 2024-01-15
# No dates field
---

# Result: MentionedDate(date='2024-01-15') automatically created
```

**To opt out of auto-inclusion:**
```yaml
dates:
  - "~"  # IMPORTANT: Tilde MUST be quoted! Prevents entry date auto-inclusion
  - "2024-01-20 (future appointment)"

# Result: Only 2024-01-20 added, NOT 2024-01-15
```

**Why quotes are required:**
In YAML, an unquoted `~` is interpreted as `null`. The quoted `"~"` is treated as a literal string, which the parser recognizes as the opt-out signal.

**Mixed scenario:**
```yaml
---
date: 2024-01-15
dates:
  - "2024-01-20 (future event)"
  - "2023-12-25 (past event)"
---

# Result: All three dates added:
# - 2024-01-15 (entry date, auto-included)
# - 2024-01-20 (explicit)
# - 2023-12-25 (explicit)
```

### Complete Dates Examples

```yaml
dates:
  - "~"  # Opt out of entry date auto-inclusion
  - "2024-01-20 (dentist)"
  - "2024-01-25 (lunch with @Ana-Sofía at #Café-Central)"
  - date: "2023-12-25"
    context: "Christmas dinner"
    locations:
      - "Mom's house"
    people:
      - Mom
      - Dad
      - Sister
  - "2024-06-01 (@Alice's graduation at #McGill-campus)"
```

---

## Events and Tags

### `events`

**Type:** List of strings
**Required:** No
**SQL:** `events` table, many-to-many via `entry_events`

**Format:**
```yaml
events:
  - thesis-writing
  - montreal-period
  - phd-research
  - teaching-semester
```

**Rules:**
- Use lowercase with hyphens (kebab-case)
- Events represent periods, milestones, or recurring themes
- Creates `Event` records if they don't exist
- Can have `notes` field (editable in wiki)

**Examples:**
```yaml
# Life events
events:
  - phd-studies
  - montreal-period
  - thesis-defense-prep

# Projects
events:
  - manuscript-writing
  - poetry-workshop
  - research-project-x
```

**SQL Result:**
```sql
-- Events table
Event(event='thesis-writing', display_name='Thesis Writing', notes=NULL)
Event(event='montreal-period', display_name='Montreal Period', notes=NULL)

-- Entry relationship
INSERT INTO entry_events (entry_id, event_id) VALUES
  (entry.id, thesis_writing.id),
  (entry.id, montreal_period.id);
```

---

### `tags`

**Type:** List of strings
**Required:** No
**SQL:** `tags` table, many-to-many via `entry_tags`

**Format:**
```yaml
tags:
  - philosophy
  - research
  - personal
  - reflection
```

**Rules:**
- Simple keyword tags (no spaces)
- Use lowercase
- For categorization and filtering
- Creates `Tag` records if they don't exist

**Examples:**
```yaml
# Topic tags
tags:
  - philosophy
  - identity
  - relationships
  - creativity

# Mood tags
tags:
  - anxious
  - hopeful
  - contemplative

# Type tags
tags:
  - dream-record
  - letter-draft
  - poem-notes
```

**SQL Result:**
```sql
-- Tags table
Tag(tag='philosophy')
Tag(tag='research')
Tag(tag='personal')

-- Entry relationship
INSERT INTO entry_tags (entry_id, tag_id) VALUES
  (entry.id, philosophy.id),
  (entry.id, research.id),
  (entry.id, personal.id);
```

---

### `related_entries`

**Type:** List of date strings
**Required:** No
**SQL:** Self-referential many-to-many via `entry_related` table

**Format:**
```yaml
related_entries:
  - "2024-01-10"
  - "2024-01-05"
  - "2023-12-20"
```

**Rules:**
- Links to other entries by date
- Bidirectional relationship
- Dates must be valid entry dates

**Examples:**
```yaml
# Link to previous entries on same topic
related_entries:
  - "2024-01-10"  # First discussion of topic
  - "2024-01-12"  # Follow-up thoughts

# Link to entries in a sequence
related_entries:
  - "2023-12-25"  # Part 1
  - "2024-01-01"  # Part 2
  # This entry is Part 3
```

**SQL Result:**
```sql
-- Self-referential relationship
INSERT INTO entry_related (entry_id, related_entry_id) VALUES
  (current_entry.id, entry_2024_01_10.id),
  (current_entry.id, entry_2024_01_05.id);
```

---

## References and Citations

### `references`

**Type:** List of dicts
**Required:** No
**SQL:** `references`, `reference_sources` tables

**Purpose:** Track quotes, citations, and references to external works.

### Basic Reference Structure

```yaml
references:
  - content: "The quoted text or description"
    mode: direct              # Optional: direct, indirect, paraphrase, visual
    speaker: "Character Name"  # Optional: who said it
    source:                    # Optional but recommended
      title: "Book Title"
      type: book              # Required if source present
      author: "Author Name"   # Optional
```

### Required Fields

**At least ONE of these:**
- `content` - Direct quote text
- `description` - Paraphrased content or summary

**If `source` is present:**
- `title` - Required
- `type` - Required (validated enum)

### Reference Modes

| Mode | Description | Example |
|------|-------------|---------|
| `direct` | Direct quotation (default) | Exact words from source |
| `indirect` | Indirect quotation | "She said that..." |
| `paraphrase` | Paraphrased content | Summary in your words |
| `visual` | Visual reference | Image, artwork, diagram |

### Reference Types (Validated)

Valid `type` values:
- `book`
- `article`
- `film`
- `play`
- `poem`
- `essay`
- `song`
- `podcast`
- `lecture`
- `interview`
- `other`

### Examples

**Example 1: Direct Quote from Book**
```yaml
references:
  - content: "To be or not to be, that is the question"
    mode: direct
    speaker: Hamlet
    source:
      title: "Hamlet"
      type: play
      author: "William Shakespeare"
```

**Example 2: Paraphrase**
```yaml
references:
  - description: "Discussion of existential dread and the absurd"
    mode: paraphrase
    source:
      title: "Being and Nothingness"
      type: book
      author: "Jean-Paul Sartre"
```

**Example 3: Visual Reference**
```yaml
references:
  - description: "Painting of urban isolation"
    mode: visual
    source:
      title: "Nighthawks"
      type: artwork
      author: "Edward Hopper"
```

**Example 4: Minimal (Content Only)**
```yaml
references:
  - content: "Quote from conversation (no formal source)"
```

**Example 5: Multiple References**
```yaml
references:
  # Book quote
  - content: "The unexamined life is not worth living."
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"

  # Film quote
  - content: "You're gonna need a bigger boat."
    speaker: Chief Brody
    source:
      title: "Jaws"
      type: film
      author: "Steven Spielberg"

  # Paraphrase
  - description: "Argument about identity and memory"
    mode: paraphrase
    source:
      title: "Reasons and Persons"
      type: book
      author: "Derek Parfit"
```

### SQL Mapping

```sql
-- reference_sources table (deduplicated by title+author)
ReferenceSource(
  title='Hamlet',
  type='play',
  author='William Shakespeare'
)

-- references table (one per entry-reference pair)
Reference(
  entry_id=entry.id,
  source_id=source.id,
  content='To be or not to be, that is the question',
  description=NULL,
  mode='direct',
  speaker='Hamlet'
)
```

### Gotchas

```yaml
# ❌ INVALID - Missing both content and description
references:
  - source:
      title: "Book"
      type: book
# Error: At least one of content or description required

# ❌ INVALID - Source missing type
references:
  - content: "Quote"
    source:
      title: "Book"
      author: "Author"
# Error: type required when source present

# ✅ VALID - Content without source
references:
  - content: "Overheard quote without source"

# ✅ VALID - Description without source
references:
  - description: "Interesting idea from conversation"
```

---

## Poems and Creative Work

### `poems`

**Type:** List of dicts
**Required:** No
**SQL:** `poems`, `poem_versions` tables

**Purpose:** Track poems and their revisions across entries.

### Basic Poem Structure

```yaml
poems:
  - title: "Poem Title"
    content: |
      First line of poem
      Second line
      Third line
    revision_date: "2024-01-15"  # Optional, defaults to entry date
    notes: "Editorial notes"     # Optional
```

### Required Fields

- `title` - Required
- `content` - Required (can be multi-line)

### Optional Fields

- `revision_date` - Defaults to entry date if omitted
- `notes` - Editorial notes about this version

### Examples

**Example 1: Simple Poem**
```yaml
poems:
  - title: "Winter Morning"
    content: |
      Frost on the window
      Steam rising from my cup
      A silent world awaits
```

**Example 2: Poem with Revision Date**
```yaml
poems:
  - title: "Ode to Montreal"
    content: |
      Streets of cobblestone and memory
      Where every corner holds a story
      Of lives intertwined, of winters shared
    revision_date: "2024-01-20"
    notes: "Second draft, revised opening"
```

**Example 3: Multiple Poems**
```yaml
poems:
  - title: "Morning Thoughts"
    content: "Single line haiku style"

  - title: "Evening Reflection"
    content: |
      Longer poem with
      Multiple lines and
      Structured stanzas

      Second stanza here
      With emotional depth
    notes: "First draft, needs work"
```

**Example 4: Poem Revision Tracking**

**Entry 1 (2024-01-10):**
```yaml
poems:
  - title: "City Symphony"
    content: |
      Draft version here
      Rough ideas
    notes: "Initial draft"
```

**Entry 2 (2024-01-15):**
```yaml
poems:
  - title: "City Symphony"
    content: |
      Revised version here
      Better flow
      New ending
    notes: "Second revision, improved rhythm"
```

**Entry 3 (2024-01-20):**
```yaml
poems:
  - title: "City Symphony"
    content: |
      Final version here
      Polished lines
      Complete work
    revision_date: "2024-01-20"
    notes: "Final version, ready for publication"
```

### Version Tracking

The system tracks poem versions across entries:

**SQL Result:**
```sql
-- poems table (one record per unique title)
Poem(title='City Symphony')

-- poem_versions table (multiple versions)
PoemVersion(
  poem_id=city_symphony.id,
  entry_id=entry_2024_01_10.id,
  content='Draft version...',
  revision_date='2024-01-10',
  notes='Initial draft',
  version_hash='abc123...'  -- Auto-generated
)

PoemVersion(
  poem_id=city_symphony.id,
  entry_id=entry_2024_01_15.id,
  content='Revised version...',
  revision_date='2024-01-15',
  notes='Second revision...',
  version_hash='def456...'
)

PoemVersion(
  poem_id=city_symphony.id,
  entry_id=entry_2024_01_20.id,
  content='Final version...',
  revision_date='2024-01-20',
  notes='Final version...',
  version_hash='ghi789...'
)
```

**Wiki Export:** Automatically compiles version history by poem title, showing all revisions chronologically.

### Gotchas

```yaml
# ✅ Valid - revision_date defaults to entry date
---
date: 2024-01-15
poems:
  - title: "Poem"
    content: "Content"
# Result: revision_date = 2024-01-15

# ✅ Valid - explicit revision_date
poems:
  - title: "Poem"
    content: "Content"
    revision_date: "2024-01-20"  # Different from entry date

# ❌ Invalid - missing title
poems:
  - content: "Content without title"

# ❌ Invalid - missing content
poems:
  - title: "Title without content"
```

---

## Manuscript Metadata

### `manuscript`

**Type:** Dict
**Required:** No
**SQL:** `manuscript_entries`, `manuscript_themes` tables

**Purpose:** Editorial metadata for manuscript development.

### Structure

```yaml
manuscript:
  status: draft         # Required if manuscript present
  edited: true          # Optional boolean
  themes:               # Optional list
    - identity
    - loss
    - transformation
  notes: "Editorial notes"  # Optional
```

### Status Values (Enum)

| Status | Description |
|--------|-------------|
| `source` | Raw source material |
| `draft` | First draft for manuscript |
| `reviewed` | Under review |
| `included` | Included in manuscript |
| `excluded` | Excluded from manuscript |
| `final` | Final version |

### Examples

**Example 1: Basic Manuscript Tagging**
```yaml
manuscript:
  status: draft
  edited: false
```

**Example 2: With Themes**
```yaml
manuscript:
  status: reviewed
  edited: true
  themes:
    - identity-crisis
    - family-relationships
    - coming-of-age
```

**Example 3: With Editorial Notes**
```yaml
manuscript:
  status: included
  edited: true
  themes:
    - urban-isolation
    - immigrant-experience
  notes: |
    Key scene for Chapter 3.
    Captures protagonist's turning point.
    Consider expanding dialogue with Marie.
```

**Example 4: Excluded Entry**
```yaml
manuscript:
  status: excluded
  notes: "Too personal, doesn't fit narrative arc"
```

### SQL Mapping

```sql
-- manuscript_entries table
ManuscriptEntry(
  entry_id=entry.id,
  status='included',
  edited=true,
  notes='Key scene for Chapter 3...'
)

-- manuscript_themes table + association
ManuscriptTheme(theme='identity-crisis')
ManuscriptTheme(theme='family-relationships')

INSERT INTO manuscript_entry_themes (entry_id, theme_id) VALUES
  (entry.id, identity_crisis.id),
  (entry.id, family_relationships.id);
```

### Workflow Example

**Stage 1: Source Material**
```yaml
---
date: 2024-01-10
manuscript:
  status: source
---
```

**Stage 2: First Draft**
```yaml
---
date: 2024-01-10
manuscript:
  status: draft
  edited: true
  themes:
    - identity
  notes: "Revised for manuscript, expanded middle section"
---
```

**Stage 3: Review**
```yaml
---
date: 2024-01-10
manuscript:
  status: reviewed
  edited: true
  themes:
    - identity
    - transformation
  notes: |
    Beta reader feedback:
    - Strengthen emotional arc
    - Add more sensory details
---
```

**Stage 4: Final**
```yaml
---
date: 2024-01-10
manuscript:
  status: final
  edited: true
  themes:
    - identity
    - transformation
  notes: "Final version, incorporated all feedback"
---
```

---

## Complete Examples

### Minimal Entry
```yaml
---
date: 2024-01-15
---

Today was a quiet day. I spent most of it reading.
```

### Basic Entry with Core Metadata
```yaml
---
date: 2024-01-15
word_count: 342
reading_time: 1.7
epigraph: "The only way out is through."
epigraph_attribution: "Robert Frost"
city: Montreal
tags:
  - personal
  - reflection
---

Today I walked through Parc La Fontaine and reflected on...
```

### Entry with People and Locations
```yaml
---
date: 2024-01-15
city: Montreal
locations:
  - Café Olimpico
  - Mont Royal
people:
  - "@Sofi (Ana-Sofía)"
  - John
  - Alice (Alice Anderson)
tags:
  - social
  - friends
events:
  - montreal-period
---

Met with Sofi at Café Olimpico this morning...
```

### Entry with Timeline and References
```yaml
---
date: 2024-01-15
city: Montreal
people:
  - Dr. Smith
dates:
  - "2024-01-20 (thesis defense)"
  - "2024-01-10 (preliminary meeting with @Dr-Smith)"
references:
  - content: "The unexamined life is not worth living."
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"
tags:
  - philosophy
  - thesis
events:
  - phd-research
---

Preparing for my thesis defense next week...
```

### Entry with Poems
```yaml
---
date: 2024-01-15
city: Montreal
tags:
  - poetry
  - creative
poems:
  - title: "Winter in Montreal"
    content: |
      Snow falls on cobblestones
      Each flake a memory
      Of winters past and yet to come
    notes: "First draft, needs revision"
---

Wrote a new poem today while watching the snow fall...
```

### Comprehensive Entry (All Fields)
```yaml
---
date: 2024-01-15
word_count: 1250
reading_time: 6.2
epigraph: "In the middle of the journey of our life I found myself within a dark woods where the straight way was lost."
epigraph_attribution: "Dante, Inferno, Canto I"
notes: "Important entry for manuscript Chapter 3"

city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
    - Mont Royal
  Toronto:
    - Robarts Library

people:
  - "@Sofi (Ana-Sofía)"
  - John (John Smith)
  - Alice
  - Dr. Martinez

dates:
  - "2024-01-20 (thesis defense at #McGill-campus)"
  - "2024-01-10 (coffee with @Sofi at #Café-Olimpico)"
  - "2023-12-25 (Christmas dinner)"

events:
  - phd-research
  - thesis-writing
  - montreal-period

tags:
  - philosophy
  - identity
  - research
  - personal

related_entries:
  - "2024-01-10"
  - "2024-01-12"

references:
  - content: "The unexamined life is not worth living."
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"

  - description: "Discussion of personal identity and memory"
    mode: paraphrase
    source:
      title: "Reasons and Persons"
      type: book
      author: "Derek Parfit"

poems:
  - title: "Montreal Winter"
    content: |
      Streets of memory and snow
      Where every corner holds
      A story yet untold
    revision_date: "2024-01-15"
    notes: "Second draft, improved flow"

manuscript:
  status: included
  edited: true
  themes:
    - identity-crisis
    - academic-life
    - urban-isolation
  notes: |
    Key entry for Chapter 3: The Turning Point
    Captures protagonist's moment of clarity
---

Today marked a turning point in my research...
```

---

## Edge Cases and Gotchas

### 1. People Name Parsing

**Gotcha:** Hyphens in single-word names become spaces

```yaml
# INPUT
people:
  - Ana-Sofía

# DATABASE
Person(name='Ana Sofía')  # Hyphen → space

# EXPORT (back to YAML)
people:
  - Ana-Sofía  # Space → hyphen for readability
```

**Gotcha:** Parentheses trigger name/full_name split

```yaml
# INPUT
people:
  - John (John Smith)

# DATABASE
Person(name='John', full_name='John Smith')

# NOT this:
Person(full_name='John (John Smith)')  # ❌ Wrong
```

**Gotcha:** `@` prefix required for aliases

```yaml
# Creates Alias:
people:
  - "@Johnny"  # ✅ Alias(alias='Johnny')

# Creates Person:
people:
  - "Johnny"  # ❌ Person(name='Johnny'), NOT alias
```

---

### 2. Locations Require City Context

**Gotcha:** Flat list requires exactly 1 city

```yaml
# ✅ VALID
city: Montreal
locations:
  - Café Olimpico

# ❌ INVALID - Multiple cities with flat list
city: [Montreal, Toronto]
locations:
  - Café Olimpico  # Which city??

# Warning logged: "Locations require single city for flat list"
# Result: Locations skipped
```

**Fix:** Use nested dict

```yaml
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Robarts Library
```

---

### 3. Dates Field Auto-Inclusion

**Gotcha:** Entry date automatically added to `mentioned_dates`

```yaml
# Entry date: 2024-01-15
# No dates field

# Result: MentionedDate(date='2024-01-15') auto-created
```

**Gotcha:** Explicit dates field still includes entry date

```yaml
# Entry date: 2024-01-15
dates:
  - "2024-01-20"

# Result: BOTH dates added:
# - 2024-01-15 (auto)
# - 2024-01-20 (explicit)
```

**To opt out (tilde MUST be quoted!):**

```yaml
dates:
  - "~"  # MUST use quotes! Prevent auto-inclusion
  - "2024-01-20"

# Result: Only 2024-01-20 added
```

**Why quotes matter:**
```yaml
# ❌ WRONG - Unquoted tilde is null
dates:
  - ~  # Interpreted as null, not opt-out signal

# ✅ CORRECT - Quoted tilde is literal string
dates:
  - "~"  # Recognized as opt-out signal
```

---

### 4. References Need Content or Description

**Gotcha:** Must have at least one

```yaml
# ❌ INVALID
references:
  - source:
      title: "Book"
      type: book

# ✅ VALID
references:
  - content: "Quote text"
    source:
      title: "Book"
      type: book

# ✅ ALSO VALID
references:
  - description: "Summary"
    mode: paraphrase
    source:
      title: "Book"
      type: book
```

---

### 5. Poem Revision Date Default

**Gotcha:** Missing `revision_date` defaults to entry date

```yaml
# Entry date: 2024-01-15
poems:
  - title: "Poem"
    content: "..."
    # No revision_date

# Result: PoemVersion(revision_date='2024-01-15')
```

**Explicit revision date:**

```yaml
poems:
  - title: "Poem"
    content: "..."
    revision_date: "2024-01-20"  # Override default
```

---

### 6. Context References in Dates

**Gotcha:** `#` and `@` extract structured data

```yaml
dates:
  - "2024-01-15 (meeting with @John at #Café-Olimpico)"

# Parsed to:
# {
#   "date": "2024-01-15",
#   "context": "meeting with John at Café Olimpico",
#   "people": ["John"],
#   "locations": ["Café Olimpico"]
# }

# Creates relationships:
# - MentionedDate ↔ Person(John)
# - MentionedDate ↔ Location(Café Olimpico)
```

---

### 7. YAML String Quoting

**Gotcha:** Special characters need quotes

```yaml
# ✅ Use quotes for special chars
locations:
  - "Mom's apartment"  # Apostrophe
  - "Café #5"          # Hash symbol
  - "Place: The Beginning"  # Colon

dates:
  - "~"  # Tilde MUST be quoted (YAML reserved character)

# ❌ Without quotes (parsing error or unexpected behavior)
locations:
  - Mom's apartment  # Syntax error

dates:
  - ~  # Interpreted as null, not literal tilde!
```

**Gotcha:** Multi-line strings

```yaml
# Use literal style (|) for multi-line
epigraph: |
  First line
  Second line
  Third line

# Use folded style (>) for long single line
notes: >
  This is a very long note that spans
  multiple lines but will be folded
  into a single line.
```

---

### 8. File Hash Change Detection

**Gotcha:** Unchanged files skipped by default

```bash
# First import
plm sync-db --input md/

# Modify entry metadata in database
metadb update-entry 2024-01-15 --word-count 500

# Try to re-import (file unchanged)
plm sync-db --input md/
# Result: File skipped (hash unchanged)
```

**Fix:** Use `--force` flag

```bash
plm sync-db --input md/ --force
# Result: All files processed, database updated from files
```

**Gotcha:** Export overwrites by default

```bash
# Export creates file
plm export-db --output md/

# Export again (overwrites)
plm export-db --output md/
# Result: File overwritten with database values
```

**To preserve manual edits:**

```bash
plm export-db --output md/ --preserve-body
# Result: Metadata updated, body content preserved
```

---

## Command Reference

### Import: YAML → SQL

**Basic import:**
```bash
plm sync-db --input md/
```

**Force update (ignore file hash):**
```bash
plm sync-db --input md/ --force
```

**Import specific file:**
```bash
plm sync-db --file md/2024/2024-01-15.md
```

**Import with verbose logging:**
```bash
plm sync-db --input md/ --verbose
```

---

### Export: SQL → YAML

**Basic export:**
```bash
plm export-db --output md/
```

**Force overwrite existing files:**
```bash
plm export-db --output md/ --force
```

**Preserve existing body content:**
```bash
plm export-db --output md/ --preserve-body
```

**Export specific date:**
```bash
plm export-db --date 2024-01-15 --output md/
```

**Export date range:**
```bash
plm export-db --start 2024-01-01 --end 2024-01-31 --output md/
```

---

### Typical Workflows

**Workflow 1: Initial Import**
```bash
# Import all entries
plm sync-db --input md/ --verbose

# Verify in database
metadb stats
```

**Workflow 2: Daily Entry Addition**
```bash
# Create new entry
echo "---
date: 2024-01-15
city: Montreal
tags: [personal]
---

Entry content..." > md/2024/2024-01-15.md

# Import new entry
plm sync-db --file md/2024/2024-01-15.md
```

**Workflow 3: Database Edit → YAML Sync**
```bash
# Edit in database (via web UI or direct query)
metadb update-entry 2024-01-15 --add-tag philosophy

# Export updated metadata back to YAML
plm export-db --date 2024-01-15 --output md/ --force --preserve-body
```

**Workflow 4: Bulk Re-import After Manual Edits**
```bash
# Edit YAML files manually
vim md/2024/2024-01-15.md

# Re-import all (force update)
plm sync-db --input md/ --force
```

**Workflow 5: Backup and Restore**
```bash
# Export all entries from database
plm export-db --output md-backup/ --force

# Restore from backup
plm sync-db --input md-backup/ --force
```

---

## Appendix: SQL Schema Reference

### Core Tables

**entries**
- `id` (PK)
- `date` (UNIQUE, ISO 8601)
- `file_path`
- `file_hash` (MD5)
- `word_count`
- `reading_time`
- `epigraph`
- `epigraph_attribution`
- `notes`
- `created_at`
- `updated_at`

**cities**
- `id` (PK)
- `city`
- `country`

**locations**
- `id` (PK)
- `name`
- `city_id` (FK → cities)

**people**
- `id` (PK)
- `name`
- `full_name`
- `relation_type` (enum)
- `name_fellow` (boolean)

**aliases**
- `id` (PK)
- `alias`
- `person_id` (FK → people)

**dates** (mentioned_dates)
- `id` (PK)
- `date`
- `context`

**events**
- `id` (PK)
- `event`
- `display_name`
- `notes`

**tags**
- `id` (PK)
- `tag`

**reference_sources**
- `id` (PK)
- `title`
- `type` (enum)
- `author`

**references**
- `id` (PK)
- `entry_id` (FK → entries)
- `source_id` (FK → reference_sources)
- `content`
- `description`
- `mode` (enum)
- `speaker`

**poems**
- `id` (PK)
- `title`

**poem_versions**
- `id` (PK)
- `poem_id` (FK → poems)
- `entry_id` (FK → entries)
- `content`
- `revision_date`
- `notes`
- `version_hash`

**manuscript_entries**
- `id` (PK)
- `entry_id` (FK → entries)
- `status` (enum)
- `edited` (boolean)
- `notes`

**manuscript_themes**
- `id` (PK)
- `theme`

### Association Tables (Many-to-Many)

- `entry_cities` (entries ↔ cities)
- `entry_locations` (entries ↔ locations)
- `entry_people` (entries ↔ people)
- `entry_aliases` (entries ↔ aliases)
- `entry_dates` (entries ↔ dates)
- `entry_events` (entries ↔ events)
- `entry_tags` (entries ↔ tags)
- `entry_related` (entries ↔ entries, self-referential)
- `people_dates` (people ↔ dates)
- `location_dates` (locations ↔ dates)
- `manuscript_entry_themes` (manuscript_entries ↔ manuscript_themes)

---

## Support and Further Reading

- **SQL↔Wiki Guide:** See `METADATA_GUIDE_SQL_WIKI.md` for wiki export/import
- **Full Examples:** See `examples/` directory for complete entry templates
- **Source Code:** Conversion logic in `dev/pipeline/` and `dev/dataclasses/`
- **Issue Tracker:** Report bugs and edge cases on GitHub

---

*Last Updated: 2024-01-15*
