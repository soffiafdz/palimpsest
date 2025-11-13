# Phase 2 Extended: Comprehensive Metadata Wiki for Autofiction Manuscript

**Date:** 2025-11-13
**Status:** 🔄 **IN PROGRESS** - Design Phase
**Branch:** `claude/md2wiki-analysis-report-011CV528Jk6fsr3YrK6FhCvR`

---

## Executive Summary

Phase 2 Extended aims to create a **comprehensive metadata wiki** for autofiction manuscript creation by exporting ALL relevant database entities to interconnected vimwiki pages. This extends Phase 2's metadata-only approach (people, themes, tags, poems, references) to include the **core narrative elements** needed for manuscript development.

### Current State (Phase 2)
✅ **Metadata Entities (5/5):**
- People - Relationship tracking
- Themes - Conceptual threads
- Tags - Keyword classification
- Poems - Creative writing with versions
- References - External citations

### Extended Scope (Phase 2 Extended)
🔄 **Core Narrative Entities (5):**
- **Entries** - The journal entries themselves (foundation!)
- **Locations** - Geographic places and venues
- **Cities** - Geographic regions (parent of locations)
- **Events** - Story arcs spanning multiple entries
- **Timeline/Dates** - Temporal navigation and analysis

**Total Entities:** 10 (5 existing + 5 new)

---

## Design Philosophy: Autofiction Manuscript Wiki

### Purpose
Transform the journal database into a **navigable wiki** that supports:

1. **Source Material Access** - Quick access to journal entries
2. **Character Development** - Track people, relationships, evolution
3. **Setting Development** - Understand locations, cities, geographic patterns
4. **Plot Structure** - Identify events, story arcs, timelines
5. **Thematic Analysis** - Track themes, motifs, emotional patterns
6. **Temporal Navigation** - Browse by date, find patterns across time
7. **Cross-Referencing** - Discover connections between entities

### Wiki Structure

```
vimwiki/
├── index.md                     # Main wiki home page
├── entries.md                   # Entry index (by date)
├── entries/
│   ├── 2024/
│   │   ├── 01-january.md       # Monthly index
│   │   ├── 2024-01-15.md       # Individual entry
│   │   └── ...
│   └── ...
│
├── people.md                    # People index ✅ (Phase 2)
├── people/
│   ├── alice_johnson.md
│   └── ...
│
├── locations.md                 # Location index
├── locations/
│   ├── montréal/
│   │   ├── location_index.md   # Locations in Montreal
│   │   ├── café_olimpico.md
│   │   └── ...
│   └── ...
│
├── cities.md                    # City index
├── cities/
│   ├── montréal.md
│   ├── toronto.md
│   └── ...
│
├── events.md                    # Events index
├── events/
│   ├── thesis_defense.md
│   ├── conference_2024.md
│   └── ...
│
├── timeline.md                  # Chronological timeline
├── timeline/
│   ├── 2024.md                 # Year view
│   ├── 2024-01.md              # Month view
│   └── ...
│
├── themes.md                    # Themes index ✅ (Phase 2)
├── themes/
│   └── ...
│
├── tags.md                      # Tags index ✅ (Phase 2)
├── tags/
│   └── ...
│
├── poems.md                     # Poems index ✅ (Phase 2)
├── poems/
│   └── ...
│
├── references.md                # References index ✅ (Phase 2)
└── references/
    └── ...
```

---

## Entity Designs

### 1. Entry (Core Priority!)

**Database Model:** `Entry`
**Dataclass:** `dev/dataclasses/wiki_entry.py`

**Purpose:** The **foundation** of the wiki - each journal entry page with all its metadata and cross-references.

**Key Attributes:**
- date (ISO format)
- file_path (source markdown)
- word_count, reading_time
- epigraph, epigraph_attribution
- notes (wiki-editable)

**Relationships:**
- people mentioned
- locations visited
- cities
- events
- themes
- tags
- poems written
- references cited
- mentioned dates
- related entries
- manuscript metadata

