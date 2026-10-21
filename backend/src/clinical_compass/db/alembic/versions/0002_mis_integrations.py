"""MIS integrations: external identities and launch codes

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-22 10:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "external_identities",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("system", sa.String(length=16), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("internal_id", sa.String(length=64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system", "kind", "external_id", name="uq_external_identity"),
    )
    op.create_index("ix_external_identities_internal_id", "external_identities", ["internal_id"])
    op.create_table(
        "launch_codes",
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("system", sa.String(length=16), nullable=False),
        sa.Column("doctor_id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("code_hash"),
    )


def downgrade() -> None:
    op.drop_table("launch_codes")
    op.drop_index("ix_external_identities_internal_id", table_name="external_identities")
    op.drop_table("external_identities")
