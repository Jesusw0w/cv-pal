"""job platforms, salary expectations per contract type, and a GitHub link

- ``job_platforms``: where the user keeps a profile, and when they last updated it.
- ``applications.platform_id``: which platform an application went through.
- ``career_goals.salary_expectations`` replaces ``min_salary`` / ``salary_currency``.
  An existing floor becomes the full-time annual expectation, which is what the single
  field meant.
- ``career_profiles.github_url``: a GitHub link stored as the website moves here.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-09-23

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: str | Sequence[str] | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_GITHUB = "%github.com/%"


def upgrade() -> None:
    """Create job_platforms, and move the salary and GitHub data to their new homes."""
    op.create_table(
        "job_platforms",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("profile_url", sa.String(length=512), nullable=True),
        sa.Column("profile_updated_on", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "name"),
    )
    op.create_index(
        op.f("ix_job_platforms_user_id"), "job_platforms", ["user_id"], unique=False
    )

    with op.batch_alter_table("applications") as batch:
        batch.add_column(sa.Column("platform_id", sa.Integer(), nullable=True))
        batch.create_index(
            batch.f("ix_applications_platform_id"), ["platform_id"], unique=False
        )
        batch.create_foreign_key(
            "fk_applications_platform_id_job_platforms",
            "job_platforms",
            ["platform_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("career_profiles") as batch:
        batch.add_column(sa.Column("github_url", sa.String(length=512), nullable=True))
    op.execute(
        sa.text(
            "UPDATE career_profiles SET github_url = website_url, website_url = NULL "
            "WHERE website_url LIKE :github"
        ).bindparams(github=_GITHUB)
    )

    with op.batch_alter_table("career_goals") as batch:
        batch.add_column(
            sa.Column(
                "salary_expectations",
                sa.JSON(),
                nullable=False,
                server_default="[]",
            )
        )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT id, min_salary, salary_currency FROM career_goals "
            "WHERE min_salary IS NOT NULL"
        )
    ).all()
    for goal_id, minimum, currency in rows:
        expectation = {
            "employment_type": "full_time",
            "minimum": minimum,
            "target": None,
            "currency": currency or "EUR",
            "period": "year",
        }
        connection.execute(
            sa.text(
                "UPDATE career_goals SET salary_expectations = :value WHERE id = :id"
            ).bindparams(value=json.dumps([expectation]), id=goal_id)
        )
    with op.batch_alter_table("career_goals") as batch:
        # The default only filled the existing rows; the model supplies it from now on.
        batch.alter_column("salary_expectations", server_default=None)
        batch.drop_column("min_salary")
        batch.drop_column("salary_currency")


def downgrade() -> None:
    """Restore the single salary floor from the full-time annual expectation."""
    with op.batch_alter_table("career_goals") as batch:
        batch.add_column(sa.Column("min_salary", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("salary_currency", sa.String(length=3), nullable=True)
        )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, salary_expectations FROM career_goals")
    ).all()
    for goal_id, raw in rows:
        expectations = json.loads(raw) if isinstance(raw, str) else raw or []
        annual = next(
            (
                item
                for item in expectations
                if item.get("employment_type") == "full_time"
                and item.get("period") == "year"
            ),
            None,
        )
        if annual is not None:
            connection.execute(
                sa.text(
                    "UPDATE career_goals SET min_salary = :minimum, "
                    "salary_currency = :currency WHERE id = :id"
                ).bindparams(
                    minimum=annual["minimum"], currency=annual["currency"], id=goal_id
                )
            )
    with op.batch_alter_table("career_goals") as batch:
        batch.drop_column("salary_expectations")

    op.execute(
        sa.text(
            "UPDATE career_profiles SET website_url = github_url "
            "WHERE website_url IS NULL AND github_url IS NOT NULL"
        )
    )
    with op.batch_alter_table("career_profiles") as batch:
        batch.drop_column("github_url")

    with op.batch_alter_table("applications") as batch:
        batch.drop_constraint(
            "fk_applications_platform_id_job_platforms", type_="foreignkey"
        )
        batch.drop_index(batch.f("ix_applications_platform_id"))
        batch.drop_column("platform_id")

    op.drop_index(op.f("ix_job_platforms_user_id"), table_name="job_platforms")
    op.drop_table("job_platforms")
