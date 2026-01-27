#!/usr/bin/env python3
"""
extract_entities.py
-------------------
Extract people and locations from narrative_analysis YAML files for curation.

This script scans all narrative_analysis YAML files and extracts unique people
and location mentions from scenes and threads. It auto-groups similar names
using Levenshtein distance and other heuristics, then generates draft curation
files for manual review.

Key Features:
    - Extracts from scenes[].people, scenes[].locations, threads[].people, threads[].locations
    - Auto-groups similar names (typos, variations, nicknames)
    - Tracks occurrence context (date, scene/thread name) for disambiguation
    - Generates draft YAML files with review instructions

Usage:
    python -m dev.bin.extract_entities [--dry-run]

Output:
    - data/curation/people_curation_draft.yaml
    - data/curation/locations_curation_draft.yaml
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
import argparse
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import NARRATIVE_ANALYSIS_DIR, CURATION_DIR


@dataclass
class Occurrence:
    """A single occurrence of an entity in the source files."""
    date: str
    context_type: str  # "scene" or "thread"
    context_name: str


@dataclass
class EntityMention:
    """An entity mention with all its occurrences."""
    raw_name: str
    occurrences: List[Occurrence] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.occurrences)

    def sample_occurrences(self, limit: int = 5) -> List[Dict[str, str]]:
        """Return sample occurrences for the draft file."""
        samples = self.occurrences[:limit]
        return [
            {"date": o.date, f"{o.context_type}": o.context_name}
            for o in samples
        ]


@dataclass
class EntityGroup:
    """A group of similar entity mentions that likely refer to the same entity."""
    id: int
    members: List[EntityMention]

    @property
    def total_count(self) -> int:
        return sum(m.total_count for m in self.members)


def normalize_name(name: str) -> str:
    """
    Normalize a name for comparison.

    Removes @ prefix, strips whitespace, lowercases, removes accents,
    and normalizes punctuation.

    Args:
        name: Raw name string

    Returns:
        Normalized string for comparison
    """
    # Remove @ prefix
    if name.startswith("@"):
        name = name[1:]

    # Lowercase and strip
    name = name.lower().strip()

    # Remove accents (NFD decomposition, then strip combining chars)
    name = unicodedata.normalize("NFD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))

    # Normalize hyphens and spaces
    name = re.sub(r"[-\s]+", " ", name)

    # Remove punctuation except spaces
    name = re.sub(r"[^\w\s]", "", name)

    return name.strip()


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.

    Args:
        s1: First string
        s2: Second string

    Returns:
        Edit distance (minimum insertions, deletions, substitutions)
    """
    if len(s1) < len(s2):
        s1, s2 = s2, s1

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def should_group(name1: str, name2: str) -> bool:
    """
    Determine if two names should be grouped as the same entity.

    Conservative approach - only groups when highly confident:
    - Exact match after normalization
    - Very small Levenshtein distance (typos only)

    Does NOT use aggressive heuristics like:
    - Substring matching (too many false positives)
    - First N characters (too many false positives)

    Args:
        name1: First raw name
        name2: Second raw name

    Returns:
        True if names should be grouped
    """
    n1 = normalize_name(name1)
    n2 = normalize_name(name2)

    # Skip empty names
    if not n1 or not n2:
        return False

    # Exact match after normalization
    if n1 == n2:
        return True

    # Levenshtein distance ≤ 1 for typos (very conservative)
    # Only for names of similar length to avoid false positives
    if abs(len(n1) - len(n2)) <= 1 and levenshtein_distance(n1, n2) <= 1:
        return True

    return False


