"""policy settings, tickets, action rollback data, demo flag

Revision ID: 0006
Revises: 0005
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("action", sa.Column("before", sa.JSON(), nullable=False, server_default="{}"))
    op.add_column("action", sa.Column("approved_by", sa.String(64), nullable=True))
    op.add_column("incident", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("journey_run", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("audit_event", sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "app_setting",
        sa.Column("key", sa.String(32), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=False),
    )
    op.create_table(
        "ticket",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incident.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("state", sa.String(8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_ticket_incident_id", "ticket", ["incident_id"])


def downgrade() -> None:
    op.drop_table("ticket")
    op.drop_table("app_setting")
    op.drop_column("audit_event", "is_demo")
    op.drop_column("journey_run", "is_demo")
    op.drop_column("incident", "is_demo")
    op.drop_column("action", "approved_by")
    op.drop_column("action", "before")
