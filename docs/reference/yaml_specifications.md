# YAML Specifications

## Overview

The Palimpsest system uses YAML files for metadata storage and version control. This document specifies the format and structure of all YAML files.

---

## Journal Metadata YAML

### Two Types

**Metadata YAML** (human-edited)
- Location: `data/journal/content/yaml/{YEAR}/{DATE}.yaml`
- Purpose: Human-edited metadata → parsed into database
- Format: Concise, accepts variations

**Export YAML** (machine-generated)
- Location: `data/metadata/journal/{YEAR}/{DATE}.yaml`
- Purpose: Database export for version control
- Format: Complete, verbose
- Distinguishable by presence of `created_at` field

---

### Metadata YAML Format

Human-edited source that gets parsed into the database:

```yaml
# data/journal/content/yaml/2024/2024-12-03.yaml
# date, file_path, word_count, reading_time derived from filename/MD frontmatter

people:
  - name: Léa
    lastname: Moreau
    alias: null

locations:
  Montréal:
    - Lola Rosa
    - The Neuro

scenes:
  - name: Psychiatric Session
    description: Sofia discusses medication adjustment.
    dates: ['2024-12-03']
    people: [Robert]
    locations: [The Neuro]

events:
  - name: The Dose Increase
    scenes: [Psychiatric Session]

threads:
  - name: The Bookend Kiss
    from_date: '2024-12-15'
    to_date: '2024-11'
    to_entry: '2024-11-08'
    content: The greeting kiss bookends the goodbye kiss.
    people: [Léa]

tags: [Depression, Medication]
themes: [The Spiral]
arcs: [The Long Wanting]
```

**Field Rules:**

- `people`: Can use first name, full name, or alias (resolved via database)
- `locations`: Nested by city
- `scenes`: Optional `people`/`locations` fields (omit if empty)
- `threads.to_date`: Flexible precision (YYYY, YYYY-MM, or YYYY-MM-DD)
- Empty arrays: omit field entirely

---

### Export YAML Format

Machine-generated complete export from database:

```yaml
# data/metadata/journal/2024/2024-12-03.yaml
date: '2024-12-03'
file_path: data/journal/content/md/2024/2024-12-03.md
word_count: 749
reading_time: 2.9
created_at: '2024-12-20T15:30:00Z'
updated_at: '2025-01-15T09:45:00Z'

summary: >-
  Long summary text folded at 80 characters for readability.

rating: 4.5
rating_justification: >-
  Detailed reasoning for the rating.

people:
  - name: Robert
    lastname: Franck
    alias: Dr-Franck

locations:
  Montréal:
    - The Neuro

scenes:
  - name: Psychiatric Session
    description: >-
      Sofia discusses medication adjustment with Dr. Franck.
    dates: ['2024-12-03']
    people: [Robert]
    locations: [The Neuro]

events:
  - name: The Dose Increase
    scenes: [Psychiatric Session]

threads:
  - name: The Bookend Kiss
    from_date: '2024-12-15'
    to_date: '2024-11'
    to_entry: '2024-11-08'
    content: >-
      The greeting kiss bookends the goodbye kiss—structural
      symmetry marking the relationship's progression.
    people: [Léa]

tags:
  - name: Depression
    description: >-
      Persistent low mood, anhedonia, emotional numbness.

themes:
  - name: The Spiral
    description: >-
      Cyclical patterns of self-destructive behavior.

motifs:
  - name: THE SPIRAL
    description: Downward emotional trajectory.

arcs: [The Long Wanting]

poems:
  - title: Muse
    content: |-
      I miss the idea I built of you.
      Linebreaks preserved.

references:
  - content: Quote text...
    mode: direct
    description: Context.
    source:
      title: Book Title
      author: Author Name
      type: book
```

**Formatting Rules:**

- Long text: `>-` (folded, 80 char lines)
- Preserved linebreaks: `|-` (poems)
- People: minimal disambiguation (first name → full name → alias)
- Empty fields: omitted entirely
- Descriptions: included for tags/themes/motifs

---

### Scene Hierarchy

Entry-level data is superset of scene data:

```yaml
# Entry level
people:
  - Robert Franck
  - Léa Moreau
  - Inès  # Mentioned but not in specific scene

# Scene level
scenes:
  - name: Psychiatric Session
    people: [Robert]  # Subset of entry.people
```

**Validation:**
- `scene.people ⊆ entry.people`
- `scene.locations ⊆ entry.locations`
- `scene.dates ⊆ entry.narrated_dates`

---

## Manuscript Metadata YAML

### Directory Structure

```
data/metadata/manuscript/
├── chapters/
│   └── {slug}.yaml
└── characters/
    └── {slug}.yaml
```

---

### Chapter YAML

**Minimal Input:**

```yaml
# chapters/the_gray_fence.yaml
title: The Gray Fence
type: prose

scenes:
  - name: First Sight
    description: Sofia sees Léa at the fence.
    source_entries: ['2024-11-08']
```

**Complete Export:**

