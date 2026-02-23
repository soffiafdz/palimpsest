# Wiki Redesign Specification

This document outlines the new design for the Palimpsest wiki, based on the requirements in `docs/development/wiki-redesign-prompt.md`.

## Design Principles (Recap)

1.  **Monospace & Concealment:** Designs must account for invisible wikilink characters disrupting alignment. No tables with links.
2.  **One Link Per Line:** Never place two wikilinks on the same line (e.g., `[Link A] · [Link B]`). The raw text length will trigger unexpected wrapping.
3.  **Navigation First:** Prioritize links to key actions (edit metadata, view source) and related entities. No "Back" links.
4.  **No Scrolling:** Main pages < 150 lines. Use subpages for large lists.
5.  **Editability:** Clear signals for editable data (YAML links via `<leader>em`).
6.  **Context:** Dates must always have years (except in year-specific contexts).

---

## 1. Entry Page (Journal Day)

**User Task:** Review a specific day's journal entry, see its metadata context, and navigate to connected entities.
**Primary Action:** Read the entry content (linked), Edit metadata.

**Information Hierarchy:**
1.  Header: Date, Summary, Rating.
2.  Navigation: Previous/Next Day (Vertical stack).
3.  Content Links: Open Markdown (Source), Open Metadata (YAML).
4.  Context: People, Places, Events, Threads (Vertical lists with indentation for secondary links).
5.  Creative: Poems, References.

**Mockup:**

```markdown
# Friday, November 8, 2024

[< Nov 7, 2024][/journal/entries/2024/2024-11-07]
[Nov 9, 2024 >][/journal/entries/2024/2024-11-09]

**Rating:** ★★★★☆ (4.0)
**Summary:** Met Léa for coffee. Discussed the manuscript. Rainy day.

---

## Content
- [Read Entry (Markdown)][/data/journal/content/2024/2024-11-08.md]
- [Edit Metadata (YAML)][/data/metadata/journal/2024/2024-11-08.yaml]
- **Stats:** 450 words · 2 min read

## Context
**People**
- [Léa Fournier][/journal/people/lea-fournier] (Friend)
- [Marc-André][/journal/people/marc-andre] (Colleague)

**Places**
- [Café Olimpico][/journal/locations/montreal/cafe-olimpico]
  City: [Montréal][/journal/cities/montreal]

**Events**
- [The Coffee Meeting][/journal/events/the-coffee-meeting]
  Arc: [The Manuscript][/journal/arcs/the-manuscript]

**Threads**
- [Project Planning][/journal/threads/project-planning] (Nov 2024 – Dec 2024)

## Creative
**Poems**
- [Rain on the Window][/journal/poems/rain-on-the-window] (v2)

**References**
- [The Unbearable Lightness of Being][/journal/references/the-unbearable-lightness-of-being] (Book)
```

**Subpage Strategy:**
-   **Rating:** If justification is long (> 3 lines), link to `[Full Rating & Justification][/journal/entries/2024/2024-11-08-rating]` subpage.

**Context Builder Changes:**
-   Ensure `prev_date` and `next_date` are available.
-   Provide `reading_time` and `word_count`.

---

## 2. Person Page

**User Task:** Understand who this person is, their relationship to the narrator, and their narrative significance.
**Primary Action:** See relationship status, recent interactions, and key arcs.

### Tier 1: Narrator (Special Case)

**Information Hierarchy:**
1.  Header: Name.
2.  Stats: Total Entries.
3.  Top Companions (aggregated).
4.  Top Places (aggregated).

**Mockup:**

```markdown
# Narrator

**Entries:** 384
**First:** [Jan 1, 2021][/journal/entries/2021/2021-01-01]
**Last:** [Jun 30, 2025][/journal/entries/2025/2025-06-30]

---

## Top Companions
1. [Léa Fournier][/journal/people/lea-fournier] (89)
2. [Marc-André][/journal/people/marc-andre] (45)
3. [Sophie][/journal/people/sophie] (22)

## Top Places
1. [Apartment - Jarry][/journal/locations/montreal/apartment-jarry] (153)
2. [Café Olimpico][/journal/locations/montreal/cafe-olimpico] (40)
```

### Tier 2: Frequent (20+ Entries)

**Information Hierarchy:**
1.  Header: Name, Relation, Tier (Implicit).
2.  Stats: Entry Count, Date Range.
3.  Arc/Event Spine: Major arcs they participate in.
4.  Recent/Key Entries (limited).
5.  Link to "All Entries" subpage.

**Mockup:**

