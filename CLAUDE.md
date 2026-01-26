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
