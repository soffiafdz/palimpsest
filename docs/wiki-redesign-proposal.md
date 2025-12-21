# Wiki Redesign: Journal-First Architecture

This document proposes a comprehensive wiki system for Palimpsest that treats the **journal as the primary focus**, with the manuscript as a secondary project layer.

---

## Design Philosophy

```
┌─────────────────────────────────────────────────────────────────┐
│                     PALIMPSEST WIKI                             │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                    JOURNAL (Primary)                       │ │
│  │                                                            │ │
│  │  A decade of life, documented.                            │ │
│  │  384+ entries. Thousands of moments. Hundreds of people.  │ │
│  │                                                            │ │
│  │  The wiki helps you:                                       │ │
│  │  • Navigate by any dimension (time, place, person, theme) │ │
│  │  • Discover patterns across years                          │ │
│  │  • Track relationships and their evolution                 │ │
│  │  • Explore the geography of your life                      │ │
│  │  • Find connections you didn't know existed               │ │
│  │                                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │                  MANUSCRIPT (Secondary)                    │ │
│  │                                                            │ │
│  │  One creative project built on a subset of journal data.  │ │
│  │  Character mappings. Narrative arcs. Thematic curation.   │ │
│  │                                                            │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Assets: Complete Relationship Map

### The Entry as Center

Every analysis starts from **Entry** and radiates outward through 12 association tables:

```
                              ┌─────────────┐
                              │   CITIES    │
                              │  entry_cities
                              └──────┬──────┘
                                     │
┌─────────────┐              ┌───────┴───────┐              ┌─────────────┐
│  LOCATIONS  │──────────────│               │──────────────│   PEOPLE    │
│entry_locations              │     ENTRY     │  entry_people │+ aliases    │
└─────────────┘              │               │              └─────────────┘
                              │   384+ docs   │
┌─────────────┐              │   156k words  │              ┌─────────────┐
│   EVENTS    │──────────────│               │──────────────│    TAGS     │
│ entry_events│              └───────┬───────┘  entry_tags  └─────────────┘
└─────────────┘                      │
                                     │
┌─────────────┐              ┌───────┴───────┐              ┌─────────────┐
│  REFERENCES │──────────────│    MOMENTS    │──────────────│   POEMS     │
│   + sources │ entry_moments│  (with type)  │              │ + versions  │
└─────────────┘              └───────────────┘              └─────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                │                │
              moment_people    moment_locations  moment_events
                    │                │                │
                    ▼                ▼                ▼
                 People          Locations         Events
```

### Computed Properties Available

Every entity has rich computed properties ready for dashboard use:

| Entity | Key Properties |
|--------|----------------|
| **Entry** | `age_display`, `date_range`, `reading_time_display`, `has_person()`, `has_tag()` |
| **Person** | `display_name`, `entry_count`, `appearances_count`, `first/last_appearance`, `mention_timeline`, `mention_frequency`, `privacy_sensitivity`, `is_close_relationship` |
| **Location** | `entry_count`, `visit_count`, `first/last_visit_date`, `visit_timeline`, `visit_frequency`, `visit_span_days` |
| **City** | `entry_count`, `visit_frequency` (by month) |
| **Moment** | `entry_count`, `people_present`, `locations_visited`, `is_reference`, `type_display` |
| **Event** | `duration_days`, `chronological_entries`, `start/end_date`, `all_people`, `moment_locations` |
| **Tag** | `usage_count`, `usage_span_days`, `first/last_used`, `chronological_entries` |
| **Alias** | `usage_count`, `first/last_used` |
| **Reference** | `content_preview` |
| **ReferenceSource** | `display_name`, `reference_count` |
| **Poem** | `version_count`, `latest_version` |

---

## Part 1: Journal Dashboards

### 1.1 HOME — Journal Command Center

**Purpose:** Bird's-eye view of your entire journal corpus

```
┌─────────────────────────────────────────────────────────────────┐
│  PALIMPSEST — Journal                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  THE CORPUS                                                     │
│  ═══════════                                                    │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐            │
│  │ 384 Entries  │ │ 156,234      │ │ 2016 → 2025  │            │
│  │              │ │ Words        │ │ ~9 years     │            │
│  └──────────────┘ └──────────────┘ └──────────────┘            │
│                                                                 │
│  DIMENSIONS                                                     │
│  ══════════                                                     │
│  People     │ 127 individuals │ 43 close relationships         │
│  Places     │ 8 cities        │ 89 specific locations          │
│  Events     │ 24 narrative events spanning multiple entries    │
│  Tags       │ 45 categories                                    │
│  Moments    │ 892 dated moments │ 156 references               │
│  References │ 67 external sources (books, films, etc.)         │
│  Poems      │ 12 poems with 28 versions                        │
│                                                                 │
│  RECENT ENTRIES                      QUICK NAVIGATION           │
│  ════════════════                    ════════════════           │
│  • 2025-12-05 (3 days ago)           [Timeline]                 │
│  • 2025-12-03 (5 days ago)           [People]                   │
│  • 2025-12-01 (1 week ago)           [Places]                   │
│  • 2025-11-28                        [Events]                   │
│  • 2025-11-25                        [Tags]                     │
│                                      [References]               │
│  YEAR DISTRIBUTION                   [Poems]                    │
│  ═════════════════                                              │
│  2025 ████████████████░░░░ 89 entries                          │
│  2024 ██████████████████░░ 102 entries                         │
│  2023 ████████████░░░░░░░░ 67 entries                          │
│  2022 ██████████░░░░░░░░░░ 54 entries                          │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- Entry count, word sum, date range from Entry model
- Dimension counts from each entity
- Year distribution from Entry.date grouped

