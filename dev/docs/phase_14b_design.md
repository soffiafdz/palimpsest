# Phase 14b: Jumpstart Migration - Design Decisions

## Overview

Phase 14b imports 972 narrative_analysis YAML files into the new database schema, generating initial wiki pages. This document captures all design decisions from the CS/Novelist dialogue.

---

## 1. Entity Curation Workflow

**See:** `entity_curation_workflow.md` for full details.

**Summary:**
- Extract all people/locations from narrative_analysis YAMLs
- Auto-group similar names (Levenshtein, substring matching)
- Generate draft curation files with context (occurrences, dates, scenes)
- Manually curate to resolve ambiguity (typos, duplicates, disambiguation)
- Validate curation files
- Use curated mappings during jumpstart import

**Scripts:**
- `dev/bin/extract_entities.py` - Auto-extraction with grouping
- `dev/bin/validate_curation.py` - Validation before import
- `dev/bin/jumpstart.py` - Main import script

---

## 2. YAML Formats

### 2.1 Journal Metadata YAML

**Two distinct YAML types:**

**Type A: Metadata YAML** (human-edited source)
- Location: `data/journal/content/yaml/{YEAR}/{DATE}.yaml`
- Purpose: Human-edited metadata → parsed into DB
- Format: Concise, heuristic-friendly
- Generated: Auto-skeleton by `dev/pipeline/txt2md.py` when MD created
- Edited: Manually by novelist or via wiki interface

**Type B: Export YAML** (machine-generated backup)
- Location: `data/metadata/journal/{YEAR}/{DATE}.yaml`
- Purpose: DB → version-controlled export for git
- Format: Complete, verbose, all fields populated
- Generated: DB export after any wiki/parser changes
- Never manually edited

**Metadata YAML Format** (concise, human-edited):

```yaml
# data/journal/content/yaml/2024/2024-12-03.yaml
# date, file_path, word_count, reading_time derived from filename/MD frontmatter

# PREPOPULATED (unambiguous keyword matches):
people:
  - name: Clara
    lastname: Moreno
    alias: null

locations:
  Montréal:
    - Lola Rosa
    - The Neuro

# REVIEW REQUIRED (ambiguous - choose one):
people_review_required:
  - # Found "Melissa" - which one?
    - {name: Melissa, lastname: null, alias: null}
    - {name: Melissa, lastname: Díaz, alias: null}

# MANUAL CURATION:
scenes: []
events: []
threads: []
tags: []
themes: []
arcs: []
```

**Export YAML Format** (complete, machine-generated):

```yaml
# data/metadata/journal/2024/2024-12-03.yaml
date: '2024-12-03'
file_path: data/journal/content/md/2024/2024-12-03.md
word_count: 749
reading_time: 2.9
created_at: '2024-12-20T15:30:00Z'  # Distinguishes from human-edited
updated_at: '2025-01-15T09:45:00Z'

summary: >-
  Long summary text folded at 80 characters for readability in
  version control diffs.

rating: 4.5
rating_justification: >-
  Detailed reasoning for the rating.

# People with minimal disambiguation
people:
  - name: Robert  # Unique first name
    lastname: Franck
    alias: Dr-Franck
  - name: Clara
    lastname: Moreno
    alias: null

locations:
  Montréal:
    - The Neuro
    - Jarry's apartment

scenes:
  - name: Psychiatric Session
    description: >-
      Sofia discusses medication adjustment with Dr. Franck at The
      Neuro, expressing concern about worsening symptoms.
    dates: ['2024-12-03']
    people: [Robert]  # Minimal disambiguation: first name sufficient
    locations: [The Neuro]

  - name: The Raki in the Fridge
    description: Sofia debates drinking alone.
    dates: ['2024-12-03']
    # Empty people/locations omitted entirely

events:
  - name: The Dose Increase
    scenes: [Psychiatric Session, The Raki in the Fridge]

threads:
  - name: The Bookend Kiss
    from_date: '2024-12-15'
    to_date: '2024-11'  # Flexible precision preserved
    to_entry: '2024-11-08'
    content: >-
      The greeting kiss bookends the goodbye kiss—structural symmetry
      marking the relationship's progression.
    people: [Clara]
    locations: [Station Jarry]

tags:
  - name: Depression
    description: >-
      Persistent low mood, anhedonia, emotional numbness characteristic
      of depressive episodes.

themes:
  - name: The Spiral
    description: >-
      Cyclical patterns of self-destructive behavior triggered by
      emotional dysregulation.

motifs:
  - name: THE SPIRAL
    description: Downward emotional trajectory and loss of control.

arcs: [The Long Wanting, The Chemical Refuge]

poems:
  - title: Muse
    content: |-
      I miss the idea I built of you.
      Linebreaks preserved with |-.

references:
  - content: Quote text...
    mode: direct
    description: Context for the reference.
    source:
      title: Book Title
      author: Author Name
      type: book
```

