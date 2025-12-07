# Metadata Quick Reference Guide

Fast reference for Palimpsest metadata fields with examples.

---

## Navigation

- **Full YAML↔SQL Guide:** [Full YAML↔SQL Guide](../dev-guides/technical/metadata-yaml-sql-guide.md)
- **Full SQL↔Wiki Guide:** [Full SQL↔Wiki Guide](sql-wiki-guide.md)

---

## Field Quick Reference

### Core Fields (Required/Basic)

```yaml
date: 2024-01-15 # Required (YYYY-MM-DD)
word_count: 1543 # Optional (auto-calculated)
reading_time: 7.5 # Optional (minutes)
```

### Text Fields

```yaml
epigraph: "Quote text"
epigraph_attribution: "Author, Work"
notes: "Editorial notes"
```

### Geographic

```yaml
# Single city
city: Montreal

# Multiple cities
city: [Montreal, Toronto, Paris]

# Locations (single city)
city: Montreal
locations:
  - Café Olimpico
  - Mont Royal

# Locations (multiple cities)
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Robarts Library
```

### People (Multiple Formats)

```yaml
people:
  - John # Simple name
  - Jane Smith # Full name
  - Ana-Sofía # Hyphenated (→ "Ana Sofía")
  - Bob (Robert Johnson) # Name + expansion
  - "@Johnny (John)" # Alias
  - "@Sofi (Ana-Sofía)" # Alias with hyphenated name

  # Multiple nicknames for same person (use alias array)
  - name: Clara
    alias: [Clarabelais, Ari]  # DON'T add person twice!
```

### Dates and Timeline

```yaml
dates:
  - "2024-01-20" # Simple date
  - "2024-01-15 (thesis defense)" # With context
  - "2024-01-10 (meeting with @John at #Café-X)" # With references
  - "~"  # MUST be quoted! Opt out of entry date auto-inclusion
  - date: "2024-01-05" # Explicit dict
    context: "appointment"
    people: [John]
    locations: [Café Olimpico]
```

### Events and Tags

```yaml
events:
  - thesis-writing
  - montreal-period

tags:
  - philosophy
  - personal

related_entries:
  - "2024-01-10"
  - "2024-01-12"
```

### References

```yaml
references:
  - content: "The quote text"
    mode: direct # direct, indirect, paraphrase, visual
    speaker: "Speaker Name"
    source:
      title: "Book Title"
      type: book # Required: book, article, film, etc.
      author: "Author Name"
```

### Poems

```yaml
poems:
  - title: "Poem Title"
    content: |
      Line 1
      Line 2
      Line 3
    revision_date: "2024-01-15" # Optional (defaults to entry date)
    notes: "Editorial notes"
```

### Manuscript

```yaml
manuscript:
  status: draft # draft, reviewed, included, excluded, final
  edited: true
  themes:
    - identity
    - relationships
  notes: "Editorial notes"
```

---

## Complete Entry Templates

### Minimal Entry

```yaml
---
date: 2024-01-15
---
Entry content here.
```

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

### Entry with Poems

```yaml
---
date: 2024-01-15
tags:
  - poetry
  - creative
poems:
  - title: "Winter Thoughts"
    content: |
      First line
      Second line
      Third line
---
Entry content here.
```

### Manuscript Entry

```yaml
---
date: 2024-01-15
city: Montreal
people:
  - Ana Sofía
tags:
  - identity
  - friendship
manuscript:
  status: included
  edited: true
  themes:
    - identity-crisis
    - urban-isolation
  notes: "Key entry for Chapter 3"
---
Entry content here.
```

### Comprehensive Entry (All Fields)

```yaml
---
date: 2024-01-15
word_count: 1250
reading_time: 6.2
epigraph: "Quote text here"
epigraph_attribution: "Author, Work"
notes: "Editorial notes"

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

events:
  - phd-research
  - thesis-writing

tags:
  - philosophy
  - identity
  - research

related_entries:
  - "2024-01-10"
  - "2024-01-12"

references:
  - content: "Quote text"
    speaker: Speaker
    source:
      title: "Source Title"
      type: book
      author: "Author Name"

poems:
  - title: "Poem Title"
    content: |
      Poem content
      Multiple lines
    revision_date: "2024-01-15"

manuscript:
  status: included
  edited: true
  themes:
    - identity
    - urban-isolation
  notes: "Key entry for Chapter 3"
---
Entry content here.
```

