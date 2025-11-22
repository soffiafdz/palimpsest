# Manuscript Subwiki Design Document

## Overview

The Palimpsest project will have **two separate wiki systems**:

1. **Main Wiki** (`data/wiki/`) - Comprehensive metadata dashboard for ALL journal entities
2. **Manuscript Subwiki** (`data/wiki/manuscript/`) - Focused workspace for manuscript adaptation

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

## Database Schema Enhancements

### Fields to Add

#### ManuscriptEntry
**Existing**: status, edited, notes
**To Add**:
- `entry_type` (Enum): `vignette`, `scene`, `summary`, `reflection`, `dialogue`
- `character_notes` (Text): Notes about character development in this entry
- `narrative_arc` (FK): Link to Arc if part of a narrative thread

#### ManuscriptEvent
**Existing**: arc_id, notes
**No changes needed** - current fields are sufficient

#### ManuscriptPerson
**Existing**: character (fictional name)
**To Add**:
- `character_description` (Text): Physical description of character
- `character_arc` (Text): Character development notes
- `voice_notes` (Text): Notes about character's narrative voice
- `appearance_notes` (Text): Notes about how character appears in manuscript

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

#### sql2wiki.py (Main Wiki)
**Entities**: All database entities
**Command**: `python -m dev.pipeline.sql2wiki export {entity_type}`
**Function**: Export comprehensive metadata for all journal content

#### manuscript2wiki.py (Manuscript Subwiki)
**Entities**: Only manuscript-designated entities
**Command**: `python -m dev.pipeline.manuscript2wiki export {entity_type}`
**Function**: Export manuscript-specific metadata for adaptation workspace

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

## Implementation Phases

### Phase 1: Database Schema
1. Add migration for ManuscriptEntry fields (entry_type, character_notes, narrative_arc)
2. Add migration for ManuscriptPerson fields (character_description, character_arc, voice_notes)
3. Update models with new fields

### Phase 2: Manuscript Dataclasses
1. Create `dev/dataclasses/manuscript_entry.py`
2. Create `dev/dataclasses/manuscript_person.py` (Character)
3. Create `dev/dataclasses/manuscript_event.py`
4. Create `dev/dataclasses/manuscript_arc.py`
5. All inherit from WikiEntity, implement from_database() and to_wiki()

### Phase 3: Export Pipeline
1. Create `dev/pipeline/manuscript2wiki.py`
2. Implement export functions for all manuscript entities
3. Add CLI interface matching sql2wiki.py pattern
4. Create manuscript wiki indexes

### Phase 4: Import Pipeline
1. Extend `wiki2sql.py` to handle manuscript wiki imports
2. Add import functions for manuscript-specific fields
3. Test bidirectional sync for manuscript metadata

### Phase 5: Integration
1. Add cross-wiki links between main and manuscript
2. Update main wiki entry export to show manuscript status
3. Create manuscript homepage and navigation
4. Update Neovim integration to handle manuscript wiki

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
