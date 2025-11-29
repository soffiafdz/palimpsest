# SQL ↔ Vimwiki Metadata Guide

Complete guide for using Palimpsest's bidirectional SQL database and Vimwiki export/import system.

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Wiki Structure](#wiki-structure)
4. [Entity Types](#entity-types)
   - [Entries](#entries)
   - [People](#people)
   - [Locations](#locations)
   - [Cities](#cities)
   - [Events](#events)
   - [Tags](#tags)
   - [Themes](#themes)
   - [References](#references)
   - [Poems](#poems)
5. [Editable vs Read-Only Fields](#editable-vs-read-only-fields)
6. [Wiki Formatting Rules](#wiki-formatting-rules)
7. [Manuscript Wiki](#manuscript-wiki)
8. [Complete Examples](#complete-examples)
9. [Command Reference](#command-reference)

---

## Overview

### What is the SQL↔Wiki System?

The Wiki export system generates a **Vimwiki-compatible knowledge base** from your database:

```
┌──────────────────┐         ┌──────────────────┐
│   SQL Database   │ ──────► │   Vimwiki Pages  │
│   (palimpsest.db)│ ◄────── │   (wiki/*.md)    │
└──────────────────┘         └──────────────────┘
     Structured data          Browsable wiki
     Relationships            Index pages
     Queryable                Cross-linked
```

### Two-Way Sync

**SQL → Wiki (Export):**
- Generates wiki pages for all entities
- Creates index pages
- Builds cross-links
- **Preserves user-editable fields** (notes, vignettes)

**Wiki → SQL (Import):**
- Reads edited wiki pages
- Syncs **only editable fields** back to database
- Database-computed fields remain read-only

### When to Use Wiki Export

- **Browse your journal** as a hyperlinked wiki
- **Manuscript curation** - add notes and organize themes
- **Character development** - track people appearances and relationships
- **Timeline visualization** - see events chronologically
- **Reference management** - organize citations and sources

---

## Quick Start

### Export Database to Wiki

```bash
# Export all entities to wiki
plm export-wiki all

# Export specific entity types
plm export-wiki entries
plm export-wiki people

# Force overwrite existing wiki pages
plm export-wiki all --force

# Custom wiki directory
plm export-wiki all --wiki-dir path/to/wiki/
```

### Import Edited Wiki Back to Database

```bash
# Import editable fields from all wiki pages
plm import-wiki all

# Import specific entity types
plm import-wiki people
plm import-wiki entries

# Import manuscript wiki
plm import-wiki manuscript-all

# Custom wiki directory
plm import-wiki all --wiki-dir path/to/wiki/
```

### Browse Wiki

```bash
# Open in default editor
vim wiki/index.md

# Or use Vimwiki plugin (recommended)
# :e wiki/index.md
```

---

## Wiki Structure

### Directory Layout

```
wiki/
├── index.md                   # Main index
├── entries/
│   ├── index.md              # Entries index (chronological)
│   ├── 2024/
│   │   ├── 2024-01-15.md
│   │   ├── 2024-01-16.md
│   │   └── ...
│   └── 2023/
│       └── ...
├── people/
│   ├── index.md              # People index (alphabetical)
│   ├── john-smith.md
│   ├── ana-sofia.md
│   └── ...
├── locations/
│   ├── index.md              # Locations index (by city)
│   ├── montreal/
│   │   ├── cafe-olimpico.md
│   │   └── mont-royal.md
│   └── toronto/
│       └── ...
├── cities/
│   ├── index.md
│   ├── montreal.md
│   ├── toronto.md
│   └── ...
├── events/
│   ├── index.md
│   ├── thesis-writing.md
│   ├── montreal-period.md
│   └── ...
├── tags/
│   ├── index.md
│   ├── philosophy.md
│   ├── personal.md
│   └── ...
├── themes/
│   ├── index.md
│   ├── identity.md
│   ├── relationships.md
│   └── ...
├── references/
│   ├── index.md
│   ├── hamlet.md
│   ├── being-and-nothingness.md
│   └── ...
├── poems/
│   ├── index.md
│   ├── winter-in-montreal.md
│   ├── city-symphony.md
│   └── ...
└── manuscript/
    ├── index.md
    ├── entries/
    ├── characters/
    ├── themes/
    └── ...
```

### File Naming Conventions

- **Dates:** `YYYY-MM-DD.md` (e.g., `2024-01-15.md`)
- **Names:** `lowercase-with-hyphens.md` (e.g., `john-smith.md`)
- **Multi-word:** `word1-word2-word3.md` (e.g., `cafe-olimpico.md`)
- **Special chars:** Removed or converted to hyphens

---

## Entity Types

## Entries

**Path:** `wiki/entries/{YYYY}/{YYYY-MM-DD}.md`

### Structure

```markdown
# Palimpsest — Entry

*Breadcrumbs: [[../../index.md|Home]] > [[../index.md|Entries]] > [[index.md|{YYYY}]]*

## {YYYY-MM-DD}

---

### Metadata
| Property | Value |
| --- | --- |
| **Date** | {date} |
| **Word Count** | {word_count} words |
| **Reading Time** | {reading_time} minutes |
| **Age** | {computed_age} |

### Epigraph
> {epigraph}
> — {epigraph_attribution}

### Source
[[../../../md/YYYY/YYYY-MM-DD.md|Read Full Entry]]

### People ({count})
- [[../../people/{person-slug}.md|{person_name}]] — {relation_type}

### Locations ({count})
- [[../../locations/{city}/{location-slug}.md|{location_name}]] — {city}

### Cities ({count})
- [[../../cities/{city-slug}.md|{city_name}, {country}]]

### Events ({count})
- [[../../events/{event-slug}.md|{event_name}]]

### Themes ({count})
- [[../../themes/{theme-slug}.md|{theme_name}]]

### Tags ({count})
#tag1 #tag2 #tag3

### Poems Written ({count})
- [[../../poems/{poem-slug}.md|{poem_title}]] — Revised {revision_date}

### References Cited ({count})
- [[../../references/{source-slug}.md|{source_title}]] by {author}
  > {content_preview}...

### Mentioned Dates ({count})
- {date} — {context}
  - People: {people_list}
  - Locations: {locations_list}

### Manuscript
- **Status:** {status}
- **Edited:** {yes/no}
- **Themes:** {theme1}, {theme2}, ...
- **View in Manuscript Wiki:** [[../../manuscript/entries/{YYYY-MM-DD}.md|→]]

### Navigation
- **Previous:** [[{prev_date}.md|{prev_date}]]
- **Next:** [[{next_date}.md|{next_date}]]

**Related Entries:**
- [[{related_date}.md|{related_date}]]

### Quick Summary
**Tags**: `tag1` · `tag2` · `tag3`
**Themes**: theme1 · theme2

### Notes
{user_editable_notes}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | `entries.notes` | ✅ Synced to database on import |

All other fields are **read-only** (database-computed, regenerated on export).

### Complete Example

```markdown
# Palimpsest — Entry

*Breadcrumbs: [[../../index.md|Home]] > [[../index.md|Entries]] > [[index.md|2024]]*

## 2024-01-15

---

### Metadata
| Property | Value |
| --- | --- |
| **Date** | 2024-01-15 |
| **Word Count** | 1,250 words |
| **Reading Time** | 6.2 minutes |
| **Age** | 32 years, 5 months |

### Epigraph
> In the middle of the journey of our life I found myself within a dark woods where the straight way was lost.
> — Dante, Inferno, Canto I

### Source
[[../../../md/2024/2024-01-15.md|Read Full Entry]]

### People (3)
- [[../../people/ana-sofia.md|Ana Sofía]] — Friend
- [[../../people/john-smith.md|John Smith]] — Colleague
- [[../../people/dr-martinez.md|Dr. Martinez]] — Academic Advisor

### Locations (2)
- [[../../locations/montreal/cafe-olimpico.md|Café Olimpico]] — Montreal
- [[../../locations/montreal/mont-royal.md|Mont Royal]] — Montreal

### Cities (1)
- [[../../cities/montreal.md|Montreal, Canada]]

### Events (2)
- [[../../events/thesis-writing.md|Thesis Writing]]
- [[../../events/montreal-period.md|Montreal Period]]

### Themes (3)
- [[../../themes/identity.md|Identity]]
- [[../../themes/academic-life.md|Academic Life]]
- [[../../themes/urban-isolation.md|Urban Isolation]]

### Tags (4)
#philosophy #research #personal #reflection

### Poems Written (1)
- [[../../poems/winter-in-montreal.md|Winter in Montreal]] — Revised 2024-01-15

### References Cited (2)
- [[../../references/apology.md|Apology]] by Plato
  > The unexamined life is not worth living.

- [[../../references/reasons-and-persons.md|Reasons and Persons]] by Derek Parfit
  > Discussion of personal identity and memory (paraphrased)

### Mentioned Dates (3)
- 2024-01-20 — Thesis defense at McGill campus
  - People: Dr. Smith, Dr. Johnson
  - Locations: McGill University
- 2024-01-10 — Coffee with Ana Sofía at Café Olimpico
  - People: Ana Sofía
  - Locations: Café Olimpico
- 2023-12-25 — Christmas dinner

### Manuscript
- **Status:** included
- **Edited:** Yes
- **Themes:** identity-crisis, academic-life, urban-isolation
- **View in Manuscript Wiki:** [[../../manuscript/entries/2024-01-15.md|→]]

### Navigation
- **Previous:** [[2024-01-14.md|2024-01-14]]
- **Next:** [[2024-01-16.md|2024-01-16]]

**Related Entries:**
- [[2024-01-10.md|2024-01-10]]
- [[2024-01-12.md|2024-01-12]]

### Quick Summary
**Tags**: `philosophy` · `research` · `personal` · `reflection`
**Themes**: identity · academic-life · urban-isolation

### Notes
Important entry for manuscript Chapter 3. Captures turning point in protagonist's journey. Consider expanding the conversation with Ana Sofía for manuscript version.
```

---

## People

**Path:** `wiki/people/{name-slug}.md`

### Structure

```markdown
# Palimpsest — People

*Breadcrumbs: [[../index.md|Home]] > [[index.md|People]] > {Name}*

## {Name}

### Category
{relation_type}  # e.g., Friend, Family, Fellow, Professional

### Alias
- {alias1}
- {alias2}

### Presence
- **Range:** {first_appearance_date} → {last_appearance_date}
- **Mentions:** {total_count} entries
- **First:** [[../entries/YYYY/YYYY-MM-DD.md|{date}]] — {context}
- **Last:** [[../entries/YYYY/YYYY-MM-DD.md|{date}]] — {context}

### Themes
- {theme1}
- {theme2}

### Appearances ({count})

#### {YYYY}
- **{YYYY-MM-DD}** — [[../entries/YYYY/YYYY-MM-DD.md|Entry]] — {context}
- **{YYYY-MM-DD}** — [[../entries/YYYY/YYYY-MM-DD.md|Entry]]

#### {YYYY-1}
...

### Vignettes
{wiki_only_vignettes_for_manuscript_use}

### Notes
{wiki_only_notes_not_stored_in_database}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | N/A | ❌ Wiki-only, NOT imported |
| **Vignettes** | N/A | ❌ Wiki-only, NOT imported |
| **Category** | N/A | ❌ Wiki-only, NOT imported |
| **Themes** | N/A | ❌ Wiki-only, NOT imported |

**Important:** Person wiki pages have **NO database-linked editable fields**. All fields are for your reference only (manuscript development, character notes, etc.).

### Complete Example

```markdown
# Palimpsest — People

*Breadcrumbs: [[../index.md|Home]] > [[index.md|People]] > Ana Sofía*

## Ana Sofía

### Category
Friend

### Alias
- Sofi
- AS

### Presence
- **Range:** 2023-06-15 → 2024-01-20
- **Mentions:** 47 entries
- **First:** [[../entries/2023/2023-06-15.md|2023-06-15]] — Met at philosophy conference
- **Last:** [[../entries/2024/2024-01-20.md|2024-01-20]] — Coffee at Café Olimpico

### Themes
- Identity
- Friendship
- Philosophy
- Immigrant experience

### Appearances (47)

#### 2024
- **2024-01-20** — [[../entries/2024/2024-01-20.md|Entry]] — Coffee conversation about thesis
- **2024-01-15** — [[../entries/2024/2024-01-15.md|Entry]] — Discussion about identity
- **2024-01-10** — [[../entries/2024/2024-01-10.md|Entry]] — Walk through Mile End

#### 2023
- **2023-12-25** — [[../entries/2023/2023-12-25.md|Entry]] — Christmas dinner
- **2023-12-20** — [[../entries/2023/2023-12-20.md|Entry]]
...

### Vignettes
**Physical Description:**
- Dark curly hair, always tied back
- Expressive hands when talking about philosophy
- Fond of vintage coats and scarves

**Voice & Mannerisms:**
- Alternates between Spanish and English mid-sentence
- Starts sentences with "Mira..." when making a point
- Laughs before delivering punchlines

**Relationship Arc:**
- Met at conference June 2023
- Became close friends over shared academic interests
- Confidante during thesis struggles

### Notes
Key character for manuscript. Represents the "intellectual companion" archetype. Consider developing backstory about her move from Spain. Her philosophical insights often trigger protagonist's revelations.

For manuscript: Expand café conversations, add more cultural context, develop her own subplot about adjustment to Montreal.
```

---

## Locations

**Path:** `wiki/locations/{city}/{location-slug}.md`

### Structure

```markdown
# Palimpsest — Location

*Breadcrumbs: [[../../index.md|Home]] > [[../index.md|Locations]] > [[index.md|{City}]] > {Location}*

## {Location Name}

### Location Info
- **City:** [[../../cities/{city-slug}.md|{city}, {country}]]
- **Total Visits:** {count}

### Visit History
- **First Visit:** {date}
- **Last Visit:** {date}
- **Span:** {days} days

### Timeline

#### {YYYY}
- **{YYYY-MM-DD}** — [[../../entries/YYYY/YYYY-MM-DD.md|Entry]] — {context}
- **{YYYY-MM-DD}** — [[../../entries/YYYY/YYYY-MM-DD.md|Entry]]

#### {YYYY-1}
...

### People Encountered ({count})
- [[../../people/{person-slug}.md|{person_name}]] — {visit_count} visits

### Mentioned Dates ({count})
- {date} — {context}

### Notes
{wiki_only_notes}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | N/A | ❌ Wiki-only, NOT imported |

### Complete Example

```markdown
# Palimpsest — Location

*Breadcrumbs: [[../../index.md|Home]] > [[../index.md|Locations]] > [[index.md|Montreal]] > Café Olimpico*

## Café Olimpico

### Location Info
- **City:** [[../../cities/montreal.md|Montreal, Canada]]
- **Total Visits:** 23

### Visit History
- **First Visit:** 2023-06-20
- **Last Visit:** 2024-01-20
- **Span:** 214 days

### Timeline

#### 2024
- **2024-01-20** — [[../../entries/2024/2024-01-20.md|Entry]] — Morning coffee with Ana Sofía
- **2024-01-15** — [[../../entries/2024/2024-01-15.md|Entry]] — Solo writing session
- **2024-01-10** — [[../../entries/2024/2024-01-10.md|Entry]] — Thesis work

#### 2023
- **2023-12-15** — [[../../entries/2023/2023-12-15.md|Entry]]
- **2023-12-01** — [[../../entries/2023/2023-12-01.md|Entry]]
...

### People Encountered (4)
- [[../../people/ana-sofia.md|Ana Sofía]] — 15 visits
- [[../../people/john-smith.md|John Smith]] — 5 visits
- [[../../people/alice.md|Alice]] — 2 visits
- [[../../people/bob.md|Bob]] — 1 visit

### Mentioned Dates (3)
- 2024-01-10 — Coffee with Ana Sofía
- 2023-12-15 — Study session
- 2023-11-20 — First meeting with Alice here

### Notes
**Setting for Manuscript:**
Small Italian café in Mile End. Central meeting place for protagonist and Ana Sofía. Represents intellectual community and immigrant culture in Montreal.

**Sensory Details:**
- Smell of espresso and fresh pastries
- Blue and white tiled walls
- Small marble tables, always crowded
- Italian conversations from the baristas
- Corner window seat (protagonist's favorite)

**Symbolic Meaning:**
Third space between home and university. Place of intellectual refuge and social connection. Contrast to institutional spaces of McGill.
```

---

## Cities

**Path:** `wiki/cities/{city-slug}.md`

### Structure

```markdown
# Palimpsest — City

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Cities]] > {City}*

## {City}, {Country}

### City Info
- **Country:** {country}
- **Entries:** {total_entries}
- **Locations:** {total_locations}
- **Timeline:** {first_date} → {last_date}

### Locations ({count})
- [[../locations/{city}/{location-slug}.md|{location_name}]] — {visit_count} visits

### Entries ({count})

#### {YYYY}
- [[../entries/YYYY/YYYY-MM-DD.md|YYYY-MM-DD]]

#### {YYYY-1}
...

### Notes
{wiki_only_notes}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | N/A | ❌ Wiki-only, NOT imported |

### Complete Example

```markdown
# Palimpsest — City

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Cities]] > Montreal*

## Montreal, Canada

### City Info
- **Country:** Canada
- **Entries:** 342
- **Locations:** 28
- **Timeline:** 2023-06-01 → 2024-01-20

### Locations (28)
- [[../locations/montreal/cafe-olimpico.md|Café Olimpico]] — 23 visits
- [[../locations/montreal/mont-royal.md|Mont Royal]] — 18 visits
- [[../locations/montreal/mcgill-library.md|McGill Library]] — 45 visits
- [[../locations/montreal/parc-la-fontaine.md|Parc La Fontaine]] — 12 visits
...

### Entries (342)

#### 2024
- [[../entries/2024/2024-01-20.md|2024-01-20]]
- [[../entries/2024/2024-01-19.md|2024-01-19]]
- [[../entries/2024/2024-01-18.md|2024-01-18]]
...

#### 2023
- [[../entries/2023/2023-12-31.md|2023-12-31]]
...

### Notes
**Manuscript Setting:**
Primary location for the narrative. Represents liminal space of academic life and immigrant experience. Mile End neighborhood particularly important for cultural diversity themes.

**Themes Associated:**
- Urban isolation vs. community
- Bilingualism (French/English)
- Academic institutions (McGill)
- Winter as metaphor
- Immigrant identity

**Key Locations:**
Café Olimpico (intellectual community), Mont Royal (nature/reflection), McGill (institutional constraints), Parc La Fontaine (contemplation).
```

---

## Events

**Path:** `wiki/events/{event-slug}.md`

### Structure

```markdown
# Palimpsest — Event

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Events]] > {Event}*

## {Event Display Name}

### Event Info
- **Timeline:** {first_date} → {last_date}
- **Duration:** {days} days
- **Entries:** {total_entries}

### Entries ({count})

#### {YYYY}
- [[../entries/YYYY/YYYY-MM-DD.md|YYYY-MM-DD]] — {entry_context}

#### {YYYY-1}
...

### Notes
{user_editable_notes}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | `events.notes` | ✅ Synced to database on import |

### Complete Example

```markdown
# Palimpsest — Event

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Events]] > Thesis Writing*

## Thesis Writing

### Event Info
- **Timeline:** 2023-09-01 → 2024-04-15
- **Duration:** 227 days
- **Entries:** 156

### Entries (156)

#### 2024
- [[../entries/2024/2024-01-20.md|2024-01-20]] — Chapter 3 revisions
- [[../entries/2024/2024-01-15.md|2024-01-15]] — Breakthrough on main argument
- [[../entries/2024/2024-01-10.md|2024-01-10]] — Advisor meeting
...

#### 2023
- [[../entries/2023/2023-12-31.md|2023-12-31]] — Year-end progress review
- [[../entries/2023/2023-12-15.md|2023-12-15]] — Chapter 2 complete
...

### Notes
Sofir narrative arc in manuscript. Represents protagonist's intellectual journey and struggle with identity.

**Phases:**
1. Sept-Nov 2023: Initial research and outline
2. Dec 2023: First draft crisis
3. Jan 2024: Breakthrough and revisions
4. Feb-Apr 2024: Final push to completion

**Key Moments:**
- 2024-01-15: Sofir conceptual breakthrough
- 2023-12-10: Low point, considering quitting
- 2024-03-20: Defense preparation begins

**For Manuscript:**
Structure Part 2 around this arc. Use thesis as metaphor for self-discovery. Parallel intellectual and personal growth.
```

---

## Tags

**Path:** `wiki/tags/{tag-slug}.md`

### Structure

```markdown
# Palimpsest — Tag

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Tags]] > {Tag}*

## #{Tag}

### Tag Info
- **Entries:** {total_entries}
- **Timeline:** {first_date} → {last_date}

### Entries ({count})

#### {YYYY}
- [[../entries/YYYY/YYYY-MM-DD.md|YYYY-MM-DD]]

#### {YYYY-1}
...
```

### Editable Fields

**None** - Tags have no editable fields.

### Complete Example

```markdown
# Palimpsest — Tag

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Tags]] > philosophy*

## #philosophy

### Tag Info
- **Entries:** 89
- **Timeline:** 2023-06-15 → 2024-01-20

### Entries (89)

#### 2024
- [[../entries/2024/2024-01-20.md|2024-01-20]]
- [[../entries/2024/2024-01-15.md|2024-01-15]]
...

#### 2023
- [[../entries/2023/2023-12-31.md|2023-12-31]]
...
```

---

## Themes

**Path:** `wiki/themes/{theme-slug}.md`

### Structure

```markdown
# Palimpsest — Theme

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Themes]] > {Theme}*

## {Theme}

### Theme Info
- **Entries:** {total_entries}
- **Timeline:** {first_date} → {last_date}

### Entries ({count})

#### {YYYY}
- [[../entries/YYYY/YYYY-MM-DD.md|YYYY-MM-DD]]

#### {YYYY-1}
...

### Notes
{wiki_only_notes}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | N/A | ❌ Wiki-only, NOT imported |

### Complete Example

```markdown
# Palimpsest — Theme

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Themes]] > Identity*

## Identity

### Theme Info
- **Entries:** 67
- **Timeline:** 2023-06-20 → 2024-01-20

### Entries (67)

#### 2024
- [[../entries/2024/2024-01-20.md|2024-01-20]]
- [[../entries/2024/2024-01-15.md|2024-01-15]]
...

### Notes
**Central Theme for Manuscript:**
Core exploration of personal/cultural/academic identity. Links to immigrant experience, bilingualism, academic impostor syndrome.

**Subtopics:**
- Cultural identity (Latinx in Canada)
- Academic identity (student → scholar)
- Linguistic identity (Spanish/English/French)
- Relational identity (friendship, family, romance)

**Key Entries:**
- 2024-01-15: Breakthrough realization
- 2023-11-10: Identity crisis during thesis work
- 2023-08-05: Conversation with Ana Sofía about belonging

**Development Arc:**
Early entries: confusion, fragmentation
Middle: exploration through relationships
Later: integration and acceptance
```

---

## References

**Path:** `wiki/references/{source-slug}.md`

### Structure

```markdown
# Palimpsest — References

*Breadcrumbs: [[../index.md|Home]] > [[index.md|References]] > {Source Title}*

## {Source Title}

### Source Information
- **Type:** {type}  # book, article, film, etc.
- **Author:** {author}
- **Citations:** {total_citations}

### Citations

#### [[../entries/YYYY/YYYY-MM-DD.md|{date}]]

*Mode: {mode}* • *Speaker: {speaker}*

> {citation content}

{description if paraphrase}

#### [[../entries/YYYY/YYYY-MM-DD.md|{date}]]

...

### Notes
{wiki_only_notes}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | N/A | ❌ Wiki-only, NOT imported |

### Complete Example

```markdown
# Palimpsest — References

*Breadcrumbs: [[../index.md|Home]] > [[index.md|References]] > Being and Nothingness*

## Being and Nothingness

### Source Information
- **Type:** book
- **Author:** Jean-Paul Sartre
- **Citations:** 12

### Citations

#### [[../entries/2024/2024-01-15.md|2024-01-15]]

*Mode: paraphrase*

Discussion of existential dread and the absurd. Argument that existence precedes essence and we are condemned to be free.

#### [[../entries/2024/2024-01-10.md|2024-01-10]]

*Mode: direct* • *Speaker: Sartre*

> "Man is condemned to be free; because once thrown into the world, he is responsible for everything he does."

#### [[../entries/2023/2023-12-20.md|2023-12-20]]

*Mode: indirect*

> Sartre argues that bad faith is a form of self-deception where we deny our freedom and responsibility.

...

### Notes
**Key Text for Manuscript:**
Sofir philosophical influence on protagonist. Cited frequently during thesis work on identity and freedom.

**Themes:**
- Freedom and responsibility
- Bad faith and authenticity
- Existence precedes essence

**Use in Manuscript:**
Reference when protagonist grapples with choices and identity. Contrast with Latinx cultural context (collectivism vs. individualism). Ana Sofía often challenges protagonist's Sartrean assumptions.
```

---

## Poems

**Path:** `wiki/poems/{poem-slug}.md`

### Structure

```markdown
# Palimpsest — Poem

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Poems]] > {Poem Title}*

## {Poem Title}

### Poem Info
- **Versions:** {version_count}
- **First Written:** {first_revision_date}
- **Last Revised:** {last_revision_date}

### Version History

#### Version {N} — {revision_date}
**Entry:** [[../entries/YYYY/YYYY-MM-DD.md|{date}]]
**Notes:** {version_notes}

```
{poem content}
```

#### Version {N-1} — {revision_date}
...

### Notes
{wiki_only_notes}
```

### Editable Fields

| Field | SQL Column | Import Behavior |
|-------|-----------|-----------------|
| **Notes** | N/A | ❌ Wiki-only, NOT imported |

### Complete Example

```markdown
# Palimpsest — Poem

*Breadcrumbs: [[../index.md|Home]] > [[index.md|Poems]] > Winter in Montreal*

## Winter in Montreal

### Poem Info
- **Versions:** 3
- **First Written:** 2024-01-10
- **Last Revised:** 2024-01-20

### Version History

#### Version 3 — 2024-01-20
**Entry:** [[../entries/2024/2024-01-20.md|2024-01-20]]
**Notes:** Final version, polished for publication

```
Snow falls on cobblestones,
Each flake a memory
Of winters past and yet to come.

The city sleeps beneath white silence,
Dreams of spring suspended
In the frozen breath of January.

I walk these streets alone,
My footsteps marking time
In the vast emptiness of winter.
```

#### Version 2 — 2024-01-15
**Entry:** [[../entries/2024/2024-01-15.md|2024-01-15]]
**Notes:** Second revision, improved rhythm and imagery

```
Snow on cobblestones,
Memories of winter
Past and future.

City sleeps in white,
Dreaming of spring
In January's breath.

Walking alone,
Footsteps marking
Winter's emptiness.
```

#### Version 1 — 2024-01-10
**Entry:** [[../entries/2024/2024-01-10.md|2024-01-10]]
**Notes:** First draft, rough ideas

```
Winter snow falling
On Montreal streets
Memories and dreams
```

### Notes
**For Manuscript:**
Key poem representing protagonist's emotional state during thesis work. Snow as metaphor for isolation and also beauty/contemplation.

**Development:**
- V1: Haiku-like brevity, too sparse
- V2: More developed but still compressed
- V3: Full expansion, sensory details, emotional depth

**Themes:**
- Winter/isolation
- Memory and time
- Urban landscape
- Solitude vs. loneliness

**Consider:**
Including earlier version in manuscript to show creative process? Or only final version?
```

---

## Editable vs Read-Only Fields

### Field Categories

**Database-Linked Editable Fields:**
- Synced back to database when wiki imported
- Preserve user edits
- Can be modified in wiki

**Wiki-Only Fields:**
- For manuscript development and notes
- NOT stored in database
- NOT imported back
- Preserved during wiki export

**Read-Only Fields:**
- Database-computed
- Regenerated on every export
- Manual edits will be overwritten

### Entity-by-Entity Breakdown

| Entity | Editable (DB-Linked) | Wiki-Only | Read-Only |
|--------|---------------------|-----------|-----------|
| **Entry** | `notes` | — | All metadata, relationships |
| **Event** | `notes` | — | Timeline, entry list |
| **Person** | — | `notes`, `vignettes`, `category`, `themes` | Appearances, timeline |
| **Location** | — | `notes` | Visit history, people encountered |
| **City** | — | `notes` | Entries, locations |
| **Tag** | — | — | Entry list |
| **Theme** | — | `notes` | Entry list |
| **Reference** | — | `notes` | Citations, source info |
| **Poem** | — | `notes` | Version history |

### Manuscript Entities (Special)

| Entity | Editable (DB-Linked) | Wiki-Only |
|--------|---------------------|-----------|
| **Manuscript Entry** | `notes`, `character_notes` | Structural metadata |
| **Manuscript Character** | `character_description`, `character_arc`, `voice_notes`, `appearance_notes` | — |
| **Manuscript Event** | `notes` | — |

---

## Wiki Formatting Rules

### Markdown Syntax

**Headers:**
```markdown
# Level 1 (Page Title)
## Level 2 (Main Sections)
### Level 3 (Subsections)
```

**Links:**
```markdown
# Wiki links (Vimwiki style)
[[path/to/page.md|Display Text]]

# Relative paths
[[../../people/john.md|John]]
[[../entries/2024/2024-01-15.md|2024-01-15]]

# Anchor links
[[#Section Name]]
```

**Lists:**
```markdown
# Unordered
- Item 1
- Item 2

# Ordered
1. First
2. Second
```

**Emphasis:**
```markdown
*italic*
**bold**
`code`
```

**Blockquotes:**
```markdown
> Quote text
> Multi-line quote
```

**Tables:**
```markdown
| Column 1 | Column 2 |
| --- | --- |
| Value 1 | Value 2 |
```

### Custom Conventions

**Breadcrumbs:**
```markdown
*Breadcrumbs: [[../../index.md|Home]] > [[../index.md|Section]] > Current*
```

**Tags:**
```markdown
#tag1 #tag2 #tag3
```

**Date Format:**
```markdown
YYYY-MM-DD (ISO 8601)
```

**File Slugs:**
```markdown
lowercase-with-hyphens
```

---

## Manuscript Wiki

### Overview

The manuscript wiki is a **specialized view** for developing entries into narrative:

```
wiki/manuscript/
├── index.md
├── entries/
│   ├── by-status/
│   │   ├── draft.md
│   │   ├── included.md
│   │   └── excluded.md
│   ├── by-theme/
│   │   ├── identity.md
│   │   └── relationships.md
│   └── timeline.md
├── characters/
│   ├── protagonist.md
│   ├── ana-sofia.md
│   └── ...
├── themes/
│   ├── identity.md
│   ├── urban-isolation.md
│   └── ...
└── arcs/
    ├── coming-of-age.md
    └── ...
```

### Manuscript Entry Fields

**Path:** `wiki/manuscript/entries/{YYYY}/{YYYY-MM-DD}.md`

**Editable Fields:**
- `notes` - Editorial notes for this entry
- `character_notes` - Character development notes
- `status` - draft, reviewed, included, excluded, final
- `themes` - List of manuscript themes

### Manuscript Character Fields

**Path:** `wiki/manuscript/characters/{character-slug}.md`

**Editable Fields:**
- `character_description` - Physical and personality description
- `character_arc` - Development arc across manuscript
- `voice_notes` - Dialogue and voice characteristics
- `appearance_notes` - Physical appearance details

**All of these sync back to the `manuscript_people` table.**

### Example Manuscript Entry

```markdown
# Manuscript Entry — 2024-01-15

## Status
**included** (for Chapter 3)

## Themes
- identity-crisis
- academic-life
- friendship

## Character Development
**Protagonist:**
- Sofir turning point: realizes thesis anxiety is actually identity anxiety
- Emotional arc: confusion → clarity
- Growth: begins accepting dual identity

**Ana Sofía:**
- Supporting role: wisdom figure
- Catalyst for protagonist's realization
- Relationship deepens (from acquaintance to confidante)

## Notes for Revision
- Expand café conversation scene (currently 2 paragraphs → needs 2 pages)
- Add more sensory details: smell of coffee, sound of Italian conversations
- Develop Ana Sofía's backstory subtly (reference her own immigration experience)
- Cut epigraph? Might be too on-the-nose
- Move reflection on Sartre to earlier in chapter for better flow

## Scene Structure
1. Morning walk to café (set mood, weather as metaphor)
2. Café arrival (sensory grounding)
3. Conversation with Ana Sofía (philosophical → personal)
4. Protagonist's internal realization (climax)
5. Walk home (changed perspective, same streets)

## Draft Status
- Current: First draft complete
- Next: Expand dialogue, add sensory details
- Timeline: Revise by Feb 1

## Character Notes
**Ana Sofía Development:**
- First appearance: Chapter 1 (background character)
- This entry: Becomes major supporting character
- Later: Continues as intellectual companion through end

**Voice:**
- Use more Spanish phrases in dialogue
- Emphasize hand gestures when explaining concepts
- Characteristic opening: "Mira..."
```

---

## Complete Examples

### Full Workflow Example

**1. Export database to wiki:**
```bash
plm export-wiki all
```

**2. Browse and edit in Vimwiki:**
```vim
:e wiki/index.md

# Navigate to event
:e wiki/events/thesis-writing.md

# Edit notes section
i
[Add editorial notes]
:wq
```

**3. Import edits back to database:**
```bash
plm import-wiki all
```

**4. Verify changes:**
```bash
metadb query "SELECT notes FROM events WHERE event='thesis-writing'"
```

### Manuscript Curation Workflow

**1. Export to manuscript wiki:**
```bash
plm export-wiki all  # Includes manuscript wiki
```

**2. Review entries by theme:**
```vim
:e wiki/manuscript/entries/by-theme/identity.md
```

**3. Add character notes:**
```vim
:e wiki/manuscript/characters/ana-sofia.md

# Add to character_description field
```

**4. Update entry status:**
```vim
:e wiki/manuscript/entries/2024/2024-01-15.md

# Change status: draft → included
# Add themes: identity, friendship
# Add character notes
```

**5. Import manuscript edits:**
```bash
plm import-wiki manuscript-all
```

---

## Command Reference

### Export Commands

**Basic export:**
```bash
plm export-wiki all
```

**Export specific entities:**
```bash
plm export-wiki people
plm export-wiki entries
```

**Export manuscript wiki:**
```bash
plm export-wiki all  # Includes manuscript wiki
```

**Force overwrite:**
```bash
plm export-wiki all --force
```

**Preserve existing notes:**
```bash
plm export-wiki all
```

### Import Commands

**Basic import:**
```bash
plm import-wiki all
```

**Import specific entities:**
```bash
plm import-wiki people
plm import-wiki entries
```

**Import manuscript edits:**
```bash
plm import-wiki manuscript-all
```

**Verbose output:**
```bash
plm -v import-wiki all
```

### Query Commands

**Check what's editable:**
See the "Editable vs Read-Only Fields" section in this guide.

**Preview import changes:**
```bash
# Wiki diff tool - check validate wiki --help
```

**Verify wiki structure:**
```bash
validate wiki stats  # Validate wiki pages
```

---

## Best Practices

### 1. Regular Sync Workflow

```bash
# Daily: Export latest database to wiki
plm export-wiki all

# Work in wiki, edit notes

# Daily: Import notes back
plm import-wiki all
```

### 2. Manuscript Development

```bash
# Export manuscript wiki
plm export-wiki all  # Includes manuscript wiki

# Curate entries, develop characters
# vim wiki/manuscript/...

# Import manuscript edits
plm import-wiki manuscript-all
```

### 3. Safe Editing

- **Always preview with --dry-run first**
- **Back up database before import**
- **Use version control (git) for wiki/**
- **Don't edit read-only fields** (will be overwritten)

### 4. Wiki Browsing

- Use Vimwiki plugin for best experience
- Navigate with `<CR>` on links
- Search with `/` or `:vimgrep`
- Create index pages for custom views

---

## Troubleshooting

### Wiki export overwrites my notes

**Problem:** Notes lost on re-export

**Solution:** The `plm export-wiki` command automatically preserves notes. If notes are being overwritten, it may be a bug.

### Import doesn't sync my edits

**Problem:** Edited wiki fields not importing

**Check:**
1. Are you editing **editable fields**? (See table above)
2. Did you run `wiki2sql` after editing?
3. Is the wiki structure valid?

**Debug:**
```bash
# The import command currently does not have a dry-run feature.
# You can back up your database before importing to be safe.
metadb backup --suffix pre-import
plm import-wiki all
```

### Links broken after export

**Problem:** Wiki links not working

**Cause:** File paths changed or files missing

**Fix:**
```bash
# Rebuild wiki with force
plm export-wiki all --force

# Verify structure
validate wiki stats  # Validate wiki pages
```

---

## Appendix: Editable Fields Reference

### Database-Linked (Synced on Import)

| Entity | Field | SQL Column | Notes |
|--------|-------|-----------|-------|
| Entry | `notes` | `entries.notes` | Editorial notes |
| Event | `notes` | `events.notes` | Event description |
| Manuscript Entry | `notes` | `manuscript_entries.notes` | Entry notes |
| Manuscript Entry | `character_notes` | `manuscript_entries.character_notes` | Character dev |
| Manuscript Character | `character_description` | `manuscript_people.character_description` | Physical desc |
| Manuscript Character | `character_arc` | `manuscript_people.character_arc` | Development arc |
| Manuscript Character | `voice_notes` | `manuscript_people.voice_notes` | Voice/dialogue |
| Manuscript Character | `appearance_notes` | `manuscript_people.appearance_notes` | Appearance |
| Manuscript Event | `notes` | `manuscript_events.notes` | Event notes |

### Wiki-Only (NOT Synced)

| Entity | Field | Purpose |
|--------|-------|---------|
| Person | `notes` | Character development for manuscript |
| Person | `vignettes` | Character sketches and scenes |
| Person | `category` | Manual categorization |
| Person | `themes` | Thematic associations |
| Location | `notes` | Setting descriptions |
| City | `notes` | City context and themes |
| Theme | `notes` | Theme analysis |
| Reference | `notes` | Reference context |
| Poem | `notes` | Poem analysis |

---

## Support

- **YAML↔SQL Guide:** See `../../dev-guides/technical/metadata-yaml-sql-guide.md` for database import/export
- **Examples:** See `../../../examples/` directory
- **Source Code:** Wiki generation in `dev/dataclasses/wiki_*.py`
- **Issue Tracker:** Report bugs on GitHub

---

*Last Updated: 2024-01-15*
