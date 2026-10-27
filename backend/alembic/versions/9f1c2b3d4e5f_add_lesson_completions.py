"""Add lesson completion tracking for certification eligibility

Revision ID: 9f1c2b3d4e5f
Revises: 4bf3169488a5
Create Date: 2026-10-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9f1c2b3d4e5f'
down_revision: Union[str, Sequence[str], None] = '4bf3169488a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'lesson_completions',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('lesson_id', sa.UUID(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['lesson_id'], ['lessons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'lesson_id', name='uq_lesson_completion_user_lesson'),
    )
    op.create_index(op.f('ix_lesson_completions_id'), 'lesson_completions', ['id'], unique=False)
    op.create_index(op.f('ix_lesson_completions_user_id'), 'lesson_completions', ['user_id'], unique=False)
    op.create_index(op.f('ix_lesson_completions_lesson_id'), 'lesson_completions', ['lesson_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_lesson_completions_lesson_id'), table_name='lesson_completions')
    op.drop_index(op.f('ix_lesson_completions_user_id'), table_name='lesson_completions')
    op.drop_index(op.f('ix_lesson_completions_id'), table_name='lesson_completions')
    op.drop_table('lesson_completions')
