"""Представления для экранов (JSON). Каждое строится из данных, к которым у роли уже проверен доступ.

Подписи и тексты берутся из контрактов: правила — `vocabulary.rule_titles`,
тексты пациенту — реестр шаблонов. Медицинских выводов здесь нет.
"""

from datetime import datetime
from typing import Any

from clinical_compass.db.models import (
    AlertRow,
    AttachmentRow,
    BookingTaskRow,
    MessageRow,
    PatientRow,
    SymptomEventRow,
)
from clinical_compass.domain.derived import Adherence, ScheduleStatus, adherence, latest_by_slot
from clinical_compass.domain.enums import (
    FactSource,
    Instrument,
    IntakeStatus,
    PatientAction,
    RouteDecision,
    Tri,
)
from clinical_compass.domain.rules import PROFILE_FACT_ID
from clinical_compass.domain.state import QuestionnaireResponse, SymptomEvent
from clinical_compass.services.context import Deps
from clinical_compass.services.state import PatientStateService, alert_from_row

Json = dict[str, Any]

_TRI = {Tri.YES: "да", Tri.NO: "нет", Tri.UNKNOWN: "неизвестно"}


def iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


class Presenter:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._state = PatientStateService(deps)

    # ------------------------------------------------------------ базовые блоки

    def patient_brief(self, p: PatientRow) -> Json:
        return {
            "id": p.id,
            "display_id": p.display_id,
            "full_name": p.full_name,
            "first_name": p.first_name,
            "birth_year": p.birth_year,
            "observation_start": iso(p.observation_start),
        }

    def schedule(self, s: ScheduleStatus) -> Json:
        definition = self._d.contracts.instruments[s.schedule.instrument]
        return {
            **s.to_json(),
            "label": definition.label,
            "title": definition.title,
            "item_count": definition.item_count,
        }

    def schedules(self, patient_id: str, *, active_only: bool) -> list[Json]:
        return [
            self.schedule(s)
            for s in self._state.schedule_statuses(patient_id)
            if s.schedule.active or not active_only
        ]

    def plan(self, patient_id: str) -> Json | None:
        plan = self._d.repos.care.active_plan(patient_id)
        if plan is None:
            return None
        return {
            "id": plan.id,
            "drug": plan.drug,
            "instructions": plan.instructions,
            "slots": list(plan.slots),
            "start_date": plan.start_date.isoformat(),
        }

    def response(self, q: QuestionnaireResponse) -> Json:
        definition = self._d.contracts.instruments[q.instrument]
        return {
            **q.to_schema(),
            "label": definition.label,
            "severity_label": definition.band_for(q.total_score).label if q.total_score is not None else None,
            "max_score": definition.max_score,
        }

    def symptom(self, s: SymptomEvent) -> Json:
        c = self._d.contracts
        return {
            **s.to_schema(),
            "label": c.label("symptom_types", s.normalized_type.value),
            "out_of_scope": not s.normalized_type.in_leaflet_set,
            "source_label": c.label("sources", s.source.value),
            "confirmation_label": c.label("confirmations", s.confirmation.value),
        }

    def adherence(self, patient_id: str, days: int) -> Adherence | None:
        plan = self._state.plan_slots(patient_id)
        if plan is None:
            return None
        slots, start = plan
        return adherence(self._d.repos.facts.intakes(patient_id), slots, start, self._d.clock.today(), days)

    def today_intakes(self, patient_id: str) -> Json:
        today = self._d.clock.today()
        plan = self._state.plan_slots(patient_id)
        if plan is None:
            return {"date": today.isoformat(), "slots": []}
        latest = latest_by_slot(self._d.repos.facts.intakes(patient_id))
        return {
            "date": today.isoformat(),
            "slots": [
                {
                    "slot": slot.value,
                    "label": self._d.contracts.label("intake_slots", slot.value),
                    "intake": i.to_schema() if (i := latest.get((today, slot))) else None,
                }
                for slot in plan[0]
            ],
        }

    def message(self, m: MessageRow, attachments: list[AttachmentRow], *, for_patient: bool) -> Json:
        data: Json = {
            "id": m.id,
            "patient_id": m.patient_id,
            "text": m.text,
            "attachments": [self.attachment(a) for a in attachments],
            "created_at": iso(m.created_at),
        }
        if not for_patient:
            data["extraction_status"] = m.extraction_status
            data["clarifying_questions"] = list(m.clarifying_questions)
        return data

    @staticmethod
    def attachment(a: AttachmentRow) -> Json:
        return {
            "id": a.id,
            "filename": a.filename,
            "mime_type": a.mime_type,
            "size": a.size,
            "uploaded_at": iso(a.uploaded_at),
        }

    def messages(self, patient_id: str, *, for_patient: bool) -> list[Json]:
        rows = self._d.repos.messages.for_patient(patient_id)
        attachments = self._d.repos.messages.attachments(m.id for m in rows)
        return [self.message(m, attachments[m.id], for_patient=for_patient) for m in rows]

    # ------------------------------------------------------------ тексты пациенту

    def notice(self, row: AlertRow) -> Json:
        template = self._d.contracts.template(row.message_template_id)
        return {
            "alert_id": row.id,
            "created_at": iso(row.created_at),
            "patient_action": row.patient_action,
            "template": template.to_json() if template else None,
        }

    def notices(self, rows: list[AlertRow]) -> list[Json]:
        return [self.notice(r) for r in rows if r.patient_action != PatientAction.NONE.value]

    def visible_routing(self, patient_id: str) -> Json | None:
        routing = self._d.repos.care.routing(patient_id)
        if not routing.patient_visible:
            return None
        template_id = (
            "routing_required_v1"
            if routing.doctor_decision is RouteDecision.REQUIRED
            else "routing_preferred_v1"
        )
        template = self._d.contracts.template(template_id)
        return {**routing.to_schema(), "template": template.to_json() if template else None}

    # ------------------------------------------------------------ алерты и «Почему?»

    def alert(self, row: AlertRow, *, pinned: bool | None = None) -> Json:
        patient = self._d.repos.people.patient(row.patient_id)
        assert patient is not None
        template = self._d.contracts.template(row.message_template_id)
        data: Json = {
            "alert": alert_from_row(row).to_schema(),
            "patient": self.patient_brief(patient),
            "rule_title": self._d.contracts.rule_title(row.rule_id),
            "rule_source": row.rule_source,
            "medical_urgency_classified": row.medical_urgency_classified,
            "why": [self.fact_summary(row.patient_id, f) for f in row.source_fact_ids],
            "patient_template": template.to_json() if template else None,
            "acknowledged_at": iso(row.acknowledged_at),
            "acknowledged_by": row.acknowledged_by,
            "resolved_at": iso(row.resolved_at),
            "resolved_by": row.resolved_by,
        }
        if pinned is not None:
            data["pinned"] = pinned
        return data

    def fact_summary(self, patient_id: str, fact_id: str) -> Json:
        """Пересказ факта Patient State для кнопки «Почему?»."""
        if fact_id == PROFILE_FACT_ID:
            return {
                "id": fact_id,
                "kind": "clinical_profile",
                "summary": "Клинический профиль: требуется рассмотреть маршрутизацию",
            }
        for describe in (
            self._questionnaire_fact,
            self._symptom_fact,
            self._risk_fact,
            self._intake_fact,
            self._lab_fact,
        ):
            if (summary := describe(patient_id, fact_id)) is not None:
                return {"id": fact_id, **summary}
        return {"id": fact_id, "kind": "unknown", "summary": f"Факт {fact_id}"}

    def _questionnaire_fact(self, patient_id: str, fact_id: str) -> Json | None:
        q = self._d.repos.facts.questionnaire(patient_id, fact_id)
        if q is None:
            return None
        definition = self._d.contracts.instruments[q.instrument]
        parts = [f"{definition.label}: {q.total_score} из {definition.max_score}"]
        if q.delta_from_previous is not None:
            parts.append(f"изменение {q.delta_from_previous:+d}")
        if q.phq9_item9 is not None:
            parts.append(f"вопрос 9: {q.phq9_item9}")
        return {
            "kind": "questionnaire",
            "at": iso(q.administered_at),
            "summary": ", ".join(parts),
            "source": self._d.contracts.label("sources", q.source.value),
        }

    def _symptom_fact(self, patient_id: str, fact_id: str) -> Json | None:
        s = self._d.repos.facts.symptom(patient_id, fact_id)
        if s is None:
            return None
        c = self._d.contracts
        phrase = f" — «{s.patient_phrase}»" if s.patient_phrase else ""
        return {
            "kind": "symptom",
            "summary": f"{c.label('symptom_types', s.normalized_type.value)}{phrase}; "
            f"мешает обычным делам: {_TRI[s.affects_daily_life]}",
            "source": c.label("sources", s.source.value),
            "confirmation": c.label("confirmations", s.confirmation.value),
        }

    def _risk_fact(self, patient_id: str, fact_id: str) -> Json | None:
        r = self._d.repos.facts.risk_signal(patient_id, fact_id)
        if r is None:
            return None
        c = self._d.contracts
        span = f" — «{r.evidence_span.text}»" if r.evidence_span else ""
        return {
            "kind": "risk_signal",
            "at": iso(r.created_at),
            "summary": f"Сигнал: {c.label('risk_signals', r.type.value)}{span}",
            "source": c.label("sources", r.source.value),
            "confirmation": c.label("confirmations", r.confirmation.value),
        }

    def _intake_fact(self, patient_id: str, fact_id: str) -> Json | None:
        i = self._d.repos.facts.intake(patient_id, fact_id)
        if i is None:
            return None
        c = self._d.contracts
        reason = f" — {c.label('missed_reasons', i.missed_reason.value)}" if i.missed_reason else ""
        verb = "принят" if i.status is IntakeStatus.TAKEN else "пропущен"
        slot = (c.label("intake_slots", i.slot.value) or "").lower()
        return {
            "kind": "intake",
            "summary": f"Приём {i.slot_date.isoformat()}, {slot}: {verb}{reason.lower()}",
            "source": c.label("sources", i.source.value),
        }

    def _lab_fact(self, patient_id: str, fact_id: str) -> Json | None:
        lab = self._d.repos.facts.lab(patient_id, fact_id)
        if lab is None:
            return None
        ref = f" (референс до {lab.reference_high:g})" if lab.reference_high is not None else ""
        name = self._d.contracts.label("lab_analytes", lab.analyte.value)
        return {
            "kind": "lab",
            "summary": f"{name} {lab.value:g} {lab.unit}{ref}, проба {lab.sample_date.isoformat()}",
            "source": "проверено врачом" if lab.doctor_verified else "внесено пациентом, не проверено",
        }

    # ------------------------------------------------------------ лента и задачи

    def timeline(self, patient_id: str, *, for_patient: bool) -> list[Json]:
        """Каждый факт — одна запись, от новых к старым."""
        c, facts = self._d.contracts, self._d.repos.facts
        events: list[Json] = []

        def add(
            at: datetime | None, kind: str, title: str, detail: str | None = None, author: str = "Пациент"
        ) -> None:
            if at is not None:
                events.append(
                    {"at": iso(at), "kind": kind, "title": title, "detail": detail, "author": author}
                )

        for q in facts.questionnaires(patient_id):
            definition = c.instruments[q.instrument]
            band = definition.band_for(q.total_score).label if q.total_score is not None else None
            add(
                q.administered_at,
                "questionnaire",
                f"{definition.label} заполнен: {q.total_score} из {definition.max_score}",
                band,
            )
        for i in latest_by_slot(facts.intakes(patient_id)).values():
            slot = (c.label("intake_slots", i.slot.value) or "").lower()
            verb = "принял" if i.status is IntakeStatus.TAKEN else "пропустил"
            reason = c.label("missed_reasons", i.missed_reason.value) if i.missed_reason else None
            add(i.marked_at, "intake", f"Приём {i.slot_date.isoformat()}, {slot}: {verb}", reason)
        for symptom, row in facts.symptoms(patient_id):
            if for_patient and symptom.source is not FactSource.FORM:
                continue
            add(
                row.reported_at,
                "symptom",
                f"Самочувствие: {c.label('symptom_types', symptom.normalized_type.value)}",
                symptom.patient_phrase,
            )
        for m in self._d.repos.messages.for_patient(patient_id):
            files = len(self._d.repos.messages.attachments([m.id])[m.id])
            title = f"Сообщение врачу, файлов: {files}" if files else "Сообщение врачу"
            add(m.created_at, "message", title, m.text)
        if not for_patient:
            for a in self._d.repos.alerts.for_patient(patient_id):
                add(
                    a.created_at,
                    "alert",
                    f"Правило {a.rule_id}: {c.rule_title(a.rule_id)}",
                    f"Приоритет {a.doctor_priority}, действие пациенту {a.patient_action}",
                    "Rule engine",
                )
                if a.resolved_at:
                    add(
                        a.resolved_at,
                        "alert_resolved",
                        f"Алерт {a.rule_id} закрыт",
                        author=a.resolved_by or "—",
                    )
                elif a.acknowledged_at:
                    add(
                        a.acknowledged_at,
                        "alert_ack",
                        f"Алерт {a.rule_id} принят в работу",
                        author=a.acknowledged_by or "—",
                    )
            routing = self._d.repos.care.routing(patient_id)
            if routing.confirmed_at:
                add(
                    routing.confirmed_at,
                    "routing",
                    f"Решение по маршрутизации: {routing.doctor_decision.value}",
                    author="Врач",
                )
        events.sort(key=lambda e: e["at"], reverse=True)
        return events

    def booking(self, task: BookingTaskRow) -> Json:
        """Для администратора — только контакт и срок, без клинических данных (§15)."""
        patient = self._d.repos.people.patient(task.patient_id)
        doctor = self._d.repos.people.doctor(task.requested_by_doctor_id)
        assert patient is not None
        return {
            "id": task.id,
            "patient_id": task.patient_id,
            "patient_name": patient.full_name,
            "patient_phone": patient.phone,
            "requested_by": doctor.short_name if doctor else None,
            "deadline": iso(task.deadline),
            "status": task.status,
            "created_at": iso(task.created_at),
            "updated_at": iso(task.updated_at),
        }

    def latest_score(self, responses: list[QuestionnaireResponse], instrument: Instrument) -> Json | None:
        done = [r for r in responses if r.instrument is instrument and r.total_score is not None]
        if not done:
            return None
        last = done[-1]
        assert last.total_score is not None
        definition = self._d.contracts.instruments[instrument]
        return {
            "score": last.total_score,
            "max_score": definition.max_score,
            "severity_label": definition.band_for(last.total_score).label,
            "delta_from_previous": last.delta_from_previous,
            "previous_score": done[-2].total_score if len(done) > 1 else None,
            "administered_at": iso(last.administered_at),
            "phq9_item9": last.phq9_item9,
        }

    def symptom_rows(self, patient_id: str, *, form_only: bool) -> list[Json]:
        rows: list[tuple[SymptomEvent, SymptomEventRow]] = self._d.repos.facts.symptoms(patient_id)
        return [self.symptom(s) for s, _ in reversed(rows) if not form_only or s.source is FactSource.FORM]
