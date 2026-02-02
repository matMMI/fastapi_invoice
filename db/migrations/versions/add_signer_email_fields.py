"""add signer_email and signer_function fields

Revision ID: a1b2c3d4e5f6
Revises: eb5e685c0191
Create Date: 2026-02-02 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'eb5e685c0191'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('quote', sa.Column('signer_email', sa.String(255), nullable=True))
    op.add_column('quote', sa.Column('signer_function', sa.String(200), nullable=True))


def downgrade() -> None:
    op.drop_column('quote', 'signer_function')
    op.drop_column('quote', 'signer_email')
