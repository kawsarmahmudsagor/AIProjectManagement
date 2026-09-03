"""add breakdown_jobs table

Revision ID: 9a2f6c1d8e4b
Revises: 7c1e9a4f2b3d
Create Date: 2026-09-02 00:00:00.000002

Reuses the existing `job_status` Postgres TYPE (created by b3c3697fd5fe, extended by
9edcb5514180) rather than declaring a new enum — same stage names, same cancel semantics,
same stale-job reaper as extraction_jobs. Must reference it with create_type=False, or
`alembic upgrade` fails with "type job_status already exists".

accepted_refs/dismissed_refs default to '{}'::json / '[]'::json — see
app/models/breakdown_job.py's docstring for why accepted_refs is a dict (ref -> created
Task id), not a plain list of refs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '9a2f6c1d8e4b'
down_revision: Union[str, None] = '7c1e9a4f2b3d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_status = postgresql.ENUM(
        'QUEUED', 'PARSING', 'EXTRACTING', 'STRUCTURING', 'SUCCEEDED', 'FAILED', 'CANCELLED',
        name='job_status', create_type=False,
    )
    provider_name = postgresql.ENUM('GEMINI', 'OPENAI', name='provider_name', create_type=False)

    op.create_table(
        'breakdown_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', provider_name, nullable=False),
        sa.Column('status', job_status, nullable=False, server_default='QUEUED'),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('max_tasks', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('is_scanned', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('accepted_refs', sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column('dismissed_refs', sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='SET NULL'),
    )
    op.create_index('ix_breakdown_jobs_user_id', 'breakdown_jobs', ['user_id'])
    op.create_index('ix_breakdown_jobs_project_id', 'breakdown_jobs', ['project_id'])
    op.create_index('ix_breakdown_jobs_status', 'breakdown_jobs', ['status'])


def downgrade() -> None:
    op.drop_index('ix_breakdown_jobs_status', table_name='breakdown_jobs')
    op.drop_index('ix_breakdown_jobs_project_id', table_name='breakdown_jobs')
    op.drop_index('ix_breakdown_jobs_user_id', table_name='breakdown_jobs')
    op.drop_table('breakdown_jobs')
