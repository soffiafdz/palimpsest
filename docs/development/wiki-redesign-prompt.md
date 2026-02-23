# Wiki Page Redesign — Full Context Prompt

You are redesigning the wiki page layouts for Palimpsest, a personal journal/manuscript management system. The wiki is rendered in **Vimwiki (markdown mode) inside Neovim**. Every page is auto-generated from a SQLite database via Jinja2 templates.

The current designs are bad. They treat pages as data dumps instead of tools. They ignore the constraints of the medium (monospace terminal text with syntax concealment). They produce pages that are thousands of lines long with no navigation affordances. They don't tell the user what's editable or how to edit it. They don't link to the most important things (source journal entries, metadata YAML files).

Your job: redesign every page type from first principles. Think about what the user needs to DO on each page, not what data exists.

---

## THE MEDIUM: VIMWIKI IN NEOVIM

Critical constraints you must design for:

1. **Monospace text in a terminal.** No CSS, no HTML rendering. Everything is plain markdown viewed in a text editor at ~80-120 columns wide.

2. **Syntax concealment.** Vimwiki hides link markup. A wikilink `[Léa Fournier][/journal/people/lea-fournier]` displays as just `Léa Fournier` (clickable, concealed). This means **inline wikilinks take invisible space** — the raw text is much wider than what's displayed. Any design that mixes wikilinks with inline text on the same line (like `[[Event Name]] · Arc Name`) will have unpredictable visual alignment.

3. **Tables break easily.** Markdown tables with wikilinks inside cells have mismatched column widths because the raw link text is wider than the concealed display. Avoid tables except for pure numeric data (like timeline tables where cells contain only numbers).

4. **Navigation is built-in.** Pressing Enter on a wikilink follows it. Pressing Backspace goes back. There is NO need for "← Back to Index" links — they waste space. The user navigates by following links and pressing Backspace.

5. **Scrolling is the enemy.** A 1000-line page is unusable. The user cannot see what's on the page without extensive scrolling. Keep main pages short (under ~100-150 lines) and push long lists to subpages.

6. **`:PalimpsestEdit` (`<leader>em`)** — Nvim plugin command that opens the entity's metadata YAML file in a floating window. Available on any entity page. The user needs to know this exists, but NOT via a visible link — it's a keybinding.

7. **Link format**: `[Display Text][/absolute/path]` (WikiLink1 format). This is what the `| wikilink` Jinja2 filter produces. Reference-style links like `[name][path]` also work.

---

## DATABASE SCHEMA

### Core

**Entry** — `entries` table
- `id`, `date` (unique), `file_path` (unique), `file_hash`, `metadata_hash`
- `word_count`, `reading_time` (float, minutes)
- `summary` (text, nullable), `rating` (1.0-5.0, nullable), `rating_justification` (text, nullable)
- M2M: cities, locations, people, tags, themes, arcs, events
- O2M children: scenes, threads, narrated_dates, references, poem_versions, motif_instances
- Soft-deletable

**NarratedDate** — `narrated_dates`: `date`, FK→entry

### Geography

**City** — `cities`: `name` (unique), `country` (nullable)
- O2M: locations
- M2M: entries

**Location** — `locations`: `name`, FK→city (NOT NULL). Unique on (name, city_id)
- M2M: entries, scenes, threads

### People

**Person** — `people`: `name`, `lastname` (nullable), `disambiguator` (nullable), `slug` (unique), `relation_type` (RelationType enum, nullable). Soft-deletable.
- `display_name`: "Name Lastname" or "Name (disambiguator)" or just "Name"
- M2M: entries, scenes, threads
- O2M: aliases, character_mappings
- **PersonAlias**: `alias` string, FK→person

### Simple Named Entities

**Tag** — `tags`: `name` (unique). M2M→entries.
**Theme** — `themes`: `name` (unique). M2M→entries.
**Arc** — `arcs`: `name` (unique), `description` (nullable). M2M→entries.
**Event** — `events`: `name` (unique). M2M→entries, M2M→scenes.

