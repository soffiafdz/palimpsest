# Palimpsest Project Instructions

This file contains project-specific instructions for Claude Code that persist across sessions.

## Git Commits

- **No `git add -A`** — every commit should be intentional, stage specific files
- **Brief, descriptive commit messages** — prefer one-liners
- **No AI attribution** — do not mention AI, co-authors, or automated generation in commits
- The `data/` directory is a git submodule — commit changes there separately before updating the submodule reference in the main repo

## Code Style Requirements

### Docstrings

All functions and methods must have detailed docstrings following the existing codebase pattern:

```python
def example_function(self, param1: str, param2: Optional[int] = None) -> bool:
    """
    Brief one-line description of what this function does.

    More detailed explanation if needed, covering the purpose,
    behavior, and any important notes about usage.

    Args:
        param1: Description of first parameter
        param2: Description of second parameter (optional)

    Returns:
        Description of what is returned

    Raises:
        ValidationError: When validation fails
        DatabaseError: When database operation fails

    Notes:
        - Additional implementation notes
        - Edge cases or special behaviors
    """
```

### Module Headers

All Python files must have a detailed introductory docstring:

```python
#!/usr/bin/env python3
"""
module_name.py
--------------
Brief description of the module's purpose.

Detailed explanation of what this module provides, including:
- Key features and capabilities
- How it fits into the larger system
- Important design decisions or patterns used

Key Features:
    - Feature 1 with brief description
    - Feature 2 with brief description
    - Feature 3 with brief description

Usage:
    # Example usage code
    instance = ModuleClass(param1, param2)
    result = instance.method()

Dependencies:
    - List any notable dependencies if relevant
"""
```

### Type Annotations

- All function parameters must have type annotations
- All return types must be annotated
- Use `Optional[T]` for nullable types
- Use `List[T]`, `Dict[K, V]` for collections
- Import typing constructs: `from typing import Any, Dict, List, Optional, Type`

## Project Structure

Key directories:
- `dev/core/` - Path configuration, validators, exceptions, logging
- `dev/database/models/` - SQLAlchemy ORM models
- `dev/database/managers/` - Entity managers
- `dev/wiki/` - Jinja2 template-based wiki renderer
- `dev/pipeline/` - Data conversion pipelines
- `tests/` - Pytest test suite

## No Compatibility Aliases

When making breaking changes:
- Propagate changes to all call sites
- Do NOT add compatibility aliases or backward-compatible shims
- Delete unused code completely

## Database Manager Patterns

### Using BaseManager Helpers

Always use the inherited helpers from `BaseManager`:
- `_exists(model, field, value)` - Check existence
- `_get_by_id(model, id)` - Get by ID with soft-delete support
- `_get_by_field(model, field, value)` - Get by field value
- `_get_all(model, order_by=None)` - Get all with ordering
- `_update_scalar_fields(entity, metadata, field_configs)` - Update fields
- `_update_relationships(entity, metadata, relationship_configs)` - Update M2M
- `_resolve_parent(spec, model, get_method)` - Resolve parent entities

### Database Operations

Use the DatabaseOperation context manager for all database methods:
```python
from dev.database.decorators import DatabaseOperation
from dev.core.validators import DataValidator

def method(self, metadata):
    DataValidator.validate_required_fields(metadata, ["required_field"])
    with DatabaseOperation(self.logger, "operation_name"):
        # actual database logic here
```

### Custom Exceptions

- `ValidationError` - For validation failures (user input errors)
- `DatabaseError` - For database operation failures (internal errors)

## Import Ordering

Follow this import order with blank lines between sections:

```python
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import ValidationError, DatabaseError
from dev.core.validators import DataValidator
from dev.database.decorators import handle_db_errors
```

## Testing Requirements

- Minimum coverage: 15% (enforced by CI)
- Test files: `tests/unit/` and `tests/integration/`
- Run tests with: `python -m pytest tests/ -q`
- Use fixtures from `conftest.py`

### Mandatory Testing for All Changes

**Every code addition or modification MUST include:**

1. **Unit tests** for new functions/methods
2. **Integration tests** if the change affects multiple modules
3. **Test coverage** for edge cases and error conditions

Place tests in the corresponding location:
- `dev/module/file.py` → `tests/unit/module/test_file.py`

## Development Workflow

When making any code changes, follow these steps:

