"""add the contract type a posting offers

Nullable, and deliberately so. Greenhouse and Lever do not expose the contract as a
field at all, so for every posting from them the honest value is "not stated" — and
that is a different answer from "full time". Backfilling a default would invent the
commonest contract for the majority of rows.

Not part of `content_hash`: the hash exists to collapse the same role arriving from
several sources, and two sources describing one job with different contract wording
are still the same job.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "c0d1e2f3a4b5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable employment type column."""
    op.add_column(
        "job_postings",
        sa.Column("employment_type", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    """Drop the employment type column."""
    op.drop_column("job_postings", "employment_type")
