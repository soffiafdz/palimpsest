"""
Geography Models
-----------------

Models for tracking moments, cities, and locations in the journal.

Models:
    - Moment: Points in time with context, people, and locations
    - City: Cities mentioned in entries
    - Location: Specific venues or places within cities

These models enable geographic and temporal analysis of journal entries.

Note: The original "MentionedDate" was renamed to "Moment" (P25) to better
reflect the semantic meaning - a moment captures not just a date but a
point in time with context, people involved, locations visited, and
optional event associations.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import CheckConstraint, Date, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .enums import MomentType

from .associations import (
    entry_cities,
    entry_locations,
    entry_moments,
    moment_events,
    moment_locations,
    moment_people,
)
from .base import Base

if TYPE_CHECKING:
    from .core import Entry
    from .entities import Event, Person


class Moment(Base):
    """
    Represents a point in time with context, people, and locations.

    A Moment captures a specific date with optional context about what happened,
    who was involved, where it took place, and which events it was part of.
    This enables rich temporal and relational queries across the journal.

    Moments can be of two types:
    - MOMENT (default): An event that actually happened on the referenced date
      and is narrated in the journal entry.
    - REFERENCE: A contextual link to another date. The action described happens
      on the entry date, but references something from another time.

    Attributes:
        id: Primary key
        date: The date of this moment
        context: Optional context about what happened
        type: MomentType (moment or reference), defaults to moment

    Relationships:
        entries: Many-to-many with Entry (entries that mention this moment)
        locations: Many-to-many with Location (locations visited during this moment)
        people: Many-to-many with Person (people involved in this moment)
        events: Many-to-many with Event (events this moment is part of)

    Computed Properties:
        date_formatted: ISO format string (YYYY-MM-DD)
        entry_count: Number of entries referencing this moment
        first_mention_date: When this moment was first written about
        last_mention_date: Most recent mention of this moment
        is_reference: Whether this is a reference (not a moment)

    Examples:
        # Simple moment (default type)
        Moment(date=date(2020, 3, 15))

        # Moment with context
        Moment(date=date(2020, 3, 15), context="thesis defense")

        # Reference to another date
        Moment(date=date(2025, 1, 11), type=MomentType.REFERENCE,
               context="I give Clara the negatives from the anti-date")

        # Full moment with relationships (set after creation)
        moment = Moment(date=date(2024, 7, 4), context="July 4th party")
        moment.people.extend([maria, john])
        moment.locations.append(central_park)
        moment.events.append(summer_trip_event)
    """

    __tablename__ = "moments"

    # --- Primary fields ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    context: Mapped[Optional[str]] = mapped_column(Text)
    type: Mapped[MomentType] = mapped_column(
        SAEnum(MomentType, name="momenttype", create_constraint=True),
        nullable=False,
        default=MomentType.MOMENT,
        server_default="moment",
        index=True,
    )

    # --- Relationships ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_moments, back_populates="moments"
    )
    locations: Mapped[List["Location"]] = relationship(
        "Location", secondary=moment_locations, back_populates="moments"
    )
    people: Mapped[List["Person"]] = relationship(
        "Person", secondary=moment_people, back_populates="moments"
    )
    events: Mapped[List["Event"]] = relationship(
        "Event", secondary=moment_events, back_populates="moments"
    )

    # --- Computed properties ---
    @property
    def date_formatted(self) -> str:
        """Get date in YYYY-MM-DD format"""
        return self.date.isoformat()

    @property
    def entry_count(self) -> int:
        """Count of entries referencing this date."""
        return len(self.entries) if self.entries else 0

    @property
    def location_count(self) -> int:
        """Count of locations visited on this date."""
        return len(self.locations) if self.locations else 0

    @property
    def locations_visited(self) -> List[str]:
        """Names of locations visited on this date."""
        return [loc.name for loc in self.locations] if self.locations else []

    @property
    def people_count(self) -> int:
        """Count of people present on this date."""
        return len(self.people) if self.people else 0

    @property
    def people_present(self) -> List[str]:
        """Names of people present on this date."""
        return [person.display_name for person in self.people] if self.people else []

    @property
    def first_mention_date(self) -> Optional[date]:
        """Date when this was first menioned."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_mention_date(self) -> Optional[date]:
        """Date when this was most recently mentioned."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

    @property
    def event_count(self) -> int:
        """Count of events this moment is part of."""
        return len(self.events) if self.events else 0

    @property
    def event_names(self) -> List[str]:
        """Names of events this moment is part of."""
        return [event.event for event in self.events] if self.events else []

    @property
    def is_reference(self) -> bool:
        """Check if this moment is a reference (not an actual moment)."""
        return self.type == MomentType.REFERENCE

    @property
    def type_display(self) -> str:
        """Get human-readable type name."""
        return self.type.display_name if self.type else "Moment"

    def __repr__(self) -> str:
        return f"<Moment(id={self.id}, date={self.date}, type={self.type.value})>"

    def __str__(self) -> str:
        count = self.entry_count
        type_label = "Reference" if self.is_reference else "Moment"
        if count == 0:
            return f"{type_label} {self.date_formatted} (no entries)"
        elif count == 1:
            return f"{type_label} {self.date_formatted} (1 entry)"
        else:
            return f"{type_label} {self.date_formatted} ({count} entries)"


class City(Base):
    """
    Represents Cities mentioned in entries.

    Tracks cities referenced in journal entries for geographic analysis
    and location-based queries. Cities are parent entities for Locations.

    Attributes:
        id: Primary key
        city: Name of the city (unique)
        state_province: State or province (optional)
        country: Country (optional)

    Relationships:
        locations: One-to-many with Location (specific venues in this city)
        entries: Many-to-many with Entry (entries that took place in this city)
    """

    __tablename__ = "cities"
    __table_args__ = (CheckConstraint("city != ''", name="ck_city_non_empty_name"),)

    # --- Primary fields ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    state_province: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    country: Mapped[Optional[str]] = mapped_column(String(255), index=True)

    # --- Relationship ---
    locations: Mapped[List["Location"]] = relationship(
        "Location", back_populates="city"
    )
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_cities, back_populates="cities"
    )

    # --- Computed properties ---
    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this location."""
        return len(self.entries)

    @property
    def visit_frequency(self) -> Dict[str, int]:
        """
        Calculate visit frequency by year-month.

        Returns:
            Dictionary mapping YYYY-MM strings to visit counts
        """
        frequency: Dict[str, int] = {}
        for entry in self.entries:
            year_month = entry.date.strftime("%Y-%m")
            frequency[year_month] = frequency.get(year_month, 0) + 1
        return frequency

    # Call
    def __repr__(self) -> str:
        return f"<City(id={self.id}, city={self.city})>"

    def __str__(self) -> str:
        # Build display name with available context
        parts = [self.city]

        if self.state_province:
            parts.append(self.state_province)

        if self.country:
            parts.append(self.country)

        location_str = ", ".join(parts)

        # Add entry count
        count = self.entry_count
        if count == 0:
            return f"City: {location_str} (no entries)"
        elif count == 1:
            return f"City: {location_str} (1 entry)"
        else:
            return f"City: {location_str} ({count} entries)"


