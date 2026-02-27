"""Add api_keys table.

Revision ID: 004_api_keys
Revises: 003_subscriptions
"""

from alembic import op
import sqlalchemy as sa

revision = "004_api_keys"
down_revision = "003_subscriptions"

def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("key_hash", sa.String(64), unique=True, nullable=False),
        sa.Column("role", sa.String(20), server_default="reader"),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )

def downgrade() -> None:
    op.drop_table("api_keys")
