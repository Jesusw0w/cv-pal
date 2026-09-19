"""add linkedin profile snapshots

The imported copy of a user's LinkedIn profile. One per user, replaced on re-import:
it is a photograph of a document the user exported, not a second career record, and
nothing generates a CV from it — the career profile stays the master record.

Parsed positions, educations and skills are JSON rather than tables. The shape only has
to survive being read back for a review, and normalising it would imply a promotion to
source-of-truth that the product deliberately withholds from a document it never
verified.

`raw_text` is kept so the review can be recomputed when the user's goals or career
profile change, without making them export from LinkedIn again — which for the official
data export takes up to 72 hours.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-07-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c0d1e2f3a4b5"
down_revision: str | Sequence[str] | None = "b9c0d1e2f3a4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the LinkedIn profile snapshot table."""
    op.create_table(
        "linkedin_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("profile_url", sa.String(length=512), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("headline", sa.String(length=255), nullable=True),
        sa.Column("about", sa.Text(), nullable=True),
        sa.Column("positions", sa.JSON(), nullable=False),
        sa.Column("educations", sa.JSON(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("sections_found", sa.JSON(), nullable=False),
        sa.Column("field_sources", sa.JSON(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_linkedin_profiles_user_id"),
        "linkedin_profiles",
        ["user_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop the LinkedIn profile snapshot table."""
    op.drop_index(op.f("ix_linkedin_profiles_user_id"), table_name="linkedin_profiles")
    op.drop_table("linkedin_profiles")