**Key Format Rules:**

**People References (increasing disambiguation):**
1. First name if unique: `people: [Robert]`
2. Full name if needed: `people: [Melissa Díaz]`
3. Alias if needed: `people: [Dr-Franck]`

**Empty Fields:**
- Omit entirely (no `people: []`)

**Long Text:**
- Use `>-` for folded text (80 char lines)
- Use `|-` for preserved linebreaks (poems)

**Descriptions:**
- Tags/themes/motifs include descriptions (DB fully reconstructable from YAMLs)

---

### 2.2 Metadata YAML Prepopulation

When `dev/pipeline/txt2md.py` creates a new MD file, it generates skeleton YAML with auto-detected entities.

**Prepopulation Logic:**

```python
def prepopulate_entities(md_content: str, session: Session) -> dict:
    """
    Search MD content for people (names + aliases) and locations.
    Prepopulate unambiguous matches, show candidates for ambiguous.
    """
    # Search for all Person records (name + alias)
    for person in all_people:
        search_terms = [person.name]
        if person.alias:
            search_terms.append(person.alias)

        if any(term found in md_content):
            # Check ambiguity
            same_name_count = count people with same name

            if same_name_count == 1:
                # Unambiguous - prepopulate full dict
                prepopulated_people.append({name, lastname, alias})
            else:
                # Ambiguous - show all candidates
                people_review_required.append([
                    {candidate1}, {candidate2}, ...
                ])

    # Locations: prepopulate if unambiguous AND not context-dependent
    CONTEXT_DEPENDENT = ["Home", "Apartment", "home", "apartment"]

    for location in all_locations:
        if location.name in CONTEXT_DEPENDENT:
            continue  # Skip - requires human judgment

        if location.name found in md_content:
            same_name_count = count locations with same name

            if same_name_count == 1:
                # Unambiguous - prepopulate with city
                prepopulated_locations[city].append(location.name)
            # If ambiguous - skip (cleaner than noise)
```

**Result:**
- Unambiguous people: full dict prepopulated (delete if false positive)
- Ambiguous people: all candidates shown (pick one, delete others)
- Unambiguous locations: prepopulated with city
- Ambiguous/context-dependent locations: left blank

---

### 2.3 Metadata YAML Parser & Validator

**Parser:**
- Reads `data/journal/content/yaml/{YEAR}/{DATE}.yaml`
- Resolves people by name/alias/full name against DB
- Resolves locations by name + city context
- Validates relationships (scene.people ⊆ entry.people, etc.)
- Raises `ValidationError` for unresolvable references
- Transaction rolls back on error (user must fix YAML)

**Validation Rules:**

1. **People resolution:**
   - Must find exact match in DB
   - If ambiguous (2+ people with same name), require full name or alias
   - Error: "Cannot resolve person 'Melissa' - 2 matches found"

2. **Location resolution:**
   - Requires city context (from MD frontmatter or location dict)
   - Must find exact match in DB for that city
   - Error: "Cannot resolve location 'Home' in Montréal"

3. **Thread validation:**
   - `to_entry` date must reference existing Entry (or forward ref allowed, see 2.4)
   - Date formats: YYYY, YYYY-MM, YYYY-MM-DD, "TBD"
   - Error: "Thread references non-existent entry '2025-03-15'"

