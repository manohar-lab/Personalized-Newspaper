"""add_scraping_fields_to_articles

Revision ID: a7c2e9f4d823
Revises: 3e1fb3b9558e
Create Date: 2026-10-05 11:00:00.000000

Phase 5 — Web Article Extraction & Scraping
Adds scrape_status, scraped_at, and scrape_error tracking columns to articles.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c2e9f4d823'
down_revision: Union[str, Sequence[str], None] = '3e1fb3b9558e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add Phase 5 scraping tracking fields to articles table."""
    # scrape_status: tracks the state of web scraping for this article
    # Values: PENDING | SUCCESS | FAILED | ROBOTS_BLOCKED | VALIDATION_FAILED | SKIPPED
    op.add_column(
        'articles',
        sa.Column('scrape_status', sa.String(length=30), nullable=True),
    )
    op.create_index(
        op.f('ix_articles_scrape_status'),
        'articles',
        ['scrape_status'],
        unique=False,
    )

    # scraped_at: timestamp of the last scrape attempt (success or failure)
    op.add_column(
        'articles',
        sa.Column('scraped_at', sa.DateTime(timezone=True), nullable=True),
    )

    # scrape_error: last error message from scraping (null on success)
    op.add_column(
        'articles',
        sa.Column('scrape_error', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    """Remove Phase 5 scraping tracking fields from articles table."""
    op.drop_index(op.f('ix_articles_scrape_status'), table_name='articles')
    op.drop_column('articles', 'scrape_error')
    op.drop_column('articles', 'scraped_at')
    op.drop_column('articles', 'scrape_status')