def extract_from_yaml(yaml_path: Path) -> Tuple[Dict[str, List[Occurrence]], Dict[str, List[Occurrence]]]:
    """
    Extract people and locations from a single YAML file.

    Args:
        yaml_path: Path to the narrative_analysis YAML file

    Returns:
        Tuple of (people_dict, locations_dict) where each dict maps
        raw_name -> list of occurrences
    """
    people: Dict[str, List[Occurrence]] = defaultdict(list)
    locations: Dict[str, List[Occurrence]] = defaultdict(list)

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (yaml.YAMLError, OSError) as e:
        print(f"Warning: Failed to parse {yaml_path}: {e}")
        return people, locations

    if not data:
        return people, locations

    date_str = data.get("date", yaml_path.stem.split("_")[0])
    if hasattr(date_str, "isoformat"):
        date_str = date_str.isoformat()
    else:
        date_str = str(date_str)

    # Extract from scenes
    for scene in data.get("scenes", []) or []:
        if not isinstance(scene, dict):
            continue
        scene_name = scene.get("name", "Unknown Scene")

        for person in scene.get("people", []) or []:
            if person:
                occ = Occurrence(date=date_str, context_type="scene", context_name=scene_name)
                people[str(person)].append(occ)

        for location in scene.get("locations", []) or []:
            if location:
                occ = Occurrence(date=date_str, context_type="scene", context_name=scene_name)
                locations[str(location)].append(occ)

    # Extract from threads
    for thread in data.get("threads", []) or []:
        if not isinstance(thread, dict):
            continue
        thread_name = thread.get("name", "Unknown Thread")

        for person in thread.get("people", []) or []:
            if person:
                occ = Occurrence(date=date_str, context_type="thread", context_name=thread_name)
                people[str(person)].append(occ)

        for location in thread.get("locations", []) or []:
            if location:
                occ = Occurrence(date=date_str, context_type="thread", context_name=thread_name)
                locations[str(location)].append(occ)

    return people, locations


def build_entity_mentions(
    all_occurrences: Dict[str, List[Occurrence]]
) -> List[EntityMention]:
    """
    Build EntityMention objects from aggregated occurrences.

    Args:
        all_occurrences: Dict mapping raw_name -> list of all occurrences

    Returns:
        List of EntityMention objects
    """
    mentions = []
    for raw_name, occurrences in all_occurrences.items():
        mentions.append(EntityMention(raw_name=raw_name, occurrences=occurrences))
    return mentions


def group_entities(mentions: List[EntityMention]) -> List[EntityGroup]:
    """
    Group similar entity mentions using union-find algorithm.

    Args:
        mentions: List of EntityMention objects

    Returns:
        List of EntityGroup objects
    """
    if not mentions:
        return []

    # Union-find data structure
    parent = list(range(len(mentions)))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Group mentions that should be together
    for i in range(len(mentions)):
        for j in range(i + 1, len(mentions)):
            if should_group(mentions[i].raw_name, mentions[j].raw_name):
                union(i, j)

    # Build groups
    groups_dict: Dict[int, List[EntityMention]] = defaultdict(list)
    for i, mention in enumerate(mentions):
        root = find(i)
        groups_dict[root].append(mention)

    # Create EntityGroup objects, sorted by total count descending
    groups = []
    for group_id, (_, members) in enumerate(
        sorted(groups_dict.items(), key=lambda x: -sum(m.total_count for m in x[1])),
        start=1
    ):
        # Sort members within group by count descending
        members.sort(key=lambda m: -m.total_count)
        groups.append(EntityGroup(id=group_id, members=members))

    return groups


