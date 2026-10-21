"""Детерминированный rule engine v0.2 (§12).

Правила читаются из `alert_rules_v0.2.yaml`. Движок принимает только
структурированный Patient State, не вызывает LLM и не пишет свободных текстов.

Patient State раскладывается на «кадры»: один факт (ответ опросника, симптом,
сигнал, отметка приёма, анализ) плюс контекст (`patient`, `clinical_profile`).
Условие `all`/`any` проверяется в пределах одного кадра, поэтому, например,
`R_AE_IMPACT` срабатывает, только если ОДИН И ТОТ ЖЕ симптом из листка-вкладыша
present + patient + affects_daily_life = yes.
"""

from __future__ import annotations

import operator
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

from clinical_compass import SCHEMA_VERSION
from clinical_compass.domain.enums import (
    CompletionStatus,
    Confirmation,
    DoctorPriority,
    Instrument,
    LabAnalyte,
    PatientAction,
    SymptomType,
)
from clinical_compass.domain.state import (
    DEFAULT_INTERVAL_DAYS,
    LabResult,
    PatientState,
    QuestionnaireResponse,
    SymptomEvent,
)

EVENT_ROOTS = frozenset({"questionnaire", "risk_signal", "symptom", "medication_intake", "lab"})
CONTEXT_ROOTS = frozenset({"patient", "clinical_profile"})
PROFILE_FACT_ID = "clinical_profile"

_MISSING = object()


class RuleConfigError(ValueError):
    """Конфиг правил некорректен. Неизвестный оператор — ошибка, а не пропущенное правило."""


# ---------------------------------------------------------------- conditions

Frame = dict[str, Any]
Check = Callable[[Any, Any, Frame, list[str]], bool]


def _cmp(fn: Callable[[Any, Any], bool]) -> Check:
    def check(actual: Any, expected: Any, _frame: Frame, _path: list[str]) -> bool:
        is_number = isinstance(actual, int | float) and not isinstance(actual, bool)
        return is_number and isinstance(expected, int | float) and fn(actual, expected)

    return check


def _reference(key: str, fn: Callable[[Any, Any], bool]) -> Check:
    """Сравнение со значением референса той же записи анализа (например, КФК)."""

    def check(actual: Any, _expected: Any, frame: Frame, path: list[str]) -> bool:
        parent = _lookup(frame, path[:-1])
        reference = parent.get(key) if isinstance(parent, dict) else None
        return (
            isinstance(actual, int | float) and isinstance(reference, int | float) and fn(actual, reference)
        )

    return check


def _in_leaflet(actual: Any, _expected: Any, _frame: Frame, _path: list[str]) -> bool:
    return actual in {t.value for t in SymptomType if t.in_leaflet_set}


OPERATORS: dict[str, Check] = {
    "eq": lambda a, e, _f, _p: a == e,
    "ne": lambda a, e, _f, _p: a != e,
    "gt": _cmp(operator.gt),
    "gte": _cmp(operator.ge),
    "lt": _cmp(operator.lt),
    "lte": _cmp(operator.le),
    "in": lambda a, e, _f, _p: isinstance(e, list) and a in e,
    "in_closed_leaflet_symptom_set": _in_leaflet,
    "gt_reference_high": _reference("reference_high", operator.gt),
    "lt_reference_low": _reference("reference_low", operator.lt),
}


def _lookup(frame: Frame, path: list[str]) -> Any:
    current: Any = frame
    for part in path:
        if not isinstance(current, dict) or part not in current:
            return _MISSING
        current = current[part]
    return current


@dataclass(frozen=True)
class FieldCondition:
    field: str
    op: str
    value: Any

    @property
    def roots(self) -> frozenset[str]:
        return frozenset({self.field.split(".")[0]})

    def test(self, frame: Frame) -> bool:
        path = self.field.split(".")
        actual = _lookup(frame, path)
        # Отсутствующее значение никогда не совпадает: unknown != no.
        if actual is _MISSING or actual is None:
            return False
        return OPERATORS[self.op](actual, self.value, frame, path)


@dataclass(frozen=True)
class AllOf:
    items: tuple[Condition, ...]

    @property
    def roots(self) -> frozenset[str]:
        return frozenset().union(*(c.roots for c in self.items))

    def test(self, frame: Frame) -> bool:
        return all(c.test(frame) for c in self.items)


@dataclass(frozen=True)
class AnyOf:
    items: tuple[Condition, ...]

    @property
    def roots(self) -> frozenset[str]:
        return frozenset().union(*(c.roots for c in self.items))

    def test(self, frame: Frame) -> bool:
        return any(c.test(frame) for c in self.items)


