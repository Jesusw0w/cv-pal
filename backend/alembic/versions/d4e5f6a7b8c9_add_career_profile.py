"""add career profile, experiences, educations and skills

The structured master record from which tailored CVs are rendered. The skill_evidence
join is what makes the *never fabricate experience* rule enforceable: a skill can point
at the dated roles that demonstrate it, so a generator can tell a backed claim from an
unbacked one.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-26

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the career profile tables."""
    op.create_table(
        "career_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("headline", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("website_url", sa.String(length=512), nullable=True),
        sa.Column("linkedin_url", sa.String(length=512), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_career_profiles_user_id"), "career_profiles", ["user_id"], unique=True
    )

    op.create_table(
        "experiences",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("organisation", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("employment_type", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=False),
        # Null means the role is current.
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["career_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_experiences_profile_id"), "experiences", ["profile_id"], unique=False
    )

    op.create_table(
        "educations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("institution", sa.String(length=255), nullable=False),
        sa.Column("qualification", sa.String(length=255), nullable=False),
        sa.Column("field_of_study", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("grade", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["career_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_educations_profile_id"), "educations", ["profile_id"], unique=False
    )

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("canonical_name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column("proficiency", sa.String(length=64), nullable=True),
        sa.Column("years", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["career_profiles.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        # Deduplication happens on the canonical form, so "K8s" and "Kubernetes"
        # cannot both be added to one profile.
        sa.UniqueConstraint("profile_id", "canonical_name", name="uq_skill_per_profile"),
    )
    op.create_index(
        op.f("ix_skills_profile_id"), "skills", ["profile_id"], unique=False
    )
    op.create_index(
        op.f("ix_skills_canonical_name"), "skills", ["canonical_name"], unique=False
    )

    op.create_table(
        "skill_evidence",
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("experience_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["experience_id"], ["experiences.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("skill_id", "experience_id"),
    )


def downgrade() -> None:
    """Drop the career profile tables."""
    op.drop_table("skill_evidence")
    op.drop_index(op.f("ix_skills_canonical_name"), table_name="skills")
    op.drop_index(op.f("ix_skills_profile_id"), table_name="skills")
    op.drop_table("skills")
    op.drop_index(op.f("ix_educations_profile_id"), table_name="educations")
    op.drop_table("educations")
    op.drop_index(op.f("ix_experiences_profile_id"), table_name="experiences")
    op.drop_table("experiences")
    op.drop_index(op.f("ix_career_profiles_user_id"), table_name="career_profiles")
    op.drop_table("career_profiles")
