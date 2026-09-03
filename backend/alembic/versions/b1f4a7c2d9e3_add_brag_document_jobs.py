"""add brag_document_jobs table

Revision ID: b1f4a7c2d9e3
Revises: 9a2f6c1d8e4b
Create Date: 2026-09-03 00:00:00.000000

Reuses the existing `job_status` and `provider_name` Postgres TYPEs (create_type=False),
same reasoning as 9a2f6c1d8e4b_add_breakdown_jobs.py — same stage names, same cancel
semantics, same stale-job reaper as extraction_jobs/breakdown_jobs.

`result`/`hour_stats` are separate JSON columns (see app/models/brag_document_job.py's
docstring for why): `result` holds only the LLM-authored prose, `hour_stats` holds the
deterministic arithmetic — this table has no `accepted_refs`/`dismissed_refs` columns
because, unlike BreakdownJob, a brag document job has no per-item accept/dismiss flow.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'b1f4a7c2d9e3'
down_revision: Union[str, None] = '9a2f6c1d8e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_status = postgresql.ENUM(
        'QUEUED', 'PARSING', 'EXTRACTING', 'STRUCTURING', 'SUCCEEDED', 'FAILED', 'CANCELLED',
        name='job_status', create_type=False,
    )
    provider_name = postgresql.ENUM('GEMINI', 'OPENAI', name='provider_name', create_type=False)

    op.create_table(
        'brag_document_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', provider_name, nullable=False),
        sa.Column('status', job_status, nullable=False, server_default='QUEUED'),
        sa.Column('member_name', sa.String(length=200), nullable=False),
        sa.Column('target_month', sa.String(length=20), nullable=False),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('hour_stats', sa.JSON(), nullable=True),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_brag_document_jobs_user_id', 'brag_document_jobs', ['user_id'])
    op.create_index('ix_brag_document_jobs_status', 'brag_document_jobs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_brag_document_jobs_status', table_name='brag_document_jobs')
    op.drop_index('ix_brag_document_jobs_user_id', table_name='brag_document_jobs')
    op.drop_table('brag_document_jobs')