Condition = FieldCondition | AllOf | AnyOf


def _parse_condition(raw: Any) -> Condition:
    if not isinstance(raw, dict):
        raise RuleConfigError("условие when должно быть объектом")
    if "all" in raw:
        return AllOf(tuple(_parse_condition(c) for c in raw["all"]))
    if "any" in raw:
        return AnyOf(tuple(_parse_condition(c) for c in raw["any"]))
    field_name, op = raw.get("field"), raw.get("op")
    if not isinstance(field_name, str) or not isinstance(op, str):
        raise RuleConfigError(f"условие без field/op: {raw}")
    if op not in OPERATORS:
        raise RuleConfigError(f"неизвестный оператор {op!r}")
    root = field_name.split(".")[0]
    if root not in EVENT_ROOTS | CONTEXT_ROOTS:
        raise RuleConfigError(f"неизвестное поле {field_name!r}")
    return FieldCondition(field_name, op, raw.get("value"))


# ---------------------------------------------------------------- config


@dataclass(frozen=True)
class RuleDef:
    id: str
    when: Condition
    doctor_priority: DoctorPriority
    patient_action: PatientAction
    message_template_id: str | None
    source: str
    medical_urgency_classified: bool = True
    patient_sees_only_after_doctor_confirmation: bool = False

    @property
    def event_roots(self) -> frozenset[str]:
        return self.when.roots & EVENT_ROOTS


