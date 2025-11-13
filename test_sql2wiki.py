#!/usr/bin/env python3
"""
Test script to verify sql2wiki functionality.
Creates test data in the database and runs the export.
"""
from datetime import date
from pathlib import Path

from dev.database.manager import PalimpsestDB
from dev.database.models import Person, Entry, MentionedDate, RelationType
from dev.core.paths import DB_PATH, ALEMBIC_DIR, LOG_DIR, BACKUP_DIR, MD_DIR

# Initialize database
db = PalimpsestDB(
    db_path=DB_PATH,
    alembic_dir=ALEMBIC_DIR,
    log_dir=LOG_DIR,
    backup_dir=BACKUP_DIR,
    enable_auto_backup=False,
)

print("Creating test data...")

with db.session_scope() as session:
    # Create a test entry
    entry1 = Entry(
        date=date(2024, 11, 1),
        file_path=str(MD_DIR / "2024" / "2024-11-01.md"),
        word_count=500,
        reading_time=2.5,
    )
    session.add(entry1)
    session.flush()

    entry2 = Entry(
        date=date(2024, 11, 5),
        file_path=str(MD_DIR / "2024" / "2024-11-05.md"),
        word_count=600,
        reading_time=3.0,
    )
    session.add(entry2)
    session.flush()

    # Create test people
    person1 = Person(
        name="Alice",
        full_name="Alice Johnson",
        relation_type=RelationType.FRIEND,
    )
    session.add(person1)
    session.flush()

    person2 = Person(
        name="Bob",
        relation_type=RelationType.COLLEAGUE,
    )
    session.add(person2)
    session.flush()

    # Create mentioned dates for person1
    date1 = MentionedDate(date=date(2024, 11, 1), context="Coffee meetup")
    date2 = MentionedDate(date=date(2024, 11, 5), context="Conference discussion")
    session.add_all([date1, date2])
    session.flush()

    # Link people to dates
    person1.dates.extend([date1, date2])
    person2.dates.append(date1)

    # Link entries to dates
    entry1.dates.append(date1)
    entry2.dates.append(date2)

    # Link people to entries
    person1.entries.extend([entry1, entry2])
    person2.entries.append(entry1)

    session.commit()

    print(f"Created {session.query(Person).count()} people")
    print(f"Created {session.query(Entry).count()} entries")
    print(f"Created {session.query(MentionedDate).count()} mentioned dates")

print("\nTest data created successfully!")
print("\nNow run:")
print("  python3 -m dev.pipeline.sql2wiki export people")
