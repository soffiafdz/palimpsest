"""
test_date_manager.py
--------------------
Unit tests for DateManager CRUD operations.

Tests mentioned date management including relationships with entries,
locations, and people.

Target Coverage: 90%+
"""
import pytest
from datetime import date
from dev.database.models import MentionedDate, Entry, Location, Person, City
from dev.core.exceptions import ValidationError, DatabaseError


class TestDateManagerExists:
    """Test DateManager.exists() method."""

    def test_exists_returns_false_when_not_found(self, date_manager):
        """Test exists returns False for non-existent date."""
        assert date_manager.exists(date(2024, 6, 15)) is False

    def test_exists_returns_true_when_found(self, date_manager, db_session):
        """Test exists returns True when date exists."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        db_session.add(mentioned_date)
        db_session.commit()

        assert date_manager.exists(date(2024, 6, 15)) is True


class TestDateManagerGet:
    """Test DateManager.get() method."""

    def test_get_returns_none_when_not_found(self, date_manager):
        """Test get returns None for non-existent date."""
        result = date_manager.get(target_date=date(2024, 6, 15))
        assert result is None

    def test_get_returns_date_when_found_by_date(self, date_manager, db_session):
        """Test get returns mentioned date when it exists."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15), context="Birthday")
        db_session.add(mentioned_date)
        db_session.commit()

        result = date_manager.get(target_date=date(2024, 6, 15))
        assert result is not None
        assert result.date == date(2024, 6, 15)
        assert result.context == "Birthday"

    def test_get_returns_date_when_found_by_id(self, date_manager, db_session):
        """Test get returns mentioned date by ID."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        db_session.add(mentioned_date)
        db_session.commit()

        result = date_manager.get(date_id=mentioned_date.id)
        assert result is not None
        assert result.id == mentioned_date.id

    def test_get_prefers_id_over_date(self, date_manager, db_session):
        """Test get prefers ID when both date and ID provided."""
        date1 = MentionedDate(date=date(2024, 6, 15))
        date2 = MentionedDate(date=date(2024, 7, 20))
        db_session.add_all([date1, date2])
        db_session.commit()

        result = date_manager.get(target_date=date(2024, 6, 15), date_id=date2.id)
        assert result.id == date2.id


class TestDateManagerGetAll:
    """Test DateManager.get_all() method."""

    def test_get_all_empty(self, date_manager):
        """Test get_all returns empty list when no dates."""
        result = date_manager.get_all()
        assert result == []

    def test_get_all_returns_all_dates(self, date_manager, db_session):
        """Test get_all returns all mentioned dates."""
        dates = [
            MentionedDate(date=date(2024, 1, 15)),
            MentionedDate(date=date(2024, 2, 20)),
            MentionedDate(date=date(2024, 3, 10)),
        ]
        for d in dates:
            db_session.add(d)
        db_session.commit()

        result = date_manager.get_all()
        assert len(result) == 3

    def test_get_all_ordered_by_date(self, date_manager, db_session):
        """Test get_all returns dates in chronological order."""
        dates = [
            MentionedDate(date=date(2024, 12, 31)),
            MentionedDate(date=date(2024, 1, 1)),
            MentionedDate(date=date(2024, 6, 15)),
        ]
        for d in dates:
            db_session.add(d)
        db_session.commit()

        result = date_manager.get_all()
        date_values = [d.date for d in result]
        assert date_values == [date(2024, 1, 1), date(2024, 6, 15), date(2024, 12, 31)]

    def test_get_all_without_ordering(self, date_manager, db_session):
        """Test get_all can skip ordering."""
        dates = [
            MentionedDate(date=date(2024, 12, 31)),
            MentionedDate(date=date(2024, 1, 1)),
        ]
        for d in dates:
            db_session.add(d)
        db_session.commit()

        result = date_manager.get_all(order_by_date=False)
        assert len(result) == 2


class TestDateManagerCreate:
    """Test DateManager.create() method."""

    def test_create_minimal_date(self, date_manager):
        """Test create with minimal required fields."""
        mentioned_date = date_manager.create({"date": date(2024, 6, 15)})

        assert mentioned_date is not None
        assert mentioned_date.date == date(2024, 6, 15)
        assert mentioned_date.id is not None

    def test_create_date_with_context(self, date_manager):
        """Test create with context."""
        mentioned_date = date_manager.create({
            "date": date(2024, 6, 15),
            "context": "Anniversary celebration",
        })

        assert mentioned_date.date == date(2024, 6, 15)
        assert mentioned_date.context == "Anniversary celebration"

    def test_create_date_from_iso_string(self, date_manager):
        """Test create with ISO date string."""
        mentioned_date = date_manager.create({"date": "2024-06-15"})

        assert mentioned_date.date == date(2024, 6, 15)

    def test_create_raises_on_invalid_date_string(self, date_manager):
        """Test create raises ValidationError for invalid date string."""
        with pytest.raises(ValidationError, match="Invalid date format"):
            date_manager.create({"date": "invalid-date"})

    def test_create_raises_on_invalid_date_type(self, date_manager):
        """Test create raises ValidationError for invalid date type."""
        with pytest.raises(ValidationError, match="Invalid date type"):
            date_manager.create({"date": 12345})

    def test_create_raises_on_duplicate_date(self, date_manager, db_session):
        """Test create raises DatabaseError when date already exists."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        db_session.add(mentioned_date)
        db_session.commit()

        with pytest.raises(DatabaseError, match="already exists"):
            date_manager.create({"date": date(2024, 6, 15)})

    def test_create_with_entries(self, date_manager, db_session):
        """Test create mentioned date with linked entries."""
        entry1 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        entry2 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry-2024-01-02.md")
        db_session.add_all([entry1, entry2])
        db_session.commit()

        mentioned_date = date_manager.create({
            "date": date(2024, 6, 15),
            "entries": [entry1, entry2],
        })

        assert len(mentioned_date.entries) == 2
        assert entry1 in mentioned_date.entries
        assert entry2 in mentioned_date.entries

    def test_create_with_locations(self, date_manager, db_session):
        """Test create mentioned date with linked locations."""
        city1 = City(city="France")
        city2 = City(city="England")
        db_session.add_all([city1, city2])
        db_session.flush()

        loc1 = Location(name="Paris", city=city1)
        loc2 = Location(name="London", city=city2)
        db_session.add_all([loc1, loc2])
        db_session.commit()

        mentioned_date = date_manager.create({
            "date": date(2024, 6, 15),
            "locations": [loc1, loc2],
        })

        assert len(mentioned_date.locations) == 2
        assert loc1 in mentioned_date.locations
        assert loc2 in mentioned_date.locations

    def test_create_with_people(self, date_manager, db_session):
        """Test create mentioned date with linked people."""
        person1 = Person(name="Alice")
        person2 = Person(name="Bob")
        db_session.add_all([person1, person2])
        db_session.commit()

        mentioned_date = date_manager.create({
            "date": date(2024, 6, 15),
            "people": [person1, person2],
        })

        assert len(mentioned_date.people) == 2
        assert person1 in mentioned_date.people
        assert person2 in mentioned_date.people


