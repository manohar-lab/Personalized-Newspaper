"""create_article_analysis_entities_and_keywords

Revision ID: c2d5e7f8a913
Revises: b1e4c8f5d912
Create Date: 2026-10-05 12:00:00.000000

Phase 7 — AI Article Understanding & Classification
Creates article_analysis, entities, article_entities, article_keywords tables,
and adds confidence column to article_topics table.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c2d5e7f8a913'
down_revision: Union[str, Sequence[str], None] = 'b1e4c8f5d912'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add confidence column to article_topics junction table
    op.add_column(
        'article_topics',
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
    )

    # 2. Create entities table
    op.create_table(
        'entities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('normalized_name', sa.String(length=255), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False, server_default='OTHER'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(op.f('ix_entities_normalized_name'), 'entities', ['normalized_name'], unique=True)
    op.create_index(op.f('ix_entities_entity_type'), 'entities', ['entity_type'], unique=False)

    # 3. Create article_entities junction table
    op.create_table(
        'article_entities',
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('entity_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('entities.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
    )
    op.create_index(op.f('ix_article_entities_article_id'), 'article_entities', ['article_id'], unique=False)
    op.create_index(op.f('ix_article_entities_entity_id'), 'article_entities', ['entity_id'], unique=False)

    # 4. Create article_keywords table
    op.create_table(
        'article_keywords',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('keyword', sa.String(length=100), nullable=False),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(op.f('ix_article_keywords_article_id'), 'article_keywords', ['article_id'], unique=False)
    op.create_index(op.f('ix_article_keywords_keyword'), 'article_keywords', ['keyword'], unique=False)

    # 5. Create article_analysis table
    op.create_table(
        'article_analysis',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('article_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('articles.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('primary_category', sa.String(length=50), nullable=True),
        sa.Column('article_type', sa.String(length=50), nullable=True),
        sa.Column('importance_score', sa.Float(), nullable=False, server_default='0.5'),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('analysis_version', sa.String(length=20), nullable=False, server_default='v1'),
        sa.Column('analysis_status', sa.String(length=30), nullable=False, server_default='NOT_ANALYZED'),
        sa.Column('analysis_error', sa.Text(), nullable=True),
        sa.Column('analysis_attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('analyzed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('embedding', sa.JSON(), nullable=True),
        sa.Column('embedding_model', sa.String(length=100), nullable=True),
        sa.Column('embedding_version', sa.String(length=20), nullable=True),
        sa.Column('embedded_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index(op.f('ix_article_analysis_article_id'), 'article_analysis', ['article_id'], unique=True)
    op.create_index(op.f('ix_article_analysis_primary_category'), 'article_analysis', ['primary_category'], unique=False)
    op.create_index(op.f('ix_article_analysis_analysis_status'), 'article_analysis', ['analysis_status'], unique=False)


def downgrade() -> None:
    op.drop_table('article_analysis')
    op.drop_table('article_keywords')
    op.drop_table('article_entities')
    op.drop_table('entities')
    op.drop_column('article_topics', 'confidence')
