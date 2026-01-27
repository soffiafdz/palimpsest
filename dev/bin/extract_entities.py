#!/usr/bin/env python3
"""
extract_entities.py
-------------------
Extract people and locations from narrative_analysis YAML files for curation.

This script scans all narrative_analysis YAML files and extracts unique people
and location mentions from scenes and threads. It parses structured name formats
(e.g., @Majo (María-José Castro)) and groups by parsed alias/base name.

Key Features:
    - Parses @alias (Full Name) format for smart grouping
    - Groups people by alias, pre-fills canonical from expansions
    - Tracks locations by city (hierarchical output)
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
from dev.core.paths import NARRATIVE_ANALYSIS_DIR, CURATION_DIR
from dev.utils.parsers import extract_name_and_expansion, split_hyphenated_to_spaces


@dataclass
class Occurrence:
    """A single occurrence of an entity in the source files."""
    date: str
    context_type: str  # "scene" or "thread"
    context_name: str
    city: Optional[str] = None  # For locations


@dataclass
class ParsedPerson:
    """A parsed person reference with alias and expansion."""
    raw_name: str
    alias: Optional[str]  # The @handle part (without @)
    expansion: Optional[str]  # The (Full Name) part
    name: Optional[str]  # First name parsed from expansion
    lastname: Optional[str]  # Last name parsed from expansion

    @property
    def grouping_key(self) -> str:
        """Key used for grouping - alias if present, else normalized raw name."""
        if self.alias:
            return self.alias.lower()
        return normalize_for_grouping(self.raw_name)


@dataclass
class EntityMention:
    """An entity mention with all its occurrences."""
    raw_name: str
    occurrences: List[Occurrence] = field(default_factory=list)
    parsed: Optional[ParsedPerson] = None  # For people

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
        return [
            {"date": o.date, f"{o.context_type}": o.context_name}
            for o in samples
        ]


@dataclass
class EntityGroup:
    """A group of similar entity mentions that likely refer to the same entity."""
    id: int
    members: List[EntityMention]
    canonical: Optional[Dict[str, Any]] = None  # Pre-filled if determinable

    @property
    def total_count(self) -> int:
        return sum(m.total_count for m in self.members)


def normalize_for_grouping(name: str) -> str:
    """
    Normalize a name for grouping comparison.

    Removes @ prefix, parenthetical content, strips whitespace,
    lowercases, removes accents, and normalizes punctuation.
    """
    # Remove @ prefix
    if name.startswith("@"):
        name = name[1:]

    # Remove parenthetical content
    if "(" in name:
        name = name.split("(")[0]

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


def parse_person_name(raw_name: str) -> ParsedPerson:
    """
    Parse a person reference into structured components.

    Handles formats:
        - @Majo (María-José Castro) -> alias=majo, name=María José, lastname=Castro
        - @Majo (María) -> alias=majo, name=María, lastname=None
        - @Majo -> alias=majo, name=None, lastname=None
        - María José -> alias=None, name=María José, lastname=None
        - María-José Castro -> alias=None, name=María José, lastname=Castro
    """
    alias = None
    expansion = None
    name = None
    lastname = None

    working = raw_name.strip()

    # Extract @ alias
    if working.startswith("@"):
        working = working[1:]
        # Use existing parser for parenthetical expansion
        base, expansion = extract_name_and_expansion(working)
        alias = base.strip()

        if expansion:
            # Parse expansion into name/lastname
            # Dehyphenate the expansion first
            expansion_clean = split_hyphenated_to_spaces(expansion)
            parts = expansion_clean.split()
            if len(parts) >= 2:
                # Last word is lastname, rest is name
                lastname = parts[-1]
                name = " ".join(parts[:-1])
            elif len(parts) == 1:
                name = parts[0]
    else:
        # No alias - try to parse as a plain name
        base, expansion = extract_name_and_expansion(working)
        if expansion:
            # Has parenthetical - use expansion as the full name
            expansion_clean = split_hyphenated_to_spaces(expansion)
            parts = expansion_clean.split()
            if len(parts) >= 2:
                lastname = parts[-1]
                name = " ".join(parts[:-1])
            elif len(parts) == 1:
                name = parts[0]
        else:
            # Plain name - dehyphenate and try to split
            name_clean = split_hyphenated_to_spaces(base)
            parts = name_clean.split()
            if len(parts) >= 2:
                # Could be "First Last" - but don't assume
                # Just use the whole thing as name
                name = name_clean
            elif len(parts) == 1:
                name = parts[0]

    return ParsedPerson(
        raw_name=raw_name,
        alias=alias,
        expansion=expansion,
        name=name,
        lastname=lastname,
    )


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


def should_group_people(parsed1: ParsedPerson, parsed2: ParsedPerson) -> bool:
    """
    Determine if two parsed people should be grouped.

    Groups by:
    - Same alias (case-insensitive)
    - Very similar base names (Levenshtein ≤ 1)
    """
    key1 = parsed1.grouping_key
    key2 = parsed2.grouping_key

    if not key1 or not key2:
        return False

    # Exact match on grouping key
    if key1 == key2:
        return True

    # Levenshtein distance ≤ 1 for typos
    if abs(len(key1) - len(key2)) <= 1 and levenshtein_distance(key1, key2) <= 1:
        return True

    return False


def should_group_locations(name1: str, name2: str) -> bool:
    """Determine if two location names should be grouped."""
    n1 = normalize_for_grouping(name1)
    n2 = normalize_for_grouping(name2)

    if not n1 or not n2:
        return False

    if n1 == n2:
        return True

    if abs(len(n1) - len(n2)) <= 1 and levenshtein_distance(n1, n2) <= 1:
        return True

    return False


def extract_from_yaml(
    yaml_path: Path,
) -> Tuple[Dict[str, Tuple[List[Occurrence], ParsedPerson]], Dict[str, Dict[str, List[Occurrence]]]]:
    """
    Extract people and locations from a single YAML file.

    Returns:
        Tuple of:
        - people_dict: raw_name -> (occurrences, parsed_person)
        - locations_dict: city -> {raw_name -> occurrences}
    """
    people: Dict[str, Tuple[List[Occurrence], ParsedPerson]] = {}
    locations: Dict[str, Dict[str, List[Occurrence]]] = defaultdict(lambda: defaultdict(list))

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

    # Get city from entry-level data
    city = data.get("city", "_unassigned")
    if not city:
        city = "_unassigned"
    # Normalize city name
    city = str(city).strip()

    def process_people(person_list: List, context_type: str, context_name: str):
        for person in person_list or []:
            if not person:
                continue
            raw = str(person)
            occ = Occurrence(date=date_str, context_type=context_type, context_name=context_name)

            if raw not in people:
                parsed = parse_person_name(raw)
                people[raw] = ([], parsed)
            people[raw][0].append(occ)

    def process_locations(loc_list: List, context_type: str, context_name: str):
        for location in loc_list or []:
            if not location:
                continue
            raw = str(location)
            occ = Occurrence(date=date_str, context_type=context_type, context_name=context_name, city=city)
            locations[city][raw].append(occ)

    # Extract from scenes
    for scene in data.get("scenes", []) or []:
        if not isinstance(scene, dict):
            continue
        scene_name = scene.get("name", "Unknown Scene")
        process_people(scene.get("people", []), "scene", scene_name)
        process_locations(scene.get("locations", []), "scene", scene_name)

    # Extract from threads
    for thread in data.get("threads", []) or []:
        if not isinstance(thread, dict):
            continue
        thread_name = thread.get("name", "Unknown Thread")
        process_people(thread.get("people", []), "thread", thread_name)
        process_locations(thread.get("locations", []), "thread", thread_name)

    return people, locations


def group_people(
    all_people: Dict[str, Tuple[List[Occurrence], ParsedPerson]]
) -> List[EntityGroup]:
    """Group people by parsed alias/name."""
    if not all_people:
        return []

    # Build mentions
    mentions = []
    for raw_name, (occurrences, parsed) in all_people.items():
        mention = EntityMention(raw_name=raw_name, occurrences=occurrences, parsed=parsed)
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

    # Group by parsed alias/name
    for i in range(len(mentions)):
        for j in range(i + 1, len(mentions)):
            p1 = mentions[i].parsed
            p2 = mentions[j].parsed
            if p1 and p2 and should_group_people(p1, p2):
                union(i, j)

    # Build groups
    groups_dict: Dict[int, List[EntityMention]] = defaultdict(list)
    for i, mention in enumerate(mentions):
        root = find(i)
        groups_dict[root].append(mention)

    # Create EntityGroup objects with pre-filled canonical
    groups = []
    for group_id, (_, members) in enumerate(
        sorted(groups_dict.items(), key=lambda x: -sum(m.total_count for m in x[1])),
        start=1
    ):
        members.sort(key=lambda m: -m.total_count)

        # Build canonical from the most detailed expansion
        canonical = build_people_canonical(members)

        groups.append(EntityGroup(id=group_id, members=members, canonical=canonical))

    return groups


def build_people_canonical(members: List[EntityMention]) -> Optional[Dict[str, Any]]:
    """
    Build canonical dict from group members.

    Picks the most detailed expansion available.
    """
    best_alias = None
    best_name = None
    best_lastname = None

    for member in members:
        parsed = member.parsed
        if not parsed:
            continue

        # Prefer alias if any member has one
        if parsed.alias and not best_alias:
            best_alias = parsed.alias

        # Prefer name from expansion (most detailed wins)
        if parsed.name:
            if not best_name or len(parsed.name) > len(best_name):
                best_name = parsed.name

        # Prefer lastname from expansion
        if parsed.lastname:
            if not best_lastname or len(parsed.lastname) > len(best_lastname):
                best_lastname = parsed.lastname

    # If we have at least a name or alias, build canonical
    if best_name or best_alias:
        return {
            "name": best_name or (best_alias.title() if best_alias else None),
            "lastname": best_lastname,
            "alias": best_alias,
        }

    # Fallback: use the most common raw name
    if members:
        raw = members[0].raw_name
        if raw.startswith("@"):
            raw = raw[1:]
        # Remove parenthetical
        if "(" in raw:
            raw = raw.split("(")[0].strip()
        return {
            "name": split_hyphenated_to_spaces(raw),
            "lastname": None,
            "alias": None,
        }

    return None


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
                if should_group_locations(mentions[i].raw_name, mentions[j].raw_name):
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
    Extract all entities from narrative_analysis files.

    Args:
        dry_run: If True, don't write output files

    Returns:
        Tuple of (people_group_count, location_group_count)
    """
    yaml_files = sorted(NARRATIVE_ANALYSIS_DIR.glob("**/*.yaml"))
    yaml_files = [f for f in yaml_files if not f.name.startswith("_")]

    print(f"Scanning {len(yaml_files)} YAML files...")

    # Aggregate all data
    all_people: Dict[str, Tuple[List[Occurrence], ParsedPerson]] = {}
    all_locations: Dict[str, Dict[str, List[Occurrence]]] = defaultdict(lambda: defaultdict(list))

    for yaml_path in yaml_files:
        people, locations = extract_from_yaml(yaml_path)

        # Merge people
        for raw_name, (occs, parsed) in people.items():
            if raw_name not in all_people:
                all_people[raw_name] = ([], parsed)
            all_people[raw_name][0].extend(occs)

        # Merge locations by city
        for city, city_locs in locations.items():
            for raw_name, occs in city_locs.items():
                all_locations[city][raw_name].extend(occs)

    # Group entities
    people_groups = group_people(all_people)
    locations_by_city = group_locations_by_city(all_locations)

    # Generate drafts
    people_draft = generate_people_draft(people_groups)
    locations_draft = generate_locations_draft(locations_by_city)

    # Statistics
    total_people_mentions = sum(len(occs) for occs, _ in all_people.values())
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
    print(f"  {total_people_mentions} total mentions")
    print(f"  {unique_people} unique name variants")
    print(f"  {people_group_count} auto-grouped entities")

    print(f"\nLocations:")
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
