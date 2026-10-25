"""Сценарии врача: пациенты, рабочая очередь, карточка, решения."""

from datetime import datetime, timedelta

from clinical_compass.db.models import AlertRow, BookingTaskRow
from clinical_compass.domain.enums import (
    AlertStatus,
    BookingStatus,
    DoctorPriority,
    Instrument,
    RouteDecision,
)
from clinical_compass.domain.state import RoutingDecision
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal, new_id
from clinical_compass.services.errors import ForbiddenError, InvalidInputError, NotFoundError
from clinical_compass.services.presenter import Json, Presenter
from clinical_compass.services.state import PatientStateService, routing_visible

_PRE_ACK = {AlertStatus.CREATED, AlertStatus.DELIVERED_TO_WORKPLACE, AlertStatus.VIEWED}


class DoctorService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._state = PatientStateService(deps)
        self._present = Presenter(deps)

    # ------------------------------------------------------------ списки

    def patients(self, principal: Principal) -> list[Json]:
        rows: list[Json] = []
        for patient_id in self._access.doctor_patient_ids(principal):
            patient = self._access.patient(patient_id)
            responses = self._d.repos.facts.questionnaires(patient_id)
            open_alerts = [
                a for a in self._d.repos.alerts.for_patient(patient_id) if AlertStatus(a.status).is_open
            ]
            top = max(open_alerts, key=lambda a: DoctorPriority(a.doctor_priority).rank, default=None)
            adherence = self._present.adherence(patient_id, 7)
            timeline = self._present.timeline(patient_id, for_patient=True)
            rows.append(
                {
                    "patient": self._present.patient_brief(patient),
                    "GAD7": self._present.latest_score(responses, Instrument.GAD7),
                    "PHQ9": self._present.latest_score(responses, Instrument.PHQ9),
                    "schedules": self._present.schedules(patient_id, active_only=True),
                    "adherence_7d": adherence.to_json(include_slots=True) if adherence else None,
                    "open_alerts": len(open_alerts),
                    "top_alert": self._present.alert(top) if top else None,
                    "routing": self._d.repos.care.routing(patient_id).to_schema(),
                    "last_activity": timeline[0] if timeline else None,
                    "unread_messages": self._d.repos.messages.unread_count(patient_id, sender="patient"),
                }
            )

        def order(row: Json) -> tuple[int, str]:
            top = row["top_alert"]
            rank = DoctorPriority(top["alert"]["doctor_priority"]).rank if top else -1
            return (-rank, row["patient"]["full_name"])

        return sorted(rows, key=order)

    def queue(self, principal: Principal, *, include_resolved: bool = False) -> list[Json]:
        """Рабочая очередь (§13): urgent закреплены до принятия, затем по приоритету, внутри — FIFO."""
        patient_ids = self._access.doctor_patient_ids(principal)
        rows = self._d.repos.alerts.for_patients(patient_ids, include_resolved=include_resolved)

        def pinned(row: AlertRow) -> bool:
            return (
                self._d.contracts.rules.urgent_pinned_until_acknowledged
                and row.doctor_priority == DoctorPriority.URGENT.value
                and AlertStatus(row.status) in _PRE_ACK
            )

        rows.sort(key=lambda r: (not pinned(r), -DoctorPriority(r.doctor_priority).rank, r.created_at))
        return [self._present.alert(r, pinned=pinned(r)) for r in rows]

    # ------------------------------------------------------------ карточка

    def dossier(self, principal: Principal, patient_id: str) -> Json:
        patient = self._access.require_doctor_for(principal, patient_id)
        state = self._state.build(patient_id).to_schema()
        schema_errors = self._d.contracts.schema_errors(state)
        self._d.audit(principal, "patient.viewed", "patient", patient_id, patient_id)
        adherence_7 = self._present.adherence(patient_id, 7)
        adherence_14 = self._present.adherence(patient_id, 14)
        return {
            "patient": {**self._present.patient_brief(patient), "sex": patient.sex},
            "doctor": {"id": principal.user_id, "short_name": principal.name},
            "patient_state": state,
            "schema_valid": not schema_errors,
            "schema_errors": schema_errors,
            "schedules": self._present.schedules(patient_id, active_only=False),
            "questionnaires": [
                self._present.response(q) for q in self._d.repos.facts.questionnaires(patient_id)
            ],
            "plan": self._present.plan(patient_id),
            "adherence_7d": adherence_7.to_json() if adherence_7 else None,
            "adherence_14d": adherence_14.to_json(include_slots=True) if adherence_14 else None,
            "symptoms": self._present.symptom_rows(patient_id, form_only=False),
            "messages": self._present.messages(patient_id, for_patient=False),
            "labs": [lab.to_schema() for lab in self._d.repos.facts.labs(patient_id)],
            "alerts": [self._present.alert(a) for a in self._d.repos.alerts.for_patient(patient_id)],
            "routing": self._d.repos.care.routing(patient_id).to_schema(),
            "bookings": [self._present.booking(b) for b in self._d.repos.bookings.for_patient(patient_id)],
            "timeline": self._present.timeline(patient_id, for_patient=False),
            "rule_version": self._d.contracts.rules.rule_version,
        }

    def patient_state(self, principal: Principal, patient_id: str) -> Json:
        self._access.require_read(principal, patient_id)
        state = self._state.build(patient_id).to_schema()
        return {"patient_state": state, "schema_errors": self._d.contracts.schema_errors(state)}

    def audit(self, principal: Principal, patient_id: str) -> list[Json]:
        self._access.require_doctor_for(principal, patient_id)
        return [
            {
                "seq": e.id,
                "at": e.at.isoformat(),
                "actor": e.actor,
                "action": e.action,
                "kind": e.entity,
                "id": e.entity_id,
                "patient_id": e.patient_id,
            }
            for e in self._d.repos.audit.for_patient(patient_id)
        ]

    # ------------------------------------------------------------ решения врача

    def alert_action(self, principal: Principal, alert_id: str, action: str) -> Json:
        """Жизненный цикл алерта: view → acknowledge → resolve, с временем и автором."""
        row = self._d.repos.alerts.get(alert_id)
        if row is None:
            raise NotFoundError("Алерт не найден")
        self._access.require_doctor_for(principal, row.patient_id)
        now = self._d.clock.now()
        status = AlertStatus(row.status)
        if action == "view":
            row.viewed_at = row.viewed_at or now
            if status in {AlertStatus.CREATED, AlertStatus.DELIVERED_TO_WORKPLACE}:
                row.status = AlertStatus.VIEWED.value
        elif action == "acknowledge":
            row.viewed_at = row.viewed_at or now
            if status is not AlertStatus.RESOLVED:
                row.status = AlertStatus.ACKNOWLEDGED.value
            row.acknowledged_at = row.acknowledged_at or now
            row.acknowledged_by = row.acknowledged_by or principal.name
        elif action == "resolve":
            row.viewed_at = row.viewed_at or now
            row.status = AlertStatus.RESOLVED.value
            row.acknowledged_at = row.acknowledged_at or now
            row.acknowledged_by = row.acknowledged_by or principal.name
            row.resolved_at = now
            row.resolved_by = principal.name
        else:
            raise InvalidInputError(f"Неизвестное действие {action}")
        self._d.audit(principal, f"alert.{action}", "alert", row.id, row.patient_id)
        return self._present.alert(row)

    def set_schedule(
        self,
        principal: Principal,
        patient_id: str,
        instrument: Instrument,
        interval_days: int | None,
        active: bool | None,
    ) -> Json:
        self._access.require_doctor_for(principal, patient_id)
        if not self._d.contracts.rules.doctor_configurable_schedule:
            raise ForbiddenError("Интервал опросников не настраивается")
        if interval_days is not None and not 1 <= interval_days <= 180:
            raise InvalidInputError("Интервал — от 1 до 180 дней")
        current = self._state.schedule(patient_id, instrument)
        updated = current.model_copy(
            update={
                "interval_days": interval_days if interval_days is not None else current.interval_days,
                "active": active if active is not None else current.active,
                "configured_by": "doctor",
            }
        )
        self._d.repos.care.save_schedule(patient_id, updated, self._d.clock.now())
        self._d.audit(
            principal, "schedule.updated", "schedule", f"{patient_id}|{instrument.value}", patient_id
        )
        self._d.session.flush()
        status = next(
            s for s in self._state.schedule_statuses(patient_id) if s.schedule.instrument is instrument
        )
        return status.to_json()

    def set_routing(self, principal: Principal, patient_id: str, decision: RouteDecision) -> Json:
        """Решение принимает врач; пациент видит маршрут только после подтверждения (§14)."""
        self._access.require_doctor_for(principal, patient_id)
        if decision is RouteDecision.PENDING:
            raise InvalidInputError("Выберите решение")
        current = self._d.repos.care.routing(patient_id)
        updated = RoutingDecision(
            system_recommendation=current.system_recommendation,
            doctor_decision=decision,
            patient_visible=routing_visible(decision),
            confirmed_at=self._d.clock.now(),
        )
        self._d.repos.care.save_routing(patient_id, updated, confirmed_by=principal.user_id)
        self._d.audit(principal, "routing.confirmed", "routing", patient_id, patient_id)
        return updated.to_schema()

    def set_contact_deadline(self, principal: Principal, patient_id: str, deadline: datetime) -> Json:
        """Срок контакта → задача администратору без клинических данных (§15)."""
        self._access.require_doctor_for(principal, patient_id)
        now = self._d.clock.now()
        if deadline < now - timedelta(hours=1):
            raise InvalidInputError("Срок контакта не может быть в прошлом")
        task = BookingTaskRow(
            id=new_id("booking"),
            patient_id=patient_id,
            requested_by_doctor_id=principal.user_id,
            deadline=deadline,
            status=BookingStatus.OPEN.value,
            created_at=now,
            updated_at=now,
        )
        self._d.repos.bookings.add(task)
        self._d.audit(principal, "booking.created", "booking", task.id, patient_id)
        return self._present.booking(task)
