#!/usr/bin/env python3
"""
extract_entities.py
-------------------
Extract people and locations from journal MD frontmatter for curation.

This script scans all journal MD files and extracts unique people and location
mentions from the YAML frontmatter. The MD frontmatter is the ground truth for
entity data per the Phase 14 architecture.

MD Frontmatter Format:
    ---
    date: 2024-12-03
    locations:
      Montréal: [The Neuro, Home]
    people: [Dr-Franck, Fabiola, Aliza, Sonny, Majo, Clara]
    ---

Key Features:
    - Extracts from MD frontmatter (ground truth source)
    - Groups similar names using Levenshtein distance
    - Locations are already hierarchical by city in frontmatter
    - Generates draft YAML files for manual review

Usage:
    python -m dev.bin.extract_entities [--dry-run]

Output:
    - data/curation/people_curation_draft.yaml (flat structure)
    - data/curation/locations_curation_draft.yaml (hierarchical by city)
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
from typing import Any, Dict, List, Optional, Tuple

# --- Third-party imports ---
import yaml

# --- Local imports ---
from dev.core.paths import MD_DIR, CURATION_DIR


@dataclass
class Occurrence:
    """A single occurrence of an entity in a journal entry."""
    date: str
    file_path: str


@dataclass
class EntityMention:
    """An entity mention with all its occurrences."""
    raw_name: str
    occurrences: List[Occurrence] = field(default_factory=list)

    @property
    def total_count(self) -> int:
        return len(self.occurrences)

    @property
    def unique_dates(self) -> List[str]:
        """Return sorted list of unique dates."""
        return sorted(set(o.date for o in self.occurrences))

    @property
    def date_range(self) -> str:
        """Return date range as 'YYYY-MM-DD to YYYY-MM-DD'."""
        dates = self.unique_dates
        if not dates:
            return "N/A"
        if len(dates) == 1:
            return dates[0]
        return f"{dates[0]} to {dates[-1]}"

    def sample_occurrences(self, limit: int = 5) -> List[Dict[str, str]]:
        """Return sample occurrences for the draft file."""
        samples = self.occurrences[:limit]
        return [{"date": o.date} for o in samples]


@dataclass
class EntityGroup:
    """A group of similar entity mentions that likely refer to the same entity."""
    id: int
    members: List[EntityMention]
    canonical: Optional[Dict[str, Any]] = None


def normalize_for_grouping(name: str) -> str:
    """
    Normalize a name for grouping comparison.

    Removes accents, lowercases, normalizes punctuation.
    """
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
    """Calculate Levenshtein distance between two strings."""
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
    """Determine if two names should be grouped."""
    n1 = normalize_for_grouping(name1)
    n2 = normalize_for_grouping(name2)

    if not n1 or not n2:
        return False

    if n1 == n2:
        return True

    # Levenshtein distance <= 1 for typos
    if abs(len(n1) - len(n2)) <= 1 and levenshtein_distance(n1, n2) <= 1:
        return True

    return False


def extract_frontmatter(md_path: Path) -> Optional[Dict[str, Any]]:
    """
    Extract YAML frontmatter from a markdown file.

    Returns:
        Parsed frontmatter dict, or None if no frontmatter found
    """
    try:
        with open(md_path, "r", encoding="utf-8") as f:
            content = f.read()
    except OSError as e:
        print(f"Warning: Failed to read {md_path}: {e}")
        return None

    # Match YAML frontmatter between --- markers
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None

    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError as e:
        print(f"Warning: Failed to parse frontmatter in {md_path}: {e}")
        return None


def extract_from_md(
    md_path: Path,
) -> Tuple[Dict[str, List[Occurrence]], Dict[str, Dict[str, List[Occurrence]]]]:
    """
    Extract people and locations from a single MD file's frontmatter.

    Returns:
        Tuple of:
        - people_dict: raw_name -> occurrences
        - locations_dict: city -> {raw_name -> occurrences}
    """
    people: Dict[str, List[Occurrence]] = defaultdict(list)
    locations: Dict[str, Dict[str, List[Occurrence]]] = defaultdict(lambda: defaultdict(list))

    frontmatter = extract_frontmatter(md_path)
    if not frontmatter:
        return people, locations

    # Get date
    date_val = frontmatter.get("date")
    if hasattr(date_val, "isoformat"):
        date_str = date_val.isoformat()
    elif date_val:
        date_str = str(date_val)
    else:
        date_str = md_path.stem  # Fallback to filename

    occ = Occurrence(date=date_str, file_path=str(md_path))

    # Extract people (flat list)
    people_list = frontmatter.get("people", [])
    if people_list:
        for person in people_list:
            if person:
                people[str(person)].append(occ)

    # Extract locations (hierarchical: {City: [loc1, loc2]})
    locations_data = frontmatter.get("locations", {})
    if isinstance(locations_data, dict):
        for city, locs in locations_data.items():
            if not city or not locs:
                continue
            city_str = str(city)
            if isinstance(locs, list):
                for loc in locs:
                    if loc:
                        locations[city_str][str(loc)].append(occ)
            elif locs:
                # Single location as string
                locations[city_str][str(locs)].append(occ)

    return people, locations


def group_entities(
    all_mentions: Dict[str, List[Occurrence]]
) -> List[EntityGroup]:
    """Group entities by normalized name similarity."""
    if not all_mentions:
        return []

    # Build mentions
    mentions = []
    for raw_name, occurrences in all_mentions.items():
        mention = EntityMention(raw_name=raw_name, occurrences=occurrences)
        mentions.append(mention)

    # Union-find for grouping
    parent = list(range(len(mentions)))

    def find(x: int) -> int:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Group by name similarity
    for i in range(len(mentions)):
        for j in range(i + 1, len(mentions)):
            if should_group(mentions[i].raw_name, mentions[j].raw_name):
                union(i, j)

    # Build groups
    groups_dict: Dict[int, List[EntityMention]] = defaultdict(list)
    for i, mention in enumerate(mentions):
        root = find(i)
        groups_dict[root].append(mention)

    # Create EntityGroup objects
    groups = []
    for group_id, (_, members) in enumerate(
        sorted(groups_dict.items(), key=lambda x: -sum(m.total_count for m in x[1])),
        start=1
    ):
        members.sort(key=lambda m: -m.total_count)

        # Pre-fill canonical with most common name
        canonical_name = members[0].raw_name if members else None

        groups.append(EntityGroup(
            id=group_id,
            members=members,
            canonical={"name": canonical_name, "lastname": None, "alias": None} if canonical_name else None,
        ))

    return groups


def group_locations_by_city(
    all_locations: Dict[str, Dict[str, List[Occurrence]]]
) -> Dict[str, List[EntityGroup]]:
    """
    Group locations within each city.

    Returns:
        Dict mapping city -> list of EntityGroup
    """
    result: Dict[str, List[EntityGroup]] = {}
    global_id = 1

    for city in sorted(all_locations.keys()):
        city_locs = all_locations[city]

        # Build mentions for this city
        mentions = []
        for raw_name, occurrences in city_locs.items():
            mention = EntityMention(raw_name=raw_name, occurrences=occurrences)
            mentions.append(mention)

        if not mentions:
            continue

        # Union-find for grouping within city
        parent = list(range(len(mentions)))

        def find(x: int) -> int:
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x: int, y: int) -> None:
            px, py = find(x), find(y)
            if px != py:
                parent[px] = py

        for i in range(len(mentions)):
            for j in range(i + 1, len(mentions)):
                if should_group(mentions[i].raw_name, mentions[j].raw_name):
                    union(i, j)

        # Build groups
        groups_dict: Dict[int, List[EntityMention]] = defaultdict(list)
        for i, mention in enumerate(mentions):
            root = find(i)
            groups_dict[root].append(mention)

        # Create groups for this city
        city_groups = []
        for _, members in sorted(
            groups_dict.items(), key=lambda x: -sum(m.total_count for m in x[1])
        ):
            members.sort(key=lambda m: -m.total_count)

            # Pre-fill canonical with most common name
            canonical_name = members[0].raw_name if members else None

            city_groups.append(EntityGroup(
                id=global_id,
                members=members,
                canonical={"name": canonical_name} if canonical_name else None,
            ))
            global_id += 1

        result[city] = city_groups

    return result


def generate_people_draft(groups: List[EntityGroup]) -> Dict[str, Any]:
    """Generate draft YAML for people curation."""
    draft = {
        "_instructions": """
