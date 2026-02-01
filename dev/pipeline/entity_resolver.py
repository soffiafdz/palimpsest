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
    - Validate-only mode for pre-import validation (no DB required)

Resolution Flow:
    1. Raw name lookup in curation map (case-insensitive)
    2. Check cache for existing entity
    3. Check database for existing entity (by alias, then name)
    4. Create new entity if not found

Validation Flow (no DB):
    1. Raw name lookup in curation map (case-insensitive)
    2. Return canonical info if found
    3. Return suggestions for similar names if not found

Usage:
    from dev.curation.resolve import EntityResolver

    # For DB import
    resolver = EntityResolver.load()
    people = resolver.resolve_people("Sofia", session)
    location = resolver.resolve_location("Home", session)

    # For validation only (no DB)
    resolver = EntityResolver.load()
    result = resolver.validate_person("Sofia")
    if result.found:
        print(f"Found: {result.canonical}")
    else:
        print(f"Not found. Suggestions: {result.suggestions}")
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
# Validation Result Models
# =============================================================================


@dataclass
class EntityLookupResult:
    """
    Result of an entity validation lookup.

    Attributes:
        raw_name: The original raw name that was looked up
        found: Whether the entity was found in curation
        canonical: The canonical form(s) if found (list for multi-person)
        suggestions: Similar names if not found (for error messages)
    """

    raw_name: str
    found: bool
    canonical: Optional[List[Dict[str, Any]]] = None
    suggestions: List[str] = field(default_factory=list)

    def format_canonical(self) -> str:
        """
        Format canonical info for display.

        Returns:
            Human-readable string of canonical form(s)
        """
        if not self.canonical:
            return ""

        parts = []
        for c in self.canonical:
            name = c.get("name", "")
            lastname = c.get("lastname", "")
            disambiguator = c.get("disambiguator", "")
            alias = c.get("alias", "")

            if lastname:
                display = f"{name} {lastname}"
            elif disambiguator:
                display = f"{name} ({disambiguator})"
            else:
                display = name

            if alias:
                if isinstance(alias, list):
                    display += f" [aliases: {', '.join(alias)}]"
                else:
                    display += f" [alias: {alias}]"

            parts.append(display)

        return ", ".join(parts)


