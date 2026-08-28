"""add cancelled job status

Revision ID: 9edcb5514180
Revises: b3c3697fd5fe
Create Date: 2026-08-27 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '9edcb5514180'
down_revision: Union[str, None] = 'b3c3697fd5fe'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE can't run inside the transaction Alembic normally wraps
    # migrations in (Postgres forbids using a new enum value in the same transaction that
    # added it, and older versions reject the ADD VALUE itself) — autocommit_block()
    # runs this statement on its own.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE job_status ADD VALUE IF NOT EXISTS 'CANCELLED'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE — removing an enum value requires
    # rebuilding the type, which isn't worth it for a down-migration nobody runs against
    # data that may already reference 'CANCELLED'.
    pass
