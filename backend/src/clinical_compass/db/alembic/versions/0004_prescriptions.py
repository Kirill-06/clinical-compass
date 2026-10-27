"""prescriptions: drugs a doctor prescribes to a patient

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-27 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "prescriptions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("doctor_id", sa.String(length=64), nullable=False),
        sa.Column("drug", sa.String(length=200), nullable=False),
        sa.Column("dosage", sa.String(length=200), nullable=False),
        sa.Column("regimen", sa.String(length=300), nullable=False),
        sa.Column("duration", sa.String(length=100), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(["doctor_id"], ["doctors.id"]),
        sa.ForeignKeyConstraint(["patient_id"], ["patients.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("prescriptions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_prescriptions_patient_id"), ["patient_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("prescriptions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_prescriptions_patient_id"))
    op.drop_table("prescriptions")
