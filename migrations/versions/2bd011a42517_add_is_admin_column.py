"""add_is_admin_column

Revision ID: 2bd011a42517
Revises: 721e82f0c5ec
Create Date: 2025-05-02 07:36:44.017116

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2bd011a42517'
down_revision: Union[str, None] = '721e82f0c5ec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_admin column to users table."""
    op.add_column('users', sa.Column('is_admin', sa.Boolean(), nullable=True, server_default='0'))


def downgrade() -> None:
    """Remove is_admin column from users table."""
    op.drop_column('users', 'is_admin')