---

### 1.2 TIMELINE — Chronological Navigation

**Purpose:** Navigate all entries chronologically with rich metadata overlay

```
┌─────────────────────────────────────────────────────────────────┐
│  TIMELINE                                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  [All Years] [2025] [2024] [2023] [2022] ...                   │
│                                                                 │
│  Filter: [People ▾] [Places ▾] [Events ▾] [Tags ▾]             │
│                                                                 │
│  ═══════════════════════════════════════════════════════════   │
│  DECEMBER 2025                                                  │
│  ═══════════════════════════════════════════════════════════   │
│                                                                 │
│  05 │ 1,245 words │ 4.8 min read                               │
│     │ Cities: Montréal, Mont-Saint-Hilaire                     │
│     │ People: Sylvia, Alexa, Alfonso, Beri, Yara, Clara, Alda  │
│     │ Events: Sylvia's-lab-retreat                             │
│     │ Tags: IG-story, Manuscript                               │
│     │ Moments: 3 actual, 1 reference                           │
│     │   • 2025-12-01 — Retreat first day (actual)              │
│     │   • 2025-12-03 — Last day (actual)                       │
│     │   • 2025-12-04 — Clara adds close-friends (actual)       │
│     │   • ~2024-04-16 — Bea fragments reference (reference)    │
│     └──────────────────────────────────────────────────────────│
│                                                                 │
│  03 │ 876 words │ 3.4 min read                                 │
│     │ Cities: Montréal                                         │
│     │ People: Majo, Sylvia                                     │
│     │ ...                                                       │
│     └──────────────────────────────────────────────────────────│
│                                                                 │
│  ═══════════════════════════════════════════════════════════   │
│  NOVEMBER 2025 (12 entries)                                     │
│  ═══════════════════════════════════════════════════════════   │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- Entry model with all relationships eager-loaded
- Moment.type for actual vs reference distinction
- Filter by person/place/event/tag relationships

---

### 1.3 PEOPLE — Social Universe

**Purpose:** Explore everyone who appears in your journal

#### 1.3.1 People Index

```
┌─────────────────────────────────────────────────────────────────┐
│  PEOPLE                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  127 individuals across 384 entries                            │
│                                                                 │
│  BY RELATIONSHIP                                                │
│  ════════════════                                               │
│  Romantic (5)     │ ████████████████████░░░░░░░░ 89 mentions   │
│  Family (12)      │ ██████████████░░░░░░░░░░░░░░ 67 mentions   │
│  Friends (34)     │ ████████████████████████████ 234 mentions  │
│  Colleagues (28)  │ ████████░░░░░░░░░░░░░░░░░░░░ 45 mentions   │
│  Acquaintances    │ ████░░░░░░░░░░░░░░░░░░░░░░░░ 23 mentions   │
│  Professional     │ ██░░░░░░░░░░░░░░░░░░░░░░░░░░ 12 mentions   │
│                                                                 │
│  MOST MENTIONED                       RECENT APPEARANCES        │
│  ══════════════                       ══════════════════        │
│  1. Clara (42 entries)                Clara — 2025-12-05        │
│  2. Majo (38 entries)                 Majo — 2025-12-01         │
│  3. Mom (28 entries)                  Sylvia — 2025-12-05       │
│  4. Sonny (24 entries)                Alda — 2025-12-05         │
│  5. Alda (22 entries)                 Beri — 2025-12-05         │
│                                                                 │
│  ALPHABETICAL                                                   │
│  ════════════                                                   │
│  [A] Alda (22) • Alexa (8) • Alfonso (12) • Ali (5)            │
│  [B] Beri (15) • Bob (3)                                        │
│  [C] Clara (42) • ...                                           │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

