# Manuscript Subwiki Design Document

## Overview

The Palimpsest project will have **two separate wiki systems**:

1. **Main Wiki** (`data/wiki/`) - Comprehensive metadata dashboard for ALL journal entities
2. **Manuscript Subwiki** (`data/wiki/manuscript/`) - Focused workspace for manuscript adaptation

*Design Rationale*: This architectural decision stems from the need to support distinct use cases: the Main Wiki provides a holistic, browseable view of all journal content for general reference and initial annotation, while the Manuscript Subwiki offers a highly specialized, uncluttered environment dedicated to the intensive creative process of adapting journal entries into literary works. This separation prevents the complexities of manuscript planning from overwhelming the general journaling workflow and ensures each system is optimized for its primary function.

## Separation of Concerns

### Main Wiki
**Purpose**: Complete metadata representation of journal database

**Entities**:
- Entries (`wiki/entries/YYYY/YYYY-MM-DD.md`)
- People (`wiki/people/*.md`)
- Events (`wiki/events/*.md`)
- Locations (`wiki/locations/*.md`)
- Cities (`wiki/cities/*.md`)
- Tags (`wiki/tags/*.md`)
- Themes (`wiki/themes/*.md`)
- Poems (`wiki/poems/*.md`)
- References (`wiki/references/*.md`)

**Fields**:
- All database metadata (dates, word counts, relationships, etc.)
- General editorial notes (Entry.notes, Event.notes, Person notes/vignettes)
- Cross-references between entities
- Navigation (prev/next, breadcrumbs, indexes)

**Data Source**: Core database models (`Entry`, `Person`, `Event`, etc.)

### Manuscript Subwiki
**Purpose**: Manuscript adaptation workspace and narrative planning

**Entities**:
- Manuscript Entries (`wiki/manuscript/entries/YYYY/YYYY-MM-DD.md`)
- Characters (`wiki/manuscript/characters/*.md`)
- Manuscript Events (`wiki/manuscript/events/*.md`)
- Arcs (`wiki/manuscript/arcs/*.md`)
- Themes (`wiki/manuscript/themes/*.md`)

**Fields**:
- Manuscript-specific metadata (status, editing state, adaptation type)
- Character mappings (real person → fictional character)
- Narrative structure (arcs, themes, scene types)
- Adaptation notes (different from general Entry.notes)
- Manuscript chronology and organization

**Data Source**: Manuscript-specific models (`ManuscriptEntry`, `ManuscriptPerson`, `ManuscriptEvent`, `Arc`, `Theme`)

*Design Rationale*: This clear delineation ensures that the complexities of manuscript development do not interfere with the core function of the Main Wiki as a comprehensive journal archive. Each wiki serves a specialized role, optimizing the user experience for general browsing and detailed creative adaptation, respectively, while maintaining a single, authoritative database as the source of truth.

## Database Schema Enhancements

### Fields to Add
These fields are essential for enriching the manuscript adaptation process, allowing for detailed planning and tracking of narrative elements directly within the database schema.

#### ManuscriptEntry
**Existing**: status, edited, notes
**To Add**:
- `entry_type` (Enum): `vignette`, `scene`, `summary`, `reflection`, `dialogue`
   *Rationale*: Categorizing entries helps structure the narrative and identify their primary role in the manuscript.
- `character_notes` (Text): Notes about character development in this entry
   *Rationale*: Allows for specific character-centric annotations tied to individual entries, aiding consistent character portrayal.
- `narrative_arc` (FK): Link to Arc if part of a narrative thread
   *Rationale*: Connects individual entries to overarching narrative arcs, providing structural coherence for the manuscript.

#### ManuscriptEvent
**Existing**: arc_id, notes
**No changes needed** - current fields are sufficient

#### ManuscriptPerson
**Existing**: character (fictional name)
**To Add**:
- `character_description` (Text): Physical description of character
   *Rationale*: Stores detailed physical and personality traits for consistent character visualization.
- `character_arc` (Text): Character development notes
   *Rationale*: Tracks the evolution and transformation of characters throughout the narrative.
- `voice_notes` (Text): Notes about character's narrative voice
   *Rationale*: Captures nuances in dialogue and internal monologue to ensure a distinctive character voice.
- `appearance_notes` (Text): Notes about how character appears in manuscript
   *Rationale*: Records specific details about a character's role or portrayal in different parts of the manuscript.