### Narrative Analysis

**Scene** — `scenes`: `name`, `description` (text), FK→entry. Unique on (name, entry_id).
- O2M: scene_dates
- M2M: people, locations, events

**SceneDate** — `scene_dates`: `date` (flexible: YYYY-MM-DD, YYYY-MM, YYYY, or ~prefixed), FK→scene

**Thread** — `threads`: `name`, `from_date` (flexible), `to_date` (flexible), `referenced_entry_date` (nullable), `content` (text), FK→entry. Unique on (name, entry_id).
- M2M: people, locations

### Creative

**Poem** — `poems`: `title` (unique). O2M→versions.
**PoemVersion** — `poem_versions`: `content` (text), FK→poem, FK→entry. Unique on (poem_id, entry_id).

**ReferenceSource** — `reference_sources`: `title` (unique), `author` (nullable), `type` (ReferenceType enum), `url` (nullable). O2M→references.
**Reference** — `references`: `content` (nullable), `description` (nullable), `mode` (ReferenceMode enum), FK→entry, FK→source. CHECK: content OR description must exist.

### Metadata

**Motif** — `motifs`: `name` (unique). 26 controlled-vocabulary motifs (The Anchor, The Bed, etc.). O2M→instances.
**MotifInstance** — `motif_instances`: `description` (text), FK→motif, FK→entry. Unique on (motif_id, entry_id).

### Manuscript

**Part** — `parts`: `number` (nullable, unique), `title` (nullable). O2M→chapters.
**Chapter** — `chapters`: `title` (unique), `number` (nullable), FK→part (nullable), `type` (ChapterType), `status` (ChapterStatus), `content` (nullable), `draft_path` (nullable). M2M: poems, characters, arcs. O2M: scenes, references.
**Character** — `characters`: `name` (unique), `description` (nullable), `role` (nullable), `is_narrator` (bool). M2M: chapters. O2M: person_mappings.
**PersonCharacterMap** — `person_character_map`: FK→person, FK→character, `contribution` (ContributionType), `notes` (nullable).
**ManuscriptScene** — `manuscript_scenes`: `name` (unique), `description` (nullable), FK→chapter (nullable), `origin` (SceneOrigin), `status` (SceneStatus), `notes` (nullable). O2M: sources.
**ManuscriptSource** — `manuscript_sources`: FK→manuscript_scene, `source_type` (SourceType), FK→scene (nullable), FK→entry (nullable), FK→thread (nullable), `external_note` (nullable), `notes` (nullable).
**ManuscriptReference** — `manuscript_references`: FK→chapter, FK→reference_source, `mode` (ReferenceMode), `content` (nullable), `notes` (nullable).

### Enums

**RelationType**: self, family, friend, romantic, colleague, acquaintance, professional, public, other
**ReferenceType**: book, article, film, song, podcast, interview, speech, tv_show, video, website, other
**ReferenceMode**: direct, indirect, paraphrase, visual, thematic
**ChapterType**: prose, vignette, poem
**ChapterStatus**: draft, revised, final
**SceneOrigin**: journaled, inferred, invented, composite
**SceneStatus**: fragment, draft, included, cut
**SourceType**: scene, entry, thread, external
**ContributionType**: primary, composite, inspiration

---

## METADATA SYSTEM

### Journal Entry Metadata (YAML per entry)
- Path: `data/metadata/journal/YYYY/YYYY-MM-DD.yaml`
- Contains: summary, rating, rating_justification, people, locations, cities, scenes, events, tags, themes, threads, references, poems, motifs, narrated_dates
- This is the SOURCE OF TRUTH for entry data. The DB stores it. The wiki displays it.

### Per-Entity YAML (high cardinality)
- `data/metadata/people/{slug}.yaml` — name, lastname, disambiguator, relation_type, aliases
- `data/metadata/locations/{slug}.yaml` — name, city