#### 1.3.2 Person Detail Page

```
┌─────────────────────────────────────────────────────────────────┐
│  PERSON: Clara                                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  IDENTITY                                                       │
│  ════════                                                       │
│  Name: Clara                                                    │
│  Also known as: @Ary                                           │
│  Relationship: Romantic                                         │
│  Privacy level: 5/5 (highest)                                   │
│                                                                 │
│  PRESENCE IN JOURNAL                                            │
│  ═══════════════════                                            │
│  Entries: 42                                                    │
│  Moments: 156 (actual appearances on specific dates)            │
│  References: 23 (dates mentioned in context of Clara)           │
│  Events: 4 (narrative events involving Clara)                   │
│                                                                 │
│  First appearance: 2024-04-15                                   │
│  Last appearance: 2025-12-05                                    │
│  Span: 600 days (1.6 years)                                    │
│                                                                 │
│  APPEARANCE TIMELINE                                            │
│  ═══════════════════                                            │
│  2024 │ A M J J A S O N D                                       │
│       │ . . ● ● . ● ● ● ●  (18 entries)                        │
│  2025 │ J F M A M J J A S O N D                                 │
│       │ ● ● ● ● ● ● ● . ● ● ● ●  (24 entries)                  │
│                                                                 │
│  MONTHLY FREQUENCY                                              │
│  ═════════════════                                              │
│  2024-04 ████ 4 entries                                        │
│  2024-05 ░░ 0 entries                                          │
│  2024-06 ██ 2 entries                                          │
│  2024-07 ██████ 6 entries                                      │
│  ...                                                            │
│                                                                 │
│  CO-APPEARANCES (people who appear with Clara)                  │
│  ══════════════════════════════════════════════                 │
│  • Majo — 18 shared entries                                    │
│  • Alda — 12 shared entries                                    │
│  • Sonny — 8 shared entries                                    │
│  • Mom — 4 shared entries                                      │
│                                                                 │
│  LOCATIONS (places associated with Clara)                       │
│  ═════════════════════════════════════════                      │
│  • Montréal — 34 moments                                       │
│  • Ciudad de México — 8 moments                                │
│  • Station Verdun — 5 moments                                  │
│                                                                 │
│  EVENTS (narrative events involving Clara)                      │
│  ═════════════════════════════════════════                      │
│  • Clara-arc — 24 entries, Apr 2024 → Dec 2025                 │
│  • Double-exposures — 3 entries, Nov 2024                      │
│  • Montreal-visit — 6 entries, Jul 2024                        │
│                                                                 │
│  MOMENTS (actual dated appearances)                             │
│  ═══════════════════════════════════                            │
│  2025-12-05: Clara adds close-friends on IG                    │
│  2025-12-04: Clara opens story, likes fragments                │
│  2024-11-27: Double exposure photos                            │
│  2024-04-16: The anti-date, broken tooth                       │
│  2024-04-15: First meeting at the bar                          │
│  ...                                                            │
│                                                                 │
│  REFERENCES (dates mentioned in context of Clara)               │
│  ════════════════════════════════════════════════               │
│  These are dates that appear as ~references in entries about    │
│  Clara, linking current moments to past events:                 │
│                                                                 │
│  ~2024-04-16 (anti-date) referenced in:                        │
│    • 2025-02-15: "the negatives from that night"               │
│    • 2025-06-02: "photos from the anti-date"                   │
│    • 2025-12-05: "fragments of Bea"                            │
│                                                                 │
│  ~2024-11-27 (double exposures) referenced in:                 │
│    • 2025-06-02: "the series of 3"                             │
│                                                                 │
│  NOTES                                                          │
│  ═════                                                          │
│  [Your personal notes about this person...]                     │
└─────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- Person model with all computed properties
- entry_people for entry relationships
- moment_people for specific dated appearances
- Moment.type for actual vs reference distinction
- event_people and entry_events for event connections
- moment_locations for geographic associations
- Co-appearances via shared entries

---

### 1.4 PLACES — Geographic Exploration

**Purpose:** Explore the geography of your life

#### 1.4.1 Places Index

```
┌─────────────────────────────────────────────────────────────────┐
│  PLACES                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  8 cities • 89 specific locations                              │
│                                                                 │
│  CITIES BY FREQUENCY                                            │
│  ═══════════════════                                            │
│  Montréal          │ ████████████████████████████ 245 entries  │
│  Ciudad de México  │ ████████████░░░░░░░░░░░░░░░░ 67 entries   │
│  Tijuana           │ ████████░░░░░░░░░░░░░░░░░░░░ 45 entries   │
│  San Diego         │ ████░░░░░░░░░░░░░░░░░░░░░░░░ 18 entries   │
│  Toronto           │ ██░░░░░░░░░░░░░░░░░░░░░░░░░░ 8 entries    │
│  ...                                                            │
│                                                                 │
│  LOCATION HEATMAP (top locations)                               │
│  ════════════════════════════════                               │
│  The Neuro (Montréal)        │ 45 visits                       │
│  Parents' house (Tijuana)    │ 34 visits                       │
│  Café Olimpico (Montréal)    │ 28 visits                       │
│  Station Verdun (Montréal)   │ 22 visits                       │
│  Coyoacán (CDMX)             │ 18 visits                       │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

