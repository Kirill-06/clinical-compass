"""initial schema v0.2

Revision ID: 0001
Revises:
Create Date: 2026-10-21 17:12:20.448894
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:

    op.create_table(
        "admins",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.create_index("ix_audit_patient_time", ["patient_id", "at"], unique=False)

    op.create_table(
        "doctors",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("short_name", sa.String(length=100), nullable=False),
        sa.Column("specialty", sa.String(length=200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "patients",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("display_id", sa.String(length=32), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("birth_year", sa.Integer(), nullable=False),
        sa.Column("sex", sa.String(length=16), nullable=True),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("observation_start", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("display_id"),
    )
    op.create_table(
        "sessions",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("token_hash"),
    )
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_sessions_user_id"), ["user_id"], unique=False)

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("doctor_id", sa.String(length=64), nullable=True),
        sa.Column("rule_id", sa.String(length=64), nullable=False),
        sa.Column("rule_version", sa.String(length=16), nullable=False),
        sa.Column("rule_source", sa.String(length=128), nullable=False),
        sa.Column("doctor_priority", sa.String(length=16), nullable=False),
        sa.Column("patient_action", sa.String(length=32), nullable=False),
        sa.Column("medical_urgency_classified", sa.Boolean(), nullable=False),
        sa.Column("message_template_id", sa.String(length=64), nullable=True),
        sa.Column("source_fact_ids", sa.JSON(), nullable=False),
        sa.Column("dedupe_key", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("delivered_to_workplace_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(length=100), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "dedupe_key", name="uq_alert_dedupe"),
    )
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.create_index("ix_alert_doctor_status", ["doctor_id", "status"], unique=False)

    op.create_table(
        "booking_tasks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("requested_by_doctor_id", sa.String(length=64), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.ForeignKeyConstraint(
            ["requested_by_doctor_id"],
            ["doctors.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("booking_tasks", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_booking_tasks_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "clinical_profiles",
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("route_review_needed", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("patient_id"),
    )
    op.create_table(
        "doctor_patient_links",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("doctor_id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("active_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("active_to", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["doctor_id"],
            ["doctors.id"],
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("doctor_patient_links", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_doctor_patient_links_doctor_id"), ["doctor_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_doctor_patient_links_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "extractions",
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("model_version", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("message_id"),
    )
    with op.batch_alter_table("extractions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_extractions_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "lab_results",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("analyte", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("reference_low", sa.Float(), nullable=True),
        sa.Column("reference_high", sa.Float(), nullable=True),
        sa.Column("sample_date", sa.Date(), nullable=False),
        sa.Column("entered_by", sa.String(length=16), nullable=False),
        sa.Column("doctor_verified", sa.Boolean(), nullable=False),
        sa.Column("egfr_source", sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("lab_results", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_lab_results_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "medication_intakes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("drug", sa.String(length=200), nullable=True),
        sa.Column("dose_mg", sa.Float(), nullable=True),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("slot", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("missed_reason", sa.String(length=32), nullable=True),
        sa.Column("marked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("patient_id", "slot_date", "slot", name="uq_intake_slot"),
    )
    with op.batch_alter_table("medication_intakes", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_medication_intakes_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "medication_plans",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("drug", sa.String(length=200), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("slots", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["doctors.id"],
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("medication_plans", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_medication_plans_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "messages",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("sender", sa.String(length=16), nullable=False),
        sa.Column("recipient_doctor_id", sa.String(length=64), nullable=True),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extraction_status", sa.String(length=24), nullable=False),
        sa.Column("extraction_error", sa.Text(), nullable=True),
        sa.Column("clarifying_questions", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.create_index("ix_message_patient_time", ["patient_id", "created_at"], unique=False)

    op.create_table(
        "questionnaire_responses",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("instrument", sa.String(length=8), nullable=False),
        sa.Column("administered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_scores", sa.JSON(), nullable=False),
        sa.Column("completion_status", sa.String(length=16), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=True),
        sa.Column("severity_band", sa.String(length=32), nullable=True),
        sa.Column("baseline_score", sa.Integer(), nullable=True),
        sa.Column("delta_from_previous", sa.Integer(), nullable=True),
        sa.Column("delta_from_baseline", sa.Integer(), nullable=True),
        sa.Column("phq9_item9", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("questionnaire_responses", schema=None) as batch_op:
        batch_op.create_index(
            "ix_questionnaire_patient_time", ["patient_id", "administered_at"], unique=False
        )

    op.create_table(
        "questionnaire_schedules",
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("instrument", sa.String(length=8), nullable=False),
        sa.Column("interval_days", sa.Integer(), nullable=False),
        sa.Column("configured_by", sa.String(length=32), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("patient_id", "instrument"),
    )
    op.create_table(
        "risk_signals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("type", sa.String(length=40), nullable=False),
        sa.Column("value", sa.JSON(), nullable=True),
        sa.Column("evidence_span", sa.JSON(), nullable=True),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("risk_signals", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_risk_signals_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "routing_decisions",
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("system_recommendation", sa.String(length=32), nullable=False),
        sa.Column("doctor_decision", sa.String(length=16), nullable=False),
        sa.Column("patient_visible", sa.Boolean(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by", sa.String(length=64), nullable=True),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("patient_id"),
    )
    op.create_table(
        "symptom_events",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("reported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("normalized_type", sa.String(length=32), nullable=False),
        sa.Column("patient_phrase", sa.Text(), nullable=True),
        sa.Column("evidence_span", sa.JSON(), nullable=True),
        sa.Column("polarity", sa.String(length=16), nullable=False),
        sa.Column("experiencer", sa.String(length=16), nullable=False),
        sa.Column("temporality", sa.String(length=16), nullable=False),
        sa.Column("onset_date", sa.Date(), nullable=True),
        sa.Column("onset_precision", sa.String(length=16), nullable=False),
        sa.Column("existed_before_medication", sa.String(length=8), nullable=False),
        sa.Column("worsened_since_start", sa.String(length=8), nullable=False),
        sa.Column("affects_daily_life", sa.String(length=8), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("interferes_with_driving", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("confirmation", sa.String(length=24), nullable=False),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("symptom_events", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_symptom_events_patient_id"), ["patient_id"], unique=False)

    op.create_table(
        "attachments",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("patient_id", sa.String(length=64), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["message_id"],
            ["messages.id"],
        ),
        sa.ForeignKeyConstraint(
            ["patient_id"],
            ["patients.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("attachments", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_attachments_message_id"), ["message_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_attachments_patient_id"), ["patient_id"], unique=False)


def downgrade() -> None:

    with op.batch_alter_table("attachments", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_attachments_patient_id"))
        batch_op.drop_index(batch_op.f("ix_attachments_message_id"))

    op.drop_table("attachments")
    with op.batch_alter_table("symptom_events", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_symptom_events_patient_id"))

    op.drop_table("symptom_events")
    op.drop_table("routing_decisions")
    with op.batch_alter_table("risk_signals", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_risk_signals_patient_id"))

    op.drop_table("risk_signals")
    op.drop_table("questionnaire_schedules")
    with op.batch_alter_table("questionnaire_responses", schema=None) as batch_op:
        batch_op.drop_index("ix_questionnaire_patient_time")

    op.drop_table("questionnaire_responses")
    with op.batch_alter_table("messages", schema=None) as batch_op:
        batch_op.drop_index("ix_message_patient_time")

    op.drop_table("messages")
    with op.batch_alter_table("medication_plans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_medication_plans_patient_id"))

    op.drop_table("medication_plans")
    with op.batch_alter_table("medication_intakes", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_medication_intakes_patient_id"))

    op.drop_table("medication_intakes")
    with op.batch_alter_table("lab_results", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_lab_results_patient_id"))

    op.drop_table("lab_results")
    with op.batch_alter_table("extractions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_extractions_patient_id"))

    op.drop_table("extractions")
    with op.batch_alter_table("doctor_patient_links", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_doctor_patient_links_patient_id"))
        batch_op.drop_index(batch_op.f("ix_doctor_patient_links_doctor_id"))

    op.drop_table("doctor_patient_links")
    op.drop_table("clinical_profiles")
    with op.batch_alter_table("booking_tasks", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_booking_tasks_patient_id"))

    op.drop_table("booking_tasks")
    with op.batch_alter_table("alerts", schema=None) as batch_op:
        batch_op.drop_index("ix_alert_doctor_status")

    op.drop_table("alerts")
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_sessions_user_id"))

    op.drop_table("sessions")
    op.drop_table("patients")
    op.drop_table("idempotency_keys")
    op.drop_table("doctors")
    with op.batch_alter_table("audit_events", schema=None) as batch_op:
        batch_op.drop_index("ix_audit_patient_time")

    op.drop_table("audit_events")
    op.drop_table("admins")
