"""add user security fields and password reset tokens

Revision ID: a4836f53c238
Revises: c2d3e4f5a6b7
Create Date: 2026-06-22 21:00:21.130069

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4836f53c238'
down_revision: Union[str, Sequence[str], None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('password_reset_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=8), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_password_reset_tokens_code'), 'password_reset_tokens', ['code'], unique=False)
    op.create_index(op.f('ix_password_reset_tokens_id'), 'password_reset_tokens', ['id'], unique=False)
    op.add_column('users', sa.Column('security_question', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('security_answer_hash', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'security_answer_hash')
    op.drop_column('users', 'security_question')
    op.drop_index(op.f('ix_password_reset_tokens_id'), table_name='password_reset_tokens')
    op.drop_index(op.f('ix_password_reset_tokens_code'), table_name='password_reset_tokens')
    op.drop_table('password_reset_tokens')
