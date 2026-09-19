"""add job postings

Postings are stored per user rather than globally. Two people searching the same board
have different profiles, different goals, and different reasons to keep a role — and a
shared table would make one user's deletion another user's data loss.

`content_hash` fingerprints title + company + description rather than the URL, because
the identical role is routinely posted to several boards under different links. Unique
per user, so re-importing the same posting is idempotent rather than a duplicate.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a8b9c0d1e2f3"
down_revision: str | Sequence[str] | None = "f7a8b9c0d1e2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the job postings table."""
    op.create_table(
        "job_postings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("external_id", sa.String(length=255), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "content_hash"),
    )
    op.create_index(
        op.f("ix_job_postings_user_id"), "job_postings", ["user_id"], unique=False
    )


def downgrade() -> None:
    """Drop the job postings table."""
    op.drop_index(op.f("ix_job_postings_user_id"), table_name="job_postings")
    op.drop_table("job_postings")
