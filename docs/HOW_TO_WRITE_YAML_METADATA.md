# How to Write Markdown-YAML Metadata

A comprehensive, practical guide to writing metadata in your Palimpsest journal entries.

---

## Table of Contents

1. [Introduction](#introduction)
2. [Basic Entry Structure](#basic-entry-structure)
3. [Step-by-Step Field Guide](#step-by-step-field-guide)
4. [Real-World Examples](#real-world-examples)
5. [Best Practices](#best-practices)
6. [Common Mistakes](#common-mistakes)
7. [Progressive Complexity](#progressive-complexity)
8. [Troubleshooting](#troubleshooting)

---

## Introduction

### What is Frontmatter Metadata?

Your Palimpsest journal entries consist of two parts:

```markdown
---
date: 2024-01-15
city: Montreal
tags: [personal]
---

This is the entry content (body).
It can be as long as you want.
```

The section between `---` markers is **YAML frontmatter** - structured metadata about your entry. This metadata allows Palimpsest to:

- Track people, places, and events
- Build relationship graphs
- Generate timeline views
- Create wiki pages
- Search and filter entries
- Track manuscript development

### Why Add Metadata?

**Without metadata:**
```markdown
---
date: 2024-01-15
---

Today I had coffee with María José at Café Olimpico. We talked about identity.
```

**With metadata:**
```markdown
---
date: 2024-01-15
city: Montreal
locations:
  - Café Olimpico
people:
  - "@Majo (María-José)"
tags:
  - identity
  - friendship
---

Today I had coffee with María José at Café Olimpico. We talked about identity.
```

**The benefits:**
- Find all entries where you met María José
- See all conversations at Café Olimpico
- Track the evolution of identity as a theme
- Generate a timeline of your Montreal period
- Build character profiles for manuscript writing

---

## Basic Entry Structure

### Minimal Valid Entry

The absolute minimum requirement:

```yaml
---
date: 2024-01-15
---

Your entry text goes here.
```

**That's it!** Everything else is optional. Start simple and add complexity as needed.

### Recommended Starter Template

A good default for daily entries:

```yaml
---
date: 2024-01-15
city:
tags: []
---

Entry content here.
```

Fill in `city` and `tags` as you write. Leave them empty if not applicable.

### How to Choose What to Include

Ask yourself:

1. **Where was I?** → Add `city` and `locations`
2. **Who was I with?** → Add `people`
3. **What's this about?** → Add `tags`
4. **Is this part of something bigger?** → Add `events`
5. **Did I reference a book/film?** → Add `references`
6. **Did I write poetry?** → Add `poems`
7. **Is this for a manuscript?** → Add `manuscript`

**Don't overthink it.** You can always add metadata later.

---

## Step-by-Step Field Guide

## 1. Date (Required)

**Purpose:** Uniquely identifies your entry.

**Format:** `YYYY-MM-DD` (ISO 8601)

**How to write:**
```yaml
date: 2024-01-15
```

**Rules:**
- Must be the date you wrote the entry (or the date it represents)
- One entry per date (cannot have duplicates)
- Use zero-padding (01 not 1, 02 not 2)

**Examples:**
```yaml
# ✅ Correct
date: 2024-01-15
date: 2023-12-31
date: 2024-02-29  # Leap year

# ❌ Wrong
date: 01/15/2024  # Wrong format
date: 2024-1-15   # Missing zero-padding
date: January 15, 2024  # Not ISO format
```

---

## 2. City (Optional)

**Purpose:** Track where you were when you wrote the entry.

**Format:** Single city name or list of cities

**How to write:**
```yaml
# Single city
city: Montreal

# Multiple cities (if you traveled that day)
city: [Montreal, Toronto, Paris]
```

**When to use:**
- You're in a specific city
- You traveled through multiple cities
- Location is relevant to the entry

**When to skip:**
- Location isn't relevant
- You're at home (unless you want to track that)

**Examples:**
```yaml
# Simple
city: Montreal
city: Toronto
city: Paris

# Multiple cities
city: [Montreal, New York]
city: [Barcelona, Madrid, Valencia]

# Can also write as list
city:
  - Montreal
  - Toronto
```

**Tips:**
- Use the city's common English name
- Be consistent with spelling/capitalization
- The database will track country automatically

---

## 3. Locations (Optional)

**Purpose:** Track specific places within a city.

**Format:** Depends on whether you have one or multiple cities

### Single City Format

Use a simple list:

```yaml
city: Montreal
locations:
  - Café Olimpico
  - Mont Royal
  - McGill Library
```

### Multiple Cities Format

Use a nested structure (city → locations):

```yaml
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
    - Mont Royal
  Toronto:
    - Robarts Library
    - Trinity College
```

**When to use:**
- You were at specific venues/places
- You want to track patterns (always write at this café)
- Location is significant to the entry

**What to include:**
- Cafés, restaurants, bars
- Parks, landmarks
- Friend's homes ("Sarah's apartment")
- Institutions (libraries, schools)
- Neighborhoods

**How to name places:**
```yaml
# Use quotes for special characters
locations:
  - "Mom's house"
  - "Café #5"
  - "Friend's apartment"

# Simple names don't need quotes
locations:
  - McGill Library
  - Parc La Fontaine
  - Mont Royal
```

**Examples:**
```yaml
# Day at university
city: Montreal
locations:
  - McLennan Library
  - Redpath Building
  - Café Campus

# Day trip
city: Montreal
locations:
  - Vieux-Montréal
  - Notre-Dame Basilica
  - "Jean-Talon Market"

# Multi-city trip
city: [New York, Philadelphia]
locations:
  New York:
    - MoMA
    - Central Park
  Philadelphia:
    - Liberty Bell
    - Reading Terminal Market
```

**Common mistake:**
```yaml
# ❌ Multiple cities with flat list
city: [Montreal, Toronto]
locations:
  - Café Olimpico  # Which city??

# ✅ Use nested format
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Library
```

---

## 4. People (Optional)

**Purpose:** Track who you spent time with or wrote about.

**Format:** Multiple formats supported (choose what's easiest)

### Format 1: Simple Names

```yaml
people:
  - John
  - Sarah
  - María José
```

**When to use:** Most common, easiest format

**How it works:**
- Single word (John) → stored as name
- Multiple words (John Smith) → stored as full name
- Hyphens become spaces (María-José → María José)

### Format 2: Name with Full Name

```yaml
people:
  - John (John Smith)
  - Bob (Robert Johnson)
  - Majo (María José)
```

**When to use:** You use a nickname but want to track the full name

**Format:** `nickname (Full Name)`

### Format 3: Aliases

```yaml
people:
  - "@Johnny (John)"
  - "@Majo (María-José)"
  - "@Dr-M (Dr-Martinez)"
```

**When to use:** You refer to someone differently in different entries

**Format:** `@alias (Name)` - **Requires `@` symbol**

**How it works:**
- Creates an alias that links to the person
- Later you can use either the name or the alias
- Good for nicknames, abbreviations, role names

### Format 4: Mixed (Most Flexible)

```yaml
people:
  - María José              # Simple name
  - John (John Smith)       # Name + full name
  - "@Majo (María-José)"    # Alias
  - Bob                     # Simple name
```

**Examples:**

**Academic entry:**
```yaml
people:
  - Dr. Smith
  - Dr. Johnson
  - Alice (Alice Anderson)  # Fellow student
```

**Social entry:**
```yaml
people:
  - "@Majo (María-José)"
  - Sarah
  - Tom (Thomas Williams)
```

**Family entry:**
```yaml
people:
  - Mom
  - Dad
  - "@Sis (Sarah)"
```

**Tips:**
- Start simple (just names)
- Add full names if you want better tracking
- Use aliases if you call people different things
- Be consistent with how you write each person's name

**Special cases:**

**Hyphenated names:**
```yaml
# These are the same person:
people:
  - María-José
  - María José

# Both stored as "María José" in database
```

**Quotes for special characters:**
```yaml
people:
  - "O'Brien"
  - "D'Angelo"
```

---

## 5. Dates (Optional)

**Purpose:** Track dates mentioned in your entry (past events, future plans, etc.)

**Format:** List of dates with optional context

### Simple Dates

```yaml
dates:
  - "2024-01-20"
  - "2023-12-25"
  - "2024-06-01"
```

**When to use:** Just want to note these dates

### Dates with Context

```yaml
dates:
  - "2024-01-20 (thesis defense)"
  - "2023-12-25 (Christmas dinner)"
  - "2024-06-01 (Alice's birthday)"
```

**When to use:** Want to remember what happened on each date

### Dates with People and Places

```yaml
dates:
  - "2024-01-20 (thesis defense at #McGill-campus)"
  - "2024-01-15 (coffee with @Majo at #Café-Olimpico)"
  - "2023-12-25 (Christmas with @Mom and @Dad at #home)"
```

**Special syntax:**
- `@PersonName` → Links to that person
- `#LocationName` → Links to that location
- Hyphens in names become spaces

**When to use:** You want to track who you were with and where

### Explicit Format (Most Control)

```yaml
dates:
  - date: "2024-01-20"
    context: "thesis defense"
    people:
      - Dr. Smith
      - Dr. Johnson
    locations:
      - McGill University
```

**When to use:** Multiple people/locations, need more structure

### Important: Entry Date Auto-Inclusion

**By default, your entry's date is automatically added to your mentioned dates.**

```yaml
# This entry:
---
date: 2024-01-15
# No dates field
---

# Automatically creates a mentioned date for 2024-01-15
```

**To opt out of auto-inclusion:**

```yaml
dates:
  - "~"  # Tilde prevents auto-inclusion
  - "2024-01-20"  # Only this date will be tracked
```

**Examples:**

**Appointment reminder:**
```yaml
dates:
  - "2024-01-20 (dentist at 10am)"
  - "2024-01-25 (meeting with advisor)"
```

**Past event reference:**
```yaml
dates:
  - "2023-06-15 (first met @Majo at conference)"
  - "2023-12-25 (last Christmas at home)"
```

**Detailed event:**
```yaml
dates:
  - date: "2024-01-20"
    context: "thesis defense"
    people:
      - Dr. Smith
      - Dr. Johnson
      - María José  # Attended for support
    locations:
      - McGill University
      - "Celebration dinner at Café-X"
```

**Tips:**
- Use quotes around dates ("2024-01-15")
- Add context in parentheses for clarity
- Use `@` and `#` for quick people/location references
- Don't need to track every mentioned date - only meaningful ones

---

## 6. Tags (Optional)

**Purpose:** Categorize entries by topic, mood, or type.

**Format:** List of simple keywords

**How to write:**
```yaml
tags:
  - philosophy
  - personal
  - research
```

**Or inline:**
```yaml
tags: [philosophy, personal, research]
```

**When to use:**
- Categorizing by topic
- Tracking moods
- Marking entry types

**What to include:**

**Topic tags:**
```yaml
tags:
  - philosophy
  - identity
  - relationships
  - creativity
  - research
```

**Mood tags:**
```yaml
tags:
  - anxious
  - hopeful
  - contemplative
  - frustrated
  - joyful
```

**Type tags:**
```yaml
tags:
  - dream-record
  - letter-draft
  - poem-notes
  - reflection
  - planning
```

**Examples:**

**Academic entry:**
```yaml
tags:
  - research
  - thesis
  - philosophy
  - writing
```

**Personal entry:**
```yaml
tags:
  - personal
  - identity
  - family
  - contemplative
```

**Creative entry:**
```yaml
tags:
  - poetry
  - creative
  - inspiration
```

**Tips:**
- Use lowercase
- Use hyphens instead of spaces (poem-notes not poem notes)
- Be consistent (always "philosophy" not sometimes "philosophy" and sometimes "philosophical")
- Start with 3-5 tags, don't overthink it
- You can search by tag later, so think about how you'll want to filter

**Common tag sets:**

```yaml
# Emotions
tags: [anxious, uncertain, hopeful]

# Topics
tags: [identity, family, career]

# Activities
tags: [writing, reading, reflection]

# People types
tags: [friends, family, colleagues]

# Places
tags: [home, travel, university]
```

---

## 7. Events (Optional)

**Purpose:** Track periods, milestones, or ongoing situations in your life.

**Format:** List of event names

**How to write:**
```yaml
events:
  - thesis-writing
  - montreal-period
  - phd-research
```

**When to use:**
- Marking entries that belong to a life period
- Tracking progress on projects
- Grouping entries by ongoing situations

**What to include:**

**Life periods:**
```yaml
events:
  - montreal-period
  - graduate-school
  - post-breakup
  - new-job
```

**Projects:**
```yaml
events:
  - thesis-writing
  - novel-draft
  - poetry-workshop
  - research-project-x
```

**Situations:**
```yaml
events:
  - job-search
  - family-crisis
  - health-recovery
  - moving-apartments
```

**Examples:**

**Academic life:**
```yaml
events:
  - phd-studies
  - thesis-writing
  - comprehensive-exams
  - dissertation-defense-prep
```

**Creative project:**
```yaml
events:
  - manuscript-writing
  - first-draft
  - revision-process
```

**Personal milestone:**
```yaml
events:
  - turning-30
  - career-transition
  - relationship-ending
```

**Tips:**
- Use kebab-case (hyphens between words)
- Think of events as chapters or arcs in your life
- Events span multiple entries (unlike tags)
- Use for filtering "show me all entries during thesis-writing"

**Difference between tags and events:**

```yaml
# Tag = what is this entry about?
tags: [philosophy, research]

# Event = what period/project is this part of?
events: [thesis-writing, montreal-period]
```

---

## 8. Related Entries (Optional)

**Purpose:** Link to other entries that connect to this one.

**Format:** List of dates (YYYY-MM-DD)

**How to write:**
```yaml
related_entries:
  - "2024-01-10"
  - "2024-01-12"
  - "2023-12-20"
```

**When to use:**
- This entry continues a thought from another entry
- This entry responds to a previous entry
- These entries form a sequence
- You want to create explicit connections

**Examples:**

**Continuing a thought:**
```yaml
# Entry 2024-01-15
---
date: 2024-01-15
related_entries:
  - "2024-01-10"  # Where I first discussed this idea
---

Continuing from my entry on the 10th, I've realized...
```

**Sequence of entries:**
```yaml
# Part 3 of a series
---
date: 2024-01-15
related_entries:
  - "2024-01-10"  # Part 1
  - "2024-01-12"  # Part 2
---

Third installment of my reflection on identity...
```

**Callback:**
```yaml
---
date: 2024-01-15
related_entries:
  - "2023-06-15"  # Six months ago, first meeting
---

Six months since I first met María José (see June 15 entry)...
```

**Tips:**
- Use quotes around dates
- Link to entries you explicitly reference
- Don't overuse - only for meaningful connections
- The system will find other connections automatically (through shared people, places, tags)

---

## 9. Epigraph (Optional)

**Purpose:** Add an opening quote to your entry.

**Format:** Quote text + attribution

**How to write:**
```yaml
epigraph: "The only way out is through."
epigraph_attribution: "Robert Frost"
```

**When to use:**
- You want to set the mood for the entry
- A quote inspired the entry
- You're drawing on a particular text

**Examples:**

**With full attribution:**
```yaml
epigraph: "To be or not to be, that is the question"
epigraph_attribution: "Hamlet, Act III Scene I"
```

**Simple attribution:**
```yaml
epigraph: "The unexamined life is not worth living."
epigraph_attribution: "Socrates"
```

**Without attribution:**
```yaml
epigraph: "A quote I heard somewhere"
# No epigraph_attribution field
```

**Multi-line quote:**
```yaml
epigraph: |
  Do I dare
  Disturb the universe?
  In a minute there is time
  For decisions and revisions which a minute will reverse.
epigraph_attribution: "T.S. Eliot, The Love Song of J. Alfred Prufrock"
```

**Tips:**
- Use quotes around simple text
- Use `|` for multi-line quotes (preserves line breaks)
- Attribution is optional but recommended
- Use for quotes that frame the entry, not quotes you discuss in the entry (those go in `references`)

---

## 10. References (Optional)

**Purpose:** Track quotes, citations, and references to books, films, articles, etc.

**Format:** List of reference objects

### Basic Quote

```yaml
references:
  - content: "The quoted text"
    speaker: "Who said it"
    source:
      title: "Source Title"
      type: book
      author: "Author Name"
```

### Required Fields

**You must include:**
- `content` OR `description` (at least one)

**If you include `source`, you must have:**
- `title`
- `type`

### Reference Types

Valid `type` values:
- `book`
- `article`
- `film`
- `play`
- `poem`
- `essay`
- `song`
- `podcast`
- `lecture`
- `interview`
- `artwork`
- `other`

### Reference Modes

Optional `mode` field (defaults to `direct`):
- `direct` - Direct quotation
- `indirect` - Indirect quotation
- `paraphrase` - Paraphrased content
- `visual` - Visual reference (image, artwork)

**Examples:**

**Book quote:**
```yaml
references:
  - content: "The unexamined life is not worth living."
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"
```

**Film quote:**
```yaml
references:
  - content: "You're gonna need a bigger boat."
    speaker: Chief Brody
    source:
      title: "Jaws"
      type: film
      author: "Steven Spielberg"
```

**Paraphrase:**
```yaml
references:
  - description: "Sartre argues that existence precedes essence and we are condemned to be free."
    mode: paraphrase
    source:
      title: "Being and Nothingness"
      type: book
      author: "Jean-Paul Sartre"
```

**Visual reference:**
```yaml
references:
  - description: "Painting depicting urban isolation at night"
    mode: visual
    source:
      title: "Nighthawks"
      type: artwork
      author: "Edward Hopper"
```

**Article:**
```yaml
references:
  - content: "Quote from article"
    source:
      title: "Article Title"
      type: article
      author: "Author Name"
```

**Conversation (no formal source):**
```yaml
references:
  - content: "Something profound María José said"
    speaker: María José
    # No source - informal conversation
```

**Multiple references:**
```yaml
references:
  - content: "Quote from Plato"
    source:
      title: "Republic"
      type: book
      author: "Plato"

  - description: "Sartre's argument about freedom"
    mode: paraphrase
    source:
      title: "Being and Nothingness"
      type: book
      author: "Jean-Paul Sartre"

  - content: "Line from poem"
    source:
      title: "The Waste Land"
      type: poem
      author: "T.S. Eliot"
```

**Tips:**
- Use `content` for direct quotes
- Use `description` for paraphrases or summaries
- Add `speaker` if someone specific said it
- `mode` is optional, defaults to "direct"
- Can reference informal sources (conversations) without source details
- Use for quotes you discuss in the entry (epigraph is for framing quotes)

---

## 11. Poems (Optional)

**Purpose:** Track poems you write in your entries.

**Format:** List of poem objects

**How to write:**

### Simple Poem

```yaml
poems:
  - title: "Poem Title"
    content: |
      First line of poem
      Second line
      Third line
```

**Note the `|` symbol** - This preserves line breaks (literal style)

### Poem with Revision Date

```yaml
poems:
  - title: "Poem Title"
    content: |
      Poem content here
      Multiple lines
    revision_date: "2024-01-15"
    notes: "Second draft, revised opening"
```

**When to use:**
- You write poetry in your journal
- You want to track revisions across entries
- You're developing poems over time

**Required fields:**
- `title` - Name of the poem
- `content` - The poem text

**Optional fields:**
- `revision_date` - Date of this version (defaults to entry date)
- `notes` - Notes about this revision

**Examples:**

**Simple haiku:**
```yaml
poems:
  - title: "Winter Morning"
    content: |
      Snow falls softly down
      Silence wraps the sleeping world
      A moment of peace
```

**Longer poem:**
```yaml
poems:
  - title: "Montreal Winter"
    content: |
      Streets of memory and snow,
      Where every corner holds a story yet untold.

      The city sleeps beneath white silence,
      Dreams suspended in frozen time,
      Waiting for spring's first whisper.
```

**Poem with notes:**
```yaml
poems:
  - title: "City Symphony"
    content: |
      Draft version here
      Still rough around the edges
      Needs better rhythm
    notes: "First draft, needs revision"
```

**Multiple poems in one entry:**
```yaml
poems:
  - title: "Morning Thoughts"
    content: |
      First poem here
      Short haiku style

  - title: "Evening Reflection"
    content: |
      Second poem here
      Longer, more developed
      Multiple stanzas
```

**Tracking revisions across entries:**

**Entry 2024-01-10:**
```yaml
poems:
  - title: "City Life"
    content: |
      Draft version
      Rough ideas
    notes: "Initial draft"
```

**Entry 2024-01-15:**
```yaml
poems:
  - title: "City Life"
    content: |
      Revised version
      Better flow
      New ending
    revision_date: "2024-01-15"
    notes: "Second revision, improved rhythm"
```

**Entry 2024-01-20:**
```yaml
poems:
  - title: "City Life"
    content: |
      Final version
      Polished and complete
      Ready for publication
    revision_date: "2024-01-20"
    notes: "Final version"
```

**Tips:**
- Always use `|` after `content:` for multi-line poems
- Indent the poem lines (2 spaces)
- Blank lines in poems are preserved
- `revision_date` defaults to entry date if omitted
- Same title across entries = tracked as revisions of same poem

---

## 12. Manuscript (Optional)

**Purpose:** Editorial metadata for developing entries into creative work.

**Format:** Dictionary with status, themes, and notes

**How to write:**

### Basic Manuscript Tag

```yaml
manuscript:
  status: draft
```

### Full Manuscript Metadata

```yaml
manuscript:
  status: included
  edited: true
  themes:
    - identity
    - urban-isolation
    - friendship
  notes: "Key scene for Chapter 3"
```

**When to use:**
- You're writing a memoir/novel/creative nonfiction
- You want to tag which entries to include
- You're tracking themes for narrative development
- You need editorial notes for revision

**Fields:**

**`status` (required if manuscript present):**
- `source` - Raw source material
- `draft` - First draft for manuscript
- `reviewed` - Under review
- `included` - Will be included in manuscript
- `excluded` - Will not be included
- `final` - Final version

**`edited` (optional boolean):**
- `true` - Entry has been edited for manuscript
- `false` - Raw/unedited

**`themes` (optional list):**
- Narrative themes for this entry
- Used for organizing manuscript structure

**`notes` (optional text):**
- Editorial notes
- Revision reminders
- Structural notes

**Examples:**

**Mark as source material:**
```yaml
manuscript:
  status: source
```

**Mark as draft:**
```yaml
manuscript:
  status: draft
  edited: false
```

**Include in manuscript:**
```yaml
manuscript:
  status: included
  edited: true
  themes:
    - identity-crisis
    - academic-pressure
  notes: "Good material for Part 2, Chapter 5"
```

**Exclude from manuscript:**
```yaml
manuscript:
  status: excluded
  notes: "Too personal, doesn't fit narrative"
```

**With detailed notes:**
```yaml
manuscript:
  status: reviewed
  edited: true
  themes:
    - coming-of-age
    - immigrant-experience
    - friendship
  notes: |
    Key scene for Chapter 3.
    Expand conversation with María José.
    Add more sensory details about café.
    Consider cutting epigraph.
```

**Workflow example:**

**Stage 1 - Source:**
```yaml
# Raw entry
manuscript:
  status: source
```

**Stage 2 - Draft:**
```yaml
# First editing pass
manuscript:
  status: draft
  edited: true
  themes:
    - identity
  notes: "Expanded dialogue, added description"
```

**Stage 3 - Review:**
```yaml
# Under review
manuscript:
  status: reviewed
  edited: true
  themes:
    - identity
    - friendship
  notes: |
    Feedback from beta readers:
    - Strengthen emotional arc
    - More sensory details
```

**Stage 4 - Final:**
```yaml
# Ready for publication
manuscript:
  status: final
  edited: true
  themes:
    - identity
    - friendship
  notes: "Final version, all revisions incorporated"
```

**Tips:**
- Start with just `status`
- Add `themes` to organize by narrative threads
- Use `notes` for editorial reminders
- `edited: true` when you've revised the entry text
- Track progress: source → draft → reviewed → included/excluded → final

---

## 13. Word Count and Reading Time (Optional)

**Purpose:** Track entry length.

**Format:** Integers/floats

**How to write:**
```yaml
word_count: 1543
reading_time: 7.5
```

**When to use:**
- You want to manually specify these
- Auto-calculation isn't working

**Usually skip because:**
- These are auto-calculated from your entry text
- word_count = number of words in body
- reading_time = word_count / 260 (words per minute)

**Only specify if:**
- You have a specific reason to override
- You're importing from another system

**Examples:**
```yaml
# Auto-calculated (recommended)
---
date: 2024-01-15
---
Entry text here (words counted automatically)

# Manual specification
---
date: 2024-01-15
word_count: 1250
reading_time: 6.2
---
Entry text here
```

**Tips:**
- Usually omit these fields
- Let the system calculate automatically
- Only override if you have a good reason

---

## 14. Notes (Optional)

**Purpose:** Editorial notes about the entry (for your own reference).

**Format:** Text string

**How to write:**
```yaml
notes: "Important entry for Chapter 3 of manuscript"
```

**Or multi-line:**
```yaml
notes: |
  Important entry for Chapter 3.
  Captures turning point in narrative.
  Reference when working on protagonist's arc.
```

**When to use:**
- Editorial reminders
- Future reference notes
- Context for yourself

**Examples:**

**Manuscript note:**
```yaml
notes: "Key scene for Chapter 3 - protagonist's breakthrough moment"
```

**Research note:**
```yaml
notes: "Good quote here for thesis introduction"
```

**Personal note:**
```yaml
notes: "Come back to this when working through family issues"
```

**Detailed notes:**
```yaml
notes: |
  Multiple things to note:
  - Contains important conversation with María José
  - Reference for dissertation Chapter 4
  - Breakthrough insight on identity question
  - Consider expanding for manuscript
```

**Tips:**
- Use for your own reference
- Visible in wiki exports
- Helps future-you understand why this entry matters
- Don't confuse with `manuscript.notes` (specifically for manuscript work)

---

## Real-World Examples

### Example 1: Simple Daily Entry

```yaml
---
date: 2024-01-15
city: Montreal
tags: [personal, reflection]
---

Quiet day. Spent most of it reading at home. Thinking about what's next.
```

**Why this works:**
- Has required date
- Tracks location
- Simple categorization with tags
- No need for more complexity

---

### Example 2: Social Entry

```yaml
---
date: 2024-01-15
city: Montreal
locations:
  - Café Olimpico
people:
  - "@Majo (María-José)"
  - Sarah
tags:
  - friends
  - conversation
events:
  - montreal-period
---

Had coffee with María José and Sarah at Café Olimpico. We talked about...
```

**Why this works:**
- Tracks specific location
- Tracks who you were with
- Uses alias for María José (you call her "Majo")
- Tags the interaction
- Links to broader life period

---

### Example 3: Academic Entry

```yaml
---
date: 2024-01-15
city: Montreal
locations:
  - McLennan Library
people:
  - Dr. Smith
tags:
  - research
  - thesis
  - philosophy
events:
  - thesis-writing
  - phd-research
dates:
  - "2024-01-20 (thesis defense)"
references:
  - content: "The unexamined life is not worth living."
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"
---

Meeting with Dr. Smith about my thesis today. We discussed the Socratic method...
```

**Why this works:**
- Tracks work location
- References advisor
- Clear topic tags
- Links to ongoing projects
- Notes upcoming milestone
- Records relevant citation

---

### Example 4: Creative Entry

```yaml
---
date: 2024-01-15
city: Montreal
tags:
  - poetry
  - creative
  - winter
events:
  - poetry-workshop
poems:
  - title: "Winter in Montreal"
    content: |
      Snow falls on cobblestones,
      Each flake a memory
      Of winters past and yet to come.

      The city sleeps beneath white silence,
      Dreams suspended in frozen time,
      Waiting for spring's first whisper.
    notes: "First draft, needs revision"
---

Wrote a new poem today while watching the snow fall. Inspired by...
```

**Why this works:**
- Clear creative focus
- Tracks the poem
- Notes it's a draft
- Links to poetry workshop event
- Simple tags for filtering

---

### Example 5: Travel Entry

```yaml
---
date: 2024-01-15
city: [Barcelona, Madrid]
locations:
  Barcelona:
    - Sagrada Família
    - Park Güell
  Madrid:
    - Prado Museum
    - Retiro Park
people:
  - Carlos (local friend)
tags:
  - travel
  - architecture
  - art
events:
  - spain-trip-2024
---

First day in Spain. Started in Barcelona with Carlos showing me around...
```

**Why this works:**
- Multiple cities tracked
- Locations organized by city
- Tracks local connection
- Clear travel tags
- Links to trip event

---

### Example 6: Manuscript Entry

```yaml
---
date: 2024-01-15
city: Montreal
locations:
  - Café Olimpico
people:
  - "@Majo (María-José)"
tags:
  - identity
  - friendship
  - breakthrough
events:
  - thesis-writing
  - montreal-period
related_entries:
  - "2024-01-10"
  - "2023-12-20"
manuscript:
  status: included
  edited: true
  themes:
    - identity-crisis
    - friendship-as-catalyst
    - urban-isolation
  notes: |
    KEY ENTRY for Chapter 3.
    Protagonist's breakthrough moment.
    Expand café conversation (currently 2 paragraphs → needs 2 pages).
    Add more sensory details.
    Consider María José's backstory here.
notes: "Important breakthrough about identity/thesis connection"
---

Conversation with María José at Café Olimpico changed everything...
```

**Why this works:**
- Complete tracking of event
- Links to related earlier entries
- Detailed manuscript metadata
- Editorial notes for future work
- Personal notes for reference
- Clear themes for narrative organization

---

### Example 7: Comprehensive Entry

```yaml
---
date: 2024-01-15
word_count: 1250
reading_time: 6.2
epigraph: |
  In the middle of the journey of our life I found myself within a dark woods
  where the straight way was lost.
epigraph_attribution: "Dante, Inferno, Canto I"
city: Montreal
locations:
  - Café Olimpico
  - Mont Royal
people:
  - "@Majo (María-José)"
  - John (John Smith)
  - Dr. Martinez
dates:
  - "2024-01-20 (thesis defense at #McGill-campus with @Dr-Smith)"
  - "2024-01-10 (first conversation about this topic)"
events:
  - thesis-writing
  - montreal-period
  - quarter-life-crisis
tags:
  - philosophy
  - identity
  - research
  - breakthrough
related_entries:
  - "2024-01-10"
  - "2024-01-12"
  - "2023-12-25"
references:
  - content: "The unexamined life is not worth living."
    speaker: Socrates
    source:
      title: "Apology"
      type: book
      author: "Plato"
  - description: "Discussion of personal identity and memory continuity"
    mode: paraphrase
    source:
      title: "Reasons and Persons"
      type: book
      author: "Derek Parfit"
poems:
  - title: "Midwinter Revelation"
    content: |
      In the depths of winter's hold,
      When all seems frozen, stark, and cold,
      A spark ignites—a truth unfolds:
      The self I seek is growing old.
    revision_date: "2024-01-15"
    notes: "Written in one sitting, surprisingly complete"
manuscript:
  status: included
  edited: true
  themes:
    - identity-crisis
    - academic-pressure
    - friendship-as-wisdom
    - urban-winter-metaphor
  notes: |
    CHAPTER 3 CLIMAX - Protagonist's breakthrough.

    Structure:
    1. Morning walk to café (winter setting)
    2. Conversation with María José (catalyst)
    3. Walk up Mont Royal (physical/metaphorical ascent)
    4. Revelation at summit

    To expand:
    - More dialogue with María José
    - Sensory details (cold, light, city sounds)
    - Internal monologue during walk
    - Connect to Dante epigraph more explicitly

    Cross-ref with Dec 25 entry (family crisis) and Jan 10 (first hint).
notes: "Breakthrough entry. Realized thesis anxiety is identity anxiety. Reference for Chapter 3."
---

Today was a turning point. I met María José at Café Olimpico this morning...
```

**Why this works (but maybe too much?):**
- Includes every possible field
- Very detailed for future reference
- Good for significant life moments
- Probably overkill for daily entries

**Use comprehensive metadata like this when:**
- It's a major life moment
- You're developing it for manuscript
- Multiple threads converge
- You want complete record

**For most entries, much simpler metadata is fine!**

---

## Best Practices

### 1. Start Simple, Add Complexity

**Day 1:**
```yaml
---
date: 2024-01-15
---
Entry text.
```

**Week 1:**
```yaml
---
date: 2024-01-15
city: Montreal
tags: [personal]
---
Entry text.
```

**Month 1:**
```yaml
---
date: 2024-01-15
city: Montreal
locations:
  - Café Olimpico
people:
  - Sarah
tags: [personal, friends]
---
Entry text.
```

**Don't start with everything.** Add fields as you need them.

---

### 2. Be Consistent

**Pick a format and stick with it:**

```yaml
# ✅ Consistent
city: Montreal  # Always use this form
city: Toronto
city: Paris

# ❌ Inconsistent
city: Montreal
city: toronto  # Different capitalization
city: Paris, France  # Includes country sometimes
```

**Consistency matters for:**
- City names (Montreal vs montreal vs Montréal)
- Person names (John Smith vs J Smith vs John)
- Tag names (philosophy vs Philosophy vs philosophical)

---

### 3. Don't Overthink It

**Perfect is the enemy of good.**

```yaml
# ✅ Good enough
---
date: 2024-01-15
city: Montreal
tags: [personal]
---

# ❌ Overthinking (for a casual entry)
---
date: 2024-01-15
city: Montreal
locations:
  - "Living room"
  - "Kitchen"
  - "Bedroom"
people:
  - Self
tags: [personal, quiet, reflective, indoor, weekend]
events:
  - normal-day
  - typical-weekend
---
```

**Ask: Will I actually use this metadata?**

---

### 4. Add Metadata Later

**You can always add metadata to old entries:**

1. Write entry with minimal metadata
2. Import to database
3. Later, add more metadata
4. Re-import with `--force` flag

```bash
# Initial import
palimpsest yaml2sql --input md/

# Edit files to add metadata
vim md/2024/2024-01-15.md

# Re-import
palimpsest yaml2sql --input md/ --force
```

**Don't let metadata prevent you from writing.**

---

### 5. Use Templates

**Create templates for common entry types:**

**template-daily.md:**
```yaml
---
date: YYYY-MM-DD
city:
tags: []
---

```

**template-research.md:**
```yaml
---
date: YYYY-MM-DD
city:
locations: []
people: []
tags: [research]
events: [thesis-writing]
references: []
---

```

**template-creative.md:**
```yaml
---
date: YYYY-MM-DD
tags: [creative]
poems: []
---

```

**Copy template, fill in date and specific details.**

---

### 6. Review and Refine

**Periodically review your metadata:**

```bash
# See what tags you're using
palimpsest db query "SELECT DISTINCT tag FROM tags ORDER BY tag"

# See what people you've mentioned
palimpsest db query "SELECT name, full_name FROM people ORDER BY name"

# Check for inconsistencies
palimpsest db query "SELECT city FROM cities ORDER BY city"
```

**Refine:**
- Consolidate duplicate tags (personal-reflection → reflection)
- Standardize person names (John vs John Smith)
- Fix inconsistent city names

---

## Common Mistakes

### 1. Wrong Date Format

```yaml
# ❌ Wrong
date: 01/15/2024
date: 2024-1-15
date: January 15, 2024

# ✅ Correct
date: 2024-01-15
```

**Always use YYYY-MM-DD with zero-padding.**

---

### 2. Multiple Cities with Flat Location List

```yaml
# ❌ Wrong
city: [Montreal, Toronto]
locations:
  - Café Olimpico  # Which city??

# ✅ Correct
city: [Montreal, Toronto]
locations:
  Montreal:
    - Café Olimpico
  Toronto:
    - Library
```

**Multiple cities require nested location structure.**

---

### 3. Forgetting @ for Aliases

```yaml
# ❌ Creates a Person named "Majo"
people:
  - Majo

# ✅ Creates an Alias "Majo" pointing to person
people:
  - "@Majo (María-José)"
```

**Aliases require the @ symbol.**

---

### 4. Missing Required Reference Fields

```yaml
# ❌ Missing both content and description
references:
  - source:
      title: "Book"
      type: book

# ✅ Has content
references:
  - content: "Quote"
    source:
      title: "Book"
      type: book

# ✅ Has description
references:
  - description: "Paraphrase"
    source:
      title: "Book"
      type: book
```

**References need content OR description.**

---

### 5. Forgetting Quotes for Special Characters

```yaml
# ❌ Syntax error
locations:
  - Mom's house

# ✅ Correct
locations:
  - "Mom's house"
```

**Use quotes for apostrophes, colons, hash symbols, etc.**

---

### 6. Not Using | for Multi-line Poems

```yaml
# ❌ Line breaks not preserved
poems:
  - title: "Poem"
    content: "Line 1
Line 2
Line 3"

# ✅ Line breaks preserved
poems:
  - title: "Poem"
    content: |
      Line 1
      Line 2
      Line 3
```

**Always use `|` after `content:` for poems.**

---

## Progressive Complexity

### Week 1: Minimal

```yaml
---
date: 2024-01-15
---
```

**Just write. Don't worry about metadata.**

---

### Week 2: Basic Context

```yaml
---
date: 2024-01-15
city: Montreal
tags: [personal]
---
```

**Add location and basic categorization.**

---

### Week 3: People and Places

```yaml
---
date: 2024-01-15
city: Montreal
locations:
  - Café Olimpico
people:
  - Sarah
tags: [personal, friends]
---
```

**Track who and where.**

---

### Month 2: Events and Connections

```yaml
---
date: 2024-01-15
city: Montreal
locations:
  - Café Olimpico
people:
  - Sarah
tags: [personal, friends]
events:
  - montreal-period
related_entries:
  - "2024-01-10"
---
```

**Link to life periods and other entries.**

---

### Month 3: References and Creative Work

```yaml
---
date: 2024-01-15
city: Montreal
people:
  - Sarah
tags: [philosophy, creative]
references:
  - content: "Quote"
    source:
      title: "Book"
      type: book
      author: "Author"
poems:
  - title: "Poem Title"
    content: |
      Poem text here
---
```

**Track intellectual and creative work.**

---

### Later: Manuscript Development

```yaml
---
date: 2024-01-15
city: Montreal
people:
  - Sarah
tags: [identity, breakthrough]
manuscript:
  status: included
  themes:
    - identity-crisis
  notes: "Key scene for Chapter 3"
---
```

**Develop entries into creative work.**

---

## Troubleshooting

### "My YAML won't parse"

**Check:**
1. Are quotes balanced? `"text"` not `"text`
2. Is indentation correct? (2 spaces)
3. Are special characters quoted? `"Mom's house"`
4. Are lists formatted correctly?

**Common issues:**
```yaml
# ❌ Missing closing quote
epigraph: "Quote text

# ❌ Wrong indentation
people:
- John  # Should be 2 spaces

# ❌ Unquoted special character
locations:
  - Mom's house  # Needs quotes
```

---

### "Import fails with error"

**Check:**
1. Is date in YYYY-MM-DD format?
2. Is date unique (no duplicates)?
3. Are all required fields present?
4. Are reference types valid?

**Run with verbose flag:**
```bash
palimpsest yaml2sql --file entry.md --verbose
```

**Check the error message** - it will tell you what's wrong.

---

### "People/locations not linking correctly"

**Check:**
1. Are you spelling names consistently?
2. Are you using hyphens correctly?
3. For aliases, did you use @?

**Compare:**
```yaml
# Entry 1
people:
  - María José

# Entry 2
people:
  - Maria Jose  # Different spelling! Won't link
```

**Fix: Be consistent.**

---

### "Too much metadata feels overwhelming"

**Solution: Start minimal.**

```yaml
# Perfectly valid entry
---
date: 2024-01-15
---

Entry text.
```

**Add metadata only when it matters:**
- Don't track location if it's not relevant
- Don't add people if you were alone
- Don't overthink tags

**Remember: You can always add more later.**

---

### "How much is too much?"

**Rules of thumb:**

**For daily entries:**
- Date, city, 2-3 tags → Good
- Adding locations and people if relevant → Good
- 10+ fields → Probably too much

**For significant entries:**
- More metadata makes sense
- Events, references, manuscripts → Appropriate
- Still don't need everything

**Ask yourself:**
- Will I actually search for this?
- Does this help me find/understand this entry later?
- Am I adding metadata just to add it?

**If you're not sure, skip it.**

---

## Quick Start Checklist

### Your First Entry

- [ ] Create file: `md/YYYY/YYYY-MM-DD.md`
- [ ] Add `---` at top
- [ ] Add `date: YYYY-MM-DD`
- [ ] Add `---` after metadata
- [ ] Write entry content
- [ ] Save file

**Example:**
```markdown
---
date: 2024-01-15
---

Today I...
```

### Your First Import

```bash
palimpsest yaml2sql --input md/ --verbose
```

### Add More Metadata

- [ ] Add `city` if relevant
- [ ] Add `tags` for categorization
- [ ] Add `people` if you mentioned anyone
- [ ] Add `locations` if you were somewhere specific

**Re-import:**
```bash
palimpsest yaml2sql --input md/ --force
```

---

## Summary

### Required
- `date` (YYYY-MM-DD)

### Common
- `city`
- `tags`
- `people`

### As Needed
- `locations` (with city)
- `events` (life periods)
- `dates` (mentioned dates)
- `related_entries` (links)

### Special
- `references` (quotes/citations)
- `poems` (creative work)
- `manuscript` (narrative development)
- `epigraph` (opening quotes)

### Usually Skip
- `word_count` (auto-calculated)
- `reading_time` (auto-calculated)

### Remember
1. Start simple
2. Be consistent
3. Add more over time
4. Metadata serves you, not the other way around

---

## Next Steps

1. **Read:** Quick reference guide (METADATA_QUICK_REFERENCE.md)
2. **Reference:** Complete field guide (METADATA_GUIDE_YAML_SQL.md)
3. **Start writing:** Begin with minimal metadata
4. **Experiment:** Try different fields
5. **Find your style:** What works for you?

**Most important: Start writing.** The metadata will evolve naturally.

---

*Happy journaling!*
