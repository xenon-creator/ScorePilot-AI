"""add ocr fields to submissions

Revision ID: 09d8419b4c2e
Revises: b7f71c3e46d2
Create Date: 2026-06-23 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '09d8419b4c2e'
down_revision: Union[str, Sequence[str], None] = 'b7f71c3e46d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('submissions', sa.Column('cleaned_text', sa.Text(), nullable=True))
    op.add_column('submissions', sa.Column('ocr_engine', sa.String(), nullable=True))
    op.add_column('submissions', sa.Column('ocr_confidence', sa.Float(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('submissions', 'ocr_confidence')
    op.drop_column('submissions', 'ocr_engine')
    op.drop_column('submissions', 'cleaned_text')
