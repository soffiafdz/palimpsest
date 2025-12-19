# Metadata Field Reference

Complete reference for Palimpsest's YAML frontmatter metadata fields. This guide uses progressive disclosure - start with Quick Start if you're new, dive deeper as needed.

---

## Navigation

- [Quick Start](#quick-start) - Templates and common patterns (5 min)
- [Core Fields](#core-fields-reference) - Essential fields explained (20 min)
- [Advanced Fields](#advanced-fields) - Geographic, people, dates, references, poems, manuscript (30 min)
- [Field Type Reference](#field-type-reference) - Complete lookup table
- [Common Patterns](#common-patterns) - Name parsing, locations, dates, references
- [Common Gotchas](#common-gotchas) - **Critical debugging resource**
- [Enum Values](#enum-values-reference) - Valid values for type fields
- [SQL Schema](#sql-schema-quick-reference) - Database structure

**Related Documentation:**
- [Metadata Examples](metadata-examples.md) - Complex entry templates
- [Wiki Field Reference](wiki-fields.md) - SQL↔Wiki system
- [Command Reference](commands.md) - CLI commands

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

### Basic Entry

```yaml
---
date: 2024-01-15
city: Montreal
tags:
  - personal
  - reflection
---

Entry content here.
```

### Entry with People and Places

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
tags:
  - social
events:
  - montreal-period
---

Entry content here.
```

### Entry with References

```yaml
---
date: 2024-01-15
tags:
  - philosophy
  - research
references:
  - content: "The unexamined life is not worth living."
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"
---

Entry content here.
```

### Comprehensive Entry

See [Metadata Examples](metadata-examples.md) for full examples with all fields.

---

## Core Fields Reference

### `date` (Required)

**Type:** String (ISO 8601 format: YYYY-MM-DD)
**Required:** ✅ YES
**SQL:** `entries.date` (Primary key)
**Auto-calculated:** No

Every entry must have exactly one date. This is the entry's unique identifier.

**Format:**
```yaml
date: 2024-01-15
```

**Rules:**
- Must be valid date string (YYYY-MM-DD)
- Must be unique (one entry per date)
- Must use zero-padding (2024-01-05, not 2024-1-5)

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
**Auto-calculated:** ✅ YES

Word count of entry body content.

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

# Omit to auto-calculate (recommended)
# (No word_count field)
```

---

### `reading_time`

**Type:** Float
**Required:** No (auto-calculated if missing)
**SQL:** `entries.reading_time`
**Auto-calculated:** ✅ YES

Minutes to read entry (calculated at 260 words/min).

**Format:**
```yaml
reading_time: 7.5
```

**Rules:**
- Minutes to read entry
- Calculated at 260 words per minute
- Stored with 2 decimal precision

**Examples:**
```yaml
# Manual specification
reading_time: 8.25

# Auto-calculated from word_count (recommended)
# reading_time = word_count / 260
```

---

### `epigraph` and `epigraph_attribution`

**Type:** String
**Required:** No
**SQL:** `entries.epigraph`, `entries.epigraph_attribution`
**Auto-calculated:** No

Opening quote for your entry.

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
**Auto-calculated:** No

Editorial notes for your own use.

**Format:**
```yaml
notes: "Important entry about thesis defense. Reference for Chapter 3."
```

**Rules:**
- Editorial notes for your own use
- Visible in wiki exports
- Can be multi-line
- Editable in wiki, syncs back to database

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

## Advanced Fields

### Geographic Fields

#### `city` / `cities`

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

---

#### `locations`

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

# Multiple cities (nested - REQUIRED)
city: [Montreal, Paris]
locations:
  Montreal:
    - Café Olimpico
    - McGill campus
  Paris:
    - Café de Flore
    - Luxembourg Gardens
```

**Gotcha:**
```yaml
# ❌ INVALID - Multiple cities with flat list
city: [Montreal, Toronto]
locations:
  - Café Olimpico  # Which city?? → Locations skipped

# ✅ FIX - Use nested dict
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Robarts Library
```

---

### People and Relationships

#### `people`

**Type:** List (multiple formats supported)
**Required:** No
**SQL:** `people`, `aliases` tables, many-to-many via `entry_people`, `entry_aliases`

**Format 1: Simple Names**

```yaml
people:
  - John
  - Jane Smith
  - Ana Sofía
```

**Parsing Rules:**
- Single word → `name` field only
- Multiple words (space-separated) → First word becomes `name`, full string becomes `full_name`
- Hyphens in single words → converted to spaces

**Results:**
```sql
-- "John" (single word)
Person(name='John', full_name=NULL)

-- "Jane Smith" (two words)
Person(name='Jane', full_name='Jane Smith')

-- "Ana Sofía" (two words)
Person(name='Ana', full_name='Ana Sofía')
```

**CRITICAL: Space vs Hyphen Distinction**
```yaml
# ⚠️ WARNING: These create THREE DIFFERENT people!
people:
  - María              # Person(name='María', full_name=NULL)
  - María-José         # Person(name='María José', full_name=NULL)
  - María José         # Person(name='María', full_name='María José')
```

**Solution - Use one canonical form:**
```yaml
# Option 1: Compound name with alias array
people:
  - name: María José
    alias: [María, Majo]

# Option 2: Alias notation
people:
  - "@María (María-José)"  # "María" is alias for "María José"
```

**Format 2: Hyphenated Names**

```yaml
people:
  - Ana-Sofía
  - Jean-Paul
  - Dr-Martinez
```

Hyphens in **single words** → converted to spaces, stored as "Ana Sofía", "Jean Paul", etc.

**Format 3: Name with Expansion**

```yaml
people:
  - John (John Smith)
  - Bob (Robert Johnson)
  - Sofi (Ana Sofía)
```

Creates person with both `name` and `full_name` fields.

**Format 4: Alias Notation**

```yaml
people:
  - "@Johnny"
  - "@Sofi (Ana-Sofía)"
  - "@J (John Smith)"
```

**Requires `@` prefix** to create alias records.

**Gotcha:**
```yaml
# ❌ Without @ → Creates Person, NOT Alias
people:
  - "Johnny"  # Person(name='Johnny')

# ✅ With @ → Creates Alias
people:
  - "@Johnny"  # Alias(alias='Johnny')
```

**Format 5: Explicit Dict (Multiple Nicknames)**

```yaml
people:
  - name: Clara
    alias: [Clarabelais, Ari]  # Multiple nicknames for same person
```

**Important:**
```yaml
# ✅ CORRECT - One person with multiple nicknames
people:
  - name: Clara
    alias: [Clarabelais, Ari]

# ❌ WRONG - Creates duplicate relationships
people:
  - "@Clarabelais (Clara)"
  - "@Ari (Clara)"  # Don't do this!
```

---

### Dates and Timeline

#### `dates`

**Type:** List (strings or dicts)
**Required:** No
**SQL:** `dates` table (`mentioned_dates`), many-to-many via `entry_dates`

Track dates mentioned in entry (past events, future appointments, etc.).

**Format 1: Simple Date Strings**

```yaml
dates:
  - "2024-01-15"
  - "2023-12-25"
  - "2024-06-01"
```

**Format 2: Inline Context**

```yaml
dates:
  - "2024-01-15 (thesis defense)"
  - "2023-06-01 (birthday party)"
  - "2024-03-20 (dentist appointment)"
```

**Format 3: Context with References**

Special syntax extracts people and locations:
- `@PersonName` → extracts person reference
- `#LocationName` → extracts location reference

```yaml
dates:
  - "2024-01-15 (meeting with @John at #Café-Olimpico)"
  - "2023-12-25 (dinner with @Ana-Sofía at #Mom's-place)"
```

Parsed to:
```python
{
    "date": "2024-01-15",
    "context": "meeting with John at Café Olimpico",
    "people": ["John"],
    "locations": ["Café Olimpico"]
}
```

Creates `people_dates` and `location_dates` relationships.

**Format 4: Explicit Dict**

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

**Entry Date Auto-Inclusion**

By default, the entry's own date is automatically added to `mentioned_dates`.

```yaml
---
date: 2024-01-15
# No dates field
---

# Result: MentionedDate(date='2024-01-15') automatically created
```

**To opt out:**
```yaml
dates:
  - "~"  # MUST be quoted! Prevents entry date auto-inclusion
  - "2024-01-20"

# Result: Only 2024-01-20 added, NOT 2024-01-15
```

**Why quotes are required:** Unquoted `~` is interpreted as `null` in YAML.

**CRITICAL: Date Associations Behavior**

#### Scenario A: NO `dates:` field
```yaml
---
date: 2024-01-15
people: [María, John]
locations: [Café X]
---
```
**Result:**
- Entry date (2024-01-15) auto-added WITH people/locations
- Creates `people_dates` and `location_dates` associations

#### Scenario B: HAS `dates:` field
```yaml
---
date: 2024-01-15
people: [María, John]
locations: [Café X]
dates:
  - "2024-01-20"
---
```
**Result:**
- Both dates added to `mentioned_dates`
- People/locations NOT associated with dates
- Only linked to entry via `entry_people`/`entry_locations`

#### Scenario C: Explicit date associations
```yaml
---
date: 2024-01-15
people: [María, John]
dates:
  - date: "2024-01-15"
    people: [María]
    locations: [Café X]
  - date: "2024-01-20"
    people: [John]
---
```
**Result:**
- 2024-01-15: María and Café X associated
- 2024-01-20: John associated
- Entry has both as general mentions

---

### Events and Tags

#### `events`

**Type:** List of strings
**Required:** No
**SQL:** `events` table, many-to-many via `entry_events`

Life events, periods, or recurring themes.

**Format:**
```yaml
events:
  - thesis-writing
  - montreal-period
  - phd-research
```

**Rules:**
- Use lowercase with hyphens (kebab-case)
- Events represent periods, milestones, or themes
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
```

---

#### `tags`

**Type:** List of strings
**Required:** No
**SQL:** `tags` table, many-to-many via `entry_tags`

Simple keyword tags for categorization.

**Format:**
```yaml
tags:
  - philosophy
  - research
  - personal
```

**Rules:**
- Simple keyword tags (no spaces)
- Use lowercase
- For categorization and filtering

**Examples:**
```yaml
# Topic tags
tags:
  - philosophy
  - identity
  - relationships

# Mood tags
tags:
  - anxious
  - hopeful

# Type tags
tags:
  - dream-record
  - poem-notes
```

---

#### `related_entries`

**Type:** List of date strings
**Required:** No
**SQL:** Self-referential many-to-many via `entry_related` table

Links to other entries by date.

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

---

### References and Citations

#### `references`

**Type:** List of dicts
**Required:** No
**SQL:** `references`, `reference_sources` tables

Track quotes, citations, and references to external works.

**Basic Structure:**
```yaml
references:
  - content: "The quoted text"         # Optional (need content OR description)
    description: "My interpretation"    # Optional (need content OR description)
    mode: direct                        # Optional: direct, indirect, paraphrase, visual
    speaker: "Character Name"           # Optional
    source:                             # Optional but recommended
      title: "Book Title"
      type: book                        # Required if source present
      author: "Author Name"             # Optional
      url: "https://example.com"        # Optional
```

**Required Fields:**
- At least ONE of: `content` or `description` (can have BOTH!)
- If `source` present: `title` and `type` required

**Reference Modes:**
- `direct` - Direct quotation (default)
- `indirect` - Indirect quotation
- `paraphrase` - Paraphrased content
- `visual` - Visual reference

**Examples:**

**Direct Quote:**
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

**Paraphrase:**
```yaml
references:
  - description: "Discussion of existential dread and the absurd"
    mode: paraphrase
    source:
      title: "Being and Nothingness"
      type: book
      author: "Jean-Paul Sartre"
```

**Both Content AND Description:**
```yaml
references:
  - content: "The unexamined life is not worth living"
    description: "Socrates argues self-reflection is essential"
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"
```

**Website Reference:**
```yaml
references:
  - content: "Quote from the blog"
    source:
      title: "Article Title"
      type: website
      author: "Author Name"
      url: "https://example.com/article"
```

**Gotcha:**
```yaml
# ❌ INVALID - Missing both content and description
references:
  - source:
      title: "Book"
      type: book

# ✅ VALID - Has content
references:
  - content: "Quote"
    source:
      title: "Book"
      type: book
```

---

### Poems and Creative Work

#### `poems`

**Type:** List of dicts
**Required:** No
**SQL:** `poems`, `poem_versions` tables

Track poems and their revisions across entries.

**Basic Structure:**
```yaml
poems:
  - title: "Poem Title"
    content: |
      First line
      Second line
      Third line
    revision_date: "2024-01-15"  # Optional, defaults to entry date
    notes: "Editorial notes"     # Optional
```

**Required Fields:**
- `title` - Required
- `content` - Required (can be multi-line)

**Examples:**

**Simple Poem:**
```yaml
poems:
  - title: "Winter Morning"
    content: |
      Frost on the window
      Steam rising from my cup
      A silent world awaits
```

**With Revision Date:**
```yaml
poems:
  - title: "Ode to Montreal"
    content: |
      Streets of cobblestone
      Where every corner holds a story
    revision_date: "2024-01-20"
    notes: "Second draft, revised opening"
```

**Gotcha:**
```yaml
# Entry date: 2024-01-15
poems:
  - title: "Poem"
    content: "..."
    # revision_date defaults to 2024-01-15
```

The system tracks poem versions across entries, creating version history.

---

### Manuscript Metadata

#### `manuscript`

**Type:** Dict
**Required:** No
**SQL:** `manuscript_entries`, `manuscript_themes` tables

Editorial metadata for manuscript development.

**Structure:**
```yaml
manuscript:
  status: draft         # Required if manuscript present
  edited: true          # Optional boolean
  themes:               # Optional list
    - identity
    - loss
  notes: "Editorial notes"
```

**Status Values (Enum):**
- `source` - Raw source material
- `draft` - First draft
- `reviewed` - Under review
- `included` - Included in manuscript
- `excluded` - Excluded from manuscript
- `final` - Final version

**Examples:**

**Basic:**
```yaml
manuscript:
  status: draft
  edited: false
```

**With Themes:**
```yaml
manuscript:
  status: included
  edited: true
  themes:
    - identity-crisis
    - urban-isolation
  notes: "Key scene for Chapter 3"
```

---

## Common Patterns

### Name Parsing

```yaml
# Simple names
people:
  - John              # → Person(name='John')
  - Jane Smith        # → Person(name='Jane', full_name='Jane Smith')

# Hyphenated names (hyphen → space)
people:
  - Ana-Sofía        # → Person(name='Ana Sofía')
  - Jean-Paul        # → Person(name='Jean Paul')

# IMPORTANT: Different formats create different people
people:
  - María             # Person(name='María')
  - María-José        # Person(name='María José')  [DIFFERENT!]
  - María José        # Person(full_name='María José')  [DIFFERENT!]

# Name with expansion
people:
  - John (John Smith) # → Person(name='John', full_name='John Smith')

# Aliases (requires @ prefix)
people:
  - "@Johnny"         # → Alias(alias='Johnny')
  - "@Sofi (Ana-Sofía)" # → Alias + Person

# Multiple nicknames (use alias array)
people:
  - name: María José
    alias: [María, Majo, MJ]
```

### Location Patterns

```yaml
# Single city (flat list)
city: Montreal
locations:
  - Café Olimpico
  - Mont Royal

# Multiple cities (nested dict - REQUIRED)
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Robarts Library

# Quoted strings (preserve special characters)
locations:
  - "Mom's apartment"
  - "Café #5"
```

### Date Context Patterns

```yaml
# Simple dates
dates:
  - "2024-01-15"
  - "2024-01-20"

# With context
dates:
  - "2024-01-15 (thesis defense)"

# With people/location references
dates:
  - "2024-01-15 (meeting with @John at #Café-X)"

# Explicit dict
dates:
  - date: "2024-01-15"
    context: "thesis defense"
    people: [Dr. Smith]
    locations: [McGill University]

# Opt out of entry date
dates:
  - "~"  # Prevents auto-inclusion
```

### Reference Patterns

```yaml
# Direct quote
references:
  - content: "Quote text"
    mode: direct
    source:
      title: "Source"
      type: book

# Paraphrase
references:
  - description: "Summary"
    mode: paraphrase
    source:
      title: "Source"
      type: book

# Minimal (no source)
references:
  - content: "Quote from conversation"
```

---

## Common Gotchas

### 1. People: @ Prefix for Aliases

```yaml
# ❌ Creates Person, NOT Alias
people:
  - "Johnny"

# ✅ Creates Alias
people:
  - "@Johnny"

# ✅ Multiple nicknames (use alias array)
people:
  - name: Clara
    alias: [Clarabelais, Ari]

# ❌ DON'T add same person twice
people:
  - "@Clarabelais (Clara)"
  - "@Ari (Clara)"  # Wrong!
```

### 1b. People: Name Variants Create Different People

```yaml
# ⚠️ WARNING: These create THREE DIFFERENT people!
people:
  - María              # Person(name='María')
  - María-José         # Person(name='María José')
  - María José         # Person(full_name='María José')

# ✅ SOLUTION: Use one canonical form + aliases
people:
  - name: María José
    alias: [María, Majo]
```

### 2. Locations: Multiple Cities Need Nested Dict

```yaml
# ❌ INVALID
city: [Montreal, Toronto]
locations:
  - Café Olimpico  # Which city??

# ✅ VALID
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Library
```

### 3. Dates: Entry Date Auto-Inclusion

```yaml
# NO dates field → Entry date added WITH people/locations
people: [María]
locations: [Café X]
# Result: Associations created

# HAS dates field → Entry date added WITHOUT associations
people: [María]
dates:
  - "2024-01-20"
# Result: No date associations

# Explicit associations
dates:
  - date: "2024-01-15"
    people: [María]
# Result: Creates people_dates records

# Opt out (tilde MUST be quoted!)
dates:
  - "~"
  - "2024-01-20"
# Result: Only 2024-01-20
```

### 4. References: Need Content OR Description

```yaml
# ❌ INVALID - Missing both
references:
  - source:
      title: "Book"
      type: book

# ✅ VALID - Has content
references:
  - content: "Quote"
    source:
      title: "Book"
      type: book

# ✅ VALID - Has both
references:
  - content: "Quote"
    description: "My interpretation"
    source:
      title: "Book"
      type: book
```

### 5. Poem Revision Date Defaults

```yaml
# Entry date: 2024-01-15
poems:
  - title: "Poem"
    content: "..."
    # revision_date defaults to 2024-01-15
```

### 6. YAML String Quoting

```yaml
# ✅ Use quotes for special characters
locations:
  - "Mom's apartment"  # Apostrophe
  - "Café #5"          # Hash
  - "Title: Subtitle"  # Colon

dates:
  - "~"  # Tilde MUST be quoted

# ❌ Without quotes → Error
locations:
  - Mom's apartment  # Syntax error

dates:
  - ~  # Interpreted as null!
```

---

## Field Type Reference

| Field                  | Type                | Required | Auto | Default |
| ---------------------- | ------------------- | -------- | ---- | ------- |
| `date`                 | string (YYYY-MM-DD) | ✅       | No   | N/A     |
| `word_count`           | int                 | No       | ✅   | 0       |
| `reading_time`         | float               | No       | ✅   | 0.0     |
| `epigraph`             | string              | No       | No   | NULL    |
| `epigraph_attribution` | string              | No       | No   | NULL    |
| `notes`                | string              | No       | No   | NULL    |
| `city`                 | string or list      | No       | No   | NULL    |
| `locations`            | list or dict        | No       | No   | NULL    |
| `people`               | list                | No       | No   | NULL    |
| `dates`                | list                | No       | No   | NULL    |
| `events`               | list                | No       | No   | NULL    |
| `tags`                 | list                | No       | No   | NULL    |
| `related_entries`      | list                | No       | No   | NULL    |
| `references`           | list[dict]          | No       | No   | NULL    |
| `poems`                | list[dict]          | No       | No   | NULL    |
| `manuscript`           | dict                | No       | No   | NULL    |

---

## Enum Values Reference

### Reference Mode

- `direct` (default)
- `indirect`
- `paraphrase`
- `visual`

### Reference Type

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
- `artwork`
- `website`
- `other`

### Manuscript Status

- `source`
- `draft`
- `in_progress`
- `reviewed`
- `included`
- `excluded`
- `final`

### Person Relation Type

- `Family`
- `Friend`
- `Romantic`
- `Professional`
- `Academic`
- `Acquaintance`
- `Other`

---

## SQL Schema Quick Reference

### Main Tables

- `entries` - Journal entries
- `cities` - Cities visited
- `locations` - Specific locations
- `people` - People mentioned
- `aliases` - Person aliases
- `dates` - Mentioned dates
- `events` - Life events/periods
- `tags` - Entry tags
- `reference_sources` - Reference sources
- `references` - Citations
- `poems` - Poem titles
- `poem_versions` - Poem revisions
- `manuscript_entries` - Manuscript metadata
- `manuscript_themes` - Manuscript themes

### Association Tables (Many-to-Many)

- `entry_cities`
- `entry_locations`
- `entry_people`
- `entry_aliases`
- `entry_dates`
- `entry_events`
- `entry_tags`
- `entry_related` (self-referential)
- `people_dates`
- `location_dates`
- `manuscript_entry_themes`

---

## Wiki Editable Fields

### Database-Linked (Synced on Import)

| Entity               | Field                   | SQL Column                                |
| -------------------- | ----------------------- | ----------------------------------------- |
| Entry                | `notes`                 | `entries.notes`                           |
| Event                | `notes`                 | `events.notes`                            |
| Manuscript Entry     | `notes`                 | `manuscript_entries.notes`                |
| Manuscript Entry     | `character_notes`       | `manuscript_entries.character_notes`      |
| Manuscript Character | `character_description` | `manuscript_people.character_description` |
| Manuscript Character | `character_arc`         | `manuscript_people.character_arc`         |
| Manuscript Character | `voice_notes`           | `manuscript_people.voice_notes`           |
| Manuscript Character | `appearance_notes`      | `manuscript_people.appearance_notes`      |

### Wiki-Only (NOT Synced)

| Entity    | Fields                                     |
| --------- | ------------------------------------------ |
| Person    | `notes`, `vignettes`, `category`, `themes` |
| Location  | `notes`                                    |
| City      | `notes`                                    |
| Theme     | `notes`                                    |
| Reference | `notes`                                    |
| Poem      | `notes`                                    |

---

## Validation Rules

### Date Format
- Must be YYYY-MM-DD (ISO 8601)
- Must be valid calendar date
- Must be unique (one entry per date)

### Name Parsing
- Single word → `name`
- Multiple words → `full_name`
- Hyphens in single word → spaces
- Parentheses → name/full_name split
- `@` prefix → alias

### Location Requirements
- Flat list → exactly 1 city required
- Nested dict → multiple cities allowed
- Quoted strings → preserve special chars

### Reference Requirements
- `content` OR `description` required (at least one)
- If `source` present: `title` and `type` required

### Poem Requirements
- `title` required
- `content` required
- `revision_date` defaults to entry date

---

*Last Updated: 2024-12-18*
