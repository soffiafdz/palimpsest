#!/usr/bin/env python3
"""
yaml_skeleton.py
----------------
Generate commented YAML skeleton files for journal metadata.

When txt2md converts a raw .txt export into a daily .md file, this module
creates a companion .yaml skeleton in the metadata directory. The skeleton
contains the entry date as the only uncommented field; every other field
is presented as a YAML comment with instructions, types, constraints, and
concrete examples so that the human author can fill them in.

Key Features:
    - Auto-populates the ``date`` field from the entry
    - All other fields are commented-out with inline documentation
    - Follows the same skip/force logic as txt2md markdown files
    - Creates year-based subdirectories automatically

Usage:
    from dev.pipeline.yaml_skeleton import generate_skeleton

    path = generate_skeleton(entry_date, yaml_dir)
    path = generate_skeleton(entry_date, yaml_dir, force_overwrite=True)

Dependencies:
    - No external dependencies (plain string templating)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from pathlib import Path
from typing import Optional

# --- Local imports ---
from dev.core.logging_manager import PalimpsestLogger, safe_logger


# =============================================================================
# Skeleton Template
# =============================================================================

_SKELETON_TEMPLATE = """\
date: {date}

## ═══════════════════════════════════════════════════════════════════════════
## EDITORIAL METADATA
## ═══════════════════════════════════════════════════════════════════════════
##
## summary (string, optional):
##   Brief editorial summary of the entry. Use YAML block scalar >- for
##   multi-line text (folded, strip final newline).
##
##   Example:
##     summary: >-
##       A quiet afternoon of reading that spirals into anxious texting.
##       The bookstore scene contrasts the isolation at home.
##
# summary: >-
#   ...

##
## rating (number, optional):
##   Numeric rating for the entry, typically 0-5 (decimals allowed).
##
# rating:

##
## rating_justification (string, optional):
##   Explanation for the rating. Use >- for multi-line.
##
# rating_justification: >-
#   ...

## ═══════════════════════════════════════════════════════════════════════════
## CONTROLLED VOCABULARY
## ═══════════════════════════════════════════════════════════════════════════
##
## arcs (list of strings, optional):
##   Story arcs this entry belongs to. Use existing arc names from
##   the database when possible.
##
##   Example:
##     arcs:
##       - The Dating Carousel
##       - The Thesis Grind
##
# arcs:
#   - ...

##
## tags (list of strings, optional):
##   Keyword tags for the entry. Use existing tags when possible.
##
##   Example:
##     tags:
##       - Anxiety
##       - Montreal
##       - Writing
##
# tags:
#   - ...

##
## themes (list of objects, optional):
##   Thematic elements present in the entry. Each theme has a name
##   and a description explaining how it manifests in this entry.
##
##   Example:
##     themes:
##       - name: Loneliness
##         description: >-
##           The narrator sits alone at the kitchen table, aware
##           of the silence where conversation used to be.
##       - name: Self-Discovery
##         description: >-
##           A moment of clarity about who they are becoming.
##
# themes:
#   - name: ...
#     description: >-
#       ...

##
## motifs (list of objects, optional):
##   Recurring patterns or symbols. Each motif has a name and description.
##
##   Fields per motif:
##     name (string, required): Motif identifier
##     description (string, required): How the motif manifests in this entry
##
##   Example:
##     motifs:
##       - name: The Mirror
##         description: >-
##           Catching her reflection in the cafe window and looking away
##
# motifs:
#   - name: ...
#     description: >-
#       ...

## ═══════════════════════════════════════════════════════════════════════════
## PEOPLE
## ═══════════════════════════════════════════════════════════════════════════
##
## people (list of objects, optional):
##   People mentioned in the entry. Each person needs enough info
##   to disambiguate (lastname OR disambiguator required).
##
##   Fields per person:
##     name (string, required): First name or primary identifier
##     lastname (string): Family name (required if no disambiguator)
##     disambiguator (string): Context hint if no lastname known
##     alias (string or list): Alternative names used in the entry
##
##   Example:
##     people:
##       - name: Clara
##         lastname: Dupont
##       - name: Kate
##         disambiguator: The barista
##       - name: Patricia
##         lastname: González
##         alias: Paty
##       - name: Laura Elena
##         lastname: Lozano
##         alias:
##           - Mom
##           - Mother
##
# people:
#   - name: ...
#     lastname: ...

## ═══════════════════════════════════════════════════════════════════════════
## NARRATIVE ANALYSIS
## ═══════════════════════════════════════════════════════════════════════════
##
## scenes (list of objects, optional):
##   Narrative scenes — distinct moments distinguished by location or action.
##   100% coverage required: every narrated moment needs a scene.
##
##   Fields per scene:
##     name (string, required): Evocative, specific name (not literal)
##     description (string, required): Documentary, not editorial; punchy
##     date (string or list, required): YYYY-MM-DD; use list for multi-day
##     people (list of strings, optional): People present — delete if empty
##     locations (list of strings, optional): Where it happens — delete if empty
##
##   Rules:
##     - Scene names must be unique within the entry
##     - Use actual names, never "narrator" / "friend" / "the woman"
##     - Home location → use [Home], never "Apartment"
##     - Online presence (text, Zoom, IG) counts as present in people
##     - Different locations = separate scenes
##     - Delete empty arrays: do NOT write people: [] or locations: []
##
##   Example:
##     scenes:
##       - name: The Gray Fence
##         description: >-
##           Walking past the construction site, Sofia notices the fence
##           has been repainted. She texts Clara a photo.
##         date: {date}
##         people:
##           - Clara
##         locations:
##           - Plateau
##
# scenes:
#   - name: ...
#     description: >-
#       ...
#     date: {date}

