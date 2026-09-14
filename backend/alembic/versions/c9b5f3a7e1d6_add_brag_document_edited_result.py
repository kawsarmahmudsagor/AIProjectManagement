"""add edited_result column to brag_document_jobs

Revision ID: c9b5f3a7e1d6
Revises: a3f7c1e9b2d4
Create Date: 2026-09-08 00:00:00.000000

Nullable JSON, same shape as `result` (schemas.brag_document.LLMBragDocumentResult) —
holds the user's manually-edited version once they've saved at least one change via
PATCH /brag-document-jobs/{id}, so the original LLM draft in `result` never gets
overwritten and "reset changes" (POST .../reset) is just clearing this column back to
NULL. See models/brag_document_job.py's docstring on the column and its
`effective_result` property.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9b5f3a7e1d6'
down_revision: Union[str, None] = 'a3f7c1e9b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('brag_document_jobs', sa.Column('edited_result', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('brag_document_jobs', 'edited_result')