class Location(Base):
    """
    Represents specific venues or places mentioned in entries.

    Tracks venues referenced in journal entries for geographic analysis
    and location-based queries. Each location belongs to a parent City.

    Attributes:
        id: Primary key
        name: Name of the location/venue (unique)
        city_id: Foreign key to parent City
        city: Relationship to parent City

    Relationships:
        city: Many-to-one with City (parent city)
        entries: Many-to-many with Entry (entries mentioning this location)
        moments: Many-to-many with Moment (moments at this location)

    Computed Properties:
        entry_count: Number of entries mentioning this location
        visit_frequency: Monthly visit frequency statistics
        visit_span_days: Days between first and last visit
    """

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_location_non_empty_name"),
        UniqueConstraint("name", "city_id", name="uq_location_name_city"),
    )

    # --- Primary fields ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(255), nullable=False, index=True  # Removed unique=True (now composite)
    )

    # --- Geographical location ---
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    city: Mapped["City"] = relationship(back_populates="locations")

    # --- Relationships ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_locations, back_populates="locations"
    )
    moments: Mapped[List["Moment"]] = relationship(
        "Moment", secondary=moment_locations, back_populates="locations"
    )

    # --- Computed properties ---
    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this location."""
        return len(self.entries)

    @property
    def visit_count(self) -> int:
        """Total number of recorded visits (explicit moments)."""
        return len(self.moments)

    @property
    def first_visit_date(self) -> Optional[date]:
        """Earliest date this location was visited."""
        moment_dates = [m.date for m in self.moments]
        return min(moment_dates) if moment_dates else None

    @property
    def last_visit_date(self) -> Optional[date]:
        """Most recent date this location was visited."""
        moment_dates = [m.date for m in self.moments]
        return max(moment_dates) if moment_dates else None

    @property
    def visit_timeline(self) -> List[Dict[str, Any]]:
        """
        Complete timeline of visits with context.

        Returns:
            List of dicts with keys: date, source ('entry'|'moment'), context
        """
        timeline = []

        # Add entry dates
        for entry in self.entries:
            timeline.append(
                {
                    "date": entry.date,
                    "source": "entry",
                    "entry_id": entry.id,
                    "context": None,
                }
            )

        # Add explicit moments
        for moment in self.moments:
            timeline.append(
                {
                    "date": moment.date,
                    "source": "moment",
                    "context": moment.context,
                    "moment_id": moment.id,
                }
            )

        # Sort by date
        timeline.sort(key=lambda x: x["date"])
        return timeline

    @property
    def visit_frequency(self) -> Dict[str, int]:
        """
        Calculate visit frequency by year-month.
        Uses all recorded visits (from moments).

        Returns:
            Dictionary mapping YYYY-MM strings to visit counts
        """
        frequency: Dict[str, int] = {}
        for moment in self.moments:
            year_month = moment.date.strftime("%Y-%m")
            frequency[year_month] = frequency.get(year_month, 0) + 1
        return frequency

    @property
    def visit_span_days(self) -> int:
        """Days between first and last visit."""
        first = self.first_visit_date
        last = self.last_visit_date
        if not first or not last or first == last:
            return 0
        return (last - first).days

    # Call
    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name={self.name})>"

    def __str__(self) -> str:
        loc_name = f"{self.name} ({self.city.city})"
        count = self.visit_count
        if count == 0:
            return f"Location {loc_name} (no visits)"
        elif count == 1:
            return f"Location {loc_name} (1 visit)"
        else:
            return f"Location {loc_name} ({count} visits)"
