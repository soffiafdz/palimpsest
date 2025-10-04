#!/usr/bin/env python3
"""
export_manager.py
-----------------
Data export functionality for the database.
"""
import csv
import json
import shutil
from pathlib import Path
from datetime import datetime, timezone, date
from typing import Dict, Any, Union, Optional

from sqlalchemy.orm import Session

from dev.core.exceptions import ExportError
from dev.core.logging_manager import PalimpsestLogger
from dev.core.temporal_files import TemporalFileManager

from .decorators import handle_db_errors, log_database_operation
from .query_analytics import QueryAnalytics

# Import models for export
from .models import (
    Entry,
    Person,
    Location,
    Event,
    Tag,
    Reference,
    ReferenceSource,
    MentionedDate,
    Poem,
    PoemVersion,
    Alias,
)
from .models_manuscript import (
    ManuscriptEntry,
    ManuscriptPerson,
    ManuscriptEvent,
    Theme,
    Arc,
)


class ExportManager:
    """
    Handles data export operations for the database.

    Provides CSV and JSON export functionality with temporal file management
    for safe export operations.
    """

    def __init__(self, logger: Optional[PalimpsestLogger] = None) -> None:
        """
        Initialize export manager.

        Args:
            logger: Optional logger for export operations
        """
        self.logger = logger

    @handle_db_errors
    @log_database_operation("export_to_csv")
    def export_to_csv(
        self, session: Session, export_dir: Union[str, Path]
    ) -> Dict[str, Path]:
        """
        Export all database tables to CSV files.

        Args:
            session: SQLAlchemy session
            export_dir: Directory for CSV files

        Returns:
            Dictionary mapping table names to exported file paths
        """
        export_dir = Path(export_dir)
        export_dir.mkdir(parents=True, exist_ok=True)

        exported_files = {}

        # Define tables to export
        tables = {
            "entries": Entry,
            "people": Person,
            "locations": Location,
            "events": Event,
            "tags": Tag,
            "references": Reference,
            "reference_sources": ReferenceSource,
            "mentioned_dates": MentionedDate,
            "poems": Poem,
            "poem_versions": PoemVersion,
            "aliases": Alias,
            "manuscript_entries": ManuscriptEntry,
            "manuscript_people": ManuscriptPerson,
            "manuscript_events": ManuscriptEvent,
            "themes": Theme,
            "arcs": Arc,
        }

        with TemporalFileManager() as temp_manager:
            for table_name, model_class in tables.items():
                try:
                    exported_files[table_name] = self._export_table_to_csv(
                        session, model_class, table_name, export_dir, temp_manager
                    )
                except ExportError as e:
                    if self.logger:
                        self.logger.log_error(
                            e, {"operation": "export_table_csv", "table": table_name}
                        )
                    raise  # Re-raise instead of continuing
                except Exception as e:
                    if self.logger:
                        self.logger.log_error(
                            e, {"operation": "export_table_csv", "table": table_name}
                        )
                    raise ExportError(f"Failed to export table {table_name}: {e}")

        return exported_files

    def _export_table_to_csv(
        self,
        session: Session,
        model_class: type,
        table_name: str,
        export_dir: Path,
        temp_manager: TemporalFileManager,
    ) -> Path:
        """
        Export a single table to CSV.

        Args:
            session: SQLAlchemy session
            model_class: SQLAlchemy model class
            table_name: Name of the table
            export_dir: Export directory
            temp_manager: Temporal file manager

        Returns:
            Path to exported CSV file
        """
        temp_file = temp_manager.create_temp_file(suffix=".csv")
        final_file = export_dir / f"{table_name}.csv"

        with open(temp_file, "w", newline="", encoding="utf-8") as csvfile:
            records = session.query(model_class).all()

            if records:
                # Get column names from the first record
                fieldnames = [column.name for column in model_class.__table__.columns]

                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()

                for record in records:
                    row_data = {}
                    for field in fieldnames:
                        value = getattr(record, field, None)
                        if isinstance(value, (datetime, date)):
                            value = value.isoformat()
                        elif value is not None and hasattr(value, "value"):  # Enum
                            value = value.value
                        row_data[field] = value
                    writer.writerow(row_data)

        # Move temp file to final location
        shutil.move(str(temp_file), str(final_file))
        return final_file

    @handle_db_errors
    @log_database_operation("export_to_json")
    def export_to_json(
        self,
        session: Session,
        export_file: Union[str, Path],
        batch_size: int = 100,
    ) -> Path:
        """
        Export complete database to JSON.

        Args:
            session: SQLAlchemy session
            export_file: Path for JSON export file
            batch_size: Number of entries to process at once

        Returns:
            Path to exported JSON file
        """
        export_file = Path(export_file)

        with TemporalFileManager() as temp_manager:
            temp_file = temp_manager.create_temp_file(suffix=".json")

            with open(temp_file, "w", encoding="utf-8") as f:
                f.write("{\n")
                f.write(
                    f'  "export_timestamp": "{datetime.now(timezone.utc).isoformat()}",\n'
                )
                # Get stats (lightweight)
                analytics = QueryAnalytics(self.logger)
                stats = analytics.get_database_stats(session)
                f.write(f'  "database_stats": {json.dumps(stats, default=str)},\n')

                # Stream entries in batches
                f.write('  "entries": [\n')

                total_entries = session.query(Entry).count()
                offset = 0
                first_entry = True

                while offset < total_entries:
                    entries = (
                        session.query(Entry)
                        .order_by(Entry.date)
                        .limit(batch_size)
                        .offset(offset)
                        .all()
                    )

                    for entry in entries:
                        if not first_entry:
                            f.write(",\n")
                        first_entry = False

                        entry_data = self._serialize_entry(entry)
                        f.write("    ")
                        f.write(json.dumps(entry_data, ensure_ascii=False, default=str))

                    offset += batch_size
                    session.expunge_all()  # Clear session to free memory

                f.write("\n  ],\n")

                # Export other tables (people, locations, events) in batches
                # TODO: Add missing tables here
                f.write('  "people": [\n')
                people = session.query(Person).all()
                for i, person in enumerate(people):
                    if i > 0:
                        f.write(",\n")
                    person_data = self._serialize_person(person)
                    f.write("    ")
                    f.write(json.dumps(person_data, ensure_ascii=False, default=str))
                f.write("\n  ],\n")

                # Locations
                f.write('  "locations": [\n')
                locations = session.query(Location).all()
                for i, location in enumerate(locations):
                    if i > 0:
                        f.write(",\n")
                    f.write("    ")
                    f.write(
                        json.dumps(
                            {
                                "id": location.id,
                                "name": location.name,
                                "full_name": location.full_name,
                            },
                            ensure_ascii=False,
                            default=str,
                        )
                    )
                f.write("\n  ],\n")

                # Events
                f.write('  "events": [\n')
                events = session.query(Event).all()
                for i, event in enumerate(events):
                    if i > 0:
                        f.write(",\n")
                    f.write("    ")
                    f.write(
                        json.dumps(
                            {
                                "id": event.id,
                                "event": event.event,
                                "title": event.title,
                                "description": event.description,
                            },
                            ensure_ascii=False,
                            default=str,
                        )
                    )
                f.write("\n  ]\n")

                # Close JSON
                f.write("}\n")

            # Move to final location
            export_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_file), str(export_file))

        return export_file

    def _gather_export_data(self, session: Session) -> Dict[str, Any]:
        """
        Gather all data for JSON export.

        Args:
            session: SQLAlchemy session

        Returns:
            Dictionary with all export data
        """
        analytics = QueryAnalytics(self.logger)

        data = {
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "database_stats": analytics.get_database_stats(session),
            "entries": [],
        }

        # Export entries with all relationships
        entries = session.query(Entry).order_by(Entry.date).all()
        for entry in entries:
            entry_data = self._serialize_entry(entry)
            data["entries"].append(entry_data)

        # Export people with all data
        data["people"] = []
        people = session.query(Person).all()
        for person in people:
            person_data = self._serialize_person(person)
            data["people"].append(person_data)

        # Export locations
        data["locations"] = []
        locations = session.query(Location).all()
        for location in locations:
            data["locations"].append(
                {
                    "id": location.id,
                    "name": location.name,
                    "full_name": location.full_name,
                }
            )

        # Export events
        data["events"] = []
        events = session.query(Event).all()
        for event in events:
            data["events"].append(
                {
                    "id": event.id,
                    "event": event.event,
                    "title": event.title,
                    "description": event.description,
                }
            )

        return data

    def _serialize_entry(self, entry: Entry) -> Dict[str, Any]:
        """
        Serialize an entry with all its relationships.

        Args:
            entry: Entry instance

        Returns:
            Dictionary with serialized entry data
        """
        return {
            "id": entry.id,
            "date": entry.date.isoformat() if entry.date else None,
            "file_path": entry.file_path,
            "file_hash": entry.file_hash,
            "word_count": entry.word_count,
            "reading_time": entry.reading_time,
            "epigraph": entry.epigraph,
            "notes": entry.notes,
            "created_at": entry.created_at.isoformat() if entry.created_at else None,
            "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
            # Relationships
            "mentioned_dates": [
                {"date": md.date.isoformat(), "context": md.context}
                for md in entry.dates
            ],
            "locations": [loc.display_name for loc in entry.locations],
            "people": [person.display_name for person in entry.people],
            "events": [event.display_name for event in entry.events],
            "tags": [tag.tag for tag in entry.tags],
            "related_entries": [re.date.isoformat() for re in entry.related_entries],
            # References
            "references": [
                {
                    "content": ref.content,
                    "speaker": ref.speaker,
                    "source": (
                        {
                            "title": ref.source.title if ref.source else None,
                            "type": ref.source.type if ref.source else None,
                            "author": ref.source.author if ref.source else None,
                        }
                        if ref.source
                        else None
                    ),
                }
                for ref in entry.references
            ],
            # Poems
            "poems": [
                {
                    "title": pv.poem.title if pv.poem else None,
                    "content": pv.content,
                    "notes": pv.notes,
                    "revision_date": (
                        pv.revision_date.isoformat() if pv.revision_date else None
                    ),
                }
                for pv in entry.poems
            ],
            # Manuscript data
            "manuscript": (
                {
                    "status": entry.manuscript.status.value,
                    "edited": entry.manuscript.edited,
                    "notes": entry.manuscript.notes,
                    "themes": [theme.theme for theme in entry.manuscript.themes],
                }
                if entry.manuscript
                else None
            ),
        }

    def _serialize_person(self, person: Person) -> Dict[str, Any]:
        """
        Serialize a person with all their data.

        Args:
            person: Person instance

        Returns:
            Dictionary with serialized person data
        """
        return {
            "id": person.id,
            "name": person.name,
            "full_name": person.full_name,
            "relation_type": person.relation_type,
            "aliases": [alias.alias for alias in person.aliases],
            "manuscript": (
                {"character": person.manuscript.character}
                if person.manuscript
                else None
            ),
        }