@dataclass(frozen=True)
class RuleSet:
    schema_version: str
    rule_version: str
    status: str
    rules: tuple[RuleDef, ...]
    questionnaire_default_days: dict[Instrument, int] = field(default_factory=dict)
    doctor_configurable_schedule: bool = True
    urgent_pinned_until_acknowledged: bool = True
    personal_push_default: bool = False

    @classmethod
    def parse(cls, raw: Any) -> RuleSet:
        if not isinstance(raw, dict):
            raise RuleConfigError("корень конфига должен быть объектом")
        if raw.get("schema_version") != SCHEMA_VERSION:
            raise RuleConfigError(
                f"schema_version {raw.get('schema_version')} не совпадает с {SCHEMA_VERSION}"
            )
        rules_raw = raw.get("rules")
        if not isinstance(rules_raw, list) or not rules_raw:
            raise RuleConfigError("нет списка rules")
        rules: list[RuleDef] = []
        seen: set[str] = set()
        for item in rules_raw:
            rule_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(rule_id, str) or not rule_id:
                raise RuleConfigError("у правила нет id")
            if rule_id in seen:
                raise RuleConfigError(f"повторяющийся id {rule_id}")
            seen.add(rule_id)
            try:
                rules.append(
                    RuleDef(
                        id=rule_id,
                        when=_parse_condition(item.get("when")),
                        doctor_priority=DoctorPriority(item["doctor_priority"]),
                        patient_action=PatientAction(item["patient_action"]),
                        message_template_id=item.get("message_template_id"),
                        source=str(item.get("source", "unspecified")),
                        medical_urgency_classified=item.get("medical_urgency_classified") is not False,
                        patient_sees_only_after_doctor_confirmation=(
                            item.get("patient_sees_only_after_doctor_confirmation") is True
                        ),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise RuleConfigError(f"{rule_id}: {exc}") from exc
        special = raw.get("special_handling") or {}
        schedule = special.get("questionnaire_schedule") or {}
        workplace = special.get("workplace_alerts") or {}
        return cls(
            schema_version=raw["schema_version"],
            rule_version=str(raw.get("rule_version", "unknown")),
            status=str(raw.get("status", "unknown")),
            rules=tuple(rules),
            questionnaire_default_days={
                Instrument.GAD7: int(schedule.get("GAD7_default_days", DEFAULT_INTERVAL_DAYS)),
                Instrument.PHQ9: int(schedule.get("PHQ9_default_days", DEFAULT_INTERVAL_DAYS)),
            },
            doctor_configurable_schedule=schedule.get("doctor_configurable") is not False,
            urgent_pinned_until_acknowledged=workplace.get("urgent_pinned_until_acknowledged") is not False,
            personal_push_default=workplace.get("personal_push_default") is True,
        )


# ---------------------------------------------------------------- evaluation


@dataclass(frozen=True)
class RuleContext:
    """Контекст пациента помимо фактов Patient State."""

    sex: str | None = None
    """`female` | `male` | None — неизвестный пол: правила по полу не срабатывают."""
    route_review_needed: bool = False


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    doctor_priority: DoctorPriority
    patient_action: PatientAction
    source_fact_ids: tuple[str, ...]
    message_template_id: str | None
    rule_version: str
    source: str
    medical_urgency_classified: bool

    @property
    def dedupe_key(self) -> str:
        """Одно правило по одному набору фактов — один алерт."""
        return f"{self.rule_id}|{','.join(sorted(self.source_fact_ids))}"

    def to_json(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "matched": True,
            "doctor_priority": self.doctor_priority.value,
            "patient_action": self.patient_action.value,
            "message_template_id": self.message_template_id,
            "source_fact_ids": list(self.source_fact_ids),
            "evidence_source_id": self.source,
            "rule_version": self.rule_version,
            "medical_urgency_classified": self.medical_urgency_classified,
        }


@dataclass(frozen=True)
class _Frame:
    root: str | None
    fact_id: str
    data: Frame


class RuleEngine:
    def __init__(self, rules: RuleSet) -> None:
        self.rules = rules

    def evaluate(self, state: PatientState, context: RuleContext | None = None) -> list[RuleResult]:
        frames = list(_frames(state, context or RuleContext()))
        results: list[RuleResult] = []
        for rule in self.rules.rules:
            roots = rule.event_roots
            for frame in frames:
                # Правило без событийных полей проверяется один раз — на контексте.
                applicable = frame.root is None if not roots else frame.root in roots
                if applicable and rule.when.test(frame.data):
                    results.append(
                        RuleResult(
                            rule_id=rule.id,
                            doctor_priority=rule.doctor_priority,
                            patient_action=rule.patient_action,
                            source_fact_ids=(frame.fact_id,),
                            message_template_id=rule.message_template_id,
                            rule_version=self.rules.rule_version,
                            source=rule.source,
                            medical_urgency_classified=rule.medical_urgency_classified,
                        )
                    )
        return results


def _frames(state: PatientState, context: RuleContext) -> Iterator[_Frame]:
    base: Frame = {
        "patient": {"sex": context.sex},
        "clinical_profile": {"route_review_needed": context.route_review_needed},
    }
    yield _Frame(None, PROFILE_FACT_ID, base)
    for q in state.questionnaires:
        if q.completion_status is CompletionStatus.COMPLETE:
            yield _Frame("questionnaire", q.id, {**base, "questionnaire": _questionnaire(q)})
    for r in state.risk_signals:
        if r.confirmation is not Confirmation.REJECTED:
            risk = {"type": r.type.value, "source": r.source.value, "confirmation": r.confirmation.value}
            yield _Frame("risk_signal", r.id, {**base, "risk_signal": risk})
    for s in state.symptoms:
        if s.confirmation is not Confirmation.REJECTED:
            yield _Frame("symptom", s.id, {**base, "symptom": _symptom(s)})
    for i in state.medication_intakes:
        intake = {
            "status": i.status.value,
            "slot": i.slot.value,
            "missed_reason": i.missed_reason.value if i.missed_reason else None,
        }
        yield _Frame("medication_intake", i.id, {**base, "medication_intake": intake})
    for lab in state.labs:
        yield _Frame("lab", lab.id, {**base, "lab": _lab(lab)})


def _questionnaire(q: QuestionnaireResponse) -> Frame:
    fields: Frame = {
        "instrument": q.instrument.value,
        "total_score": q.total_score,
        "delta_from_previous": q.delta_from_previous,
        "delta_from_baseline": q.delta_from_baseline,
        "phq9_item9": q.phq9_item9,
    }
    # Поля доступны и как questionnaire.total_score, и как questionnaire.PHQ9.total_score.
    return {**fields, q.instrument.value: fields}


def _symptom(s: SymptomEvent) -> Frame:
    return {
        "normalized_type": s.normalized_type.value,
        "polarity": s.polarity.value,
        "experiencer": s.experiencer.value,
        "temporality": s.temporality.value,
        "affects_daily_life": s.affects_daily_life.value,
        "severity": s.severity.value,
        "confirmation": s.confirmation.value,
    }


def _lab(lab: LabResult) -> Frame:
    unit = lab.unit.lower().replace(" ", "")
    data: Frame = {
        "analyte": lab.analyte.value,
        "value": lab.value,
        "unit": lab.unit,
        "reference_low": lab.reference_low,
        "reference_high": lab.reference_high,
    }
    if lab.analyte is LabAnalyte.HEMOGLOBIN:
        if unit in {"g/l", "г/л"}:
            data["hemoglobin_g_l"] = lab.value
        elif unit in {"g/dl", "г/дл"}:
            data["hemoglobin_g_l"] = lab.value * 10
    elif lab.analyte is LabAnalyte.EGFR:
        data["egfr_ml_min_1_73m2"] = lab.value
    elif lab.analyte is LabAnalyte.CPK:
        data["cpk"] = lab.value
    return data
