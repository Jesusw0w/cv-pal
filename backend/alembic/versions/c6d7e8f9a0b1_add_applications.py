"""track applications, the last step of the journey

The product could tailor a CV for a posting and then had nothing to say about what
happened. The dashboard "funnel" counted saved postings, scored matches and uploaded
CVs — three figures that only ever grow and that nothing passes between — because there
was no row anywhere recording that an application had been sent.

`cv_id` uses SET NULL rather than CASCADE: deleting a CV must not delete the record of
having applied with it. `applied_at` is separate from `created_at` because people enter
an application days after sending it, and every interval on this table is measured from
when it actually went out.

Revision ID: c6d7e8f9a0b1
Revises: b5c6d7e8f9a0
Create Date: 2026-09-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from cv_pal.constants import (
    DEFAULT_STATUS_MAX_LENGTH,
)

revision: str = "c6d7e8f9a0b1"
down_revision: str | Sequence[str] | None = "b5c6d7e8f9a0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the applications table."""
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), nullable=False),
        sa.Column("cv_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=DEFAULT_STATUS_MAX_LENGTH), nullable=False),
        sa.Column("applied_at", sa.Date(), nullable=False),
        sa.Column("status_changed_at", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["cv_id"], ["cvs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        # Applying twice to the same role is not two applications.
        sa.UniqueConstraint("user_id", "job_posting_id"),
    )
    op.create_index("ix_applications_user_id", "applications", ["user_id"])
    op.create_index("ix_applications_job_posting_id", "applications", ["job_posting_id"])
    op.create_index("ix_applications_cv_id", "applications", ["cv_id"])


def downgrade() -> None:
    """Drop the applications table."""
    op.drop_index("ix_applications_cv_id", table_name="applications")
    op.drop_index("ix_applications_job_posting_id", table_name="applications")
    op.drop_index("ix_applications_user_id", table_name="applications")
    op.drop_table("applications")
