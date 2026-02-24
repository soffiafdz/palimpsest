"""Add slug field to Person and drop unique constraint on aliases

Changes:
1. Add 'slug' column to people table (unique, for exports)
2. Drop unique constraint on person_aliases.alias (multiple people can share aliases)

Revision ID: 20260201_person_slug
Revises: de61400b5e14
Create Date: 2026-02-01
"""
import unicodedata
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260201_person_slug"
down_revision = "de61400b5e14"
branch_labels = None
depends_on = None


def slugify(text: str) -> str:
    """Convert text to slug format."""
    text = text.lower().strip()
    normalized = unicodedata.normalize("NFD", text)
    without_accents = "".join(
        c for c in normalized if unicodedata.category(c)[0] != "M"
    )
    return without_accents.replace(" ", "-")


def generate_slug(name: str, lastname: str | None, disambiguator: str | None) -> str:
    """Generate slug from name components."""
    name_slug = slugify(name)
    if lastname:
        return f"{name_slug}_{slugify(lastname)}"
    elif disambiguator:
        return f"{name_slug}_{slugify(disambiguator)}"
    else:
        return name_slug


def upgrade() -> None:
    """Add slug to people, drop unique constraint on aliases."""
    # --- Part 1: Add slug column to people ---
    # Add column as nullable first
    op.add_column("people", sa.Column("slug", sa.String(200), nullable=True))

    # Populate slugs from existing data
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT id, name, lastname, disambiguator FROM people")
    )

    # Track slugs to handle duplicates
    used_slugs: dict[str, int] = {}

    for row in result:
        person_id, name, lastname, disambiguator = row
        base_slug = generate_slug(name, lastname, disambiguator)

        # Handle potential duplicates by adding suffix
        slug = base_slug
        counter = 1
        while slug in used_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1

        used_slugs[slug] = person_id
        conn.execute(
            sa.text("UPDATE people SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": person_id}
        )

    # Make column non-nullable and add unique constraint
    # SQLite requires table recreation for this
    op.execute("""
        CREATE TABLE people_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            lastname VARCHAR(100),
            disambiguator VARCHAR(100),
            slug VARCHAR(200) NOT NULL UNIQUE,
            relation_type VARCHAR(20),
            notes TEXT,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at DATETIME,
            CONSTRAINT ck_person_non_empty_name CHECK (name != '')
        )
    """)

    op.execute("""
        INSERT INTO people_new (id, name, lastname, disambiguator, slug, relation_type, notes, is_deleted, deleted_at)
        SELECT id, name, lastname, disambiguator, slug, relation_type, notes, is_deleted, deleted_at
        FROM people
    """)

    op.execute("DROP TABLE people")
    op.execute("ALTER TABLE people_new RENAME TO people")
    op.execute("CREATE INDEX ix_people_name ON people(name)")

    # --- Part 2: Drop unique constraint on person_aliases.alias ---
    op.execute("""
        CREATE TABLE person_aliases_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            alias VARCHAR(100) NOT NULL,
            FOREIGN KEY (person_id) REFERENCES people(id)
        )
    """)

    op.execute("""
        INSERT INTO person_aliases_new (id, person_id, alias)
        SELECT id, person_id, alias FROM person_aliases
    """)

    op.execute("DROP TABLE person_aliases")
    op.execute("ALTER TABLE person_aliases_new RENAME TO person_aliases")
    op.execute("CREATE INDEX ix_person_aliases_alias ON person_aliases(alias)")


def downgrade() -> None:
    """Remove slug from people, restore unique constraint on aliases."""
    # --- Part 1: Remove slug column ---
    op.execute("""
        CREATE TABLE people_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name VARCHAR(100) NOT NULL,
            lastname VARCHAR(100),
            disambiguator VARCHAR(100),
            relation_type VARCHAR(20),
            notes TEXT,
            is_deleted BOOLEAN DEFAULT 0,
            deleted_at DATETIME,
            CONSTRAINT ck_person_non_empty_name CHECK (name != '')
        )
    """)

    op.execute("""
        INSERT INTO people_new (id, name, lastname, disambiguator, relation_type, notes, is_deleted, deleted_at)
        SELECT id, name, lastname, disambiguator, relation_type, notes, is_deleted, deleted_at
        FROM people
    """)

    op.execute("DROP TABLE people")
    op.execute("ALTER TABLE people_new RENAME TO people")
    op.execute("CREATE INDEX ix_people_name ON people(name)")

    # --- Part 2: Restore unique constraint on aliases ---
    op.execute("""
        CREATE TABLE person_aliases_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            alias VARCHAR(100) NOT NULL UNIQUE,
            FOREIGN KEY (person_id) REFERENCES people(id)
        )
    """)

    # This may fail if duplicate aliases exist
    op.execute("""
        INSERT INTO person_aliases_new (id, person_id, alias)
        SELECT id, person_id, alias FROM person_aliases
    """)

    op.execute("DROP TABLE person_aliases")
    op.execute("ALTER TABLE person_aliases_new RENAME TO person_aliases")
    op.execute("CREATE UNIQUE INDEX ix_person_aliases_alias ON person_aliases(alias)")
