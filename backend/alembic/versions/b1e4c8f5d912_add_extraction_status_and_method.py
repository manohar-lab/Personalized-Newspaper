"""add_extraction_fields_to_articles

Revision ID: b1e4c8f5d912
Revises: a7c2e9f4d823
Create Date: 2026-10-05 11:30:00.000000

Phase 5 — Web Article Extraction & Scraping
Adds extraction_status, extracted_at, extraction_error, extraction_method columns to articles.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1e4c8f5d912'
down_revision: Union[str, Sequence[str], None] = 'a7c2e9f4d823'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 5 extraction fields to articles table."""
    op.add_column(
        'articles',
        sa.Column('extraction_status', sa.String(length=30), nullable=True, server_default='NOT_ATTEMPTED'),
    )
    op.create_index(
        op.f('ix_articles_extraction_status'),
        'articles',
        ['extraction_status'],
        unique=False,
    )

    op.add_column(
        'articles',
        sa.Column('extracted_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.add_column(
        'articles',
        sa.Column('extraction_error', sa.Text(), nullable=True),
    )

    op.add_column(
        'articles',
        sa.Column('extraction_method', sa.String(length=30), nullable=True),
    )


def downgrade() -> None:
    """Remove Phase 5 extraction fields from articles table."""
    op.drop_index(op.f('ix_articles_extraction_status'), table_name='articles')
    op.drop_column('articles', 'extraction_method')
    op.drop_column('articles', 'extraction_error')
    op.drop_column('articles', 'extracted_at')
    op.drop_column('articles', 'extraction_status')
