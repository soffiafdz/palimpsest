# Wiki Page Design Plan

Comprehensive design proposal for all Palimpsest wiki page types.
Developed through CS/Novelist/Graphic Designer dialogue.
Review each page design individually.

---

## Design Principles

1. **Every element earns its space** — no naked links; inline context always
2. **Nested structure over flat lists** — leverage Arc → Event → Scene hierarchy
3. **Computed aggregates over exhaustive dumps** — top companions, frequencies,
   time spans rather than listing every entry
4. **Scale-aware rendering** — different layouts for 3 items vs 300 items
5. **Consistent zones** — editable header → narrative spine → context → appendix
6. **City → Neighborhood → Location** — geographic nesting everywhere
7. **People and locations on separate lines** — never interleaved; they are
   independent dimensions (a scene can have 8 people at 1 location or
   1 person crossing 4 locations)
8. **Wiki as navigation dashboard** — pages link out to source files (journal
   markdown, narrative analysis YAML) rather than reproducing content
9. **Narrator excluded from frequency lists** — the narrator appears in every
   entry; listing them adds zero information

---

## Architectural Decisions

### Editable Boundary

The original design proposed "journal = read-only, manuscript = editable."
After analysis, the boundary shifted to:

- **Entry pages** = read-only (generated from DB)
- **Journal entity pages** = editable for curation fields that have no
  YAML source (relation_type, neighborhood, country, arc description)
- **Manuscript pages** = fully editable

Only 3 DB fields lack a YAML/markdown source:

| Model | Field | Editable on wiki |
|-------|-------|-----------------|
| Person | `relation_type` | Yes — only editable field on Person pages |
| City | `country` | Yes — only editable field on City pages |
| Arc | `description` | Yes — only editable field on Arc pages |

Additionally, `Location.neighborhood` is a new field (string on Location
model) requiring a schema migration. It adds an intermediate geographic
hierarchy: City → Neighborhood → Location.

**Full name is NOT editable** — it is computed from `name + lastname`
(both sourced from YAML). Disambiguator is also YAML-sourced. The Person
wiki page displays these as read-only generated content.

### Manuscript Metadata Architecture

**YAML as structured metadata source:**
Manuscript structural metadata (Part number/title, Character name/role,
Scene origin/status, Chapter type/status) is stored in YAML files:
- `data/manuscript/parts.yaml`
- `data/manuscript/characters/*.yaml` (or single file)
- `data/manuscript/scenes/*.yaml`
- `data/manuscript/chapters/*.yaml`

**Wiki as prose content + generated views:**
Wiki pages are auto-generated from DB, displaying both YAML-sourced metadata
and editable prose content:
- **Fully generated pages:** Part, Index pages, all Journal pages
- **Mixed pages:** Chapter, Character, ManuscriptScene have editable prose
  sections (synopsis, description, notes) alongside generated sections

**Floating window editing (Palimpsest nvim plugin):**
Structured metadata is edited via floating window popup:
- Keybinding: `<leader>em` or command `:PalimpsestEditMeta`
- Opens YAML file in floating window overlay
- User edits, saves, closes → back to wiki seamlessly
- No navigation friction, feels like metadata panel

**Parser behavior:**
- Reads editable prose sections from wiki (synopsis, descriptions, notes)
- Ignores generated sections (sources, chapter lists, aggregations)
- YAML files parsed separately for structured metadata
- Sync updates DB from both sources, regenerates wiki pages

This avoids the "ugly split" of editable-above-line, generated-below-line
within single pages. Structured data lives in YAML (edited via popup),
prose lives in wiki sections, generated content feels unified.

### Palimpsest Plugin Commands

**Command Reference Table**

| Command | Keybinding | Context | Purpose | Autocomplete |
|---------|-----------|---------|---------|--------------|
| `:PalimpsestEdit` | `<leader>em` | Any entity page | Open metadata YAML in floating window | N/A |
| `:PalimpsestNew {type}` | `<leader>en` | Any page | Create new entity (scene/chapter/character/part) | Entity type on input |
| `:PalimpsestAddSource` | — | ManuscriptScene page | Add source reference to Sources section | Entry dates, scene names, thread names |
| `:PalimpsestLinkToManuscript` | — | Journal pages (Entry, Person, Poem, etc.) | Link journal content as manuscript source | Manuscript scene names |
| `:PalimpsestAddBasedOn` | — | Character page | Add person mapping to Based On section | People (display_name + entry count + relation), contribution types |
| `:PalimpsestLinkToCharacter` | — | Person page | Link journal person to manuscript character | Character names, contribution types |
| `:PalimpsestAddScene` | — | Chapter page | Add scene to Scenes section | Manuscript scene names |
| `:PalimpsestAddCharacter` | — | Chapter page | Add character to Characters section | Character names |
| `:PalimpsestAddArc` | — | Chapter page | Add arc to Arcs section | Arc names |
| `:PalimpsestAddReference` | — | Chapter page | Add reference to References section | Reference sources, prompts for quote/mode |
| `:PalimpsestAddPoem` | — | Chapter page | Add poem to Poems section | Poem titles |

---

### Palimpsest Plugin Command Details

**`:PalimpsestEdit` (or `<leader>em`)**
Opens metadata YAML for current entity in floating window.

**Manuscript entities:**
- Part page → `data/manuscript/parts.yaml` (positioned at this part)
- Chapter page → `data/manuscript/chapters/{slug}.yaml`
- Character page → `data/manuscript/characters/{slug}.yaml`
- Scene page → `data/manuscript/scenes/{slug}.yaml`

**Journal entities:**
- Entry page → `data/metadata/journal/YYYY/YYYY-MM-DD.yaml`
- Person page → `data/metadata/people/{slug}.yaml` (241 people, individual files)
- Location page → `data/metadata/locations/{slug}.yaml` (348 locations, individual files)
- City page → `data/metadata/cities.yaml` (11 cities, single file, positioned at this city)
- Arc page → `data/metadata/arcs.yaml` (33 arcs, single file, positioned at this arc)

**File size handling:**
- Small YAML files (<100 lines): floating window (default 60% screen)
- Large YAML files (Entry metadata ~200+ lines): configurable (floating or split)

**`:PalimpsestNew {type}` (or `<leader>en` with type prompt)**
Creates new entity with optional context. Types: `scene`, `chapter`, `character`, `part`.

**Context-aware creation:**
- On Chapter page → `:PalimpsestNew scene` pre-fills `chapter_id`
- On Part page → `:PalimpsestNew chapter` pre-fills `part_id`
- Opens YAML template in floating window, user fills fields, saves to create

**DB-backed autocomplete:**
YAML editing includes autocomplete from DB for relational fields:
- Character `based_on.person` → autocomplete People (display_name + entry count + relation)
- Scene `sources.entry_date` → autocomplete Entry dates
- Scene `sources.scene_name` → autocomplete Scene names from that entry (after date selected)
- Chapter `arcs` → autocomplete Arc names
- Any person/location reference → autocomplete from DB

Uses `nvim-cmp` or native completion API, queries `palimpsest.db` on keystroke.

**`:PalimpsestAddSource`** (on ManuscriptScene page)
Guided insertion of source references into wiki Sources section.

Workflow:
1. Cursor in `## Sources` section of ManuscriptScene page
2. Command prompts for source type: scene, entry, thread, external
3. DB-backed autocomplete for relevant fields:
   - Scene: entry date → scene name from that entry
   - Entry: entry date
   - Thread: thread name → entry date
   - External: free text (URL, book title, etc.)
4. Inserts formatted wiki line: `**Scene:** [[2024-11-08]] — The Gray Fence`

**`:PalimpsestLinkToManuscript`** (on journal pages)
Bidirectional linking: mark journal content as manuscript source.

Workflow:
1. On journal page (Entry, Scene context, Person, Poem, etc.)
2. Command prompts: "Link to which manuscript scene?"
3. Autocompletes manuscript scene names
4. Adds source link to selected scene's Sources section
5. Use case: while reviewing journal, mark sources for manuscript without leaving context

Parser extracts sources from wiki structured format:
```markdown
**Scene:** [[2024-11-08]] — The Gray Fence
**Entry:** [[2024-11-15]]
**Thread:** The Bookend Kiss ([[2024-12-15]])
**External:** Interview notes, March 2024
```

Pattern: `**{Type}:** [[{date}]]( — {name})?` or `**{Type}:** {name} ([[{date}]])`

**`:PalimpsestAddBasedOn`** (on Character page)
Guided insertion of person-character mappings into Based On section.

Workflow:
1. Cursor in `## Based On` section of Character page
2. Command prompts for person
3. DB-backed autocomplete: shows People with display_name, entry count, relation type
4. Select contribution type: primary, composite, inspiration (autocomplete)
5. Optionally add notes paragraph (free text)
6. Inserts formatted wiki section:
```markdown
**[[Clara Dupont]]** · primary
The central inspiration. Most scenes are drawn directly
from journal observations.
```

**`:PalimpsestLinkToCharacter`** (on Person page)
Bidirectional linking: mark journal person as character inspiration.