#### 1.4.2 City Detail Page

```
┌─────────────────────────────────────────────────────────────────┐
│  CITY: Montréal                                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OVERVIEW                                                       │
│  ════════                                                       │
│  Entries: 245                                                   │
│  Locations: 34 specific venues                                  │
│  Time span: 2016 → 2025                                        │
│                                                                 │
│  VISIT FREQUENCY BY MONTH                                       │
│  ════════════════════════                                       │
│  2025 │ J F M A M J J A S O N D                                │
│       │ 8 7 9 6 8 12 10 8 7 9 8 3 (entries/month)              │
│  2024 │ ...                                                     │
│                                                                 │
│  LOCATIONS IN THIS CITY                                         │
│  ══════════════════════                                         │
│                                                                 │
│  The Neuro                    45 visits │ 2018-09 → 2025-12    │
│    └─ People often here: Sylvia, Majo, lab colleagues          │
│                                                                 │
│  Station Verdun               22 visits │ 2020-03 → 2025-12    │
│    └─ Transit hub, meeting point                               │
│                                                                 │
│  Café Olimpico                28 visits │ 2017-05 → 2024-08    │
│    └─ People often here: Majo, Alda                            │
│                                                                 │
│  ...                                                            │
│                                                                 │
│  PEOPLE ASSOCIATED WITH THIS CITY                               │
│  ═════════════════════════════════                              │
│  • Majo — 89 entries in Montréal                               │
│  • Sylvia — 45 entries                                         │
│  • Clara — 34 entries                                          │
│  • Lab colleagues — various                                     │
└─────────────────────────────────────────────────────────────────┘
```

#### 1.4.3 Location Detail Page

