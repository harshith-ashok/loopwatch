"""incident children: evidence, hypothesis, action, verification

Revision ID: 0004
Revises: 0003
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "evidence",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incident.id"), nullable=False),
        sa.Column("ref", sa.String(8), nullable=False),
        sa.Column("tool", sa.String(48), nullable=False),
        sa.Column("args", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        _created_at(),
    )
    op.create_index("ix_evidence_incident_id", "evidence", ["incident_id"])
    op.create_table(
        "hypothesis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incident.id"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("cause", sa.String(160), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("supporting", sa.JSON(), nullable=False),
        sa.Column("weakening", sa.JSON(), nullable=False),
        _created_at(),
    )
    op.create_index("ix_hypothesis_incident_id", "hypothesis", ["incident_id"])
    op.create_table(
        "action",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incident.id"), nullable=False),
        sa.Column("type", sa.String(32), nullable=False),
        sa.Column("target", sa.String(64), nullable=False),
        sa.Column("risk", sa.String(8), nullable=False),
        sa.Column("mode", sa.String(12), nullable=False),
        sa.Column("state", sa.String(20), nullable=False),
        sa.Column("rollback", sa.Text(), nullable=False),
        _created_at(),
    )
    op.create_index("ix_action_incident_id", "action", ["incident_id"])
    op.create_table(
        "verification",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), sa.ForeignKey("incident.id"), nullable=False),
        sa.Column("run_number", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("ms", sa.Integer(), nullable=False),
        _created_at(),
    )
    op.create_index("ix_verification_incident_id", "verification", ["incident_id"])


def downgrade() -> None:
    for table in ("verification", "action", "hypothesis", "evidence"):
        op.drop_table(table)