**Wiki Page Structure:**
```markdown
# Entry — 2024-01-15

**Date:** 2024-01-15
**Word Count:** 847 words
**Reading Time:** 4.2 minutes
**Age:** 10 months ago

## Epigraph
> "To live is to be slowly born."
> — Antoine de Saint-Exupéry

## Content Preview
[First 200 words or summary]

[Link to source: [[../../data/journal/content/md/2024/2024-01-15.md|Read Full Entry]]]

## Metadata

### People
- [[people/alice_johnson.md|Alice Johnson]] (Friend)
- [[people/bob.md|Bob]] (Colleague)

### Locations
- [[locations/montréal/café_olimpico.md|Café Olimpico]] (Montréal)
- [[cities/montréal.md|Montréal]]

### Events
- [[events/thesis_defense.md|Thesis Defense]]

### Themes
- [[themes/academic_pressure.md|Academic Pressure]]
- [[themes/friendship.md|Friendship]]

### Tags
- #coffee #writing #anxiety

### Poems
- [[poems/morning_light.md|Morning Light]] (v1)

### References
- [[references/camus_sisyphus.md|Camus - The Myth of Sisyphus]]

### Mentioned Dates
- 2024-01-10 — Coffee with Alice
- 2024-02-01 — Thesis defense date

## Manuscript
**Status:** Draft
**Type:** Vignette
**Characters:** Alice → Emma, Bob → David
**Narrative Arc:** Academic struggle

## Related Entries
- [[entries/2024/2024-01-14.md|2024-01-14]] (Previous)
- [[entries/2024/2024-01-16.md|2024-01-16]] (Next)
- [[entries/2024/2024-01-10.md|2024-01-10]] (Related: Coffee meeting)

## Notes
[User-editable notes about this entry for manuscript use]
```

**Field Ownership:**
- **Database-Computed:** date, file_path, word_count, reading_time, epigraph, all relationships
- **Wiki-Editable:** notes

---

### 2. Location

**Database Model:** `Location`
**Dataclass:** `dev/dataclasses/wiki_location.py`

**Purpose:** Track specific venues/places for geographic narrative development.

**Key Attributes:**
- name (venue name)
- city (parent)
- visit_count, first_visit, last_visit
- visit_timeline

**Relationships:**
- entries (visits)
- mentioned_dates (explicit visits)
- parent city

**Wiki Page Structure:**
```markdown
# Location — Café Olimpico

**City:** [[cities/montréal.md|Montréal]]
**Total Visits:** 12
**First Visit:** 2023-09-15
**Last Visit:** 2024-11-05
**Span:** 14 months

## Visit Timeline

### 2024
- **2024-11-05** — [[entries/2024/2024-11-05.md|Conference discussion]]
- **2024-09-20** — [[entries/2024/2024-09-20.md|Writing session]]
- **2024-06-12** — [[entries/2024/2024-06-12.md|Birthday celebration]]

### 2023
- **2023-12-08** — [[entries/2023/2023-12-08.md|Final edits]]
- **2023-09-15** — [[entries/2023/2023-09-15.md|First visit]]

## People Encountered
- [[people/alice_johnson.md|Alice Johnson]] (8 visits)
- [[people/bob.md|Bob]] (3 visits)

## Significance
[User-editable significance notes for manuscript]

## Associated Themes
- [[themes/creativity.md|Creativity]]
- [[themes/friendship.md|Friendship]]
- [[themes/urban_life.md|Urban Life]]

## Notes
[User-editable notes about this location]
```

**Field Ownership:**
- **Database-Computed:** name, city, visit counts, timeline, relationships
- **Wiki-Editable:** significance, notes

---

### 3. City

**Database Model:** `City`
**Dataclass:** `dev/dataclasses/wiki_city.py`

**Purpose:** Geographic regions for setting development.

**Key Attributes:**
- city, state_province, country
- entry_count
- visit_frequency (by month)

**Relationships:**
- locations (child venues)
- entries

