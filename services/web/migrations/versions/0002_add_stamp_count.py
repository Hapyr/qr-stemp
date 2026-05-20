"""add Stempel.count (multi-stamp claims)

Revision ID: 0002_add_stamp_count
Revises: 0001_baseline
Create Date: 2026-05-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_add_stamp_count"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("stempel") as batch:
        batch.add_column(
            sa.Column("count", sa.Integer(), nullable=False, server_default="1")
        )


def downgrade():
    with op.batch_alter_table("stempel") as batch:
        batch.drop_column("count")
