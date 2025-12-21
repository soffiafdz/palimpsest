"""add_narrative_analysis_schema

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2025-12-21 12:00:00.000000

Adds schema support for narrative analysis data propagation:
- TagCategory: Semantic categories for grouping tags
- Tag.category_id: FK to TagCategory
- ManuscriptEntry.narrative_rating: 1-5 rating from analysis
- ManuscriptEntry.summary: Narrative summary from analysis
- Motif: Thematic motifs (THE BODY, THE OBSESSIVE LOOP, etc.)
- entry_motifs: Many-to-many linking entries to motifs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add narrative analysis schema.

    Creates:
    - tag_categories table
    - tags.category_id FK
    - manuscript_entries.narrative_rating column
    - manuscript_entries.summary column
    - motifs table
    - entry_motifs association table
    """
    # Create tag_categories table
    op.create_table(
        'tag_categories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.CheckConstraint("name != ''", name='ck_tag_category_non_empty_name'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_tag_categories_name', 'tag_categories', ['name'], unique=True)

    # Add category_id to tags
    op.add_column(
        'tags',
        sa.Column('category_id', sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        'fk_tags_category_id',
        'tags', 'tag_categories',
        ['category_id'], ['id'],
        ondelete='SET NULL'
    )

    # Add narrative_rating and summary to manuscript_entries
    op.add_column(
        'manuscript_entries',
        sa.Column('narrative_rating', sa.Integer(), nullable=True)
    )
    op.create_check_constraint(
        'ck_manuscript_entries_rating_range',
        'manuscript_entries',
        'narrative_rating >= 1 AND narrative_rating <= 5'
    )
    op.create_index(
        'ix_manuscript_entries_narrative_rating',
        'manuscript_entries',
        ['narrative_rating']
    )
    op.add_column(
        'manuscript_entries',
        sa.Column('rating_justification', sa.Text(), nullable=True)
    )
    op.add_column(
        'manuscript_entries',
        sa.Column('summary', sa.Text(), nullable=True)
    )

    # Create motifs table
    op.create_table(
        'motifs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.CheckConstraint("name != ''", name='ck_motif_non_empty_name'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_motifs_name', 'motifs', ['name'], unique=True)

    # Create entry_motifs association table
    op.create_table(
        'entry_motifs',
        sa.Column('entry_id', sa.Integer(), nullable=False),
        sa.Column('motif_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ['entry_id'], ['manuscript_entries.id'],
            ondelete='CASCADE'
        ),
        sa.ForeignKeyConstraint(
            ['motif_id'], ['motifs.id']
        ),
        sa.PrimaryKeyConstraint('entry_id', 'motif_id')
    )


def downgrade() -> None:
    """
    Remove narrative analysis schema.
    """
    # Drop entry_motifs
    op.drop_table('entry_motifs')

    # Drop motifs
    op.drop_index('ix_motifs_name', table_name='motifs')
    op.drop_table('motifs')

    # Remove summary, rating_justification, and narrative_rating from manuscript_entries
    op.drop_column('manuscript_entries', 'summary')
    op.drop_column('manuscript_entries', 'rating_justification')
    op.drop_index('ix_manuscript_entries_narrative_rating', table_name='manuscript_entries')
    op.drop_constraint('ck_manuscript_entries_rating_range', 'manuscript_entries', type_='check')
    op.drop_column('manuscript_entries', 'narrative_rating')

    # Remove category_id from tags
    op.drop_constraint('fk_tags_category_id', 'tags', type_='foreignkey')
    op.drop_column('tags', 'category_id')

    # Drop tag_categories
    op.drop_index('ix_tag_categories_name', table_name='tag_categories')
    op.drop_table('tag_categories')
