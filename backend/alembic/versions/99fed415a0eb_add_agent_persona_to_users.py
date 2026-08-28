"""add agent_persona to users

Revision ID: 99fed415a0eb
Revises: 9edcb5514180
Create Date: 2026-08-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '99fed415a0eb'
down_revision: Union[str, None] = '9edcb5514180'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    agent_persona = sa.Enum('BUSINESS_ANALYST', 'TECHNICAL_DEVELOPER', name='agent_persona')
    agent_persona.create(op.get_bind())
    op.add_column(
        'users',
        sa.Column(
            'agent_persona',
            agent_persona,
            nullable=False,
            server_default='BUSINESS_ANALYST',
        ),
    )


def downgrade() -> None:
    op.drop_column('users', 'agent_persona')
    sa.Enum(name='agent_persona').drop(op.get_bind())