4. **Scene hierarchy:**
   - `scene.people ⊆ entry.people`
   - `scene.locations ⊆ entry.locations`
   - `scene.dates ⊆ entry.narrated_dates`
   - Error: "Scene 'X' has person 'Y' not in entry.people"

---

### 2.4 Thread Forward References

**Problem:** Threads can reference future entries not yet imported.

**Solution: Deferred Linking (Option B)**

**Import Process:**
1. First pass: Import all entries, store thread `to_entry` as string (not resolved FK)
2. After all entries loaded: Resolution pass updates `Thread.to_entry_id` by looking up date
3. Threads to non-existent entries remain with NULL `to_entry_id` (valid for future entries)

**Implementation:**

```python
# Pass 1: Import entry with thread string
thread = Thread(
    name="The Kiss Foreshadowed",
    from_date=date(2024, 11, 8),
    to_date="2024-12",  # Flexible precision
    to_entry_str="2024-12-15",  # String storage
    to_entry_id=None,  # Not resolved yet
)

# Pass 2: Resolve after all entries loaded
for thread in all_threads:
    if thread.to_entry_str:
        target_entry = session.query(Entry).filter_by(
            date=parse_date(thread.to_entry_str)
        ).first()

        if target_entry:
            thread.to_entry_id = target_entry.id
        else:
            # Log warning but allow (future entry)
            logger.warning(f"Thread '{thread.name}' references future entry")
```

---

## 3. Manuscript Metadata Format

### 3.1 Directory Structure

```
data/metadata/manuscript/
├── chapters/
│   ├── the_gray_fence.yaml
│   ├── the_kiss_at_jarry.yaml
│   └── ...
└── characters/
    ├── clara.yaml
    ├── majo.yaml
    └── ...
```

### 3.2 Chapter YAML

**Minimal Input** (human-edited bootstrap):

```yaml
# chapters/the_gray_fence.yaml
title: The Gray Fence
type: prose  # prose, vignette, poem

scenes:
  - name: First Sight
    description: Sofia sees Clara at the fence.
    source_entries: ['2024-11-08']
```

**Complete Export** (machine-generated):

```yaml
# chapters/the_gray_fence.yaml
title: The Gray Fence
slug: the_gray_fence
type: prose
status: draft  # draft, revised, final
order: 1
word_count: 3420
reading_time: 13.5
created_at: '2024-12-20T15:30:00Z'
updated_at: '2025-01-15T09:45:00Z'

notes: >-
  First chapter introducing Clara. Needs work on pacing in the middle
  section. Consider cutting the coffee shop scene.

themes:
  - name: Longing
    description: Unfulfilled desire and anticipation.

scenes:
  - id: 42
    name: First Sight
    origin: journaled  # journaled, inferred, invented, composite
    status: included   # fragment, draft, included, cut
    description: >-
      Sofia sees Clara for the first time at the fence outside the
      apartment building.
    source_entries: ['2024-11-08', '2024-12-15']
    notes: >-
      Primary scene from Nov 8. Dec 15 thread provided emotional
      framing for how to structure the ending.
    created_at: '2024-12-20T15:30:00Z'
    updated_at: '2025-01-10T12:00:00Z'

  - id: 43
    name: The Invented Dialogue
    origin: invented
    status: draft
    description: Fictional conversation between Clara and Majo.
    # No source_entries - purely created
    notes: Needs revision.

draft_file: data/manuscript/drafts/the_gray_fence.md
```

**Field Rules:**

**Required (input):**
- `title`
- `type` (enum: prose, vignette, poem)

**Optional (input, with defaults):**
- `status` - defaults to "draft"
- `scenes.origin` - defaults to "invented"
- `scenes.status` - defaults to "draft"
- `scenes.source_entries` - omit if purely fictional

**Always in export:**
- All fields above plus `id`, `slug`, `created_at`, `updated_at`, etc.

---

### 3.3 Character YAML

**Minimal Input:**

```yaml
# characters/clara.yaml
name: Clara
role: Love Interest

based_on:
  - person: Clara Moreno  # Resolved via DB lookup
```

**Complete Export:**

