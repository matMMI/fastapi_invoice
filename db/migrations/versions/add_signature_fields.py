"""Add signature fields to quote

Revision ID: add_signature_fields
Revises: a7920be705d8
Create Date: 2024-12-23 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_signature_fields'
down_revision: Union[str, None] = '57b41b91be2d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add share token fields
    op.add_column('quote', sa.Column('share_token', sa.String(100), nullable=True))
    op.add_column('quote', sa.Column('share_token_expires_at', sa.DateTime(timezone=True), nullable=True))
    
    # Add electronic signature fields
    op.add_column('quote', sa.Column('signed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('quote', sa.Column('signature_data', sa.Text(), nullable=True))
    op.add_column('quote', sa.Column('signer_name', sa.String(200), nullable=True))
    op.add_column('quote', sa.Column('signer_ip', sa.String(50), nullable=True))
    
    # Create unique index on share_token
    op.create_index('ix_quote_share_token', 'quote', ['share_token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_quote_share_token', table_name='quote')
    op.drop_column('quote', 'signer_ip')
    op.drop_column('quote', 'signer_name')
    op.drop_column('quote', 'signature_data')
    op.drop_column('quote', 'signed_at')
    op.drop_column('quote', 'share_token_expires_at')
    op.drop_column('quote', 'share_token')
