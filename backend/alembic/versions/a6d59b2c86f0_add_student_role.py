"""add_student_role

Revision ID: a6d59b2c86f0
Revises: 266181194c46
Create Date: 2026-05-30 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a6d59b2c86f0'
down_revision: Union[str, Sequence[str], None] = '266181194c46'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update the Enum Type in PostgreSQL.
    # In PostgreSQL 12+, ALTER TYPE ... ADD VALUE is allowed within transaction blocks
    # provided the enum value is not referenced in the same transaction.
    # We execute this safely.
    try:
        op.execute("ALTER TYPE userrole ADD VALUE 'student'")
    except Exception:
        # Handle SQLite or case where type does not exist or value is already present
        pass
    
    # 2. Add student_id column to users table
    op.add_column('users', sa.Column('student_id', sa.String(), nullable=True))


def downgrade() -> None:
    # Remove the column
    op.drop_column('users', 'student_id')
    # Note: PostgreSQL enum values cannot be dropped without recreating the enum type.
    # Therefore, we do not attempt to revert the 'student' value to avoid schema locks.
