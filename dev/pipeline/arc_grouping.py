#!/usr/bin/env python3
"""
arc_grouping.py
---------------
Orchestrates the fourth-pass analysis: grouping Events into Arcs.

Arcs are the highest-level narrative structures - the overarching storylines
that span multiple Events and potentially the entire memoir. If Events are
chapters, Arcs are the book's main plotlines.

This script generates prompts for an LLM to identify and group Events into Arcs.

Usage:
    # Preview all events
    python -m dev.pipeline.arc_grouping --dry-run

    # Generate the full arc grouping prompt
    python -m dev.pipeline.arc_grouping --prompt
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from dev.core.paths import JOURNAL_DIR

ANALYSIS_DIR = JOURNAL_DIR / "narrative_analysis"
EVENTS_DIR = ANALYSIS_DIR / "_events"

AGENT_PROMPT_TEMPLATE = '''# Fourth-Pass: Event-to-Arc Grouping

You are analyzing event manifest files to group Events into overarching narrative Arcs.

## Definitions

- **Event**: A chapter-like grouping of related Scenes (already identified in event files)
- **Arc**: An overarching narrative thread that spans multiple Events across time

## The Narrative Hierarchy

```
Arc (e.g., "The Clara Obsession")
├── Event 1 (e.g., "First Date with Clara")
├── Event 2 (e.g., "Second Date with Clara")
├── Event 7 (e.g., "Third Date with Clara")
└── ... (events spanning Nov 2024 - Dec 2025)
```

## Key Principles

**IDENTIFY MAJOR NARRATIVE THREADS**

An Arc should:
1. **Span significant time** - Events from multiple months, ideally across batches
2. **Share a central theme or subject** - A person, struggle, or transformation
3. **Have narrative coherence** - Events that tell one larger story together
4. **Be substantial** - Include at least 3-4 events minimum

**Potential Arc Types:**
- **Character Arcs**: Events centered on a specific person (Clara, Majo, Amanda)
- **Thematic Arcs**: Events unified by theme (mental health crisis, professional journey)
- **Transformation Arcs**: Events tracking a specific change (HRT journey, recovery)

**Events can belong to MULTIPLE arcs:**
- "The Tamino Concert" belongs to both "The Clara Obsession" and "The Cavalry's Watch"
- "Nymeria's Crisis" belongs to both "The Animal Anchor" and "The Clara Obsession"

## Events to Group

{event_summary}

## Output

Create a single markdown file: `{output_file}`

Format:
```markdown
# Narrative Arcs

## Arc 1: [Evocative Title]

**Theme**: One-sentence description of what unifies this arc
**Timespan**: Month Year - Month Year
**Events**:
1. [Event name] (Batch N)
2. [Event name] (Batch N)
...

**Arc Summary**: 2-3 sentence narrative description of this arc's trajectory

---

## Arc 2: [Title]
...

---

## Cross-Arc Events

Events that appear in multiple arcs:
- [Event name]: Arc 1, Arc 3
- [Event name]: Arc 2, Arc 4
...

---

## Standalone Events

Events that don't fit naturally into any arc (should be rare):
- [Event name] (Batch N) - [brief reason]
```

## Guidelines

1. **The Clara Arc is central** - This is the memoir's spine; most events connect to it
2. **Mental Health is a parallel thread** - Depression, mania, intervention form their own arc
3. **The Body has its own story** - HRT, transition, dysphoria events form an arc
4. **Friends are structural supports** - "The Cavalry" events form a rescue arc
5. **Alternative loves provide counterpoint** - Florence, Paty, Amanda events
6. **Professional life continues** - Academic milestones during personal chaos
7. **Nymeria anchors the emotional core** - The dog's illness and death

Be generous with cross-arc assignments - events often serve multiple narrative purposes.
'''


@dataclass
class Event:
    """Represents an event from a batch."""

    number: int
    title: str
    batch_label: str
    entries: List[str]
    scenes: List[str] = field(default_factory=list)
    narrative_arc: Optional[str] = None


def parse_event_file(filepath: Path) -> List[Event]:
    """Parse an event manifest file and extract events."""
    events = []
    content = filepath.read_text()

    # Extract batch label from filename
    # e.g., events_nov_dec_2024.md -> Nov-Dec 2024
    stem = filepath.stem.replace("events_", "")
    parts = stem.split("_")

    # Reconstruct label
    if len(parts) == 3:  # e.g., nov_dec_2024
        batch_label = f"{parts[0].title()}-{parts[1].title()} {parts[2]}"
    elif len(parts) == 2:  # e.g., mar_2025
        batch_label = f"{parts[0].title()} {parts[1]}"
    else:
        batch_label = stem

    # Parse events using regex
    event_pattern = re.compile(
        r"## Event (\d+): (.+?)\n"
        r"\*\*Entries\*\*: ([^\n]+)\n"
        r"\*\*Scenes\*\*:\n((?:- .+\n)*)",
        re.MULTILINE
    )

    for match in event_pattern.finditer(content):
        event_num = int(match.group(1))
        title = match.group(2).strip()
        entries_str = match.group(3).strip()
        scenes_block = match.group(4)

        # Parse entries
        entries = [e.strip() for e in entries_str.split(",")]

        # Parse scenes
        scenes = []
        for line in scenes_block.strip().split("\n"):
            if line.startswith("- "):
                scene = line[2:].split(" - ")[0].strip()
                scenes.append(scene)

        events.append(Event(
            number=event_num,
            title=title,
            batch_label=batch_label,
            entries=entries,
            scenes=scenes,
        ))

    return events


def get_all_events() -> List[Event]:
    """Get all events from all batch files."""
    all_events = []

    # Process files in chronological order
    batch_order = [
        "events_nov_dec_2024.md",
        "events_jan_feb_2025.md",
        "events_mar_2025.md",
        "events_apr_2025.md",
        "events_may_2025.md",
        "events_jun_jul_2025.md",
        "events_aug_dec_2025.md",
    ]

    for filename in batch_order:
        filepath = EVENTS_DIR / filename
        if filepath.exists():
            events = parse_event_file(filepath)
            all_events.extend(events)

    return all_events


def format_event_summary(events: List[Event]) -> str:
    """Format all events for the prompt."""
    lines = []
    current_batch = None

    for event in events:
        if event.batch_label != current_batch:
            if current_batch is not None:
                lines.append("")
            lines.append(f"### {event.batch_label}")
            current_batch = event.batch_label

        # Format event with key scenes
        scene_preview = ", ".join(event.scenes[:3])
        if len(event.scenes) > 3:
            scene_preview += f" (+{len(event.scenes) - 3} more)"

        lines.append(f"- **{event.title}** ({event.entries[0]})")
        if scene_preview:
            lines.append(f"  Scenes: {scene_preview}")

    return "\n".join(lines)


def generate_prompt(events: List[Event]) -> str:
    """Generate the full arc grouping prompt."""
    output_file = ANALYSIS_DIR / "_arcs" / "arcs_manifest.md"

    return AGENT_PROMPT_TEMPLATE.format(
        event_summary=format_event_summary(events),
        output_file=output_file,
    )


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Orchestrate event-to-arc grouping (fourth-pass)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview all events without generating prompt"
    )
    parser.add_argument(
        "--prompt",
        action="store_true",
        help="Output the arc grouping prompt"
    )
    args = parser.parse_args()

    events = get_all_events()

    if args.prompt:
        print(generate_prompt(events))
        return 0

    # Default: show event summary
    print(f"Total events: {len(events)}\n")

    current_batch = None
    for event in events:
        if event.batch_label != current_batch:
            if current_batch is not None:
                print()
            print(f"### {event.batch_label}")
            current_batch = event.batch_label

        print(f"  {event.number}. {event.title}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