```
┌─────────────────────────────────────────────────────────────────┐
│  LOCATION: The Neuro (Montréal)                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  VISIT HISTORY                                                  │
│  ═════════════                                                  │
│  Total visits: 45                                               │
│  First visit: 2018-09-15                                       │
│  Last visit: 2025-12-01                                        │
│  Span: 2,634 days (7.2 years)                                  │
│                                                                 │
│  PEOPLE AT THIS LOCATION                                        │
│  ═══════════════════════                                        │
│  Via moments at this location:                                  │
│  • Sylvia — 34 moments here                                    │
│  • Majo — 12 moments here                                      │
│  • Lab colleagues — various                                     │
│                                                                 │
│  EVENTS AT THIS LOCATION                                        │
│  ═══════════════════════                                        │
│  • Thesis-journey — 23 entries involving The Neuro             │
│  • Thesis-seminar — 3 entries                                  │
│                                                                 │
│  VISIT TIMELINE                                                 │
│  ══════════════                                                 │
│  2025-12-01: Thesis defense prep                               │
│  2025-11-28: Meeting with Sylvia                               │
│  2025-06-02: Thesis seminar                                    │
│  ...                                                            │
│                                                                 │
│  NOTES                                                          │
│  ═════                                                          │
│  [Your notes about this location...]                            │
└─────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- City and Location models with computed properties
- entry_cities and entry_locations for entry connections
- moment_locations for specific dated visits
- Cross-reference with people via shared moments

---

### 1.5 EVENTS — Narrative Groupings

**Purpose:** Explore multi-entry narrative events

```
┌─────────────────────────────────────────────────────────────────┐
│  EVENTS                                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  24 events spanning 384 entries                                │
│                                                                 │
│  BY DURATION                                                    │
│  ═══════════                                                    │
│  Thesis-journey     │ 2018-09 ──────────────────── 2025-12     │
│                     │ 67 entries │ 7+ years                    │
│                                                                 │
│  Clara-arc          │ 2024-04 ───────── 2025-12                │
│                     │ 42 entries │ 20 months                   │
│                                                                 │
│  HRT-crisis         │ 2025-01 ──── 2025-03                     │
│                     │ 12 entries │ 3 months                    │
│                                                                 │
│  Sylvia's-lab-retreat │ 2025-12-01 ─ 2025-12-05               │
│                       │ 3 entries │ 5 days                     │
│  ...                                                            │
│                                                                 │
│  BY ENTRY COUNT                                                 │
│  ══════════════                                                 │
│  1. Thesis-journey (67)                                        │
│  2. Clara-arc (42)                                             │
│  3. Daily-life (34)                                            │
│  4. Family (28)                                                │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

#### Event Detail Page

