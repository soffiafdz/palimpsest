"""
test_location_manager.py
------------------------
Unit tests for LocationManager CRUD operations.

Tests managing City and Location entities with their parent-child relationship.

Target Coverage: 90%+
"""
import pytest
from dev.database.models import City, Location, Entry
from dev.core.exceptions import ValidationError, DatabaseError


class TestCityExists:
    """Test LocationManager.city_exists() method."""

    def test_city_exists_returns_false_when_not_found(self, location_manager):
        """Test city_exists returns False for non-existent city."""
        assert location_manager.city_exists("NonExistent") is False

    def test_city_exists_returns_true_when_found(self, location_manager, db_session):
        """Test city_exists returns True when city exists."""
        location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        assert location_manager.city_exists("Montreal") is True

    def test_city_exists_normalizes_input(self, location_manager, db_session):
        """Test city_exists normalizes whitespace."""
        location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        assert location_manager.city_exists("  Montreal  ") is True


class TestGetCity:
    """Test LocationManager.get_city() method."""

    def test_get_city_returns_none_when_not_found(self, location_manager):
        """Test get_city returns None for non-existent city."""
        result = location_manager.get_city(city_name="NonExistent")
        assert result is None

    def test_get_city_by_name(self, location_manager, db_session):
        """Test get_city by name."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        result = location_manager.get_city(city_name="Montreal")
        assert result is not None
        assert result.id == city.id

    def test_get_city_by_id(self, location_manager, db_session):
        """Test get_city by ID."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        result = location_manager.get_city(city_id=city.id)
        assert result is not None
        assert result.city == "Montreal"

    def test_get_city_id_takes_precedence_over_name(self, location_manager, db_session):
        """Test ID takes precedence when both provided."""
        city1 = location_manager.create_city({"city": "Montreal"})
        city2 = location_manager.create_city({"city": "Toronto"})
        db_session.commit()

        result = location_manager.get_city(city_id=city2.id, city_name="Montreal")
        assert result.city == "Toronto"


class TestGetAllCities:
    """Test LocationManager.get_all_cities() method."""

    def test_get_all_cities_empty(self, location_manager):
        """Test get_all_cities returns empty list when no cities."""
        result = location_manager.get_all_cities()
        assert result == []

    def test_get_all_cities_returns_all(self, location_manager, db_session):
        """Test get_all_cities returns all cities."""
        location_manager.create_city({"city": "Montreal"})
        location_manager.create_city({"city": "Toronto"})
        location_manager.create_city({"city": "Vancouver"})
        db_session.commit()

        result = location_manager.get_all_cities()
        assert len(result) == 3
        city_names = {c.city for c in result}
        assert city_names == {"Montreal", "Toronto", "Vancouver"}

    def test_get_all_cities_ordered_alphabetically(self, location_manager, db_session):
        """Test get_all_cities returns cities ordered by name."""
        location_manager.create_city({"city": "Vancouver"})
        location_manager.create_city({"city": "Montreal"})
        location_manager.create_city({"city": "Toronto"})
        db_session.commit()

        result = location_manager.get_all_cities()
        city_names = [c.city for c in result]
        assert city_names == ["Montreal", "Toronto", "Vancouver"]


class TestCreateCity:
    """Test LocationManager.create_city() method."""

    def test_create_minimal_city(self, location_manager, db_session):
        """Test creating city with minimal required fields."""
        city = location_manager.create_city({"city": "Montreal"})

        assert city is not None
        assert city.id is not None
        assert city.city == "Montreal"

    def test_create_city_with_all_fields(self, location_manager, db_session):
        """Test creating city with all fields."""
        city = location_manager.create_city({
            "city": "Montreal",
            "state_province": "Quebec",
            "country": "Canada"
        })

        assert city.city == "Montreal"
        assert city.state_province == "Quebec"
        assert city.country == "Canada"

    def test_create_city_missing_name_raises_error(self, location_manager):
        """Test creating city without name raises error."""
        with pytest.raises(ValidationError):
            location_manager.create_city({})

    def test_create_duplicate_city_raises_error(self, location_manager, db_session):
        """Test creating duplicate city raises error."""
        location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        with pytest.raises(DatabaseError) as exc_info:
            location_manager.create_city({"city": "Montreal"})
        assert "already exists" in str(exc_info.value).lower()


