"""create_user_interest_embeddings

Revision ID: d3e6f8a1b234
Revises: c2d5e7f8a913
Create Date: 2026-10-05 13:00:00.000000

Phase 8 — Personal Relevance Scoring & Multi-Factor Personalization
Creates user_interest_embeddings table to persist user semantic profile embeddings.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'd3e6f8a1b234'
down_revision: Union[str, Sequence[str], None] = 'c2d5e7f8a913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'user_interest_embeddings',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('embedding', postgresql.JSON(), nullable=False),
        sa.Column('embedding_model', sa.String(length=100), nullable=False),
        sa.Column('embedding_version', sa.String(length=20), nullable=False, server_default='v1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'embedding_version', name='uq_user_interest_embedding_version'),
    )
    op.create_index(
        'ix_user_interest_embeddings_user_id',
        'user_interest_embeddings',
        ['user_id'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('ix_user_interest_embeddings_user_id', table_name='user_interest_embeddings')
    op.drop_table('user_interest_embeddings')
