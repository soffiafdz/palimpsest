2024 SCENE AND EVENT RENAME PROPOSALS
======================================

Generated: 2026-01-31
Source: /home/soffiafdz/Documents/palimpsest/data/metadata/journal/2024/
Files processed: 68 (January-October 2024)
Output: /home/soffiafdz/Documents/palimpsest/proposals_2024.json

SUMMARY
-------
Total problematic names: 157

Scenes:
  - Screenplay format (INT./EXT./FLASHBACK:): 7
  - Colon-prefix (Location: Action): 16
  Total scenes: 23

Events:
  - "At location" prefix: 53
  - Date suffix (YYYY-MM-DD): 55
  - Truncated text: 29 ⚠️ NEEDS MANUAL REVIEW
  - Numbered (e.g., "Event (2)"): 2
  Total events: 134

JSON STRUCTURE
--------------
The proposals_2024.json file contains three sections:

1. summary: Quick counts by issue type

2. organized: Proposals grouped by issue type
   - scenes_screenplay
   - scenes_colon
   - events_at_location
   - events_date_suffix
   - events_truncated
   - events_numbered

3. by_date: Original chronological view with full context
   Each entry contains:
   - date
   - file path
   - summary (entry summary)
   - scenes: array of problematic scenes with:
     * original name
     * proposed name
     * description
     * date
     * people
     * locations
     * issues (tags)
   - events: array of problematic events with:
     * original name
     * proposed name
     * scenes (list of scene names)
     * issues (tags)

AUTOMATED PROPOSALS
-------------------
The script applied these transformations:

Scenes:
  - Screenplay format: Removed INT./EXT./FLASHBACK: prefix and location/time suffix
    Example: "INT. BEDROOM - 1-2 AM" → extracted key phrase from description

  - Colon-prefix: Extracted action part after colon
    Example: "The Bar: First Date Confessions" → "First Date Confessions"

Events:
  - "At location": Removed "At " prefix
    Example: "At Bon Délire" → "Bon Délire"

  - Date suffix: Removed (YYYY-MM-DD) suffix
    Example: "Writing (2024-01-29)" → "Writing"

  - Numbered: Removed numbering suffix
    Example: "Alone at Home (3)" → "Alone at Home"

  - Truncated: Flagged for manual review
    Example: "S Was Planning To Play We" → "[TRUNCATED: S Was Planning To Play We]"

MANUAL REVIEW NEEDED
--------------------
29 truncated event names require manual review and proposal creation.

These are sentence fragments (likely encoding errors or AI truncation):
  - "S Day To See The Cuba Photos"
  - "T Be Enough"
  - "Ll Meet She"
  - "T Let It Out"
  - "I Won"
  - "S Confession Emerges"
  - "T Have A Uterus I Don"
  - "Je Veux Qu"
  - "You Don"
  - "She Hasn"
  ... and 19 more

To fix these, you need to:
1. Read the source YAML file
2. Read the associated scenes
3. Understand the event's narrative essence
4. Create an evocative, specific event name

NEXT STEPS
----------
1. Review automated proposals for scenes and simple events
2. Manually create proposals for the 29 truncated events
3. Apply renames systematically across all files
4. Update md_frontmatter fields to match renamed scenes/events

NOTES
-----
- Event names should differ from scene names (especially 1:1 ratios)
- Event names must be unique unless linking to the same real-world event
- Prefer evocative over literal names
- Avoid generic names that could apply to any entry