class TestUpdateCity:
    """Test LocationManager.update_city() method."""

    def test_update_city_name(self, location_manager, db_session):
        """Test updating city name."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        location_manager.update_city(city, {"city": "Montréal"})
        db_session.commit()
        db_session.refresh(city)

        assert city.city == "Montréal"

    def test_update_city_state_province(self, location_manager, db_session):
        """Test updating state/province."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        location_manager.update_city(city, {"state_province": "Quebec"})
        db_session.commit()
        db_session.refresh(city)

        assert city.state_province == "Quebec"

    def test_update_nonexistent_city_raises_error(self, location_manager):
        """Test updating non-existent city raises error."""
        fake_city = City()
        fake_city.id = 99999

        with pytest.raises(DatabaseError):
            location_manager.update_city(fake_city, {"city": "Test"})


class TestDeleteCity:
    """Test LocationManager.delete_city() method."""

    def test_delete_city(self, location_manager, db_session):
        """Test deleting a city."""
        city = location_manager.create_city({"city": "Montreal"})
        city_id = city.id
        db_session.commit()

        location_manager.delete_city(city)
        db_session.commit()

        result = location_manager.get_city(city_id=city_id)
        assert result is None


class TestGetOrCreateCity:
    """Test LocationManager.get_or_create_city() method."""

    def test_get_or_create_returns_existing(self, location_manager, db_session):
        """Test get_or_create returns existing city."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()
        original_id = city.id

        result = location_manager.get_or_create_city("Montreal")
        assert result.id == original_id

    def test_get_or_create_creates_new(self, location_manager, db_session):
        """Test get_or_create creates new city when doesn't exist."""
        result = location_manager.get_or_create_city("Montreal")

        assert result is not None
        assert result.city == "Montreal"
        assert result.id is not None

    def test_get_or_create_with_extra_fields(self, location_manager, db_session):
        """Test get_or_create with state_province and country."""
        result = location_manager.get_or_create_city(
            "Montreal",
            state_province="Quebec",
            country="Canada"
        )

        assert result.city == "Montreal"
        assert result.state_province == "Quebec"
        assert result.country == "Canada"


class TestLocationExists:
    """Test LocationManager.location_exists() method."""

    def test_location_exists_returns_false_when_not_found(self, location_manager):
        """Test location_exists returns False for non-existent location."""
        assert location_manager.location_exists("NonExistent") is False

    def test_location_exists_returns_true_when_found(self, location_manager, db_session):
        """Test location_exists returns True when location exists."""
        location_manager.create_location({"name": "Cafe X", "city": "Montreal"})
        db_session.commit()

        assert location_manager.location_exists("Cafe X") is True


class TestGetLocation:
    """Test LocationManager.get_location() method."""

    def test_get_location_returns_none_when_not_found(self, location_manager):
        """Test get_location returns None for non-existent location."""
        result = location_manager.get_location(location_name="NonExistent")
        assert result is None

    def test_get_location_by_name(self, location_manager, db_session):
        """Test get_location by name."""
        location = location_manager.create_location({
            "name": "Cafe X",
            "city": "Montreal"
        })
        db_session.commit()

        result = location_manager.get_location(location_name="Cafe X")
        assert result is not None
        assert result.id == location.id

    def test_get_location_by_id(self, location_manager, db_session):
        """Test get_location by ID."""
        location = location_manager.create_location({
            "name": "Cafe X",
            "city": "Montreal"
        })
        db_session.commit()

        result = location_manager.get_location(location_id=location.id)
        assert result is not None
        assert result.name == "Cafe X"


