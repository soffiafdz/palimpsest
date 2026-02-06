#!/usr/bin/env python3
"""
location_manager.py
--------------------
Manages City and Location entities with their parent-child relationship.

Cities are high-level geographic entities that contain specific Locations (venues).
Both entities have many-to-many relationships with entries, and Locations also
link to Scenes for narrative tracking.

Key Features:
    - CRUD operations for cities and locations
    - Parent-child relationship management (City → Locations)
    - M2M relationships with entries (both entities)
    - Location tracking via Scene M2M
    - Geographic analysis and frequency statistics

Usage:
    loc_mgr = LocationManager(session, logger)

    # Create city
    city = loc_mgr.create_city({
        "name": "Seattle",
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
# --- Standard library imports ---
from typing import Any, Dict, List, Optional

# --- Third-party imports ---
from sqlalchemy.orm import Session

# --- Local imports ---
from dev.core.exceptions import DatabaseError, ValidationError
from dev.core.logging_manager import PalimpsestLogger, safe_logger
from dev.core.validators import DataValidator
from dev.database.decorators import DatabaseOperation
from dev.database.models import City, Entry, Location, Scene

from .entity_manager import EntityManager, EntityManagerConfig

# Configuration for City entity
CITY_CONFIG = EntityManagerConfig(
    model_class=City,
    name_field="name",
    display_name="city",
    supports_soft_delete=False,
    order_by="name",
    scalar_fields=[
        ("name", DataValidator.normalize_string),
        ("country", DataValidator.normalize_string, True),
    ],
    relationships=[
        ("entries", "entries", Entry),
        ("locations", "locations", Location),
    ],
)


class LocationManager(EntityManager):
    """
    Manages City and Location table operations and relationships.

    Inherits EntityManager for City CRUD and adds Location-specific
    operations for the child entity.

    This manager handles both entities since they have a tight parent-child
    relationship: every Location belongs to a City.
    """

    def __init__(
        self,
        session: Session,
        logger: Optional[PalimpsestLogger] = None,
    ):
        """
        Initialize the location manager.

        Args:
            session: SQLAlchemy session
            logger: Optional logger for operation tracking
        """
        super().__init__(session, logger, CITY_CONFIG)

    # =========================================================================
    # CITY OPERATIONS (via EntityManager)
    # =========================================================================

    # Inherited from EntityManager:
    # - exists(name, entity_id) -> bool
    # - get(name, entity_id) -> Optional[City]
    # - get_all() -> List[City]
    # - get_or_create(name, extra_metadata) -> City
    # - create(metadata) -> City
    # - update(entity, metadata) -> City
    # - delete(entity) -> None

    def city_exists(self, city_name: str) -> bool:
        """
        Check if a city exists.

        Args:
            city_name: The city name to check

        Returns:
            True if city exists, False otherwise
        """
        with DatabaseOperation(self.logger, "city_exists"):
            return self.exists(name=city_name)

    def get_city(
        self, city_name: Optional[str] = None, city_id: Optional[int] = None
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
        with DatabaseOperation(self.logger, "get_city"):
            return self.get(name=city_name, entity_id=city_id)

    def get_all_cities(self) -> List[City]:
        """
        Retrieve all cities.

        Returns:
            List of all City objects, ordered by city name
        """
        with DatabaseOperation(self.logger, "get_all_cities"):
            return self.get_all()

    def create_city(self, metadata: Dict[str, Any]) -> City:
        """
        Create a new city.

        Args:
            metadata: Dictionary with required key:
                - name: City name (required, unique)
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
        DataValidator.validate_required_fields(metadata, ["name"])
        with DatabaseOperation(self.logger, "create_city"):
            return self.create(metadata)

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
        with DatabaseOperation(self.logger, "update_city"):
            return self.update(city, metadata)

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
        with DatabaseOperation(self.logger, "delete_city"):
            self.delete(city)

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
        with DatabaseOperation(self.logger, "get_or_create_city"):
            return self.get_or_create(
                city_name,
                extra_metadata={
                    "state_province": state_province,
                    "country": country,
                },
            )

    # =========================================================================
    # LOCATION OPERATIONS (Child entity)
    # =========================================================================

    def location_exists(self, location_name: str) -> bool:
        """
        Check if a location exists.

        Args:
            location_name: The location name to check

        Returns:
            True if location exists, False otherwise
        """
        with DatabaseOperation(self.logger, "location_exists"):
            return self._exists(Location, "name", location_name)

    def get_location(
        self, location_name: Optional[str] = None, location_id: Optional[int] = None
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
        with DatabaseOperation(self.logger, "get_location"):
            if location_id is not None:
                return self._get_by_id(Location, location_id)
            if location_name is not None:
                return self._get_by_field(Location, "name", location_name)
            return None

    def get_all_locations(self) -> List[Location]:
        """
        Retrieve all locations.

        Returns:
            List of all Location objects, ordered by name
        """
        with DatabaseOperation(self.logger, "get_all_locations"):
            return self._get_all(Location, order_by="name")

    def create_location(self, metadata: Dict[str, Any]) -> Location:
        """
        Create a new location.

        Args:
            metadata: Dictionary with required keys:
                - name: Location name (required, unique)
                - city: City object, city ID, or city name (required)
                Optional keys:
                - entries: List of Entry objects or IDs
                - scenes: List of Scene objects or IDs

        Returns:
            Created Location object

        Raises:
            ValidationError: If name or city is missing/invalid
            DatabaseError: If location already exists
        """
        DataValidator.validate_required_fields(metadata, ["name", "city"])
        with DatabaseOperation(self.logger, "create_location"):
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

            safe_logger(self.logger).log_debug(
                f"Created location: {location_name}",
                {"location_id": location.id, "city": city.name},
            )

            # Update relationships
            self._update_location_relationships(location, metadata, incremental=False)

            return location

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
                - scenes: List of scenes (incremental by default)
                - remove_entries: Entries to unlink
                - remove_scenes: Scenes to unlink

        Returns:
            Updated Location object
        """
        with DatabaseOperation(self.logger, "update_location"):
            db_location = self.session.get(Location, location.id)
            if db_location is None:
                raise DatabaseError(f"Location with id={location.id} does not exist")

            location = self.session.merge(db_location)

            # Update name
            self._update_scalar_fields(
                location, metadata, [("name", DataValidator.normalize_string)]
            )

            # Update city using parent resolution
            if "city" in metadata:
                city = self._resolve_parent(
                    metadata["city"],
                    City,
                    lambda **kw: self.get_city(city_id=kw.get("id")),
                    self.get_or_create_city,
                    "id",
                )
                if city:
                    location.city = city

            # Update relationships
            self._update_location_relationships(location, metadata, incremental=True)

            return location

    def delete_location(self, location: Location) -> None:
        """
        Delete a location.

        Args:
            location: Location object or ID to delete

        Notes:
            - This is a hard delete
            - All relationships are cascade deleted
        """
        with DatabaseOperation(self.logger, "delete_location"):
            if isinstance(location, int):
                location = self.session.get(Location, location)  # type: ignore[assignment]
                if not location:
                    raise DatabaseError(f"Location not found with id: {location}")

            safe_logger(self.logger).log_debug(
                f"Deleting location: {location.name}",
                {"location_id": location.id, "city": location.city.name},
            )

            self.session.delete(location)
            self.session.flush()

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
        with DatabaseOperation(self.logger, "get_or_create_location"):
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

            safe_logger(self.logger).log_debug(
                f"Created location: {normalized_location}",
                {"location_id": location.id, "city": city.name},
            )

            return location

    def _update_location_relationships(
        self,
        location: Location,
        metadata: Dict[str, Any],
        incremental: bool = True,
    ) -> None:
        """
        Update relationships for a location.

        Args:
            location: Location entity to update
            metadata: Dictionary containing relationship data
            incremental: If True, add/remove items; if False, replace
        """
        self._update_relationships(
            location,
            metadata,
            [
                ("entries", "entries", Entry),
                ("scenes", "scenes", Scene),
            ],
            incremental,
        )

    # =========================================================================
    # QUERY METHODS
    # =========================================================================

    def get_locations_for_city(self, city: City) -> List[Location]:
        """
        Get all locations in a specific city.

        Args:
            city: City object

        Returns:
            List of Location objects in the city, ordered by name
        """
        with DatabaseOperation(self.logger, "get_locations_for_city"):
            return sorted(city.locations, key=lambda loc: loc.name)

    def get_cities_for_entry(self, entry: Entry) -> List[City]:
        """
        Get all cities mentioned in an entry.

        Args:
            entry: Entry object

        Returns:
            List of City objects, ordered by name
        """
        with DatabaseOperation(self.logger, "get_cities_for_entry"):
            return sorted(entry.cities, key=lambda c: c.name)

    def get_locations_for_entry(self, entry: Entry) -> List[Location]:
        """
        Get all locations mentioned in an entry.

        Args:
            entry: Entry object

        Returns:
            List of Location objects, ordered by name
        """
        with DatabaseOperation(self.logger, "get_locations_for_entry"):
            return sorted(entry.locations, key=lambda loc: loc.name)
