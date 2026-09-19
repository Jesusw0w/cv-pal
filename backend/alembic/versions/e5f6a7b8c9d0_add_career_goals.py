"""add career goals

What the user is looking for, as opposed to what they have already done. Kept in its own
table rather than on the career profile because the two change for different reasons: the
profile changes when the user's history does, goals when they change their mind.

Each preference carries a flag saying whether it filters or merely scores. That pairing
is the point of the table — a non-negotiable that is really a preference returns nothing,
and a preference treated as a filter hides work the user would have taken.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the career goals table."""
    op.create_table(
        "career_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        # JSON on both SQLite and PostgreSQL. Nothing queries across users by these, so
        # a child table would buy indexing nobody needs and cost two more joins.
        sa.Column("target_roles", sa.JSON(), nullable=False),
        sa.Column("work_regimes", sa.JSON(), nullable=False),
        sa.Column("regime_non_negotiable", sa.Boolean(), nullable=False),
        sa.Column("min_salary", sa.Integer(), nullable=True),
        sa.Column("salary_currency", sa.String(length=3), nullable=True),
        sa.Column("salary_non_negotiable", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_career_goals_user_id"), "career_goals", ["user_id"], unique=True
    )


def downgrade() -> None:
    """Drop the career goals table."""
    op.drop_index(op.f("ix_career_goals_user_id"), table_name="career_goals")
    op.drop_table("career_goals")
