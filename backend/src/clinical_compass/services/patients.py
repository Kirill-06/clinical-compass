"""Сценарии пациента: опросники, приём препарата, самочувствие, сообщения врачу."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

from clinical_compass.db.models import AttachmentRow, ExtractionRow, MessageRow
from clinical_compass.domain.derived import DueStatus, deltas_for
from clinical_compass.domain.enums import (
    CompletionStatus,
    Confirmation,
    Experiencer,
    FactSource,
    Instrument,
    IntakeSlot,
    IntakeStatus,
    LabAnalyte,
    MissedReason,
    Polarity,
    Role,
    Severity,
    SymptomType,
    Temporality,
    Tri,
)
from clinical_compass.domain.extraction import (
    FreeTextExtraction,
    IntakeWindow,
    MockLexiconExtractor,
    facts_from_extraction,
)
from clinical_compass.domain.instruments import ScoringError, score_items
from clinical_compass.domain.state import LabResult, MedicationIntake, QuestionnaireResponse, SymptomEvent
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal, new_id
from clinical_compass.services.errors import ConflictError, InvalidInputError, NotFoundError
from clinical_compass.services.presenter import Json, Presenter
from clinical_compass.services.realtime import chat_channel
from clinical_compass.services.safety import SafetyService
from clinical_compass.services.state import PatientStateService

logger = logging.getLogger(__name__)

_SAFETY_NET = MockLexiconExtractor()
"""Встроенный словарь красных флагов: срабатывает, если основной экстрактор не справился."""


@dataclass(frozen=True)
class Upload:
    filename: str
    mime_type: str
    data: bytes


@dataclass(frozen=True)
class SymptomReport:
    type: SymptomType
    phrase: str | None = None
    affects_daily_life: Tri = Tri.UNKNOWN
    severity: Severity = Severity.UNKNOWN
    worsened_since_start: Tri = Tri.UNKNOWN
    onset_date: date | None = None


class PatientService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._state = PatientStateService(deps)
        self._present = Presenter(deps)

    # ------------------------------------------------------------ чтение

    def dashboard(self, principal: Principal, patient_id: str) -> Json:
        patient = self._access.require_self(principal, patient_id)
        doctor_id = self._access.doctor_of(patient_id)
        doctor = self._d.repos.people.doctor(doctor_id) if doctor_id else None
        open_alerts = [a for a in self._d.repos.alerts.for_patient(patient_id) if a.status != "resolved"]
        return {
            "patient": self._present.patient_brief(patient),
            "doctor": {"id": doctor.id, "short_name": doctor.short_name} if doctor else None,
            "schedules": self._present.schedules(patient_id, active_only=True),
            "plan": self._present.plan(patient_id),
            "today": self._present.today_intakes(patient_id),
            "notices": self._present.notices(open_alerts),
            "emergency_alert_ids": SafetyService(self._d).pending_for(patient_id),
            "unread_messages": self._d.repos.messages.unread_count(patient_id, sender="doctor"),
            "routing": self._present.visible_routing(patient_id),
            "recent": self._present.timeline(patient_id, for_patient=True)[:6],
        }

    def history(self, principal: Principal, patient_id: str) -> Json:
        self._access.require_self(principal, patient_id)
        adherence = self._present.adherence(patient_id, 14)
        return {
            "questionnaires": [
                self._present.response(q) for q in reversed(self._d.repos.facts.questionnaires(patient_id))
            ],
            "plan": self._present.plan(patient_id),
            "adherence": adherence.to_json(include_slots=True) if adherence else None,
            "messages": self._present.messages(patient_id, for_patient=True),
            "symptoms": self._present.symptom_rows(patient_id, form_only=True),
        }

    def attachment(
        self, principal: Principal, patient_id: str, attachment_id: str
    ) -> tuple[AttachmentRow, bytes]:
        self._access.require_read(principal, patient_id)
        row = self._d.repos.messages.attachment(attachment_id)
        if row is None or row.patient_id != patient_id:
            raise NotFoundError("Файл не найден")
        data = self._d.storage.get(row.storage_key)
        if data is None:
            raise NotFoundError("Содержимое файла недоступно")
        return row, data

    # ------------------------------------------------------------ запись

    def idempotent(self, principal: Principal, key: str | None, action: Callable[[], Json]) -> Json:
        """Повторная отправка с тем же ключом возвращает прежний ответ, а не создаёт дубль."""
        if not key:
            return action()
        full_key = f"{principal.user_id}|{key}"
        prior = self._d.repos.idempotency.get(full_key)
        if prior is not None:
            return {**prior, "duplicate": True}
        response = action()
        self._d.repos.idempotency.save(full_key, response, self._d.clock.now())
        return response

    def submit_questionnaire(
        self, principal: Principal, patient_id: str, instrument: Instrument, items: list[int]
    ) -> Json:
        self._access.require_self(principal, patient_id)
        status = next(
            s for s in self._state.schedule_statuses(patient_id) if s.schedule.instrument is instrument
        )
        definition = self._d.contracts.instruments[instrument]
        if not status.schedule.active:
            raise ConflictError(f"{definition.label} не назначен врачом")
        if status.status is DueStatus.UPCOMING:
            raise ConflictError(
                f"{definition.label} пока не назначен. Следующий — {status.next_due_at.date().isoformat()}"
            )
        try:
            score = score_items(definition, items)
        except ScoringError as exc:
            raise InvalidInputError(str(exc)) from exc
        deltas = deltas_for(instrument, score.total, self._d.repos.facts.questionnaires(patient_id))
        response = QuestionnaireResponse(
            id=new_id("q"),
            instrument=instrument,
            administered_at=self._d.clock.now(),
            item_scores=tuple(items),
            completion_status=CompletionStatus.COMPLETE,
            total_score=score.total,
            severity_band=score.band.code,
            baseline_score=deltas.baseline,
            delta_from_previous=deltas.from_previous,
            delta_from_baseline=deltas.from_baseline,
            phq9_item9=score.phq9_item9,
            source=FactSource.FORM,
        )
        self._d.repos.facts.add_questionnaire(patient_id, response)
        self._d.audit(principal, "questionnaire.submitted", "questionnaire", response.id, patient_id)
        alerts = self._state.evaluate(patient_id, principal)
        return {
            "response": self._present.response(response),
            "patient_notices": self._present.notices(alerts),
        }

    def mark_intake(
        self,
        principal: Principal,
        patient_id: str,
        *,
        slot_date: date,
        slot: IntakeSlot,
        status: IntakeStatus,
        missed_reason: MissedReason | None,
    ) -> Json:
        self._access.require_self(principal, patient_id)
        if status is IntakeStatus.UNKNOWN:
            raise InvalidInputError("Отметка должна быть «принял» или «пропустил»")
        days_back = (self._d.clock.today() - slot_date).days
        if not 0 <= days_back <= self._d.limits.intake_backfill_days:
            raise InvalidInputError("Отметить можно только сегодняшний и два предыдущих дня")
        plan = self._d.repos.care.active_plan(patient_id)
        if plan is None:
            raise ConflictError("План приёма не назначен")
        if slot.value not in plan.slots:
            raise InvalidInputError("Этот приём не входит в назначенную схему")
        previous = self._d.repos.facts.intake_for_slot(patient_id, slot_date, slot)
        intake = MedicationIntake(
            id=previous.id if previous else new_id("intake"),
            drug=plan.drug,
            slot_date=slot_date,
            slot=slot,
            status=status,
            missed_reason=(missed_reason or MissedReason.UNKNOWN) if status is IntakeStatus.MISSED else None,
            marked_at=self._d.clock.now(),
            source=FactSource.FORM,
            confirmation=Confirmation.PATIENT_CONFIRMED,
        )
        self._d.repos.facts.upsert_intake(patient_id, intake)
        action = "intake.corrected" if previous else "intake.marked"
        self._d.audit(principal, action, "intake", intake.id, patient_id)
        alerts = self._state.evaluate(patient_id, principal)
        return {
            "intake": intake.to_schema(),
            "corrected": previous is not None,
            "patient_notices": self._present.notices(alerts),
        }

    def report_symptom(self, principal: Principal, patient_id: str, report: SymptomReport) -> Json:
        self._access.require_self(principal, patient_id)
        phrase = (report.phrase or "").strip() or None
        if report.type is SymptomType.OTHER_UNLISTED and phrase is None:
            raise InvalidInputError("Опишите, что вас беспокоит")
        if phrase and len(phrase) > self._d.limits.max_phrase_length:
            raise InvalidInputError(f"Описание длиннее {self._d.limits.max_phrase_length} символов")
        symptom = SymptomEvent(
            id=new_id("sym"),
            normalized_type=report.type,
            patient_phrase=phrase,
            polarity=Polarity.PRESENT,
            experiencer=Experiencer.PATIENT,
            temporality=Temporality.CURRENT,
            onset_date=report.onset_date,
            onset_precision="day" if report.onset_date else "unknown",
            worsened_since_start=report.worsened_since_start,
            affects_daily_life=report.affects_daily_life,
            severity=report.severity,
            status="ongoing",
            source=FactSource.FORM,
            confirmation=Confirmation.PATIENT_CONFIRMED,
        )
        self._d.repos.facts.add_symptom(patient_id, symptom, self._d.clock.now())
        self._d.audit(principal, "symptom.reported", "symptom", symptom.id, patient_id)
        if report.type is SymptomType.OTHER_UNLISTED and phrase:
            self._extract_symptom_risks(principal, patient_id, symptom.id, phrase)
        alerts = self._state.evaluate(patient_id, principal)
        return {"symptom": symptom.to_schema(), "patient_notices": self._present.notices(alerts)}

    def _extract_symptom_risks(
        self, principal: Principal, patient_id: str, symptom_id: str, text: str
    ) -> None:
        """Check free form symptom text for risks without creating duplicate AI facts."""
        now = self._d.clock.now()
        try:
            extraction = self._d.extractor.extract(
                message_id=symptom_id, patient_id=patient_id, timestamp=now, text=text
            )
        except Exception as exc:
            logger.warning("Извлечение рисков из симптома %s не удалось: %s", symptom_id, exc)
            if isinstance(self._d.extractor, MockLexiconExtractor):
                return
            extraction = _SAFETY_NET.extract(
                message_id=symptom_id, patient_id=patient_id, timestamp=now, text=text
            )
        self._save_symptom_risks(principal, patient_id, extraction)

    def _save_symptom_risks(
        self, principal: Principal, patient_id: str, extraction: FreeTextExtraction
    ) -> None:
        risk_only = extraction.model_copy(
            update={"entities": tuple(e for e in extraction.entities if e.type == "risk_signal")}
        )
        for signal in facts_from_extraction(risk_only, new_id).risk_signals:
            self._d.repos.facts.add_risk_signal(patient_id, signal)
            self._d.audit(principal, "risk_signal.extracted", "risk_signal", signal.id, patient_id)

    def send_message(
        self, principal: Principal, patient_id: str, text: str | None, files: list[Upload]
    ) -> Json:
        """Сообщение сохраняется ДО обработки ИИ; сбой извлечения его не теряет (§21)."""
        self._access.require_self(principal, patient_id)
        body = (text or "").strip()
        self._validate_message(body, files)
        now = self._d.clock.now()
        message = MessageRow(
            id=new_id("msg"),
            patient_id=patient_id,
            sender="patient",
            recipient_doctor_id=self._access.doctor_of(patient_id),
            text=body or None,
            created_at=now,
            extraction_status="pending" if body else "not_applicable",
            clarifying_questions=[],
        )
        attachments = [self._store_file(message.id, patient_id, f) for f in files]
        self._d.repos.messages.add(message, *attachments)
        self._d.audit(principal, "message.sent", "message", message.id, patient_id)
        self._d.session.flush()

        if body:
            self._extract_facts(principal, message, body)
        self._d.notify(chat_channel(patient_id), "message", message_id=message.id, sender="patient")

        alerts = self._state.evaluate(patient_id, principal)
        return {
            "message": {
                **self._present.message(message, attachments, for_patient=False),
                "sender": "patient",
            },
            "clarifying_questions": list(message.clarifying_questions),
            "patient_notices": self._present.notices(alerts),
        }

    def _extract_facts(self, principal: Principal, message: MessageRow, text: str) -> None:
        """Извлечь факты из текста сообщения. Сообщение уже сохранено и не теряется.

        Любой сбой AI-слоя (недоступен, таймаут, ответ не разбирается) помечает
        сообщение как «не обработано», а текст всё равно проверяется встроенным
        словарём красных флагов: недоступность модели не должна скрывать
        сигнал о самоповреждении или передозировке.
        """
        patient_id, now = message.patient_id, message.created_at
        try:
            extraction = self._d.extractor.extract(
                message_id=message.id, patient_id=patient_id, timestamp=now, text=text
            )
            self.ingest_extraction(patient_id, extraction, principal)
        except Exception as exc:
            logger.warning("Извлечение фактов из сообщения %s не удалось: %s", message.id, exc)
            message.extraction_status = "failed"
            message.extraction_error = str(exc)[:500]
            self._apply_safety_net(principal, message, text)
            return
        message.extraction_status = "extracted"
        message.clarifying_questions = list(extraction.clarifying_questions)

    def _apply_safety_net(self, principal: Principal, message: MessageRow, text: str) -> None:
        if isinstance(self._d.extractor, MockLexiconExtractor):
            return  # словарь и был основным экстрактором — повторять нечего
        fallback = _SAFETY_NET.extract(
            message_id=message.id, patient_id=message.patient_id, timestamp=message.created_at, text=text
        )
        if fallback.entities:
            self.ingest_extraction(message.patient_id, fallback, principal)

    def ingest_extraction(self, patient_id: str, extraction: FreeTextExtraction, actor: Principal) -> None:
        """Факты из текста сохраняются как `pending` до подтверждения (§10.1).

        Сначала разбирается весь ответ модели и только потом что-либо пишется:
        если ответ не разбирается, в базе не остаётся половины фактов.
        """
        window = IntakeWindow.for_message(
            extraction.timestamp,
            utc_offset_hours=self._d.clock.utc_offset_hours,
            backfill_days=self._d.limits.intake_backfill_days,
        )
        facts = facts_from_extraction(extraction, new_id, window=window)
        self._d.repos.messages.add(
            ExtractionRow(
                message_id=extraction.message_id,
                patient_id=patient_id,
                model_version=extraction.model_version,
                payload=extraction.model_dump(mode="json"),
                created_at=self._d.clock.now(),
            )
        )
        for signal in facts.risk_signals:
            self._d.repos.facts.add_risk_signal(patient_id, signal)
            self._d.audit(actor, "risk_signal.extracted", "risk_signal", signal.id, patient_id)
        for symptom in facts.symptoms:
            self._d.repos.facts.add_symptom(patient_id, symptom, self._d.clock.now())
            self._d.audit(actor, "symptom.extracted", "symptom", symptom.id, patient_id)
        for intake in facts.medication_intakes:
            existing = self._d.repos.facts.intake_for_slot(patient_id, intake.slot_date, intake.slot)
            if existing is not None:
                continue
            self._d.repos.facts.upsert_intake(patient_id, intake)
            self._d.audit(
                actor,
                "medication_intake.extracted",
                "intake",
                intake.id,
                patient_id,
            )

    def add_lab(self, principal: Principal, patient_id: str, body: dict[str, Any]) -> Json:
        self._access.require_read(principal, patient_id)
        by_doctor = principal.role is Role.DOCTOR
        lab = LabResult.model_validate(
            {
                **body,
                "id": new_id("lab"),
                "analyte": LabAnalyte(body["analyte"]),
                "entered_by": "doctor" if by_doctor else "patient",
                "doctor_verified": by_doctor,
            }
        )
        self._d.repos.facts.add_lab(patient_id, lab)
        self._d.audit(principal, "lab.added", "lab", lab.id, patient_id)
        alerts = self._state.evaluate(patient_id, principal)
        return {"lab": lab.to_schema(), "alerts": [self._present.alert(a) for a in alerts]}

    # ------------------------------------------------------------ helpers

    def _validate_message(self, body: str, files: list[Upload]) -> None:
        limits = self._d.limits
        if not body and not files:
            raise InvalidInputError("Напишите сообщение или прикрепите файл")
        if len(body) > limits.max_text_length:
            raise InvalidInputError(f"Сообщение длиннее {limits.max_text_length} символов")
        if len(files) > limits.max_files:
            raise InvalidInputError(f"Не более {limits.max_files} файлов")
        for f in files:
            if f.mime_type not in limits.mime_types:
                raise InvalidInputError(f"Формат «{f.filename}» не поддерживается")
            if len(f.data) > limits.max_file_bytes:
                raise InvalidInputError(f"Файл «{f.filename}» больше 10 МБ")

    def _store_file(self, message_id: str, patient_id: str, upload: Upload) -> AttachmentRow:
        attachment_id = new_id("att")
        self._d.storage.put(attachment_id, upload.data)
        return AttachmentRow(
            id=attachment_id,
            message_id=message_id,
            patient_id=patient_id,
            filename=upload.filename[:255],
            mime_type=upload.mime_type,
            size=len(upload.data),
            storage_key=attachment_id,
            uploaded_at=self._d.clock.now(),
        )
