"""add practical release schedule

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("practical_exercises", sa.Column("release_key", sa.String(length=40), nullable=True))
    op.add_column("practical_exercises", sa.Column("release_at", sa.DateTime(), nullable=True))
    op.add_column("practical_exercises", sa.Column("expires_at", sa.DateTime(), nullable=True))
    op.add_column("practical_exercises", sa.Column("source", sa.String(length=80), nullable=True))
    op.create_index(op.f("ix_practical_exercises_release_key"), "practical_exercises", ["release_key"], unique=False)
    op.create_index(
        "ix_practical_exercises_release_unique",
        "practical_exercises",
        ["course_id", "release_key", "practical_type", "title"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_practical_exercises_release_unique", table_name="practical_exercises")
    op.drop_index(op.f("ix_practical_exercises_release_key"), table_name="practical_exercises")
    op.drop_column("practical_exercises", "source")
    op.drop_column("practical_exercises", "expires_at")
    op.drop_column("practical_exercises", "release_at")
    op.drop_column("practical_exercises", "release_key")