### Single-File YAML (low cardinality)
- `data/metadata/cities.yaml` — list of {name, country}
- `data/metadata/arcs.yaml` — list of {name, description}

### Editing Workflow
- User presses `<leader>em` on any wiki page → nvim floating window opens the corresponding YAML
- Entry page → `data/metadata/journal/YYYY/YYYY-MM-DD.yaml`
- Person page → `data/metadata/people/{slug}.yaml`
- Location page → `data/metadata/locations/{slug}.yaml`
- City page → `data/metadata/cities.yaml` (positioned at this city)
- Arc page → `data/metadata/arcs.yaml` (positioned at this arc)
- After editing YAML: `plm metadata import` → `plm wiki generate` → pages update

---

## REAL DATA PROFILE

| Entity | Count | Key Distribution |
|--------|-------|-----------------|
| Entries | 384 | 122 (2021), 49 (2022), 4 (2023), 84 (2024), 125 (2025) |
| People | 241 | 58 @ 1 entry, 110 @ 2-5, 47 @ 6-19, 14 @ 20-49, 12 @ 50+ |
| Locations | 348 | 195 @ 1 entry (56%), 286 in Montréal. Top: "Apartment - Jarry" (153) |
| Cities | 11 | Montréal (286 locs), CDMX (30), Tijuana (14), Québec (6) |
| Scenes | 3,097 | ~8 avg per entry, max 20 |
| Events | 1,026 | **99% single-entry** (1,015 of 1,026). 2-3 scenes avg. |
| Arcs | 33 | Biggest: "The Dating Carousel" (177 entries). |
| Threads | 147 | Across 84 entries. 300 entries have 0, max 6 per entry. |
| Tags | 1,834 | **79% single-use** (1,452). Top: "dating-app" (76). |
| Themes | 804 | **97% single-use** (776). Max 3 entries. |
| Motifs | 26 | 2,265 instances. |
| Poems | 26 | 30 versions total. |
| Ref Sources | 42 | 59 references total. |

**Curation gaps:** All 241 people have NULL `relation_type`. All 11 cities have NULL `country`. No `neighborhood` field on Location yet.

---

## AVAILABLE JINJA2 FILTERS

These exist in `filters.py` and can be used by templates:

- `wikilink(name, display=None)` → `[display][/resolved/path]` or `[name][]` fallback
- `entry_date_short(date_str)` → `[Mar 13][/journal/entries/2025/2025-03-13]` (month+day only, for use inside year-headed sections)
- `entry_date_display(date_str)` → `[Jun 30, 2025][/path]` (full date with year)
- `date_long(date)` → "Friday, November 8, 2024"
- `date_range(start, end)` → "Nov 2024 – Jan 2025"
- `mid_dot_join(items)` → "A · B · C"
- `adaptive_list(items, threshold=4)` → inline mid-dot if ≤4 items, bulleted list if >4
- `timeline_table(monthly_counts)` → markdown table with years as rows, months as columns, peaks bolded
- `source_path(entity_type, identifier)` → relative path to source file ("journal_md" or "metadata_yaml")
- `flexible_date_display(date_str)` → human-readable flexible date
- `thread_date_range(from_date, to_date)` → "Nov 8, 2024 → Dec 2024"
- `chunked_list(items, chunk_size=3)` → list of lists for grouped display

---

## WIKI FILE STRUCTURE

