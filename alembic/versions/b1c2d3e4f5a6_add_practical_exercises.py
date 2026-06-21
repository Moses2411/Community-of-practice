"""add practical exercises and attempts

Revision ID: b1c2d3e4f5a6
Revises: a671dffdc4ff
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "a671dffdc4ff"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "practical_exercises",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("practical_type", sa.String(length=40), nullable=False),
        sa.Column("difficulty", sa.String(length=40), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("starter_code", sa.Text(), nullable=True),
        sa.Column("expected_output", sa.Text(), nullable=True),
        sa.Column("solution_notes", sa.Text(), nullable=True),
        sa.Column("checks_json", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["course_id"], ["courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_practical_exercises_id"), "practical_exercises", ["id"], unique=False)

    op.create_table(
        "practical_attempts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("submitted_code", sa.Text(), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("total_points", sa.Float(), nullable=True),
        sa.Column("feedback_json", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["practical_exercises.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_practical_attempts_id"), "practical_attempts", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_practical_attempts_id"), table_name="practical_attempts")
    op.drop_table("practical_attempts")
    op.drop_index(op.f("ix_practical_exercises_id"), table_name="practical_exercises")
    op.drop_table("practical_exercises")
