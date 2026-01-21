#!/usr/bin/env python3
"""
scene_identification.py
-----------------------
Orchestrates agentic scene and motif identification for journal entries.

This script manages the second-pass analysis of core material (Nov 2024 - Dec 2025),
where agents read full journal entries to identify:
1. Missing motifs from the predefined list
2. Narrative scenes with dramatic weight

The script batches entries by month with overlap for cross-entry scene detection.

Usage:
    # Preview batches (dry-run)
    python -m dev.pipeline.scene_identification --dry-run

    # Generate prompts for manual agent execution
    python -m dev.pipeline.scene_identification --generate-prompts

    # Show batch N details
    python -m dev.pipeline.scene_identification --batch 3
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from typing import List, Tuple

from dev.core.paths import JOURNAL_DIR

CONTENT_DIR = JOURNAL_DIR / "content" / "md"
ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"

# Core material date range
CORE_START = date(2024, 11, 1)
CORE_END = date(2025, 12, 31)

# Overlap entries for cross-entry scene detection
OVERLAP_COUNT = 2

# The 21 canonical motifs
MOTIFS = [
    "THE BODY",
    "DIGITAL SURVEILLANCE",
    "WRITING AS SURVIVAL",
    "CLOSURE & ENDINGS",
    "WAITING & TIME",
    "THE OBSESSIVE LOOP",
    "LANGUAGE & SILENCE",
    "HAUNTED GEOGRAPHY",
    "MASKS & PERFORMANCE",
    "VALIDATION & REJECTION",
    "SUBSTITUTION & REPLACEMENT",
    "THE UNRELIABLE NARRATOR",
    "GHOSTS & PALIMPSESTS",
    "THE CAVALRY",
    "MEDICALIZATION",
    "MENTAL HEALTH",
    "BUREAUCRATIC TRAUMA",
    "MOTHERHOOD/CHILDLESSNESS",
    "SEX & DESIRE",
    "SUPPORT NETWORK",
    "LANGUAGE & IDENTITY",
]

AGENT_PROMPT_TEMPLATE = '''# Scene & Motif Identification Task

You are analyzing journal entries from a personal memoir project. Your task is to identify:
1. **Missing Motifs** - themes from the canonical list not yet captured in the analysis
2. **Scenes** - discrete narrative moments with dramatic weight

## Context

This is a memoir covering Nov 2024 - Dec 2025. The narrator is a trans woman
navigating relationships, identity, and mental health in Montréal.

## Canonical Motifs (use ONLY these)

{motif_list}

## Scene Definition

A **scene** is a discrete narrative moment characterized by:
- Specific time, place, or action
- Unity of location or purpose
- Narrative or dramatic weight

Scenes do NOT require named people - the narrator may be alone or among unnamed others.
A scene may span multiple entries (note these for cross-reference).

## Your Task

For each entry in your batch:

1. **Read the full journal entry** at `{content_dir}/YYYY/YYYY-MM-DD.md`
2. **Read the existing analysis** at `{analysis_dir}/YYYY/YYYY-MM-DD_analysis.md`
3. **Compare** the entry content against existing Thematic Arcs
4. **Identify scenes** with narrative weight
5. **Append output** to the analysis file

## Entries to Process

{entry_list}

## Overlap Entries (for context only, do not modify)

{overlap_list}

## Output Format

Append the following sections to each analysis file (after Tag Categories or Cleaned Tags):

```markdown
## Scenes

1. **[Scene Title]** - [1-2 sentence description with key context]
2. **[Scene Title]** - [Description]
...

## Additional Motifs

- [MOTIF NAME]: [Brief justification from entry content]
```

**Rules:**
- Only add motifs from the canonical list above
- Only add "Additional Motifs" section if motifs are genuinely missing
- Scene titles should be evocative but concise (2-5 words)
- Note cross-entry scenes with "(continues in YYYY-MM-DD)" or "(continued from YYYY-MM-DD)"
- Some entries may have no identifiable scenes (reflective/abstract entries)

## Example Output

For an entry about a date:

```markdown
## Scenes

1. **Preparation Anxiety** - Getting ready for the date; clothing choices, makeup, confessing nerves to Majo
2. **Lola Rosa** - Sharing poutine with Majo; receiving advice about focusing on own feelings
3. **The Metro Wait** - Texting Clara, watching the gray dots, anticipation
4. **Walking the Village** - Searching for a bar; quinceañera conversation foreshadowing disclosure
5. **Two Secrets Game** - Post-movie at the pub; "Option Tea vs Kafé" leading to trans disclosure
6. **First Kiss** - Bus stop goodbye; the kiss, warmth, promise of next time

## Additional Motifs

- SEX & DESIRE: First kiss scene, physical intimacy building throughout
- LANGUAGE & IDENTITY: "I became a woman in quite a different way" - identity through different path
```
'''


@dataclass
class Batch:
    """A batch of entries for agent processing."""

    number: int
    label: str
    entries: List[date]
    overlap_before: List[date]
    overlap_after: List[date]


def get_all_entries() -> List[date]:
    """Get all journal entry dates in the core material range."""
    entries = []

    for year_dir in sorted(CONTENT_DIR.iterdir()):
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
    """Create monthly batches with overlap."""
    batches = []

    # Group entries by (year, month)
    monthly: dict[Tuple[int, int], List[date]] = {}
    for entry in entries:
        key = (entry.year, entry.month)
        if key not in monthly:
            monthly[key] = []
        monthly[key].append(entry)

    # Define batch groupings (some months combined due to low count)
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
        # Collect entries for this batch
        batch_entries = []
        for mk in month_keys:
            if mk in monthly:
                batch_entries.extend(monthly[mk])
        batch_entries.sort()

        if not batch_entries:
            continue

        # Find overlap entries
        first_entry_idx = entries.index(batch_entries[0])
        last_entry_idx = entries.index(batch_entries[-1])

        overlap_before = entries[max(0, first_entry_idx - OVERLAP_COUNT):first_entry_idx]
        overlap_after = entries[last_entry_idx + 1:last_entry_idx + 1 + OVERLAP_COUNT]

        batches.append(Batch(
            number=batch_num,
            label=label,
            entries=batch_entries,
            overlap_before=overlap_before,
            overlap_after=overlap_after,
        ))

    return batches


def format_entry_list(entries: List[date], include_paths: bool = True) -> str:
    """Format a list of entries for the prompt."""
    lines = []
    for entry in entries:
        if include_paths:
            content_path = f"{CONTENT_DIR}/{entry.year}/{entry}.md"
            lines.append(f"- {entry} (content: `{content_path}`)")
        else:
            lines.append(f"- {entry}")
    return "\n".join(lines)


def generate_prompt(batch: Batch) -> str:
    """Generate the full agent prompt for a batch."""
    motif_list = "\n".join(f"- {m}" for m in MOTIFS)
    entry_list = format_entry_list(batch.entries)

    overlap_parts = []
    if batch.overlap_before:
        overlap_parts.append("Before: " + ", ".join(str(d) for d in batch.overlap_before))
    if batch.overlap_after:
        overlap_parts.append("After: " + ", ".join(str(d) for d in batch.overlap_after))
    overlap_list = "\n".join(overlap_parts) if overlap_parts else "(none)"

    return AGENT_PROMPT_TEMPLATE.format(
        motif_list=motif_list,
        content_dir=CONTENT_DIR,
        analysis_dir=ANALYSIS_DIR,
        entry_list=entry_list,
        overlap_list=overlap_list,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Orchestrate scene and motif identification agents"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview batches without generating prompts"
    )
    parser.add_argument(
        "--generate-prompts",
        action="store_true",
        help="Generate prompt files for each batch"
    )
    parser.add_argument(
        "--batch",
        type=int,
        help="Show details for a specific batch number"
    )
    args = parser.parse_args()

    entries = get_all_entries()
    batches = create_batches(entries)

    print(f"Core material: {len(entries)} entries ({CORE_START} to {CORE_END})")
    print(f"Batches: {len(batches)}\n")

    if args.batch:
        # Show specific batch
        batch = next((b for b in batches if b.number == args.batch), None)
        if not batch:
            print(f"Batch {args.batch} not found")
            return 1

        print(f"Batch {batch.number}: {batch.label}")
        print(f"Entries: {len(batch.entries)}")
        print(f"Overlap before: {batch.overlap_before}")
        print(f"Overlap after: {batch.overlap_after}")
        print("\n" + "=" * 60 + "\n")
        print(generate_prompt(batch))
        return 0

    # Show all batches
    for batch in batches:
        print(f"Batch {batch.number}: {batch.label}")
        print(f"  Entries: {len(batch.entries)}")
        print(f"  Range: {batch.entries[0]} to {batch.entries[-1]}")
        print(f"  Overlap: {len(batch.overlap_before)} before, {len(batch.overlap_after)} after")
        print()

    if args.generate_prompts:
        prompt_dir = ANALYSIS_DIR / "_prompts"
        prompt_dir.mkdir(exist_ok=True)

        for batch in batches:
            prompt_file = prompt_dir / f"batch_{batch.number:02d}_{batch.label.replace(' ', '_').replace('-', '_')}.md"
            prompt_file.write_text(generate_prompt(batch))
            print(f"Generated: {prompt_file}")

        print(f"\nPrompts saved to {prompt_dir}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
