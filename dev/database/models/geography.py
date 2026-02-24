#!/usr/bin/env python3
"""
geography.py
------------
Geographic models for the Palimpsest database.

This module contains location-related models:

Models:
    - City: Cities mentioned in entries
    - Location: Specific venues or places within cities

Locations are linked to entries, scenes, and threads for comprehensive
geographic analysis of journal entries.
"""
# --- Annotations ---
from __future__ import annotations

# --- Standard library imports ---
from datetime import date
from typing import TYPE_CHECKING, Dict, List, Optional

# --- Third party imports ---
from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

# --- Local imports ---
from .associations import entry_cities, entry_locations, scene_locations, thread_locations
from .base import Base

if TYPE_CHECKING:
    from .analysis import Scene, Thread
    from .core import Entry


class City(Base):
    """
    Represents a city mentioned in journal entries.

    Cities are geographic containers for locations. They provide
    regional grouping for geographic analysis.

    Attributes:
        id: Primary key
        name: Name of the city (unique)
        country: Country (optional)

    Relationships:
        locations: One-to-many with Location (venues in this city)
        entries: M2M with Entry (entries mentioning this city)
    """

    __tablename__ = "cities"
    __table_args__ = (CheckConstraint("name != ''", name="ck_city_non_empty_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    country: Mapped[Optional[str]] = mapped_column(String(255))

    # --- Relationships ---
    locations: Mapped[List["Location"]] = relationship(
        "Location", back_populates="city"
    )
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_cities, back_populates="cities"
    )

    # --- Computed properties ---
    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this city."""
        return len(self.entries)

    @property
    def location_count(self) -> int:
        """Number of locations in this city."""
        return len(self.locations)

    @property
    def location_names(self) -> List[str]:
        """Names of all locations in this city."""
        return [loc.name for loc in self.locations]

    @property
    def first_mentioned(self) -> Optional[date]:
        """Earliest entry date mentioning this city."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_mentioned(self) -> Optional[date]:
        """Most recent entry date mentioning this city."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

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

    @property
    def display_name(self) -> str:
        """Get display name with optional country."""
        if self.country:
            return f"{self.name}, {self.country}"
        return self.name

    def __repr__(self) -> str:
        return f"<City(id={self.id}, name='{self.name}')>"

    def __str__(self) -> str:
        return self.display_name


class Location(Base):
    """
    Represents a specific venue or place within a city.

    Locations are specific places (cafes, parks, apartments) that
    appear in journal entries. Each location belongs to a city.

    Attributes:
        id: Primary key
        name: Name of the location/venue
        city_id: Foreign key to parent City
        neighborhood: Optional neighborhood/district within the city

    Relationships:
        city: Many-to-one with City (parent city)
        entries: M2M with Entry (entries mentioning this location)
        scenes: M2M with Scene (scenes at this location)
        threads: M2M with Thread (threads involving this location)

    Notes:
        - Unique constraint on (name, city_id) allows same-named
          locations in different cities
    """

    __tablename__ = "locations"
    __table_args__ = (
        CheckConstraint("name != ''", name="ck_location_non_empty_name"),
        UniqueConstraint("name", "city_id", name="uq_location_name_city"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    city_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cities.id", ondelete="CASCADE"), nullable=False
    )
    neighborhood: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, default=None
    )

    # --- Relationships ---
    city: Mapped["City"] = relationship("City", back_populates="locations")
    entries: Mapped[List["Entry"]] = relationship(
        "Entry", secondary=entry_locations, back_populates="locations"
    )
    scenes: Mapped[List["Scene"]] = relationship(
        "Scene", secondary=scene_locations, back_populates="locations"
    )
    threads: Mapped[List["Thread"]] = relationship(
        "Thread", secondary=thread_locations, back_populates="locations"
    )

    # --- Computed properties ---
    @property
    def entry_count(self) -> int:
        """Number of entries mentioning this location."""
        return len(self.entries)

    @property
    def scene_count(self) -> int:
        """Number of scenes at this location."""
        return len(self.scenes)

    @property
    def first_visit(self) -> Optional[date]:
        """Earliest entry date at this location."""
        if not self.entries:
            return None
        return min(entry.date for entry in self.entries)

    @property
    def last_visit(self) -> Optional[date]:
        """Most recent entry date at this location."""
        if not self.entries:
            return None
        return max(entry.date for entry in self.entries)

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

    @property
    def display_name(self) -> str:
        """Get display name with city."""
        return f"{self.name}, {self.city.name}"

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name='{self.name}', city_id={self.city_id})>"

    def __str__(self) -> str:
        return self.display_name
