# -*- coding: utf-8 -*-
"""
Alembic migration: add app_logs table (v2.2)
Revision: 002_v22
"""
from alembic import op
import sqlalchemy as sa

revision      = "002_v22"
down_revision = "001_v2"
branch_labels = None
depends_on    = None


def upgrade():
    op.create_table(
        "app_logs",
        sa.Column("id",        sa.Integer(),  primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("level",     sa.String(16),  nullable=False),
        sa.Column("logger",    sa.String(128), nullable=False),
        sa.Column("message",   sa.Text(),      nullable=False),
        sa.Column("exception", sa.Text(),      nullable=True),
        sa.Column("source",    sa.String(255), nullable=True),
    )
    op.create_index("ix_app_logs_ts",        "app_logs", ["timestamp"])
    op.create_index("ix_app_logs_level",     "app_logs", ["level"])
    op.create_index("ix_app_logs_logger",    "app_logs", ["logger"])
    op.create_index("ix_app_logs_level_ts",  "app_logs", ["level",  "timestamp"])
    op.create_index("ix_app_logs_logger_ts", "app_logs", ["logger", "timestamp"])


def downgrade():
    op.drop_table("app_logs")
