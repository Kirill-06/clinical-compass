"""Patient State и rule engine: сборка состояния, оценка правил, создание алертов.

Цепочка на каждую запись пациента:
данные → БД → Patient State → rule engine → алерты в рабочую очередь врача
(doctor_priority) + тексты пациенту (patient_action).
"""

from datetime import date

from clinical_compass.db.models import AlertRow
from clinical_compass.domain.derived import ScheduleStatus, latest_by_slot, schedule_status
from clinical_compass.domain.enums import AlertStatus, Instrument, IntakeSlot, Role, RouteDecision
from clinical_compass.domain.rules import RuleContext, RuleEngine
from clinical_compass.domain.state import Alert, PatientState, QuestionnaireSchedule
from clinical_compass.services.context import Deps, Principal, new_id
from clinical_compass.services.realtime import queue_channel

ROUTING_REVIEW_RULE = "R_ROUTING_REVIEW"

SYSTEM_RULES = Principal(user_id="rule-engine", role=Role.ADMIN, name="Rule engine")
"""Служебный субъект для журнала аудита: алерты создаёт rule engine, а не человек."""


class PatientStateService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._engine = RuleEngine(deps.contracts.rules)

    # ------------------------------------------------------------ расписание

    def schedule(self, patient_id: str, instrument: Instrument) -> QuestionnaireSchedule:
        stored = self._d.repos.care.schedule(patient_id, instrument)
        if stored is not None:
            return stored
        return QuestionnaireSchedule(
            instrument=instrument,
            interval_days=self._d.contracts.rules.questionnaire_default_days[instrument],
            configured_by="system_default",
            active=True,
        )

    def schedule_statuses(self, patient_id: str) -> list[ScheduleStatus]:
        patient = self._d.repos.people.patient(patient_id)
        assert patient is not None
        responses = self._d.repos.facts.questionnaires(patient_id)
        return [
            schedule_status(
                self.schedule(patient_id, i),
                responses,
                patient.observation_start,
                self._d.clock.now(),
                utc_offset_hours=self._d.clock.utc_offset_hours,
            )
            for i in Instrument
        ]

    def plan_slots(self, patient_id: str) -> tuple[list[IntakeSlot], date] | None:
        plan = self._d.repos.care.active_plan(patient_id)
        if plan is None:
            return None
        return [IntakeSlot(s) for s in plan.slots], plan.start_date

    # ------------------------------------------------------------ Patient State

    def build(self, patient_id: str) -> PatientState:
        facts = self._d.repos.facts
        return PatientState(
            patient_id=patient_id,
            doctor_id=self._d.repos.people.doctor_of(patient_id, self._d.clock.now()),
            updated_at=self._d.clock.now(),
            questionnaire_schedules=tuple(
                s.schedule.model_copy(update={"next_due_at": s.next_due_at})
                for s in self.schedule_statuses(patient_id)
            ),
            questionnaires=tuple(facts.questionnaires(patient_id)),
            medication_intakes=tuple(latest_by_slot(facts.intakes(patient_id)).values()),
            symptoms=tuple(s for s, _ in facts.symptoms(patient_id)),
            risk_signals=tuple(facts.risk_signals(patient_id)),
            labs=tuple(facts.labs(patient_id)),
            routing=self._d.repos.care.routing(patient_id),
            alerts=tuple(alert_from_row(a) for a in self._d.repos.alerts.for_patient(patient_id)),
        )

    def rule_context(self, patient_id: str) -> RuleContext:
        patient = self._d.repos.people.patient(patient_id)
        return RuleContext(
            sex=patient.sex if patient else None,
            route_review_needed=self._d.repos.care.route_review_needed(patient_id),
        )

    # ------------------------------------------------------------ правила → алерты

    def evaluate(self, patient_id: str, actor: Principal) -> list[AlertRow]:
        """Оценить правила и создать новые алерты.

        Идемпотентно: одно правило по одному набору фактов — один алерт;
        закрытый алерт по тому же факту заново не создаётся.
        """
        self._d.session.flush()
        state = self.build(patient_id)
        existing = self._d.repos.alerts.dedupe_keys(patient_id)
        doctor_id = state.doctor_id
        created: list[AlertRow] = []
        for result in self._engine.evaluate(state, self.rule_context(patient_id)):
            if result.dedupe_key in existing:
                continue
            existing.add(result.dedupe_key)
            now = self._d.clock.now()
            row = AlertRow(
                id=new_id("alert"),
                patient_id=patient_id,
                doctor_id=doctor_id,
                rule_id=result.rule_id,
                rule_version=result.rule_version,
                rule_source=result.source,
                doctor_priority=result.doctor_priority.value,
                patient_action=result.patient_action.value,
                medical_urgency_classified=result.medical_urgency_classified,
                message_template_id=result.message_template_id,
                source_fact_ids=list(result.source_fact_ids),
                dedupe_key=result.dedupe_key,
                # Алерт сразу попадает в рабочую очередь врача (§13.1), без push.
                status=AlertStatus.DELIVERED_TO_WORKPLACE.value,
                created_at=now,
                delivered_to_workplace_at=now,
            )
            self._d.repos.alerts.add(row)
            self._d.audit(SYSTEM_RULES, "alert.created", "alert", row.id, patient_id)
            created.append(row)
            if result.rule_id == ROUTING_REVIEW_RULE:
                self._mark_routing_review(patient_id, actor)
        doctors = {row.doctor_id for row in created if row.doctor_id}
        for doctor_id in sorted(doctors):
            self._d.notify(queue_channel(doctor_id), "alerts", patient_id=patient_id, count=len(created))
        return created

    def _mark_routing_review(self, patient_id: str, actor: Principal) -> None:
        routing = self._d.repos.care.routing(patient_id)
        if routing.system_recommendation == "review_needed":
            return
        self._d.repos.care.save_routing(
            patient_id, routing.model_copy(update={"system_recommendation": "review_needed"})
        )
        self._d.audit(actor, "routing.recommended", "routing", patient_id, patient_id)


def alert_from_row(row: AlertRow) -> Alert:
    return Alert.model_validate(
        {
            "id": row.id,
            "rule_id": row.rule_id,
            "doctor_priority": row.doctor_priority,
            "patient_action": row.patient_action,
            "source_fact_ids": tuple(row.source_fact_ids),
            "message_template_id": row.message_template_id,
            "rule_version": row.rule_version,
            "created_at": row.created_at,
            "delivered_to_workplace_at": row.delivered_to_workplace_at,
            "viewed_at": row.viewed_at,
            "status": row.status,
        }
    )


def routing_visible(decision: RouteDecision) -> bool:
    """Пациент видит маршрут только при решении врача `preferred` или `required` (§14)."""
    return decision in {RouteDecision.PREFERRED, RouteDecision.REQUIRED}