```markdown
# Léa Fournier

**Relation:** Friend
**Entries:** 89
**Period:** [Jan 2021 – Present][/journal/people/lea-fournier-timeline]

---

## Narrative Arcs
**[The Dating Carousel][/journal/arcs/the-dating-carousel]** (2021–2022)
- [First Date][/journal/events/first-date]
  Date: [Nov 8, 2021][/journal/entries/2021/2021-11-08]

- [The Weekend Trip][/journal/events/the-weekend-trip]
  Dates:
  - [Nov 15, 2021][/journal/entries/2021/2021-11-15]
  - [Nov 16, 2021][/journal/entries/2021/2021-11-16]

**[The Manuscript][/journal/arcs/the-manuscript]** (2024–2025)
- [Feedback Session][/journal/events/feedback-session]
  Date: [Mar 10, 2025][/journal/entries/2025/2025-03-10]

## Recent Interactions
- [Jun 30, 2025][/journal/entries/2025/2025-06-30]
  Lunch at Olimpico.
- [Jun 15, 2025][/journal/entries/2025/2025-06-15]
  Phone call about the draft.

## Navigation
- [View All 89 Entries][/journal/people/lea-fournier/entries]
- [Manuscript Character: Léa][/manuscript/characters/lea]
```

**Subpage Strategy:**
-   **Entries:** `[View All {N} Entries][/journal/people/{slug}/entries]` is MANDATORY.
-   **Timeline:** Optional timeline visualization subpage.

**Context Builder Changes:**
-   Compute "Arc/Event Spine": Group events by Arc for this person.
-   Identify "Recent Interactions" (last 5).

### Tier 3: Infrequent (<20 Entries)

**Information Hierarchy:**
1.  Header: Name, Relation.
2.  Stats: Entry Count.
3.  All Entries List (grouped by year/month).

**Mockup:**

```markdown
# The Barista

**Relation:** Acquaintance
**Entries:** 3

---

## Appearances
**2025**
- [Jun 30, 2025][/journal/entries/2025/2025-06-30]
  Made a great latte.

**2024**
- [Nov 8, 2024][/journal/entries/2024/2024-11-08]
  Asked about my book.
- [Jan 15, 2024][/journal/entries/2024/2024-01-15]
  New haircut.
```

---

## 3. Location Page

**User Task:** See when and why I visited this place.
**Primary Action:** Check visit history and associated events.

### Tier 1: Dashboard (20+ Entries)

**Information Hierarchy:**
1.  Header: Name, City.
2.  Stats: Visit Count, First/Last.
3.  Events Here (Arc-grouped).
4.  Frequent People Here.
5.  Link to "All Visits" subpage.

**Mockup:**

```markdown
# Apartment - Jarry
[Montréal][/journal/cities/montreal]

**Visits:** 153
**First:** [Jan 1, 2021][/journal/entries/2021/2021-01-01]
**Last:** [Jun 30, 2025][/journal/entries/2025/2025-06-30]

---

## Events
**[The Pandemic][/journal/arcs/the-pandemic]**
- [Lockdown Begins][/journal/events/lockdown-begins]
  Date: [Mar 15, 2020][/journal/entries/2020/2020-03-15]

## Frequent People
1. [Léa Fournier][/journal/people/lea-fournier] (15)
2. [Marc-André][/journal/people/marc-andre] (10)

## Navigation
- [View All 153 Visits][/journal/locations/montreal/apartment-jarry/entries]
```

### Tier 2/3: Mid/Minimal (<20 Entries)

**Information Hierarchy:**
1.  Header: Name, City.
2.  Stats.
3.  All Visits List.

**Mockup:**

```markdown
# The Old Port
[Montréal][/journal/cities/montreal]

**Visits:** 5

---

## Visits
**2025**
- [Jun 01, 2025][/journal/entries/2025/2025-06-01]
  Walk with Léa.

**2024**
- [Jul 14, 2024][/journal/entries/2024/2024-07-14]
  Fireworks.
```

**Subpage Strategy:**
-   **Visits:** Subpage for >20 entries.

**Context Builder Changes:**
-   Group events by Arc for location context.

---

## 4. City Page

**User Task:** Overview of life in a specific city.
**Primary Action:** See top locations and key timeline.

**Mockup:**

```markdown
# Montréal
**Country:** Canada
**Entries:** 286
**Locations:** 150

---

## Top Locations
1. [Apartment - Jarry][/journal/locations/montreal/apartment-jarry] (153)
2. [Café Olimpico][/journal/locations/montreal/cafe-olimpico] (40)
3. [Parc Jarry][/journal/locations/montreal/parc-jarry] (25)

## Key People
1. [Léa Fournier][/journal/people/lea-fournier]
2. [Marc-André][/journal/people/marc-andre]

## Timeline
[View Timeline Subpage][/journal/cities/montreal/timeline]
```

