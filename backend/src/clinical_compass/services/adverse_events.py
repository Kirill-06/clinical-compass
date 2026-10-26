"""Нежелательные явления по пациентам врача и обезличенная выгрузка сводки.

Пациенты отмечают побочные эффекты формой или пишут о них в чате. Врачу важно
видеть их вместе: какие эффекты встречаются чаще, мешают ли они жизни и какие
эффекты отсутствуют в листке-вкладыше. Последние — кандидаты в новые свойства
препарата, которые фармкомпания может захотеть изучить.

Выгрузка для анализа не содержит ФИО и телефонов: только ID пациента в сервисе,
год рождения и пол.
"""

import csv
import io
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from clinical_compass.db.models import PatientRow
from clinical_compass.domain.derived import latest_by_slot
from clinical_compass.domain.enums import (
    AlertStatus,
    DoctorPriority,
    Instrument,
    IntakeStatus,
    MissedReason,
    SymptomType,
    Tri,
)
from clinical_compass.domain.state import QuestionnaireResponse, SymptomEvent
from clinical_compass.services.access import AccessPolicy
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.presenter import Json, Presenter, iso

ADHERENCE_WINDOW_DAYS = 14
_OUTSIDE_LEAFLET_LABEL = "Другие эффекты (описаны пациентом)"
"""Подпись для врача: в справочнике у этого кода текст для пациента «Другое — опишу сам(а)»."""


@dataclass
class _EffectStats:
    reports: int = 0
    patients: set[str] = field(default_factory=set)
    affects_daily_life: int = 0
    severity: Counter[str] = field(default_factory=Counter)
    last_reported_at: str | None = None


