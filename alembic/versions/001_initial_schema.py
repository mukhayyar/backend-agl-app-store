"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-26
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Apps
    op.create_table(
        "apps",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text),
        sa.Column("description", sa.Text),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("project_license", sa.String(255)),
        sa.Column("is_free_license", sa.Boolean, default=True),
        sa.Column("developer_name", sa.String(255)),
        sa.Column("icon", sa.String(500)),
        sa.Column("runtime", sa.String(255)),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("added_at", sa.DateTime),
        sa.Column("is_mobile_friendly", sa.Boolean, default=False),
        sa.Column("verification_verified", sa.Boolean, default=False),
        sa.Column("verification_method", sa.String(50), default="none"),
        sa.Column("verification_login_name", sa.String(255)),
        sa.Column("verification_login_provider", sa.String(50)),
        sa.Column("verification_login_is_organization", sa.Boolean, default=False),
        sa.Column("verification_website", sa.String(500)),
        sa.Column("verification_timestamp", sa.DateTime),
        sa.Column("extends", sa.String(255)),
    )

    # Users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("display_name", sa.String(255)),
        sa.Column("invite_code", sa.String(100), unique=True),
        sa.Column("accepted_publisher_agreement_at", sa.DateTime),
        sa.Column("default_account_provider", sa.String(50)),
        sa.Column("default_account_login", sa.String(255)),
        sa.Column("created_at", sa.DateTime),
        sa.Column("updated_at", sa.DateTime),
        sa.Column("role", sa.String(20), nullable=False, server_default="user"),
    )

    # Categories
    op.create_table(
        "categories",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("description", sa.Text),
    )

    # Connected Accounts
    op.create_table(
        "connected_accounts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("provider_user_id", sa.BigInteger, nullable=False),
        sa.Column("login", sa.String(255)),
        sa.Column("avatar_url", sa.String(500)),
        sa.Column("display_name", sa.String(255)),
        sa.Column("email", sa.String(255)),
        sa.Column("last_used", sa.DateTime),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )
    op.create_index("ix_connected_accounts_user_id", "connected_accounts", ["user_id"])

    # Releases
    op.create_table(
        "releases",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("app_id", sa.String(255), sa.ForeignKey("apps.id")),
        sa.Column("version", sa.String(100)),
        sa.Column("timestamp", sa.DateTime),
        sa.Column("date", sa.DateTime),
        sa.Column("type", sa.String(50)),
        sa.Column("urgency", sa.String(50)),
        sa.Column("description", sa.Text),
        sa.Column("url", sa.String(500)),
        sa.Column("date_eol", sa.DateTime),
    )

    # Screenshots
    op.create_table(
        "screenshots",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("app_id", sa.String(255), sa.ForeignKey("apps.id")),
        sa.Column("caption", sa.Text),
        sa.Column("default_screenshot", sa.Boolean, default=False),
    )

    # Screenshot Sizes
    op.create_table(
        "screenshot_sizes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("screenshot_id", sa.Integer, sa.ForeignKey("screenshots.id")),
        sa.Column("width", sa.String(10)),
        sa.Column("height", sa.String(10)),
        sa.Column("scale", sa.String(10), default="1x"),
        sa.Column("src", sa.String(500)),
    )

    # Favorites
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("app_id", sa.String(255), sa.ForeignKey("apps.id"), nullable=False),
        sa.Column("created_at", sa.DateTime),
        sa.UniqueConstraint("user_id", "app_id", name="uq_user_app_favorite"),
    )

    # App Stats
    op.create_table(
        "app_stats",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("app_id", sa.String(255), sa.ForeignKey("apps.id")),
        sa.Column("date", sa.DateTime),
        sa.Column("installs", sa.Integer, default=0),
        sa.Column("updates", sa.Integer, default=0),
        sa.Column("country", sa.String(2)),
    )

    # Transactions
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(100), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("value", sa.Integer),
        sa.Column("currency", sa.String(3)),
        sa.Column("kind", sa.String(20)),
        sa.Column("status", sa.String(20)),
        sa.Column("reason", sa.Text),
        sa.Column("created", sa.DateTime),
        sa.Column("updated", sa.DateTime),
    )

    # Transaction Details
    op.create_table(
        "transaction_details",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("transaction_id", sa.String(100), sa.ForeignKey("transactions.id")),
        sa.Column("recipient", sa.String(255)),
        sa.Column("amount", sa.Integer),
        sa.Column("currency", sa.String(3)),
        sa.Column("kind", sa.String(20)),
    )

    # User Roles
    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("role_name", sa.String(50)),
    )

    # Association tables
    op.create_table(
        "app_developers",
        sa.Column("app_id", sa.String, sa.ForeignKey("apps.id")),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id")),
        sa.Column("is_primary", sa.Boolean, default=False),
    )

    op.create_table(
        "app_categories",
        sa.Column("app_id", sa.String, sa.ForeignKey("apps.id")),
        sa.Column("category", sa.String, sa.ForeignKey("categories.name")),
    )


def downgrade() -> None:
    op.drop_table("app_categories")
    op.drop_table("app_developers")
    op.drop_table("user_roles")
    op.drop_table("transaction_details")
    op.drop_table("transactions")
    op.drop_table("app_stats")
    op.drop_table("favorites")
    op.drop_table("screenshot_sizes")
    op.drop_table("screenshots")
    op.drop_table("releases")
    op.drop_table("connected_accounts")
    op.drop_table("categories")
    op.drop_table("users")
    op.drop_table("apps")
