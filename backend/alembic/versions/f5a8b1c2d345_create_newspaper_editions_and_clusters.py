"""create_newspaper_editions_and_clusters

Revision ID: f5a8b1c2d345
Revises: e4f7a9b2c345
Create Date: 2026-10-05 15:00:00.000000

Phase 9 — Intelligent Personal Newspaper Generator
Creates newspaper_editions, newspaper_stories, story_clusters, and story_cluster_articles tables.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'f5a8b1c2d345'
down_revision: Union[str, Sequence[str], None] = 'e4f7a9b2c345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create newspaper_editions table
    op.create_table(
        'newspaper_editions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'user_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('users.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('edition_date', sa.String(length=10), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, server_default='YOUR DAILY'),
        sa.Column('subtitle', sa.String(length=500), nullable=True),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='READY'),
        sa.Column('generated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('user_id', 'edition_date', name='uq_user_edition_date'),
    )
    op.create_index('ix_newspaper_editions_user_id', 'newspaper_editions', ['user_id'])
    op.create_index('ix_newspaper_editions_edition_date', 'newspaper_editions', ['edition_date'])
    op.create_index('ix_newspaper_editions_status', 'newspaper_editions', ['status'])

    # 2. Create newspaper_stories table
    op.create_table(
        'newspaper_stories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            'edition_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('newspaper_editions.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column(
            'article_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('articles.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('section', sa.String(length=100), nullable=False, server_default='TOP STORIES'),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('layout_type', sa.String(length=30), nullable=False, server_default='STANDARD'),
        sa.Column('editorial_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('is_lead', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('personalization_reason', sa.String(length=255), nullable=True),
        sa.Column('display_headline', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_newspaper_stories_edition_id', 'newspaper_stories', ['edition_id'])
    op.create_index('ix_newspaper_stories_article_id', 'newspaper_stories', ['article_id'])
    op.create_index('ix_newspaper_stories_section', 'newspaper_stories', ['section'])

    # 3. Create story_clusters table
    op.create_table(
        'story_clusters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cluster_key', sa.String(length=255), unique=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_story_clusters_cluster_key', 'story_clusters', ['cluster_key'])

    # 4. Create story_cluster_articles table
    op.create_table(
        'story_cluster_articles',
        sa.Column(
            'cluster_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('story_clusters.id', ondelete='CASCADE'),
            primary_key=True,
        ),
        sa.Column(
            'article_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('articles.id', ondelete='CASCADE'),
            primary_key=True,
        ),
        sa.Column('similarity_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='false'),
    )


def downgrade() -> None:
    op.drop_table('story_cluster_articles')
    op.drop_table('story_clusters')
    op.drop_table('newspaper_stories')
    op.drop_table('newspaper_editions')
