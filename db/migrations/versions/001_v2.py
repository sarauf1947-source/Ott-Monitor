# -*- coding: utf-8 -*-
"""add v2 auth settings reports pinned tables

Revision ID: 001_v2
Revises: (set to your last migration ID if one exists, otherwise leave None)
"""
from alembic import op
import sqlalchemy as sa

revision      = "001_v2"
down_revision = None
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id",              sa.Integer(),     primary_key=True, autoincrement=True),
        sa.Column("username",        sa.String(64),    unique=True,  nullable=False),
        sa.Column("email",           sa.String(255),   unique=True,  nullable=False),
        sa.Column("full_name",       sa.String(255),   nullable=True),
        sa.Column("hashed_password", sa.String(255),   nullable=False),
        sa.Column("role",            sa.String(16),    nullable=False, server_default="viewer"),
        sa.Column("is_active",       sa.Boolean(),     nullable=False, server_default="true"),
        sa.Column("created_at",      sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login",      sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_email",    "users", ["email"])

    op.create_table(
        "system_settings",
        sa.Column("id",         sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("category",   sa.String(64),   nullable=False),
        sa.Column("key",        sa.String(128),  nullable=False),
        sa.Column("value",      sa.Text(),       nullable=True),
        sa.Column("is_secret",  sa.Boolean(),    server_default="false"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(64),   nullable=True),
        sa.UniqueConstraint("category", "key", name="uq_settings_category_key"),
    )
    op.create_index("ix_settings_category", "system_settings", ["category"])

    op.create_table(
        "scheduled_reports",
        sa.Column("id",               sa.Integer(),    primary_key=True, autoincrement=True),
        sa.Column("name",             sa.String(255),  nullable=False),
        sa.Column("report_type",      sa.String(64),   nullable=False, server_default="full"),
        sa.Column("frequency",        sa.String(32),   nullable=False, server_default="weekly"),
        sa.Column("channel_ids",      sa.Text(),       nullable=True),
        sa.Column("export_format",    sa.String(16),   server_default="pdf"),
        sa.Column("email_recipients", sa.Text(),       nullable=True),
        sa.Column("webhook_url",      sa.String(500),  nullable=True),
        sa.Column("is_active",        sa.Boolean(),    server_default="true"),
        sa.Column("last_run_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at",      sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at",       sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("created_by",       sa.String(64),   nullable=True),
    )

    op.create_table(
        "pinned_channels",
        sa.Column("id",         sa.Integer(),   primary_key=True, autoincrement=True),
        sa.Column("user_id",    sa.Integer(),   nullable=False),
        sa.Column("channel_id", sa.String(36),  nullable=False),
        sa.Column("pinned_at",  sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "channel_id", name="uq_pinned_user_channel"),
    )
    op.create_index("ix_pinned_user_id", "pinned_channels", ["user_id"])


def downgrade():
    op.drop_table("pinned_channels")
    op.drop_table("scheduled_reports")
    op.drop_table("system_settings")
    op.drop_table("users")
