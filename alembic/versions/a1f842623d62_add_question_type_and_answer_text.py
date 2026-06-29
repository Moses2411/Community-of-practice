"""add question_type and answer_text for theory questions

Revision ID: a1f842623d62
Revises: a4836f53c238
Create Date: 2026-06-29 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1f842623d62'
down_revision: Union[str, Sequence[str], None] = 'a4836f53c238'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.add_column(sa.Column("question_type", sa.String(10), nullable=False, server_default="mcq"))
        batch_op.alter_column("correct_option", existing_type=sa.String(1), nullable=True)

    with op.batch_alter_table("quiz_answers") as batch_op:
        batch_op.add_column(sa.Column("answer_text", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("quiz_answers") as batch_op:
        batch_op.drop_column("answer_text")

    with op.batch_alter_table("quiz_questions") as batch_op:
        batch_op.drop_column("question_type")
        batch_op.alter_column("correct_option", existing_type=sa.String(1), nullable=False)