class TestDateManagerUpdate:
    """Test DateManager.update() method."""

    def test_update_context(self, date_manager, db_session):
        """Test update mentioned date context."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15), context="Old context")
        db_session.add(mentioned_date)
        db_session.commit()

        updated = date_manager.update(mentioned_date, {"context": "New context"})

        assert updated.context == "New context"

    def test_update_raises_when_date_not_found(self, date_manager):
        """Test update raises when mentioned date doesn't exist."""
        fake_date = MentionedDate(date=date(2024, 6, 15), id=99999)

        with pytest.raises(DatabaseError, match="not found"):
            date_manager.update(fake_date, {"context": "New"})

    def test_update_adds_entries_incrementally(self, date_manager, db_session):
        """Test update adds entries incrementally."""
        entry1 = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        entry2 = Entry(date=date(2024, 1, 2), file_path="/path/to/entry-2024-01-02.md")
        entry3 = Entry(date=date(2024, 1, 3), file_path="/path/to/entry-2024-01-03.md")
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        mentioned_date.entries.append(entry1)
        db_session.add_all([mentioned_date, entry1, entry2, entry3])
        db_session.commit()

        date_manager.update(mentioned_date, {"entries": [entry2, entry3]})

        assert len(mentioned_date.entries) == 3
        assert entry1 in mentioned_date.entries
        assert entry2 in mentioned_date.entries
        assert entry3 in mentioned_date.entries

    def test_update_adds_locations_incrementally(self, date_manager, db_session):
        """Test update adds locations incrementally."""
        city1 = City(city="France")
        city2 = City(city="England")
        db_session.add_all([city1, city2])
        db_session.flush()

        loc1 = Location(name="Paris", city=city1)
        loc2 = Location(name="London", city=city2)
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        mentioned_date.locations.append(loc1)
        db_session.add_all([mentioned_date, loc1, loc2])
        db_session.commit()

        date_manager.update(mentioned_date, {"locations": [loc2]})

        assert len(mentioned_date.locations) == 2
        assert loc1 in mentioned_date.locations
        assert loc2 in mentioned_date.locations

    def test_update_adds_people_incrementally(self, date_manager, db_session):
        """Test update adds people incrementally."""
        person1 = Person(name="Alice")
        person2 = Person(name="Bob")
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        mentioned_date.people.append(person1)
        db_session.add_all([mentioned_date, person1, person2])
        db_session.commit()

        date_manager.update(mentioned_date, {"people": [person2]})

        assert len(mentioned_date.people) == 2
        assert person1 in mentioned_date.people
        assert person2 in mentioned_date.people


