"""developer workflow: api tokens and app submissions

Revision ID: 002
Revises: 001
Create Date: 2026-04-11
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── developer_tokens ────────────────────────────────────────────────────
    op.create_table(
        "developer_tokens",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("token_prefix", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("last_used_at", sa.DateTime),
        sa.Column("expires_at", sa.DateTime),
    )
    op.create_index("ix_developer_tokens_user_id", "developer_tokens", ["user_id"])
    op.create_index("ix_developer_tokens_token_hash", "developer_tokens", ["token_hash"])

    # ── app_submissions ──────────────────────────────────────────────────────
    op.create_table(
        "app_submissions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("app_id", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("icon", sa.String(500)),
        sa.Column("homepage", sa.String(500)),
        sa.Column("license", sa.String(255)),
        sa.Column("app_type", sa.String(50), server_default="desktop-application"),
        sa.Column("categories", sa.JSON),
        sa.Column("screenshots", sa.JSON),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("submitted_at", sa.DateTime, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime),
        sa.Column("reviewer_id", sa.Integer, sa.ForeignKey("users.id")),
    )
    op.create_index("ix_app_submissions_user_id", "app_submissions", ["user_id"])
    op.create_index("ix_app_submissions_status", "app_submissions", ["status"])
    op.create_index("ix_app_submissions_app_id", "app_submissions", ["app_id"])


def downgrade() -> None:
    op.drop_table("app_submissions")
    op.drop_table("developer_tokens")
