"""add a phone number to the career profile

The parseability check has always reported "No phone number found" on an uploaded CV,
while the profile had nowhere to keep one and the generated contact line could not
carry one. Every CV this product wrote therefore failed a check this product makes.

Nullable, because it genuinely is optional — the finding is INFO, not a warning.

Revision ID: a4b5c6d7e8f9
Revises: f3a4b5c6d7e8
Create Date: 2026-09-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a4b5c6d7e8f9"
down_revision: str | Sequence[str] | None = "f3a4b5c6d7e8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the phone column."""
    with op.batch_alter_table("career_profiles") as batch:
        batch.add_column(sa.Column("phone", sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Drop the phone column."""
    with op.batch_alter_table("career_profiles") as batch:
        batch.drop_column("phone")
