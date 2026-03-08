"""
test_location_manager.py
------------------------
Unit tests for LocationManager with focus on composite identity (name, city_id).

The Location model has a composite unique constraint on (name, city_id),
meaning the same location name can exist in different cities. These tests
verify that lookup, existence, and creation methods respect this constraint.

Target Coverage: 90%+
"""
from dev.database.models import City, Location


class TestLocationCompositeIdentity:
    """Test that location operations respect the (name, city_id) constraint."""

    def _create_cities(self, db_session):
        """Create two cities for multi-city tests."""
        city_a = City(name="CityA")
        city_b = City(name="CityB")
        db_session.add_all([city_a, city_b])
        db_session.flush()
        return city_a, city_b

    def test_same_name_different_cities(self, location_manager, db_session):
        """Two locations with the same name in different cities can coexist."""
        city_a, city_b = self._create_cities(db_session)

        loc_a = Location(name="Central Park", city=city_a)
        loc_b = Location(name="Central Park", city=city_b)
        db_session.add_all([loc_a, loc_b])
        db_session.flush()

        assert loc_a.id != loc_b.id
        assert loc_a.city_id == city_a.id
        assert loc_b.city_id == city_b.id

    def test_get_location_with_city_name(self, location_manager, db_session):
        """get_location with city_name returns the correct one."""
        city_a, city_b = self._create_cities(db_session)

        loc_a = Location(name="Market", city=city_a)
        loc_b = Location(name="Market", city=city_b)
        db_session.add_all([loc_a, loc_b])
        db_session.flush()

        result = location_manager.get_location(
            location_name="Market", city_name="CityB"
        )
        assert result is not None
        assert result.id == loc_b.id

    def test_get_location_without_city_name_returns_first(
        self, location_manager, db_session
    ):
        """get_location without city_name returns any matching location."""
        city_a, _ = self._create_cities(db_session)

        loc = Location(name="UniquePlace", city=city_a)
        db_session.add(loc)
        db_session.flush()

        result = location_manager.get_location(location_name="UniquePlace")
        assert result is not None
        assert result.name == "UniquePlace"

    def test_get_location_with_city_name_no_match(
        self, location_manager, db_session
    ):
        """get_location returns None when city doesn't match."""
        city_a, _ = self._create_cities(db_session)

        db_session.add(Location(name="Library", city=city_a))
        db_session.flush()

        result = location_manager.get_location(
            location_name="Library", city_name="NonexistentCity"
        )
        assert result is None

    def test_location_exists_with_city_name(self, location_manager, db_session):
        """location_exists with city_name checks the correct city."""
        city_a, city_b = self._create_cities(db_session)

        db_session.add(Location(name="Station", city=city_a))
        db_session.flush()

        assert location_manager.location_exists("Station", city_name="CityA") is True
        assert location_manager.location_exists("Station", city_name="CityB") is False

    def test_location_exists_without_city_name(self, location_manager, db_session):
        """location_exists without city_name checks name only."""
        city_a, _ = self._create_cities(db_session)

        db_session.add(Location(name="Museum", city=city_a))
        db_session.flush()

        assert location_manager.location_exists("Museum") is True

    def test_create_location_allows_same_name_different_city(
        self, location_manager, db_session
    ):
        """create_location allows same name in different cities."""
        city_a, city_b = self._create_cities(db_session)

        loc1 = location_manager.create_location({"name": "Plaza", "city": city_a})
        loc2 = location_manager.create_location({"name": "Plaza", "city": city_b})

        assert loc1.id != loc2.id
        assert loc1.city_id == city_a.id
        assert loc2.city_id == city_b.id

    def test_create_location_rejects_duplicate_in_same_city(
        self, location_manager, db_session
    ):
        """create_location raises error for duplicate name+city."""
        city_a, _ = self._create_cities(db_session)

        location_manager.create_location({"name": "Cafe", "city": city_a})

        import pytest
        from dev.core.exceptions import DatabaseError

        with pytest.raises(DatabaseError, match="already exists"):
            location_manager.create_location({"name": "Cafe", "city": city_a})

    def test_get_or_create_location_finds_existing(
        self, location_manager, db_session
    ):
        """get_or_create_location returns existing when name+city match."""
        city_a, _ = self._create_cities(db_session)

        created = location_manager.create_location({"name": "Harbor", "city": city_a})
        found = location_manager.get_or_create_location("Harbor", "CityA")

        assert found.id == created.id

    def test_get_or_create_location_creates_in_correct_city(
        self, location_manager, db_session
    ):
        """get_or_create_location creates under the specified city."""
        self._create_cities(db_session)

        loc = location_manager.get_or_create_location("NewPlace", "CityB")
        assert loc.city.name == "CityB"