**Wiki Page Structure:**
```markdown
# City — Montréal

**Province:** Quebec
**Country:** Canada
**Total Entries:** 45
**First Entry:** 2023-09-01
**Last Entry:** 2024-11-05
**Duration:** 14 months

## Statistics
- Total locations tracked: 8
- Most visited month: October 2024 (9 entries)
- Average entries per month: 3.2

## Locations
- [[locations/montréal/café_olimpico.md|Café Olimpico]] (12 visits)
- [[locations/montréal/mont_royal.md|Mont Royal Park]] (8 visits)
- [[locations/montréal/mcgill_library.md|McGill Library]] (15 visits)

## People Met Here
- [[people/alice_johnson.md|Alice Johnson]]
- [[people/bob.md|Bob]]
- [[people/claire.md|Claire]]

## Associated Themes
- [[themes/academic_life.md|Academic Life]]
- [[themes/urban_exploration.md|Urban Exploration]]
- [[themes/belonging.md|Belonging]]

## Visit Frequency
### 2024
- November: 2 entries
- October: 9 entries
- September: 6 entries
...

### 2023
- December: 4 entries
- November: 5 entries
...

## Notes
[User-editable notes about this city for manuscript]
```

**Field Ownership:**
- **Database-Computed:** city, location, entry count, frequency, relationships
- **Wiki-Editable:** notes

---

### 4. Event

**Database Model:** `Event`
**Dataclass:** `dev/dataclasses/wiki_event.py`

**Purpose:** Track narrative arcs spanning multiple entries (story structure).

**Key Attributes:**
- event (identifier)
- title, description
- start_date, end_date, duration
- chronological_entries

**Relationships:**
- entries
- people involved
- manuscript mapping

**Wiki Page Structure:**
```markdown
# Event — Thesis Defense Preparation

**Identifier:** thesis_defense
**Duration:** 2024-01-10 to 2024-02-15 (36 days)
**Total Entries:** 14
**Status:** Completed

## Description
Preparation period for doctoral thesis defense, including revisions, practice presentations, and emotional processing.

## Timeline

### Week 1 (Jan 10-16)
- [[entries/2024/2024-01-10.md|2024-01-10]] — Initial panic
- [[entries/2024/2024-01-12.md|2024-01-12]] — Advisor feedback
- [[entries/2024/2024-01-15.md|2024-01-15]] — Coffee with Alice

### Week 2 (Jan 17-23)
- [[entries/2024/2024-01-18.md|2024-01-18]] — First practice presentation
- [[entries/2024/2024-01-21.md|2024-01-21]] — Late night revisions

...

### Defense Day
- [[entries/2024/2024-02-15.md|2024-02-15]] — The defense

## People Involved
- [[people/alice_johnson.md|Alice Johnson]] — Emotional support
- [[people/prof_smith.md|Prof. Smith]] — Advisor
- [[people/bob.md|Bob]] — Practice audience

## Locations
- [[locations/montréal/mcgill_library.md|McGill Library]] (8 visits)
- [[locations/montréal/café_olimpico.md|Café Olimpico]] (3 visits)

## Themes
- [[themes/academic_pressure.md|Academic Pressure]]
- [[themes/self_doubt.md|Self-Doubt]]
- [[themes/achievement.md|Achievement]]
- [[themes/friendship.md|Friendship]]

## Manuscript Treatment
**Narrative Arc:** Condensed to 3 scenes
**Characters:** Protagonist, Emma (Alice), Prof. Renard (Smith)
**Emotional Core:** Imposter syndrome → validation

## Notes
[User-editable notes about this event for manuscript]
```

**Field Ownership:**
- **Database-Computed:** event, title, dates, duration, entries, relationships
- **Wiki-Editable:** description (enhanced), manuscript treatment, notes

---

### 5. Timeline/Calendar View

**Purpose:** Chronological navigation and temporal pattern discovery.

**Implementation:** Not a database entity, but **generated views** from entries.

**Wiki Pages:**

