"""add_evaluation_metadata_and_marking_scheme

Revision ID: a6e60b2d35c1
Revises: f5d63f918e9a
Create Date: 2026-06-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6e60b2d35c1'
down_revision: Union[str, Sequence[str], None] = 'f5d63f918e9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add marking_scheme column to questions table
    op.add_column('questions', sa.Column('marking_scheme', sa.JSON(), nullable=True))
    # Add evaluation_metadata column to answers table
    op.add_column('answers', sa.Column('evaluation_metadata', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('answers', 'evaluation_metadata')
    op.drop_column('questions', 'marking_scheme')