---

## 5. Event Page

**User Task:** Recall details of a specific event and its scenes.
**Primary Action:** Read scene descriptions and see participating people.

**Mockup:**

```markdown
# The First Date
**Arc:** [The Dating Carousel][/journal/arcs/the-dating-carousel]
**Date:** [Nov 8, 2021][/journal/entries/2021/2021-11-08]

---

## Scenes
**1. Meeting at the Bar**
*People:*
- [Léa Fournier][/journal/people/lea-fournier]

*Location:*
- [Bar Henrietta][/journal/locations/montreal/bar-henrietta]

> Awkward first greeting. She wore a red dress.

**2. Walking Home**
*People:*
- [Léa Fournier][/journal/people/lea-fournier]

*Location:*
- [Rachel Street][/journal/locations/montreal/rachel-street]

> It started raining.

## Related Entries
- [Nov 8, 2021][/journal/entries/2021/2021-11-08]
- [Nov 9, 2021][/journal/entries/2021/2021-11-09]
  (Reflection)
```

---

## 6. Arc Page

**User Task:** Track a long-running narrative structure.
**Primary Action:** See the sequence of events.

**Mockup:**

```markdown
# The Dating Carousel
**Status:** Active
**Entries:** 177

> A chaotic period of trying to find love in the city.

---

## Event Timeline
**2021**
- [The First Date][/journal/events/the-first-date]
  Date: [Nov 8, 2021][/journal/entries/2021/2021-11-08]

- [The Weekend Trip][/journal/events/the-weekend-trip]
  Dates:
  - [Nov 15, 2021][/journal/entries/2021/2021-11-15]
  - [Nov 16, 2021][/journal/entries/2021/2021-11-16]

**2022**
- [The Breakup][/journal/events/the-breakup]
  Date: [Feb 14, 2022][/journal/entries/2022/2022-02-14]

## Key People
- [Léa Fournier][/journal/people/lea-fournier]
- [Sophie][/journal/people/sophie]

## Navigation
- [View All 177 Entries][/journal/arcs/the-dating-carousel/entries]
```

**Subpage Strategy:**
-   **Entries:** Subpage for >20 entries.

---

## 7. Tag/Theme Page

**User Task:** Analyze patterns across entries.

**Mockup (Dashboard - >5 entries):**

```markdown
# #writing (Tag)

**Entries:** 45
**First:** [Jan 10, 2021][/journal/entries/2021/2021-01-10]

---

## Co-occurring Patterns
- [cafes][/journal/tags/cafes] (15)
- [The Manuscript][/journal/arcs/the-manuscript] (10)

## Recent Entries
- [Jun 30, 2025][/journal/entries/2025/2025-06-30]
- [Jun 28, 2025][/journal/entries/2025/2025-06-28]

[View All 45 Entries][/journal/tags/writing/entries]
```

---

## 8. Manuscript Pages

### Chapter Page

```markdown
# Chapter 1: The Beginning
**Part:** [Part I][/manuscript/parts/part-i]
**Status:** Draft
**Type:** Prose

---

## Synopsis
Introduction to the city and the main conflict.

## Scenes
1. **[The Arrival][/manuscript/scenes/the-arrival]** (Composite)
   - Source: [Nov 8, 2021][/journal/entries/2021/2021-11-08]

2. **[The Dream][/manuscript/scenes/the-dream]** (Inferred)

## Characters
- [Protagonist][/manuscript/characters/protagonist]
- [Léa][/manuscript/characters/lea]
```

### Character Page

```markdown
# Léa (Character)
**Based On:** [Léa Fournier][/journal/people/lea-fournier]
**Role:** Love Interest

---

## Appearances
- [Chapter 1: The Beginning][/manuscript/chapters/chapter-1]
  (Primary)
- [Chapter 5: The Fall][/manuscript/chapters/chapter-5]
  (Mentioned)
```

---

## 9. Index Pages

**User Task:** Navigate to specific entities.
**Design:** Clean lists, grouped by letter or category.

**Mockup (People Index):**

```markdown
# People Index

## A
- [Alice][/journal/people/alice]
- [Arthur][/journal/people/arthur]

## C
- [Léa Fournier][/journal/people/lea-fournier] (89)
```

**Context Builder Changes:**
-   Ensure indices are sorted and grouped efficiently.

---

## 10. Poem & Reference Pages

**Poem Page:**
```markdown
# Rain on the Window
**Versions:** 2
**Last Edit:** [Nov 8, 2024][/journal/entries/2024/2024-11-08]

---

## Latest Version (v2)
The rain falls hard
Against the glass
Like memories...

[View All Versions][/journal/poems/rain-on-the-window/versions]
```
