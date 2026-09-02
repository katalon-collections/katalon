"""Add AI config, secrets, and usage tracking.

Revision ID: 0024
Revises: 0023
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admin_config", sa.Column("ai_enabled", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("admin_config", sa.Column("ai_base_url", sa.String(length=512), nullable=True))
    op.add_column("admin_config", sa.Column("ai_model", sa.String(length=256), nullable=True))
    op.add_column("admin_config", sa.Column("ai_max_input_tokens", sa.Integer(), nullable=False, server_default="6000"))
    op.add_column("admin_config", sa.Column("ai_max_output_tokens", sa.Integer(), nullable=False, server_default="800"))
    op.add_column("admin_config", sa.Column("ai_daily_user_token_limit", sa.Integer(), nullable=False, server_default="50000"))
    op.add_column("admin_config", sa.Column("ai_monthly_global_token_limit", sa.Integer(), nullable=False, server_default="1000000"))

    op.create_table(
        "app_secrets",
        sa.Column("key", sa.String(length=128), primary_key=True),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "ai_usage_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=256), nullable=False),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_ai_usage_events_user_id", "ai_usage_events", ["user_id"])
    op.create_index("ix_ai_usage_events_provider", "ai_usage_events", ["provider"])
    op.create_index("ix_ai_usage_events_model", "ai_usage_events", ["model"])
    op.create_index("ix_ai_usage_events_created_at", "ai_usage_events", ["created_at"])
    op.create_index("ix_ai_usage_events_user_created", "ai_usage_events", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_events_user_created", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_created_at", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_model", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_provider", table_name="ai_usage_events")
    op.drop_index("ix_ai_usage_events_user_id", table_name="ai_usage_events")
    op.drop_table("ai_usage_events")
    op.drop_table("app_secrets")

    op.drop_column("admin_config", "ai_monthly_global_token_limit")
    op.drop_column("admin_config", "ai_daily_user_token_limit")
    op.drop_column("admin_config", "ai_max_output_tokens")
    op.drop_column("admin_config", "ai_max_input_tokens")
    op.drop_column("admin_config", "ai_model")
    op.drop_column("admin_config", "ai_base_url")
    op.drop_column("admin_config", "ai_enabled")
