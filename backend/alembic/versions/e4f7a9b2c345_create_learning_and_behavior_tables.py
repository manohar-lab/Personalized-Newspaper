"""create_learning_and_behavior_tables

Revision ID: e4f7a9b2c345
Revises: d3e6f8a1b234
Create Date: 2026-10-05 14:00:00.000000

Phase 8 — Automatic User Interest Learning Agent
Creates user_behavior_events, reading_sessions, user_entity_interests, user_keyword_interests,
and adds confidence column to user_interests.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e4f7a9b2c345'
down_revision: Union[str, Sequence[str], None] = 'd3e6f8a1b234'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add confidence column to user_interests
    op.add_column(
        'user_interests',
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
    )

    # 2. Create user_behavior_events table
    op.create_table(
        'user_behavior_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'article_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('articles.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('value', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('event_metadata', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_user_behavior_events_user_id', 'user_behavior_events', ['user_id'])
    op.create_index('ix_user_behavior_events_article_id', 'user_behavior_events', ['article_id'])
    op.create_index('ix_user_behavior_events_event_type', 'user_behavior_events', ['event_type'])
    op.create_index('ix_user_behavior_events_created_at', 'user_behavior_events', ['created_at'])

    # 3. Create reading_sessions table
    op.create_table(
        'reading_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'article_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('articles.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Float(), nullable=True),
        sa.Column('completion_percentage', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_reading_sessions_user_id', 'reading_sessions', ['user_id'])
    op.create_index('ix_reading_sessions_article_id', 'reading_sessions', ['article_id'])

    # 4. Create user_entity_interests table
    op.create_table(
        'user_entity_interests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'entity_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('entities.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.1'),
        sa.Column('interaction_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positive_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('negative_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'entity_id', name='uq_user_entity'),
    )
    op.create_index('ix_user_entity_interests_user_id', 'user_entity_interests', ['user_id'])
    op.create_index('ix_user_entity_interests_entity_id', 'user_entity_interests', ['entity_id'])

    # 5. Create user_keyword_interests table
    op.create_table(
        'user_keyword_interests',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('keyword', sa.String(length=100), nullable=False),
        sa.Column('score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='0.1'),
        sa.Column('interaction_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positive_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('negative_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'keyword', name='uq_user_keyword'),
    )
    op.create_index('ix_user_keyword_interests_user_id', 'user_keyword_interests', ['user_id'])
    op.create_index('ix_user_keyword_interests_keyword', 'user_keyword_interests', ['keyword'])


def downgrade() -> None:
    op.drop_table('user_keyword_interests')
    op.drop_table('user_entity_interests')
    op.drop_table('reading_sessions')
    op.drop_table('user_behavior_events')
    op.drop_column('user_interests', 'confidence')
