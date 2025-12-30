# Scenes/Events/Arcs Review Workflow

This document describes the workflow for reviewing and curating the narrative analysis.

## Curation Status

The scene/events/arcs data is currently **under active curation**. After review is complete, this section will be updated to reflect that the data represents validated ground-truth.

---

## Document Overview

### For Reading/Annotation (PDFs in _review/)

| Document | Purpose | Use When |
|----------|---------|----------|
| `_review/core_review.pdf` | Entry → Scene → Event → Arc hierarchy | Quick reference, overview |
| `_review/flashback_review.pdf` | Same for flashback material | Quick reference, overview |
| `_review/core_source_review.pdf` | Analysis + original journal text | Validating scene accuracy against source |
| `_review/flashback_source_review.pdf` | Same for flashback | Validating scene accuracy against source |

### For Active Curation (Markdown in _review/)

| Document | Purpose |
|----------|---------|
| `corrections_log.md` | **Record corrections here** - share with Claude to implement |
| `unmapped_core.md` | Checklist of scenes without event assignments |
| `unmapped_flashback.md` | Checklist of scenes without event assignments |
| `events_view_core.md` | Event-centric view for validating groupings |
| `events_view_flashback.md` | Same for flashback |

---

## Review Workflow

### Phase 1: Scene Validation

**Goal**: Verify scenes are correctly extracted from entries

1. Open `core_source_review.pdf` (or flashback version)
2. For each entry, compare:
   - Listed scenes vs. actual source text
   - Are all significant moments captured?
   - Are scene titles accurate and evocative?
   - Are descriptions correct?
3. Record corrections in `corrections_log.md`:
   ```markdown
   ## Scene: 2024-11-15
   - Problem: Scene title doesn't match content
   - Current: "The Sexual Fantasy"
   - Correction: "Morning Fantasies" (better captures the timing)
   ```

### Phase 2: Event Assignment

**Goal**: Ensure scenes are correctly grouped into events

1. Review `unmapped_core.md` first (prioritize unmapped scenes)
2. For each unmapped scene, decide:
   - Should it join an existing event?
   - Should a new event be created?
   - Is it too minor to warrant event inclusion?
3. Use `events_view_core.md` to see existing events
4. Record in `corrections_log.md`:
   ```markdown
   ## Event Assignment: 2024-11-12
   - Scene: "Aliza's Mock Candidacy"
   - Current Event: NOT MAPPED
   - Correct Event: Event 7: Academic Life and Weight Loss
   ```
   Or for new events:
   ```markdown
   ## New Event: 2024-11
   - Event Name: "Aliza's Candidacy Journey"
   - Entries: 2024-11-12, 2024-11-27
   - Scenes:
     - Aliza's Mock Candidacy (from 2024-11-12)
     - Aliza's Practice Candidacy (from 2024-11-27)
   - Thematic Arcs: THE_CAVALRY, MASKS_&_PERFORMANCE
   ```

### Phase 3: Event Validation

**Goal**: Verify events correctly group related scenes

1. Open `events_view_core.md`
2. For each event, ask:
   - Do all scenes belong together narratively?
   - Are any scenes miscategorized?
   - Is the event name appropriate?
3. Record corrections as needed

### Phase 4: Arc Assignment

**Goal**: Verify events are assigned to correct thematic arcs

1. Review events in context of the major arcs:
   - THE_CLARA_OBSESSION
   - THE_BREAKDOWN
   - THE_BODY'S_BETRAYAL
   - THE_CAVALRY
   - ALTERNATIVE_LOVES
   - PROFESSIONAL_SURVIVAL
   - THE_ANIMAL_ANCHOR
2. Check arc manifest: `_arcs/arcs_manifest.md`
3. Record corrections:
   ```markdown
   ## Arc Assignment: Event 12: Hypomania and Self-Portrait
   - Current Arcs: THE_BODY, THE_UNRELIABLE_NARRATOR
   - Correct Arcs: THE_BODY, THE_UNRELIABLE_NARRATOR, THE_BREAKDOWN
   ```

---

## Implementing Corrections

After completing your review:

1. Save all corrections in `corrections_log.md`
2. Share the file with Claude (copy/paste or reference the file)
3. Claude will:
   - Parse your corrections
   - Update the analysis files
   - Update the events files
   - Regenerate review documents

Example prompt:
> "I've completed reviewing the core story scenes. Please implement the corrections in `_review/corrections_log.md`"

---

## Progress Tracking

Use the checklists in unmapped files:
- `- [ ]` = Not reviewed
- `- [x]` = Resolved (assigned to event or marked as minor)

---

## File Locations

```
data/journal/narrative_analysis/
├── _review/                         ← Working documents + review PDFs
│   ├── corrections_log.md          ← Record your corrections
│   ├── unmapped_core.md            ← Priority checklist
│   ├── unmapped_flashback.md       ← Priority checklist
│   ├── events_view_core.md         ← Event validation
│   ├── events_view_flashback.md
│   ├── core_review.pdf             ← Hierarchy view (generated)
│   ├── flashback_review.pdf        ← (generated)
│   ├── core_source_review.pdf      ← Source + analysis (generated)
│   └── flashback_source_review.pdf ← (generated)
├── _events/                         ← Monthly event files (source of truth)
├── _arcs/                           ← Arc manifest
├── 2024/, 2025/, etc.              ← Individual analysis files
└── consolidated_tags_themes.md     ← Reference index (curated)

tmp/                                 ← Timeline compilations (for reading)
├── core_analyses_compiled.pdf
├── early_transition_compiled.pdf
└── montreal_life_compiled.pdf
```

---

## Regenerating Documents

After corrections are implemented, regenerate using the CLI:

```bash
# Review PDFs (output to _review/)
plm narrative compile-review --all --pdf
plm narrative compile-source --all --pdf

# Working documents (output to _review/)
plm narrative extract-unmapped
plm narrative events-view

# Timeline compilations for reading (output to tmp/)
plm narrative compile-timeline core --pdf
plm narrative compile-timeline early_transition --pdf
plm narrative compile-timeline montreal_life --pdf
```
