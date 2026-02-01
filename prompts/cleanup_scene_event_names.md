# Scene and Event Name Cleanup Prompt

Use this prompt with Sonnet agents to clean up scene and event names in metadata YAML files.

## Task Overview

Clean up scene and event names in `/home/soffiafdz/Documents/palimpsest/data/metadata/journal/{YYYY}/{YYYY-MM-DD}.yaml` files for years 2021-2024 (excluding 2024-11 onwards).

## Rules

### 1. Scene Name Cleanup

Rename any scene that has:
- **Colons (`:`)** - e.g., `"FLASHBACK: EXT. PARC LA FONTAINE"` → `"The Laura Flashback"`
- **Parentheses (`(`)** - e.g., `"INT. BEDROOM - EARLY MORNING (INSOMNIA)"` → `"Early Morning Insomnia"`
- **Screenwriting format** - Any name starting with `INT.`, `EXT.`, or following the pattern `LOCATION - TIME`:
  - `"INT. APARTMENT - AFTERNOON"` → Something evocative based on description
  - `"EXT. PARC LA FONTAINE - YEARS AGO"` → Based on what happens in the scene

**Good scene names are:**
- **Like book chapter titles** - evocative, literary, intriguing
- Short but memorable (2-5 words typically)
- Capture a specific image, tension, or turning point from the description
- No colons, parentheses, or screenwriting conventions
- Examples: `"The Gray Fence"`, `"Option Tea, Option Kafé"`, `"The Swipe Trick"`, `"Demacrada"`, `"Chekhov's Raki"`, `"The Uninvited Memory"`

**To rename a scene:**
1. **Read the scene's `description` field carefully** - this is essential
2. Identify the core image, emotion, or narrative beat
3. Create a name like a book chapter title - something that would make a reader curious
4. Avoid literal/functional names ("Texting at Home") - prefer evocative ones ("The Unanswered Ellipsis")
5. Ensure uniqueness within the entry

### 2. Event Name Cleanup

Rename any event that has:
- **Colons (`:`)**
- **Parentheses (`(`)** - e.g., `"Writing (2021-08-06)"`, `"At Table (2022-01-26)"`, `"Alone at Home (2)"`
- **Truncated/auto-generated names** - e.g., `"S Instagram While Insisting She Doesn"`, `"T Be Enough"`

**Good event names are:**
- **Like section titles in a memoir** - evocative, thematic
- Different from the scene names they contain
- Capture the narrative arc or emotional throughline of grouped scenes
- Specific to THIS entry (avoid generic names like "Morning Routine", "At Home", "Writing")
- Examples: `"The Cavalry Arrives"`, `"Splitting the Wait"`, `"Through the Fog"`, `"Un Clavo No Saca A Otro Clavo"`, `"The Trans Traveler"`

**To rename an event:**
1. **Read all scenes listed in the event's `scenes` array** - look up each scene's description
2. Understand what narrative thread or emotional arc connects them
3. Create a name that captures the overarching movement - the "chapter" these scenes form together
4. Think: "If this were a section in a book, what would it be called?"
5. Avoid dates, locations, or actions in the name - prefer mood, metaphor, or key images

### 3. Event Uniqueness Across Entries

Two events in DIFFERENT entries may share the same name ONLY IF they describe the same real-world event that spans multiple journal entries.

**Check:** If you find two events with the same name:
1. Look at the scene dates within each event
2. If the dates are the same or consecutive (same real event narrated across entries) → OK to keep same name
3. If the dates are different (unrelated events) → Rename one to be unique

**Example of valid same-name events:**
- Entry 2024-03-15 has event "The Saint Patrick's Party" with scenes dated 2024-03-17
- Entry 2024-03-18 has event "The Saint Patrick's Party" with scenes dated 2024-03-17
- Both describe the same party → OK

**Example requiring rename:**
- Entry 2021-08-07 has event "Alone at Home (1)"
- Entry 2021-08-03 has event "Alone at Home (2)"
- Different days, unrelated → Rename both to something specific

## Process

For each YAML file:

1. **Read the file** completely
2. **Identify scenes to rename** - list them with current name and proposed new name
3. **Identify events to rename** - list them with current name and proposed new name
4. **Check for cross-entry event duplicates** - only if you've processed multiple files
5. **Present changes in a table** for approval before editing:

```
| Type | Current Name | Proposed Name | Reason |
|------|--------------|---------------|--------|
| Scene | INT. APARTMENT - AFTERNOON | The Aliza Text | Screenwriting format |
| Event | Writing (2024-02-13) | Craving Intimacy | Parentheses, generic |
```

6. **After approval**, edit the YAML file
7. **Update `md_frontmatter.events`** if event names changed (this field lists event names)

## Files to Process

```
/home/soffiafdz/Documents/palimpsest/data/metadata/journal/2021/*.yaml
/home/soffiafdz/Documents/palimpsest/data/metadata/journal/2022/*.yaml
/home/soffiafdz/Documents/palimpsest/data/metadata/journal/2023/*.yaml
/home/soffiafdz/Documents/palimpsest/data/metadata/journal/2024/*.yaml (exclude 2024-11-* onwards)
```

## Reference Files

For context on existing names:
- `/home/soffiafdz/Documents/palimpsest/scene_names_2021-2024.txt`
- `/home/soffiafdz/Documents/palimpsest/event_names_2021-2024.txt`

## Important Notes

- Always read the source journal entry at `/home/soffiafdz/Documents/palimpsest/data/journal/content/md/{YYYY}/{YYYY-MM-DD}.md` if you need more context
- Scene names must be unique within an entry
- Event names should be unique across ALL entries (unless same real-world event)
- Don't change scene/event names that are already good (no colons, parentheses, or screenwriting format)
- Preserve all other fields (description, date, people, locations, etc.)