---

## Common Patterns

### Name Parsing

```yaml
# Simple names
people:
  - John              # → Person(name='John', full_name=None)
  - Jane Smith        # → Person(name='Jane', full_name='Jane Smith')

# Hyphenated names (hyphen → space)
people:
  - Ana-Sofía        # → Person(name='Ana Sofía', full_name=None)
  - Jean-Paul         # → Person(name='Jean Paul', full_name=None)

# IMPORTANT: Hyphenated compound names vs multiple names
people:
  - María             # → Person(name='María', full_name=None)
  - María-José        # → Person(name='María José', full_name=None)  [DIFFERENT PERSON!]
  - María José        # → Person(name='María', full_name='María José')  [DIFFERENT PERSON!]

# Name with expansion (explicit format)
people:
  - John (John Smith) # → Person(name='John', full_name='John Smith')
  - Bob (Robert)      # → Person(name='Bob', full_name='Robert')

# These create the SAME person:
people:
  - Jane Smith        # Auto-parsed: name='Jane', full_name='Jane Smith'
  - Jane (Jane Smith) # Explicit: name='Jane', full_name='Jane Smith'

# Aliases (requires @ prefix)
people:
  - "@Johnny"         # → Alias(alias='Johnny')
  - "@Sofi (Ana-Sofía)" # → Alias(alias='Sofi'), Person(name='Ana Sofía')

# Multiple nicknames for same person (use alias array)
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
  - "2024-01-20 (dentist appointment)"

# With people/location references (@ and #)
dates:
  - "2024-01-15 (meeting with @John at #Café-X)"
  # Extracts: people=['John'], locations=['Café X']

# Explicit dict with people/locations
dates:
  - date: "2024-01-15"
    context: "thesis defense"
    people: [Dr. Smith, Dr. Johnson]
    locations: [McGill University]
  # Creates people_dates and location_dates associations!

# Opt out of entry date auto-inclusion
dates:
  - "~"  # Prevents entry date from being added
  - "2024-01-20"
```

### Date Field Behavior (IMPORTANT!)

```yaml
# SCENARIO A: NO dates field
---
date: 2024-01-15
people: [María, John]
locations: [Café X]
---
# Result: Entry date (2024-01-15) auto-added to mentioned_dates
#         WITH people and locations attached as date associations
#         (people_dates and location_dates records created)

# SCENARIO B: HAS dates field
---
date: 2024-01-15
people: [María, John]
locations: [Café X]
dates:
  - "2024-01-20"
---
# Result: Both dates added to mentioned_dates:
#         - 2024-01-15: NO people/locations attached (just exists)
#         - 2024-01-20: NO people/locations attached (just exists)
#         People/locations only linked to entry, not to specific dates

# SCENARIO C: Explicit date associations
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
# Result:
#         - 2024-01-15: María + Café X associated with THIS date
#         - 2024-01-20: John associated with THIS date
#         Entry also has María and John as general mentions

# SCENARIO D: Opt out of entry date
---
date: 2024-01-15
dates:
  - "~"
  - "2024-01-20"
---
# Result: ONLY 2024-01-20 added to mentioned_dates
#         Entry date (2024-01-15) excluded entirely
```

### Reference Patterns

```yaml
# Direct quote
references:
  - content: "Quote text"
    mode: direct
    speaker: Speaker
    source:
      title: "Source"
      type: book
      author: "Author"

# Paraphrase
references:
  - description: "Summary of argument"
    mode: paraphrase
    source:
      title: "Source"
      type: book
      author: "Author"

# Visual reference
references:
  - description: "Painting description"
    mode: visual
    source:
      title: "Artwork Title"
      type: artwork
      author: "Artist"

# Both content AND description (allowed!)
references:
  - content: "The exact quote"
    description: "My interpretation and context"
    mode: direct
    source:
      title: "Book Title"
      type: book

# Website reference (with URL)
references:
  - content: "Quote from article"
    source:
      title: "Article Title"
      type: website
      author: "Author Name"
      url: "https://example.com/article"

# Minimal (no source)
references:
  - content: "Quote from conversation"
```

### Poem Patterns