class AdverseEventService:
    def __init__(self, deps: Deps) -> None:
        self._d = deps
        self._access = AccessPolicy(deps)
        self._present = Presenter(deps)

    def summary(self, principal: Principal) -> Json:
        """Сводка нежелательных явлений по всем пациентам врача."""
        patient_ids = self._access.doctor_patient_ids(principal)
        stats: dict[SymptomType, _EffectStats] = defaultdict(_EffectStats)
        outside_leaflet: list[Json] = []
        missed_due_to_ae = 0
        for patient_id in patient_ids:
            patient = self._access.patient(patient_id)
            for symptom, row in self._d.repos.facts.symptoms(patient_id):
                effect = stats[symptom.normalized_type]
                effect.reports += 1
                effect.patients.add(patient_id)
                effect.affects_daily_life += symptom.affects_daily_life is Tri.YES
                effect.severity[symptom.severity.value] += 1
                effect.last_reported_at = max(filter(None, [effect.last_reported_at, iso(row.reported_at)]))
                if not symptom.normalized_type.in_leaflet_set:
                    outside_leaflet.append(self._new_effect(patient, symptom, iso(row.reported_at)))
            missed_due_to_ae += self._missed_reasons(patient_id)[MissedReason.ADVERSE_EVENT]
        effects = [self._effect_row(kind, s) for kind, s in stats.items()]
        effects.sort(key=lambda e: (-int(e["reports"]), str(e["label"])))
        outside_leaflet.sort(key=lambda e: str(e["reported_at"]), reverse=True)
        return {
            "patients_total": len(patient_ids),
            "effects": effects,
            "outside_leaflet": outside_leaflet,
            "missed_doses_due_to_adverse_event": missed_due_to_ae,
        }

    def patients_csv(self, principal: Principal) -> str:
        """Одна строка на пациента врача: шкалы, приверженность, причины пропусков, побочные эффекты."""
        patients = sorted(
            (self._access.patient(p) for p in self._access.doctor_patient_ids(principal)),
            key=lambda patient: patient.display_id,
        )
        rows = [self._csv_row(patient) for patient in patients]
        for patient in patients:
            self._d.audit(principal, "export.patients_csv", "patient", patient.id, patient.id)
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=list(CSV_COLUMNS), delimiter=";", lineterminator="\r\n")
        writer.writeheader()
        writer.writerows(rows)
        # BOM: Excel на русской системе сразу открывает UTF-8 с кириллицей.
        return "﻿" + out.getvalue()

    # ------------------------------------------------------------------ части сводки

    def _effect_row(self, kind: SymptomType, s: _EffectStats) -> Json:
        return {
            "type": kind.value,
            "label": _OUTSIDE_LEAFLET_LABEL
            if not kind.in_leaflet_set
            else self._d.contracts.label("symptom_types", kind.value) or kind.value,
            "in_leaflet": kind.in_leaflet_set,
            "reports": s.reports,
            "patients": len(s.patients),
            "affects_daily_life": s.affects_daily_life,
            "severity": dict(s.severity),
            "last_reported_at": s.last_reported_at,
        }

    @staticmethod
    def _new_effect(patient: PatientRow, symptom: SymptomEvent, reported_at: str | None) -> Json:
        return {
            "patient": {
                "id": patient.id,
                "display_id": patient.display_id,
                "birth_year": patient.birth_year,
                "sex": patient.sex,
            },
            "description": symptom.patient_phrase,
            "reported_at": reported_at,
            "affects_daily_life": symptom.affects_daily_life.value,
            "severity": symptom.severity.value,
            "source": symptom.source.value,
        }

    def _missed_reasons(self, patient_id: str) -> Counter[MissedReason]:
        """Причины пропусков за всё наблюдение (исправленная отметка заменяет исходную)."""
        intakes = latest_by_slot(self._d.repos.facts.intakes(patient_id)).values()
        return Counter(
            i.missed_reason or MissedReason.UNKNOWN for i in intakes if i.status is IntakeStatus.MISSED
        )

    # ------------------------------------------------------------------ строка выгрузки

    def _csv_row(self, patient: PatientRow) -> dict[str, object]:
        pid = patient.id
        responses = self._d.repos.facts.questionnaires(pid)
        adherence = self._present.adherence(pid, ADHERENCE_WINDOW_DAYS)
        symptoms = [s for s, _ in self._d.repos.facts.symptoms(pid)]
        reasons = self._missed_reasons(pid)
        open_alerts = Counter(
            a.doctor_priority for a in self._d.repos.alerts.for_patient(pid) if AlertStatus(a.status).is_open
        )
        gad, phq = _scores(responses, Instrument.GAD7), _scores(responses, Instrument.PHQ9)
        observed = (self._d.clock.today() - self._d.clock.at(patient.observation_start).today()).days
        row: dict[str, object] = {
            "patient_id": patient.display_id,
            "birth_year": patient.birth_year,
            "sex": patient.sex,
            "observation_start": self._d.clock.at(patient.observation_start).today().isoformat(),
            "days_observed": observed,
            "gad7_baseline": gad.baseline,
            "gad7_last": gad.last,
            "gad7_change": gad.change,
            "phq9_baseline": phq.baseline,
            "phq9_last": phq.last,
            "phq9_change": phq.change,
            "phq9_item9_last": phq.item9,
            "adherence_14d_pct": round(adherence.ratio * 100)
            if adherence and adherence.ratio is not None
            else "",
            "doses_taken_14d": adherence.taken if adherence else "",
            "doses_missed_14d": adherence.missed if adherence else "",
            "doses_unmarked_14d": adherence.unknown if adherence else "",
            "ae_reports": len(symptoms),
            "ae_in_leaflet": sum(1 for s in symptoms if s.normalized_type.in_leaflet_set),
            "ae_outside_leaflet": sum(1 for s in symptoms if not s.normalized_type.in_leaflet_set),
            "ae_affecting_daily_life": sum(1 for s in symptoms if s.affects_daily_life is Tri.YES),
        }
        row |= {f"missed_{reason.value}": reasons[reason] for reason in MissedReason}
        row |= {f"open_alerts_{p.value}": open_alerts[p.value] for p in DoctorPriority}
        return row


@dataclass(frozen=True)
class _Scores:
    baseline: int | str = ""
    last: int | str = ""
    change: int | str = ""
    item9: int | str = ""


def _scores(responses: list[QuestionnaireResponse], instrument: Instrument) -> _Scores:
    done = [r for r in responses if r.instrument is instrument and r.total_score is not None]
    if not done:
        return _Scores()
    first, last = done[0], done[-1]
    return _Scores(
        baseline=first.total_score if first.total_score is not None else "",
        last=last.total_score if last.total_score is not None else "",
        change=last.delta_from_previous if last.delta_from_previous is not None else "",
        item9=last.phq9_item9 if last.phq9_item9 is not None else "",
    )


CSV_COLUMNS = (
    "patient_id", "birth_year", "sex", "observation_start", "days_observed",
    "gad7_baseline", "gad7_last", "gad7_change",
    "phq9_baseline", "phq9_last", "phq9_change", "phq9_item9_last",
    "adherence_14d_pct", "doses_taken_14d", "doses_missed_14d", "doses_unmarked_14d",
    *(f"missed_{reason.value}" for reason in MissedReason),
    "ae_reports", "ae_in_leaflet", "ae_outside_leaflet", "ae_affecting_daily_life",
    *(f"open_alerts_{priority.value}" for priority in DoctorPriority),
)  # fmt: skip
"""Порядок столбцов выгрузки; описание каждого — в docs/EXPORT.md."""
