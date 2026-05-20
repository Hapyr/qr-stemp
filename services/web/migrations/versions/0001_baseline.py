"""baseline schema (pre count column)

Revision ID: 0001_baseline
Revises:
Create Date: 2026-05-20

Mirrors the schema deployed before Flask-Migrate was introduced. Used so
existing databases can be stamped to this revision without altering data.
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=120), unique=True),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("password_hash", sa.String(length=512), nullable=True),
        sa.Column("user_token", sa.String(length=512), nullable=True),
    )
    op.create_index("ix_user_email", "user", ["email"], unique=True)
    op.create_index("ix_user_user_token", "user", ["user_token"])

    op.create_table(
        "stempel",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("client_id", sa.String(length=128), nullable=True),
        sa.Column("token", sa.String(length=128), nullable=True),
        sa.Column("used", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_stempel_host_id", "stempel", ["host_id"])
    op.create_index("ix_stempel_client_id", "stempel", ["client_id"])
    op.create_index("ix_stempel_token", "stempel", ["token"])

    op.create_table(
        "redeem_request",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("host_id", sa.Integer(), sa.ForeignKey("user.id")),
        sa.Column("client_id", sa.String(length=128), nullable=True),
        sa.Column("redeem_token", sa.String(length=128), unique=True),
        sa.Column("consumed", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_redeem_request_host_id", "redeem_request", ["host_id"])
    op.create_index(
        "ix_redeem_request_redeem_token", "redeem_request", ["redeem_token"], unique=True
    )


def downgrade():
    op.drop_table("redeem_request")
    op.drop_table("stempel")
    op.drop_table("user")