```
wiki_root/
├── index.md                              # Main portal
├── indexes/
│   ├── entry-index.md                    # Links to per-year pages
│   ├── entries-2021.md ... entries-2025.md
│   ├── people-index.md
│   ├── places-index.md
│   ├── event-index.md
│   ├── arc-index.md
│   ├── tags-index.md
│   ├── themes-index.md
│   ├── poems-index.md
│   ├── references-index.md
│   └── manuscript-index.md
├── journal/
│   ├── entries/YYYY/YYYY-MM-DD.md        # One per entry
│   ├── people/{slug}.md                  # One per person
│   ├── locations/{city_slug}/{loc_slug}.md
│   ├── cities/{slug}.md
│   ├── events/{slug}.md
│   ├── arcs/{slug}.md
│   ├── tags/{slug}.md                    # Only for usage_count >= 2
│   ├── themes/{slug}.md                  # Only for usage_count >= 2
│   ├── poems/{slug}.md
│   ├── references/{slug}.md
│   └── motifs/{slug}.md
└── manuscript/
    ├── chapters/{slug}.md
    ├── characters/{slug}.md
    └── scenes/{slug}.md
```

---

## CONTEXT DATA AVAILABLE PER PAGE TYPE

This is what the context builder provides to each template. You can use any of these fields. You can also request changes to the context builder if you need different/additional data.

### Entry Page
- `entry_date`, `date_str`, `summary`, `rating`, `rating_justification`
- `word_count`, `reading_time` (string like "5 min read")
- `people_groups`: List of {relation, names} — grouped by RelationType, narrator excluded
- `places`: List of {name (city), locations, neighborhoods} — nested
- `events`: List of {name, arc (nullable)}
- `threads`: List of {name, from_date, to_date, referenced_entry_date, content, people, locations}
- `themes`: List of {name, path}
- `tags`: List of {name, path}
- `references`: List of {content, source_title, author, mode}
- `poems`: List of {title, version (int)}
- `prev_date`, `next_date` — chronologically adjacent entries

### Person Page
- `display_name`, `slug`, `relation` (nullable), `entry_count`, `first_appearance`, `last_appearance`
- `characters`: List of {name, contribution} — manuscript mappings
- `tier`: "narrator" | "frequent" | "infrequent"

Narrator tier:
- `top_companions`: List of {relation, companions: [{name, count}]} — top 15
- `top_places`: List of {name (city), locations: [{name, count}]}

Frequent tier (20+ entries):
- `date_range`, `arc_event_spine`: List of {name (arc), entry_count, date_range, events: [{name, description, entry_dates}]}
- `entries_outside_events`: hierarchical listing
- `entry_summaries`: Dict[date_str → truncated_summary]
- `places`, `companions` (top 10), `threads`

Infrequent tier (<20 entries):
- `entries`: hierarchical listing
- `places`: simple list

### Location Page
- `name`, `city`, `entry_count`, `first_visit`, `last_visit`
- `tier`: "dashboard" | "mid" | "minimal"

Dashboard (20+): `date_range`, `timeline`, `events_here` (arc-grouped), `frequent_people`, `threads`
Mid (3-19): `events_here`, `entries_outside_events`, `frequent_people`
Minimal (<3): `entries`

### City Page
- `name`, `country`, `entry_count`, `location_count`, `date_range`, `timeline`
- `top_locations`: List of {name, entry_count} — top 20 with >=3 entries
- `frequent_people`: top 15

### Event Page
- `name`, `arc` (nullable), `scene_count`, `entry_count`
- `scenes`: List of {name, description, date, people, locations: [{city, names}], entry_date}
- `entry_dates`: sorted ISO dates

### Arc Page
- `name`, `description`, `entry_count`, `date_range`, `timeline`
- `events`: List of {name, scene_count, entry_dates}
- `frequent_people`: top 10
- `entries`: hierarchical listing

### Tag/Theme Page
- `name`, `entry_count`, `tier`: "dashboard" | "minimal"
- `entries`: hierarchical listing
- Dashboard (5+): `date_range`, `timeline`, `patterns` (co-occurring tags/themes), `frequent_people`

### Poem Page
- `title`, `version_count`, `first_appearance`, `last_appearance`
- `versions`: List of {number, entry_date, content, line_count, word_count} — newest first
- `arcs`, `themes`: sorted name lists

### Reference Source Page
- `title`, `author`, `type`, `url`, `reference_count`, `first_referenced`, `last_referenced`
- `references`: List of {entry_date, mode, content, description}