```yaml
# Simple poem
poems:
  - title: "Title"
    content: |
      Line 1
      Line 2

# With explicit revision date
poems:
  - title: "Title"
    content: "Content"
    revision_date: "2024-01-20"  # Override entry date
    notes: "Editorial notes"

# Multiple poems
poems:
  - title: "Poem 1"
    content: "Content 1"
  - title: "Poem 2"
    content: |
      Multi-line
      Content 2
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

# ✅ Multiple nicknames for same person (use alias array)
people:
  - name: Clara
    alias: [Clarabelais, Ari]

# ❌ DON'T add same person twice with different nicknames
people:
  - "@Clarabelais (Clara)"
  - "@Ari (Clara)"  # Wrong! Use alias array instead
  # Validator will flag this as ERROR: "Multiple aliases for 'Clara'"
```

### 1b. People: Name Variants Create Different People

```yaml
# ⚠️ WARNING: These create THREE DIFFERENT people!
people:
  - María              # Person(name='María', full_name=None)
  - María-José         # Person(name='María José', full_name=None)
  - María José         # Person(name='María', full_name='María José')

# ✅ SOLUTION: Use one canonical form + aliases
people:
  - name: María José
    alias: [María, Majo]

# OR use explicit alias notation
people:
  - "@María (María-José)"  # "María" is alias for "María José"
```

### 2. Locations: Multiple Cities Need Nested Dict

```yaml
# ❌ INVALID - Flat list with multiple cities
city: [Montreal, Toronto]
locations:
  - Café Olimpico  # Which city??

# ✅ VALID - Nested dict
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Library
```

### 3. Dates: Entry Date Auto-Inclusion & Associations

```yaml
# Entry date: 2024-01-15
# NO dates field → 2024-01-15 auto-added WITH people/locations
people: [María]
locations: [Café X]
# Result: María and Café X associated with 2024-01-15 date

# HAS dates field → Entry date added WITHOUT associations
people: [María]
locations: [Café X]
dates:
  - "2024-01-20"
# Result: Both dates exist, but NO people/location associations
#         María and Café X only linked to entry, not dates

# To add associations, be explicit:
dates:
  - date: "2024-01-15"
    people: [María]
    locations: [Café X]
# Result: Creates people_dates and location_dates records

# To opt out (IMPORTANT: tilde must be quoted!):
dates:
  - "~"  # MUST use quotes
  - "2024-01-20"
# Result: Only 2024-01-20 (entry date excluded)
```

### 4. References: Need Content OR Description (or both!)

```yaml
# ❌ INVALID - Missing both
references:
  - source:
      title: "Book"
      type: book

# ✅ VALID - Has content only
references:
  - content: "Quote"
    source:
      title: "Book"
      type: book

# ✅ VALID - Has description only
references:
  - description: "Summary of the argument"
    mode: paraphrase
    source:
      title: "Book"
      type: book

# ✅ VALID - Has BOTH (perfectly fine!)
references:
  - content: "The exact quote"
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
  - "Café #5"          # Hash symbol
  - "Title: Subtitle"  # Colon

dates:
  - "~"  # Tilde MUST be quoted (YAML reserved character)

# ❌ Without quotes → Syntax error or unexpected behavior
locations:
  - Mom's apartment

dates:
  - ~  # Interpreted as null, not literal tilde!
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

## Enum Values

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

## Command Quick Reference

### Import/Export

```bash
# YAML → SQL
plm sync-db --input md/
plm sync-db --file md/2024/2024-01-15.md
plm sync-db --input md/ --force

# SQL → YAML
plm export-db --output md/
plm export-db --date 2024-01-15 --output md/
plm export-db --output md/ --force --preserve-body

# SQL → Wiki
plm export-wiki
plm export-wiki all

# Wiki → SQL
plm import-wiki
plm import-wiki all
```

### Database Queries

```bash
# Stats
metadb stats

# Query
metadb query "SELECT * FROM entries WHERE date='2024-01-15'"

# Update
metadb update-entry 2024-01-15 --add-tag philosophy
```

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
- If `source` present:
  - `title` required
  - `type` required (validated enum)

### Poem Requirements

- `title` required
- `content` required
- `revision_date` defaults to entry date

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

_Last Updated: 2024-01-15_
