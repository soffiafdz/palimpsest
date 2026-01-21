# Narrative Analysis Curation Workflow

This document describes the workflow for reviewing and curating the narrative analysis.

## Curation Status

The scene/events/arcs data is currently **under active curation**. After review is complete, this section will be updated to reflect that the data represents validated ground-truth.

---

## Document Overview

### Curation Documents (in `_curation/`)

| Document | Purpose | Use When |
|----------|---------|----------|
| `curation_summary.pdf` | Compact view: date, rating, summary, proposed motifs/tags | Quick review pass |
| `curation_full.pdf` | Full context: everything + journal text + themes + scenes | When you need source context |
| `vocabulary_proposal.md` | Consolidated motifs (~20) and tags (~30) definitions | Reference for vocabulary |

### Supplementary Views (in `_curation/`)

| Document | Purpose |
|----------|---------|
| `events_view_core.pdf` | Event-centric view for core story |
| `events_view_flashback.pdf` | Event-centric view for flashback |
| `unmapped_core.pdf` | Checklist of scenes without event assignments |
| `unmapped_flashback.pdf` | Checklist of scenes without event assignments |

---

## Vocabulary

### Motifs (~20 recurring patterns)

Cross-entry patterns tracked for arc structure:
- THE_BODY, VALIDATION_REJECTION, MASKS_PERFORMANCE, WAITING_TIME
- OBSESSIVE_LOOP, GHOSTS_PALIMPSESTS, ISOLATION, UNRELIABLE_NARRATOR
- DIGITAL_SURVEILLANCE, RESURRECTION_RETURN, CLOSURE_ENDINGS, MEDICALIZATION
- HAUNTED_GEOGRAPHY, THRESHOLD_LIMINAL, WRITING_SURVIVAL, LANGUAGE_SILENCE
- THE_CAVALRY, SUBSTITUTION, THE_DOUBLE, DISCLOSURE_SECRET, SEX_DESIRE

### Tags (~30 cross-entry categories)

Searchable categories for wiki dashboards:
- transition, identity, anxiety, depression, romance, family, dysphoria
- mental-health, obsession, therapy, academia, intimacy, technology
- rejection, messaging, medication, dating-apps, isolation, physical-health
- alcohol, photography, crisis, sleep, writing, food, sexuality
- media, work, substances, immigration

---

## Review Workflow

### Phase 1: Summary Review

1. Open `curation_summary.pdf` on iPad
2. For each entry, verify:
   - Proposed motifs are correct
   - Proposed tags are correct
   - People/locations are complete
3. Mark corrections directly on PDF

### Phase 2: Full Review (as needed)

1. Reference `curation_full.pdf` when you need:
   - Original journal text
   - Theme descriptions
   - Scene breakdowns
2. Cross-reference with summary corrections

### Phase 3: Apply Corrections

Share corrections with Claude to:
1. Apply vocabulary corrections to analysis files
2. Propagate to database
3. Regenerate wiki pages

---

## File Locations

```
data/journal/narrative_analysis/
├── _curation/                       <- Curation documents
│   ├── curation_summary.pdf         <- Quick review (compact)
│   ├── curation_full.pdf            <- Full context (with journal text)
│   ├── vocabulary_proposal.md       <- Vocabulary definitions
│   ├── events_view_core.pdf         <- Event validation
│   ├── events_view_flashback.pdf
│   ├── unmapped_core.pdf            <- Unmapped scenes
│   └── unmapped_flashback.pdf
├── _events/                         <- Monthly event manifests
├── _arcs/                           <- Arc manifest
└── 20*/                             <- Individual analysis files by year
```

---

## Regenerating Documents

```bash
# Main curation documents
python -c "from dev.pipeline.curation import generate_review_documents; generate_review_documents()"

# Supplementary views
plm narrative events-view --pdf
plm narrative extract-unmapped --pdf

# Legacy hierarchy views (if needed)
plm narrative compile-review --all --pdf
plm narrative compile-source --all --pdf
```