```yaml
title: The Gray Fence
slug: the_gray_fence
type: prose
status: draft
order: 1
word_count: 3420
reading_time: 13.5
created_at: '2024-12-20T15:30:00Z'
updated_at: '2025-01-15T09:45:00Z'

notes: >-
  First chapter introducing Léa.

themes:
  - name: Longing
    description: Unfulfilled desire and anticipation.

scenes:
  - id: 42
    name: First Sight
    origin: journaled
    status: included
    description: >-
      Sofia sees Léa for the first time.
    source_entries: ['2024-11-08']
    notes: Primary scene from Nov 8.

draft_file: data/manuscript/drafts/the_gray_fence.md
```

**Field Rules:**

**Required:** `title`, `type`

**Optional (with defaults):**
- `status`: defaults to "draft"
- `scenes.origin`: defaults to "invented"
- `scenes.status`: defaults to "draft"
- `scenes.source_entries`: omit if no journal sources

**Enums:**
- `type`: prose, vignette, poem
- `status`: draft, revised, final
- `origin`: journaled, inferred, invented, composite
- `scene.status`: fragment, draft, included, cut

---

### Character YAML

**Minimal Input:**

```yaml
# characters/lea.yaml
name: Léa
role: Love Interest

based_on:
  - person: Léa Moreau
```

**Complete Export:**

```yaml
name: Léa
slug: lea
role: Love Interest
archetype: The Muse
created_at: '2024-12-20T15:30:00Z'

description: >-
  Mid-30s architect with turquoise eyes.

based_on:
  - person:
      name: Léa
      lastname: Moreau
      alias: null
    notes: >-
      Physical description directly drawn from real relationship.

appearances:
  - chapter_slug: the_gray_fence
    scenes: [First Sight]

notes: >-
  Character development notes.
```

**Composite Characters:**

```yaml
name: The Therapist
role: Supporting

based_on:
  - person: Robert Franck
    notes: Borrowed mannerisms and office setting.
  - person: Elena Smith
    notes: Therapeutic approach and dialogue style.

notes: >-
  Composite character blending two real people.
```

**Fictional Characters:**

```yaml
name: The Barista
role: Minor

# No based_on - purely invented

notes: Minor character in two scenes.
```

---

## Validation Rules

### Parser Validation

**People Resolution:**
- Must find exact match in database
- Ambiguous names (2+ matches) require full name or alias
- Error: "Cannot resolve person 'Melissa' - 2 matches found"

**Location Resolution:**
- Requires city context
- Must find exact match in database
- Error: "Cannot resolve location 'Home' in Montréal"

**Thread Validation:**
- `to_entry` must reference existing entry (or NULL for future)
- Valid date formats: YYYY, YYYY-MM, YYYY-MM-DD, "TBD"
- Error: "Thread references non-existent entry"

**Scene Hierarchy:**
- Scene people/locations must exist in entry
- Error: "Scene has person not in entry.people"

---

## Thread Date Formats

Threads preserve precision ambiguity:

- `"2024"` - year only (approximate)
- `"2024-11"` - year-month (approximate)
- `"2024-11-08"` - full date (precise)
- `"TBD"` - unknown

Export maintains original precision (doesn't normalize).

---

## Curation YAML Files

Single-file bulk-editing formats for curation-only fields. These are the primary source of truth for their respective fields; values propagate to per-entity YAML and DB on import/export.

### Neighborhoods (`data/metadata/neighborhoods.yaml`)

Maps location neighborhoods grouped by city slug:

```yaml
# Neighborhood for each location, grouped by city slug
# Valid: any free-text string (or ~ for unset)
montreal:
  cafe-olimpico: Mile End
  parc-jarry: Villeray
  apartment-jarry: ~
paris:
  cafe-de-flore: Saint-Germain
  jardin-du-luxembourg: ~
```

**Structure:** `{city_slug: {location_slug: neighborhood_string | null}}`

**Rules:**
- All locations listed (filled values + `~` for null)
- Grouped by parent city slug
- Free-text values (no enum constraint)
- `~` (null) clears existing neighborhood value on import
- Slug keys match per-entity YAML filenames

### Relation Types (`data/metadata/relation_types.yaml`)

Maps person relation types by person slug:

```yaml
# Valid: family, friend, romantic, colleague, professional, acquaintance, public, other
ines: romantic
lea: friend
marc: ~
robert: professional
```

**Structure:** `{person_slug: relation_type_string | null}`

**Rules:**
- All people listed (filled values + `~` for null)
- Values must be valid `RelationType` enum values (lowercase)
- `~` (null) clears existing relation type on import
- Slug keys match per-entity YAML filenames

### Import/Export Commands

```bash
# Export curation files
plm metadata export --type neighborhoods
plm metadata export --type relation_types

# Import curation files
plm metadata import --type neighborhoods
plm metadata import --type relation_types

# Export all (includes curation files)
plm metadata export
```

---

## Database Reconstruction

Export YAMLs contain complete data. Database can be fully reconstructed from:
- `data/metadata/journal/**/*.yaml`
- `data/metadata/manuscript/**/*.yaml`
- `data/metadata/neighborhoods.yaml`
- `data/metadata/relation_types.yaml`

All relationships, descriptions, and metadata preserved in export format.