## Directory Structure

```
data/wiki/
├── index.md                    # Main wiki homepage
├── people.md                   # People index
├── entries.md                  # Entries index
├── events.md                   # Events index
├── ...
├── people/                     # All people
│   ├── alice_johnson.md
│   └── bob.md
├── entries/                    # All entries
│   └── 2024/
│       ├── 2024-04-05.md
│       ├── 2024-11-01.md
│       └── 2024-11-05.md
└── manuscript/                 # MANUSCRIPT SUBWIKI
    ├── index.md                # Manuscript homepage
    ├── characters.md           # Characters index
    ├── entries.md              # Manuscript entries index
    ├── arcs.md                 # Story arcs index
    ├── themes.md               # Manuscript themes index
    ├── events.md               # Manuscript events index
    ├── characters/             # Fictional characters
    │   ├── alice.md            # Character adapted from Alice Johnson
    │   └── robert.md           # Character adapted from Bob
    ├── entries/                # Manuscript-adapted entries
    │   └── 2024/
    │       ├── 2024-04-05.md   # Entry if in manuscript
    │       └── 2024-11-01.md   # Entry if in manuscript
    ├── events/                 # Manuscript-adapted events
    │   └── conference_trip.md
    ├── arcs/                   # Story arcs
    │   ├── career_transition.md
    │   └── friendship_evolution.md
    └── themes/                 # Manuscript themes
        ├── identity.md
        └── belonging.md
```

## Entity Formats

### Manuscript Entry
```markdown
# Palimpsest — Manuscript Entry

*[[../../index.md|Home]] > [[../../manuscript/index.md|Manuscript]] > [[../entries.md|Entries]] > 2024-11-01*

## 2024-11-01

### Source
- **Original Entry**: [[../../../entries/2024/2024-11-01.md|View in Main Wiki]]
- **Date**: 2024-11-01
- **Word Count**: 500 words
- **Status**: source
- **Edited**: Yes

### Manuscript Metadata
- **Entry Type**: vignette
- **Narrative Arc**: [[../../arcs/friendship_evolution.md|Friendship Evolution]]
- **Themes**:
  - [[../../themes/identity.md|Identity]]
  - [[../../themes/belonging.md|Belonging]]

### Characters
- [[../../characters/alice.md|Alice]] (based on Alice Johnson) - protagonist's mentor
- [[../../characters/robert.md|Robert]] (based on Bob) - colleague

### Adaptation Notes
This entry captures the excitement of new professional connections. Will be adapted as a coffee shop vignette emphasizing Alice's influence on the protagonist's career direction.

### Character Notes
- Alice's dialogue needs to convey warmth but also professional wisdom
- Robert appears briefly but sets up later conflict

### Navigation
- **Previous**: [[2024-04-05.md|2024-04-05]]
- **Next**: [[2024-11-05.md|2024-11-05]]
```

### Character (Manuscript Person)
```markdown
# Palimpsest — Character

*[[../../index.md|Home]] > [[../../manuscript/index.md|Manuscript]] > [[../characters.md|Characters]] > Alice*

## Alice

### Based On
**Real Person**: [[../../../people/alice_johnson.md|Alice Johnson]] (friend)

### Character Description
Mid-thirties software engineer with an infectious enthusiasm for her work. Short dark hair, always dressed professionally but with creative flair (statement jewelry, colorful scarves).

### Character Arc
Starts as the protagonist's mentor and inspiration, gradually becomes a peer and friend. Represents the professional identity the protagonist aspires to embody.

### Voice Notes
Speaks with confidence but never condescension. Uses technical jargon naturally but explains concepts patiently. Warm laugh, asks incisive questions.

### Appearances
- **First**: [[../entries/2024/2024-11-01.md|2024-11-01]] — Coffee meetup vignette
- **Last**: [[../entries/2024/2024-11-05.md|2024-11-05]] — Conference scene
- **Total Scenes**: 2

### Character Notes
Need to balance her supportive role with her own career ambitions. She's not just a mentor figure - she has her own story.
```