##
## events (list of objects, optional):
##   Events group related scenes. Avoid 1:1 scene-to-event ratio.
##   Event names must differ from scene names and be unique across entries.
##
##   Fields per event:
##     name (string, required): Creative, specific — not generic
##     scenes (list of strings, required): Scene names belonging to this event
##
##   Rules:
##     - Only name and scenes fields (no type, dates, people, locations)
##     - Names should capture the narrative essence, not be generic
##       ("Splitting the Wait" not "City Errands")
##
##   Example:
##     events:
##       - name: The Bookend Kiss
##         scenes:
##           - The Gray Fence
##           - Option Tea, Option Kafé
##
# events:
#   - name: ...
#     scenes:
#       - ...

##
## threads (list of objects, optional):
##   Connections to moments NOT narrated in the current entry — echoes,
##   memories, foreshadowing triggered by the entry's content.
##
##   Fields per thread:
##     name (string, required): Unique, descriptive identifier
##     from (string, required): Proximate date (near entry timeframe)
##     to (string, required): Distant date — YYYY, YYYY-MM, or YYYY-MM-DD
##     entry (string, optional): Journal entry date narrating the distant moment
##     content (string, required): The CONNECTION between both moments
##     people (list of strings, optional): Delete if empty
##     locations (list of strings, optional): Delete if empty
##
##   Rules:
##     - Do NOT create threads for events narrated within this entry
##     - Content describes the connection, not what happens in either moment
##     - Use "TBD" for unknown dates
##
##   Example:
##     threads:
##       - name: The Swipe That Didn't Match
##         from: "{date}"
##         to: "2024-04-24"
##         entry: "2024-04-24"
##         content: >-
##           Seeing Bea's face on Tinder triggers the memory of their
##           night together; the match leads nowhere.
##         people:
##           - Bea
##
# threads:
#   - name: ...
#     from: "{date}"
#     to: "..."
#     content: >-
#       ...

## ═══════════════════════════════════════════════════════════════════════════
## CREATIVE CONTENT
## ═══════════════════════════════════════════════════════════════════════════
##
## references (list of objects, optional):
##   External works referenced in the entry.
##
##   Fields per reference:
##     content (string): The referenced text or description
##     description (string): Context of the reference
##     mode (string): How it's used — one of:
##       direct, indirect, paraphrase, visual, thematic
##     source (object): Source details:
##       title (string): Work title
##       author (string): Creator name
##       type (string): Source type — one of:
##         book, poem, article, film, song, podcast, interview,
##         speech, tv_show, video, website, other
##       url (string, optional): URL if applicable
##
##   Example:
##     references:
##       - content: "We accept the love we think we deserve"
##         description: >-
##           Quoted while texting Clara about the breakup
##         mode: direct
##         source:
##           title: The Perks of Being a Wallflower
##           author: Stephen Chbosky
##           type: book
##
# references:
#   - content: "..."
#     description: >-
#       ...
#     mode: direct
#     source:
#       title: ...
#       author: ...
#       type: book

##
## poems (list of objects, optional):
##   Poems written in or for this entry.
##
##   Fields per poem:
##     title (string): Poem title
##     content (string): Full poem text (use | for multi-line)
##
##   Example:
##     poems:
##       - title: Untitled (January)
##         content: |
##           first line of the poem
##           second line of the poem
##
# poems:
#   - title: ...
#     content: |
#       ...
"""


# =============================================================================
# Public API
# =============================================================================


def generate_skeleton(
    entry_date: date,
    yaml_dir: Path,
    force_overwrite: bool = False,
    logger: Optional[PalimpsestLogger] = None,
) -> Optional[Path]:
    """
    Generate a commented YAML skeleton for a journal entry.

    Creates a YAML file with the entry date as the only uncommented field.
    All other metadata fields are presented as instructional comments with
    types, constraints, and examples.

    The file is placed in a year-based subdirectory:
    ``yaml_dir/YYYY/YYYY-MM-DD.yaml``

    Args:
        entry_date: Date of the journal entry
        yaml_dir: Base directory for YAML metadata files
        force_overwrite: If True, overwrite existing skeleton files
        logger: Optional logger for debug output

    Returns:
        Path to created file, or None if skipped (file already exists)

    Raises:
        OSError: If directory creation or file write fails
    """
    # Create year directory structure
    year_dir = yaml_dir / str(entry_date.year)
    year_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{entry_date.isoformat()}.yaml"
    output_path = year_dir / filename

    # Check for existing file
    if output_path.exists() and not force_overwrite:
        safe_logger(logger).log_debug(
            f"Skeleton {output_path.name} exists, skipping"
        )
        return None

    # Render template with the entry date
    date_str = entry_date.isoformat()
    content = _SKELETON_TEMPLATE.format(date=date_str)

    # Write file
    output_path.write_text(content, encoding="utf-8")

    action = "Overwrote" if output_path.exists() else "Created"
    safe_logger(logger).log_debug(f"{action} skeleton: {output_path.name}")

    return output_path