class TestGetAllLocations:
    """Test LocationManager.get_all_locations() method."""

    def test_get_all_locations_empty(self, location_manager):
        """Test get_all_locations returns empty list when no locations."""
        result = location_manager.get_all_locations()
        assert result == []

    def test_get_all_locations_returns_all(self, location_manager, db_session):
        """Test get_all_locations returns all locations."""
        location_manager.create_location({"name": "Cafe X", "city": "Montreal"})
        location_manager.create_location({"name": "Park Y", "city": "Toronto"})
        db_session.commit()

        result = location_manager.get_all_locations()
        assert len(result) == 2


class TestCreateLocation:
    """Test LocationManager.create_location() method."""

    def test_create_location_with_city_name(self, location_manager, db_session):
        """Test creating location with city name (creates city if needed)."""
        location = location_manager.create_location({
            "name": "Cafe X",
            "city": "Montreal"
        })

        assert location is not None
        assert location.name == "Cafe X"
        assert location.city is not None
        assert location.city.city == "Montreal"

    def test_create_location_with_city_object(self, location_manager, db_session):
        """Test creating location with City object."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        location = location_manager.create_location({
            "name": "Cafe X",
            "city": city
        })

        assert location.city.id == city.id

    def test_create_location_with_city_id(self, location_manager, db_session):
        """Test creating location with city ID."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        location = location_manager.create_location({
            "name": "Cafe X",
            "city": city.id
        })

        assert location.city.id == city.id

    def test_create_location_missing_name_raises_error(self, location_manager):
        """Test creating location without name raises error."""
        with pytest.raises(ValidationError):
            location_manager.create_location({"city": "Montreal"})

    def test_create_location_missing_city_raises_error(self, location_manager):
        """Test creating location without city raises error."""
        with pytest.raises(ValidationError):
            location_manager.create_location({"name": "Cafe X"})

    def test_create_duplicate_location_raises_error(self, location_manager, db_session):
        """Test creating duplicate location raises error."""
        location_manager.create_location({"name": "Cafe X", "city": "Montreal"})
        db_session.commit()

        with pytest.raises(DatabaseError) as exc_info:
            location_manager.create_location({"name": "Cafe X", "city": "Montreal"})
        assert "already exists" in str(exc_info.value).lower()


class TestUpdateLocation:
    """Test LocationManager.update_location() method."""

    def test_update_location_name(self, location_manager, db_session):
        """Test updating location name."""
        location = location_manager.create_location({
            "name": "Cafe X",
            "city": "Montreal"
        })
        db_session.commit()

        location_manager.update_location(location, {"name": "Cafe Experience"})
        db_session.commit()
        db_session.refresh(location)

        assert location.name == "Cafe Experience"

    def test_update_location_city(self, location_manager, db_session):
        """Test updating location city."""
        location = location_manager.create_location({
            "name": "Cafe X",
            "city": "Montreal"
        })
        db_session.commit()

        location_manager.update_location(location, {"city": "Toronto"})
        db_session.commit()
        db_session.refresh(location)

        assert location.city.city == "Toronto"


class TestDeleteLocation:
    """Test LocationManager.delete_location() method."""

    def test_delete_location(self, location_manager, db_session):
        """Test deleting a location."""
        location = location_manager.create_location({
            "name": "Cafe X",
            "city": "Montreal"
        })
        location_id = location.id
        db_session.commit()

        location_manager.delete_location(location)
        db_session.commit()

        result = location_manager.get_location(location_id=location_id)
        assert result is None


class TestGetOrCreateLocation:
    """Test LocationManager.get_or_create_location() method."""

    def test_get_or_create_location_returns_existing(self, location_manager, db_session):
        """Test get_or_create returns existing location."""
        location = location_manager.create_location({
            "name": "Cafe X",
            "city": "Montreal"
        })
        db_session.commit()
        original_id = location.id

        result = location_manager.get_or_create_location("Cafe X", "Montreal")
        assert result.id == original_id

    def test_get_or_create_location_creates_new(self, location_manager, db_session):
        """Test get_or_create creates new location when doesn't exist."""
        result = location_manager.get_or_create_location("Cafe X", "Montreal")

        assert result is not None
        assert result.name == "Cafe X"
        assert result.city.city == "Montreal"


