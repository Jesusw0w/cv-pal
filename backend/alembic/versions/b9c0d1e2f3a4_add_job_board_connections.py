"""add job board connections

A company board the user wants watched. Only Tier A boards can be connected — the ones
publishing an unauthenticated JSON endpoint for their own listings — because there is
nothing to store for a paste and nothing safe to store for a site that would have to be
scraped.

`last_synced_at` is the whole scheduling story for now: syncing is an endpoint that a
cron entry or a systemd timer triggers. Adding a job queue would mean adding Redis to a
self-hosted application for one periodic task, and the sync is idempotent by content
hash, so a timer needs no coordination.

Revision ID: b9c0d1e2f3a4
Revises: a8b9c0d1e2f3
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9c0d1e2f3a4"
down_revision: str | Sequence[str] | None = "a8b9c0d1e2f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the job board connections table."""
    op.create_table(
        "job_board_connections",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("identifier", sa.String(length=255), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "source", "identifier"),
    )
    op.create_index(
        op.f("ix_job_board_connections_user_id"),
        "job_board_connections",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the job board connections table."""
    op.drop_index(
        op.f("ix_job_board_connections_user_id"), table_name="job_board_connections"
    )
    op.drop_table("job_board_connections")