Workflow:
1. On Person page (e.g., Clara's page)
2. Command prompts: "Link to which character?"
3. Autocompletes manuscript character names
4. Prompts for contribution type (primary/composite/inspiration)
5. Adds person mapping to selected character's Based On section
6. Use case: while reviewing journal people, mark character inspirations

Parser extracts person mappings from wiki structured format:
```markdown
**[[Person Display Name]]** · {contribution_type}
Optional notes paragraph describing the contribution.
```

Pattern: `**[[{person}]]** · {contribution}` + optional prose block

### Journal Entity Metadata Files

**Per-entity YAML files** (high cardinality):
- `data/metadata/people/{slug}.yaml` (241 people)
- `data/metadata/locations/{slug}.yaml` (348 locations)

Format:
```yaml
name: Clara
lastname: Dupont
relation_type: romantic
```

**Single YAML file** (low cardinality):
- `data/metadata/cities.yaml` (11 cities)
- `data/metadata/arcs.yaml` (33 arcs)

Format:
```yaml
cities:
  - name: Montreal
    country: Canada
  - name: Mexico City
    country: Mexico
```

`:PalimpsestEdit` positions cursor at relevant entry within single-file YAMLs.

### Thread Display

Threads do NOT get their own wiki pages. They are contextual connectors
displayed inline on:
- Entry pages (Connections zone)
- Person pages (when the person is involved in the thread)
- Location pages (when the location is referenced in the thread)

Thread display format (used everywhere):

```markdown
#### [[The Bookend Kiss]]
*Nov 8, 2024 → Dec 2024* · see [[2024-12-15]]

The greeting kiss at Jarry bookends the goodbye —
structural symmetry marking the relationship's progression.

**People:** [[Clara]]
**[[Montreal]]:** [[Station Jarry]]
```

Thread fields rendered:
- `name` as `####` wikilinked heading
- `from_date → to_date` as italic date range
- `entry` (optional) as "see [[date]]" wikilink to the entry narrating
  the distant moment
- `content` as the connection description paragraph
- `people` on their own line(s)
- `locations` on their own line(s), grouped by city

### Computation Strategy

All computed aggregates (co-occurrence, frequency counts, arc-event
grouping) are calculated at **wiki generation time** as batch operations.
Not real-time queries. Even O(n²) self-joins on association tables are
acceptable for a one-time render of a few hundred pages.

### Empty Section Suppression (General Rule)

No empty sections are rendered on any page. If a zone has no data (no
threads, no events, no patterns, etc.), the template omits it entirely.
This applies universally — the mockups show all possible zones, but the
actual rendered page only includes zones with content.

### Overflow Page Pattern (Reusable)

High-frequency entities (locations with 20+ entries, frequent people, etc.)
can generate overwhelming entry lists. Rather than truncating or requiring
DB queries (the DB is NOT user-facing), these use a **secondary overflow
page** linked from the main page:

- **Main page** stays a clean dashboard: narrative spine (Arc → Event),
  frequent people, timeline, threads
- **Overflow page** (`{Entity} — Entries.md`) carries the full hierarchical
  entry listing using the reusable Entry Listing Pattern
- Main page links to overflow: `[All 89 entries](cafe-olimpico-entries.md)`

The overflow page is generated automatically when entry count exceeds the
threshold (20 entries). Below the threshold, entries are listed directly
on the main page.

This pattern applies to:
- Location pages (20+ entries)
- Person pages (handled via the frequent tier's Arc → Event spine, with
  "Entries outside events" moving to overflow when large)

### Location Visibility Tiers

Locations range from "Home" (400+ entries) to "Random Gas Station" (1 entry).
Different tiers get different visibility:

| Entry Count | Own Page? | Listed on City Page? | Discoverable Via |
|-------------|-----------|---------------------|------------------|
| 20+         | Yes (dashboard + overflow) | Yes (top 10 per neighborhood) | City page, Entry pages |
| 3–19        | Yes (with inline entries) | Yes | City page, Entry pages |
| 1–2         | Yes (minimal page) | No | Entry pages only |

This prevents the City page from ballooning with hundreds of one-off
locations while ensuring every location has a resolvable wikilink target.

### Location Error Correction Workflow

The wiki surfaces data quality issues (duplicates, misspellings) but does
NOT handle merging or renaming. The correction path:

1. User spots "Café X" and "Cafe X" on City page
2. Clicks through to each Location page
3. Follows Entry page links (every Location page lists its entries)
4. On Entry page, follows "Edit metadata" link to the YAML source
5. Fixes the name in YAML files to use consistent spelling
6. Re-imports metadata (`plm import-metadata`)
7. Regenerates wiki (`plm wiki generate`)

Regeneration handles cleanup: locations that no longer exist in the DB
don't get pages generated. Orphaned wiki files are detected during the
diff step (rendered output vs existing files) and removed.

### City Page Neighborhood Fallback

On first wiki generation, no locations have neighborhoods assigned. The
City page uses a **conditional layout**:

- **When neighborhoods exist:** Grouped layout with `###` neighborhood
  headings, top 10 locations per neighborhood by frequency, "Other"
  bucket for uncurated locations
- **When no neighborhoods exist:** Flat frequency-sorted top-20 list
  under `## Top Locations` — no empty "Neighborhoods" section

The template checks: `{% if any_neighborhoods_in_city %}` → grouped,
`{% else %}` → flat. This ensures the City page is useful on day one
while providing incentive to curate neighborhoods via Location page editing.

### Real Data Profile (384 entries, 2021-2025)

Actual entity counts from the database (post-import):

| Entity | Count | Key Distribution |
|--------|-------|-----------------|
| Entries | 384 | 122 (2021), 49 (2022), 4 (2023), 84 (2024), 125 (2025) |
| People | 241 | 58 @ 1 entry, 110 @ 2-5, 47 @ 6-19, 14 @ 20-49, 12 @ 50+ |
| Locations | 348 | 195 @ 1 entry (56%), 286 in Montréal. Top: "Apartment - Jarry" (153) |
| Cities | 11 | Montréal (286 locs), CDMX (30), Tijuana (14), Québec (6), ... |
| Scenes | 3,097 | ~8 avg per entry, max 20 |
| Events | 1,026 | **99% single-entry** (1,015 of 1,026). 2-3 scenes avg. |
| Arcs | 33 | Biggest: "The Dating Carousel" (177 entries). 997/1026 events overlap arcs. |
| Threads | 147 | Across 84 entries. 300 entries have 0, max 6 per entry. |
| Tags | 1,834 | **79% single-use** (1,452). Top: "dating-app" (76). Long-tail problem. |
| Themes | 804 | **97% single-use** (776). Max 3 entries. Interpretive labels, not categories. |
| Motifs | 25 | 2,265 instances. Working as designed. |
| Poems | 26 | 30 versions total. Small, manageable. |
| Ref Sources | 42 | 59 references total. Small. |

**Curation gaps:** All 241 people have NULL `relation_type`. All 11 cities
have NULL `country`. Location model has no `neighborhood` column yet
(schema migration needed).

### Tag Data Quality Issue (Deferred)

Tags suffer from: no controlled vocabulary (ad-hoc per-entry creation),
format chaos (kebab-case / Title Case / plain), synonym fragmentation
("drinking" + "alcohol" + "drunk" + "alcoholism" = same concept split
across 6 tags), and moment-specific labels that aren't categories
("4AM Text", "Before Midnight").

**Deferred action:** Tag consolidation curation pass after wiki design
is finalized. The wiki designs accommodate both current messy state and
eventual clean state via:
- Visibility thresholds (1-entry tags: no page, only inline on Entry)
- Category grouping (tag_categories for index organization)
- Consolidation-friendly index structure

### Tag & Theme Visibility Tiers

| Entry Count | Own Page? | Listed on Index? | Display |
|-------------|-----------|-----------------|---------|
| 1           | No        | No              | Inline label on Entry page only |
| 2-4         | Yes (minimal — just entry links) | Yes | Simple entry list |
| 5+          | Yes (full dashboard) | Yes | Timeline, patterns, frequent people |

Themes are kept separate from tags despite similar single-use patterns.
Tags are objective (what the entry mentions), themes are interpretive
(what the entry means). Themes at 97% single-use are effectively per-entry
annotations — visible on Entry pages, minimal wiki pages when 2+.

### Co-occurrence Thresholds

- **Minimum entity count:** Don't render Patterns section if the
  entity (tag/theme/motif) has fewer than 5 entries
- **Minimum overlap:** Don't list a co-occurring tag/theme unless
  overlap >= 3 entries
- **Theme → Arc relevance:** Require at least 3 shared entries OR
  20% of the arc's total entries (whichever is lower) to list an
  arc on a Theme page

### People Scaling in Scenes

People and locations within scenes (on Event pages) use separate lines.
When a scene has many people (5+), chunk into bulleted groups of 3-4:

```markdown
**People:**
- [[Sofia]], [[Clara]], [[Majo]]
- [[Bob]], [[Alice]], [[Fernanda]]
- [[Charlie]], [[Dave]], [[Eve]]
```

Same pattern for locations when a scene spans many places:

```markdown
**[[Montreal]]:**
- [[Café Olimpico]] · [[Librairie S+M]]
- [[Parc La Fontaine]] · [[Marché Jean-Talon]]
- [[Home]]
```

For few people/locations (1-4), a single line suffices:

```markdown
**People:**
- [[Sofia]], [[Clara]]

**[[Montreal]]:** [[Home]]
```

The template always uses the bulleted list format for consistency,
regardless of count.

### Entry Listing Pattern (Reusable)

Used on Tag, Theme, Person, Location, Arc pages — anywhere entries
are listed. Hierarchical structure with conditional week grouping:

**Year** → `###` heading with total count
**Month with 8+ entries** → `####` sub-heading, entries grouped by week
**Month with <8 entries** → `**Month:**` bold label, entries inline
**Weeks with no entries** → omitted (Week 1 jumps to Week 3 if needed)

```markdown
### 2024 · 32 entries

#### November · 20 entries
**Week 1:** [[2024-11-01]] · [[2024-11-02]] · [[2024-11-04]] ·
  [[2024-11-05]]
**Week 2:** [[2024-11-08]] · [[2024-11-10]] · [[2024-11-11]] ·
  [[2024-11-12]] · [[2024-11-14]]
**Week 3:** [[2024-11-15]] · [[2024-11-18]] · [[2024-11-19]] ·
  [[2024-11-21]] · [[2024-11-22]]
**Week 4:** [[2024-11-25]] · [[2024-11-26]] · [[2024-11-28]]

**October:** [[2024-10-03]] · [[2024-10-17]]
**September:** [[2024-09-01]] · [[2024-09-14]] · [[2024-09-21]] ·
  [[2024-09-28]] · [[2024-09-30]]
**August:** [[2024-08-05]]
**June:** [[2024-06-14]]
```

### Timeline Table Pattern (Reusable)

Used on Tag, Theme, City, Arc pages — anywhere temporal distribution
matters. Shows month-by-month density as a table:

```markdown
## Timeline

| Year | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Total |
|-----:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------:|
| 2023 |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  3  |  —  |  2  |  5 |
| 2024 |  —  |  —  |  —  |  —  |  —  |  1  |  —  |  1  |  5  |  2  | **20** |  3  | 32 |
| 2025 |  3  |  7  |     |     |     |     |     |     |     |     |     |     | 10 |
```

This is the ONE place tables are justified — data is genuinely columnar.
Spikes are visually obvious (bolded high counts). Renders cleanly in both
Neovim (aligned columns) and Quartz (HTML table).

### Patterns Section (Reusable)

Used on Tag, Theme, Motif pages. Shows co-occurring entities as bulleted
wikilinked lists:

```markdown
## Patterns

**Tags:**
- [[loneliness]] (28)
- [[routine]] (22)
- [[reflection]] (15)
- [[procrastination]] (11)

**Themes:**
- [[identity]] (31)
- [[memory]] (24)
- [[solitude]] (18)
```

Section label is "Patterns" (signals self-discovery, not database dump).
Only rendered when entity has 5+ entries. Individual co-occurrences only
listed when overlap >= 3 entries.

### Frequent People Section (Reusable)

Used on Tag, Theme, Location, City, Arc pages. Bulleted list with
wikilinks and counts. **Narrator always excluded.**

```markdown
## Frequent people

- [[Majo]] (12)
- [[Clara]] (8)
- [[Bob]] (5)
```

---

## Page Inventory

### Journal Entity Pages (13 types)
| # | Page | Editable Fields | Key Question It Answers |
|---|------|----------------|------------------------|
| 1 | Entry | — | "What happened this day?" |
| 2 | Person (narrator) | relation | "Overview of my journal life" |
| 3 | Person (frequent) | relation | "Who is this person and how do they appear in my narrative?" |
| 4 | Person (infrequent) | relation | "When/where did I encounter this person?" |
| 5 | Location | neighborhood | "What happens at this place?" |
| 6 | City | country | "What is my relationship with this city?" |
| 7 | Event | — | "What scenes make up this narrative event?" |
| 8 | Arc | description | "What is this arc's narrative trajectory?" |
| 9 | Tag | — | "What entries share this tag and what patterns emerge?" |
| 10 | Theme | — | "How does this theme manifest across the journal?" |
| 11 | Poem | — | "How has this poem evolved?" |
| 12 | Reference Source | — | "How is this work referenced across the journal?" |
| 13 | Motif | — | "Where does this motif recur?" |

### Manuscript Entity Pages (4 types)
| # | Page | Editable Fields |
|---|------|----------------|
| 14 | Chapter | title, number, part, type, status, synopsis, scenes, characters, arcs, notes, references, poems |
| 15 | Character | name, description, role, is_narrator, chapters, person mappings |
| 16 | ManuscriptScene | name, description, chapter, origin, status, notes, sources |
| 17 | Part | number, title |

### Index Pages (10 types)
| # | Page | Purpose |
|---|------|---------|
| 18 | Main Index | Portal to all sections |
| 19 | People Index | All people grouped by relation |
| 20 | Places Index | Locations nested by city → neighborhood |
| 21 | Entry Index | All entries by year → month |
| 22 | Event Index | Events nested under arcs |
| 23 | Arc Index | All arcs with timeline |
| 24 | Tag & Theme Index | Frequency-sorted with co-occurrence |
| 25 | Poem Index | All poems with version counts |
| 26 | Reference Index | Sources grouped by type |
| 27 | Manuscript Index | Parts → chapters → scenes hierarchy |

---

## Journal Entity Pages — Detailed Designs

### Page 1: Entry

**Purpose:** Dashboard for a single journal day — overview and navigation.
**Read-only.** Generated from DB. Links out to source files for actual
reading and editing.

**Design rationale:** The entry page is NOT a reproduction of the journal
content. It's a metadata dashboard. The user reads the actual journal entry
via the "Read entry" link. The user edits metadata via the "Edit metadata"
link. The wiki page shows the structured relationships: who, where, what
events, what themes.

Scenes are NOT shown on entry pages. Instead, events (grouped under arcs)
link out to Event pages, which show scenes. This respects the hierarchy:
Entry → Events → Scenes, with Arcs as a grouping layer.

**Mockup:**

```markdown
# Tuesday, November 8, 2024

The entry opens with a nostalgic trigger: Bea appears on Tinder.
The narrator swipes right, but the lack of a match feels like a silent
rejection. This serves as a backdrop to the primary narrative arc
involving Clara, a French filmmaker and photographer. The narrator
recounts their "first" date, which lasted six hours and felt deeply
promising. However, current tension stems from a message left unopened
for five days.

**Rating:** [4/5](2024-11-08-rating.md)

1,247 words · 6 min read
[Read entry](../../../journal/content/md/2024/2024-11-08.md) ·
[Edit metadata](../../../narrative_analysis/2024/2024-11-08.yaml)

---

## People

**Romantic:** [[Clara Dupont]]
**Friends:** [[Majo Rodríguez]]
**Colleagues:** [[Bob Williams]]

## Places

**[[Montreal]]**

**Plateau Mont-Royal**
[[Café Olimpico]] · [[Home]]

**Mile End**
[[Fairmount Bagels]]

---

## Events

- [[The Long November]] · The Long Wanting
- [[Morning Rituals]] · The Long Wanting
- [[Family Dinner]] · Growing Up
- [[Chance Encounter]] · unlinked

---

## Threads

#### [[The Bookend Kiss]]
*Nov 8, 2024 → Dec 2024* · see [[2024-12-15]]

The greeting kiss at Jarry bookends the goodbye —
structural symmetry marking the relationship's progression.

**People:** [[Clara]]
**[[Montreal]]:** [[Station Jarry]]

---

## Themes & Tags

**Themes:** identity · memory · longing
**Tags:** writing · loneliness · routine

---

## References

> *"The body keeps the score"*
> — **The Body Keeps the Score**, van der Kolk *(direct)*

## Poems

- [[Untitled (November)]] · v2
```

**Zone breakdown:**
- **Header:** Date as `#` title, summary paragraph (100-250 words), rating,
  word count + reading time, links to source files (journal markdown and
  narrative analysis YAML).
- **People:** Grouped by relation type. Narrator excluded. Format per group:
  1-4 people = inline with mid-dots, 5+ people = bulleted list. Uses
  `display_name` for all people. Suppressed entirely if entry has only
  narrator.
- **Places:** Nested City → Neighborhood → Location when neighborhoods exist.
  Fallback: City → flat location list. Cities as bold wikilinked labels,
  neighborhoods as bold sub-labels, locations as mid-dot separated links.
- **Events:** Flat bulleted list with inline arc context:
  `[[Event]] · Arc Name` or `[[Event]] · unlinked`. Arc name plain text.
- **Threads:** Each thread as `####` wikilinked heading with full context
  (from→to dates, entry link, connection description, people, locations).
- **Themes & Tags:** Compact inline lists with mid-dot separators.
- **References:** Blockquotes with source attribution and mode. The quote
  content IS the reference metadata — not reproduction of journal content.
- **Poems:** Wikilinks with version number. Full content lives on the
  Poem page.

**What is NOT on the entry page:**
- Epigraph (it's journal content — read it in the actual entry, unless
  tracked as Reference instance)
- Scene details (drill into Event pages for scenes)
- Rating justification (on linked subpage instead, keeps dashboard clean)

**Scaling:** Entry pages are bounded by one day's data. Rarely exceeds a
screenful. No special scaling needed.

**Computed data:**
- Day of week in title (from entry_date)
- Reading time display
- Event ↔ Arc grouping (computed from shared entries)

### Entry Review Decisions

1. **Summary and rating placement:** Summary as paragraph immediately after
   title (100-250 words typical). Rating on separate line as wikilink to
   rating subpage: `**Rating:** [4/5](2024-11-08-rating.md)`. Word count and
   links below. Rating justification on linked subpage (minimal page: title,
   back-link, justification text). Subpage auto-generated when
   `rating_justification` populated.

2. **Narrator exclusion:** Narrator never appears in People section (applies
   design principle #9). If entry has only narrator → People section
   suppressed entirely. If entry has others → show only non-narrator people.

3. **People adaptive formatting:** Per relation group: 1-4 people = inline
   with mid-dots, 5+ people = bulleted list. Template checks count per group,
   not total entry count.

4. **People relation fallback:** If most people lack `relation_type` → flat
   alphabetical list. If curated → grouped by relation with "Uncategorized"
   bucket for NULLs. Same pattern as City neighborhood fallback.

5. **Places nesting:** City → Neighborhood → Location when neighborhoods
   assigned. Fallback when no neighborhoods: City → flat location list (no
   "Other" bucket on Entry pages — show ALL locations).

6. **Events format:** Flat bulleted list, NOT grouped under arc headings.
   Arc shown as inline suffix: `[[Event Name]] · Arc Name` or
   `[[Event Name]] · unlinked`. Arc name plain text (not wikilinked).

7. **Section ordering:** People → Places → Events → Threads → Themes & Tags →
   References → Poems. Threads after primary narrative structure, before
   interpretive annotations.

8. **References format:** Blockquote with mode. Direct quotes use italics +
   quotation marks. Speaker shown when present:
   `— **Speaker**, **Source Title**, Author *(mode)*`.

9. **Epigraph handling:** Only appears in References section if tracked as
   Reference instance with source metadata. Decorative epigraph text in
   markdown does not generate reference entry.

10. **AI-generated entries:** Conditional section suppression. Empty sections
    (no people, locations, events, threads) not rendered. Results in minimal
    page: summary → rating → tags/themes → poems.

---

### Page 2: Person (Narrator Tier)

**Purpose:** The user's own page — aggregate view of the entire journal.
**Editable:** `relation_type` field only.

The narrator appears in every entry. Listing entries, scenes, or locations
exhaustively is meaningless. Instead, show aggregates: who do I see most,
where do I spend time, what characters am I mapped to.

**Mockup:**

```markdown
# Sofía Fernández

**Relation:** self | **Narrator**

*Appears in all entries.*

---

## Top Companions

**Romantic:**
- [[Clara]] (89)

**Family:**
- [[Mom]] (67)
- [[Dad]] (45)
- [[Fernanda]] (38)

**Friends:**
- [[Majo]] (56)
- [[Bob]] (23)
- [[Alice]] (18)

## Top Places

**[[Montreal]]**

**Plateau Mont-Royal**
[[Home]] (412) · [[Café Olimpico]] (89)

**Mile End**
[[Fairmount Bagels]] (34) · [[Casa de Majo]] (28)

**Downtown**
[[McGill Library]] (45)

**[[Mexico City]]**

**Coyoacán**
[[Casa Azul]] (23) · [[Jardín Centenario]] (12)

---

## Characters

- [[Sofia (character)]] · primary
```

**Zone breakdown:**
- **Header:** `display_name` as `#` title, relation (editable),
  narrator flag note.
- **Top Companions:** Most frequent co-appearing people, grouped by
  relation type. Format: wikilinked name with entry count. Top 10-15.
  Computed via JOIN on entry_people for co-occurrence pairs.
- **Top Places:** Most frequent locations nested by City → Neighborhood.
  Entry frequency counts in parentheses. Top 10-15 per city.
- **Characters:** Manuscript character mappings.

**No entry lists.** No timeline. No arcs/events. The narrator's page is
pure aggregation.

**Computed data:**
- Co-appearance frequency (entry_people self-join for pairs)
- Location frequency (entry_locations + scene_locations)
- first_appearance / last_appearance

---

### Page 3: Person (Frequent Tier — 20+ entries)

**Purpose:** Who is this person and how do they weave through the narrative?
**Editable:** `relation_type` field only.
**Threshold:** 20+ entries (configurable).

**Mockup:**

```markdown
# Clara Dupont

**Relation:** romantic
89 entries · Nov 2023 – Jan 2025

---

## Arcs

### [[The Long Wanting]]
18 entries · Nov 2024 – Jan 2025

**[[The Long November]]**
*The slow accumulation of glances, texts, and near-misses*
[[2024-11-08]] · [[2024-11-15]] · [[2024-11-22]]

**[[The Goodbye]]**
*The kiss at the station that closes the arc*
[[2024-12-15]]

### [[Starting Over]]
6 entries · Feb – Mar 2025

**[[Empty Mornings]]**
*The routines that no longer include her*
[[2025-02-01]] · [[2025-02-08]]

### Unlinked events
**[[Chance Encounter]]**
[[2025-03-20]]

---

## Entries outside events

### 2024 · 5 entries
**October:** [[2024-10-30]] · [[2024-11-02]]

### 2023 · 3 entries
**December:** [[2023-12-10]]
**November:** [[2023-11-15]] · [[2023-11-22]]

---

## Places

**[[Montreal]]**

**Plateau Mont-Royal**
[[Café Olimpico]] (12) · [[Home]] (8)

**Mile End**
[[Station Jarry]] (3) · [[Casa de Majo]] (2)

---

## Companions

- [[Majo]] (34 shared)
- [[Bob]] (12 shared)
- [[Alice]] (8 shared)

---

## Characters

- [[Clara (character)]] · primary
```

**Zone breakdown:**
- **Header:** `display_name` as `#` title, relation (editable), entry
  count + date range.
- **Arcs & Events:** The narrative spine. Arcs as `###` wikilinked headings
  with entry count and date range. Events nested under arcs: bold wikilink
  + italic description + entry date links. Events without arcs under
  "Unlinked events." Leverages: Person → Scene → Event → Entry → Arc path.
- **Entries outside events:** Entries where this person appears but not
  in any event. Uses the reusable hierarchical entry listing pattern
  (year → month → optional week grouping).
- **Places:** Top locations where this person appears, nested by City →
  Neighborhood → Location with frequency counts. Via scene_people +
  scene_locations join. Top 10, with "see all" link if more exist.
- **Companions:** Other people who co-appear with this person. Wikilinked
  names with shared entry count. Top 5-10. Narrator excluded.
- **Characters:** Manuscript character mappings (if any).

**Computed data:**
- Arc participation (Person → Scene → Event → Entry → Arc path)
- Co-appearance with other people (entry_people self-join)
- Location frequency (scene_people + scene_locations join)
- first_appearance / last_appearance

---

### Page 4: Person (Infrequent Tier — <20 entries)

**Purpose:** Quick reference for occasional people.
**Editable:** `relation_type` field only.

**Mockup:**

```markdown
# Dr. Martínez García

**Relation:** professional
2 entries

---

## Entries

**2024:** [[2024-06-15]] · [[2024-09-22]]

---

## Places

**[[Montreal]]:** [[Clinique Plateau]]
```

**Zone breakdown:**
- **Header:** `display_name` as `#` title, relation (editable), entry count.
- **Entries:** Simple year-grouped list. Few enough to list directly.
- **Places:** Simple city-grouped list. No frequency counts needed.
- **Characters:** Manuscript character mappings (if any, unlikely for
  infrequent people).

No arcs, no events, no companions — insufficient data for those sections.

### Person Review Decisions

1. **Narrator identification:** Via `relation_type = RelationType.SELF`. Add
   `SELF = "self"` to `RelationType` enum + migration. Template checks
   `person.relation_type == RelationType.SELF` to switch to aggregate-only
   rendering mode.
2. **Display name:** `#` heading = `person.display_name`.
3. **NULL relation_type fallback:** Conditional layout for relation-grouped
   sections (narrator companions, People Index). If most people lack
   `relation_type` → flat frequency-sorted list. Once curated above
   threshold → grouped by relation with "Uncategorized" bucket for
   remaining NULLs. Same pattern as City neighborhood fallback.
4. **Threads on frequent tier:** Add `## Threads` section using standard
   thread display format. Placed after Companions, before Characters.
   Suppressed if no threads for this person.
5. **1-entry people get pages:** Unlike tags (1-entry = no page), every
   person gets a wiki page regardless of entry count. People are
   irreducible entities, not disposable labels.
6. **Entry count source:** Header count = `person.entry_count` (via
   `entry_people`). Places frequency = scene-level join (`scene_people ∩
   scene_locations`). Different metrics for different questions.
7. **20-entry threshold confirmed:** Consistent with Location tiers.
   Infrequent (<20) gets entry list + places. Frequent (20+) gets
   Arc → Event spine + all dashboard zones.

---

### Page 5: Location

**Purpose:** What happens at this place? Who goes here?
**Editable:** `neighborhood` field.

Three layout tiers based on entry count:

#### Location with 20+ entries (dashboard + overflow page)

The main page is a navigation dashboard. The full entry list lives on a
linked overflow page.

**Mockup (main page — `cafe-olimpico.md`):**

```markdown
# Café Olimpico

**City:** [[Montreal]]
**Neighborhood:** Plateau Mont-Royal
89 entries · Oct 2023 – Jan 2025

---

## Timeline

| Year | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Total |
|-----:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------:|
| 2023 |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  2  |  3  |  4  |  9 |
| 2024 |  5  |  4  |  6  |  3  |  5  |  4  |  3  |  5  |  6  |  4  | **12** |  5  | 62 |
| 2025 |  8  | 10  |     |     |     |     |     |     |     |     |     |     | 18 |

---

## Events here

### [[The Long Wanting]]
**[[The Long November]]**
*The slow accumulation of glances, texts, and near-misses*
[[2024-11-08]] · [[2024-11-15]]

**[[Morning Rituals]]**
*Parallel routines that almost intersect*
[[2024-11-08]] · [[2024-12-03]]

### Unlinked events
**[[Chance Encounter]]**
[[2025-03-20]]

---

## Frequent people

- [[Majo]] (34)
- [[Clara]] (28)
- [[Bob]] (15)

---

## Threads

#### [[The Bookend Kiss]]
*Nov 8, 2024 → Dec 2024* · see [[2024-12-15]]

The greeting kiss at Jarry bookends the goodbye.

**People:** [[Clara]]

---

[All 89 entries](cafe-olimpico-entries.md)
```

**Mockup (overflow page — `cafe-olimpico-entries.md`):**

```markdown
# Café Olimpico — Entries

← [[Café Olimpico]]

---

### 2025 · 18 entries

#### February · 10 entries
**Week 1:** [[2025-02-01]] · [[2025-02-03]]
**Week 2:** [[2025-02-08]] · [[2025-02-10]] · [[2025-02-14]]
**Week 3:** [[2025-02-17]] · [[2025-02-19]]
**Week 4:** [[2025-02-24]] · [[2025-02-26]] · [[2025-02-28]]

#### January · 8 entries
**Week 1:** [[2025-01-02]] · [[2025-01-05]]
**Week 2:** [[2025-01-08]] · [[2025-01-12]]
**Week 3:** [[2025-01-15]] · [[2025-01-19]]
**Week 4:** [[2025-01-25]] · [[2025-01-28]]

### 2024 · 62 entries
...
```

#### Location with 3–19 entries (inline entries)

Entries listed directly on the main page. No overflow page needed.

**Mockup:**

```markdown
# Station Jarry

**City:** [[Montreal]]
**Neighborhood:** Mile End
8 entries · Nov 2024 – Jan 2025

---

## Events here

### [[The Long Wanting]]
**[[The Goodbye]]**
*The kiss at the station that closes the arc*
[[2024-12-15]]

---

## Entries outside events

### 2024 · 5 entries
**December:** [[2024-12-03]] · [[2024-12-10]]
**November:** [[2024-11-08]] · [[2024-11-15]] · [[2024-11-22]]

### 2025 · 2 entries
**January:** [[2025-01-05]] · [[2025-01-19]]

---

## Frequent people

- [[Clara]] (6)
- [[Majo]] (3)
```

#### Location with 1–2 entries (minimal page)

Sparse page. Not listed on the City page — discoverable only via the Entry
pages that mention it.

**Mockup:**

```markdown
# Random Gas Station

**City:** [[Montreal]]
2 entries

---

## Entries

**2024:** [[2024-08-15]] · [[2024-09-22]]
```

**Zone breakdown (general):**
- **Header:** Location name, city (wikilink), neighborhood (editable),
  entry count + date range.
- **Timeline:** (20+ entries only) Month-by-month density table. Uses
  reusable timeline table pattern.
- **Events here:** Events whose scenes include this location, nested under
  arcs. Same arc → event nesting pattern as Person page. Leverages:
  Location → Scene → Event → Entry → Arc. Omitted if no events.
- **Frequent people:** Most frequent people at this location via
  scene_locations + scene_people join. Narrator excluded. Top 10-15.
  Omitted if fewer than 3 people.
- **Entries outside events / Entries:** Entry-level appearances not covered
  by events. For 20+ entry locations, this moves to the overflow page.
  For 3-19 entry locations, inline on the main page using reusable
  hierarchical entry listing pattern. For 1-2 entry locations, simple
  flat list.
- **Threads:** Threads referencing this location (via thread_locations).
  Uses standard thread display format. Omitted if none.
- **Overflow link:** (20+ entries only) Link to the full entry list page
  at the bottom.

**Entry count source:** Uses `entry_locations` association table for the
headline entry count. Scene-level data (via `scene_locations`) feeds the
"Events here" section and people frequency computations.

**Computed data:**
- Events at this location (Location → Scene → Event)
- People frequency (scene_locations + scene_people join)
- Thread appearances (thread_locations)
- Monthly entry distribution (for timeline, 20+ only)

---

### Page 6: City

**Purpose:** Overview of life in this city.
**Editable:** `country` field.

Cities can have hundreds of locations (mid-hundreds in practice). The City
page uses a conditional layout depending on whether neighborhoods have been
curated.

#### City with curated neighborhoods

**Mockup:**

```markdown
# Montreal

**Country:** Canada
523 entries · 287 locations · Oct 2023 – Jan 2025

---

## Timeline

| Year | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Total |
|-----:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------:|
| 2023 |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  | 15  | 18  | 20  |  53 |
| 2024 | 22  | 20  | 25  | 18  | 22  | 19  | 15  | 20  | 22  | 18  | **28** | 21  | 250 |
| 2025 | 25  | 22  |     |     |     |     |     |     |     |     |     |     |  47 |

---

## Neighborhoods & Locations

### Plateau Mont-Royal
- [[Home]] (412)
- [[Café Olimpico]] (89)
- [[Parc La Fontaine]] (34)
- [[Librairie S+M]] (12)
- [[Boulangerie Hof Kelsten]] (8)
... and 18 more

### Mile End
- [[Fairmount Bagels]] (34)
- [[Casa de Majo]] (28)
- [[Station Jarry]] (15)
- [[Drawn & Quarterly]] (10)
- [[Dépanneur Le Pick Up]] (7)
... and 12 more

### Downtown
- [[McGill Library]] (45)
- [[Gare Centrale]] (8)
- [[Cinéma du Parc]] (6)
... and 9 more

### Other
- [[Marché Jean-Talon]] (12)
- [[Parc Jarry]] (5)
- [[Aéroport Trudeau]] (3)
... and 34 more

---

## Frequent people

- [[Clara]] (89)
- [[Majo]] (67)
- [[Mom]] (45)
- [[Bob]] (23)

---

## Arcs & Events

### [[The Long Wanting]]
- [[The Long November]]
- [[Morning Rituals]]
- [[The Goodbye]]

### [[Starting Over]]
- [[Empty Mornings]]
```

#### City without neighborhoods (first generation)

When no locations in this city have neighborhoods assigned, the template
falls back to a flat frequency-sorted list. This is useful on day one
and incentivizes curation.

**Mockup:**

```markdown
# Montreal

**Country:** Canada
523 entries · 287 locations · Oct 2023 – Jan 2025

---

## Timeline

| Year | Jan | Feb | Mar | ... | Dec | Total |
|-----:|:---:|:---:|:---:|:---:|:---:|------:|
| 2024 | 22  | 20  | 25  | ... | 21  | 250 |
...

---

## Top Locations

- [[Home]] (412)
- [[Café Olimpico]] (89)
- [[McGill Library]] (45)
- [[Parc La Fontaine]] (34)
- [[Fairmount Bagels]] (34)
- [[Casa de Majo]] (28)
- [[Station Jarry]] (15)
- [[Marché Jean-Talon]] (12)
- [[Librairie S+M]] (12)
- [[Drawn & Quarterly]] (10)
- [[Gare Centrale]] (8)
- [[Boulangerie Hof Kelsten]] (8)
- [[Dépanneur Le Pick Up]] (7)
- [[Cinéma du Parc]] (6)
- [[Parc Jarry]] (5)
... and 272 more (3+ entries)

---

## Frequent people
...

## Arcs & Events
...
```

**Zone breakdown:**
- **Header:** City name, country (editable), entry count + location count +
  date range.
- **Timeline:** Month-by-month table showing entry density. Spikes bolded.
  Uses reusable timeline table pattern.
- **Neighborhoods & Locations (curated):** `###` headings per neighborhood.
  Top 10 locations per neighborhood by entry frequency, with "... and N
  more" suffix when more exist. Locations with fewer than 3 entries are
  excluded from the City page (they still have their own pages, discoverable
  via Entry pages). Locations without neighborhood under "Other."
- **Top Locations (fallback):** When no neighborhoods exist, flat
  frequency-sorted list of all locations with 3+ entries. Top 20 shown,
  "... and N more" suffix for the rest.
- **Frequent people:** Top people in entries mentioning this city. Narrator
  excluded. Top 10-15.
- **Arcs & Events:** Arcs with events that have scenes at locations in
  this city. Compact: arc heading → event links.

**Template conditional:** `{% if any_neighborhoods_in_city %}` → grouped
layout with neighborhood headings. `{% else %}` → flat top locations list.
Triggers as soon as ANY location in the city has a neighborhood assigned.

**Scaling:** Mid-hundreds of locations handled via:
- Neighborhood grouping (top 10 per neighborhood)
- 3-entry minimum threshold for City page listing
- "... and N more" suffixes
- 1-2 entry locations still have pages, just not listed here

**Computed data:**
- Entries per month (for timeline)
- People frequency in city entries
- Events at city locations (City → Location → Scene → Event)
- Location frequency counts (for ordering and thresholds)

---

### Page 7: Event

**Purpose:** Narrative event showing its constituent scenes across entries.
This is where scene details live — descriptions, people, locations.
**Read-only.**

**Real data:** 1,026 events. **99% are single-entry** (1,015 of 1,026).
Typical event: 1 entry, 2-3 scenes. Only 11 events span 2+ entries.
997 of 1,026 events overlap with arcs (only 29 truly unlinked).

#### Single-entry event (99% of cases)

**Mockup:**

```markdown
# The Sophie Saga Begins

**Arc:** [[The Dating Carousel]] · 4 scenes · [[2024-01-28]]

---

**The Promise Broken**
Sonny lies hungover after celebrating the narrator's medal;
unable to stop talking about Sophie, the narrator retreats to write.

**People:**
- [[Sonny]], [[Sophie]]

**[[Montréal]]:** [[Bon Délire]]

**The Match**
A name joke on Hinge, instant matching, something different
in the exchange.

**People:**
- [[Sophie]]

**The Brief First Date**
A 5 a 7 at Bar Pamplemousse before her concert; beer,
conversation about McGill and Cuba.

**People:**
- [[Sophie]]

**[[Montréal]]:** [[Station Saint-Laurent]] · [[Bar Pamplemousse]]

**The Goodbye Hug**
Walking her to the venue, she calls her friend, they embrace;
later that night, a text with a blue heart.

**People:**
- [[Sophie]]

---

## All People

- [[Sophie]] (4 scenes)
- [[Sonny]] (1 scene)

## All Places

**[[Montréal]]**
[[Bon Délire]] · [[Station Saint-Laurent]] · [[Bar Pamplemousse]]
```

#### Multi-entry event (rare — 11 cases)

Same structure, but scenes grouped under `###` entry date headings:

```markdown
# The Long November

**Arc:** [[The Long Wanting]] · 5 scenes
[[2024-11-08]] · [[2024-11-15]] · [[2024-11-22]]

---

### [[2024-11-08]] · Tuesday

**The Gray Fence**
Sofia watches Clara from the balcony as she walks past
without looking up.

**People:**
- [[Sofia]], [[Clara]]

**[[Montréal]]:** [[Home]]

**Morning Coffee**
Majo calls to debrief the weekend; the conversation
circles back to Clara.

**People:**
- [[Sofia]], [[Majo]]

**[[Montréal]]:** [[Café Olimpico]]

---

### [[2024-11-15]] · Friday

**The Text That Wasn't**
...

---

## All People
...

## All Places
...
```

**Zone breakdown:**
- **Header:** Event name, arc wikilink (computed from shared entries),
  scene count. For single-entry: entry date as wikilink. For multi-entry:
  entry dates listed inline.
- **Description:** Conditionally rendered IF Event.notes is populated.
  Currently empty for all 1,026 events — the YAML only stores `name` and
  `scenes` for events. If populated later (via wiki curation), displays
  as italic paragraph below header.
- **Scenes:** For single-entry events: scenes listed directly (no entry
  sub-heading needed). For multi-entry events: `###` entry date headings
  group scenes by entry. Scenes as **bold names** (NOT sub-headings).
  Each scene: bold name → description → people (bulleted) → locations
  (by city). Blank line between scenes.
- **All People:** Aggregate across all scenes with scene count.
  Narrator excluded.
- **All Places:** Aggregate locations, City → Location with frequency.

**Scene formatting:** Scenes use bold names rather than `####` headings
to save vertical space. For scenes with many people (5+), chunk into
bulleted groups of 3-4. For few (1-4), single bullet.

**Single-entry events still get their own page** because:
1. They are wikilink targets from Arc, Person, Location pages
2. Entry pages stay clean dashboards; scene details delegate here
3. Consistent navigation — no two rendering paths

**Computed data:**
- Arc linkage (Event → Entry → Arc, find most common arc)
- Aggregate people and locations across scenes

---

### Page 8: Arc

**Purpose:** Long narrative arc — its trajectory across time.
**Editable:** `description` field.

**Real data:** 33 arcs, ranging from 2 entries ("The Quebec Road Trip") to
177 entries ("The Dating Carousel"). 997 of 1,026 events overlap with arcs.
Since 99% of events are single-entry, event lines on the Arc page almost
always show a single date (not a range).

**Mockup:**

```markdown
# The Dating Carousel

An arc tracing the repeating patterns of app-dating,
obsessive attachment, and digital surveillance across
two years of romantic pursuits.

177 entries · Nov 2021 – Jan 2025

---

## Timeline

| Year | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Total |
|-----:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------:|
| 2021 |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  | 12  |  8  |  20 |
| 2022 |  5  |  4  |  3  |  —  |  —  |  —  |  1  |  2  |  3  |  4  |  5  |  3  |  30 |
| 2024 |  8  |  6  |  5  |  —  |  —  |  —  |  2  |  4  |  6  |  5  | **18** |  8  |  62 |
| 2025 | 12  | 10  |     |     |     |     |     |     |     |     |     |     |  22 |

---

## Events

**[[The Sophie Saga Begins]]** · Jan 28
[[2024-01-28]]

**[[Holiday Silence and Chronic Pain]]** · Jan 28
[[2024-01-28]]

**[[The Cat Emergency and Alexandra's Ghost]]** · Jan 28
[[2024-01-28]]

**[[Four Texts Too Many]]** · Jan 28
[[2024-01-28]]

...

---

## Key People

- [[Sophie]] (48)
- [[Alda]] (34)
- [[Clara]] (28)
- [[Kate]] (22)
- [[Aliza]] (18)

## Key Tags

- [[dating-app]] (65)
- [[rejection]] (14)
- [[instagram]] (12)
- [[validation-seeking]] (10)

## Key Places

**[[Montréal]]**
[[Apartment - Jarry]] (89) · [[Home]] (34) · [[Café Velours]] (8)

**[[Ciudad de México]]**
[[Casa Coyoacán]] (5)
```

**Zone breakdown:**
- **Header:** Arc name, description (editable — one of 3 editable journal
  fields), entry count + date range.
- **Timeline:** Month-by-month density table. Uses reusable timeline pattern.
  Arcs can span years, so this is essential for seeing trajectory shape.
- **Events:** Chronological by first entry date. Each event: bold wikilink +
  single date (99% of cases) or date range (rare multi-entry events).
  Entry date links below. Two-line format per event (no italic description —
  Event.notes is empty for all current data; conditionally rendered if
  populated later).
- **Key People:** Most frequent people in arc entries. Narrator excluded.
  Top 10.
- **Key Tags:** Tags co-occurring in arc entries. Wikilinked with frequency
  count. (Using tags rather than themes since themes are 97% single-use
  and would rarely co-occur meaningfully with arcs.)
- **Key Places:** Top locations in arc entries, City → Neighborhood →
  Location with frequency.

**Scaling for large arcs:** "The Dating Carousel" has 177 entries and
potentially hundreds of events. The Events section uses the same overflow
strategy: show all events inline (they're compact two-line items), but
if an arc has 50+ events, link to an overflow page
(`the-dating-carousel-events.md`).

**Computed data:**
- Events in arc (Arc → Entry ∩ Event → Entry overlap)
- People frequency (Arc → Entry → Person)
- Tag co-occurrence (Arc → Entry → Tag)
- Location frequency (Arc → Entry → Scene → Location)
- Monthly entry distribution

---

### Page 9: Tag

**Purpose:** Discover temporal and thematic patterns around a tag.
**Read-only.**

**Real data:** 1,834 tags. 1,452 (79%) appear in 1 entry only — no page
generated. 303 appear in 2-5 entries — minimal page. 79 appear in 6+
entries — full dashboard. Only 8 tags have 20+ entries.
Top: "dating-app" (76).

Three tiers matching the visibility rules in Architectural Decisions:

#### Tag with 5+ entries (full dashboard — ~79 tags)

**Mockup:**

```markdown
# writing

47 entries · Oct 2023 – Jan 2025

---

## Timeline

| Year | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec | Total |
|-----:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|------:|
| 2023 |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  —  |  3  |  —  |  2  |  5 |
| 2024 |  —  |  —  |  —  |  —  |  —  |  1  |  —  |  1  |  5  |  2  | **20** |  3  | 32 |
| 2025 |  3  |  7  |     |     |     |     |     |     |     |     |     |     | 10 |

---

## Entries

### 2025 · 10 entries

**January:** [[2025-01-05]] · [[2025-01-12]] · [[2025-01-19]]

#### February · 7 entries
**Week 1:** [[2025-02-01]] · [[2025-02-03]]
**Week 2:** [[2025-02-08]] · [[2025-02-10]] · [[2025-02-14]]
**Week 4:** [[2025-02-25]] · [[2025-02-27]]

### 2024 · 32 entries

#### November · 20 entries
**Week 1:** [[2024-11-01]] · [[2024-11-02]] · [[2024-11-04]] ·
  [[2024-11-05]]
**Week 2:** [[2024-11-08]] · [[2024-11-10]] · [[2024-11-11]] ·
  [[2024-11-12]] · [[2024-11-14]]
**Week 3:** [[2024-11-15]] · [[2024-11-18]] · [[2024-11-19]] ·
  [[2024-11-21]] · [[2024-11-22]]
**Week 4:** [[2024-11-25]] · [[2024-11-26]] · [[2024-11-28]]

**October:** [[2024-10-03]] · [[2024-10-17]]
**September:** [[2024-09-01]] · [[2024-09-14]] · [[2024-09-21]] ·
  [[2024-09-28]] · [[2024-09-30]]
**August:** [[2024-08-05]]
**June:** [[2024-06-14]]

### 2023 · 5 entries

**December:** [[2023-12-10]] · [[2023-12-25]]
**October:** [[2023-10-14]] · [[2023-10-20]] · [[2023-10-28]]

---

## Patterns

**Tags:**
- [[loneliness]] (28)
- [[routine]] (22)
- [[reflection]] (15)
- [[procrastination]] (11)

**Themes:**
- [[identity]] (31)
- [[memory]] (24)
- [[solitude]] (18)

---

## Frequent people

- [[Majo]] (12)
- [[Clara]] (8)
- [[Bob]] (5)
```

**Zone breakdown:**
- **Header:** Tag name, entry count + date range.
- **Timeline:** Month-by-month density table. Reveals temporal patterns
  (spikes, seasonal clustering).
- **Entries:** Uses reusable hierarchical entry listing pattern. Year →
  month → week (when 8+ entries in a month). Months with few entries use
  bold label + inline links.
- **Patterns:** Co-occurring tags and themes as bulleted wikilinked lists
  with overlap counts. Only shown when tag has 5+ entries. Individual
  items only listed with 3+ overlap.
- **Frequent people:** Top people in entries with this tag. Narrator
  excluded.

**Computed data:**
- Monthly entry distribution (for timeline)
- Co-occurring tags (entry_tags self-join for pairs)
- Co-occurring themes (entry_tags + entry_themes join)
- People frequency (entry_tags + entry_people join)

#### Tag with 2-4 entries (minimal — ~303 tags)

**Mockup:**

```markdown
# consumerism

3 entries

---

## Entries

- [[2024-11-22]]
- [[2024-12-15]]
- [[2025-01-05]]
```

No timeline, no patterns, no frequent people — insufficient data for
those zones. Just the header and entry list.

#### Tag with 1 entry (no page — ~1,452 tags)

No wiki page generated. Displayed only as an inline label on the Entry
page's "Themes & Tags" zone. The wikilink resolves nowhere (or to a
redirect to the Tag Index with an anchor).

---

### Page 10: Theme

**Purpose:** Interpretive annotation — what this entry means, not what
it mentions.
**Read-only.**

**Real data:** 804 themes. **97% appear in only 1 entry** (776 of 804).
Maximum is 3 entries. Themes are used as per-entry interpretive labels
(longer phrases like "Relief in Cancellation", "Art as Symptom"), not
recurring categories.

This means: no theme has enough data for a Timeline table, Patterns
section, Arcs section, or Frequent People. The Theme page is a minimal
stub for the 28 themes with 2-3 entries, and nonexistent for the 776
single-entry themes (which appear only as inline labels on Entry pages).

#### Theme with 2-3 entries

**Mockup:**

```markdown
# Self-Sabotage

3 entries

---

## Entries

- [[2024-11-08]]
- [[2024-12-03]]
- [[2025-01-15]]
```

#### Theme with 1 entry

No wiki page generated. Displayed only as an inline label on the Entry
page's "Themes & Tags" zone.

**Design rationale:** The original Theme page design (Arcs, Timeline,
Patterns, Frequent People) was based on assumed data distribution.
Real data shows themes are effectively per-entry annotations — they
capture interpretive meaning but don't recur. The wiki accommodates
this by rendering themes inline on Entry pages and generating minimal
pages only for the rare multi-entry cases.

If theme usage patterns change after tag consolidation (themes absorbing
some tag-like recurring concepts), the page template can be upgraded to
the full Tag-style dashboard. The template checks entry count and
conditionally renders zones.

---

### Page 11: Poem

**Purpose:** A poem and its evolution through versions.
**Read-only.**

**Mockup:**

```markdown
# Untitled (November)

3 versions · first appeared [[2024-11-08]]

---

## Latest Version — [[2025-01-15]]

[Read entry](../entries/2025/2025-01-15.md)

> The fence stands gray against November sky
> paint peeling where my fingers traced the wood
> she walked past without looking up — I stood
> and watched the pigeons settle, watched them fly
>
> Three months of mornings at this balcony
> three months of coffee going cold, the good
> intentions melting into if-I-could
> and would-she-notice-if-she-noticed-me

---

## Version History

### Version 2 — [[2024-12-03]]

[Read entry](../entries/2024/2024-12-03.md)

> The fence stands gray against November sky
> she walked past without looking up — I stayed
> and watched the pigeons settle, half afraid
> that if I moved the moment too would die

### Version 1 — [[2024-11-08]]

[Read entry](../entries/2024/2024-11-08.md)

> The fence stands gray
> she walks past
> I stay

---

## Chapters

- [[The Gray Fence]] · included
```

**Zone breakdown:**
- **Header:** Poem title, version count, first appearance date (wikilink).
- **Latest Version:** Full poem content in blockquote. "Read entry" link to
  the journal entry where this version appears. This is the definitive version.
- **Version History:** All prior versions in reverse chronological order.
  Each with `###` heading, "Read entry" link to the journal entry, entry date
  wikilink, and full content in blockquote. Full content for all versions —
  poems are short and versions are few, so inline display is justified.
- **Chapters:** If poem is linked to manuscript chapters (chapter_poems M2M),
  show chapter wikilinks.

**Computed data:**
- Version count, first/last appearance
- Word count and line count per version (could add if useful)

---

### Page 12: Reference Source

**Purpose:** How a referenced work appears across the journal.
**Read-only.**

**Mockup:**

```markdown
# The Body Keeps the Score

**Author:** Bessel van der Kolk
**Type:** book
5 references · Nov 2024 – Jan 2025

---

## References

### [[2025-01-15]]
> Returning to the central thesis after the arc closes
> *(thematic)*

### [[2025-01-05]]
> Sofia's physical tension as a somatic echo
> *(indirect)*

### [[2024-12-15]]
> *"Traumatized people chronically feel unsafe inside their bodies"*
> *(direct)*

### [[2024-11-22]]
> The idea of embodied memory — how the body stores what the
> mind can't articulate
> *(thematic)*

### [[2024-11-08]]
> *"The body keeps the score"*
> — **Sofia** *(direct)*

---

## Manuscript Usage

- [[The Gray Fence]] · thematic
- [[Empty Mornings]] · direct
```

**Zone breakdown:**
- **Header:** Title, author, type (book/article/film/etc.), reference count
  + date range. URL link if exists.
- **References:** Each reference instance in **reverse chronological order**
  (newest first). Entry date as `###` wikilinked heading. Content as
  blockquote: direct quotes use *quotation marks + italics* for clear visual
  distinction from paraphrases/descriptions (plain text). Mode in
  parentheses. **Speaker** shown when present (`— **Speaker Name**`).
- **Manuscript Usage:** If referenced in manuscript chapters via
  ManuscriptReference. Chapter wikilink + mode.

**A ReferenceSource without journal references** still gets a wiki page
showing the header + Manuscript Usage section. This handles works referenced
only in the manuscript (e.g., an inspiration source added directly by the
author without journaling about it).

**Computed data:**
- Reference count, date range
- Manuscript chapter references

---

### Page 13: Motif

**Purpose:** Track a recurring motif across the journal.
**Read-only.**

**Mockup:**

```markdown
# the fence

8 instances · Nov 2024 – Jan 2025

---

## Instances

### 2025 · 2 instances

**[[2025-01-19]]** — The fence reappears in a dream,
  now overgrown and impossible to see through
**[[2025-01-05]]** — Driving past a different fence
  triggers the memory

### 2024 · 6 instances

**[[2024-12-15]]** — Walking past the fence one last time
  on the way to the station
**[[2024-12-03]]** — The fence in rain, paint peeling
**[[2024-11-22]]** — Touching the fence post while waiting
**[[2024-11-15]]** — Noticing the fence has been repainted gray
**[[2024-11-08]]** — First mention: Clara walks past the
  gray fence without looking up
**[[2024-11-01]]** — The fence glimpsed from the bus

---

## Patterns

**Themes:**
- [[longing]] (6)
- [[distance]] (4)

**Motifs:**
- [[the balcony]] (5)
- [[gray]] (3)
```

**Zone breakdown:**
- **Header:** Motif name, instance count + date range.
- **Instances:** Grouped by year. Each instance: entry date wikilink (bold)
  + description. The description IS the instance's metadata (MotifInstance
  has a `description` field). Chronological within each year.
- **Patterns:** Co-occurring themes and OTHER motifs. Reveals thematic and
  symbolic clusters. Same threshold rules as Tag patterns.

**Difference from Tag:** Motif instances carry inline descriptions (the
`MotifInstance.description` field), so entries show context rather than
just date links. No timeline table needed — motifs are typically rarer
and don't have enough data density for a month-by-month table.

---

## Manuscript Entity Pages — Detailed Designs

### Page 14: Chapter

**Purpose:** The central manuscript editing page.
**Pure wiki editing.** No YAML metadata files.

**Mockup:**

```markdown
# The Gray Fence

**Number:** 3 | **Part:** [[Part I — Arrival]]
**Type:** prose | **Status:** draft

---

## Synopsis

Sofia watches Clara from the balcony, tracking the slow
accumulation of near-misses that define their early
non-relationship. The chapter interleaves three November
mornings with the same view of the same fence.

## Scenes

- [[Morning at the Fence]]
- [[The Dog Walker]]
- [[Plateau Drift]]

## Characters

- [[Sofia (character)]]
- [[Clara (character)]]

## Arcs

- [[The Long Wanting]]

## Notes

The fence is both literal and metaphorical — it separates
Sofia's balcony world from Clara's street-level life. Need
to work on the transition between scenes 1 and 3.

## References

> *"The body keeps the score"*
> — **The Body Keeps the Score**, van der Kolk *(thematic)*

## Poems

- [[Untitled (November)]]

---

## Sources

**From journal scenes:**
- [[2024-11-08]] — The Gray Fence (scene)
- [[2024-11-22]] — Plateau Drift (scene)

**From entries:**
- [[2024-11-15]] — whole entry

**From threads:**
- [[The Bookend Kiss]] ([[2024-12-15]])
```

**No YAML metadata.** Chapter defined entirely by wiki page content.

**Zone breakdown:**
- **Header:** Title from `#` heading. Metadata line: number, part (wikilink),
  type, status. All parsed from wiki.
- **Synopsis (editable):** Free prose describing chapter's narrative arc
- **Scenes (editable):** Ordered list of manuscript scenes. Added via
  `:PalimpsestAddScene` or manual editing
- **Characters (editable):** List of characters appearing. Added via
  `:PalimpsestAddCharacter` or manual editing
- **Arcs (editable):** List of narrative arcs this chapter belongs to. Added
  via `:PalimpsestAddArc` or manual editing
- **Notes (editable):** Free-form author notes, craft observations, TODOs
- **References (editable):** Blockquoted content with source attribution + mode.
  Added via `:PalimpsestAddReference` or manual editing
- **Poems (editable):** List of poems appearing in chapter. Added via
  `:PalimpsestAddPoem` or manual editing
- **Sources (generated):** Aggregated from ManuscriptScene → ManuscriptSource.
  Grouped by source type. Read-only, regenerated from DB

**Parser behavior:**
- Extracts title from `#` heading
- Parses metadata line: number (integer), part (wikilink → part ID),
  type (validates against ChapterType enum), status (validates against ChapterStatus enum)
- Reads Synopsis and Notes section content (prose)
- Parses Scenes list → manuscript_scene IDs
- Parses Characters list → character IDs
- Parses Arcs list → arc IDs
- Parses References (blockquote format)
- Parses Poems list → poem IDs
- Ignores Sources section (generated)

**Creation:** `:PalimpsestNew chapter` creates wiki page template, user edits directly.
No `:PalimpsestEdit` needed (direct wiki editing).

### Chapter Review Decisions

1. **No YAML metadata files:** All chapter metadata (title, number, part, type,
   status) is parseable from wiki header. No separate YAML files needed.
   Consistent with Character (pure wiki editing).

2. **Metadata from header line:** Parser extracts number (integer), part
   (resolves wikilink to part ID), type and status (validates against enums)
   from header metadata line. Format: `**Number:** 3 | **Part:** [[Part I]]`

3. **All relationships in wiki:** Scenes, Characters, Arcs, References, Poems
   stored as structured lists in wiki sections. Parser extracts entity IDs/slugs
   via wikilink resolution and DB lookup.

4. **Guided relationship insertion:** Special commands for adding relationships:
   - `:PalimpsestAddScene` (autocomplete manuscript scenes)
   - `:PalimpsestAddCharacter` (autocomplete characters)
   - `:PalimpsestAddArc` (autocomplete arcs)
   - `:PalimpsestAddReference` (autocomplete reference sources, prompts for quote/mode)
   - `:PalimpsestAddPoem` (autocomplete poems)

5. **Parser boundary:** Everything above final `---` is editable (title, metadata,
   synopsis, all relationship lists, notes). Sources section below `---` is
   generated (aggregated from scene sources).

6. **Scene ordering matters:** Scenes list order determines chapter structure.
   Parser preserves order (uses list position for scene sequence in chapter).

7. **Complex but unified:** Chapter is the most complex page (most editable
   sections), but keeping everything in wiki avoids context switching. All
   chapter planning happens in one document.

---

### Page 15: Character

**Purpose:** Manuscript character definition and mapping.
**Pure wiki editing.** No YAML metadata files.

**Mockup:**

```markdown
# Clara (character)

---

## Description

Clara exists mostly in absence — glimpsed through windows,
mentioned in conversations, present in the spaces between
scenes. She is less a character than a gravitational pull.

## Based On

**[[Clara Dupont]]** · primary
The central inspiration. Most scenes are drawn directly
from journal observations.

**[[Majo Rodríguez]]** · composite
Some of Clara's dialogue borrows Majo's speech patterns.

---

## Chapters

- [[The Gray Fence]] · Part I, draft
- [[The Goodbye]] · Part II, draft

## Scenes

**[[The Gray Fence]]:**
- [[Morning at the Fence]] (journaled, included)
- [[Plateau Drift]] (journaled, draft)

**[[The Goodbye]]:**
- [[Station Kiss]] (journaled, included)
```

**No YAML metadata.** Character defined entirely by wiki page content.

**Zone breakdown:**
- **Header:** Character name extracted from `#` heading. Format: `# {Name} (character)`
- **Description (editable):** Free prose describing character's narrative function
- **Based On (editable):** Person-character mappings. Added via `:PalimpsestAddBasedOn`
  or manual editing. Format: `**[[Person]]** · {contribution_type}` + optional notes
- **Chapters (generated):** From chapter_characters M2M. Chapter wikilink + part + status
- **Scenes (generated):** ManuscriptScenes where character appears, grouped by chapter

**Parser behavior:**
- Extracts character name from `#` heading
- Reads Description section content → `description` DB field
- Parses Based On section → creates PersonCharacterMap entries
- Ignores Chapters and Scenes sections (generated)

**Creation:** `:PalimpsestNew character` creates wiki page template, user edits directly.
No `:PalimpsestEdit` needed (or opens current wiki page in place).

### Character Review Decisions

1. **No YAML metadata files:** Character has no structured metadata fields beyond
   name. Role and is_narrator fields deemed redundant (all non-narrator characters
   are obviously not narrators; role categorization is reductive). Character
   defined entirely by wiki page content.

2. **Pure wiki editing:** Character pages edited directly in wiki, no floating
   window YAML editing. Name extracted from heading, description from prose
   section, person mappings from structured Based On section.

3. **Guided person mapping:** `:PalimpsestAddBasedOn` command provides DB-backed
   autocomplete for adding person-character mappings. Ensures data integrity
   (no typos, only actual journal people). Autocomplete shows display_name,
   entry count, relation type.

4. **Bidirectional linking:** `:PalimpsestLinkToCharacter` from Person pages
   creates character mappings. While reviewing journal people, mark character
   inspirations without leaving context.

5. **Parser extracts from wiki:** Character name from `#` heading (format:
   `# {Name} (character)`), description from prose section, person mappings
   from structured format (`**[[Person]]** · {contribution}`).

6. **Creation workflow:** `:PalimpsestNew character` creates wiki page template
   with editable sections. User fills name, description, adds person mappings,
   saves. Parser extracts → DB updates → page regenerates with Chapters/Scenes.

---

### Page 16: ManuscriptScene

**Purpose:** A narrative unit in the manuscript with source tracking.
**Fully editable.**

**Mockup:**

```markdown
# Morning at the Fence

**Chapter:** [[The Gray Fence]]
**Origin:** journaled | **Status:** included

---

## Description

Sofia watches from the balcony as Clara walks past the gray
fence. The scene captures the first of three November mornings
with the same view — establishing the motif of watching from
above.

## Sources

**Scene:** [[2024-11-08]] — The Gray Fence
**Entry:** [[2024-11-15]]
**Thread:** The Bookend Kiss ([[2024-12-15]])

## Notes

This scene sets up the fence motif. The physical separation
(balcony above, street below) mirrors the emotional distance.
Consider adding sensory detail — what does the November air
smell like?

---

## Context

**The Gray Fence** (journal scene, [[2024-11-08]])
Sofia watches Clara from the balcony as she walks past
without looking up.
**People:** [[Sofia]], [[Clara]]
**[[Montreal]]:** [[Home]]
```

**Zone breakdown:**
- **Header (editable):** Name, chapter (wikilink or "Unassigned"), origin +
  status.
- **Description (editable):** Free text → `description` DB field.
- **Sources (editable):** Source materials. Format depends on source_type:
  scene, entry, thread, or external.
- **Notes (editable):** Free text → `notes` DB field.
- **Context (generated):** If sourced from journal scenes, shows the
  original scene's description, people, and locations for reference.
  Read-only, regenerated from DB.

**Parser boundary:** Header through Notes are editable (above `---`).
Context is generated (below `---`).

---

### Page 17: Part

**Purpose:** Grouping of chapters into manuscript parts.
**Fully generated.** Metadata edited via YAML popup.

**Mockup:**

```markdown
# Part I: Arrival

[Edit metadata](javascript:void(0)) <!-- triggers floating window -->

---

## Chapters

**1.** [[The Gray Fence]] · prose · draft · 3 scenes · 2 characters
**2.** [[Morning Rituals]] · vignette · draft · 1 scene · 1 character
**3.** [[The Café]] · prose · draft · 4 scenes · 3 characters
```

**Compact page.** Parts are thin organizational wrappers around chapters.

**Metadata source:** `data/manuscript/parts.yaml`
```yaml
parts:
  - number: 1
    title: Arrival
  - number: 2
    title: The Middle
```

**Zone breakdown:**
- **Header:** `# Part {number}: {title}` (from YAML)
- **Edit link:** Triggers `<leader>em` → floating window with YAML
- **Chapters:** Ordered list of chapters assigned to this part. Each
  chapter: number, wikilink, type, status, scene count, character count.
  Generated from `Chapter.part_id` DB relationships.

**Page generation:** Fully auto-generated from DB. No parsing needed.
Part metadata changes via YAML floating window, chapter assignments via
Chapter pages.

---

### Page 16: ManuscriptScene

**Purpose:** A narrative unit in the manuscript with source tracking.
**Mixed:** YAML metadata + editable wiki prose sections + generated context.

**Mockup:**

```markdown
# Morning at the Fence

[Edit metadata](javascript:void(0))

**Chapter:** [[The Gray Fence]]
**Origin:** journaled | **Status:** included

---

## Description

Sofia watches from the balcony as Clara walks past the gray fence.
The scene captures the first of three November mornings with the same
view — establishing the motif of watching from above.

## Sources

**Scene:** [[2024-11-08]] — The Gray Fence
**Entry:** [[2024-11-15]]
**Thread:** The Bookend Kiss ([[2024-12-15]])

## Notes

This scene sets up the fence motif. The physical separation (balcony
above, street below) mirrors the emotional distance. Consider adding
sensory detail — what does the November air smell like?

---

## Context

**The Gray Fence** (journal scene, [[2024-11-08]])
Sofia watches Clara from the balcony as she walks past without looking up.

**People:** [[Sofia]], [[Clara]]
**[[Montreal]]:** [[Home]]
```

**Metadata source:** `data/manuscript/scenes/{slug}.yaml`
```yaml
name: Morning at the Fence
chapter_id: 3  # or slug: the-gray-fence
origin: journaled
status: included
```

**Zone breakdown:**
- **Header:** Scene name, chapter link, origin/status display (from YAML)
- **Edit link:** Triggers `:PalimpsestEdit` → floating window with YAML
- **Description (editable):** Prose section describing the scene's narrative function
- **Sources (editable):** Structured list of source materials (journal scenes, entries,
  threads, external references). Added via `:PalimpsestAddSource` or manual editing.
- **Notes (editable):** Free-form author notes, craft observations, TODOs
- **Context (generated):** If sourced from journal scene, shows original scene content
  (description, people, locations) for reference

**Parser behavior:**
- Reads Description, Sources, Notes sections (between first and second `---`)
- Parses Sources structured format: `**{Type}:** [[{date}]]( — {name})?`
- Ignores header and Context sections (generated)
- YAML parsed separately for metadata

### ManuscriptScene Review Decisions

1. **Mixed YAML + wiki pattern:** Metadata (name, chapter, origin, status) in
   YAML. Prose content (description, notes) in wiki. Sources in wiki as
   structured section (parseable format with wikilinks).

2. **Sources in wiki rationale:** Sources are documentation/notes ("how I
   wrote this"), not entity attributes. Keeping with Description and Notes
   creates unified "author workspace." Parser handles structured format.

3. **Guided source insertion:** `:PalimpsestAddSource` command provides
   DB-backed autocomplete for adding sources (entry dates, scene names,
   thread names). Inserts formatted wiki line. No manual typing/searching.

4. **Bidirectional linking:** `:PalimpsestLinkToManuscript` command from
   journal pages marks content as manuscript source. While reviewing journal,
   link to manuscript scenes without leaving context.

5. **Context section:** Generated reference showing journal scene content
   when scene is sourced from journal. Read-only, provides context for editing.
   Suppressed if scene has no journal sources.

6. **Parser boundaries:** First `---` ends header, second `---` starts
   generated sections. Everything between is editable (Description, Sources,
   Notes). Consistent with other manuscript pages.

---

### Part Review Decisions

1. **Fully generated pages:** Part pages are entirely auto-generated from DB.
   No editable/generated split. Clean, unified view.

2. **YAML metadata source:** Part number and title stored in
   `data/manuscript/parts.yaml`. Parsed separately, not extracted from wiki.

3. **Floating window editing:** Edit Part metadata via `<leader>em` keybinding
   or `:PalimpsestEditMeta` command (Palimpsest nvim plugin). Opens YAML in
   popup overlay, seamless save/close flow.

4. **Character count added:** Chapter list shows character count alongside
   scene count: `3 scenes · 2 characters`. Helps distinguish intimate vs.
   ensemble chapters.

5. **Empty parts:** Part pages render even with no chapters assigned (just
   title, empty Chapters section). Supports manuscript planning/scaffolding.

6. **Part creation:** Create parts by adding entries to `parts.yaml`. Assign
   chapters to parts via Chapter page metadata (also YAML-backed).

---

## Index Pages — Detailed Designs

### Page 18: Main Index

**Purpose:** Portal to all wiki sections.

**Mockup:**

```markdown
# Palimpsest Wiki

972 entries · 156 people · 45 locations · 12 arcs

---

## Journal

- **[[Entries|Entry Index]]** — Browse all entries by year and month
- **[[People|People Index]]** — 156 people by relationship type
- **[[Places|Places Index]]** — 45 locations across 3 cities
- **[[Events|Event Index]]** — Narrative events grouped by arc
- **[[Arcs|Arc Index]]** — 12 narrative arcs with timelines
- **[[Tags & Themes|Tag & Theme Index]]** — 89 tags, 34 themes
- **[[Poems|Poem Index]]** — 23 poems with version histories
- **[[References|Reference Index]]** — 67 referenced works

## Manuscript

- **[[Manuscript|Manuscript Index]]** — Parts, chapters, scenes
- 3 parts · 12 chapters · 34 scenes
- **Progress:** 4 draft · 6 revised · 2 final

---

## Recent Entries

- [[2025-02-06]] · 1,102w
- [[2025-02-05]] · 987w
- [[2025-02-04]] · 1,350w
- [[2025-02-03]] · 845w
- [[2025-02-02]] · 1,200w
```

---

### Page 19: People Index

**Purpose:** Find any person in the journal.

**Mockup:**

```markdown
# People

156 people

---

## Self
- [[Sofia]] (972)

## Romantic
- [[Clara]] (89)

## Family
- [[Mom]] (67)
- [[Dad]] (45)
- [[Fernanda]] (38)

## Friends
- [[Majo]] (56)
- [[Bob]] (23)
- [[Alice]] (18)
- [[Charlie]] (12)
...

## Colleagues
- [[Frank]] (15)
- [[Grace]] (8)
...

## Professional
- [[Dr. Martínez]] (2)
- [[Notary]] (1)
```

Grouped by relation type as `##` headings. Sorted by entry frequency
descending within each group. Wikilinked names with entry count.

---

### Page 20: Places Index

**Purpose:** Browse all locations geographically.

**Mockup:**

```markdown
# Places

45 locations · 3 cities

---

## [[Montreal]] · 523 entries

### Plateau Mont-Royal
- [[Home]] (412)
- [[Café Olimpico]] (89)
- [[Parc La Fontaine]] (34)

### Mile End
- [[Fairmount Bagels]] (34)
- [[Casa de Majo]] (28)

### Downtown
- [[McGill Library]] (45)

### Other
- [[Marché Jean-Talon]] (12)

---

## [[Mexico City]] · 45 entries

### Coyoacán
- [[Casa Azul]] (23)
- [[Jardín Centenario]] (12)

### Centro
- [[Palacio de Bellas Artes]] (5)

---

## [[New York]] · 8 entries

- [[Penn Station]] (3)
- [[Clara's Apartment]] (5)
```

Cities as `##` wikilinked headings with entry count. Neighborhoods as
`###` headings. Locations with entry frequency. Cities ordered by
frequency.

---

### Page 21: Entry Index

**Purpose:** Browse all entries chronologically.

**Mockup:**

```markdown
# Entries

972 entries · Oct 2023 – Feb 2025

---

## 2025 · 47 entries

### February · 6 entries
[[2025-02-06]] · 1,102w
[[2025-02-05]] · 987w
[[2025-02-04]] · 1,350w
[[2025-02-03]] · 845w
[[2025-02-02]] · 1,200w
[[2025-02-01]] · 950w

### January · 25 entries
[[2025-01-31]] · 1,100w
[[2025-01-30]] · 890w
...

---

## 2024 · 365 entries

### December · 31 entries
...
```

Years as `##` headings with count. Months as `###` headings with count.
Each entry as date wikilink + word count. One entry per line for
scannability.

---

### Page 22: Event Index

**Purpose:** Browse narrative events grouped by arc.

**Mockup:**

```markdown
# Events

87 events · 12 arcs

---

## [[The Long Wanting]] · Nov 2024 – Jan 2025

- [[The Long November]] · Nov 8 – 22 · 5 scenes
- [[Morning Rituals]] · Nov 8, Dec 3 · 3 scenes
- [[The Goodbye]] · Dec 15 · 2 scenes
- [[Empty Mornings]] · Feb 1 – 8 · 2 scenes
- [[Chance Encounter]] · Mar 20 · 1 scene

## [[Starting Over]] · Feb – Mar 2025

- [[New Routines]] · Feb 5 – 12 · 3 scenes
...

---

## Unlinked Events

- [[Family Dinner]] · Dec 25 · 3 scenes
- [[Airport Pickup]] · Nov 1 · 1 scene
```

Arcs as `##` wikilinked headings with date range. Events as bulleted
wikilinks with date range and scene count. Unlinked events in a
separate section.

---

### Page 23: Arc Index

**Purpose:** Overview of all narrative arcs.

**Mockup:**

```markdown
# Arcs

12 arcs · Oct 2023 – Feb 2025

---

**[[The Long Wanting]]** · Nov 2024 – Jan 2025 · 12 entries
An arc tracing the gravitational pull between Sofia and Clara.

**[[Starting Over]]** · Feb – Mar 2025 · 6 entries
Learning to rebuild routines without Clara.

**[[Growing Up]]** · Oct 2023 – Dec 2024 · 34 entries
The slow reckoning with adulthood and responsibility.

...
```

Arcs sorted chronologically by first entry date. Each arc: bold wikilink +
date range + entry count, description beneath (if it has one). Compact
format — one arc per 2-3 lines.

---

### Page 24: Tag & Theme Index

**Purpose:** Browse all tags and themes by frequency.

**Mockup:**

```markdown
# Tags & Themes

89 tags · 34 themes

---

## Tags

- [[writing]] (47)
- [[loneliness]] (38)
- [[routine]] (35)
- [[reflection]] (22)
- [[procrastination]] (18)
- [[insomnia]] (15)
...

## Themes

- [[identity]] (34)
- [[memory]] (28)
- [[longing]] (24)
- [[solitude]] (20)
- [[distance]] (16)
...
```

Two sections. Sorted by usage count descending. Bulleted wikilinks
with count.

---

### Page 25: Poem Index

**Purpose:** Browse all poems.

**Mockup:**

```markdown
# Poems

23 poems

---

- [[Untitled (November)]] · 3 versions · first [[2024-11-08]]
- [[The Fence]] · 2 versions · first [[2024-11-22]]
- [[Morning Song]] · 1 version · first [[2024-12-03]]
...
```

Sorted chronologically by first appearance. Each poem: wikilink + version
count + first appearance date.

---

### Page 26: Reference Index

**Purpose:** Browse all referenced works.

**Mockup:**

```markdown
# References

67 works

---

## Books

- [[The Body Keeps the Score]] by van der Kolk · 5 references
- [[In Search of Lost Time]] by Proust · 3 references
...

## Articles

- [[On Self-Respect]] by Didion · 2 references
...

## Films

- [[In the Mood for Love]] by Wong Kar-wai · 4 references
...

## Songs

- [[Skinny Love]] by Bon Iver · 1 reference
...
```

Grouped by type as `##` headings. Sorted by reference count within each
group. Each source: wikilink + author + reference count.

---

### Page 27: Manuscript Index

**Purpose:** Hierarchical overview of manuscript structure.

**Mockup:**

```markdown
# Manuscript

3 parts · 12 chapters · 34 scenes
**Progress:** 4 draft · 6 revised · 2 final

---

## [[Part I — Arrival]]

**1.** [[The Gray Fence]] · prose · draft · 3 scenes · 2 characters
**2.** [[Morning Rituals]] · vignette · draft · 1 scene · 1 character
**3.** [[The Café]] · prose · revised · 4 scenes · 3 characters

## [[Part II — The Middle]]

**4.** [[November Letters]] · prose · draft · 2 scenes · 2 characters
**5.** [[The Goodbye]] · prose · final · 3 scenes · 4 characters

---

## Unassigned Scenes

- [[Loose Fragment]] · invented · fragment
- [[The Dream]] · inferred · fragment
```

Parts as `##` wikilinked headings. Chapters under parts: number, wikilink,
type, status, scene count, character count. Progress stats in header.
Unassigned scenes in separate section.

---

## Content Source Summary

How each page type gets its data:

| Page Type | Source | Editing Method | Parser |
|-----------|--------|---------------|--------|
| **Fully Generated (journal)** | | | |
| Entry | DB → wiki | — (read-only) | None |
| Event | DB → wiki | — (read-only) | None |
| Tag, Theme, Poem, Reference, Motif | DB → wiki | — (read-only) | None |
| All Index Pages | DB → wiki | — (read-only) | None |
| **YAML Metadata (floating window)** | | | |
| Person | Per-entity YAML | `:PalimpsestEdit` | YAML loader |
| Location | Per-entity YAML | `:PalimpsestEdit` | YAML loader |
| City | Single YAML file | `:PalimpsestEdit` | YAML loader |
| Arc | Single YAML file | `:PalimpsestEdit` | YAML loader |
| Part | YAML metadata | `:PalimpsestEdit` | YAML loader |
| ManuscriptScene (metadata) | YAML metadata | `:PalimpsestEdit` | YAML loader |
| **Pure Wiki (parsed from markdown)** | | | |
| Chapter | Wiki page | Direct editing | markdown-it-py (complex) |
| Character | Wiki page | Direct editing | markdown-it-py (moderate) |
| ManuscriptScene (prose) | Wiki page | Direct editing | markdown-it-py (moderate) |

### Index Pages Review

**All 10 index pages confirmed as fully auto-generated navigation.** No editable content, pure DB views. Original designs work for both Neovim/vimwiki (primary) and Quartz static site (secondary).

**Package functions on indexes:**
- `:PalimpsestEdit` — Not applicable (nothing to edit)
- `:PalimpsestNew {type}` — Contextual on Manuscript Index (create chapter/part)
- Primary interaction: browsing via wikilinks

**Markdown-based enhancements (vimwiki-first, Quartz-compatible):**

**People Index:**
- Add co-occurrence table showing top person pairs (who appears together most)
```markdown
## Frequent Pairs

| Person 1 | Person 2 | Shared Entries |
|----------|----------|----------------|
| [[Clara Dupont]] | [[Majo Rodríguez]] | 34 |
| [[Mom]] | [[Dad]] | 28 |
```

**Manuscript Index:**
- Add progress table showing chapter status breakdown
```markdown
**Progress Summary:**

| Status | Count | Chapters |
|--------|-------|----------|
| Draft | 4 | [[Ch 1]], [[Ch 2]], [[Ch 4]], [[Ch 7]] |
| Revised | 6 | [[Ch 3]], [[Ch 5]], [[Ch 6]], [[Ch 8]], [[Ch 9]], [[Ch 10]] |
| Final | 2 | [[Ch 11]], [[Ch 12]] |
```

- Add source coverage stats
```markdown
**Journal Coverage:**
- Entries sourced: 127 / 384 (33%)
- Scenes sourced: 89 / 3,097 (3%)
- Unsourced entries: [link to filtered view]
```

**Tag & Theme Index:**
- Add co-occurrence table for top tag pairs
```markdown
## Tag Patterns

| Tag 1 | Tag 2 | Co-occurrences |
|-------|-------|----------------|
| [[loneliness]] | [[routine]] | 28 |
| [[writing]] | [[procrastination]] | 22 |
```

**Arc Index:**
- Add arc overlap table
```markdown
## Arc Overlaps

| Arc 1 | Arc 2 | Shared Entries |
|-------|-------|----------------|
| [[The Long Wanting]] | [[The Dating Carousel]] | 45 |
| [[Growing Up]] | [[The Therapy Journey]] | 12 |
```

**Design principle:** All enhancements use standard markdown (tables, lists, links). No JavaScript, no interactive elements. Must render cleanly in Neovim and Quartz. Vimwiki is primary interface; static site is bonus.

---

## Review Status

Review order (simple → complex):

**Journal (simple → complex):**
1. ✅ Tag / Theme / Motif — REVIEWED
2. ✅ Poem / Reference Source — REVIEWED
3. ✅ City / Location — REVIEWED
4. ✅ Event / Arc — REVIEWED
5. ✅ Person (3 tiers) — REVIEWED
6. ✅ Entry — REVIEWED

**Manuscript:**
7. ✅ Part — REVIEWED
8. ✅ ManuscriptScene — REVIEWED
9. ✅ Character — REVIEWED
10. ✅ Chapter — REVIEWED

**Indexes:**
11. ✅ All indexes — REVIEWED
