"""let a watched board save only postings matching the user's target roles

Goals were read by scoring alone: a target role changed how a posting ranked once it
was saved, and nothing else. A board sync therefore saved a company's entire listing —
every warehouse and sales role alongside the engineering ones — and left the user to
filter by eye.

Off by default, and deliberately: turning it on for existing connections would silently
change what a sync saves, and a job posting that never arrives is not something the user
can go looking for.

Revision ID: b5c6d7e8f9a0
Revises: a4b5c6d7e8f9
Create Date: 2026-09-07

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b5c6d7e8f9a0"
down_revision: str | Sequence[str] | None = "a4b5c6d7e8f9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the opt-in filter flag."""
    with op.batch_alter_table("job_board_connections") as batch:
        batch.add_column(
            sa.Column(
                "filter_by_goals",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    # Set for the existing rows, then dropped, so future inserts go through the model
    # rather than a database-side default the model does not know about.
    with op.batch_alter_table("job_board_connections") as batch:
        batch.alter_column("filter_by_goals", server_default=None)


def downgrade() -> None:
    """Drop the filter flag."""
    with op.batch_alter_table("job_board_connections") as batch:
        batch.drop_column("filter_by_goals")
