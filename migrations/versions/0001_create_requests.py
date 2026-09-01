"""create requests table

Revision ID: 0001
Revises:
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(255), nullable=False),
        sa.Column("value", sa.Numeric(15, 2), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "MANUAL_REVIEW", "FAILED"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("requests")
