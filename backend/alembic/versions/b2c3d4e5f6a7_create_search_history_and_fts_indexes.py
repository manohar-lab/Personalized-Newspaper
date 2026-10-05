"""create_search_history_and_fts_indexes

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-10-05 15:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create user_search_history table
    op.create_table(
        'user_search_history',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('query', sa.String(length=255), nullable=False),
        sa.Column('filters', sa.Text(), nullable=True),
        sa.Column('result_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_search_history_user_id'), 'user_search_history', ['user_id'], unique=False)
    op.create_index(op.f('ix_user_search_history_query'), 'user_search_history', ['query'], unique=False)
    op.create_index(op.f('ix_user_search_history_created_at'), 'user_search_history', ['created_at'], unique=False)

    # 2. Create PostgreSQL Full-Text Search GIN Index on Articles (title, description, content)
    # Using raw SQL with coalesce to support efficient tsvector queries
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_articles_fts_gin ON articles
        USING gin(to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || coalesce(content, '')));
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_articles_fts_gin;")
    op.drop_index(op.f('ix_user_search_history_created_at'), table_name='user_search_history')
    op.drop_index(op.f('ix_user_search_history_query'), table_name='user_search_history')
    op.drop_index(op.f('ix_user_search_history_user_id'), table_name='user_search_history')
    op.drop_table('user_search_history')