class TestDateManagerDelete:
    """Test DateManager.delete() method."""

    def test_delete_removes_mentioned_date(self, date_manager, db_session):
        """Test delete permanently removes mentioned date."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        db_session.add(mentioned_date)
        db_session.commit()
        date_id = mentioned_date.id

        date_manager.delete(mentioned_date)
        db_session.commit()

        result = db_session.get(MentionedDate, date_id)
        assert result is None

    def test_delete_by_id(self, date_manager, db_session):
        """Test delete can accept mentioned date ID."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        db_session.add(mentioned_date)
        db_session.commit()
        date_id = mentioned_date.id

        date_manager.delete(date_id)
        db_session.commit()

        result = db_session.get(MentionedDate, date_id)
        assert result is None


class TestDateManagerGetOrCreate:
    """Test DateManager.get_or_create() method."""

    def test_get_or_create_returns_existing_date(self, date_manager, db_session):
        """Test get_or_create returns existing mentioned date."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        db_session.add(mentioned_date)
        db_session.commit()
        original_id = mentioned_date.id

        result = date_manager.get_or_create(date(2024, 6, 15))
        assert result.id == original_id

    def test_get_or_create_creates_new_date(self, date_manager):
        """Test get_or_create creates new mentioned date when doesn't exist."""
        result = date_manager.get_or_create(date(2024, 6, 15))

        assert result is not None
        assert result.date == date(2024, 6, 15)
        assert result.id is not None

    def test_get_or_create_with_context(self, date_manager):
        """Test get_or_create with context."""
        result = date_manager.get_or_create(date(2024, 6, 15), context="Birthday")

        assert result.date == date(2024, 6, 15)
        assert result.context == "Birthday"

    def test_get_or_create_from_iso_string(self, date_manager):
        """Test get_or_create with ISO date string."""
        result = date_manager.get_or_create("2024-06-15")

        assert result.date == date(2024, 6, 15)

    def test_get_or_create_raises_on_invalid_string(self, date_manager):
        """Test get_or_create raises ValidationError for invalid date string."""
        with pytest.raises(ValidationError, match="Invalid date format"):
            date_manager.get_or_create("invalid-date")


class TestDateManagerLinkToEntry:
    """Test DateManager.link_to_entry() method."""

    def test_link_to_entry_adds_entry(self, date_manager, db_session):
        """Test linking mentioned date to entry."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        db_session.add_all([mentioned_date, entry])
        db_session.commit()

        date_manager.link_to_entry(mentioned_date, entry)

        assert entry in mentioned_date.entries

    def test_link_to_entry_idempotent(self, date_manager, db_session):
        """Test linking same entry twice doesn't duplicate."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        mentioned_date.entries.append(entry)
        db_session.add_all([mentioned_date, entry])
        db_session.commit()

        date_manager.link_to_entry(mentioned_date, entry)

        assert len(mentioned_date.entries) == 1

    def test_link_to_entry_raises_on_unpersisted_date(self, date_manager, db_session):
        """Test linking raises if mentioned date not persisted."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        db_session.add(entry)
        db_session.commit()

        with pytest.raises(ValueError, match="must be persisted"):
            date_manager.link_to_entry(mentioned_date, entry)

    def test_link_to_entry_raises_on_unpersisted_entry(self, date_manager, db_session):
        """Test linking raises if entry not persisted."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        entry = Entry(date=date(2024, 1, 1), file_path="/path/to/entry-2024-01-01.md")
        db_session.add(mentioned_date)
        db_session.commit()

        with pytest.raises(ValueError, match="must be persisted"):
            date_manager.link_to_entry(mentioned_date, entry)


class TestDateManagerLinkToLocation:
    """Test DateManager.link_to_location() method."""

    def test_link_to_location_adds_location(self, date_manager, db_session):
        """Test linking mentioned date to location."""
        city = City(city="France")
        db_session.add(city)
        db_session.flush()

        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        location = Location(name="Paris", city=city)
        db_session.add_all([mentioned_date, location])
        db_session.commit()

        date_manager.link_to_location(mentioned_date, location)

        assert location in mentioned_date.locations

    def test_link_to_location_idempotent(self, date_manager, db_session):
        """Test linking same location twice doesn't duplicate."""
        city = City(city="France")
        db_session.add(city)
        db_session.flush()

        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        location = Location(name="Paris", city=city)
        mentioned_date.locations.append(location)
        db_session.add_all([mentioned_date, location])
        db_session.commit()

        date_manager.link_to_location(mentioned_date, location)

        assert len(mentioned_date.locations) == 1

    def test_link_to_location_raises_on_unpersisted_date(self, date_manager, db_session):
        """Test linking raises if mentioned date not persisted."""
        city = City(city="France")
        db_session.add(city)
        db_session.flush()

        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        location = Location(name="Paris", city=city)
        db_session.add(location)
        db_session.commit()

        with pytest.raises(ValueError, match="must be persisted"):
            date_manager.link_to_location(mentioned_date, location)

    def test_link_to_location_raises_on_unpersisted_location(self, date_manager, db_session):
        """Test linking raises if location not persisted."""
        city = City(city="France")
        db_session.add(city)
        db_session.flush()

        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        location = Location(name="Paris", city=city)
        db_session.add(mentioned_date)
        db_session.commit()

        with pytest.raises(ValueError, match="Location must be persisted"):
            date_manager.link_to_location(mentioned_date, location)


