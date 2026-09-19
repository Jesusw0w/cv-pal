"""widen hashed_password for argon2id

bcrypt hashes are 60 characters; argon2id encodes to about 97 at the configured
parameters. The column is widened to 255 so stronger parameters later do not need
another migration.

Existing bcrypt hashes are left untouched — they still verify, and are replaced with
argon2id the next time their owner logs in.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Widen users.hashed_password to 255 characters."""
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "hashed_password",
            existing_type=sa.String(length=128),
            type_=sa.String(length=255),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Narrow users.hashed_password back to 128 characters."""
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "hashed_password",
            existing_type=sa.String(length=255),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
