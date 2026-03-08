"""Move character M2M from chapters to scenes, drop chapter_arcs.

Characters are now linked to manuscript scenes instead of chapters.
Chapter-level characters are derived as the union of scene characters.
The chapter_arcs association table is also removed.

Revision ID: 20260308_scene_characters
Revises: 20260223_theme_instances
Create Date: 2026-03-08
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260308_scene_characters"
down_revision = "20260223_theme_instances"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create scene_characters association table
    op.create_table(
        "scene_characters",
        sa.Column(
            "manuscript_scene_id",
            sa.Integer(),
            sa.ForeignKey("manuscript_scenes.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Migrate existing chapter_characters data to scene_characters
    # For each chapter-character link, link the character to all scenes
    # in that chapter
    conn = op.get_bind()
    existing = conn.execute(
        sa.text(
            "SELECT chapter_id, character_id FROM chapter_characters"
        )
    ).fetchall()
    for chapter_id, character_id in existing:
        scenes = conn.execute(
            sa.text(
                "SELECT id FROM manuscript_scenes WHERE chapter_id = :cid"
            ),
            {"cid": chapter_id},
        ).fetchall()
        for (scene_id,) in scenes:
            conn.execute(
                sa.text(
                    "INSERT OR IGNORE INTO scene_characters "
                    "(manuscript_scene_id, character_id) "
                    "VALUES (:sid, :cid)"
                ),
                {"sid": scene_id, "cid": character_id},
            )

    # Drop old tables
    op.drop_table("chapter_characters")
    op.drop_table("chapter_arcs")


def downgrade() -> None:
    # Recreate chapter_arcs
    op.create_table(
        "chapter_arcs",
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "arc_id",
            sa.Integer(),
            sa.ForeignKey("arcs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Recreate chapter_characters
    op.create_table(
        "chapter_characters",
        sa.Column(
            "chapter_id",
            sa.Integer(),
            sa.ForeignKey("chapters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "character_id",
            sa.Integer(),
            sa.ForeignKey("characters.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Migrate scene_characters back to chapter_characters
    conn = op.get_bind()
    existing = conn.execute(
        sa.text(
            "SELECT sc.character_id, ms.chapter_id "
            "FROM scene_characters sc "
            "JOIN manuscript_scenes ms ON sc.manuscript_scene_id = ms.id "
            "WHERE ms.chapter_id IS NOT NULL"
        )
    ).fetchall()
    seen = set()
    for character_id, chapter_id in existing:
        key = (chapter_id, character_id)
        if key not in seen:
            seen.add(key)
            conn.execute(
                sa.text(
                    "INSERT INTO chapter_characters "
                    "(chapter_id, character_id) VALUES (:chid, :cid)"
                ),
                {"chid": chapter_id, "cid": character_id},
            )

    op.drop_table("scene_characters")
