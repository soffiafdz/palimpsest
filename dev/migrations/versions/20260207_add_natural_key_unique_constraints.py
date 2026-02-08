"""Add unique constraints for natural key support in JSON exports.

Adds UniqueConstraint to entities that need deterministic natural keys
for portable JSON exports. Also adds unique=True to columns that serve
as natural keys (Poem.title, Chapter.title, Character.name, etc.).

Revision ID: 20260207_natural_keys
Revises: 20260201_person_slug
Create Date: 2026-02-07
"""
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260207_natural_keys"
down_revision = "20260201_person_slug"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add unique constraints for natural key support."""
    # --- Journal domain ---

    # Thread: unique (name, entry_id)
    with op.batch_alter_table("threads") as batch_op:
        batch_op.create_unique_constraint("uq_thread_name_entry", ["name", "entry_id"])

    # Poem: title unique
    with op.batch_alter_table("poems") as batch_op:
        batch_op.create_unique_constraint("uq_poem_title", ["title"])

    # PoemVersion: unique (poem_id, entry_id)
    with op.batch_alter_table("poem_versions") as batch_op:
        batch_op.create_unique_constraint("uq_poem_version_poem_entry", ["poem_id", "entry_id"])

    # MotifInstance: unique (motif_id, entry_id)
    with op.batch_alter_table("motif_instances") as batch_op:
        batch_op.create_unique_constraint("uq_motif_instance_motif_entry", ["motif_id", "entry_id"])

    # Reference: unique (source_id, entry_id, mode)
    with op.batch_alter_table("references") as batch_op:
        batch_op.create_unique_constraint(
            "uq_reference_source_entry_mode", ["source_id", "entry_id", "mode"]
        )

    # --- Manuscript domain ---

    # Part: unique number
    with op.batch_alter_table("parts") as batch_op:
        batch_op.create_unique_constraint("uq_part_number", ["number"])

    # Chapter: title unique
    with op.batch_alter_table("chapters") as batch_op:
        batch_op.create_unique_constraint("uq_chapter_title", ["title"])

    # Character: name unique
    with op.batch_alter_table("characters") as batch_op:
        batch_op.create_unique_constraint("uq_character_name", ["name"])

    # ManuscriptScene: name unique
    with op.batch_alter_table("manuscript_scenes") as batch_op:
        batch_op.create_unique_constraint("uq_ms_scene_name", ["name"])

    # PersonCharacterMap: unique (person_id, character_id)
    with op.batch_alter_table("person_character_map") as batch_op:
        batch_op.create_unique_constraint(
            "uq_person_character_map", ["person_id", "character_id"]
        )

    # ManuscriptReference: unique (chapter_id, source_id)
    with op.batch_alter_table("manuscript_references") as batch_op:
        batch_op.create_unique_constraint(
            "uq_manuscript_reference_chapter_source", ["chapter_id", "source_id"]
        )


def downgrade() -> None:
    """Remove unique constraints."""
    # --- Manuscript domain ---
    with op.batch_alter_table("manuscript_references") as batch_op:
        batch_op.drop_constraint("uq_manuscript_reference_chapter_source")

    with op.batch_alter_table("person_character_map") as batch_op:
        batch_op.drop_constraint("uq_person_character_map")

    with op.batch_alter_table("manuscript_scenes") as batch_op:
        batch_op.drop_constraint("uq_ms_scene_name")

    with op.batch_alter_table("characters") as batch_op:
        batch_op.drop_constraint("uq_character_name")

    with op.batch_alter_table("chapters") as batch_op:
        batch_op.drop_constraint("uq_chapter_title")

    with op.batch_alter_table("parts") as batch_op:
        batch_op.drop_constraint("uq_part_number")

    # --- Journal domain ---
    with op.batch_alter_table("references") as batch_op:
        batch_op.drop_constraint("uq_reference_source_entry_mode")

    with op.batch_alter_table("motif_instances") as batch_op:
        batch_op.drop_constraint("uq_motif_instance_motif_entry")

    with op.batch_alter_table("poem_versions") as batch_op:
        batch_op.drop_constraint("uq_poem_version_poem_entry")

    with op.batch_alter_table("poems") as batch_op:
        batch_op.drop_constraint("uq_poem_title")

    with op.batch_alter_table("threads") as batch_op:
        batch_op.drop_constraint("uq_thread_name_entry")