class TestGetLocationsForCity:
    """Test LocationManager.get_locations_for_city() method."""

    def test_get_locations_for_city(self, location_manager, db_session):
        """Test getting all locations in a city."""
        city = location_manager.create_city({"city": "Montreal"})
        location_manager.create_location({"name": "Cafe X", "city": city})
        location_manager.create_location({"name": "Park Y", "city": city})
        db_session.commit()
        db_session.refresh(city)

        result = location_manager.get_locations_for_city(city)
        assert len(result) == 2
        location_names = {loc.name for loc in result}
        assert location_names == {"Cafe X", "Park Y"}

    def test_get_locations_for_city_empty(self, location_manager, db_session):
        """Test getting locations for city with no locations."""
        city = location_manager.create_city({"city": "Montreal"})
        db_session.commit()

        result = location_manager.get_locations_for_city(city)
        assert len(result) == 0


class TestGetCitiesForEntry:
    """Test LocationManager.get_cities_for_entry() method."""

    def test_get_cities_for_entry(self, location_manager, entry_manager, tmp_dir, db_session):
        """Test getting all cities mentioned in an entry."""
        city1 = location_manager.create_city({"city": "Montreal"})
        city2 = location_manager.create_city({"city": "Toronto"})
        db_session.commit()

        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path),
            "cities": [city1.id, city2.id]
        })
        db_session.commit()
        db_session.refresh(entry)

        result = location_manager.get_cities_for_entry(entry)
        city_names = {c.city for c in result}
        assert city_names == {"Montreal", "Toronto"}


class TestGetLocationsForEntry:
    """Test LocationManager.get_locations_for_entry() method."""

    def test_get_locations_for_entry(self, location_manager, entry_manager, tmp_dir, db_session):
        """Test getting all locations mentioned in an entry."""
        loc1 = location_manager.create_location({"name": "Cafe X", "city": "Montreal"})
        loc2 = location_manager.create_location({"name": "Park Y", "city": "Toronto"})
        db_session.commit()

        file_path = tmp_dir / "2024-01-15.md"
        file_path.write_text("# Test")
        entry = entry_manager.create({
            "date": "2024-01-15",
            "file_path": str(file_path)
        })
        db_session.commit()

        # Manually link locations to entry
        entry.locations.append(loc1)
        entry.locations.append(loc2)
        db_session.commit()
        db_session.refresh(entry)

        result = location_manager.get_locations_for_entry(entry)
        location_names = {loc.name for loc in result}
        assert location_names == {"Cafe X", "Park Y"}


class TestLocationManagerEdgeCases:
    """Test edge cases and special scenarios."""

    def test_city_with_unicode_name(self, location_manager, db_session):
        """Test city with unicode characters."""
        city = location_manager.create_city({"city": "Montréal"})
        assert city.city == "Montréal"

    def test_location_with_unicode_name(self, location_manager, db_session):
        """Test location with unicode characters."""
        location = location_manager.create_location({
            "name": "Café Français",
            "city": "Montreal"
        })
        assert location.name == "Café Français"

    def test_city_with_hyphenated_name(self, location_manager, db_session):
        """Test city with hyphenated name."""
        city = location_manager.create_city({"city": "Saint-Jean"})
        assert city.city == "Saint-Jean"

    def test_create_multiple_locations_same_city(self, location_manager, db_session):
        """Test creating multiple locations in the same city."""
        location_manager.create_location({"name": "Cafe X", "city": "Montreal"})
        location_manager.create_location({"name": "Park Y", "city": "Montreal"})
        location_manager.create_location({"name": "Museum Z", "city": "Montreal"})
        db_session.commit()

        # Should only create one city
        cities = location_manager.get_all_cities()
        assert len(cities) == 1
        assert cities[0].city == "Montreal"

        # Should have three locations
        locations = location_manager.get_all_locations()
        assert len(locations) == 3