# PEOPLE CURATION DRAFT
#
# This file was auto-generated by extract_entities.py
# Source: Journal MD frontmatter (ground truth)
#
# Review each group and:
# 1. CONFIRM if all members refer to the same person
# 2. SPLIT if members refer to different people
# 3. Verify/edit the 'canonical' section
#
# After review, save as people_curation.yaml (remove _draft)
# Then run: python -m dev.bin.validate_curation
""".strip(),
        "groups": []
    }

    for group in groups:
        group_data: Dict[str, Any] = {
            "id": group.id,
            "members": [],
            "canonical": group.canonical,
        }

        for member in group.members:
            member_data: Dict[str, Any] = {
                "name": member.raw_name,
                "total_count": member.total_count,
                "date_range": member.date_range,
                "sample_occurrences": member.sample_occurrences(limit=3)
            }
            group_data["members"].append(member_data)

        draft["groups"].append(group_data)

    return draft


def generate_locations_draft(
    locations_by_city: Dict[str, List[EntityGroup]]
) -> Dict[str, Any]:
    """Generate hierarchical draft YAML for locations curation."""
    draft = {
        "_instructions": """
# LOCATIONS CURATION DRAFT (Hierarchical by City)
#
# This file was auto-generated by extract_entities.py
# Source: Journal MD frontmatter (ground truth)
#
# Review each city and its locations:
# 1. CONFIRM if all members refer to the same location
# 2. SPLIT if members refer to different locations
# 3. Verify/edit the 'canonical' name for each location
#
# After review, save as locations_curation.yaml (remove _draft)
# Then run: python -m dev.bin.validate_curation
""".strip(),
        "cities": []
    }

    for city in sorted(locations_by_city.keys()):
        groups = locations_by_city[city]

        city_data: Dict[str, Any] = {
            "name": city,
            "locations": []
        }

        for group in groups:
            loc_data: Dict[str, Any] = {
                "id": group.id,
                "members": [],
                "canonical": group.canonical.get("name") if group.canonical else None,
            }

            for member in group.members:
                member_data: Dict[str, Any] = {
                    "name": member.raw_name,
                    "total_count": member.total_count,
                    "date_range": member.date_range,
                    "sample_occurrences": member.sample_occurrences(limit=3)
                }
                loc_data["members"].append(member_data)

            city_data["locations"].append(loc_data)

        draft["cities"].append(city_data)

    return draft


def extract_all(dry_run: bool = False) -> Tuple[int, int]:
    """
    Extract all entities from journal MD files.

    Args:
        dry_run: If True, don't write output files

    Returns:
        Tuple of (people_group_count, location_group_count)
    """
    md_files = sorted(MD_DIR.glob("**/*.md"))
    print(f"Scanning {len(md_files)} MD files...")

    # Aggregate all data
    all_people: Dict[str, List[Occurrence]] = defaultdict(list)
    all_locations: Dict[str, Dict[str, List[Occurrence]]] = defaultdict(lambda: defaultdict(list))

    files_with_people = 0
    files_with_locations = 0

    for md_path in md_files:
        people, locations = extract_from_md(md_path)

        if people:
            files_with_people += 1
        if locations:
            files_with_locations += 1

        # Merge people
        for raw_name, occs in people.items():
            all_people[raw_name].extend(occs)

        # Merge locations by city
        for city, city_locs in locations.items():
            for raw_name, occs in city_locs.items():
                all_locations[city][raw_name].extend(occs)

    # Group entities
    people_groups = group_entities(all_people)
    locations_by_city = group_locations_by_city(all_locations)

    # Generate drafts
    people_draft = generate_people_draft(people_groups)
    locations_draft = generate_locations_draft(locations_by_city)

    # Statistics
    total_people_mentions = sum(len(occs) for occs in all_people.values())
    unique_people = len(all_people)
    people_group_count = len(people_groups)

    total_location_mentions = sum(
        len(occs)
        for city_locs in all_locations.values()
        for occs in city_locs.values()
    )
    unique_locations = sum(len(city_locs) for city_locs in all_locations.values())
    location_group_count = sum(len(groups) for groups in locations_by_city.values())
    city_count = len(locations_by_city)

    print(f"\nPeople:")
    print(f"  {files_with_people} files with people field")
    print(f"  {total_people_mentions} total mentions")
    print(f"  {unique_people} unique name variants")
    print(f"  {people_group_count} auto-grouped entities")

    print(f"\nLocations:")
    print(f"  {files_with_locations} files with locations field")
    print(f"  {total_location_mentions} total mentions")
    print(f"  {unique_locations} unique name variants")
    print(f"  {location_group_count} auto-grouped entities")
    print(f"  {city_count} cities")

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

    return people_group_count, location_group_count


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Extract people and locations from journal MD frontmatter for curation"
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
