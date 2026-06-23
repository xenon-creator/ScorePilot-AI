"""add new grading fields

Revision ID: b7f71c3e46d2
Revises: a6e60b2d35c1
Create Date: 2026-06-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7f71c3e46d2'
down_revision: Union[str, Sequence[str], None] = 'a6e60b2d35c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Check constraint check
    op.add_column('submissions', sa.Column('point_scores', sa.JSON(), nullable=True))
    op.add_column('submissions', sa.Column('holistic_adjustment', sa.Float(), nullable=True, server_default='0'))
    op.add_column('submissions', sa.Column('match_details', sa.JSON(), nullable=True))
    op.add_column('submissions', sa.Column('confidence_score', sa.Integer(), nullable=True, server_default='70'))
    
    # Add check constraint for confidence_score
    op.create_check_constraint(
        'ck_submissions_confidence_score',
        'submissions',
        'confidence_score >= 0 AND confidence_score <= 100'
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('ck_submissions_confidence_score', 'submissions', type_='check')
    op.drop_column('submissions', 'confidence_score')
    op.drop_column('submissions', 'match_details')
    op.drop_column('submissions', 'holistic_adjustment')
    op.drop_column('submissions', 'point_scores')