@dataclass
class LocationLookupResult:
    """
    Result of a location validation lookup.

    Attributes:
        raw_name: The original raw name that was looked up
        found: Whether the location was found in curation
        canonical_name: The canonical location name if found
        city: The city name if found
        suggestions: Similar names if not found (for error messages)
    """

    raw_name: str
    found: bool
    canonical_name: Optional[str] = None
    city: Optional[str] = None
    suggestions: List[str] = field(default_factory=list)

    def format_canonical(self) -> str:
        """
        Format canonical info for display.

        Returns:
            Human-readable string like "Location Name (City)"
        """
        if not self.canonical_name:
            return ""
        return f"{self.canonical_name} ({self.city})"


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

    def clear_caches(self) -> None:
        """
        Clear entity caches.

        Call this after a session rollback to avoid stale/detached objects.
        Does not clear the curation maps (people_map, locations_map) which
        are loaded from files and remain valid.
        """
        self.created_people.clear()
        self.created_locations.clear()
        self.created_cities.clear()

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

    # =========================================================================
    # Validation Methods (no DB required)
    # =========================================================================

    def validate_person(self, raw_name: str) -> EntityLookupResult:
        """
        Validate a person name against curation without DB access.

        Checks if the raw name exists in the curation map and returns
        the canonical form if found, or suggestions if not.

        Args:
            raw_name: Raw person name from metadata YAML

        Returns:
            EntityLookupResult with found status and canonical/suggestions
        """
        lookup_key = raw_name.lower()
        canonicals = self.people_map.get(lookup_key)

        if canonicals:
            return EntityLookupResult(
                raw_name=raw_name,
                found=True,
                canonical=canonicals,
            )

        # Not found - find suggestions
        suggestions = self._find_similar_people(raw_name)
        return EntityLookupResult(
            raw_name=raw_name,
            found=False,
            suggestions=suggestions,
        )

    def validate_location(self, raw_name: str) -> LocationLookupResult:
        """
        Validate a location name against curation without DB access.

        Checks if the raw name exists in the curation map and returns
        the canonical form if found, or suggestions if not.

        Args:
            raw_name: Raw location name from metadata YAML

        Returns:
            LocationLookupResult with found status and canonical/suggestions
        """
        lookup_key = raw_name.lower()
        canonical = self.locations_map.get(lookup_key)

        if canonical:
            return LocationLookupResult(
                raw_name=raw_name,
                found=True,
                canonical_name=canonical.get("name"),
                city=canonical.get("city"),
            )

        # Not found - find suggestions
        suggestions = self._find_similar_locations(raw_name)
        return LocationLookupResult(
            raw_name=raw_name,
            found=False,
            suggestions=suggestions,
        )

    def _find_similar_people(self, raw_name: str, max_suggestions: int = 5) -> List[str]:
        """
        Find similar person names in curation for suggestions.

        Uses simple substring matching and Levenshtein-like scoring.

        Args:
            raw_name: The name to find similar matches for
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of similar names with their canonical forms
        """
        raw_lower = raw_name.lower()
        scored: List[tuple] = []

        for key, canonicals in self.people_map.items():
            # Score based on substring match or first letter match
            score = 0
            if raw_lower in key or key in raw_lower:
                score = 3  # Substring match
            elif raw_lower[0] == key[0]:
                score = 1  # Same first letter

            if score > 0:
                # Format the canonical for display
                for c in canonicals:
                    name = c.get("name", "")
                    lastname = c.get("lastname", "")
                    disambiguator = c.get("disambiguator", "")

                    if lastname:
                        display = f"{name} {lastname}"
                    elif disambiguator:
                        display = f"{name} ({disambiguator})"
                    else:
                        display = name

                    scored.append((score, display))

        # Sort by score descending, take top suggestions
        scored.sort(key=lambda x: (-x[0], x[1]))
        seen: Set[str] = set()
        suggestions = []
        for _, display in scored:
            if display not in seen:
                seen.add(display)
                suggestions.append(display)
                if len(suggestions) >= max_suggestions:
                    break

        return suggestions

    def _find_similar_locations(self, raw_name: str, max_suggestions: int = 5) -> List[str]:
        """
        Find similar location names in curation for suggestions.

        Args:
            raw_name: The name to find similar matches for
            max_suggestions: Maximum number of suggestions to return

        Returns:
            List of similar locations formatted as "Name (City)"
        """
        raw_lower = raw_name.lower()
        scored: List[tuple] = []

        for key, canonical in self.locations_map.items():
            score = 0
            if raw_lower in key or key in raw_lower:
                score = 3
            elif raw_lower[0] == key[0]:
                score = 1

            if score > 0:
                name = canonical.get("name", "")
                city = canonical.get("city", "")
                display = f"{name} ({city})"
                scored.append((score, display))

        scored.sort(key=lambda x: (-x[0], x[1]))
        seen: Set[str] = set()
        suggestions = []
        for _, display in scored:
            if display not in seen:
                seen.add(display)
                suggestions.append(display)
                if len(suggestions) >= max_suggestions:
                    break

        return suggestions

    def person_exists(self, raw_name: str) -> bool:
        """
        Quick check if a person name exists in curation.

        Args:
            raw_name: Raw person name

        Returns:
            True if found in curation map
        """
        return raw_name.lower() in self.people_map

    def location_exists(self, raw_name: str) -> bool:
        """
        Quick check if a location name exists in curation.

        Args:
            raw_name: Raw location name

        Returns:
            True if found in curation map
        """
        return raw_name.lower() in self.locations_map

    # =========================================================================
    # DB Resolution Methods
    # =========================================================================

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

    def resolve_city(self, city_name: str, session: Session) -> City:
        """
        Resolve a city name to a City entity.

        Public wrapper for _get_or_create_city that matches resolve_location API.

        Args:
            city_name: City name
            session: Database session

        Returns:
            City entity (existing or newly created)
        """
        return self._get_or_create_city(city_name, session)

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
