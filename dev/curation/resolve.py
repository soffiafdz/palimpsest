#!/usr/bin/env python3
"""
resolve.py
----------
Entity resolution using curated mappings.

This module provides the EntityResolver class which loads curated
entity files and resolves raw entity names to their canonical
database representations.

Key Features:
    - Loads all per-year curation files for people and locations
    - Resolves same_as chains to final canonicals
    - Supports multi-person entries (e.g., "Parents" -> [Mom, Dad])
    - In-memory caching for deduplication during import
    - Creates new database entities when needed

Resolution Flow:
    1. Raw name lookup in curation map (case-insensitive)
    2. Check cache for existing entity
    3. Check database for existing entity (by alias, then name)
    4. Create new entity if not found

Usage:
    from dev.curation.resolve import EntityResolver

    resolver = EntityResolver.load()
    people = resolver.resolve_people("Sofia", session)
    location = resolver.resolve_location("Home", session)
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# --- Third-party imports ---
import yaml
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.paths import CURATION_DIR
from dev.database.models import City, Location, Person, PersonAlias


# =============================================================================
# Entity Resolver
# =============================================================================

@dataclass
class EntityResolver:
    """
    Resolves raw entity names to canonical forms using curated files.

    Loads curated people and location files and provides lookup methods
    for resolving raw names to their canonical database representations.

    Attributes:
        people_map: Mapping of lowercase raw name -> list of canonical dicts
        locations_map: Mapping of lowercase raw name -> {name, city} dict

    Caches:
        created_people: Cache of created/found Person entities
        created_locations: Cache of created/found Location entities
        created_cities: Cache of created/found City entities
    """

    # Mapping: raw_name (lowercase) -> canonical dict(s)
    people_map: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    locations_map: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Track which entities we've already created
    created_people: Dict[str, Person] = field(default_factory=dict)
    created_locations: Dict[str, Location] = field(default_factory=dict)
    created_cities: Dict[str, City] = field(default_factory=dict)

    @classmethod
    def load(cls) -> "EntityResolver":
        """
        Load entity resolution maps from per-year curated files.

        Loads all curation files from CURATION_DIR and builds lookup
        maps for people and locations. Resolves same_as chains during
        loading.

        Returns:
            EntityResolver with populated mappings

        Raises:
            FileNotFoundError: If no curation files exist
            ValueError: If curation files are invalid
        """
        resolver = cls()

        # Load all people curation files
        people_files = sorted(CURATION_DIR.glob("*_people_curation.yaml"))
        if not people_files:
            raise FileNotFoundError(
                f"No people curation files found in {CURATION_DIR}\n"
                "Run extract_entities.py and complete manual curation first."
            )

        # First pass: collect all canonicals
        # raw_name -> list of canonical dicts (list for multi-person entries)
        people_canonicals: Dict[str, List[Dict[str, Any]]] = {}
        people_same_as: Dict[str, str] = {}  # raw_name -> target_name

        for people_file in people_files:
            with open(people_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            for raw_name, entry in data.items():
                if not isinstance(entry, dict):
                    continue

                # Skip entries marked as skip or self
                if entry.get("skip") or entry.get("self"):
                    continue

                same_as = entry.get("same_as")

                if same_as:
                    people_same_as[raw_name] = same_as
                elif "canonical" in entry:
                    canonical = entry["canonical"]
                    if isinstance(canonical, list):
                        # Multi-person entry: list of canonical dicts
                        valid = [
                            c for c in canonical
                            if isinstance(c, dict) and c.get("name")
                        ]
                        if valid:
                            people_canonicals[raw_name] = valid
                    elif isinstance(canonical, dict):
                        # All null values -> name defaults to raw key
                        if all(v is None for v in canonical.values()):
                            people_canonicals[raw_name] = [{
                                "name": raw_name,
                                "lastname": None,
                                "alias": None,
                            }]
                        elif canonical.get("name"):
                            people_canonicals[raw_name] = [canonical]
                # No canonical key -> skip (already not added)

        # Second pass: resolve same_as references
        def resolve_person_canonical(
            name: str, visited: Set[str]
        ) -> Optional[List[Dict[str, Any]]]:
            if name in visited:
                return None  # Circular reference
            visited.add(name)

            if name in people_canonicals:
                return people_canonicals[name]
            if name in people_same_as:
                return resolve_person_canonical(people_same_as[name], visited)
            return None

        # Build final people map
        all_people_names = set(people_canonicals.keys()) | set(people_same_as.keys())
        for raw_name in all_people_names:
            canonicals = resolve_person_canonical(raw_name, set())
            if canonicals:
                resolver.people_map[raw_name.lower()] = canonicals

        # Load all locations curation files
        locations_files = sorted(CURATION_DIR.glob("*_locations_curation.yaml"))
        if not locations_files:
            raise FileNotFoundError(
                f"No locations curation files found in {CURATION_DIR}\n"
                "Run extract_entities.py and complete manual curation first."
            )

        # First pass: collect all canonicals by city
        # Structure: city -> raw_name -> canonical_name
        loc_canonicals: Dict[str, Dict[str, str]] = {}
        loc_same_as: Dict[str, Dict[str, str]] = {}  # city -> raw_name -> target

        for locations_file in locations_files:
            with open(locations_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data:
                continue

            for city, locations in data.items():
                if not isinstance(locations, dict):
                    continue

                if city not in loc_canonicals:
                    loc_canonicals[city] = {}
                    loc_same_as[city] = {}

                for raw_name, entry in locations.items():
                    if not isinstance(entry, dict):
                        continue

                    # Skip entries marked as skip
                    if entry.get("skip"):
                        continue

                    same_as = entry.get("same_as")

                    if same_as:
                        loc_same_as[city][raw_name] = same_as
                    elif "canonical" in entry:
                        canonical = entry["canonical"]
                        # canonical: null -> canonical = raw key
                        if canonical is None:
                            loc_canonicals[city][raw_name] = raw_name
                        elif isinstance(canonical, str):
                            loc_canonicals[city][raw_name] = canonical
                    # No canonical key -> skip (already not added)

        # Second pass: resolve same_as references within each city
        def resolve_location_canonical(
            city: str, name: str, visited: Set[str]
        ) -> Optional[str]:
            key = f"{city}|{name}"
            if key in visited:
                return None  # Circular reference
            visited.add(key)

            if city in loc_canonicals and name in loc_canonicals[city]:
                return loc_canonicals[city][name]
            if city in loc_same_as and name in loc_same_as[city]:
                return resolve_location_canonical(
                    city, loc_same_as[city][name], visited
                )
            return None

        # Build final locations map
        for city in set(loc_canonicals.keys()) | set(loc_same_as.keys()):
            if city == "_unassigned":
                continue

            all_names: Set[str] = set()
            if city in loc_canonicals:
                all_names.update(loc_canonicals[city].keys())
            if city in loc_same_as:
                all_names.update(loc_same_as[city].keys())

            for raw_name in all_names:
                canonical_name = resolve_location_canonical(city, raw_name, set())
                if canonical_name:
                    resolver.locations_map[raw_name.lower()] = {
                        "name": canonical_name,
                        "city": city,
                    }

        return resolver

    def _resolve_single_person(
        self, canonical: Dict[str, Any], session: Session
    ) -> Optional[Person]:
        """
        Resolve a single canonical dict to a Person entity.

        Args:
            canonical: Canonical dict with name, lastname, alias, disambiguator
            session: Database session

        Returns:
            Person entity (existing or newly created), or None if invalid
        """
        name = canonical.get("name", "")
        if not name:
            return None

        lastname = canonical.get("lastname") or ""
        disambiguator = canonical.get("disambiguator") or ""

        # Handle aliases - can be string or list
        aliases_raw = canonical.get("alias")
        if isinstance(aliases_raw, list):
            aliases = [str(a) for a in aliases_raw if a]
        elif aliases_raw:
            aliases = [str(aliases_raw)]
        else:
            aliases = []

        # Cache key uses first alias for consistency
        first_alias = aliases[0] if aliases else ""
        cache_key = f"{name}|{lastname}|{first_alias}|{disambiguator}".lower()

        # Check cache first
        if cache_key in self.created_people:
            return self.created_people[cache_key]

        # Check database - try by alias first, then name/lastname
        person: Optional[Person] = None
        for alias in aliases:
            person = (
                session.query(Person)
                .join(PersonAlias)
                .filter(PersonAlias.alias == alias)
                .first()
            )
            if person:
                break

        if not person:
            if lastname:
                person = (
                    session.query(Person)
                    .filter_by(name=name, lastname=lastname)
                    .first()
                )
            elif disambiguator:
                person = (
                    session.query(Person)
                    .filter_by(name=name, disambiguator=disambiguator)
                    .first()
                )
            else:
                person = (
                    session.query(Person)
                    .filter_by(name=name, lastname=None)
                    .first()
                )

        if person:
            self.created_people[cache_key] = person
            return person

        # Create new person
        person = Person(
            name=name,
            lastname=lastname if lastname else None,
            disambiguator=disambiguator if disambiguator else None,
        )
        session.add(person)
        session.flush()

        # Add aliases
        for alias in aliases:
            person_alias = PersonAlias(person_id=person.id, alias=alias)
            session.add(person_alias)

        session.flush()
        self.created_people[cache_key] = person
        return person

    def resolve_people(
        self, raw_name: str, session: Session
    ) -> List[Person]:
        """
        Resolve a raw person name to one or more Person entities.

        Supports multi-person entries (e.g., "Parents" -> [Mom, Dad]).

        Args:
            raw_name: Raw name from YAML
            session: Database session

        Returns:
            List of Person entities (may be empty if not in curation)
        """
        lookup_key = raw_name.lower()
        canonicals = self.people_map.get(lookup_key)

        if not canonicals:
            return []

        people = []
        for canonical in canonicals:
            person = self._resolve_single_person(canonical, session)
            if person:
                people.append(person)
        return people

    def resolve_location(
        self, raw_name: str, session: Session
    ) -> Optional[Location]:
        """
        Resolve a raw location name to a Location entity.

        Args:
            raw_name: Raw location name from YAML
            session: Database session

        Returns:
            Location entity (existing or newly created), or None if not in curation
        """
        lookup_key = raw_name.lower()
        canonical = self.locations_map.get(lookup_key)

        if not canonical:
            return None

        name = canonical.get("name", "")
        city_name = canonical.get("city", "")

        if not name or not city_name:
            return None

        cache_key = f"{name}|{city_name}".lower()

        # Check cache first
        if cache_key in self.created_locations:
            return self.created_locations[cache_key]

        # Ensure city exists
        city = self._get_or_create_city(city_name, session)

        # Check database for location
        location = (
            session.query(Location).filter_by(name=name, city_id=city.id).first()
        )

        if location:
            self.created_locations[cache_key] = location
            return location

        # Create new location
        location = Location(name=name, city_id=city.id)
        session.add(location)
        session.flush()
        self.created_locations[cache_key] = location
        return location

    def _get_or_create_city(self, city_name: str, session: Session) -> City:
        """
        Get or create a city by name.

        Args:
            city_name: City name
            session: Database session

        Returns:
            City entity (existing or newly created)
        """
        cache_key = city_name.lower()

        if cache_key in self.created_cities:
            return self.created_cities[cache_key]

        city = session.query(City).filter_by(name=city_name).first()
        if city:
            self.created_cities[cache_key] = city
            return city

        city = City(name=city_name)
        session.add(city)
        session.flush()
        self.created_cities[cache_key] = city
        return city
