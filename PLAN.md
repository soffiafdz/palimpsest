# Phase 14: Complete Data Architecture Redesign

## Document Purpose

This document captures ALL conclusions from the CS/Novelist dialogue sessions that designed the Phase 14 data architecture. It serves as the authoritative reference for all agents working on this phase. This is a temporary planning document—not permanent documentation.

**Status:** Planning complete. Implementation in progress (Phase 14b).

**Previous phases completed:**
- Phase 13a: Legacy code cleanup (complete)
- Arc sync script (complete, 133 files updated)
- Phase 14a: DB Schema + Source Files (complete)

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Entity File Organization](#entity-file-organization) ← NEW
4. [The CS/Novelist Dialogue Conclusions](#the-csnovelist-dialogue-conclusions)
5. [MD Frontmatter Specification](#md-frontmatter-specification)
6. [Database Schema - Journal Domain](#database-schema---journal-domain)
7. [Database Schema - Manuscript Domain](#database-schema---manuscript-domain)
8. [YAML Export Specifications](#yaml-export-specifications)
9. [Directory Structure](#directory-structure)
10. [Existing Infrastructure](#existing-infrastructure)
11. [Implementation Phases](#implementation-phases)
12. [Pending Decisions](#pending-decisions)
13. [Controlled Vocabularies](#controlled-vocabularies)
14. [Verification Commands](#verification-commands)
15. [Migration Strategy Details](#migration-strategy-details)

---

## Executive Summary

Phase 14 is a complete redesign of the Palimpsest data architecture. The old database schema is **FULLY DEPRECATED**—we design from scratch.

### Core Decisions

1. **Vimwiki is the single workspace** for editing all metadata (both journal analysis and manuscript content)
2. **Database derives from wiki** — wiki is parsed on save, DB is updated
3. **YAML files are machine-generated exports** for git version control, not human-authored sources
4. **Journal MD files remain ground truth** for prose content (read-only in wiki)
5. **Manuscript drafts** are separate `.md` files; metadata lives in wiki

### What This Replaces

- The current `narrative_analysis/` YAML files (will be deleted after migration)
- The current database schema (deprecated entirely)
- The current MD frontmatter structure (will be minimized)

---

## Architecture Overview

### Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              VIMWIKI                                        │
│  Workspace for BOTH journal metadata AND manuscript content                 │
│  Location: data/wiki/                                                       │
│  (SOURCE OF TRUTH for all metadata)                                         │
│                                                                             │
│  - Journal entry pages: metadata editable, prose displayed (read-only)      │
│  - Manuscript chapter pages: dashboard with metadata, links to draft files  │
│  - Entity pages: people, characters, locations, arcs, etc.                  │
│  - Dashboards: coverage reports, entity indexes                             │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ parse on save (dev/wiki/parser.py)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE                                       │
│  Queryable state (SQLite)                                                   │
│  Location: data/metadata/palimpsest.db                                      │
│  (DERIVED from wiki)                                                        │
│                                                                             │
│  - All entities with full relationships                                     │
│  - Enables complex queries across journal and manuscript                    │
│  - Supports wiki generation and validation                                  │
└─────────────────────────────────┬───────────────────────────────────────────┘
                                  │
                                  │ export (dev/pipeline/export_yaml.py)
                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            YAML FILES                                       │
│  Git-tracked exports (machine-generated)                                    │
│  Location: data/metadata/journal/, data/metadata/manuscript/                │
│  (BACKUP/VERSION CONTROL - not manually edited)                             │
│                                                                             │
│  - Human-readable for git diffs                                             │
│  - Recovery if wiki/DB corrupts                                             │
│  - Historical record of metadata changes                                    │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Ground Truth by Domain

| Domain | Ground Truth Source | DB Role | YAML Role | Wiki Role |
|--------|---------------------|---------|-----------|-----------|
| Journal prose | MD files (`data/journal/content/md/`) | — | — | Display only (read-only) |
| Journal metadata | Wiki pages | Derived (queryable index) | Export (git backup) | **Editable workspace** |
| Manuscript metadata | Wiki pages | Derived (queryable index) | Export (git backup) | **Editable workspace** |
| Manuscript prose | Draft files (`data/manuscript/drafts/`) | Path reference only | — | Links to files |

### Migration Path

```
[PHASE 14b - JUMPSTART (file cleanup only)]
┌─────────────────────────────────────────────────────────────────┐
│  CURRENT STATE                                                  │
│  - MD frontmatter (✓ already minimal)                           │
│  - Narrative analysis YAMLs (scenes, events, threads, etc.)     │
│  - Legacy archives (poems, references, notes by entry date)     │
│  - Per-year curation files (for entity resolution)              │
└───────────────────────────┬─────────────────────────────────────┘
                            │ merge & transform
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  CLEAN FILES                                                    │
│  - NEW metadata/journal/YYYY/*.yaml with:                       │
│    - narrative analysis + poems + references                    │
│    - consistent entity names (resolved via curation)            │
│  - narrative_analysis/ DELETED                                  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ import to DB
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  DATABASE                                                       │
│  All entities with full relationships                           │
└───────────────────────────┬─────────────────────────────────────┘
                            │ export
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  CANONICAL YAML FILES                                           │
│  Exported from DB with all relationships                        │
│  - metadata/people/*.yaml (person + entries, scenes, threads)   │
│  - metadata/journal/YYYY/*.yaml (entry + all analysis)          │
│  - metadata/locations/{city}/*.yaml                             │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ▼
                      WIKI PAGES

[ONGOING WORKFLOW after migration]
WIKI (edit) ──→ DB (derived) ──→ Canonical YAML (exported for git)
```

---

## Entity File Organization

**Concluded 2025-01-30** — This section documents decisions about how entity YAML files are organized.

### The Problem

Curation files are substantial:
- `2016_people_curation.yaml`: 75KB (just names + dates)
- Total across years: ~300KB for people alone

Per-year splitting causes consistency problems:
- People span multiple years (Clara appears in 2021, 2024, 2025—which file owns her?)
- Character mappings are decided at manuscript time, not when person first appeared
- Updating `relation_type` means hunting across files
- Merging duplicate people requires cross-file edits

### Decision: Per-Entity Files for People and Locations

**People:** One file per person in `metadata/people/`

```
metadata/
  people/
    clara-moreno.yaml
    jose-luis-borboa.yaml
    monica-garcia-college.yaml   # disambiguator in filename
    monica-lopez-work.yaml
```

**File naming:**
- Primary: `{name}-{lastname}.yaml` or `{name}.yaml` if no lastname
- Disambiguator appended when needed: `monica-garcia-college.yaml`

**Locations:** Organized by city subdirectories

```
metadata/
  locations/
    montreal/
      home.yaml
      cafe-olimpico.yaml
      the-neuro.yaml
    mexico-city/
      coyoacan.yaml
      colonia-roma.yaml
```

### Full Person YAML Schema

Based on database models (`dev/database/models/entities.py` and `dev/database/models/manuscript.py`):

```yaml
# metadata/people/clara-moreno.yaml
name: Clara
lastname: Moreno
disambiguator: null
relation_type: romantic        # RelationType enum

aliases:
  - Clarita
  - C

# Manuscript domain - character mappings
characters:
  - character: elise           # slug reference to character
    contribution: primary      # ContributionType: primary, composite, inspiration
    notes: "Main romantic arc protagonist"
```

**Fields from Person model:**
- `name`: First/given name (required)
- `lastname`: Last/family name (optional)
- `disambiguator`: Context tag for same-name people with unknown lastnames
- `relation_type`: RelationType enum (family, friend, romantic, colleague, acquaintance, professional, public, other)
- `aliases`: List of alternative names for lookup

**Fields from PersonCharacterMap:**
- `characters`: List of character mappings
  - `character`: Reference to Character entity
  - `contribution`: ContributionType enum (primary, composite, inspiration)
  - `notes`: How this person contributes to the character

### Full Location YAML Schema

```yaml
# metadata/locations/montreal/cafe-olimpico.yaml
name: Café Olimpico
city: Montreal
```

### Simpler Entity Types: Single Files

These have fewer entries and simpler structure—single files are fine:

```
metadata/
  arcs.yaml              # Arc definitions
  poems.yaml             # Poem parent entities
  reference_sources.yaml # Books, films, songs, etc.
```

**Tags, themes, motifs:** Auto-created on import if they don't exist (just name strings).

### Curation Files vs Canonical Files

Two distinct file types:

| Type | Purpose | Format | Location |
|------|---------|--------|----------|
| **Curation files** | Working documents for manual review | Per-year, includes `dates` for context | `data/curation/2021_people_curation.yaml` |
| **Canonical files** | Source of truth after curation | Per-entity, no dates list | `data/metadata/people/clara-moreno.yaml` |

Curation files are temporary. After curation is complete and entities are merged into canonical files, curation files can be archived or deleted.

---

## The CS/Novelist Pseudo-Adversary Dialogue Technique

### What It Is

The CS/Novelist dialogue is a pseudo-adversarial design technique where Claude plays **both roles alternately**, and the user provides corrections/refinements to each persona's statements. It's a structured way to explore design decisions by having two perspectives argue, with the user as the arbiter who steers both toward the correct solution.

### The Roles

**The Novelist (Domain Expert / End User)**
- Represents the creative workflow and practical needs
- Argues for what the system must support to enable the work
- Focuses on: discoverability, workflow, ease of use, creative freedom
- Asks: "How will I actually use this when I'm writing?"
- Pushes back on: unnecessary complexity, rigid structures, technical ceremony that impedes creativity
- Tendency: wants everything accessible, rich metadata, minimal friction

**The CS (Computer Scientist / Architect)**
- Represents technical architecture and best practices
- Argues for clean design, separation of concerns, maintainability
- Focuses on: data integrity, queryability, scalability, consistency
- Asks: "How do we structure this so it's reliable and maintainable?"
- Pushes back on: redundancy, ambiguity, unstructured data, over-engineering
- Tendency: wants clear sources of truth, normalized data, typed schemas

### How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│  1. Claude (as Role A) makes a proposal with justification      │
├─────────────────────────────────────────────────────────────────┤
│  2. User complements/contradicts/rectifies from their own       │
│     perspective (blending both CS and Novelist viewpoints)      │
├─────────────────────────────────────────────────────────────────┤
│  3. Claude (as Role B) responds, incorporating user's input     │
├─────────────────────────────────────────────────────────────────┤
│  4. User refines again                                          │
├─────────────────────────────────────────────────────────────────┤
│  5. Claude (as Role A) counter-responds                         │
├─────────────────────────────────────────────────────────────────┤
│  6. Continue until agreement or user says "move on"             │
└─────────────────────────────────────────────────────────────────┘
```

### Rules of Engagement

1. **Claude alternates roles** — After each user response, Claude switches to the other persona
2. **User is the arbiter** — User corrections are incorporated immediately; the persona doesn't argue against the user
3. **Concise turns** — Each persona speaks in 2-4 focused paragraphs, not essays
4. **Specific proposals** — Abstract discussion is converted to concrete proposals (schemas, examples, workflows)
5. **No circular arguments** — If a point is settled, don't revisit unless the user raises it
6. **Signal agreement** — When both personas converge, acknowledge it and move to the next topic
7. **User can inject new concerns** — User may add points the current persona should raise

### When to Use It

**Good for:**
- Architecture decisions with multiple valid approaches
- Balancing user needs against technical constraints
- Exploring trade-offs (simplicity vs power, flexibility vs structure)
- Designing workflows that must serve both creative and technical goals
- Resolving tension between "what I want" and "what's maintainable"

**Not good for:**
- Simple implementation tasks with clear requirements
- Debugging or fixing specific issues
- Pure research/exploration questions
- Tasks where one perspective clearly dominates

### How to Initiate

**User prompt:**
> "Let's use the CS/Novelist dialogue to design X. Start as [Novelist/CS] and propose..."

Or:
> "Take the Novelist role and explain what you'd need for X. I'll correct, then you switch to CS."

### Example Exchange (From This Session)

**Topic:** Where should metadata editing happen?

**Claude (as Novelist):**
> "I want everything in MD frontmatter for easy discovery. When I'm in vim looking at an entry, I want to see scenes, events, arcs, people—all right there. Going to a separate file breaks my flow."

**User correction:**
> "I agree about flow, but MD frontmatter is getting cluttered. The prose file should stay clean. What about the wiki you mentioned?"

**Claude (as CS):**
> "The Novelist is right about flow, but wrong about location. MD frontmatter should be minimal—source metadata only. Full analysis belongs in a queryable system. Proposal: wiki as the editing interface, DB as queryable state, YAML as git-tracked backup. User edits in wiki, never touches SQL, MD stays clean."

**User correction:**
> "Yes, but wiki must be the source of truth. I don't want to edit YAMLs directly."

**Claude (as Novelist):**
> "Agreed. Wiki is my workspace. I edit there. The DB follows me, not the reverse. YAMLs are just exports for git history. But how do I know my wiki edits actually saved to the DB?"

**Claude (as CS):**
> "Sync happens on save or on-demand. Parser reads wiki, updates DB, exports YAML. Wiki is source of truth for metadata. If wiki and DB conflict, wiki wins—DB is rebuilt from wiki."

**User:** "Agreed. Move on."

### Key Dynamics

**The Novelist grounds the discussion in reality:**
- "But when I'm actually writing at 2am, will I really fill out this form?"
- "What happens when I don't know the chapter number yet?"
- "This feels like homework, not writing support."

**The CS enforces constraints:**
- "Without structure, you can't query 'which scenes are unused.'"
- "Freeform text can't be parsed reliably."
- "This creates two sources of truth—which one wins?"

**The user resolves by:**
- Picking one side: "The CS is right here."
- Synthesizing: "Keep the structure but make it optional."
- Redirecting: "This is over-engineering. Simplify."
- Adding context: "You're both missing that X already exists."

### Ending the Dialogue

The dialogue ends when:
1. **Agreement reached** — Both personas converge, user confirms
2. **User decides** — User picks a direction, discussion moves on
3. **Scope deferred** — "This is a Phase 14c problem, not 14a. Move on."
4. **Topic exhausted** — All aspects covered, document conclusions

### Post-Dialogue

After the dialogue:
1. **Document conclusions** — Capture every decision with rationale
2. **Note pending items** — What wasn't fully resolved
3. **Create actionable plan** — Convert discussion to implementation tasks

---

## The CS/Novelist Dialogue Conclusions

This section documents the key decisions reached through the pseudo-adversarial CS/Novelist dialogue.

### On MD Frontmatter

**Novelist wanted:** Rich metadata in MD frontmatter for easy discovery (scenes, events, arcs, threads, references, poems, tags, themes, motifs).

**CS countered:** MD frontmatter should be minimal—just source-text context. Analysis metadata belongs in YAML/DB, not cluttering the source files.

**Resolution:** MD frontmatter is minimal (date, word_count, reading_time, locations, people, narrated_dates). All analysis fields removed.

### On YAML vs Database

**Novelist wanted:** Everything accessible without SQL.

**CS countered:** YAML for version control, DB for queries, wiki for interface.

**Resolution:** YAML serves as git-tracked backup/export. DB is queryable state. User never touches SQL—wiki is the interface.

### On Wiki as Workspace

**Novelist concern:** "I don't know SQL. I don't want to create DB entities manually."

**CS response:** Wiki is the workspace. You edit wiki pages. The sync layer parses wiki and updates DB. DB exports to YAML for git.

**Resolution:** Wiki-first architecture. DB follows the wiki, not the other way around.

### On Manuscript Drafts

**Novelist concern:** "Drafting is non-linear. I don't start knowing this is Chapter 7."

**CS response:**
- Chapter numbers are nullable (assign when ready)
- Parts are optional (table exists but doesn't interfere)
- Fragments are first-class citizens (ManuscriptScene with chapter_id = null)
- Draft files are separate from metadata

**Resolution:**
- Prose drafts live in `data/manuscript/drafts/{chapter-title}.md`
- Chapter wiki pages are dashboards (metadata, source links, status)
- No forced structure until you're ready

### On Chapter Types

**Novelist concern:** "Some chapters are poems, some are text message conversations, some are lists."

**CS initial proposal:** `prose`, `poem`, `correspondence`, `vignette`, `fragment`, `epigraph`

**Novelist pushback:** "Too many types. Simplify."

**Resolution:** Three types only:
- `prose` — Full narrative chapters
- `vignette` — Middle ground: correspondence, drafted messages, lists, fragments, anything that's neither full prose nor pure poem
- `poem` — Verse

### On Source Tracking

**Novelist concern:** "Not every manuscript scene traces to a journal scene. What about gaps, inferred events, invented scenes?"

**CS response:** ManuscriptScene has `origin` enum:
- `journaled` — From a journal scene
- `inferred` — Reconstructed from gaps/references
- `invented` — Created for narrative purpose
- `composite` — Merged from multiple sources

**Resolution:** ManuscriptSource table links to heterogeneous sources (scene, entry, thread, or external note). A manuscript scene can have multiple sources or none.

### On Poems and References in Chapters

**Novelist concern:** "A prose chapter can include a poem. A poem can reference a book. These shouldn't be mutually exclusive."

**CS response:** Poems and references are M2M relationships on Chapter, not exclusive to chapter type.

**Resolution:**
- `Chapter.poems: M2M → Poem` (any chapter can include/reference poems)
- `ManuscriptReference` junction table for chapter ↔ ReferenceSource with mode and notes

### On the Narrator as Character

**Novelist question:** "In auto-fiction, is the narrator a Character entity?"

**CS response:** Yes. The narrator is a constructed version of the author, shaped for the page. She should be a Character with `is_narrator=True`, mapped to the author Person via PersonCharacterMap.

**Resolution:** Character table has `is_narrator: bool`. The narrator character maps to the real person (Sofia) with `contribution: primary`.

### On Invented Material Flag

**Novelist concern:** "Auto-fiction blurs the line. Having a boolean `has_invented_material` feels too black-and-white."

**CS response:** Agreed. Remove it.

**Resolution:** No `has_invented_material` field on Chapter. The `origin` field on ManuscriptScene provides enough granularity.

### On YAML Export Format

**Novelist question:** "Since YAML is machine-generated, should we use JSON instead?"

**CS response:** Stick with YAML because:
1. Git diffs are more readable
2. Multi-line strings (poems, descriptions) are cleaner
3. Debugging/inspection is easier
4. Consistency with project conventions

**Resolution:** YAML for all exports. Human-readability matters even for machine-generated files.

### On Directory Structure

**Novelist preference:** "Exports should be in metadata/ since that's where the DB lives."

**CS response:** Agreed. All metadata (DB + YAML exports) in `data/metadata/`.

**Resolution:**
- `data/metadata/palimpsest.db`
- `data/metadata/journal/{YYYY}/{YYYY-MM-DD}.yaml`
- `data/metadata/manuscript/index.yaml`, `chapters/`, `characters/`

### On Naming Conventions

**Novelist preference:** "Don't call it 'exports'. Don't use version suffixes like 'models_v2'."

**Resolution:**
- YAML directories are just `journal/` and `manuscript/` inside `metadata/`
- New models replace old models in `dev/database/models/` (no v2 suffix)
- Deprecated code is deleted, not versioned

---

## MD Frontmatter Specification

### Target Structure

```yaml
---
date: 2024-12-03
word_count: 749
reading_time: 2.9
locations:
  Montréal: [The Neuro, Home]
  México: [Coyoacán]
people: [Dr-Franck, Fabiola, Aliza, Sonny, Majo, Clara]
narrated_dates: [2024-11-29, 2024-11-30, 2024-12-01, 2024-12-02, 2024-12-03]
---
```

### Field Specifications

| Field | Type | Format | Required | Notes |
|-------|------|--------|----------|-------|
| `date` | scalar | `YYYY-MM-DD` | Yes | Entry date |
| `word_count` | int | numeric | Yes | Computed from body text |
| `reading_time` | float | minutes | Yes | Computed (word_count / ~250) |
| `locations` | dict | `{City: [loc1, loc2]}` | No | Nested by city; omit if empty |
| `people` | array | inline if <80 chars | No | No @ prefix; omit if empty |
| `narrated_dates` | array | `YYYY-MM-DD` list | No | Derived from scene dates; omit if same as entry date |

### Formatting Rules

- **Inline arrays** when <80 characters: `people: [Clara, Majo, Aliza]`
- **Block arrays** when ≥80 characters
- **Empty fields omitted entirely** (not `people: []`)
- **No @ prefix** on people names
- **Locations nested by city** to support multi-city entries

### Fields REMOVED from MD (migrate to wiki/DB)

These fields currently exist in some MD frontmatter but will be removed:

| Field | Migration Action |
|-------|------------------|
| `scenes` | Already in YAML analysis → wiki/DB |
| `events` | Already in YAML analysis → wiki/DB |
| `arcs` | Already in YAML analysis → wiki/DB |
| `threads` | Already in YAML analysis → wiki/DB |
| `tags` | Already in YAML analysis → wiki/DB |
| `themes` | Already in YAML analysis → wiki/DB |
| `motifs` | Already in YAML analysis → wiki/DB |
| `references` | Already in YAML analysis → wiki/DB |
| `poems` | Already in YAML analysis → wiki/DB |
| `epigraph` | Remains in body text after frontmatter |
| `epigraph_attribution` | Remains in body text |
| `notes` | Extract to `data/legacy/notes_archive.yaml`, then delete |
| `city` | Absorbed into `locations` dict |

### Validation Rules

1. `date` must be valid ISO date
2. `word_count` must be positive integer
3. `reading_time` must be positive float
4. `people` in MD must be superset of people in analysis (MD ≥ analysis)
5. After migration: `people` in MD must exactly match analysis

---

## Database Schema - Journal Domain

### Core Entities

```python
class Entry(Base):
    """
    Journal entry - the source text.

    One Entry per journal day. Links to the MD file containing prose.
    All analysis entities (scenes, events, etc.) belong to an Entry.
    """
    __tablename__ = "entries"

    id: int                          # Primary key
    date: date                       # Unique, indexed - the entry date
    file_path: str                   # Unique - relative path to MD file
    file_hash: str                   # SHA256 of file content for change detection
    word_count: int                  # From MD frontmatter
    reading_time: float              # From MD frontmatter (minutes)
    created_at: datetime             # Record creation timestamp
    updated_at: datetime             # Record update timestamp

    # Relationships
    cities: List[City]               # M2M via entry_cities
    locations: List[Location]        # M2M via entry_locations
    people: List[Person]             # M2M via entry_people
    narrated_dates: List[NarratedDate]  # O2M (dates belong to entry)
    scenes: List[Scene]              # O2M (scenes belong to entry)
    events: List[Event]              # O2M (events belong to entry)
    arcs: List[Arc]                  # M2M via entry_arcs
    threads: List[Thread]            # O2M (threads belong to entry)
    references: List[Reference]      # O2M (references belong to entry)
    poem_versions: List[PoemVersion] # O2M (versions belong to entry)
    tags: List[Tag]                  # M2M via entry_tags
    themes: List[Theme]              # M2M via entry_themes
    motif_instances: List[MotifInstance]  # O2M (instances belong to entry)

    # Manuscript relationship
    manuscript_sources: List[ManuscriptSource]  # Entries that feed manuscript scenes


class City(Base):
    """
    City entity for geographic organization.

    Cities contain locations. Entries can span multiple cities.
    """
    __tablename__ = "cities"

    id: int                          # Primary key
    name: str                        # Unique - city name (e.g., "Montréal", "México")
    country: str                     # Nullable - country name

    # Relationships
    locations: List[Location]        # O2M (locations belong to city)
    entries: List[Entry]             # M2M via entry_cities


class Location(Base):
    """
    Specific location within a city.

    Examples: "The Neuro", "Home", "Cinéma Moderne", "Coyoacán"
    """
    __tablename__ = "locations"

    id: int                          # Primary key
    name: str                        # Location name
    city_id: int                     # FK → City

    # Unique constraint on (name, city_id)

    # Relationships
    city: City                       # M2O
    entries: List[Entry]             # M2M via entry_locations
    scenes: List[Scene]              # M2M via scene_locations
    threads: List[Thread]            # M2M via thread_locations


class Person(Base):
    """
    Real person appearing in the journal.

    People have aliases (short identifiers used in frontmatter/scenes),
    a name, and optionally a lastname. Aliases are stored in separate table.
    """
    __tablename__ = "people"

    id: int                          # Primary key
    name: str                        # Indexed - first name (e.g., "María José")
    lastname: str                    # Nullable - last name (e.g., "Castro Lopez")
    disambiguator: str               # Nullable - context tag for same-name people
    relation_type: RelationType      # Nullable - enum (family, friend, romantic, etc.)

    # Relationships
    aliases: List[PersonAlias]       # O2M (aliases belong to person)
    entries: List[Entry]             # M2M via entry_people
    scenes: List[Scene]              # M2M via scene_people
    threads: List[Thread]            # M2M via thread_people
    character_mappings: List[PersonCharacterMap]  # O2M (maps to characters)


class PersonAlias(Base):
    """
    An alias for a person.

    Stores alternative names/nicknames for a person, enabling lookup
    by any known name.
    """
    __tablename__ = "person_aliases"

    id: int                          # Primary key
    person_id: int                   # FK → Person
    alias: str                       # Unique - the alias string

    # Relationships
    person: Person                   # M2O


class NarratedDate(Base):
    """
    A date narrated within an entry.

    Entries often narrate events from multiple days. This tracks which
    dates are covered by an entry's scenes.
    """
    __tablename__ = "narrated_dates"

    id: int                          # Primary key
    date: date                       # The narrated date
    entry_id: int                    # FK → Entry

    # Relationships
    entry: Entry                     # M2O
```

### Analysis Entities

```python
class Scene(Base):
    """
    Granular narrative moment within an entry.

    Scenes are the atomic units of narrative. They have a name, description,
    can span multiple dates, and link to people and locations present.
    """
    __tablename__ = "scenes"

    id: int                          # Primary key
    name: str                        # Scene name (unique per entry)
    description: str                 # Punchy, documentary description
    entry_id: int                    # FK → Entry

    # Unique constraint on (name, entry_id)

    # Relationships
    entry: Entry                     # M2O
    dates: List[SceneDate]           # O2M (dates belong to scene)
    people: List[Person]             # M2M via scene_people
    locations: List[Location]        # M2M via scene_locations
    events: List[Event]              # M2M via event_scenes (scenes belong to events)
    manuscript_sources: List[ManuscriptSource]  # Scenes that feed manuscript


class SceneDate(Base):
    """
    A date associated with a scene.

    Scenes can span multiple dates (e.g., a scene about "that weekend").
    """
    __tablename__ = "scene_dates"

    id: int                          # Primary key
    date: date                       # The date
    scene_id: int                    # FK → Scene

    # Relationships
    scene: Scene                     # M2O


class Event(Base):
    """
    Groups scenes within an entry.

    Events are higher-level groupings of scenes. An event like "The Cinema Date"
    might contain scenes "Waiting Outside", "The Film", "The Walk Home".
    """
    __tablename__ = "events"

    id: int                          # Primary key
    name: str                        # Event name (unique per entry)
    entry_id: int                    # FK → Entry

    # Unique constraint on (name, entry_id)

    # Relationships
    entry: Entry                     # M2O
    scenes: List[Scene]              # M2M via event_scenes


class Arc(Base):
    """
    Story arc spanning multiple entries.

    Arcs track narrative threads across the journal. Examples:
    "The Long Wanting", "The March Crisis", "The Chemical Refuge"
    """
    __tablename__ = "arcs"

    id: int                          # Primary key
    name: str                        # Unique - arc name
    description: str                 # Nullable - arc description

    # Relationships
    entries: List[Entry]             # M2M via entry_arcs
    chapters: List[Chapter]          # M2M via chapter_arcs (manuscript)


class Thread(Base):
    """
    Temporal echo/connection between moments.

    Threads link a moment in the current entry to a moment elsewhere in time.
    The 'from' date is near the entry, the 'to' date is distant (past or future).
    The 'content' describes the CONNECTION between both moments.
    """
    __tablename__ = "threads"

    id: int                          # Primary key
    name: str                        # Thread name (unique identifier)
    from_date: date                  # Proximate date (near the entry)
    to_date: str                     # Distant date (YYYY, YYYY-MM, or YYYY-MM-DD)
    referenced_entry_date: date      # Nullable - entry that narrates the distant moment
    content: str                     # Description of the CONNECTION
    entry_id: int                    # FK → Entry (where thread is defined)

    # Relationships
    entry: Entry                     # M2O
    people: List[Person]             # M2M via thread_people
    locations: List[Location]        # M2M via thread_locations
    manuscript_sources: List[ManuscriptSource]  # Threads that feed manuscript
```

### Creative Entities

```python
class ReferenceSource(Base):
    """
    External work referenced in the journal.

    Books, films, songs, poems, articles, podcasts, etc. that are
    mentioned or quoted in journal entries.
    """
    __tablename__ = "reference_sources"

    id: int                          # Primary key
    title: str                       # Unique - work title
    author: str                      # Nullable - creator name
    type: ReferenceType              # Enum: book, film, song, poem, article, podcast, etc.
    url: str                         # Nullable - link to work

    # Relationships
    references: List[Reference]      # O2M (instances in journal entries)
    manuscript_references: List[ManuscriptReference]  # O2M (uses in manuscript)


class Reference(Base):
    """
    A specific reference instance in a journal entry.

    Tracks how a ReferenceSource is used in a particular entry:
    direct quote, paraphrase, thematic allusion, etc.
    """
    __tablename__ = "references"

    id: int                          # Primary key
    entry_id: int                    # FK → Entry
    source_id: int                   # FK → ReferenceSource
    content: str                     # Nullable - the quote if direct
    description: str                 # Nullable - how it's used
    mode: ReferenceMode              # Enum: direct, indirect, paraphrase, visual

    # Relationships
    entry: Entry                     # M2O
    source: ReferenceSource          # M2O


class Poem(Base):
    """
    Poem entity that can have versions across entries.

    A poem may evolve over time. Each version appears in a specific entry.
    The Poem entity is the canonical "work", PoemVersions are instances.
    """
    __tablename__ = "poems"

    id: int                          # Primary key
    title: str                       # Poem title

    # Relationships
    versions: List[PoemVersion]      # O2M (versions of this poem)
    chapters: List[Chapter]          # M2M via chapter_poems (manuscript uses)


class PoemVersion(Base):
    """
    Specific version of a poem in an entry.

    Each time a poem appears (or is revised) in the journal,
    that's a PoemVersion linked to the entry.
    """
    __tablename__ = "poem_versions"

    id: int                          # Primary key
    content: str                     # The poem text
    poem_id: int                     # FK → Poem
    entry_id: int                    # FK → Entry

    # Relationships
    poem: Poem                       # M2O
    entry: Entry                     # M2O
```

### Metadata Entities

```python
class Tag(Base):
    """
    Freeform tag for categorizing entries.
    """
    __tablename__ = "tags"

    id: int                          # Primary key
    name: str                        # Unique - tag name

    # Relationships
    entries: List[Entry]             # M2M via entry_tags


class Theme(Base):
    """
    Thematic element appearing in entries.

    Themes are more abstract than tags. Examples:
    "The Spiral", "Self-Medication", "Cyclical Behavior"
    """
    __tablename__ = "themes"

    id: int                          # Primary key
    name: str                        # Unique - theme name

    # Relationships
    entries: List[Entry]             # M2M via entry_themes


class Motif(Base):
    """
    Controlled vocabulary motif.

    There are exactly 26 motifs. Each has a canonical name.
    MotifInstances track how they appear in specific entries.
    """
    __tablename__ = "motifs"

    id: int                          # Primary key
    name: str                        # Unique - motif name (e.g., "THE BOTTLE")

    # Relationships
    instances: List[MotifInstance]   # O2M (appearances in entries)


class MotifInstance(Base):
    """
    How a motif appears in a specific entry.

    Each instance has an entry-specific description explaining
    how the motif manifests in that particular narrative.
    """
    __tablename__ = "motif_instances"

    id: int                          # Primary key
    motif_id: int                    # FK → Motif
    entry_id: int                    # FK → Entry
    description: str                 # Entry-specific description

    # Relationships
    motif: Motif                     # M2O
    entry: Entry                     # M2O
```

### Association Tables (Journal Domain)

```python
# Entry associations
entry_cities = Table(
    "entry_cities",
    Column("entry_id", FK("entries.id")),
    Column("city_id", FK("cities.id")),
)

entry_locations = Table(
    "entry_locations",
    Column("entry_id", FK("entries.id")),
    Column("location_id", FK("locations.id")),
)

entry_people = Table(
    "entry_people",
    Column("entry_id", FK("entries.id")),
    Column("person_id", FK("people.id")),
)

entry_arcs = Table(
    "entry_arcs",
    Column("entry_id", FK("entries.id")),
    Column("arc_id", FK("arcs.id")),
)

entry_tags = Table(
    "entry_tags",
    Column("entry_id", FK("entries.id")),
    Column("tag_id", FK("tags.id")),
)

entry_themes = Table(
    "entry_themes",
    Column("entry_id", FK("entries.id")),
    Column("theme_id", FK("themes.id")),
)

# Scene associations
scene_people = Table(
    "scene_people",
    Column("scene_id", FK("scenes.id")),
    Column("person_id", FK("people.id")),
)

scene_locations = Table(
    "scene_locations",
    Column("scene_id", FK("scenes.id")),
    Column("location_id", FK("locations.id")),
)

# Event associations
event_scenes = Table(
    "event_scenes",
    Column("event_id", FK("events.id")),
    Column("scene_id", FK("scenes.id")),
)

# Thread associations
thread_people = Table(
    "thread_people",
    Column("thread_id", FK("threads.id")),
    Column("person_id", FK("people.id")),
)

thread_locations = Table(
    "thread_locations",
    Column("thread_id", FK("threads.id")),
    Column("location_id", FK("locations.id")),
)
```

---

## Database Schema - Manuscript Domain

### Structure Entities

```python
class Part(Base):
    """
    Book section (optional).

    Parts divide the manuscript into major sections.
    Example: "Part I: Before", "Part II: During", "Part III: After"

    Parts are entirely optional. Chapters can exist without parts.
    """
    __tablename__ = "parts"

    id: int                          # Primary key
    number: int                      # Nullable - part number (assign when ready)
    title: str                       # Nullable - part title

    # Relationships
    chapters: List[Chapter]          # O2M (chapters in this part)


class Chapter(Base):
    """
    Any discrete unit of the manuscript.

    Chapters are not just prose—they can be poems, vignettes (correspondence,
    drafted messages, lists), or prose sections. The type field distinguishes.

    Chapters have nullable number/part until structure is finalized.
    """
    __tablename__ = "chapters"

    id: int                          # Primary key
    title: str                       # Chapter title (used as filename slug)
    number: int                      # Nullable - chapter number (assign when ready)
    part_id: int                     # Nullable - FK → Part

    type: ChapterType                # Enum: prose, vignette, poem
    status: ChapterStatus            # Enum: draft, revised, final

    content: str                     # Nullable - inline content for short pieces
    draft_path: str                  # Nullable - path to .md file for longer chapters

    # Relationships
    part: Part                       # Nullable M2O
    poems: List[Poem]                # M2M via chapter_poems (poems used in chapter)
    references: List[ManuscriptReference]  # O2M (references used)
    characters: List[Character]      # M2M via chapter_characters
    arcs: List[Arc]                  # M2M via chapter_arcs
    scenes: List[ManuscriptScene]    # O2M (manuscript scenes in chapter)
```

**Chapter Types Explained:**

| Type | Description | Examples |
|------|-------------|----------|
| `prose` | Full narrative chapters | Standard book chapters with prose narrative |
| `vignette` | Middle ground: non-standard format | Text message conversations, drafted messages, lists ("100 Questions"), fragments, correspondence |
| `poem` | Pure verse | Standalone poems as chapters |

### Character Entities

```python
class Character(Base):
    """
    Fictional character in the manuscript.

    Characters are the manuscript's representation of real people.
    A character might be based on one person (primary), composite
    of several people, or inspired loosely.

    The narrator is a special character with is_narrator=True.
    """
    __tablename__ = "characters"

    id: int                          # Primary key
    name: str                        # Character name (e.g., "Elise")
    description: str                 # Nullable - physical, personality notes
    role: str                        # Nullable - "protagonist", "love interest", etc.
    is_narrator: bool                # Default False - True for the narrator character

    # Relationships
    person_mappings: List[PersonCharacterMap]  # O2M (who they're based on)
    chapters: List[Chapter]          # M2M via chapter_characters


class PersonCharacterMap(Base):
    """
    Maps real person to fictional character.

    This is a M2M relationship with metadata. A character can be based on
    multiple people (composite), and a person can inspire multiple characters.

    The contribution field indicates the nature of the mapping.
    """
    __tablename__ = "person_character_maps"

    id: int                          # Primary key
    person_id: int                   # FK → Person
    character_id: int                # FK → Character
    contribution: ContributionType   # Enum: primary, composite, inspiration
    notes: str                       # Nullable - "Clara's words, Vero's physicality"

    # Relationships
    person: Person                   # M2O
    character: Character             # M2O
```

**Contribution Types Explained:**

| Type | Description | Example |
|------|-------------|---------|
| `primary` | Main basis for character | Clara → Elise (Elise is basically Clara) |
| `composite` | One of several people merged | Majo + Alda + Aliza → "The Cavalry" |
| `inspiration` | Loose influence | Vero → Elise (borrowed physical description) |

### Source Tracking Entities

```python
class ManuscriptScene(Base):
    """
    A narrative unit in the manuscript.

    ManuscriptScenes are the building blocks of chapters. They can:
    - Trace to journal scenes (journaled)
    - Be reconstructed from gaps (inferred)
    - Be purely invented (invented)
    - Combine multiple sources (composite)

    Scenes with chapter_id=None are unassigned fragments.
    """
    __tablename__ = "manuscript_scenes"

    id: int                          # Primary key
    name: str                        # Scene name
    description: str                 # Nullable - scene description
    chapter_id: int                  # Nullable - FK → Chapter (None = fragment)

    origin: SceneOrigin              # Enum: journaled, inferred, invented, composite
    status: SceneStatus              # Enum: fragment, draft, included, cut
    notes: str                       # Nullable - adaptation notes

    # Relationships
    chapter: Chapter                 # Nullable M2O
    sources: List[ManuscriptSource]  # O2M (what this scene draws from)


class ManuscriptSource(Base):
    """
    Links manuscript scene to source material.

    Sources are heterogeneous—a manuscript scene can draw from:
    - Journal scenes
    - Journal entries (without specific scene)
    - Threads (temporal echoes)
    - External material (texts, screenshots, memories)

    Only one of scene_id/entry_id/thread_id/external_note is populated.
    """
    __tablename__ = "manuscript_sources"

    id: int                          # Primary key
    manuscript_scene_id: int         # FK → ManuscriptScene

    source_type: SourceType          # Enum: scene, entry, thread, external

    # Nullable FKs - only one populated based on source_type
    scene_id: int                    # Nullable - FK → Scene
    entry_id: int                    # Nullable - FK → Entry
    thread_id: int                   # Nullable - FK → Thread
    external_note: str               # Nullable - description of external source

    notes: str                       # Nullable - how this source is used

    # Relationships
    manuscript_scene: ManuscriptScene  # M2O
    scene: Scene                     # Nullable M2O
    entry: Entry                     # Nullable M2O
    thread: Thread                   # Nullable M2O


class ManuscriptReference(Base):
    """
    How a chapter uses a referenced work.

    Junction table between Chapter and ReferenceSource with metadata
    about how the reference is used (mode, quote, notes).
    """
    __tablename__ = "manuscript_references"

    id: int                          # Primary key
    chapter_id: int                  # FK → Chapter
    source_id: int                   # FK → ReferenceSource

    mode: ReferenceMode              # Enum: direct, indirect, paraphrase, visual, thematic
    content: str                     # Nullable - quote if direct
    notes: str                       # Nullable - how it's used

    # Relationships
    chapter: Chapter                 # M2O
    source: ReferenceSource          # M2O
```

### Association Tables (Manuscript Domain)

```python
# Chapter associations
chapter_poems = Table(
    "chapter_poems",
    Column("chapter_id", FK("chapters.id")),
    Column("poem_id", FK("poems.id")),
)

chapter_characters = Table(
    "chapter_characters",
    Column("chapter_id", FK("chapters.id")),
    Column("character_id", FK("characters.id")),
)

chapter_arcs = Table(
    "chapter_arcs",
    Column("chapter_id", FK("chapters.id")),
    Column("arc_id", FK("arcs.id")),
)
```

### Relationship Diagram

```
JOURNAL DOMAIN                           MANUSCRIPT DOMAIN
══════════════════════════════════════════════════════════════════════════════

Entry ◄───────────────────────────────── ManuscriptSource (source_type: entry)
  │
  ├── Scene ◄────────────────────────── ManuscriptSource (source_type: scene)
  │     │
  │     └── people, locations, dates
  │
  ├── Thread ◄───────────────────────── ManuscriptSource (source_type: thread)
  │
  ├── Reference
  │     └── ReferenceSource ◄────────── ManuscriptReference
  │
  ├── PoemVersion
  │     └── Poem ◄───────────────────── Chapter.poems (M2M)
  │
  └── Arc ◄──────────────────────────── Chapter.arcs (M2M)

                                        ManuscriptScene
                                              │
                                              ▼
Part (opt) ──► Chapter ──► ManuscriptScene ──► ManuscriptSource
                  │
                  ├── ManuscriptReference ──► ReferenceSource
                  ├── M2M ──► Poem
                  ├── M2M ──► Character ──► PersonCharacterMap ──► Person
                  └── M2M ──► Arc
```

---

## YAML Export Specifications

YAML exports are machine-generated from the database for git version control. They are human-readable (for diffs and debugging) but not manually edited.

### Journal YAML Export

**Location:** `data/metadata/journal/{YYYY}/{YYYY-MM-DD}.yaml`

```yaml
# Exported from wiki/DB — do not edit manually
# Entry: 2024-12-03

date: '2024-12-03'

# Manuscript curation metadata
summary: "Sofia increases her antidepressant dose after a difficult week..."
rating: 4.5
rating_justification: "Raw vulnerability, Chekhov's gun with the raki bottle..."

# Narrative structure
arcs:
  - The Long Wanting
  - The March Crisis
  - The Chemical Refuge

# People with expanded details
people:
  - alias: Dr-Franck
    name: Robert
    lastname: Franck
  - alias: null
    name: Fabiola
    lastname: null
  - alias: Majo
    name: María José
    lastname: Castro Lopez
  - alias: Clara
    name: Clara
    lastname: null

# Scenes
scenes:
  - name: Psychiatric Session
    description: "Sofia meets with Dr. Franck to discuss increasing her dose"
    date: '2024-12-03'
    people: [Dr-Franck]
    locations: [Home]

  - name: The Two Sips
    description: "Sofia drinks raki from the fridge, a loaded gesture"
    date: '2024-12-03'
    people: []
    locations: [Home]

  - name: Waiting for the Text
    description: "Sofia checks her phone repeatedly, hoping for Clara"
    date: '2024-12-03'
    people: [Clara]
    locations: [Home]

# Events (group scenes)
events:
  - name: The Raki Afternoon
    scenes: [The Two Sips, Waiting for the Text]

  - name: The Dose Increase
    scenes: [Psychiatric Session]

# Threads (temporal echoes)
threads:
  - name: Chekhov's Raki
    from: '2024-12-03'
    to: '2024-12-08'
    entry: '2024-12-08'
    content: "The two sips foreshadow the full relapse five days later"
    people: []
    locations: [Home]

# References (intertextuality)
references:
  - source:
      title: "In the Mood for Love"
      author: "Wong Kar-wai"
      type: film
    mode: thematic
    description: "The mood of missed connections and unfulfilled longing"

# Poems
poems:
  - title: Muse
    content: |
      I miss the idea I built of you.
      The one that answered back.

# Metadata
tags: [Depression, Medication, Alcohol, Self-Sabotage]
themes: [The Spiral, Self-Medication, Cyclical Behavior]

motifs:
  - name: THE BOTTLE
    description: "The raki as temptation and foreshadowing"
  - name: THE SPIRAL
    description: "Descent into depressive episode"
  - name: THE WAIT
    description: "Compulsive phone checking"
```

### Manuscript Index YAML

**Location:** `data/metadata/manuscript/index.yaml`

```yaml
# Exported from wiki/DB — do not edit manually
# Manuscript: Palimpsest

title: "Palimpsest"

parts:
  - number: 1
    title: "Before"
    chapters:
      - the-long-wanting
      - poem-muse
      - the-cavalry-arrives
      - the-third-date

  - number: 2
    title: "During"
    chapters:
      - december-texts
      - the-fourth-date
      - christmas-apart
      - new-years-message

  - number: 3
    title: "After"
    chapters:
      - the-return
      - the-ending

# Chapters not yet assigned to parts
unassigned:
  - fragment-metro-crying
  - untitled-draft
  - the-hundred-questions
```

### Manuscript Chapter YAML

**Location:** `data/metadata/manuscript/chapters/{chapter-title}.yaml`

```yaml
# Exported from wiki/DB — do not edit manually
# Chapter: The Long Wanting

title: "The Long Wanting"
type: prose
status: draft
number: 1
part: 1

# What this chapter uses
characters:
  - elise
  - the-cavalry
  - narrator

arcs:
  - The Long Wanting
  - The Dating Carousel

poems:
  - Muse

references:
  - source: "In the Mood for Love"
    mode: thematic
    notes: "The mood of missed connections pervades the prose"

# Manuscript scenes in this chapter
scenes:
  - name: The Dumpling Date
    origin: journaled
    status: included
    description: "Their first real date, at the dumpling place on St-Laurent"
    sources:
      - type: scene
        ref: "2024-11-09/the-dumpling-date"

  - name: December Mood
    origin: journaled
    status: included
    description: "The atmospheric weight of waiting"
    sources:
      - type: entry
        ref: "2024-12-15"
        notes: "General mood, not a specific scene"

  - name: The Invented Goodbye
    origin: invented
    status: included
    description: "A composite goodbye that captures many small moments"
    notes: "Drawn from multiple fragmentary memories"
```

### Manuscript Character YAML

**Location:** `data/metadata/manuscript/characters/{character-name}.yaml`

```yaml
# Exported from wiki/DB — do not edit manually
# Character: Elise

name: Elise
role: love interest
is_narrator: false
description: "Withdrawn, artistic, emotionally unavailable. Dark hair, quiet voice."

based_on:
  - person: Clara
    contribution: primary
    notes: null

  - person: Vero
    contribution: inspiration
    notes: "Physical description borrowed—the way she holds a cigarette"
```

---

## Directory Structure

### Complete Structure

```
palimpsest/
├── .palimpsest                          # Project marker (nvim auto-detection)
├── .gitignore
├── pyproject.toml
├── CLAUDE.md                            # Claude Code instructions
├── PLAN.md                              # THIS FILE - Phase 14 planning document
│
├── dev/                                 # Python codebase
│   ├── __init__.py
│   │
│   ├── core/                            # Core utilities
│   │   ├── __init__.py
│   │   ├── paths.py                     # Central path configuration (SINGLE SOURCE)
│   │   ├── validators.py                # Data validation utilities
│   │   ├── exceptions.py                # Custom exceptions
│   │   └── logging.py                   # Logging configuration
│   │
│   ├── database/                        # Database layer
│   │   ├── __init__.py
│   │   ├── models/                      # SQLAlchemy models (Phase 14 schema)
│   │   │   ├── __init__.py
│   │   │   ├── base.py                  # Base model class
│   │   │   ├── core.py                  # Entry, NarratedDate, SchemaInfo
│   │   │   ├── geography.py             # City, Location
│   │   │   ├── entities.py              # Person, PersonAlias, Tag, Theme
│   │   │   ├── analysis.py              # Scene, SceneDate, Event, Arc, Thread
│   │   │   ├── creative.py              # Reference, ReferenceSource, Poem, PoemVersion
│   │   │   ├── metadata.py              # Motif, MotifInstance
│   │   │   ├── manuscript.py            # Part, Chapter, Character, ManuscriptScene, etc.
│   │   │   └── enums.py                 # All enums (ReferenceType, ChapterType, etc.)
│   │   ├── manager.py                   # DatabaseManager class
│   │   └── decorators.py                # Database operation decorators
│   │
│   ├── wiki/                            # Wiki system
│   │   ├── __init__.py
│   │   ├── exporter.py                  # DB → Wiki (generates wiki pages)
│   │   ├── parser.py                    # Wiki → DB (NEW: parses wiki edits)
│   │   ├── renderer.py                  # Jinja2 template rendering
│   │   ├── configs.py                   # Entity export configurations
│   │   ├── filters.py                   # Custom Jinja2 filters
│   │   └── templates/                   # Jinja2 templates (27+ files)
│   │       ├── entry.md.j2
│   │       ├── person.md.j2
│   │       ├── scene.md.j2
│   │       ├── chapter.md.j2
│   │       ├── character.md.j2
│   │       └── ...
│   │
│   ├── pipeline/                        # Data pipelines
│   │   ├── __init__.py
│   │   ├── cli.py                       # Pipeline CLI commands
│   │   ├── jumpstart.py                 # NEW: narrative_analysis → DB migration
│   │   ├── export_yaml.py               # NEW: DB → YAML export
│   │   └── validate.py                  # Validation pipelines
│   │
│   ├── lua/palimpsest/                  # NVim pseudo-package
│   │   ├── init.lua                     # Entry point
│   │   ├── config.lua                   # Path configuration
│   │   ├── vimwiki.lua                  # VimWiki registration
│   │   ├── commands.lua                 # Custom :Palimpsest commands
│   │   ├── keymaps.lua                  # Keybindings
│   │   ├── autocmds.lua                 # Auto-commands
│   │   ├── validators.lua               # YAML/frontmatter validation
│   │   ├── fzf.lua                      # FZF integration
│   │   └── templates.lua                # Template expansion
│   │
│   ├── migrations/                      # Alembic migrations
│   │   ├── versions/
│   │   └── env.py
│   │
│   └── bin/                             # Utility scripts
│       ├── extract_entities.py          # Entity extraction from YAMLs
│       ├── validate_curation.py         # Validate curated entity files
│       └── consolidate_curation.py      # Finalize curation
│
├── data/                                # Data directory (git submodule)
│   ├── metadata/                        # All metadata
│   │   ├── palimpsest.db                # SQLite database
│   │   ├── journal/                     # Journal YAML exports
│   │   │   └── {YYYY}/
│   │   │       └── {YYYY-MM-DD}.yaml
│   │   ├── manuscript/                  # Manuscript YAML exports
│   │   │   ├── index.yaml
│   │   │   ├── chapters/
│   │   │   │   └── {chapter-title}.yaml
│   │   │   └── characters/
│   │   │       └── {character-name}.yaml
│   │   ├── people/                      # Per-entity people files (NEW)
│   │   │   └── {name-lastname}.yaml
│   │   └── locations/                   # Per-city location files (NEW)
│   │       └── {city}/
│   │           └── {location}.yaml
│   │
│   ├── journal/                         # Journal content
│   │   ├── content/
│   │   │   └── md/                      # Ground truth MD files
│   │   │       └── {YYYY}/
│   │   │           └── {YYYY-MM-DD}.md
│   │   └── inbox/                       # Incoming files
│   │
│   ├── wiki/                            # VimWiki output
│   │   ├── index.md                     # Main index
│   │   ├── entries/                     # Journal entry pages
│   │   │   └── {YYYY}/
│   │   │       └── {YYYY-MM-DD}.md
│   │   ├── people/                      # Person pages
│   │   │   └── {person-name}.md
│   │   ├── locations/                   # Location pages
│   │   ├── events/                      # Event pages
│   │   ├── narrative/                   # Arcs, threads
│   │   ├── manuscript/                  # Manuscript section
│   │   │   ├── chapters/
│   │   │   └── characters/
│   │   ├── poems/                       # Poem pages
│   │   ├── references/                  # Reference pages
│   │   ├── tags/                        # Tag indexes
│   │   ├── themes/                      # Theme indexes
│   │   ├── log/                         # VimWiki diary
│   │   └── ...
│   │
│   ├── manuscript/                      # Manuscript drafts
│   │   └── drafts/
│   │       └── {chapter-title}.md       # Prose draft files
│   │
│   ├── curation/                        # Entity curation files (temporary)
│   │   ├── 2021_people_curation.yaml
│   │   ├── 2021_locations_curation.yaml
│   │   └── ...
│   │
│   ├── legacy/                          # Archived data
│   │   └── notes_archive.yaml           # Extracted notes from MD frontmatter
│   │
│   ├── narrative_analysis/              # DEPRECATED (delete after migration)
│   │   └── {YYYY}/
│   │       └── {YYYY-MM-DD}_analysis.yaml
│   │
│   ├── logs/                            # Pipeline logs
│   │   ├── jumpstart/
│   │   │   ├── import_report_YYYYMMDD_HHMMSS.json
│   │   │   └── failed_imports.json
│   │   └── archive/
│   │
│   └── docs/                            # Data documentation
│       ├── md_frontmatter_spec.md
│       ├── yaml_export_spec.md
│       └── data_architecture.md
│
├── backups/                             # Backup directory
│   └── database/
│       ├── daily/
│       └── weekly/
│
├── logs/                                # Application logs
│
└── tests/                               # Test suite
    ├── unit/
    └── integration/
```

### Path Configuration

All paths are defined in `dev/core/paths.py`:

```python
from pathlib import Path

# Root detection
ROOT = Path(__file__).parent.parent.parent  # palimpsest/

# Main directories
DEV_DIR = ROOT / "dev"
DATA_DIR = ROOT / "data"

# Database
METADATA_DIR = DATA_DIR / "metadata"
DB_PATH = METADATA_DIR / "palimpsest.db"

# YAML exports
JOURNAL_YAML_DIR = METADATA_DIR / "journal"
MANUSCRIPT_YAML_DIR = METADATA_DIR / "manuscript"

# Entity files (NEW)
PEOPLE_DIR = METADATA_DIR / "people"
LOCATIONS_DIR = METADATA_DIR / "locations"

# Journal
JOURNAL_DIR = DATA_DIR / "journal"
JOURNAL_MD_DIR = JOURNAL_DIR / "content" / "md"

# Wiki
WIKI_DIR = DATA_DIR / "wiki"
WIKI_ENTRIES_DIR = WIKI_DIR / "entries"
WIKI_MANUSCRIPT_DIR = WIKI_DIR / "manuscript"

# Manuscript
MANUSCRIPT_DIR = DATA_DIR / "manuscript"
MANUSCRIPT_DRAFTS_DIR = MANUSCRIPT_DIR / "drafts"

# Legacy (for migration)
NARRATIVE_ANALYSIS_DIR = DATA_DIR / "narrative_analysis"
LEGACY_DIR = DATA_DIR / "legacy"

# Curation
CURATION_DIR = DATA_DIR / "curation"

# Logs
LOGS_DIR = DATA_DIR / "logs"
JUMPSTART_LOGS_DIR = LOGS_DIR / "jumpstart"
```

---

## Existing Infrastructure

This section documents what already exists and will be leveraged.

### Database Infrastructure

**Location:** `dev/database/`

- `manager.py` — DatabaseManager class with ORM operations
- `decorators.py` — `@handle_db_errors`, `DatabaseOperation` context manager
- `models/` — Current models (Phase 14 schema implemented)

**Database file:** `data/metadata/palimpsest.db` (SQLite 3.x)

### Wiki Infrastructure

**Location:** `dev/wiki/`

- `exporter.py` — Main export engine, exports DB → wiki markdown
- `configs.py` — Entity configurations (folder, template, query per entity type)
- `renderer.py` — Jinja2 template rendering
- `filters.py` — Custom Jinja2 filters
- `templates/` — 27+ Jinja2 templates

**Wiki output:** `data/wiki/`

### NVim Integration

**Location:** `dev/lua/palimpsest/`

| File | Purpose |
|------|---------|
| `init.lua` | Entry point, loads all modules if inside palimpsest project |
| `config.lua` | Path configuration, project root detection |
| `vimwiki.lua` | VimWiki instance registration |
| `commands.lua` | Custom `:Palimpsest*` commands |
| `keymaps.lua` | Keybindings for palimpsest workflows |
| `autocmds.lua` | Auto-commands (formatting, validation) |
| `validators.lua` | YAML/frontmatter validation |
| `fzf.lua` | FZF integration for file browsing |
| `templates.lua` | Template expansion helpers |

**Project detection:** Uses `.palimpsest` marker file at project root.

**VimWiki configuration:**
```lua
M.paths = {
    root = root,
    wiki = root .. "/data/wiki",
    log = root .. "/data/wiki/log",
    journal = root .. "/data/journal/content/md",
    templates = root .. "/templates/wiki",
}

M.vimwiki = {
    name = "Palimpsest",
    syntax = "markdown",
    ext = ".md",
    links_space_char = "_",
    diary_rel_path = "log",
}
```

### Pipeline Infrastructure

**Location:** `dev/pipeline/`

- `cli.py` — Pipeline CLI commands
- Existing import/export scripts (to be replaced/extended)

### Backup Infrastructure

**Location:** `backups/database/`

- `daily/` — Daily automatic backups
- `weekly/` — Weekly backups

---

## Implementation Phases

### Phase 14a: DB Schema + Source Files ✓ COMPLETE

**Goal:** Replace database models with new schema, prepare source file infrastructure.

**Status:** Complete

### Phase 14b: Jumpstart ← CURRENT

**Goal:** Clean up messy current files into consistent format matching the future MD→DB pipeline.

**Jumpstart is file cleanup only. No DB operations.**

**Current State (verified 2025-01-30):**

| Data Type | Location | Status |
|-----------|----------|--------|
| MD frontmatter | `data/journal/content/md/` | ✓ Already minimal (date, word_count, reading_time, locations, people) |
| Narrative analysis | `data/narrative_analysis/` | Has scenes, events, threads, arcs, tags, themes, motifs |
| Poems | `data/legacy/poems_archive.yaml` | ✓ Already extracted (40+ poems by entry date) |
| References | `data/legacy/references_archive.yaml` | ✓ Already extracted (100+ references by entry date) |
| Notes | `data/legacy/notes_archive.yaml` | ✓ Already extracted (editor notes by entry date) |
| Curation files | `data/curation/` | Per-year people and locations curation |

**Key Insight:** MD frontmatter cleanup is ALREADY DONE. Poems, references, and notes were previously extracted to `data/legacy/`. The narrative_analysis YAMLs do NOT contain poems/references — those are only in the legacy archives.

**Input:**
- Narrative analysis YAMLs (scenes, events, threads, arcs, tags, themes, motifs)
- Legacy archives (poems, references, notes — keyed by entry date)
- Per-year curation files for entity resolution

**Output:**
- NEW metadata YAML files (`metadata/journal/YYYY/YYYY-MM-DD.yaml`) with:
  - All narrative analysis data (scenes, events, threads, arcs, tags, themes, motifs)
  - Poems and references merged from legacy archives
  - Consistent entity names (resolved via curation)
- narrative_analysis/ directory deleted after transformation
- (Optional) Add `narrated_dates` to MD frontmatter if not already present

**Completed:**
1. ✓ Build `dev/bin/extract_entities.py` - extract people/locations from YAMLs
2. ✓ Run extraction → generates per-year curation draft files
3. ✓ Manual curation for 2020+ (pre-2020 too noisy, abandoned)
4. ✓ Build `dev/bin/validate_curation.py` - ensure curation quality
5. ✓ Extract poems/references/notes to legacy archives (already done previously)

**Remaining:**
6. Build jumpstart script that:
   - Reads narrative_analysis YAMLs
   - Merges poems from `data/legacy/poems_archive.yaml` (by entry date)
   - Merges references from `data/legacy/references_archive.yaml` (by entry date)
   - Resolves entity names via curation files
   - Writes to `metadata/journal/YYYY/YYYY-MM-DD.yaml`
   - Deletes narrative_analysis/ after successful transformation

**Cutoff decision:** Pre-2020 entries are too noisy for curation. Only 2020+ entries will have curated entities.

**Definition of Done:**
- New metadata YAML files created (`metadata/journal/YYYY/YYYY-MM-DD.yaml`)
- Poems and references merged from legacy archives
- Entity names consistent (resolved via curation)
- narrative_analysis/ deleted
- All files ready for future DB import

---

### Phase 14b-2: DB Import (after jumpstart)

**Goal:** Import clean files into database.

**Tasks:**
1. Build DB import script
2. Import clean MD frontmatter + clean narrative analysis YAMLs → DB
3. Validate import (entry counts, relationship integrity)

---

### Phase 14b-3: Export Canonical YAMLs (after DB import)

**Goal:** Export from DB to canonical YAML files with all relationships.

**Tasks:**
1. Build `dev/pipeline/export_yaml.py` - DB → canonical YAML export
2. Export to:
   - `metadata/people/{name}.yaml` - person with all relationships (entries, scenes, threads, characters)
   - `metadata/locations/{city}/{location}.yaml` - location with relationships
   - `metadata/journal/{YYYY}/{YYYY-MM-DD}.yaml` - entry with all analysis data
3. Generate wiki pages from DB
4. **After validation:** Delete `narrative_analysis/`

**Canonical YAMLs are DB exports** — They include all relationships from the database.

---

### Phase 14c: Wiki Parsing + Sync + NVim Integration

**Goal:** Enable wiki → DB → YAML workflow. Wiki edits update DB and export to YAML.

**Tasks:**

1. **Create wiki parser** (`dev/wiki/parser.py`)
   - Parse structured wiki page sections
   - Extract metadata from tables, link lists
   - Handle journal entry pages, manuscript chapter pages, entity pages
   - Validate parsed data before DB update

2. **Create YAML export** (`dev/pipeline/export_yaml.py`)
   - Export journal entries: `data/metadata/journal/{YYYY}/{YYYY-MM-DD}.yaml`
   - Export manuscript: `index.yaml`, `chapters/*.yaml`, `characters/*.yaml`
   - Use consistent YAML formatting (ruamel.yaml)

3. **Implement sync mechanism**
   - On-demand sync (command-based) vs save hooks (auto-sync)
   - Parse wiki changes → update DB → export YAML
   - Handle conflicts (wiki wins, DB is derived)

4. **Update NVim integration** (`dev/lua/palimpsest/`)
   - Add `:PalimpsestSync` command (parse wiki → DB → YAML)
   - Add `:PalimpsestExport` command (DB → YAML)
   - Add keymaps for common operations
   - Integrate with wiki parser (Lua calls Python)

**Implementation Notes:**
- Wiki pages must have structured sections for reliable parsing
- Metadata sections use tables or bullet lists
- Links follow consistent patterns
- Parser validates before updating DB

**Tests:**
- Edit wiki page → DB updated correctly
- DB changes → YAML exports correctly
- Round-trip: wiki → DB → YAML → reimport → same data

**Definition of Done:**
- Wiki parser works for all page types
- YAML export generates correct files
- NVim commands functional
- Round-trip validated

---

### Phase 14d: Vimwiki Templates

**Goal:** Update wiki templates for the new workflow (editable metadata sections).

**Tasks:**

1. **Update journal entry templates**
   - Metadata sections editable (scenes, events, arcs, etc.)
   - Prose displayed but read-only (links to MD file)
   - Structured format for reliable parsing

2. **Create manuscript chapter templates**
   - Dashboard view: metadata, source links, status
   - Link to draft file for prose
   - Characters, arcs, poems, references lists

3. **Create character templates**
   - Character info: name, role, description
   - Person mappings (who they're based on)
   - Chapters where they appear

4. **Update entity templates**
   - People, locations, arcs, etc.
   - Bidirectional links (entity ↔ entries/chapters)

5. **Add structured sections**
   - Use consistent delimiters for parser
   - Metadata tables with editable cells
   - Link lists for relationships

**Template Structure Example:**

```markdown
# Entry: 2024-12-03

## Metadata
| Field | Value |
|-------|-------|
| Rating | 4.5 |
| Summary | Sofia increases her dose... |

## Arcs
- [[narrative/arcs/the-long-wanting|The Long Wanting]]
- [[narrative/arcs/the-march-crisis|The March Crisis]]

## Scenes
### Psychiatric Session
- **Date:** 2024-12-03
- **People:** [[people/dr-franck|Dr-Franck]]
- **Locations:** [[locations/home|Home]]
- **Description:** Sofia meets with Dr. Franck to discuss increasing her dose

### The Two Sips
...

## Events
- **The Raki Afternoon:** [[#The Two Sips]], [[#Waiting for the Text]]
- **The Dose Increase:** [[#Psychiatric Session]]

## Threads
...

---
*Source: [[file:../../journal/content/md/2024/2024-12-03.md|2024-12-03.md]]*
```

**Tests:**
- Templates render correctly from DB
- Templates parse correctly to DB
- Round-trip preserves data

**Definition of Done:**
- All templates updated
- Parsing works reliably
- Wiki is navigable and editable

---

### Phase 14e: Documentation + Cleanup

**Goal:** Create documentation, update CLAUDE.md, remove deprecated code.

**Tasks:**

1. **Create `data/docs/` spec files**
   - `md_frontmatter_spec.md` — Frontmatter field documentation
   - `yaml_export_spec.md` — YAML structure documentation
   - `data_architecture.md` — Architecture overview

2. **Update `CLAUDE.md`**
   - Remove outdated guidelines
   - Add new patterns (wiki editing, DB queries)
   - Update narrative analysis guidelines for wiki

3. **Remove deprecated code**
   - Old database models
   - Old sync scripts
   - Outdated pipeline code

4. **Final test suite**
   - All unit tests pass
   - All integration tests pass
   - Coverage maintained

**Tests:**
- Full workflow: write in wiki → DB → YAML → git diff
- All tests pass

**Definition of Done:**
- Documentation complete
- CLAUDE.md updated
- Deprecated code removed
- All tests pass

---

## Pending Decisions

These items were discussed but not fully resolved:

### 1. Manuscript Draft Files: Content vs Path

**Question:** Should shorter pieces (poems, vignettes) store content inline in DB/YAML, or always use separate files?

**Current plan:**
- Short pieces: `Chapter.content` field (inline)
- Long prose: `Chapter.draft_path` field (separate file)

**Open question:** What's the threshold? Who decides per-chapter?

### 2. Wiki Sync Mechanism

**Question:** On-demand sync (`:PalimpsestSync` command) or auto-sync on save?

**Options:**
- **On-demand:** User explicitly syncs when ready
- **Auto-save:** Sync triggers on wiki file save
- **Hybrid:** Auto-sync for metadata pages, on-demand for drafts

**Current plan:** On-demand initially, evaluate auto-sync later.

### 3. Archive Strategy for narrative_analysis/

**Decision:** Delete after validation.

**Question:** Keep a single archived copy in `backups/` or truly delete?

**Current plan:** Truly delete (git history preserves everything).

### 4. NVim ↔ Python Integration Method

**Question:** How does Lua call Python scripts?

**Options:**
- Shell out (`vim.fn.system()`)
- Neovim job control (`vim.fn.jobstart()`)
- RPC/socket (more complex)

**Current plan:** Shell out initially, evaluate job control for async operations.

---

## Controlled Vocabularies

### Motifs (26 total)

The complete motif vocabulary:

1. The Anchor
2. The Bed
3. The Body
4. The Bottle
5. The Cavalry
6. The Chaser
7. The Death of Ivan
8. The Edge
9. The Ghost
10. The High-Functioning Collapse
11. The Hunger
12. The Institution
13. The Loop
14. The Mask
15. The Mirror
16. The Obsession
17. The Page
18. The Place
19. The Replacement
20. The Scroll
21. The Spiral
22. The Telling
23. The Touch
24. The Transformation
25. The Void
26. The Wait

### Enums

**ChapterType:**
- `prose` — Full narrative chapters
- `vignette` — Correspondence, drafted messages, lists, fragments
- `poem` — Verse

**ChapterStatus:**
- `draft` — Work in progress
- `revised` — Revised but not final
- `final` — Complete

**SceneOrigin:**
- `journaled` — From journal scene
- `inferred` — Reconstructed from gaps/references
- `invented` — Created for narrative
- `composite` — Merged from multiple sources

**SceneStatus:**
- `fragment` — Unassigned piece
- `draft` — In a chapter, being worked
- `included` — Final inclusion
- `cut` — Removed from manuscript

**SourceType:**
- `scene` — Journal scene
- `entry` — Journal entry (no specific scene)
- `thread` — Temporal echo
- `external` — Outside material (texts, screenshots, memories)

**ReferenceType:**
- `book`
- `poem`
- `article`
- `film`
- `song`
- `podcast`
- (others as needed)

**ReferenceMode:**
- `direct` — Exact quote
- `indirect` — Summarized reference
- `paraphrase` — Loose adaptation
- `visual` — Image/film reference
- `thematic` — Conceptual/mood reference

**ContributionType:**
- `primary` — Main basis for character
- `composite` — One of several people merged
- `inspiration` — Loose influence

**RelationType:**
- `family` — Family members
- `friend` — Friends
- `romantic` — Romantic partners
- `colleague` — Work colleagues
- `acquaintance` — Casual acquaintances
- `professional` — Professional relationships (therapist, doctor, etc.)
- `public` — Public figures, celebrities
- `other` — Uncategorized relationships

---

## Verification Commands

```bash
# Validate DB schema
python -m dev.database.validate

# Run MD frontmatter migration (dry-run)
python -m dev.pipeline.migrate_frontmatter --dry-run

# Extract entities for curation
python -m dev.bin.extract_entities

# Validate curation files
python -m dev.bin.validate_curation

# Run jumpstart migration (dry-run)
python -m dev.pipeline.jumpstart --dry-run

# Run jumpstart (for real)
python -m dev.pipeline.jumpstart

# Retry failed imports
python -m dev.pipeline.jumpstart --failed-only

# Export DB to YAML
python -m dev.pipeline.export_yaml --all

# Validate wiki ↔ DB consistency
python -m dev.pipeline.validate_sync

# Generate vimwiki
python -m dev.wiki.cli generate --all

# Run full test suite
python -m pytest tests/ -q
```

---

## Migration Strategy Details

### Pre-Migration Validation

Before starting migration:

1. **Backup current state**
   - Copy `narrative_analysis/` to `backups/`
   - Export current DB
   - Commit all changes to git

2. **Validate source data**
   - Check YAML format (all files parse)
   - Identify malformed entries
   - Document known issues

### Entity Curation Workflow

Before import, entities must be curated:

1. **Extract** — Run extraction script, generates draft files
2. **Review** — User reviews auto-groupings
3. **Refine** — User splits/merges groups as needed
4. **Validate** — Run validation script
5. **Import** — Jumpstart uses curated files

### Rollback Strategy

If migration fails:

1. **Restore DB** from backup
2. **Regenerate wiki** from restored DB
3. **Keep narrative_analysis/** (don't delete until success)
4. **Fix issues** and retry

### Post-Migration Cleanup

After successful validation:

1. **Delete `narrative_analysis/`** (git history preserves)
2. **Archive jumpstart logs** to `data/logs/archive/`
3. **Clean up temporary files**
4. **Update documentation**

---

## Document History

- **Created:** During Phase 14 planning dialogue
- **Purpose:** Capture all CS/Novelist dialogue conclusions
- **Status:** Active planning document
- **Location:** `/home/soffiafdz/Documents/palimpsest/PLAN.md`
- **Current Phase:** 14b (Jumpstart Migration)

**Updates:**
- 2025-01-30: Added Entity File Organization section (per-entity files for people/locations)
- 2025-01-30: Moved from ~/.claude/plans/ to project root

---

*End of Phase 14 Planning Document*