class TestDateManagerLinkToPerson:
    """Test DateManager.link_to_person() method."""

    def test_link_to_person_adds_person(self, date_manager, db_session):
        """Test linking mentioned date to person."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        person = Person(name="Alice")
        db_session.add_all([mentioned_date, person])
        db_session.commit()

        date_manager.link_to_person(mentioned_date, person)

        assert person in mentioned_date.people

    def test_link_to_person_idempotent(self, date_manager, db_session):
        """Test linking same person twice doesn't duplicate."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        person = Person(name="Alice")
        mentioned_date.people.append(person)
        db_session.add_all([mentioned_date, person])
        db_session.commit()

        date_manager.link_to_person(mentioned_date, person)

        assert len(mentioned_date.people) == 1

    def test_link_to_person_raises_on_unpersisted_date(self, date_manager, db_session):
        """Test linking raises if mentioned date not persisted."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        person = Person(name="Alice")
        db_session.add(person)
        db_session.commit()

        with pytest.raises(ValueError, match="must be persisted"):
            date_manager.link_to_person(mentioned_date, person)

    def test_link_to_person_raises_on_unpersisted_person(self, date_manager, db_session):
        """Test linking raises if person not persisted."""
        mentioned_date = MentionedDate(date=date(2024, 6, 15))
        person = Person(name="Alice")
        db_session.add(mentioned_date)
        db_session.commit()

        with pytest.raises(ValueError, match="must be persisted"):
            date_manager.link_to_person(mentioned_date, person)


class TestDateManagerGetByRange:
    """Test DateManager.get_by_range() method."""

    def test_get_by_range_returns_dates_in_range(self, date_manager, db_session):
        """Test get mentioned dates within date range."""
        date1 = MentionedDate(date=date(2024, 1, 15))
        date2 = MentionedDate(date=date(2024, 2, 15))
        date3 = MentionedDate(date=date(2024, 3, 15))
        db_session.add_all([date1, date2, date3])
        db_session.commit()

        result = date_manager.get_by_range(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 2, 28),
        )

        assert len(result) == 2
        dates = [d.date for d in result]
        assert date(2024, 1, 15) in dates
        assert date(2024, 2, 15) in dates

    def test_get_by_range_with_only_start_date(self, date_manager, db_session):
        """Test get mentioned dates from start date onwards."""
        date1 = MentionedDate(date=date(2024, 1, 15))
        date2 = MentionedDate(date=date(2024, 2, 15))
        date3 = MentionedDate(date=date(2024, 3, 15))
        db_session.add_all([date1, date2, date3])
        db_session.commit()

        result = date_manager.get_by_range(start_date=date(2024, 2, 1))

        assert len(result) == 2
        dates = [d.date for d in result]
        assert date(2024, 2, 15) in dates
        assert date(2024, 3, 15) in dates

    def test_get_by_range_with_only_end_date(self, date_manager, db_session):
        """Test get mentioned dates up to end date."""
        date1 = MentionedDate(date=date(2024, 1, 15))
        date2 = MentionedDate(date=date(2024, 2, 15))
        date3 = MentionedDate(date=date(2024, 3, 15))
        db_session.add_all([date1, date2, date3])
        db_session.commit()

        result = date_manager.get_by_range(end_date=date(2024, 2, 28))

        assert len(result) == 2
        dates = [d.date for d in result]
        assert date(2024, 1, 15) in dates
        assert date(2024, 2, 15) in dates

    def test_get_by_range_returns_in_chronological_order(self, date_manager, db_session):
        """Test get_by_range returns dates in chronological order."""
        date1 = MentionedDate(date=date(2024, 3, 15))
        date2 = MentionedDate(date=date(2024, 1, 15))
        date3 = MentionedDate(date=date(2024, 2, 15))
        db_session.add_all([date1, date2, date3])
        db_session.commit()

        result = date_manager.get_by_range()

        dates = [d.date for d in result]
        assert dates == [date(2024, 1, 15), date(2024, 2, 15), date(2024, 3, 15)]