```
┌─────────────────────────────────────────────────────────────────┐
│  EVENT: Sylvia's-lab-retreat                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  OVERVIEW                                                       │
│  ════════                                                       │
│  Duration: 5 days (2025-12-01 → 2025-12-05)                    │
│  Entries: 3                                                     │
│  Total words: 3,456                                            │
│                                                                 │
│  PEOPLE INVOLVED                                                │
│  ════════════════                                               │
│  Via direct entry mentions:                                     │
│  • Sylvia, Alexa, Alfonso, Beri, Yara, Valentin, Ali           │
│                                                                 │
│  Via moments within this event:                                 │
│  • All above + Clara (mentioned in reference)                  │
│                                                                 │
│  LOCATIONS                                                      │
│  ═════════                                                      │
│  Via moments:                                                   │
│  • Station Verdun, Premiere Moisson, Gault Nature Reserve      │
│                                                                 │
│  ENTRIES (chronological)                                        │
│  ═══════════════════════                                        │
│  • 2025-12-01: Departure, first day of retreat                 │
│  • 2025-12-03: Last day, return                                │
│  • 2025-12-05: Reflection, IG stories about manuscript         │
│                                                                 │
│  MOMENTS IN THIS EVENT                                          │
│  ═════════════════════                                          │
│  Actual moments:                                                │
│  • 2025-12-01: Retreat begins, hike                            │
│  • 2025-12-03: Return to Montréal                              │
│  • 2025-12-04: Clara adds close-friends                        │
│                                                                 │
│  References:                                                    │
│  • ~2024-04-16: Bea fragments mentioned                        │
│                                                                 │
│  NOTES                                                          │
│  ═════                                                          │
│  [Your notes about this event...]                               │
└─────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- Event model with computed properties
- entry_events for entry connections
- moment_events for specific dated moments
- event_people for direct people connections
- Moment.type for actual vs reference

---

### 1.6 MOMENTS — Temporal Echoes

**Purpose:** Explore how dates echo through your journal

This is the new feature leveraging `Moment.type`:

```
┌─────────────────────────────────────────────────────────────────┐
│  MOMENTS — Temporal Echoes                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  892 moments │ 736 actual │ 156 references                     │
│                                                                 │
│  UNDERSTANDING MOMENTS vs REFERENCES                            │
│  ════════════════════════════════════                           │
│  • MOMENT: An event that happened on this date                 │
│  • REFERENCE: A date mentioned in context, echoing back        │
│                                                                 │
│  MOST ECHOED DATES (dates with most references)                │
│  ══════════════════════════════════════════════                 │
│  These dates ripple through time, referenced again and again:  │
│                                                                 │
│  2024-04-16 — The anti-date                                    │
│  ├─ Original: Entry 2024-04-16 (the night with Bea)           │
│  └─ Referenced in: 4 later entries                             │
│     • 2025-02-15: "negatives from that night"                  │
│     • 2025-06-02: "photos from the anti-date"                  │
│     • 2025-12-05: "fragments of Bea"                           │
│     • 2025-12-08: "that broken tooth"                          │
│                                                                 │
│  2024-11-27 — Double exposures                                 │
│  ├─ Original: Entry 2024-11-27 (Clara's photos)               │
│  └─ Referenced in: 3 later entries                             │
│     • 2025-06-02: "the series of 3"                            │
│     • 2025-08-15: "those double exposures"                     │
│     • 2025-12-05: "photos she made"                            │
│                                                                 │
│  2024-07-04 — Montreal visit                                   │
│  ├─ Original: Entry 2024-07-04                                 │
│  └─ Referenced in: 2 later entries                             │
│                                                                 │
│  REFERENCE PATTERNS                                             │
│  ═══════════════════                                            │
│  By how far back references reach:                              │
│  • < 1 month: 45 references                                    │
│  • 1-3 months: 34 references                                   │
│  • 3-12 months: 56 references                                  │
│  • > 1 year: 21 references                                     │
│                                                                 │
│  RECENT REFERENCES                                              │
│  ═════════════════                                              │
│  2025-12-05 references:                                         │
│    • ~2024-04-16 (Bea fragments)                               │
│  2025-12-01 references:                                         │
│    • ~2025-11-15 (cancelled retreat)                           │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- Moment model with type field
- entry_moments for which entries mention which moments
- Context field for reference descriptions
- Calculate temporal distance for "echo patterns"

---

### 1.7 TAGS — Categorical Organization

**Purpose:** Explore your journal by tags

```
┌─────────────────────────────────────────────────────────────────┐
│  TAGS                                                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  45 tags across 384 entries                                    │
│                                                                 │
│  BY FREQUENCY                                                   │
│  ════════════                                                   │
│  Photography      │ ██████████████████████████ 67 entries      │
│  Insomnia         │ ████████████████░░░░░░░░░░ 45 entries      │
│  HRT              │ ████████████░░░░░░░░░░░░░░ 34 entries      │
│  Manuscript       │ ██████████░░░░░░░░░░░░░░░░ 28 entries      │
│  Thesis           │ ████████░░░░░░░░░░░░░░░░░░ 23 entries      │
│  Film-camera      │ ██████░░░░░░░░░░░░░░░░░░░░ 18 entries      │
│  IG-story         │ ████░░░░░░░░░░░░░░░░░░░░░░ 12 entries      │
│  ...                                                            │
│                                                                 │
│  TAG TIMELINE (when tags are used)                              │
│  ═════════════════════════════════                              │
│  Photography │ ─────●●●●●●●●●●●●●●●●●●●────── (2017 → 2025)    │
│  Insomnia    │ ───────────●●●●●●●●●●●●●────── (2020 → 2025)    │
│  HRT         │ ────────────────────────●●●●── (2024 → 2025)    │
│  ...                                                            │
│                                                                 │
│  CO-OCCURRING TAGS                                              │
│  ═════════════════                                              │
│  Photography + Film-camera: 15 entries                         │
│  Insomnia + HRT: 12 entries                                    │
│  Photography + Manuscript: 8 entries                           │
└─────────────────────────────────────────────────────────────────┘
```

---

### 1.8 REFERENCES — Intertextual Map

**Purpose:** Explore external sources referenced in your journal

```
┌─────────────────────────────────────────────────────────────────┐
│  REFERENCES — Intertextual Map                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  67 sources referenced across entries                          │
│                                                                 │
│  BY TYPE                                                        │
│  ═══════                                                        │
│  Books      │ ████████████████ 23 sources                      │
│  Films      │ ████████████ 18 sources                          │
│  TV Shows   │ ████████ 12 sources                              │
│  Music      │ ██████ 8 sources                                 │
│  Articles   │ ████ 6 sources                                   │
│                                                                 │
│  MOST REFERENCED                                                │
│  ═══════════════                                                │
│  1. "The Last of Us" (TV) — 8 references                       │
│     └─ Entries: 2025-06-02, 2025-05-25, ...                    │
│     └─ Mode: direct quote (3), paraphrase (5)                  │
│                                                                 │
│  2. [Book Title] by [Author] — 5 references                    │
│     └─ Entries: 2024-03-15, 2024-07-22, ...                    │
│                                                                 │
│  REFERENCE MODES                                                │
│  ════════════════                                               │
│  Direct quotes: 34                                              │
│  Paraphrases: 28                                               │
│  Indirect allusions: 12                                         │
│  Visual references: 5                                           │
│                                                                 │
│  REFERENCES BY YEAR                                             │
│  ══════════════════                                             │
│  2025: 23 references                                           │
│  2024: 34 references                                           │
│  2023: 18 references                                           │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

**Data sources:**
- Reference model with ReferenceMode enum
- ReferenceSource model with ReferenceType enum
- reference_count computed property
- Group by type, mode, year

---

### 1.9 POEMS — Poetic Works

**Purpose:** Track poems written in journal entries

```
┌─────────────────────────────────────────────────────────────────┐
│  POEMS                                                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  12 poems with 28 total versions                               │
│                                                                 │
│  POEMS BY VERSION COUNT                                         │
│  ══════════════════════                                         │
│  "Mi color favorito"     │ 5 versions │ 2024-11 → 2025-03      │
│  "Untitled (distance)"   │ 4 versions │ 2024-07 → 2024-12      │
│  "Ruins"                 │ 3 versions │ 2025-04 → 2025-06      │
│  ...                                                            │
│                                                                 │
│  RECENT VERSIONS                                                │
│  ════════════════                                               │
│  • "Ruins" v3 — 2025-06-08 (34 lines)                          │
│  • "Mi color favorito" v5 — 2025-03-15 (28 lines)              │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 2: Manuscript Section (Secondary)

The manuscript section is a **focused layer** on top of the journal, for one specific creative project.

```
┌─────────────────────────────────────────────────────────────────┐
│  MANUSCRIPT — Auto-fiction Project                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  This section tracks the curation of journal entries into      │
│  a manuscript, including character mappings and narrative arcs.│
│                                                                 │
│  DASHBOARDS                                                     │
│  ══════════                                                     │
│  • Curation Queue — Select entries for manuscript              │
│  • Selected Entries — Entries marked for adaptation            │
│  • Characters — Real person → fictional character mapping      │
│  • Arcs — Narrative arc structure                              │
│  • Themes — Manuscript-specific thematic elements              │
│  • Progress — Editing status and readiness                     │
│                                                                 │
│  STATUS                                                         │
│  ══════                                                         │
│  47 entries selected │ 12 edited │ 23,456 words                │
│  8 characters mapped │ 4 arcs defined                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Implementation Priority

### Phase 1: Core Journal Navigation
1. **Home Dashboard** — Stats and quick navigation
2. **Timeline** — Chronological with metadata overlay
3. **People Index + Detail** — Social universe exploration
4. **Places Index + Detail** — Geographic exploration

### Phase 2: Deeper Analysis
5. **Events Index + Detail** — Narrative groupings
6. **Moments (Temporal Echoes)** — The new moment/reference feature
7. **Tags Index** — Categorical navigation

### Phase 3: Creative Content
8. **References Index** — Intertextual map
9. **Poems Index** — Poetry tracking

### Phase 4: Manuscript Layer
10. **Manuscript Home** — Project overview
11. **Curation Queue** — Entry selection workflow
12. **Characters** — Character mapping
13. **Arcs** — Narrative structure
14. **Themes** — Thematic tagging

---

## Technical Notes

All dashboards will be:
- Static markdown files generated by Jinja2 templates
- Compatible with vimwiki for navigation
- Regenerated on `plm export-wiki`
- Leveraging the existing rich computed properties on models
- Using the 12 association tables for cross-referencing

---

## Questions for You

1. **Priority confirmation** — Does this journal-first structure match your vision?

2. **Depth of detail pages** — How much information should individual entity pages show? (e.g., should a Person page show every single entry, or just summaries?)

3. **Timeline granularity** — Should the timeline be browsable by day, week, month, or year?

4. **Filtering** — Which dimensions are most important for filtering? (people, places, tags, events?)

5. **Manuscript integration** — Should manuscript status be visible in journal views (as a subtle indicator), or completely separate?
