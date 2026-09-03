"""add name column to brag_document_jobs

Revision ID: e2d6b8a1c4f7
Revises: b1f4a7c2d9e3
Create Date: 2026-09-10 00:00:00.000000

Backfills existing rows with the same f"{target_month} Brag Document" default the
application uses for new rows (routers/brag_documents.py, agents/chat_tools.py), then
tightens the column to NOT NULL — no server_default kept afterward, since every creation
path always sets this explicitly in Python (see app/models/brag_document_job.py's
docstring on the `name` column).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e2d6b8a1c4f7'
down_revision: Union[str, None] = 'b1f4a7c2d9e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('brag_document_jobs', sa.Column('name', sa.String(length=255), nullable=True))
    op.execute("UPDATE brag_document_jobs SET name = target_month || ' Brag Document' WHERE name IS NULL")
    op.alter_column('brag_document_jobs', 'name', nullable=False)


def downgrade() -> None:
    op.drop_column('brag_document_jobs', 'name')
