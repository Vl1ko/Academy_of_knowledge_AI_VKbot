"""add preferred contact time to consultation requests

Revision ID: 6b7c7ba5f95c
Revises: 2bd011a42517
Create Date: 2024-03-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6b7c7ba5f95c'
down_revision: Union[str, None] = '2bd011a42517'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add preferred_contact_time column to consultation_requests table
    op.add_column('consultation_requests',
        sa.Column('preferred_contact_time', sa.String(), nullable=True)
    )


def downgrade() -> None:
    # Remove preferred_contact_time column from consultation_requests table
    op.drop_column('consultation_requests', 'preferred_contact_time')