```yaml
# characters/clara.yaml
name: Clara
slug: clara
role: Love Interest
archetype: The Muse
created_at: '2024-12-20T15:30:00Z'
updated_at: '2025-01-15T09:45:00Z'

description: >-
  Mid-30s architect with turquoise eyes. Warm, enigmatic, emotionally
  unavailable. Represents unattainable desire.

based_on:
  - person:
      name: Clara
      lastname: Moreno
      alias: null
    notes: >-
      Physical description and emotional dynamic directly drawn from
      real relationship. Changed occupation from designer to architect.

appearances:
  - chapter_slug: the_gray_fence
    scenes: [First Sight, The Conversation]
  - chapter_slug: the_kiss_at_jarry
    scenes: [Platform Encounter, The Kiss]

notes: >-
  Need to decide: does she reciprocate in the end or remain distant?
  Current draft leans toward ambiguous ending.
```

**For composite characters:**

```yaml
# characters/the_therapist.yaml
name: The Therapist
role: Supporting

based_on:
  - person: Robert Franck
    notes: Borrowed mannerisms and office setting.
  - person: Elena Smith
    notes: Therapeutic approach and dialogue style.

notes: >-
  Composite character blending Dr. Franck and Dr. Smith. Added
  fictional backstory about immigration for thematic resonance.
```

**For purely fictional characters:**

```yaml
# characters/the_barista.yaml
name: The Barista
role: Minor

# No based_on section - purely invented

notes: Minor character appearing in two composite coffee shop scenes.
```

**Key Decisions:**

1. **No `contribution_type` enum** - Dropped as unnecessary. Number of people in `based_on` indicates composite vs. direct (1 = direct, >1 = composite). Notes explain HOW each person contributed.

2. **`based_on` is M2M relationship** - Maps to `PersonCharacterMap` table in DB. Parser resolves `person: "Clara Moreno"` → finds Person record → creates mapping.

3. **Optional fields** - `based_on`, `appearances`, `notes` all optional. Purely fictional characters omit `based_on` entirely.

---

## 4. Scene Hierarchy & Validation

**Entry-level data = UNION of scene data + additional mentions**

```yaml
# Entry level (superset)
people:
  - Robert Franck
  - Clara Moreno
  - Majo  # Mentioned in text but not in any scene

locations:
  Montréal:
    - The Neuro
    - Jarry's apartment
    - Station Jarry  # Mentioned but not in any scene

narrated_dates: ['2024-12-03', '2024-12-02']  # Includes flashback

# Scene level (subset)
scenes:
  - name: Psychiatric Session
    dates: ['2024-12-03']
    people: [Robert]
    locations: [The Neuro]
```

**Validation Rule:**
```
scene.people ⊆ entry.people
scene.locations ⊆ entry.locations
scene.dates ⊆ entry.narrated_dates
```

If scene has person/location/date not in entry, parser raises `ValidationError`.

---

## 5. Import Order & Dependencies

**Jumpstart Import Sequence:**

```
1. Load people_curation.yaml → Create Person records
2. Load locations_curation.yaml → Create City + Location records
3. Load narrative_analysis YAMLs (Pass 1):
   - Create Entry records
   - Create Scene, Event, Arc, Tag, Theme records
   - Link to people/locations via curation mappings
   - Store Thread.to_entry as string (not resolved)
4. Load legacy archives:
   - Merge poems_archive.yaml → create Poem/PoemVersion
   - Merge references_archive.yaml → create Reference/ReferenceSource
5. Resolve thread forward references (Pass 2):
   - Update Thread.to_entry_id by looking up dates
   - Log warnings for orphaned threads (future entries)
```

**Why this order?**
- People/locations must exist before entries reference them
- Entries must exist before resolving thread.to_entry_id
- Legacy archives merge by date (require entries to exist)

**Thread Resolution:**
- Two-pass approach handles forward references
- Threads can reference not-yet-written entries (NULL to_entry_id valid)
- No topological sort needed (simpler implementation)

---

## 6. Workflow Summary

### 6.1 One-Time Jumpstart (Phase 14b)