### Story Arc
```markdown
# Palimpsest — Story Arc

*[[../../index.md|Home]] > [[../../manuscript/index.md|Manuscript]] > [[../arcs.md|Arcs]] > Friendship Evolution*

## Friendship Evolution

### Description
Tracks the development of the protagonist's friendship with Alice from professional mentorship to genuine personal connection.

### Timeline
- 2024-11-01: Initial coffee meeting
- 2024-11-05: Conference discussion

### Events in Arc
- [[../../events/coffee_meetup.md|Coffee Meetup]] (2024-11-01)
- [[../../events/conference_discussion.md|Conference Discussion]] (2024-11-05)

### Entries in Arc
- [[../entries/2024/2024-11-01.md|2024-11-01]] — Coffee meetup vignette
- [[../entries/2024/2024-11-05.md|2024-11-05]] — Conference scene

### Characters
- [[../characters/alice.md|Alice]] — Primary character in arc
- [[../characters/robert.md|Robert]] — Supporting role

### Themes
- [[../themes/identity.md|Identity]]
- [[../themes/belonging.md|Belonging]]
- [[../themes/mentorship.md|Mentorship]]

### Arc Notes
This arc needs to show growth from professional admiration to genuine friendship without losing the professional context that defines their relationship.

### Status
- **Entries**: 2 of ~5 planned
- **Completion**: 40%
- **Next Steps**: Add entry about shared project collaboration
```

## Export Pipeline

### Two Separate Pipelines
The use of two distinct pipelines for the Main Wiki and Manuscript Subwiki is a deliberate design choice to maintain separation of concerns and optimize for their respective purposes.

#### sql2wiki.py (Main Wiki)
**Entities**: All database entities
**Command**: `plm export-wiki {entity_type}`
**Function**: Export comprehensive metadata for all journal content
*Rationale*: This pipeline focuses on generating a complete and accurate representation of the entire journal database in wiki format, ensuring all entities and their relationships are reflected for general browsing and reference.

#### manuscript2wiki.py (Manuscript Subwiki)
**Entities**: Only manuscript-designated entities
**Command**: `plm export-wiki {entity_type}`
**Function**: Export manuscript-specific metadata for adaptation workspace
*Rationale*: This specialized pipeline selectively exports only content relevant to the manuscript development process. It filters out non-manuscript data and formats the output specifically for creative adaptation, avoiding clutter and focusing the workspace for authors.

### Export Logic

```python
def export_manuscript_entries():
    """Export only entries with ManuscriptEntry records."""
    # Query entries with manuscript metadata
    query = select(Entry).join(ManuscriptEntry)

    for entry in entries:
        manuscript = entry.manuscript
        wiki_entry = ManuscriptWikiEntry.from_database(
            entry, manuscript, wiki_dir, journal_dir
        )
        # Export to wiki/manuscript/entries/YYYY/YYYY-MM-DD.md
```

### Import Pipeline (wiki2sql.py)

Update existing `wiki2sql.py` to handle both:
- Main wiki edits → Core models (Entry.notes, Event.notes)
- Manuscript wiki edits → Manuscript models (ManuscriptEntry.notes, character_notes, etc.)

## Navigation

### Cross-Wiki Links

Entries in both wikis should link to each other:
- Main Entry → "View in Manuscript" (if applicable)
- Manuscript Entry → "View Original" (always)

Example in main wiki entry:
```markdown
### Manuscript
- **Status**: Included (source)
- **View**: [[../../manuscript/entries/2024/2024-11-01.md|View in Manuscript Wiki]]
```

### Breadcrumbs

Use wiki hierarchy:
- Main Wiki: `Home > Entries > 2024 > 2024-11-01`
- Manuscript: `Home > Manuscript > Entries > 2024 > 2024-11-01`

## Benefits of Separation

1. **Clear Boundaries**: Editorial notes (Entry.notes) vs Adaptation notes (ManuscriptEntry.notes)
2. **Focused Workspace**: Manuscript wiki only shows content being adapted
3. **Different Audiences**: Main wiki = research/reference, Manuscript = creative writing
4. **Independent Navigation**: Different organizational needs (chronological vs narrative structure)
5. **Reduced Clutter**: Main wiki doesn't show manuscript-specific metadata for entries not being adapted
6. **Parallel Development**: Can enhance manuscript workflow without affecting main wiki

## Next Steps

1. ✓ Design manuscript subwiki structure
2. Decide on database migrations needed
3. Create manuscript wiki dataclasses
4. Implement manuscript export pipeline
5. Test and iterate on manuscript wiki format
6. Extend import pipeline for manuscript metadata