### Motif Page
- `name`, `instance_count`, `date_range`, `timeline`
- `instances`: List of {entry_date, description} — newest first

### Manuscript Pages (Chapter, Character, ManuscriptScene, Part)
- Chapter: `title`, `number`, `type`, `status`, `part`, `scene_count`, `characters`, `arcs`, `poems`, `scenes` (with sources), `references`
- Character: `name`, `description`, `role`, `is_narrator`, `chapter_count`, `chapters`, `based_on`
- Scene: `name`, `description`, `chapter`, `origin`, `status`, `sources`
- Part: `display_name`, `number`, `title`, `chapter_count`, `chapters`

---

## SUBPAGE PATTERN

The design doc specifies an overflow pattern: when an entity has too many entries to display on the main page, a subpage like `{slug}-entries.md` is generated and linked from the main page. This was never implemented but should be part of the redesign.

Candidates for subpages:
- **Entry rating**: Rating number and justification on a separate subpage, linked from entry page
- **Person entries**: Frequent people (20+ entries) should have their full entry listing on a subpage
- **Location entries**: Dashboard locations (20+ entries) should have entries on a subpage
- **Arc entries**: Large arcs should push the full entry listing to a subpage
- **Poem versions**: Full content of all versions could go on a subpage, with only the latest on the main page

---

## DESIGN FAILURES TO AVOID

1. **Data dump pages.** Don't show everything about an entity on one page. Think about what the user came here to do.

2. **No editability signals.** The user must understand what's editable and how. Entry metadata → `<leader>em` opens YAML. Person relation_type → same. But the page must hint at this.

3. **Ignoring concealment.** Wikilinks take invisible space. Don't mix them with inline text expecting alignment. Don't put them in table cells.

4. **Useless back links.** Backspace already navigates back. Don't waste lines on "← Back to Index".

5. **1000-line pages.** Person pages for frequent people, arc pages for large arcs — these become unusable scrollfests. Use subpages.

6. **Entry count at top, entries at bottom.** If you mention "89 entries", the entries should be nearby or linked, not 500 lines down.

7. **Tables with wikilinks.** Column alignment breaks. Use tables only for pure numbers.

8. **Bullets everywhere.** For small lists (1-4 items), use inline mid-dot format. Bullets for 5+. The `adaptive_list` and `mid_dot_join` filters exist for this.

9. **Missing the most important links.** Entry pages MUST link to the source journal markdown AND the metadata YAML. Entity pages must make it clear how to edit metadata.

10. **Dates without context.** Events on arc pages showing "Nov 8" without the year. Entry dates in motif pages showing ISO format instead of human-readable.

11. **No density awareness.** A person with 3 entries and a person with 300 entries should not have the same page structure.

---

## YOUR TASK

Design the layout for every page type listed above. For each page:

1. **State the primary user task** — why does someone open this page?
2. **Define the information hierarchy** — what's most important, what's secondary, what goes on subpages
3. **Show a concrete mockup** in markdown (as it would appear in the wiki, WITH wikilink syntax so concealment effects are visible)
4. **Specify the subpage strategy** — what triggers a subpage, what goes on it
5. **Note any context builder changes needed** — if you need data the context builder doesn't currently provide

Design for the REAL data profile above. Léa has 89 entries. "The Dating Carousel" has 177 entries. Montréal has 286 locations. These are the stress cases.

Page types to design:
- Entry (journal day page)
- Person (narrator / frequent / infrequent tiers)
- Location (dashboard / mid / minimal tiers)
- City
- Event
- Arc
- Tag (dashboard / minimal tiers)
- Theme (dashboard / minimal tiers)
- Motif
- Poem
- Reference Source
- Chapter (manuscript)
- Character (manuscript)
- ManuscriptScene (manuscript)
- Part (manuscript)
- All index pages
- Subpage templates (entry listing, rating, poem versions, etc.)
