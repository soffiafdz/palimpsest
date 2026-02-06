# Manual Validation Guide

> **Note:** This guide references the deprecated MentionedDate/Moment classification system.
> The current schema uses Scene, Thread, and NarratedDate models instead.
> Validation is now performed via `plm import-metadata` and consistency checks.

This guide covers two validation tasks for the Palimpsest project:
1. **Moments/References Validation** - Classifying `dates:` entries in YAML frontmatter
2. **Narrative Structure Validation** - Events and arcs in manifest files

---

## Part 1: Moments vs References Validation

### The Distinction

The `dates:` field in each entry's YAML frontmatter contains items that go to the **Moments table**. Each item must be classified as:

| Type | Definition | Example |
|------|------------|---------|
| **moment** | Action that happened on that date and is **narrated in detail** in this entry | Entry on Nov 8 narrates the first date that happened Nov 2 |
| **reference** | Past date that is **briefly mentioned** but not narrated | Entry mentions "like that time in April" without detail |

### Current State

- The parser **supports** `type: moment` or `type: reference`
- Default is `moment` if no type specified
- **Most YAML files don't have the `type:` field yet** - everything is treated as moments

### Your Task

For each item in `dates:`, decide if it's a moment or reference:
- If it's a **reference**, add `type: reference`
- If it's a **moment**, no change needed (it's the default)

### Location

```
data/journal/content/md/YYYY/YYYY-MM-DD.md
```

Focus on core material: Nov 2024 - Dec 2025 (141 entries)

### YAML Structure

**Before validation:**
```yaml
dates:
  - date: 2024-04-24
    context: "Date at #Typhoon-Lounge and night with @Bea"
  - date: 2024-11-02
    context: "First date with @Clara at #Chez-Ernest"
```

**After validation (if April is a reference, Nov 2 is a moment):**
```yaml
dates:
  - date: 2024-04-24
    type: reference
    context: "Date at #Typhoon-Lounge and night with @Bea"
  - date: 2024-11-02
    context: "First date with @Clara at #Chez-Ernest"
```

### How to Decide

Read the entry prose and ask:

1. **Is this date narrated in detail?** → `moment` (no type field needed)
   - Multiple paragraphs describing what happened
   - Dialogue, sensory details, emotional processing

2. **Is this date just mentioned in passing?** → `type: reference`
   - Brief callback: "like that time we went to..."
   - Contextual reminder without narration

### Additional Checks

While validating, also check:

1. **Date accuracy** - Does the context match what happened on that date?
2. **Missing dates** - Are there dates mentioned in prose not in the `dates:` field?
3. **People/locations** - Are `@Person` and `#Location` tags present where needed?

---

## Part 2: Narrative Structure Validation

### Approach: Direct Editing

Edit the manifest files directly. After editing, regenerate the wiki:

```bash
python -c "
from dev.wiki.exporter import WikiExporter
from dev.database.manager import PalimpsestDB
from dev.core.paths import DB_PATH, WIKI_DIR

db = PalimpsestDB(DB_PATH)
exporter = WikiExporter(db, WIKI_DIR)
exporter.export_narrative(force=True)
"
```

### Files to Edit

**Event manifests** (7 files):
```
data/journal/narrative_analysis/_events/
├── events_nov_dec_2024.md   (12 events)
├── events_jan_feb_2025.md   (5 events)
├── events_mar_2025.md       (10 events)
├── events_apr_2025.md       (8 events)
├── events_may_2025.md       (8 events)
├── events_jun_jul_2025.md   (7 events)
└── events_aug_dec_2025.md   (5 events)
```

**Arc manifest** (1 file):
```
data/journal/narrative_analysis/_arcs/arcs_manifest.md
```

### Event Manifest Format