### 1. Documentation First

Before writing code:
- Understand the existing patterns in the codebase
- Plan the module header and key docstrings

### 2. Implementation

Code must include:
- **Module header**: Script purpose, features, usage examples, dependencies
- **Type annotations**: All parameters and return types
- **Detailed docstrings**: Args, Returns, Raises, Notes sections

### 3. Testing

Create tests before considering a feature complete:
- Test happy paths
- Test edge cases
- Test error conditions

### 4. Documentation Update

Update relevant docs:
- `CLAUDE.md` for persistent instructions
- Module docstrings for usage guidance

## Documentation Standards

**CRITICAL: Documentation is timeless code documentation, not implementation reports**

Documentation exists in `docs/` and should be production-level quality. Follow these strict rules to prevent report-style formatting and plan leakage.

### Absolute Prohibitions

**NEVER include in documentation:**
- Phase numbers (Phase 1, Phase 14b, etc.)
- Plan references (Phase 5, future enhancement)
- Migration language (migrate from X to Y, after migration)
- Transition language (transition guide, moving to new system)
- "Old" vs "new" comparisons (replaced old X with new Y)
- Deprecated/legacy code mentions (this replaces the old...)
- Implementation timelines (Phase 1 will..., next we'll...)
- Historical proposals (we decided to..., originally we...)
- "One-time" processes (run this once to migrate)
- "After X is done" conditional language
- References to what "changed" or "was replaced"
- Analysis reports (test failure analysis, performance report)

**These are planning artifacts, not documentation. Use git history for historical context.**

### Documentation Must Be

1. **Timeless** - Act as if current implementation is how it always was
2. **Reference Material** - Explain what exists and how to use it
3. **Production-Level** - Clean, well-organized, professional
4. **Integrated** - Update existing docs, don't create scattered new ones

### Directory Organization

- `docs/reference/` - API references, field specs, command references
- `docs/guides/` - Task-oriented workflows (how to do X)
- `docs/development/` - Architecture, patterns, contributor guides
- `docs/integrations/` - Editor and tool integrations
- `docs/narrative_structure/` - Narrative analysis guidelines (user-specific)

**DO NOT create:**
- `docs/migrations/` - Migration docs are temporary, not reference material
- `docs/plans/` or `docs/proposals/` - Use issue tracker or planning files
- `dev/docs/` - Development docs belong in `docs/development/`
- Random scattered markdown files - Integrate into existing structure

### What Documentation Should Contain

**Explain:**
- **What**: What does this feature/component do?
- **Why**: What problem does it solve?
- **How**: How do you use it?

**Include:**
- Clear examples
- Common patterns
- Troubleshooting (for current system)
- Cross-references to related docs

### Examples

**BAD - Plan Language:**
```markdown
# Phase 14b: Jumpstart Migration

This replaces the old Moment model with Scene/Thread.
After the one-time migration, narrative_analysis/ will be deleted.

## Migration Steps
1. Run jumpstart.py (one-time)
2. Validate data
3. Delete old files
```

**GOOD - Timeless Reference:**
```markdown
# Entity Curation Workflow

Extract and curate entities from YAML files before database import.

## Workflow
1. Extract entities with auto-grouping
2. Review and refine in draft file
3. Validate with disambiguation rules
4. Import to database
```

**BAD - Historical Comparison:**
```markdown
# Database Schema

The new schema replaces MentionedDate with Moment and adds Scene/Thread.
This was changed in Phase 14a to support narrative structure.
```

**GOOD - Current State:**
```markdown
# Database Schema

The database tracks narrative structure using:
- **Moment**: Temporal points with context
- **Scene**: Narrative units within entries
- **Thread**: Connections across time
```

**BAD - Future Enhancement:**
```markdown
# Conflict Resolution

Currently uses last-write-wins. Phase 5 will add three-way merge.
```

**GOOD - Current with Potential:**
```markdown
# Conflict Resolution

Uses last-write-wins strategy for simplicity.

## Potential Enhancements
- Three-way merge for automatic non-conflicting changes
- Interactive resolution UI
```

### When Writing Documentation

**Before creating a new doc:**
1. Check if existing doc covers this - update it instead
2. Determine proper directory (reference/guides/development)
3. Ensure it's timeless reference material, not a report

**When updating existing docs:**
1. Read the full document first
2. Maintain consistent style and voice
3. Update cross-references if needed
4. Don't leave orphaned sections

**After writing:**
1. Search for phase/plan/migration keywords
2. Remove any historical or temporal language
3. Verify all cross-references work
4. Check it fits the directory's purpose

### Documentation Cleanup Checklist

If you find yourself creating documentation that:
- References phases or plans → It's a planning doc, not reference material
- Describes a transition → It's temporary, not timeless
- Analyzes test failures → It's a report, not documentation
- Explains "how we got here" → It's history, use git log

**Then either:**
- Rewrite to be timeless reference material
- Move to issue tracker/planning system
- Delete after extracting useful information

## Avoid Over-Engineering

- Only make changes directly requested
- Don't add features, refactoring, or "improvements" beyond the task
- Three lines of similar code is better than a premature abstraction
- Don't add error handling for scenarios that can't happen
- Don't add docstrings/comments to code you didn't change

## Enum Values

Important enum references (see `dev/database/models/enums.py`):

Journal Domain:
- `ReferenceType`: book, article, film, song, podcast, etc.
- `ReferenceMode`: direct, indirect, paraphrase, visual, thematic
- `RelationType`: family, friend, romantic, colleague, professional, etc.

Manuscript Domain:
- `ChapterType`: prose, vignette, poem
- `ChapterStatus`: draft, revised, final
- `SceneOrigin`: journaled, inferred, invented, composite
- `SceneStatus`: fragment, draft, included, cut
- `SourceType`: scene, entry, thread, external
- `ContributionType`: primary, composite, inspiration

## Running Common Commands

```bash
# Run tests
python -m pytest tests/ -q

# Check linting
ruff check dev/

# Database migrations
alembic upgrade head

# CLI commands
python -m dev.pipeline.cli [command]
```

## Narrative Analysis YAML Editing Guidelines

When revising narrative analysis files in `data/narrative_analysis/`:

### Workflow

1. **Read source journal** (`data/journal/content/md/YYYY/YYYY-MM-DD.md`) AND analysis YAML
2. **Propose changes** in detailed table format for user approval before editing
3. **Review ALL fields**: summary, rating, arcs, threads, tags, themes, motifs, scenes, events, md_frontmatter
4. **Get explicit approval** before implementing changes

### Table Format for Proposing Changes

Use this format for scenes and events:

```
| Scene | Field | Current | Proposed |
|-------|-------|---------|----------|
| **Scene Name** | name | Old Name | **New Name** (or ✓ if unchanged) |
| | description | "old description..." | "new description..." |
| | date | 2024-11-29 | ✓ |
| | people | [Person1] | [Person1, Person2] (or **DELETE** if empty) |
| | locations | `[]` | **DELETE** |
```

- Show all fields (name, description, date, people, locations) for each scene
- Use ✓ for unchanged values
- Use **DELETE** for empty fields that should be removed
- Use **bold** for new/changed values

### Scene Guidelines

- **Descriptions**: Punchy, specific, middle-ground length—enough to identify the scene, not exhaustive; documentary (factual), not editorial (interpretive/biased)
- **No vague terms**: Replace "narrator", "friend", "romantic interest", "the woman" with actual names (Sofia, Majo, Clara, etc.)
- **Specificity**: Use actual names for all people; avoid vague references
- **Location-based**: Scenes are distinct by location; if different locations, keep separate
- **Merge criteria**: Same location + continuous action = can merge; different locations = keep separate
- **Creative names**: Prefer evocative names ("The Gray Fence", "Option Tea, Option Kafé") over literal ones ("At Cinema Moderne")
- **Required fields**: `name`, `description`, `date`
- **Optional fields**: `people`, `locations` — delete if empty (`people: []` or `locations: []`)
- **Home location consistency**: If a scene happens at Sofia's apartment, use `[Home]` as the location. Be consistent—if other scenes in the entry have `[Home]`, all home scenes must have it too. Never use "Apartment" or "Narrator's Apartment".
- **Online presence counts**: Texting, Zoom calls, IG interactions = person is present in `people` field

### Event Guidelines

- **Events group related scenes** — avoid 1:1 scene-to-event ratio
- **Event names should differ from scene names** — especially when 1:1 is unavoidable
- **Event names must be unique across entries** — unless they link to the same real-world event (scenes in different entries narrating the same event on the same day). Do a final pass to verify no accidental repetition.
- **Creative, specific event names** — avoid generic names like "At Home", "City Errands", "Morning Routine" that could apply to any entry. Names should capture the specific narrative essence of that entry (e.g., "Splitting the Wait" for errands driven by anxiety management, "Through the Fog" for pushing through medication haze).
- **Only two fields**: `name` and `scenes`
- **Remove**: `type`, `dates`, `people`, `locations` fields from events

### AI-Generated Content (poems, internal reflections)

- **Minimal metadata**: Keep only tags, themes, motifs
- **Remove**: arcs, scenes, events, people, locations

### md_frontmatter

- Must be consistent with all fields above
- Update when scenes/events are renamed or merged

### Empty Fields

- Delete empty arrays: `people: []`, `locations: []`
- Delete unused optional fields entirely

### Threads

Threads are connections to moments **NOT narrated in the current entry**. They link to memories, future events, or echoes that are triggered or foreshadowed but not actually described.

**Key distinction — Narration vs. Thread**:
- **Narration/Scene**: What is actually written/described in the entry
- **Thread**: The connection to a moment OUTSIDE the entry that the narration triggers or foreshadows

**Thread structure**:
```yaml
- name: "The Bookend Kiss"  # unique, descriptive identifier
  from: "2025-01-05"        # proximate moment (near the entry's timeframe)
  to: "2015"                # distant moment (past or future)
  entry: "2015-03-12"       # optional: journal entry that narrates the distant moment
  content: "Description of the CONNECTION between both moments"
  people: [Person]
  locations: [Location]
```

**Thread naming**: Names should be unique (function as IDs), descriptive, and lyrical without being ironic or overly clever. Examples: "The Swipe That Didn't Match", "Rancid Lipstick", "Sophie at N", "Warmth in the Spin Cycle".

**Date formats**: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` (allows approximate dates). Use "TBD" if unknown.

**Example 1 (past thread)**:
```yaml
- from: "2024-11-08"
  to: "2024-04-24"
  entry: "2024-04-24"
  content: "Seeing Bea's face on Tinder triggers the memory of their night together; when the match leads nowhere, the memory fades"
  people: [Bea]
```

**Example 2 (future thread)**:
```yaml
- from: "2024-11-16"
  to: "2025-03"
  entry: "2025-03-15"
  content: "Clara's stand-up comedian friend will later be the man Sofia sees her kissing; this innocent message plants the seed of future heartbreak"
  people: [Clara]
```

**Guidelines**:
- **Do NOT create threads for events narrated within the entry** — those are scenes, not threads
- **`from`**: the proximate moment referenced in or near the entry
- **`to`**: the distant moment it connects to (past or future)
- **`entry`**: optional, the journal entry date that narrates the distant moment
- **Content describes the CONNECTION** — not what happens in the entry, not what happens at the referenced moment, but how the two moments link and why that resonance matters narratively
- **Narrative significance required** — threads gain meaning through emotional resonance, not just temporal distance; a reference to yesterday CAN be a thread if it carries narrative weight
- **Delete empty fields**: `people`, `locations` if empty
- **md_frontmatter threads**: list thread names (not dates)

## CS/Novelist Pseudo-Adversary Dialogue Framework

When the user requests a "CS/Novelist dialogue" to design features or architecture, use this specific format:

### How It Works

You play BOTH roles alternately (CS and Novelist). The user provides corrections/refinements to each persona's statements.

**Roles:**
- **CS (Computer Scientist)**: Proposes technical architecture, justifies with engineering principles, points out limitations and best practices
- **Novelist/Editor**: Requests features, discards unnecessary complexity, focuses on workflow and usability

### Dialogue Flow

1. **You (as CS)**: Make a technical proposal with justification
2. **User**: Complements/contradicts/rectifies from their own CS/Novelist perspective
3. **You (as Novelist)**: Respond to CS's proposal, incorporating user's corrections
4. **User**: Complements/contradicts/rectifies Novelist's response
5. **You (as CS)**: Counter-respond to Novelist, incorporating user's corrections
6. **User**: Refines again
7. Continue back-and-forth until agreement on topic

### Example Exchange

**You (as CS)**: "I propose using per-file transactions because each YAML is self-contained. If file #237 fails, we don't lose files #1-236."

**User**: "Good, but also mention memory efficiency - don't want unbounded session growth"

**You (as Novelist)**: "Per-file commits make sense for recovery, but what about performance? Won't 972 individual commits be slow?"

**User**: "Actually, individual commits are fine for a one-time script. Focus more on the error reporting."

**You (as CS)**: "Individual commits are acceptable for one-time migration. We'll add detailed error logging showing exactly which files failed and why."

**User**: "Agreed. Move to next topic."

### Key Points

- You alternate between CS and Novelist perspectives
- User corrects/refines BOTH perspectives
- Continue until user indicates agreement
- Don't use a separate agent - you play both roles directly
- Keep responses concise (2-4 sentences per turn)
- Focus on decisions, not exploration

### Topics to Cover

Typical dialogue covers:
- Transaction/error handling strategy
- Entity resolution approaches
- Validation checkpoints
- Data structure designs
- Workflow optimizations

## 2025 Narrative Analysis Audit

When auditing 2025 entries, perform these actions for each file.

### Output Format

Present proposed changes in clear tables. For each section:

**Threads**:
| From | To | Entry | Current Content | Proposed Content |
|------|----|----|-----------------|------------------|

**Scenes**:
| Scene | Description | People | Locations |
|-------|-------------|--------|-----------|

**Events**:
| Event | Scenes | Changes |
|-------|--------|---------|

Keep descriptions visible in the table (current → proposed if changed, or just the value if unchanged). Use ✓ for unchanged, **DELETE** for removals.

### Audit Actions

### 1. Field Reconciliation (events2)

Some 2025 files have an `events2` field containing alternate versions of sub-fields. This is NOT a simple merge:
- Compare `events2` sub-fields against main body equivalents
- **Read the source journal entry** to determine what is CORRECT
- Propose the correct final version based on the source — may be one version, the other, a combination, or something new
- Remove `events2` after reconciliation

### 2. Thread Auditing

Threads are **narratively significant echoes** — moments that gain meaning through temporal distance and emotional resonance.

**What makes a valid thread**:
- References to moments months/years in the past that create meaning through the echo
- Foreshadowing of future events that will carry emotional weight
- The connection itself is meaningful, not just a factual reference

**What is NOT a thread**:
- Events narrated within the entry — those are scenes, not threads
- Generic context or setup without emotional/narrative resonance
- Note: Recent references (yesterday/last week) CAN be threads if they carry narrative weight

**Thread content must describe the CONNECTION**:
- BAD: "Sofia kisses Clara at Station Jarry" (just current entry)
- BAD: "The goodbye kiss outside Sofia's apartment in December" (just referenced moment)
- GOOD: "The greeting kiss at Jarry bookends the goodbye kiss in December—structural symmetry marking the relationship's progression" (the connection between both)

### 3. Data Verification

Confirm accuracy against source journal:
- **People**: Verify each person actually appears in that scene
- **Locations**: Verify locations match what's described
- **Dates**: Verify dates are accurate (multi-day scenes use array format)

### 4. Description Quality

Review against source journal for accuracy. Descriptions should be **documentary, not editorial**:
- **Summaries**: Accurate, descriptive, concise — no interpretive padding
- **Themes**: Capture actual thematic content
- **Motifs**: Match recurring patterns in the narrative
- **Scene descriptions**: Punchy, specific, identifying — not exhaustive

**Check for and fix**:
- **Vagueness**: Be specific with names, places, actions
- **Useless extension**: Cut unnecessary words and padding
- **Biased narration**: Descriptions should be factual/documentary, not interpretive or editorial

### 5. Scene Coverage Verification

- **100% coverage required**: Verify that scenes capture ALL narrative moments in the journal entry
- **No omissions**: If something is narrated (a conversation, an event, a moment), it must have a corresponding scene
- **Verify people**: Every person mentioned in a scene's narrative must appear in the people field

### 6. Structural Cleanup

- **Scene consolidation**: Merge fractured scenes where appropriate
- **Naming**: Event names must differ from scene names; prefer evocative over literal
- **Vague terms**: Replace ALL vague terms with specific names — "narrator"/"the woman"/"friend"/"romantic interest" → actual names (Sofia, Clara, Majo, etc.); "Narrator's Apartment" → "Home"
- **Empty fields**: Remove `people: []`, `locations: []`, and other empty arrays
- **Events structure**: Only `name` and `scenes` fields (remove type, dates, people, locations)
