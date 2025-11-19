# How to Write Vimwiki Metadata

A comprehensive, practical guide to editing metadata in your Palimpsest wiki pages.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Understanding Wiki Pages](#understanding-wiki-pages)
3. [What You Can Edit](#what-you-can-edit)
4. [Entity-by-Entity Guide](#entity-by-entity-guide)
5. [Manuscript Wiki Editing](#manuscript-wiki-editing)
6. [Best Practices](#best-practices)
7. [Common Workflows](#common-workflows)
8. [Troubleshooting](#troubleshooting)

---

## Introduction

### What is the Wiki System?

The Palimpsest wiki is a **browsable, hyperlinked version** of your journal database. Think of it as:

- **Database** = Structured, queryable data
- **Wiki** = Human-readable, browseable interface

```
Database (SQL)  →  Export  →  Wiki Pages (Markdown)
                   ←  Import ←  Edit Notes
```

### Two-Way Sync

**Export (SQL → Wiki):**
- Generates wiki pages from database
- Creates index pages and cross-links
- **Preserves your editable fields**

**Import (Wiki → SQL):**
- Reads your edits from wiki
- Syncs **only editable fields** back to database
- Everything else stays read-only

### Important Distinction

**Most wiki content is READ-ONLY:**
- Generated from database
- Overwritten on each export
- Manual edits will be lost

**Some fields are EDITABLE:**
- Preserved during export
- Synced back to database on import
- Your edits are safe

**This guide focuses on what you CAN edit.**

---

## Understanding Wiki Pages

### Wiki Structure

```
wiki/
├── entries/          # Journal entries
├── people/           # People you've mentioned
├── locations/        # Places you've been
├── cities/           # Cities tracked
├── events/           # Life events/periods
├── tags/             # Entry tags
├── themes/           # Themes tracked
├── references/       # Citations and sources
├── poems/            # Creative work
└── manuscript/       # Manuscript development
```

### Page Anatomy

Every wiki page has:

**1. Header** (Read-only)
```markdown
# Palimpsest — Entry

*Breadcrumbs: [[../../index.md|Home]] > [[../index.md|Entries]] > [[index.md|2024]]*
```

**2. Main Content** (Read-only)
```markdown
## 2024-01-15

### Metadata
| Property | Value |
| --- | --- |
| **Date** | 2024-01-15 |
...
```

**3. Editable Sections** (Can edit!)
```markdown
### Notes
{your notes here}
```

**Always check which sections are editable!**

---

## What You Can Edit

### Database-Linked Fields (Synced Back)

These sync to the database when you import:

| Entity | Editable Field | Database Table |
|--------|---------------|----------------|
| **Entry** | Notes section | `entries.notes` |
| **Event** | Notes section | `events.notes` |
| **Manuscript Entry** | Notes, Character Notes | `manuscript_entries.*` |
| **Manuscript Character** | Character Description, Arc, Voice, Appearance | `manuscript_people.*` |

### Wiki-Only Fields (NOT Synced)

These are for your reference only (manuscript development):

| Entity | Wiki-Only Fields |
|--------|-----------------|
| **Person** | Notes, Vignettes, Category, Themes |
| **Location** | Notes |
| **City** | Notes |
| **Theme** | Notes |
| **Reference** | Notes |
| **Poem** | Notes |

**Important:** Wiki-only notes are preserved during export but NOT synced to database.

### How to Tell What's Editable

**Look for these section headers:**

```markdown
### Notes
```

**In manuscript wiki:**
```markdown
### Character Development
### Editorial Notes
### Character Description
### Voice Notes
```

**Everything else is read-only.**

---

## Entity-by-Entity Guide

## Entries

**Path:** `wiki/entries/YYYY/YYYY-MM-DD.md`

### What You Can Edit

**1. Notes Section** (synced to database)

```markdown
### Notes
Your editorial notes here.
Can be multiple lines.
Preserved and synced to database.
```

### What You Cannot Edit

Everything else:
- Metadata table
- People list
- Locations list
- Tags
- References
- All relationship data

**These are regenerated from database on export.**

### How to Edit Entry Notes

**1. Open the entry:**
```bash
vim wiki/entries/2024/2024-01-15.md
```

**2. Scroll to Notes section:**
```markdown
### Notes
```

**3. Edit the content:**
```markdown
### Notes
Important entry for Chapter 3 of manuscript.
Captures breakthrough moment.
Reference when working on protagonist's identity arc.
```

**4. Save the file**

**5. Import to sync to database:**
```bash
palimpsest wiki2sql --input wiki/
```

### Example Entry Notes

**Simple note:**
```markdown
### Notes
Key conversation with María José about identity.
```

**Detailed note:**
```markdown
### Notes
Important entry for manuscript Chapter 3.

Themes:
- Identity crisis
- Friendship as catalyst
- Academic pressure

To expand:
- More dialogue with María José
- Add sensory details about café
- Connect to December 25 entry

Cross-reference: Related to entries from Jan 10 and Jan 12.
```

**Manuscript note:**
```markdown
### Notes
CHAPTER 3 CLIMAX

This is the turning point where protagonist realizes thesis anxiety
is actually identity anxiety.

Structure for manuscript:
1. Morning routine (establish normalcy)
2. Café scene with María José (catalyst)
3. Walk to Mont Royal (physical journey = mental journey)
4. Revelation at summit (breakthrough)

Needs expansion:
- Dialogue currently 2 paragraphs → should be 2 pages
- Add more of María José's wisdom
- Sensory details: cold air, city sounds, light quality
- Internal monologue during walk

Compare to:
- Dec 25 entry (family crisis sets up this moment)
- Jan 10 entry (first hint of the realization)
```

**Quick reference note:**
```markdown
### Notes
Good quote here for thesis introduction.
Contains Plato reference I need to cite.
```

### Tips for Entry Notes

**Use notes for:**
- Manuscript development
- Cross-references to other entries
- Reminders for later
- Editorial comments
- Research references

**Don't use notes for:**
- Metadata (use YAML frontmatter)
- Content (write in entry body)
- Relationship data (tracked automatically)

---

## Events

**Path:** `wiki/events/{event-slug}.md`

### What You Can Edit

**Notes Section** (synced to database)

```markdown
### Notes
Your notes about this event/period.
Synced to events.notes in database.
```

### What You Cannot Edit

- Timeline dates
- Entry list
- All computed data

### How to Edit Event Notes

**1. Open the event page:**
```bash
vim wiki/events/thesis-writing.md
```

**2. Find Notes section:**
```markdown
### Notes
```

**3. Add your notes:**
```markdown
### Notes
Major narrative arc in manuscript.

Phases:
1. Sept-Nov 2023: Initial research and outline
2. Dec 2023: Crisis period (doubts, writer's block)
3. Jan 2024: Breakthrough and rapid progress
4. Feb-Apr 2024: Final push to completion

Key moments:
- Jan 15: Major conceptual breakthrough
- Dec 10: Low point, almost quit
- Mar 20: Defense preparation begins

For manuscript:
Structure Part 2 around this arc.
Use thesis as metaphor for self-discovery.
Parallel intellectual and personal growth.

Character development:
- Protagonist evolves from student to scholar
- Relationships tested by pressure
- Identity questions surface through academic work
```

**4. Save and import:**
```bash
palimpsest wiki2sql --entities events --input wiki/
```

### Example Event Notes

**Life period:**
```markdown
### Notes
The Montreal period (June 2023 - April 2024)

Major transition: from visitor to resident
Central to narrative identity arc
Key relationships formed: María José, academic community

Themes:
- Immigrant experience
- Academic identity formation
- Urban isolation vs community
- Bilingualism and cultural negotiation

For manuscript:
Setting for Parts 2-3
Use winter as metaphor for isolation
Spring represents emergence/transformation
```

**Project:**
```markdown
### Notes
Poetry workshop at community center.

Weekly meetings, diverse group.
Led to several finished poems.
Important for creative confidence.

For manuscript:
Minor subplot
Contrast to academic pressure
Shows protagonist's creative side
```

**Situation:**
```markdown
### Notes
Post-breakup period.

Difficult time but ultimately transformative.
Entries are raw and honest.
Some might be too personal for manuscript.

Review entries carefully.
Consider composite character instead of real person.
Focus on emotional truth, not literal events.
```

---

## People

**Path:** `wiki/people/{name-slug}.md`

### What You Can Edit (Wiki-Only - NOT Synced!)

**All fields in people pages are wiki-only:**
- Notes
- Vignettes
- Category
- Themes

**These are preserved during export but NOT imported to database.**

**Why?** People metadata is for **manuscript development**, not database tracking.

### Editable Sections

**1. Category**
```markdown
### Category
Friend
```

**2. Themes**
```markdown
### Themes
- Identity
- Friendship
- Philosophy
- Immigrant experience
```

**3. Vignettes**
```markdown
### Vignettes
Physical description, character sketches, scenes for manuscript.
```

**4. Notes**
```markdown
### Notes
Character development notes for manuscript.
```

### How to Edit Person Pages

**1. Open person page:**
```bash
vim wiki/people/maria-jose.md
```

**2. Edit vignettes section:**
```markdown
### Vignettes

**Physical Description:**
- Late 20s, dark curly hair usually tied back
- Expressive hands when talking about philosophy
- Fond of vintage coats and scarves
- Warm brown eyes that light up when debating ideas

**Voice and Mannerisms:**
- Alternates between Spanish and English mid-sentence
- Starts philosophical points with "Mira..." (Look...)
- Laughs before delivering punchlines
- Uses hand gestures for emphasis
- Thoughtful pauses before deep responses

**Characteristic Scenes:**

*Café conversations:*
Always orders a cortado. Sits by the window. Pulls out a worn
notebook when making a point. Draws diagrams to explain concepts.

*Walking and talking:*
Prefers to discuss serious topics while walking. Says movement
helps her think. Often suggests walking to Mont Royal when the
conversation gets deep.

**Relationship Arc:**

*Initial meeting (June 2023):*
At philosophy conference. Immediate intellectual connection.
Exchanged numbers, promised to meet up in Montreal.

*Building friendship (Summer-Fall 2023):*
Weekly café meetings. Discussing papers, life, identity.
Became close confidante.

*Deepening bond (Winter 2024):*
Essential support during thesis crisis. Her wisdom catalyzed
key breakthrough. Relationship evolved from friendly acquaintance
to deep friendship.

**Symbolic Role:**
Represents wisdom, cultural bridge, intellectual companion.
Serves as mirror/catalyst for protagonist's self-discovery.
```

**3. Edit notes section:**
```markdown
### Notes

**For Manuscript:**

Key supporting character. Represents the "wise friend" archetype
but avoid making her a magical minority/exotic other trope.

*Development needed:*
- More of her own story (immigration from Spain)
- Her own struggles and complexity
- Not just support for protagonist's journey
- Give her agency and arc

*Voice:*
Blend of Spanish and English. Philosophical but grounded.
Warm but intellectually rigorous. Patient with protagonist's
confusion.

*Key scenes to develop:*
1. First meeting at conference (June 15, 2023)
2. First café conversation (June 20)
3. Christmas dinner invitation (Dec 25)
4. Breakthrough conversation (Jan 15, 2024)
5. Thesis defense attendance (Jan 20)

*Themes associated:*
- Friendship as wisdom
- Cross-cultural understanding
- Intellectual companionship
- Identity exploration
- Philosophy in practice (not just theory)

*Character function:*
- Catalyst for protagonist's growth
- Mirror for self-examination
- Voice of grounded wisdom
- Representation of belonging/community

*Potential issues:*
- Avoid "wise Latina" stereotype
- Give her full dimensionality
- Show her flaws and struggles
- Balance supporting role with own character arc

*Questions to develop:*
- What is she struggling with?
- What does she want?
- What does she fear?
- How does protagonist help her? (not just one-way)
```

**4. Save (no import needed - wiki-only)**

### Example Person Pages

**Main character:**
```markdown
### Category
Friend / Mentor

### Themes
- Wisdom
- Cross-cultural identity
- Philosophy
- Friendship

### Vignettes

**First Impression:**
Met at conference. Presenting on Sartre. Sharp questions from
audience. Afterward, approached her. She smiled and said, "You
look like you actually want to discuss this, not just debate."

**Physical Details:**
- 28 years old
- From Barcelona originally
- Curly dark hair (always in a bun when working)
- Wears vintage leather jacket
- Colorful scarves (one for every mood, she jokes)
- Silver rings on both hands

**Dialogue Patterns:**
"Mira, the thing is..." (Look, the thing is...)
"¿Entiendes?" (You understand?)
"Let me tell you something..."
Mixes languages mid-sentence naturally
Punctuates points with "exactly!" when you get it

**Settings:**
Always Café Olimpico (her "second office")
Window seat, corner table
Cortado, no sugar, with a pastry
Notebook always present (sketches ideas)

### Notes

Central character. Protagonist's intellectual and emotional anchor.

Represents possibility of authentic connection across difference.
Not just cultural difference but philosophical/emotional attunement.

Role in narrative: Catalyst and mirror. Asks questions that
force protagonist to examine assumptions. Offers wisdom without
being preachy. Has her own complexity and arc.

MUST DEVELOP: Her own story more fully. Can't just be support
for protagonist. What is her journey?

Possible arc:
- Also questioning identity (Spanish in Quebec/Canada)
- Also struggling with academic path
- Parallel journey that complements protagonist's
- Mutual support, not one-way mentorship

Voice: Warm, intellectually playful, patient but also direct.
Will call out BS lovingly. Grounded wisdom.
```

**Minor character:**
```markdown
### Category
Academic / Professional

### Themes
- Academia
- Mentorship
- Professional relationships

### Vignettes

**Office meetings:**
Book-lined office. Always offers tea.
Thoughtful pauses before responding.
Takes notes during meetings (actually listens).

### Notes

Thesis advisor. Minor character but important function.

Represents academic institution/authority.
Supportive but not central to emotional arc.

Use sparingly in manuscript. Functional role.
Maybe expand in one key scene (breakthrough moment).
```

---

## Locations

**Path:** `wiki/locations/{city}/{location-slug}.md`

### What You Can Edit (Wiki-Only)

**Notes section** (preserved but not synced to database)

```markdown
### Notes
Your notes about this location for manuscript.
```

### How to Edit Location Notes

**1. Open location page:**
```bash
vim wiki/locations/montreal/cafe-olimpico.md
```

**2. Edit notes:**
```markdown
### Notes

**For Manuscript:**

Primary setting for protagonist-María José scenes.
Represents "third place" - neither home nor institution.

**Sensory Details:**
- Smell: Espresso, fresh pastries, hint of cinnamon
- Sound: Italian conversations, espresso machine hiss, jazz softly
- Visual: Blue and white tiles, small marble tables, window light
- Touch: Warm cup in cold hands, worn wooden chairs
- Taste: Strong cortado, flaky croissant

**Symbolic Meaning:**
- Refuge from academic pressure
- Community space (immigrant culture, intellectual life)
- Contrast to institutional coldness of university
- Place of authentic connection

**Atmosphere:**
Always crowded but somehow intimate. Corner table by window
feels like private world. Regulars nod hello. Baristas know orders.

**Character associations:**
- Protagonist's thinking/writing space
- María José's "second office"
- Where breakthrough conversations happen
- Symbol of Montreal period

**Key scenes:**
1. First visit (June 20, 2023)
2. Rainy afternoon writing session (Oct 15)
3. Christmas meeting when family couldn't visit (Dec 25)
4. Breakthrough conversation (Jan 15, 2024)

**For development:**
- Expand sensory details in scenes
- Use seasonal changes (summer patio, winter warmth)
- Barista characters? Or just background?
- Other regulars as atmosphere
```

**3. Save**

### Example Location Notes

**Significant place:**
```markdown
### Notes

Mont Royal - Symbolic location for protagonist's transformation.

Physical journey up mountain = metaphorical ascent.
Used in key scenes for revelation moments.

**Sensory:**
- Winter: Crunching snow, cold air, distant city sounds
- Spring: Mud, melting snow, first green, bird songs
- Summer: Forest smells, dappled light, crowds
- Fall: Colored leaves, crisp air, quiet

**Symbolic:**
- Height/elevation = clarity, perspective
- Nature = contrast to urban/academic
- Solitude = space for reflection
- View of city = relationship to Montreal

**Key scenes:**
- First climb (July 2023) - establishing connection to city
- Winter climb (Jan 15, 2024) - breakthrough moment
- Thesis celebration (April 2024) - resolution

Use sparingly. Reserve for most important moments.
Don't overuse the symbolism.
```

**Background place:**
```markdown
### Notes

University library. Functional setting.
Represents academic pressure, institutional life.

Use for:
- Study scenes (show work/pressure)
- Running into people
- Transition scenes

Don't over-describe. It's background.
Readers know what university library is like.
```

---

## Cities

**Path:** `wiki/cities/{city-slug}.md`

### What You Can Edit (Wiki-Only)

**Notes section** (preserved but not synced)

### Example City Notes

```markdown
### Notes

**Montreal - Primary Setting**

Themes associated:
- Immigrant/cultural identity (bilingual city)
- Academic life (McGill)
- Urban isolation vs community
- Winter as metaphor
- North American vs European culture

**Neighborhoods:**
- Mile End: Immigrant community, artistic, María José territory
- Downtown: Academic, institutional, McGill area
- Plateau: Student life, cafés, cultural events

**Seasonal symbolism:**
- Winter: Isolation, introspection, struggle
- Spring: Emergence, transformation, hope
- Summer: Brief abundance, tourists, changed rhythm
- Fall: Beginning (academic year), anticipation, change

**Language:**
Use French occasionally for flavor but don't overdo.
Protagonist's French is improving but limited.
Creates sense of being outsider/insider simultaneously.

**Cultural elements:**
- Bilingualism everywhere
- European feel in North America
- Diverse immigrant communities
- Intellectual/artistic culture
- Cold winters as shared experience

**For manuscript:**
Setting for protagonist's transformation (June 2023 - April 2024).
The city itself is almost a character.
Use specific locations, seasons, cultural markers.
```

---

## Themes

**Path:** `wiki/themes/{theme-slug}.md`

### What You Can Edit (Wiki-Only)

**Notes section**

### Example Theme Notes

```markdown
### Notes

**Identity - Central Theme**

Explores multiple dimensions:

**Cultural identity:**
- Immigrant experience
- Bilingualism/multilingualism
- Belonging and otherness
- Integration vs assimilation

**Academic identity:**
- Student to scholar transition
- Impostor syndrome
- Intellectual development
- Academic vs personal self

**Personal identity:**
- Who am I becoming?
- Past vs future self
- Continuity and change
- Authentic self vs performed self

**Relational identity:**
- Self through relationships
- How others shape us
- Independence vs connection

**Key entries for this theme:**
- June 15, 2023: First questioning
- Dec 25, 2023: Crisis point
- Jan 15, 2024: Breakthrough
- April 1, 2024: Integration/acceptance

**Development arc across manuscript:**

Part 1: Fragmentation (confusion, multiple selves)
Part 2: Crisis (thesis as identity crisis)
Part 3: Integration (accepting complexity)

**Narrative approach:**
- Show through scenes, not tell
- Use relationships as mirrors
- Physical spaces reflect internal states
- Seasonal metaphors

**Related themes:**
- Friendship (María José as catalyst)
- Academic pressure
- Urban isolation
- Cultural negotiation
```

---

## References and Poems

**Path:** `wiki/references/{source-slug}.md`, `wiki/poems/{poem-slug}.md`

### What You Can Edit (Wiki-Only)

**Notes section** (for manuscript development)

### Example Reference Notes

```markdown
### Notes

**Being and Nothingness - Key Philosophical Text**

Major influence on protagonist's thinking.
Frequently referenced during thesis work.

**Themes from text:**
- Bad faith and authenticity
- Freedom and responsibility
- Existence precedes essence

**How protagonist engages:**
- Initially abstract/theoretical
- Gradually personal/applied
- Eventually questions Sartrean framework
- María José challenges assumptions (collectivist vs individualist)

**For manuscript:**
- Don't quote too much (avoid thesis-like quality)
- Use as touchstone for character's thinking
- Show evolution in how protagonist reads Sartre
- Contrast with other influences (Latinx philosophy, etc.)

**Key scenes referencing:**
- Oct 10, 2023: First deep engagement
- Jan 15, 2024: Breakthrough (moving beyond Sartre)
```

### Example Poem Notes

```markdown
### Notes

**Winter in Montreal - Central Poem**

Represents protagonist's emotional landscape.
Snow/winter = isolation, beauty, contemplation.

**Revision arc:**
- V1 (Jan 10): Haiku-like, sparse
- V2 (Jan 15): Expanded, more imagery
- V3 (Jan 20): Final, fully developed

Shows creative process.

**For manuscript:**
- Include all three versions? Or just final?
- Maybe show V1 and V3 to demonstrate growth
- Use poem as chapter epigraph?
- Integrate into narrative (show protagonist writing it)

**Themes:**
- Winter/isolation
- Memory and time
- Urban landscape
- Beauty in harshness
```

---

## Manuscript Wiki Editing

**Path:** `wiki/manuscript/`

### Overview

The manuscript wiki contains **database-linked editable fields**.

**These fields sync back to the database when imported.**

### Manuscript Entry Pages

**Path:** `wiki/manuscript/entries/YYYY/YYYY-MM-DD.md`

**Editable fields (synced to database):**
- Notes
- Character Notes
- Status (via editing)
- Themes (via editing)

**How to edit:**

```markdown
## Status
included

## Themes
- identity-crisis
- friendship-as-catalyst
- urban-isolation

## Character Development
**Protagonist:**
Major turning point. Realizes thesis anxiety is identity anxiety.

**María José:**
Supporting role. Wisdom figure. Catalyst for realization.

## Notes for Revision
Expand café conversation scene.
Add sensory details: coffee smell, Italian conversations.
Develop María José's backstory subtly.
```

**These changes sync to `manuscript_entries` table.**

### Manuscript Character Pages

**Path:** `wiki/manuscript/characters/{character-slug}.md`

**Editable fields (synced to database):**
- Character Description
- Character Arc
- Voice Notes
- Appearance Notes

**Example editing:**

```markdown
### Character Description
María José, late 20s, from Barcelona. PhD student in philosophy.
Protagonist's close friend and intellectual companion.

Warm, wise, intellectually playful. Serves as catalyst for
protagonist's growth while having her own complex journey.

### Character Arc
**Beginning:** Friendly acquaintance met at conference.
**Development:** Becomes close confidante through weekly meetings.
**Turning point:** Christmas dinner invitation (shows trust/intimacy).
**Climax:** Catalyzes protagonist's breakthrough (Jan 15).
**Resolution:** Mutual support through thesis completion.

**Her own arc:** Also navigating identity (Spanish in Quebec).
Academic pressure. Questions about future.

### Voice Notes
**Language:** Mixes Spanish and English naturally.
- "Mira..." when making a point
- "¿Entiendes?" for emphasis
- "exactly!" when you get it

**Tone:** Warm but direct. Intellectually rigorous but not pedantic.

**Dialogue patterns:**
- Asks questions rather than lectures
- Uses hand gestures
- Laughs before punchlines
- Thoughtful pauses

### Appearance Notes
- Dark curly hair (usually tied back)
- Vintage leather jacket (signature piece)
- Colorful scarves (changes daily)
- Silver rings on both hands
- Warm brown eyes
- Expressive hands
```

**These sync to `manuscript_people` table.**

### Manuscript Event/Theme Pages

**Editable:** Notes section (syncs to database)

**Example:**

```markdown
### Notes
Thesis-writing event is central narrative arc.

Use as metaphor for self-discovery.
Parallel intellectual and personal growth.
Show pressure, crisis, breakthrough, resolution.

Key entries: Sept 1 (start), Dec 10 (crisis), Jan 15 (breakthrough).
```

---

## Best Practices

### 1. Know What's Synced vs Wiki-Only

**Synced to database:**
- Entry notes
- Event notes
- All manuscript wiki fields

**Wiki-only (preserved but not synced):**
- Person vignettes/notes
- Location notes
- City notes
- Theme notes
- Reference notes
- Poem notes

**Check before editing:** Will this sync to database or is it wiki-only?

---

### 2. Use Wiki-Only Notes for Manuscript Development

**Perfect for:**
- Character sketches
- Setting descriptions
- Thematic analysis
- Creative notes
- Manuscript planning

**Example workflow:**
1. Export wiki: `palimpsest sql2wiki --output wiki/`
2. Edit person vignettes (character development)
3. Edit location notes (setting details)
4. Edit theme notes (narrative planning)
5. Export again: `palimpsest sql2wiki --output wiki/ --preserve-notes`
6. Your notes are preserved (but not imported to database)

---

### 3. Use Manuscript Wiki for Database-Synced Editing

**Perfect for:**
- Entry editorial notes
- Character development (manuscript wiki)
- Status tracking
- Theme tagging

**Example workflow:**
1. Export wiki: `palimpsest sql2wiki --output wiki/ --manuscript`
2. Edit manuscript entry notes
3. Edit character descriptions
4. Update status fields
5. Import: `palimpsest wiki2sql --input wiki/ --manuscript`
6. Changes synced to database

---

### 4. Preserve Notes During Export

**Always use `--preserve-notes` flag:**

```bash
palimpsest sql2wiki --output wiki/ --preserve-notes
```

**Without this flag:**
- Notes might be overwritten
- Wiki-only content lost
- Manuscript edits reset

**With this flag:**
- Existing notes preserved
- Only database-computed fields regenerated
- Your edits safe

---

### 5. Use Version Control

**Track wiki changes with git:**

```bash
cd wiki/
git init
git add .
git commit -m "Initial wiki export"

# After editing
git add .
git commit -m "Added character vignettes for María José"

# Can review changes
git diff
```

**Benefits:**
- See what you changed
- Revert if needed
- Track development over time

---

### 6. Don't Edit Read-Only Sections

**These will be overwritten:**
- Metadata tables
- Relationship lists
- Timeline data
- Entry lists
- All auto-generated content

**Only edit marked sections:**
- Notes
- Vignettes
- Character development
- Editorial comments

---

### 7. Use Markdown Formatting

**Wiki supports:**
- **Bold** for emphasis
- *Italic* for titles
- `code` for inline code
- Lists (bulleted and numbered)
- Headers (## and ###)
- Blockquotes (>)
- Links ([[ ]])

**Example rich notes:**

```markdown
### Notes

**For Manuscript - Chapter 3:**

This is the *turning point* where protagonist realizes:

1. Thesis anxiety is actually identity anxiety
2. Academic pressure reveals deeper questions
3. Friendship provides clarity

**Key elements:**
- Café conversation with María José
- Walk to Mont Royal (physical journey = mental journey)
- Revelation at summit

> "The breakthrough wasn't about the thesis at all."

**Cross-references:**
- See [[2024-01-10.md|Jan 10]] for setup
- See [[2023-12-25.md|Dec 25]] for crisis that led here

**TODO:**
- [ ] Expand dialogue
- [ ] Add sensory details
- [ ] Develop María José's response
```

---

## Common Workflows

### Workflow 1: Manuscript Character Development

**Goal:** Develop character profiles for creative work

**Steps:**

1. **Export wiki:**
```bash
palimpsest sql2wiki --output wiki/ --manuscript --preserve-notes
```

2. **Edit character pages:**
```bash
vim wiki/people/maria-jose.md
```

3. **Add vignettes:**
```markdown
### Vignettes

**Physical Description:**
[Detailed description]

**Voice:**
[Dialogue patterns]

**Key Scenes:**
[Scene sketches]
```

4. **Also edit manuscript character:**
```bash
vim wiki/manuscript/characters/maria-jose.md
```

5. **Add formal character data:**
```markdown
### Character Description
[Official character description]

### Character Arc
[Narrative arc]

### Voice Notes
[Dialogue guide]
```

6. **Import manuscript changes:**
```bash
palimpsest wiki2sql --input wiki/ --manuscript
```

**Result:**
- Character vignettes in people wiki (wiki-only, for reference)
- Character data in manuscript wiki (synced to database)

---

### Workflow 2: Entry Editorial Notes

**Goal:** Add notes to journal entries for reference/manuscript

**Steps:**

1. **Export wiki:**
```bash
palimpsest sql2wiki --output wiki/ --preserve-notes
```

2. **Browse entries, find important ones:**
```bash
vim wiki/entries/2024/2024-01-15.md
```

3. **Add notes:**
```markdown
### Notes
Key breakthrough entry.
Reference for Chapter 3 of manuscript.
Expand café scene when adapting.
```

4. **Import to sync:**
```bash
palimpsest wiki2sql --input wiki/
```

**Result:**
- Notes synced to `entries.notes` in database
- Available in future exports
- Can query in database

---

### Workflow 3: Event/Period Documentation

**Goal:** Document life events for narrative structure

**Steps:**

1. **Export wiki:**
```bash
palimpsest sql2wiki --output wiki/ --preserve-notes
```

2. **Edit event pages:**
```bash
vim wiki/events/thesis-writing.md
```

3. **Add comprehensive notes:**
```markdown
### Notes

**Thesis Writing Period** (Sept 2023 - April 2024)

**Phases:**
1. Research and outline (Sept-Nov)
2. Crisis (Dec)
3. Breakthrough (Jan)
4. Completion (Feb-Apr)

**Key entries:**
- Sept 1: Start
- Dec 10: Low point
- Jan 15: Breakthrough
- Apr 1: Defense

**For manuscript:**
Central arc for Part 2.
Use as metaphor for identity development.
Show pressure building, crisis, resolution.

**Themes:**
- Academic pressure
- Identity questioning
- Intellectual growth
```

4. **Import:**
```bash
palimpsest wiki2sql --entities events --input wiki/
```

**Result:**
- Event notes in database
- Structured narrative reference
- Timeline documentation

---

### Workflow 4: Thematic Analysis

**Goal:** Organize entries by themes for manuscript

**Steps:**

1. **Export wiki:**
```bash
palimpsest sql2wiki --output wiki/ --preserve-notes
```

2. **Review theme pages:**
```bash
vim wiki/themes/identity.md
```

3. **Add analysis:**
```markdown
### Notes

**Identity - Central Theme**

**Sub-themes:**
- Cultural identity (immigrant experience)
- Academic identity (student → scholar)
- Personal identity (who am I becoming?)

**Key entries:**
- June 15, 2023: First questioning
- Dec 25, 2023: Crisis
- Jan 15, 2024: Breakthrough
- Apr 1, 2024: Integration

**Narrative arc:**
Part 1: Fragmentation
Part 2: Crisis
Part 3: Integration

**Approach:**
- Show through scenes, not tell
- Use relationships as mirrors
- Physical spaces reflect internal
```

4. **No import needed** (wiki-only notes)

**Result:**
- Thematic organization
- Manuscript structure planning
- Entry selection guide

---

### Workflow 5: Location-Based Scene Development

**Goal:** Develop setting details for manuscript

**Steps:**

1. **Export wiki:**
```bash
palimpsest sql2wiki --output wiki/ --preserve-notes
```

2. **Edit location pages:**
```bash
vim wiki/locations/montreal/cafe-olimpico.md
```

3. **Add sensory details:**
```markdown
### Notes

**Café Olimpico - Primary Setting**

**Sensory:**
- Smell: Dark espresso, fresh pastry, cinnamon
- Sound: Italian, espresso machine, soft jazz
- Visual: Blue tiles, marble tables, window light
- Touch: Warm cup, cold outside, worn wood
- Taste: Strong cortado, flaky croissant

**Atmosphere:**
Crowded but intimate. Corner table feels private.
Regulars nod. Baristas know orders. Third place.

**Key scenes:**
1. First visit (June 20)
2. Rainy writing session (Oct 15)
3. Christmas meeting (Dec 25)
4. Breakthrough (Jan 15)

**Use for:**
Intimate conversations
Writing/thinking scenes
Meeting place
Refuge from academic world
```

4. **No import needed** (wiki-only)

**Result:**
- Rich setting details
- Consistent atmosphere
- Scene reference

---

## Troubleshooting

### "My edits were overwritten"

**Problem:** Exported wiki again and lost changes

**Cause:** Edited read-only sections OR didn't use `--preserve-notes`

**Solution:**
1. Only edit Notes sections
2. Always use `--preserve-notes` flag:
```bash
palimpsest sql2wiki --output wiki/ --preserve-notes
```

**Prevention:** Use version control (git) to track changes

---

### "Import didn't sync my changes"

**Problem:** Edited wiki but changes not in database

**Check:**
1. Did you edit an editable field? (See tables above)
2. Did you run wiki2sql import?
3. Are you editing wiki-only notes? (Won't sync - that's expected)

**Debug:**
```bash
# Preview what will change
palimpsest wiki2sql --input wiki/ --dry-run --verbose

# Check which fields are editable
palimpsest wiki info --editable-fields
```

---

### "Which notes sync to database?"

**Synced to database:**
- Entry notes (entries.notes)
- Event notes (events.notes)
- Manuscript entry notes
- Manuscript character fields

**Wiki-only (NOT synced):**
- Person notes/vignettes
- Location notes
- City notes
- Theme notes
- Reference notes
- Poem notes

**Use synced notes for:**
- Database queries
- Future exports
- Permanent record

**Use wiki-only notes for:**
- Manuscript development
- Creative planning
- Personal reference

---

### "Can I edit metadata?"

**No. Metadata is database-computed.**

**Cannot edit in wiki:**
- Entry dates
- Word counts
- People lists
- Location lists
- Tags
- Events (entry lists)
- Relationship data

**To change metadata:**
- Edit YAML frontmatter in entry file
- Re-import with yaml2sql
- Export fresh wiki

**Can edit in wiki:**
- Notes sections (specific fields only)

---

### "How do I organize my manuscript?"

**Use both wikis:**

**Regular wiki:**
- Vignettes (character sketches)
- Setting details (location notes)
- Thematic analysis (theme notes)
- Research (reference notes)

**Manuscript wiki:**
- Formal character data
- Entry status/themes
- Editorial notes
- Narrative structure

**Workflow:**
1. Develop ideas in regular wiki (vignettes, etc.)
2. Formalize in manuscript wiki (character arcs, etc.)
3. Sync manuscript wiki to database
4. Regular wiki stays as creative reference

---

## Summary

### What You Can Edit (Synced to Database)

**Entries:**
- Notes section → `entries.notes`

**Events:**
- Notes section → `events.notes`

**Manuscript Entries:**
- Notes, Character Notes → `manuscript_entries.*`

**Manuscript Characters:**
- All character fields → `manuscript_people.*`

### What You Can Edit (Wiki-Only)

**People:**
- Vignettes, Notes, Category, Themes

**Locations:**
- Notes

**Cities:**
- Notes

**Themes:**
- Notes

**References:**
- Notes

**Poems:**
- Notes

### Key Commands

**Export:**
```bash
palimpsest sql2wiki --output wiki/ --preserve-notes
palimpsest sql2wiki --output wiki/ --manuscript --preserve-notes
```

**Import:**
```bash
palimpsest wiki2sql --input wiki/
palimpsest wiki2sql --input wiki/ --manuscript
palimpsest wiki2sql --input wiki/ --dry-run  # Preview
```

### Best Practices

1. **Always use `--preserve-notes`** when exporting
2. **Only edit Notes sections** (marked as editable)
3. **Use version control** (git) for wiki
4. **Know what's synced** vs wiki-only
5. **Use manuscript wiki** for database-linked editing
6. **Use regular wiki notes** for creative development

### Remember

- Most wiki content is **read-only**
- Only **Notes sections** are editable
- **Manuscript wiki** syncs more fields to database
- **Wiki-only notes** preserved but not imported
- Always **preview with --dry-run** before import

---

## Next Steps

1. **Export your wiki:** `palimpsest sql2wiki --output wiki/`
2. **Browse the structure:** Understand the layout
3. **Try editing notes:** Start with entry notes
4. **Import your changes:** `palimpsest wiki2sql --input wiki/`
5. **Develop manuscript:** Use manuscript wiki for character/narrative
6. **Iterate:** Export → Edit → Import cycle

**Most important: Use wiki notes for creative development!**

---

*Happy curating!*
