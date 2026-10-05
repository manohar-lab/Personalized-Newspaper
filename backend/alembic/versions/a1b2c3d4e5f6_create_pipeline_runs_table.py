"""create_pipeline_runs_table

Revision ID: a1b2c3d4e5f6
Revises: f5a8b1c2d345
Create Date: 2026-10-05 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'f5a8b1c2d345'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('items_processed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_succeeded', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('items_failed', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pipeline_runs_job_type'), 'pipeline_runs', ['job_type'], unique=False)
    op.create_index(op.f('ix_pipeline_runs_status'), 'pipeline_runs', ['status'], unique=False)
    op.create_index(op.f('ix_pipeline_runs_started_at'), 'pipeline_runs', ['started_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pipeline_runs_started_at'), table_name='pipeline_runs')
    op.drop_index(op.f('ix_pipeline_runs_status'), table_name='pipeline_runs')
    op.drop_index(op.f('ix_pipeline_runs_job_type'), table_name='pipeline_runs')
    op.drop_table('pipeline_runs')