def generate_draft_yaml(
    groups: List[EntityGroup],
    entity_type: str
) -> Dict[str, Any]:
    """
    Generate draft YAML structure for curation.

    Args:
        groups: List of EntityGroup objects
        entity_type: "people" or "locations"

    Returns:
        Dict structure ready for YAML dump
    """
    draft = {
        "_instructions": f"""
# {entity_type.upper()} CURATION DRAFT
#
# This file was auto-generated by extract_entities.py
# Review each group and:
# 1. CONFIRM if all members refer to the same {entity_type[:-1]}
# 2. SPLIT if members refer to different {entity_type[:-1]}s
# 3. Fill in the 'canonical' section with the correct form
#
# After review, save as {entity_type}_curation.yaml (remove _draft)
# Then run: python -m dev.bin.validate_curation
""".strip(),
        "groups": []
    }

    for group in groups:
        group_data: Dict[str, Any] = {
            "id": group.id,
            "members": []
        }

        for member in group.members:
            member_data: Dict[str, Any] = {
                "name": member.raw_name,
                "total_count": member.total_count,
                "occurrences": member.sample_occurrences(limit=5)
            }
            group_data["members"].append(member_data)

        # Pre-fill canonical for single-member groups
        if len(group.members) == 1:
            name = group.members[0].raw_name
            if entity_type == "people":
                group_data["canonical"] = {
                    "name": name.lstrip("@"),
                    "lastname": None,
                    "alias": name[1:] if name.startswith("@") else None
                }
            else:  # locations
                group_data["canonical"] = {
                    "name": name,
                    "city": None  # User must fill in
                }
        else:
            group_data["canonical"] = None  # User must review

        draft["groups"].append(group_data)

    return draft


def extract_all(dry_run: bool = False) -> Tuple[int, int]:
    """
    Extract all entities from narrative_analysis files.

    Args:
        dry_run: If True, don't write output files

    Returns:
        Tuple of (people_count, locations_count)
    """
    # Collect all YAML files
    yaml_files = sorted(NARRATIVE_ANALYSIS_DIR.glob("**/*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    print(f"Scanning {len(yaml_files)} YAML files...")

    # Aggregate all occurrences
    all_people: Dict[str, List[Occurrence]] = defaultdict(list)
    all_locations: Dict[str, List[Occurrence]] = defaultdict(list)

    for yaml_path in yaml_files:
        people, locations = extract_from_yaml(yaml_path)
        for name, occs in people.items():
            all_people[name].extend(occs)
        for name, occs in locations.items():
            all_locations[name].extend(occs)

    # Build mentions and groups
    people_mentions = build_entity_mentions(all_people)
    location_mentions = build_entity_mentions(all_locations)

    people_groups = group_entities(people_mentions)
    location_groups = group_entities(location_mentions)

    # Generate draft YAMLs
    people_draft = generate_draft_yaml(people_groups, "people")
    locations_draft = generate_draft_yaml(location_groups, "locations")

    # Statistics
    total_people_mentions = sum(m.total_count for m in people_mentions)
    total_location_mentions = sum(m.total_count for m in location_mentions)
    unique_people = len(people_mentions)
    unique_locations = len(location_mentions)
    people_group_count = len(people_groups)
    location_group_count = len(location_groups)

    print(f"\nPeople:")
    print(f"  {total_people_mentions} total mentions")
    print(f"  {unique_people} unique name variants")
    print(f"  {people_group_count} auto-grouped entities")

    print(f"\nLocations:")
    print(f"  {total_location_mentions} total mentions")
    print(f"  {unique_locations} unique name variants")
    print(f"  {location_group_count} auto-grouped entities")

    if not dry_run:
        CURATION_DIR.mkdir(parents=True, exist_ok=True)

        people_path = CURATION_DIR / "people_curation_draft.yaml"
        with open(people_path, "w", encoding="utf-8") as f:
            yaml.dump(
                people_draft,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=100
            )
        print(f"\nSaved people draft to {people_path}")

        locations_path = CURATION_DIR / "locations_curation_draft.yaml"
        with open(locations_path, "w", encoding="utf-8") as f:
            yaml.dump(
                locations_draft,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=100
            )
        print(f"Saved locations draft to {locations_path}")
    else:
        print("\n[DRY RUN] Would save to:")
        print(f"  {CURATION_DIR / 'people_curation_draft.yaml'}")
        print(f"  {CURATION_DIR / 'locations_curation_draft.yaml'}")

    return unique_people, unique_locations


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract people and locations from narrative_analysis YAMLs for curation"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't write output files, just show statistics"
    )
    args = parser.parse_args()

    extract_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
