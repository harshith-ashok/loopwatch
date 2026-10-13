"""past_incident (pgvector) and hypothesis.cause_key

Revision ID: 0005
Revises: 0004
"""
import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "hypothesis",
        sa.Column("cause_key", sa.String(32), nullable=False, server_default="unknown"),
    )
    op.create_table(
        "past_incident",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("cause_key", sa.String(32), nullable=False),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("embedding", Vector(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("past_incident")
    op.drop_column("hypothesis", "cause_key")
