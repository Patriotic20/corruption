"""drop admin invite expiry

Revision ID: eddca6b4394e
Revises: 2acd8493aa51
Create Date: 2026-09-04 14:23:47.332129

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eddca6b4394e'
down_revision: Union[str, Sequence[str], None] = '2acd8493aa51'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('admin_invites', 'expires_at')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'admin_invites',
        sa.Column('expires_at', sa.DateTime(), nullable=True),
    )
    # existing invites had no deadline — give them one so the column can go NOT NULL again
    op.execute("UPDATE admin_invites SET expires_at = now() + interval '7 days'")
    op.alter_column('admin_invites', 'expires_at', nullable=False)
