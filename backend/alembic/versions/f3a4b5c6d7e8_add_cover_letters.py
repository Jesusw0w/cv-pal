"""add cover letters

Kept for one reason that outweighs a table: the *self-similarity* check needs a corpus,
and the corpus can only be the user's own letters. Without somewhere to keep them,
PLANNING's strongest quality signal — "the last ten letters were 92% identical" — cannot
be computed at all, and the generator would ship the behaviour the project exists to
prevent.

Unique per posting, so saving again replaces rather than accumulates: similarity
measured against earlier attempts at the *same* letter would measure nothing.

Cascades from both the user and the posting. A letter for a posting the user deleted
has nothing left to be about.

Revision ID: f3a4b5c6d7e8
Revises: e2f3a4b5c6d7
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f3a4b5c6d7e8"
down_revision: str | Sequence[str] | None = "e2f3a4b5c6d7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the cover letters table."""
    op.create_table(
        "cover_letters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_posting_id", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["job_posting_id"], ["job_postings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "job_posting_id"),
    )
    op.create_index("ix_cover_letters_user_id", "cover_letters", ["user_id"])
    op.create_index(
        "ix_cover_letters_job_posting_id", "cover_letters", ["job_posting_id"]
    )


def downgrade() -> None:
    """Drop the cover letters table."""
    op.drop_index("ix_cover_letters_job_posting_id", table_name="cover_letters")
    op.drop_index("ix_cover_letters_user_id", table_name="cover_letters")
    op.drop_table("cover_letters")
