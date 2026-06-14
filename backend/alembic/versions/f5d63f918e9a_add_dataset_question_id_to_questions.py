"""add_dataset_question_id_to_questions

Revision ID: f5d63f918e9a
Revises: e4d8b0325704
Create Date: 2026-06-14 13:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5d63f918e9a'
down_revision: Union[str, Sequence[str], None] = 'e4d8b0325704'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('questions', sa.Column('dataset_question_id', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('questions', 'dataset_question_id')
