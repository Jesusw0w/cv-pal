"""add cvs and suggestions tables

These tables previously existed only because ``Base.metadata.create_all()`` ran at
application startup, so they were missing from any Alembic-managed deployment. This
revision brings the migration history in line with the models, including the foreign
keys that were never declared.

Revision ID: a1b2c3d4e5f6
Revises: f6bd192ca9c2
Create Date: 2026-07-25

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f6bd192ca9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the cvs and suggestions tables and align users with the model."""
    # The original users migration left is_active and created_at nullable and gave
    # the string columns no length, neither of which matches the model.
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "email", type_=sa.String(length=320), existing_nullable=False
        )
        batch.alter_column(
            "hashed_password", type_=sa.String(length=128), existing_nullable=False
        )
        batch.alter_column(
            "full_name", type_=sa.String(length=255), existing_nullable=True
        )
        batch.alter_column(
            "is_active", existing_type=sa.Boolean(), nullable=False
        )
        batch.alter_column(
            "created_at",
            existing_type=sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        )

    op.create_table(
        "cvs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_path", sa.String(length=1024), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_cvs_user_id"), "cvs", ["user_id"], unique=False)

    op.create_table(
        "suggestions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cv_id", sa.Integer(), nullable=False),
        sa.Column("suggestion_type", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("accepted", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["cv_id"], ["cvs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_suggestions_cv_id"), "suggestions", ["cv_id"], unique=False
    )


def downgrade() -> None:
    """Drop the cvs and suggestions tables and restore the users column types."""
    op.drop_index(op.f("ix_suggestions_cv_id"), table_name="suggestions")
    op.drop_table("suggestions")
    op.drop_index(op.f("ix_cvs_user_id"), table_name="cvs")
    op.drop_table("cvs")

    with op.batch_alter_table("users") as batch:
        batch.alter_column("email", type_=sa.String(), existing_nullable=False)
        batch.alter_column(
            "hashed_password", type_=sa.String(), existing_nullable=False
        )
        batch.alter_column("full_name", type_=sa.String(), existing_nullable=True)
        batch.alter_column("is_active", existing_type=sa.Boolean(), nullable=True)
        batch.alter_column(
            "created_at", existing_type=sa.DateTime(timezone=True), nullable=True
        )
