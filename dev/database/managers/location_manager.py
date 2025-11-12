#!/usr/bin/env python3
"""
location_manager.py
--------------------
Manages City and Location entities with their parent-child relationship.

Cities are high-level geographic entities that contain specific Locations (venues).
Both entities have many-to-many relationships with entries, and Locations also
link to MentionedDates for visit tracking.

Key Features:
    - CRUD operations for cities and locations
    - Parent-child relationship management (City → Locations)
    - M2M relationships with entries (both entities)
    - Location visit tracking via MentionedDate M2M
    - Geographic analysis and frequency statistics

Usage:
    loc_mgr = LocationManager(session, logger)

    # Create city
    city = loc_mgr.create_city({
        "city": "Seattle",
        "state_province": "Washington",
        "country": "USA"
    })

    # Create location under city
    location = loc_mgr.create_location({
        "name": "Pike Place Market",
        "city": city
    })

    # Or create both at once
    location = loc_mgr.get_or_create_location(
        "Pike Place Market",
        "Seattle"
    )

    # Query locations by city
    seattle_locations = loc_mgr.get_locations_for_city(city)
"""
from typing import Dict, List, Optional, Any, Union

from dev.core.validators import DataValidator
from dev.core.exceptions import ValidationError, DatabaseError
from dev.database.decorators import (
    handle_db_errors,
    log_database_operation,
    validate_metadata,
)
from dev.database.models import City, Location, Entry, MentionedDate
from dev.database.relationship_manager import RelationshipManager
from .base_manager import BaseManager