#### A. Main Timeline Index (`timeline.md`)
```markdown
# Palimpsest — Timeline

Chronological view of journal entries for temporal analysis and navigation.

## By Year
- [[timeline/2024.md|2024]] (348 entries)
- [[timeline/2023.md|2023]] (312 entries)
- [[timeline/2022.md|2022]] (289 entries)

## Notable Periods
- [[events/thesis_defense.md|Thesis Defense]] (Jan-Feb 2024)
- [[events/summer_2023.md|Summer Research Trip]] (Jun-Aug 2023)
- [[events/relationship_end.md|Relationship End]] (Mar 2023)

## Statistics
- Total entries: 949
- Average per month: 28.7
- Longest streak: 45 days (Sep-Oct 2024)
- Total word count: 847,293 words
```

#### B. Year View (`timeline/2024.md`)
```markdown
# Timeline — 2024

**Total Entries:** 348
**Date Range:** 2024-01-01 to 2024-12-31
**Average per Month:** 29 entries

## By Month
- [[timeline/2024-12.md|December]] (15 entries, in progress)
- [[timeline/2024-11.md|November]] (28 entries)
- [[timeline/2024-10.md|October]] (32 entries)
...

## Major Events
- [[events/thesis_defense.md|Thesis Defense]] (Jan-Feb)
- [[events/conference_2024.md|Conference]] (May)
- [[events/summer_travel.md|Summer Travel]] (Jul-Aug)

## Key Themes
- [[themes/academic_transition.md|Academic Transition]]
- [[themes/personal_growth.md|Personal Growth]]
- [[themes/creativity.md|Creativity]]

## People Featured
- [[people/alice_johnson.md|Alice Johnson]] (89 mentions)
- [[people/bob.md|Bob]] (45 mentions)
...

## Locations
- [[cities/montréal.md|Montréal]] (245 entries)
- [[cities/toronto.md|Toronto]] (32 entries)
...
```

#### C. Month View (`timeline/2024-11.md`)
```markdown
# Timeline — November 2024

**Total Entries:** 28
**Word Count:** 24,589 words
**Average per Entry:** 878 words

## Entries by Week

### Week 1 (Nov 1-7)
- [[entries/2024/2024-11-01.md|Fri, Nov 1]] — Coffee meetup ☕
- [[entries/2024/2024-11-02.md|Sat, Nov 2]] — Writing day ✍️
- [[entries/2024/2024-11-05.md|Tue, Nov 5]] — Conference discussion 🎤

### Week 2 (Nov 8-14)
- [[entries/2024/2024-11-08.md|Fri, Nov 8]] — City walk 🚶
...

## Monthly Summary
- **Dominant Theme:** [[themes/creativity.md|Creativity]]
- **Most Mentioned Person:** [[people/alice_johnson.md|Alice Johnson]]
- **Primary Location:** [[cities/montréal.md|Montréal]]
- **Emotional Tone:** Reflective, optimistic

## Events
- [[events/nanowrimo_2024.md|NaNoWriMo 2024]] (ongoing)

## Poems Written
- [[poems/november_rain.md|November Rain]] (2024-11-12)

## Notes
[User-editable monthly reflection]
```

---

## Implementation Plan

### Priority Order

**Phase 2 Extended - Part 1: Core Narrative (Critical)**
1. Entry export → `WikiEntry`
2. Location export → `WikiLocation`
3. City export → `WikiCity`
4. Event export → `WikiEvent`

**Phase 2 Extended - Part 2: Navigation**
5. Timeline/calendar views

### Technical Approach

Each entity follows the established pattern:

```python
# 1. Dataclass (dev/dataclasses/wiki_{entity}.py)
@dataclass
class {Entity}(WikiEntity):
    path: Path
    # Entity-specific fields
    notes: Optional[str] = None

    @classmethod
    def from_database(cls, db_entity, wiki_dir, journal_dir):
        # Load from database
        # Generate relative links
        return cls(...)

    def to_wiki(self) -> List[str]:
        # Generate markdown
        return lines

    @property
    def computed_stats(self):
        # Derived properties

# 2. Export functions (dev/pipeline/sql2wiki.py)
def export_{entity}(db_entity, wiki_dir, journal_dir, force, logger) -> str:
    # Export single entity

def build_{entities}_index(entities, wiki_dir, force, logger) -> str:
    # Build index page

def export_{entities}(db, wiki_dir, journal_dir, force, logger) -> ConversionStats:
    # Batch export

# 3. CLI integration
@cli.command()
def export(entity_type: str):
    # Add to choices: entries, locations, cities, events, timeline, all
```

