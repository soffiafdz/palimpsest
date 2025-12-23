#!/usr/bin/env python3
"""
event_grouping.py
-----------------
Orchestrates the third-pass analysis: grouping Scenes into Events.

Events are chapter-like groupings of related Scenes that may span multiple entries.
The goal is to find the minimum natural groupings WITHOUT merging distinct narrative
threads. If Scenes were scenes in a novel, Events would be the chapters.

This script also handles merging Additional Motifs into the Thematic Arcs section.

Usage:
    # Preview batches (dry-run)
    python -m dev.pipeline.event_grouping --dry-run

    # Show batch N details
    python -m dev.pipeline.event_grouping --batch 1

    # Generate prompt for specific batch
    python -m dev.pipeline.event_grouping --batch 1 --prompt
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List

from dev.core.paths import JOURNAL_DIR

ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"

# Core material date range
CORE_START = date(2024, 11, 1)
CORE_END = date(2025, 12, 31)

AGENT_PROMPT_TEMPLATE = '''# Third-Pass: Scene-to-Event Grouping

You are analyzing narrative analysis files to group Scenes into Events.

## Definitions

- **Scene**: A discrete narrative moment (already identified in analysis files)
- **Event**: A chapter-like grouping of related Scenes that share narrative unity

## Key Principles

**BE CONSERVATIVE. Not every scene needs to belong to an event.**

An Event requires:
1. **Same participants OR same situation** - scenes with the same person(s) or same ongoing situation
2. **Causal/narrative connection** - scenes that flow into each other or share purpose
3. **Thematic unity** - scenes that together tell one coherent story

**Leave scenes UNGROUPED when:**
- They are isolated moments without clear connection to others
- They are transitional or abstract/reflective
- They belong to a different narrative thread that doesn't have enough substance for its own event
- Grouping them would force unrelated content together

**Handle BRAIDED NARRATIVES carefully:**
- An entry might contain scenes from multiple distinct threads (e.g., morning with Person A, evening with Person B)
- These should be SEPARATE events, not lumped together
- Interleaved scenes from different threads should go to their respective events

## Examples

**Good: "Third Date with Clara" Event (2024-11-24)**
Only includes the date-related scenes:
- Berri-UQAM Wait, Village Walk, The Café Question, Theater Seating, Armrest Contact,
  Restroom Fake-Out, The Pub at Beaubien, Two Secrets Game, The Bus Stop Kiss, "I will see you"

**Good: "Day with Majo" Event (2024-11-24)**
Separate event for the pre-date support:
- Preparation Anxiety, Lola Rosa, Complexe Desjardins, Meeting Lavi

**Bad: Forcing all scenes into one event**
Lumping "Day with Majo" and "Third Date with Clara" together just because they're the same day

**Bad: Creating thin events**
Making "Meeting Lavi" its own event when it's just a brief transitional scene

## Your Task

For this batch of entries ({batch_label}):

1. **Read all Scenes sections** in the analysis files
2. **Identify natural Event groupings** - be conservative
3. **Create an Events manifest** with grouped AND ungrouped scenes
4. **Merge Additional Motifs** into existing Thematic Arcs sections

## Entries in This Batch

{entry_list}

## Output

Create a single markdown file: `{output_file}`

Format:
```markdown
# Events: {batch_label}

## Event 1: [Evocative Title]
**Entries**: YYYY-MM-DD, YYYY-MM-DD, ...
**Scenes**:
- [Scene name from entry 1]
- [Scene name from entry 2]
...

## Event 2: [Evocative Title]
**Entries**: YYYY-MM-DD
**Scenes**:
- [Scene name]
...

---

## Ungrouped Scenes

Scenes that don't fit naturally into any event:

- YYYY-MM-DD: [Scene name] - [brief reason: transitional/isolated/reflective]
- YYYY-MM-DD: [Scene name] - [reason]
...

---

## Motif Merges

For each entry where Additional Motifs were found, list what was merged:

- YYYY-MM-DD: Added [MOTIF1], [MOTIF2] to Thematic Arcs
- YYYY-MM-DD: No additional motifs
...
```

## Rules

1. **Not every scene needs an event** - standalone scenes are valid
2. Events can span multiple entries but MUST have clear narrative unity
3. Braided narratives = separate events, even within same entry
4. Event titles should be evocative (2-5 words)
5. Update each analysis file's Thematic Arcs to include the Additional Motifs
6. When in doubt, leave a scene ungrouped rather than force it into an event
'''


@dataclass
class Batch:
    """A batch of entries for event grouping."""

    number: int
    label: str
    entries: List[date]


def get_core_entries() -> List[date]:
    """Get all journal entry dates in the core material range."""
    entries = []

    for year_dir in sorted((ANALYSIS_DIR.parent / "content" / "md").iterdir()):
        if not year_dir.is_dir():
            continue
        for entry_file in sorted(year_dir.glob("*.md")):
            try:
                entry_date = date.fromisoformat(entry_file.stem)
                if CORE_START <= entry_date <= CORE_END:
                    entries.append(entry_date)
            except ValueError:
                continue

    return sorted(entries)


def create_batches(entries: List[date]) -> List[Batch]:
    """Create monthly batches for event grouping."""
    batches = []

    # Group entries by (year, month)
    monthly: dict[tuple[int, int], List[date]] = {}
    for entry in entries:
        key = (entry.year, entry.month)
        if key not in monthly:
            monthly[key] = []
        monthly[key].append(entry)

    # Same batch specs as scene_identification
    batch_specs = [
        ("Nov-Dec 2024", [(2024, 11), (2024, 12)]),
        ("Jan-Feb 2025", [(2025, 1), (2025, 2)]),
        ("Mar 2025", [(2025, 3)]),
        ("Apr 2025", [(2025, 4)]),
        ("May 2025", [(2025, 5)]),
        ("Jun-Jul 2025", [(2025, 6), (2025, 7)]),
        ("Aug-Dec 2025", [(2025, 8), (2025, 9), (2025, 10), (2025, 11), (2025, 12)]),
    ]

    for batch_num, (label, month_keys) in enumerate(batch_specs, 1):
        batch_entries = []
        for mk in month_keys:
            if mk in monthly:
                batch_entries.extend(monthly[mk])
        batch_entries.sort()

        if batch_entries:
            batches.append(Batch(
                number=batch_num,
                label=label,
                entries=batch_entries,
            ))

    return batches


def format_entry_list(entries: List[date]) -> str:
    """Format a list of entries for the prompt."""
    lines = []
    for entry in entries:
        analysis_path = ANALYSIS_DIR / str(entry.year) / f"{entry}_analysis.md"
        lines.append(f"- {entry} (`{analysis_path}`)")
    return "\n".join(lines)


def generate_prompt(batch: Batch) -> str:
    """Generate the full agent prompt for a batch."""
    output_file = ANALYSIS_DIR / "_events" / f"events_{batch.label.replace(' ', '_').replace('-', '_').lower()}.md"

    return AGENT_PROMPT_TEMPLATE.format(
        batch_label=batch.label,
        entry_list=format_entry_list(batch.entries),
        output_file=output_file,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrate scene-to-event grouping (third-pass)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview batches without generating prompts"
    )
    parser.add_argument(
        "--batch",
        type=int,
        help="Show details for a specific batch number"
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Output the prompt for the specified batch"
    )
    args = parser.parse_args()

    entries = get_core_entries()
    batches = create_batches(entries)

    if args.batch:
        batch = next((b for b in batches if b.number == args.batch), None)
        if not batch:
            print(f"Batch {args.batch} not found")
            return 1

        if args.prompt:
            print(generate_prompt(batch))
        else:
            print(f"Batch {batch.number}: {batch.label}")
            print(f"Entries: {len(batch.entries)}")
            print(f"Date range: {batch.entries[0]} to {batch.entries[-1]}")
            print("\nEntries:")
            for e in batch.entries:
                print(f"  - {e}")
        return 0

    # Show all batches
    print(f"Core material: {len(entries)} entries ({CORE_START} to {CORE_END})")
    print(f"Batches: {len(batches)}\n")

    for batch in batches:
        print(f"Batch {batch.number}: {batch.label}")
        print(f"  Entries: {len(batch.entries)}")
        print(f"  Range: {batch.entries[0]} to {batch.entries[-1]}")
        print()

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
