"""add where the user may work to career goals

Job discovery (session 27) made this urgent rather than merely missing. A remote feed
returns roles that are remote *and* restricted — "Remote · Brazil", "Remote · USA" —
and with no location in the goals those were scored on skills alone and ranked
alongside jobs the user could actually take.

Free text, and a list, because the terms are the user's own. Matching compares them
against the posting's wording and infers no geography: nothing here asserts that
Portugal is in Europe. See `analysis/matching.location_fit` for why.

`server_default` is set for the existing rows and then dropped, so the column is
NOT NULL without every future insert relying on a database-side default that the
model does not know about.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-08

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2f3a4b5c6d7"
down_revision: str | Sequence[str] | None = "d1e2f3a4b5c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the work locations list and its non-negotiable flag."""
    with op.batch_alter_table("career_goals") as batch:
        batch.add_column(
            sa.Column("work_locations", sa.JSON(), nullable=False, server_default="[]")
        )
        batch.add_column(
            sa.Column(
                "location_non_negotiable",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table("career_goals") as batch:
        batch.alter_column("work_locations", server_default=None)
        batch.alter_column("location_non_negotiable", server_default=None)


def downgrade() -> None:
    """Drop the work locations list and its flag."""
    with op.batch_alter_table("career_goals") as batch:
        batch.drop_column("location_non_negotiable")
        batch.drop_column("work_locations")
