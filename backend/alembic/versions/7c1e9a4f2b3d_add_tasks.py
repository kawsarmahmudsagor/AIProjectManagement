"""add tasks table

Revision ID: 7c1e9a4f2b3d
Revises: 46f852e48df7
Create Date: 2026-09-02 00:00:00.000001

Tasks use a fixed Postgres enum for status/priority/source rather than a per-project
configurable status list — see backend/app/models/task.py's docstring and
backend/DESIGN.md §2 for the rationale. Extending the enum later (e.g. adding
IN_REVIEW) is the same five-line ALTER TYPE ... ADD VALUE pattern as
9edcb5514180_add_cancelled_job_status.py.

uq_projects_id_user_id makes a cross-tenant task-parent attachment structurally
unrepresentable at the DB level: tasks.(project_id, user_id) has a composite FK into
projects(id, user_id), so a task can never be inserted against a project it doesn't
actually belong to under that user.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '7c1e9a4f2b3d'
down_revision: Union[str, None] = '46f852e48df7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_unique_constraint('uq_projects_id_user_id', 'projects', ['id', 'user_id'])

    task_status = sa.Enum('TODO', 'IN_PROGRESS', 'BLOCKED', 'DONE', name='task_status')
    task_priority = sa.Enum('LOW', 'MEDIUM', 'HIGH', 'URGENT', name='task_priority')
    task_source = sa.Enum('MANUAL', 'AI', name='task_source')

    op.create_table(
        'tasks',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            onupdate=sa.text('now()'),
            nullable=False,
        ),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('status', task_status, nullable=False, server_default='TODO'),
        sa.Column('priority', task_priority, nullable=False, server_default='MEDIUM'),
        sa.Column('source', task_source, nullable=False, server_default='MANUAL'),
        sa.Column('estimate_minutes', sa.Integer(), nullable=True),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_id'], ['tasks.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(
            ['project_id', 'user_id'],
            ['projects.id', 'projects.user_id'],
            ondelete='CASCADE',
            name='fk_tasks_project_user',
        ),
    )
    op.create_index('ix_tasks_user_id', 'tasks', ['user_id'])
    op.create_index('ix_tasks_project_id', 'tasks', ['project_id'])
    op.create_index('ix_tasks_parent_id', 'tasks', ['parent_id'])
    op.create_index(
        'ix_tasks_project_status_position', 'tasks', ['project_id', 'status', 'position']
    )
    op.create_index('ix_tasks_user_due_date', 'tasks', ['user_id', 'due_date'])


def downgrade() -> None:
    op.drop_index('ix_tasks_user_due_date', table_name='tasks')
    op.drop_index('ix_tasks_project_status_position', table_name='tasks')
    op.drop_index('ix_tasks_parent_id', table_name='tasks')
    op.drop_index('ix_tasks_project_id', table_name='tasks')
    op.drop_index('ix_tasks_user_id', table_name='tasks')
    op.drop_table('tasks')

    sa.Enum(name='task_source').drop(op.get_bind())
    sa.Enum(name='task_priority').drop(op.get_bind())
    sa.Enum(name='task_status').drop(op.get_bind())

    op.drop_constraint('uq_projects_id_user_id', 'projects', type_='unique')
