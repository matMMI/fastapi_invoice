"""Update quote status enum

Revision ID: update_quote_status_enum
Revises: add_signature_fields
Create Date: 2024-12-23 23:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'update_quote_status_enum'
down_revision: Union[str, None] = 'add_signature_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Postgres requires running ALTER TYPE outside of a transaction block
    # or ensuring it can handle it. ADD VALUE usually requires it.
    # However, if we are inside a transaction, we can't do it easily without autocommit.
    # But SqlAlchemy/Alembic usually handles this if we use correct syntax.
    # Safe way:
    op.execute("ALTER TYPE quotestatus ADD VALUE IF NOT EXISTS 'SIGNED'")


def downgrade() -> None:
    # Cannot remove value from ENUM in Postgres without dropping/recreating type
    pass
