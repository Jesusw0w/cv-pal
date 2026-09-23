"""languages, portfolio, education date precision, application and platform details

- ``profile_languages`` and ``portfolio_items``: two new profile sections.
- ``educations.date_precision``: ``month`` (existing rows) or ``year``.
- ``applications.salary`` and ``applications.next_step``.
- ``job_platforms.state``: existing platforms are ``active``.

Revision ID: a0b1c2d3e4f5
Revises: f9a0b1c2d3e4
Create Date: 2026-09-23

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a0b1c2d3e4f5"
down_revision: str | Sequence[str] | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the two sections and add the new columns."""
    op.create_table(
        "profile_languages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("level", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["career_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "name"),
    )
    op.create_index(
        op.f("ix_profile_languages_profile_id"),
        "profile_languages",
        ["profile_id"],
        unique=False,
    )
    op.create_table(
        "portfolio_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["career_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_portfolio_items_profile_id"),
        "portfolio_items",
        ["profile_id"],
        unique=False,
    )

    # Server defaults fill the existing rows, then go: the models supply them after.
    with op.batch_alter_table("educations") as batch:
        batch.add_column(
            sa.Column(
                "date_precision",
                sa.String(length=16),
                nullable=False,
                server_default="month",
            )
        )
    with op.batch_alter_table("educations") as batch:
        batch.alter_column("date_precision", server_default=None)

    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("salary", sa.String(length=128), nullable=True))
        batch.add_column(sa.Column("next_step", sa.Text(), nullable=True))

    with op.batch_alter_table("job_platforms") as batch:
        batch.add_column(
            sa.Column(
                "state", sa.String(length=16), nullable=False, server_default="active"
            )
        )
    with op.batch_alter_table("job_platforms") as batch:
        batch.alter_column("state", server_default=None)


def downgrade() -> None:
    """Drop the new columns and the two sections."""
    with op.batch_alter_table("job_platforms") as batch:
        batch.drop_column("state")
    with op.batch_alter_table("applications") as batch:
        batch.drop_column("next_step")
        batch.drop_column("salary")
    with op.batch_alter_table("educations") as batch:
        batch.drop_column("date_precision")
    op.drop_index(op.f("ix_portfolio_items_profile_id"), table_name="portfolio_items")
    op.drop_table("portfolio_items")
    op.drop_index(
        op.f("ix_profile_languages_profile_id"), table_name="profile_languages"
    )
    op.drop_table("profile_languages")
