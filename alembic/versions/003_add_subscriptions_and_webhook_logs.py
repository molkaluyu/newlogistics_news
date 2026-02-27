"""Add subscriptions and webhook delivery logs tables.

Revision ID: 003_subscriptions
Revises: 002_dedup_hnsw
Create Date: 2026-02-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "003_subscriptions"
down_revision = "002_dedup_hnsw"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_ids", sa.ARRAY(sa.String(100)), nullable=True),
        sa.Column("transport_modes", sa.ARRAY(sa.String(50)), nullable=True),
        sa.Column("topics", sa.ARRAY(sa.String(100)), nullable=True),
        sa.Column("regions", sa.ARRAY(sa.String(50)), nullable=True),
        sa.Column("urgency_min", sa.String(20), nullable=True),
        sa.Column("languages", sa.ARRAY(sa.String(10)), nullable=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("channel_config", JSONB, nullable=True),
        sa.Column("frequency", sa.String(20), server_default="realtime"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_table(
        "webhook_delivery_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("subscription_id", sa.String(36), nullable=False),
        sa.Column("article_id", sa.String(36), nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("success", sa.Boolean, server_default="false"),
        sa.Column("attempt", sa.Integer, server_default="1"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_webhook_logs_subscription_id",
        "webhook_delivery_logs",
        ["subscription_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_webhook_logs_subscription_id",
        table_name="webhook_delivery_logs",
    )
    op.drop_table("webhook_delivery_logs")
    op.drop_table("subscriptions")