class LocationManager(BaseManager):
    """
    Manages City and Location table operations and relationships.

    This manager handles both entities since they have a tight parent-child
    relationship: every Location belongs to a City.
    """

    # =========================================================================
    # CITY OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("city_exists")
    def city_exists(self, city_name: str) -> bool:
        """
        Check if a city exists.

        Args:
            city_name: The city name to check

        Returns:
            True if city exists, False otherwise
        """
        normalized = DataValidator.normalize_string(city_name)
        if not normalized:
            return False

        return self.session.query(City).filter_by(city=normalized).first() is not None

    @handle_db_errors
    @log_database_operation("get_city")
    def get_city(
        self, city_name: str = None, city_id: int = None
    ) -> Optional[City]:
        """
        Retrieve a city by name or ID.

        Args:
            city_name: The city name
            city_id: The city ID

        Returns:
            City object if found, None otherwise

        Notes:
            - If both provided, ID takes precedence
        """
        if city_id is not None:
            return self.session.get(City, city_id)

        if city_name is not None:
            normalized = DataValidator.normalize_string(city_name)
            if not normalized:
                return None
            return self.session.query(City).filter_by(city=normalized).first()

        return None

    @handle_db_errors
    @log_database_operation("get_all_cities")
    def get_all_cities(self) -> List[City]:
        """
        Retrieve all cities.

        Returns:
            List of all City objects, ordered by city name
        """
        return self.session.query(City).order_by(City.city).all()

    @handle_db_errors
    @log_database_operation("create_city")
    @validate_metadata(["city"])
    def create_city(self, metadata: Dict[str, Any]) -> City:
        """
        Create a new city.

        Args:
            metadata: Dictionary with required key:
                - city: City name (required, unique)
                Optional keys:
                - state_province: State or province
                - country: Country
                - entries: List of Entry objects or IDs
                - locations: List of Location objects or IDs

        Returns:
            Created City object

        Raises:
            ValidationError: If city name is missing or invalid
            DatabaseError: If city already exists
        """
        city_name = DataValidator.normalize_string(metadata.get("city"))
        if not city_name:
            raise ValidationError(f"Invalid city name: {metadata.get('city')}")

        # Check for existing
        existing = self.get_city(city_name=city_name)
        if existing:
            raise DatabaseError(f"City already exists: {city_name}")

        # Create city
        city = City(
            city=city_name,
            state_province=DataValidator.normalize_string(
                metadata.get("state_province")
            ),
            country=DataValidator.normalize_string(metadata.get("country")),
        )
        self.session.add(city)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(f"Created city: {city_name}", {"city_id": city.id})

        # Update relationships
        self._update_city_relationships(city, metadata, incremental=False)

        return city

    @handle_db_errors
    @log_database_operation("update_city")
    def update_city(self, city: City, metadata: Dict[str, Any]) -> City:
        """
        Update an existing city.

        Args:
            city: City object to update
            metadata: Dictionary with optional keys:
                - city: City name
                - state_province: State or province
                - country: Country
                - entries: List of entries (incremental by default)
                - locations: List of locations (incremental by default)
                - remove_entries: Entries to unlink
                - remove_locations: Locations to unlink

        Returns:
            Updated City object
        """
        # Ensure exists
        db_city = self.session.get(City, city.id)
        if db_city is None:
            raise DatabaseError(f"City with id={city.id} does not exist")

        # Attach to session
        city = self.session.merge(db_city)

        # Update scalar fields
        field_updates = {
            "city": DataValidator.normalize_string,
            "state_province": DataValidator.normalize_string,
            "country": DataValidator.normalize_string,
        }

        for field, normalizer in field_updates.items():
            if field in metadata:
                value = normalizer(metadata[field])
                if value is not None or field in ["state_province", "country"]:
                    setattr(city, field, value)

        # Update relationships
        self._update_city_relationships(city, metadata, incremental=True)

        return city

    @handle_db_errors
    @log_database_operation("delete_city")
    def delete_city(self, city: City) -> None:
        """
        Delete a city.

        Args:
            city: City object or ID to delete

        Notes:
            - This is a hard delete
            - Locations under this city will have invalid foreign keys
            - Consider updating locations first or using cascading deletes
        """
        if isinstance(city, int):
            city = self.session.get(City, city)
            if not city:
                raise DatabaseError(f"City not found with id: {city}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting city: {city.city}",
                {"city_id": city.id, "location_count": len(city.locations)},
            )

        self.session.delete(city)
        self.session.flush()

    @handle_db_errors
    @log_database_operation("get_or_create_city")
    def get_or_create_city(
        self,
        city_name: str,
        state_province: Optional[str] = None,
        country: Optional[str] = None,
    ) -> City:
        """
        Get an existing city or create it if it doesn't exist.

        Args:
            city_name: The city name
            state_province: Optional state/province
            country: Optional country

        Returns:
            City object (existing or newly created)
        """
        normalized = DataValidator.normalize_string(city_name)
        if not normalized:
            raise ValidationError("City name cannot be empty")

        # Try to get existing
        existing = self.get_city(city_name=normalized)
        if existing:
            return existing

        # Create new with extra fields
        return self._get_or_create(
            City,
            {"city": normalized},
            {
                "state_province": DataValidator.normalize_string(state_province),
                "country": DataValidator.normalize_string(country),
            },
        )

    def _update_city_relationships(
        self,
        city: City,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """Update relationships for a city."""
        # Many-to-many with entries
        if "entries" in metadata:
            items = metadata["entries"]
            remove_items = metadata.get("remove_entries", [])
            collection = city.entries

            # Replacement mode: clear and add all
            if not incremental:
                collection.clear()
                for item in items:
                    resolved_item = self._resolve_object(item, Entry)
                    if resolved_item and resolved_item not in collection:
                        collection.append(resolved_item)
            else:
                # Incremental mode: add new items
                for item in items:
                    resolved_item = self._resolve_object(item, Entry)
                    if resolved_item and resolved_item not in collection:
                        collection.append(resolved_item)

                # Remove specified items
                for item in remove_items:
                    resolved_item = self._resolve_object(item, Entry)
                    if resolved_item and resolved_item in collection:
                        collection.remove(resolved_item)

            self.session.flush()

        # One-to-many with locations (handled differently)
        if "locations" in metadata:
            items = metadata["locations"]
            remove_items = metadata.get("remove_locations", [])

            # Get existing IDs for comparison
            existing_ids = {loc.id for loc in city.locations}

            # Replacement mode: clear and add all
            if not incremental:
                city.locations.clear()
                for item in items:
                    resolved_item = self._resolve_object(item, Location)
                    if resolved_item:
                        city.locations.append(resolved_item)
            else:
                # Incremental mode: add new items
                for item in items:
                    resolved_item = self._resolve_object(item, Location)
                    if resolved_item and resolved_item.id not in existing_ids:
                        city.locations.append(resolved_item)

                # Remove specified items
                for item in remove_items:
                    resolved_item = self._resolve_object(item, Location)
                    if resolved_item and resolved_item.id in existing_ids:
                        city.locations.remove(resolved_item)

            self.session.flush()

    # =========================================================================
    # LOCATION OPERATIONS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("location_exists")
    def location_exists(self, location_name: str) -> bool:
        """
        Check if a location exists.

        Args:
            location_name: The location name to check

        Returns:
            True if location exists, False otherwise
        """
        normalized = DataValidator.normalize_string(location_name)
        if not normalized:
            return False

        return (
            self.session.query(Location).filter_by(name=normalized).first() is not None
        )

    @handle_db_errors
    @log_database_operation("get_location")
    def get_location(
        self, location_name: str = None, location_id: int = None
    ) -> Optional[Location]:
        """
        Retrieve a location by name or ID.

        Args:
            location_name: The location name
            location_id: The location ID

        Returns:
            Location object if found, None otherwise

        Notes:
            - If both provided, ID takes precedence
        """
        if location_id is not None:
            return self.session.get(Location, location_id)

        if location_name is not None:
            normalized = DataValidator.normalize_string(location_name)
            if not normalized:
                return None
            return self.session.query(Location).filter_by(name=normalized).first()

        return None

    @handle_db_errors
    @log_database_operation("get_all_locations")
    def get_all_locations(self) -> List[Location]:
        """
        Retrieve all locations.

        Returns:
            List of all Location objects, ordered by name
        """
        return self.session.query(Location).order_by(Location.name).all()

    @handle_db_errors
    @log_database_operation("create_location")
    @validate_metadata(["name", "city"])
    def create_location(self, metadata: Dict[str, Any]) -> Location:
        """
        Create a new location.

        Args:
            metadata: Dictionary with required keys:
                - name: Location name (required, unique)
                - city: City object, city ID, or city name (required)
                Optional keys:
                - entries: List of Entry objects or IDs
                - dates: List of MentionedDate objects or IDs

        Returns:
            Created Location object

        Raises:
            ValidationError: If name or city is missing/invalid
            DatabaseError: If location already exists
        """
        location_name = DataValidator.normalize_string(metadata.get("name"))
        if not location_name:
            raise ValidationError(f"Invalid location name: {metadata.get('name')}")

        # Check for existing
        existing = self.get_location(location_name=location_name)
        if existing:
            raise DatabaseError(f"Location already exists: {location_name}")

        # Resolve city
        city_spec = metadata.get("city")
        if isinstance(city_spec, City):
            city = city_spec
        elif isinstance(city_spec, int):
            city = self.get_city(city_id=city_spec)
            if not city:
                raise ValidationError(f"City not found with id: {city_spec}")
        elif isinstance(city_spec, str):
            city = self.get_or_create_city(city_spec)
        else:
            raise ValidationError(f"Invalid city specification: {city_spec}")

        # Create location
        location = Location(name=location_name, city=city)
        self.session.add(location)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Created location: {location_name}",
                {"location_id": location.id, "city": city.city},
            )

        # Update relationships
        self._update_location_relationships(location, metadata, incremental=False)

        return location

    @handle_db_errors
    @log_database_operation("update_location")
    def update_location(
        self, location: Location, metadata: Dict[str, Any]
    ) -> Location:
        """
        Update an existing location.

        Args:
            location: Location object to update
            metadata: Dictionary with optional keys:
                - name: Location name
                - city: City object, ID, or name
                - entries: List of entries (incremental by default)
                - dates: List of mentioned dates (incremental by default)
                - remove_entries: Entries to unlink
                - remove_dates: Dates to unlink

        Returns:
            Updated Location object
        """
        # Ensure exists
        db_location = self.session.get(Location, location.id)
        if db_location is None:
            raise DatabaseError(f"Location with id={location.id} does not exist")

        # Attach to session
        location = self.session.merge(db_location)

        # Update name
        if "name" in metadata:
            name = DataValidator.normalize_string(metadata["name"])
            if name:
                location.name = name

        # Update city
        if "city" in metadata:
            city_spec = metadata["city"]
            if isinstance(city_spec, City):
                location.city = city_spec
            elif isinstance(city_spec, int):
                city = self.get_city(city_id=city_spec)
                if city:
                    location.city = city
            elif isinstance(city_spec, str):
                location.city = self.get_or_create_city(city_spec)

        # Update relationships
        self._update_location_relationships(location, metadata, incremental=True)

        return location

    @handle_db_errors
    @log_database_operation("delete_location")
    def delete_location(self, location: Location) -> None:
        """
        Delete a location.

        Args:
            location: Location object or ID to delete

        Notes:
            - This is a hard delete
            - All relationships are cascade deleted
        """
        if isinstance(location, int):
            location = self.session.get(Location, location)
            if not location:
                raise DatabaseError(f"Location not found with id: {location}")

        if self.logger:
            self.logger.log_debug(
                f"Deleting location: {location.name}",
                {"location_id": location.id, "city": location.city.city},
            )

        self.session.delete(location)
        self.session.flush()

    @handle_db_errors
    @log_database_operation("get_or_create_location")
    def get_or_create_location(
        self, location_name: str, city_name: str
    ) -> Location:
        """
        Get an existing location or create it (with its city) if needed.

        This is the recommended way to work with locations when you have
        both name and city.

        Args:
            location_name: The location name
            city_name: The city name

        Returns:
            Location object (existing or newly created)
        """
        normalized_location = DataValidator.normalize_string(location_name)
        if not normalized_location:
            raise ValidationError("Location name cannot be empty")

        # Try to get existing location
        existing = self.get_location(location_name=normalized_location)
        if existing:
            return existing

        # Get or create city first
        city = self.get_or_create_city(city_name)

        # Create location
        location = Location(name=normalized_location, city=city)
        self.session.add(location)
        self.session.flush()

        if self.logger:
            self.logger.log_debug(
                f"Created location: {normalized_location}",
                {"location_id": location.id, "city": city.city},
            )

        return location

    def _update_location_relationships(
        self,
        location: Location,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """Update relationships for a location."""
        # Many-to-many relationships
        many_to_many_configs = [
            ("entries", "entries", Entry),
            ("dates", "dates", MentionedDate),
        ]

        for rel_name, meta_key, model_class in many_to_many_configs:
            if meta_key in metadata:
                items = metadata[meta_key]
                remove_items = metadata.get(f"remove_{meta_key}", [])

                # Get the collection
                collection = getattr(location, rel_name)

                # Replacement mode: clear and add all
                if not incremental:
                    collection.clear()
                    for item in items:
                        resolved_item = self._resolve_object(item, model_class)
                        if resolved_item and resolved_item not in collection:
                            collection.append(resolved_item)
                else:
                    # Incremental mode: add new items
                    for item in items:
                        resolved_item = self._resolve_object(item, model_class)
                        if resolved_item and resolved_item not in collection:
                            collection.append(resolved_item)

                    # Remove specified items
                    for item in remove_items:
                        resolved_item = self._resolve_object(item, model_class)
                        if resolved_item and resolved_item in collection:
                            collection.remove(resolved_item)

                self.session.flush()

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    @handle_db_errors
    @log_database_operation("get_locations_for_city")
    def get_locations_for_city(self, city: City) -> List[Location]:
        """
        Get all locations in a specific city.

        Args:
            city: City object

        Returns:
            List of Location objects in the city, ordered by name
        """
        return sorted(city.locations, key=lambda loc: loc.name)

    @handle_db_errors
    @log_database_operation("get_cities_for_entry")
    def get_cities_for_entry(self, entry: Entry) -> List[City]:
        """
        Get all cities mentioned in an entry.

        Args:
            entry: Entry object

        Returns:
            List of City objects, ordered by name
        """
        return sorted(entry.cities, key=lambda c: c.city)

    @handle_db_errors
    @log_database_operation("get_locations_for_entry")
    def get_locations_for_entry(self, entry: Entry) -> List[Location]:
        """
        Get all locations mentioned in an entry.

        Args:
            entry: Entry object

        Returns:
            List of Location objects, ordered by name
        """
        return sorted(entry.locations, key=lambda loc: loc.name)