```markdown
## Event 1: First Date with Clara

**Entries**: 2024-11-08
**Scenes**:
- The Six-Hour Date - Getting ready, meeting at Chez Ernest, A&W after
- Instagram Search - Looking up Clara's profile afterward
- Thomson House Evening - Pre-date drinks with colleagues

**Thematic Arcs**: THE OBSESSIVE LOOP, SEX & DESIRE
```

**To edit:**
- Change event names by editing the `## Event N: Name` line
- Add/remove entries in the `**Entries**:` line (comma-separated)
- Add/remove/rename scenes in the bullet list
- Change thematic arcs in the `**Thematic Arcs**:` line

### Arc Manifest Format

```markdown
## Arc 1: The Clara Obsession

**Theme**: The central romantic pursuit...
**Timespan**: November 2024 - December 2025
**Events**:
1. First Date with Clara (Nov-Dec 2024)
2. Second Date with Clara (Nov-Dec 2024)
...

**Arc Summary**: The memoir's spine tracks...
```

**To edit:**
- Change arc names in the `## Arc N: Name` line
- Edit the theme description
- Add/remove events from the numbered list
- Update the summary

### What to Validate

#### Event Level
1. **Entry assignments** - Does each entry belong in this event?
2. **Scene accuracy** - Do scene titles/descriptions match the prose?
3. **Missing content** - Are entries or scenes missing?

#### Arc Level
1. **Event assignments** - Does each event belong in this arc?
2. **Cross-arc events** - Should some events appear in multiple arcs?
3. **Arc completeness** - Do the 7 arcs capture all major threads?

### The 7 Arcs

| Arc | Events | Theme |
|-----|--------|-------|
| The Clara Obsession | 29 | Central romantic thread |
| The Breakdown | 9 | Mental health crisis |
| The Body's Betrayal | 7 | HRT, transition, dysphoria |
| The Cavalry | 10 | Support network |
| Alternative Loves | 4 | Florence, Paty, Amanda |
| Professional Survival | 6 | Academic milestones |
| The Animal Anchor | 4 | Nymeria |

### Cross-Arc Events (Currently)

These events intentionally appear in multiple arcs:
- Rock Bottom and Intervention → Breakdown + Cavalry
- Medical and Professional Fallout → Breakdown + Cavalry + Professional
- The Tamino Concert → Clara + Cavalry
- Return to Tijuana and Border Crossing → Body + Professional + Nymeria
- AAIC Conference → Body + Professional
- Amanda's Rejection & Nymeria's Crisis → Alternative Loves + Nymeria + Cavalry
- Meta-Fiction Ethics & Nymeria's Death → Clara + Professional + Nymeria

---

## Quick Reference

### File Locations

| What | Where |
|------|-------|
| Entry content (with YAML) | `data/journal/content/md/YYYY/YYYY-MM-DD.md` |
| Entry analysis | `data/journal/narrative_analysis/YYYY/YYYY-MM-DD_analysis.md` |
| Event manifests | `data/journal/narrative_analysis/_events/*.md` |
| Arc manifest | `data/journal/narrative_analysis/_arcs/arcs_manifest.md` |
| Generated wiki | `data/wiki/narrative/` |

### YAML Syntax for Dates

```yaml
dates:
  # Moment (default) - narrated in detail
  - date: 2024-11-02
    context: "First date with @Clara at #Chez-Ernest"

  # Reference - briefly mentioned
  - date: 2024-04-24
    type: reference
    context: "Remembered the date at #Typhoon-Lounge"

  # Same-day reference
  - date: .
    context: "@Clara liked the IG story"

  # With additional fields
  - date: 2024-11-07
    type: reference
    context: "Drinks at #Thomson-House"
    people: [Sasha, Marc-Antoine]
    locations: [The Neuro]
```

### People/Location Syntax in Context

```yaml
context: "Date at #Typhoon-Lounge with @Bea and @Majo (María-José)"
```

- `@Name` - Simple person reference
- `@Alias (Full-Name)` - Person with alias
- `#Location-Name` - Location reference