```bash
# 1. Extract entities from narrative_analysis YAMLs
python -m dev.bin.extract_entities

# 2. Manually curate:
#    - data/curation/people_curation_draft.yaml → people_curation.yaml
#    - data/curation/locations_curation_draft.yaml → locations_curation.yaml

# 3. Validate curation
python -m dev.bin.validate_curation

# 4. Run jumpstart import
python -m dev.bin.jumpstart

# 5. Verify import (counts, spot-checks)

# 6. Export to new YAML format for git
python -m dev.bin.export_all

# 7. Delete obsolete data
rm -rf data/narrative_analysis/
rm -rf data/legacy/
```

### 6.2 Ongoing Workflow (Post-Jumpstart)

**For Journal Entries:**

**Option A: MD creation triggers skeleton**
```bash
# Pipeline creates MD + skeleton YAML automatically
python -m dev.pipeline.txt2md input.txt
# → creates: data/journal/content/md/2024/2024-12-03.md
# → creates: data/journal/content/yaml/2024/2024-12-03.yaml (prepopulated)

# Manually curate YAML, then parse into DB
python -m dev.bin.parse_metadata data/journal/content/yaml/2024/2024-12-03.yaml

# DB exports to backup YAML
python -m dev.bin.export_entry 2024-12-03
# → updates: data/metadata/journal/2024/2024-12-03.yaml
```

**Option B: Wiki editing**
```
1. Edit entry via wiki interface
2. Wiki → updates DB
3. DB → exports YAML automatically
   → updates: data/metadata/journal/2024/2024-12-03.yaml
```

**For Manuscript:**

```bash
# Bootstrap: manually create chapter/character YAMLs
vim data/metadata/manuscript/chapters/new_chapter.yaml

# Parse into DB (one-time or infrequent)
python -m dev.bin.parse_manuscript

# Work via wiki (primary interface)
# Wiki → DB → auto-exports YAML

# Git tracks export YAMLs (complete, machine-generated)
git add data/metadata/manuscript/
git commit -m "Update manuscript structure"
```

---

## 7. Key Technical Decisions

### 7.1 Two YAML Formats (Input vs Export)

**Input:**
- Concise, human-friendly
- Optional fields (minimal bootstrap)
- Heuristic-friendly (forgiving parsing)

**Export:**
- Complete, machine-optimal
- All DB fields serialized
- Verbose but unambiguous
- Distinguishable by presence of `created_at` field

### 7.2 People/Location Disambiguation

**People:**
- Minimal disambiguation (first name → full name → alias)
- Export uses least ambiguous form needed
- Input parser accepts any variation, resolves via DB lookup
- Ambiguous cases error out (require clarification)

**Locations:**
- Hierarchical structure (city → locations)
- Context-dependent locations ("Home") not auto-prepopulated
- Date-based resolution in curation (multiple residences)

### 7.3 Thread Date Flexibility

- Threads preserve precision ambiguity
- Valid formats: YYYY, YYYY-MM, YYYY-MM-DD, "TBD"
- Export doesn't normalize (keeps original precision)
- DB stores as string to preserve ambiguity

### 7.4 Scene Hierarchy

- Entry-level data is SUPERSET of scene data
- Scenes can omit people/locations if entry-level captures them
- Validation ensures no orphan references (scene data must exist in entry)

### 7.5 Manuscript Compositing

- `based_on` field maps to M2M PersonCharacterMap
- No `contribution_type` enum (dropped as unnecessary)
- Number of people indicates direct vs composite (1 vs >1)
- Fictionalization explained in prose `notes` field

---

## 8. Next Steps

**After Phase 14b Documentation:**
1. Implement entity extraction script (`dev/bin/extract_entities.py`)
2. Implement validation script (`dev/bin/validate_curation.py`)
3. Implement jumpstart script (`dev/bin/jumpstart.py`)
4. Implement metadata parser (`dev/bin/parse_metadata.py`)
5. Implement export scripts (`dev/bin/export_all.py`, `dev/bin/export_entry.py`)
6. Update `dev/pipeline/txt2md.py` to generate skeleton YAMLs
7. Test on small subset (10 entries)
8. Run full jumpstart (972 entries)
9. Validate, then delete `narrative_analysis/` and `legacy/`
