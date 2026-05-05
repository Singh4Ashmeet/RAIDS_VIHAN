"""add dispatch tier to dispatch plans

Revision ID: 0002_dispatch_tier
Revises: 0001_initial_schema
Create Date: 2026-05-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_dispatch_tier"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("dispatch_plans")}
    if "dispatch_tier" not in columns:
        op.add_column(
            "dispatch_plans",
            sa.Column("dispatch_tier", sa.String(), nullable=False, server_default="heuristic"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("dispatch_plans")}
    if "dispatch_tier" in columns:
        op.drop_column("dispatch_plans", "dispatch_tier")
