"""
Geography Models
-----------------

Models for tracking dates, cities, and locations in the journal.

Models:
    - MentionedDate: Dates referenced within journal entries
    - City: Cities mentioned in entries
    - Location: Specific venues or places within cities

These models enable geographic and temporal analysis of journal entries.
"""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import CheckConstraint, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .associations import (
    entry_cities,
    entry_dates,
    entry_locations,
    location_dates,
    people_dates,
)
from .base import Base

if TYPE_CHECKING:
    from .core import Entry
    from .entities import Person


class MentionedDate(Base):
    """
    Represents dates referenced within journal entries.

    Tracks specific dates mentioned in entries, allowing for temporal
    analysis and cross-referencing of events. Dates can optionally include
    context about why they were mentioned. They can, but not necessarily
    be the date of the entry.

    Attributes:
        id: Primary key
        date: The mentioned date
        context: Optional context about why this date was mentioned

    Relationships:
        entries: Many-to-many with Entry (entries that mention this date)
        locations: Many-to-many with Location (locations visited on this date)
        people: Many-to-many with People (people interacted with on this date)

    Computed Properties:
        date_formatted: ISO format string (YYYY-MM-DD)
        entry_count: Number of entries referencing this date
        first_mention_date: When this date was first mentioned in the journal
        last_mention_date: Most recent mention of this date

    Examples:
        # Simple date mention
        MentionedDate(date=date(2020, 3, 15))

        # Date with context
        MentionedDate(date=date(2020, 3, 15), context="thesis defense")
    """

    __tablename__ = "dates"

    # --- Primary fields ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    context: Mapped[Optional[str]] = mapped_column(Text)

    # --- Relationship ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_dates, back_populates="dates"
    )
    locations: Mapped[List["Location"]] = relationship(
        "Location", secondary=location_dates, back_populates="dates"
    )
    people: Mapped[List["Person"]] = relationship(
        "Person", secondary=people_dates, back_populates="dates"
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

    def __repr__(self) -> str:
        return f"<MentionedDate(id={self.id}, date={self.date})>"

    def __str__(self) -> str:
        count = self.entry_count
        if count == 0:
            return f"Date {self.date_formatted} (no entries)"
        elif count == 1:
            return f"Date {self.date_formatted} (1 entry)"
        else:
            return f"Date {self.date_formatted} ({count} entries)"


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
        dates: Many-to-many with MentionedDate (dates related to this location)

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

    # --- Relationship ---
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_locations, back_populates="locations"
    )
    dates: Mapped[List["MentionedDate"]] = relationship(
        "MentionedDate", secondary=location_dates, back_populates="locations"
    )

    # --- Computed properties ---
    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this location."""
        return len(self.entries)

    @property
    def visit_count(self) -> int:
        """Total number of recorded visits (explicit dates)."""
        return len(self.dates)

    @property
    def first_visit_date(self) -> Optional[date]:
        """Earliest date this location was visited."""
        dates = [md.date for md in self.dates]
        return min(dates) if dates else None

    @property
    def last_visit_date(self) -> Optional[date]:
        """Most recent date this location was visited."""
        dates = [md.date for md in self.dates]
        return max(dates) if dates else None

    @property
    def visit_timeline(self) -> List[Dict[str, Any]]:
        """
        Complete timeline of visits with context.

        Returns:
            List of dicts with keys: date, source ('entry'|'mentioned'), context
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

        # Add explicit mentioned dates
        for md in self.dates:
            timeline.append(
                {
                    "date": md.date,
                    "source": "mentioned",
                    "context": md.context,
                    "mentioned_date_id": md.id,
                }
            )

        # Sort by date
        timeline.sort(key=lambda x: x["date"])
        return timeline

    @property
    def visit_frequency(self) -> Dict[str, int]:
        """
        Calculate visit frequency by year-month.
        Uses all recorded visits (entries + mentioned dates).

        Returns:
            Dictionary mapping YYYY-MM strings to visit counts
        """
        frequency: Dict[str, int] = {}
        # Count from mentioned dates
        for md in self.dates:
            year_month = md.date.strftime("%Y-%m")
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