### Database Queries

**Entry:** Most complex (many relationships)
```python
query = (
    select(Entry)
    .options(
        joinedload(Entry.dates),
        joinedload(Entry.cities),
        joinedload(Entry.locations),
        joinedload(Entry.people),
        joinedload(Entry.events),
        joinedload(Entry.themes),
        joinedload(Entry.tags),
        joinedload(Entry.poems),
        joinedload(Entry.references),
        joinedload(Entry.manuscript),
        joinedload(Entry.related_entries),
    )
)
```

**Location:**
```python
query = (
    select(Location)
    .options(
        joinedload(Location.city),
        joinedload(Location.entries),
        joinedload(Location.dates),
    )
)
```

**City:**
```python
query = (
    select(City)
    .options(
        joinedload(City.locations),
        joinedload(City.entries),
    )
)
```

**Event:**
```python
query = (
    select(Event)
    .options(
        joinedload(Event.entries),
        joinedload(Event.people),
        joinedload(Event.manuscript),
    )
    .where(Event.deleted_at.is_(None))
)
```

---

## Cross-Referencing Strategy

Every wiki page should link to related entities:

**Entry pages link to:**
- All mentioned entities (people, locations, events, themes, tags)
- Previous/next entries (chronological navigation)
- Related entries (explicit relationships)
- Source markdown file

**Entity pages link to:**
- All related entries (appearances/mentions)
- Related entities (e.g., locations → cities, people → events)
- Timeline views (temporal context)

**Timeline pages link to:**
- Individual entries
- Events spanning that period
- Dominant entities (people, locations, themes)

---

## Expected Benefits for Autofiction

1. **Character Development**
   - Track how people appear/evolve over time
   - Identify relationship patterns
   - Find memorable interactions/dialogue

2. **Setting Development**
   - Understand place significance
   - Identify atmospheric details
   - Map geographic patterns

3. **Plot Structure**
   - Visualize event arcs
   - Find natural chapter breaks
   - Identify narrative throughlines

4. **Thematic Analysis**
   - Track theme evolution
   - Find thematic clusters
   - Identify emotional patterns

5. **Source Material Access**
   - Quick navigation to relevant entries
   - Cross-reference search
   - Temporal browsing

6. **Manuscript Planning**
   - Identify what to include/exclude
   - Plan character composites
   - Structure narrative arcs
   - Track fictional adaptations

---

## Statistics Projection

**Database Content (Estimated):**
- Entries: ~949 (primary source)
- People: ~50-100
- Locations: ~30-50
- Cities: ~10-20
- Events: ~15-30
- Themes: ~20-40
- Tags: ~50-100
- Poems: ~10-30
- References: ~30-80

**Generated Wiki Pages (Estimated):**
- Total entity pages: ~1,200-1,500
- Total index pages: ~20
- Timeline pages: ~50 (years + months)
- **Grand Total: ~1,270-1,570 wiki pages**

**Performance Target:**
- Full export: < 5 seconds
- Individual entity type: < 1 second

---

## Next Steps

1. ✅ Survey database models → COMPLETE
2. ✅ Create design document → COMPLETE
3. 🔄 Implement WikiEntry → IN PROGRESS
4. ⏳ Implement WikiLocation → PENDING
5. ⏳ Implement WikiCity → PENDING
6. ⏳ Implement WikiEvent → PENDING
7. ⏳ Implement Timeline views → PENDING
8. ⏳ Test with real database → PENDING
9. ⏳ Create Phase 2 Extended completion report → PENDING

---

**Phase 2 Extended Status: 🔄 Design Complete, Implementation Starting**

This comprehensive wiki will transform the journal database into a powerful tool for autofiction manuscript development, providing navigable access to all narrative elements, temporal patterns, and thematic connections.
