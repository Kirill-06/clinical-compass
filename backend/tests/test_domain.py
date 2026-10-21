"""Сценарии §24 спецификации на уровне предметной логики (без БД и HTTP)."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from clinical_compass.config import Settings
from clinical_compass.domain.contracts import Contracts, load_contracts, parse_yaml
from clinical_compass.domain.derived import DueStatus, adherence, deltas_for, schedule_status
from clinical_compass.domain.enums import (
    AlertStatus,
    CompletionStatus,
    Confirmation,
    DoctorPriority,
    Experiencer,
    FactSource,
    Instrument,
    IntakeSlot,
    IntakeStatus,
    LabAnalyte,
    MissedReason,
    PatientAction,
    Polarity,
    RiskSignalType,
    SymptomType,
    Temporality,
    Tri,
)
from clinical_compass.domain.extraction import FreeTextExtraction, MockLexiconExtractor, facts_from_extraction
from clinical_compass.domain.instruments import ScoringError, score_items
from clinical_compass.domain.rules import RuleConfigError, RuleContext, RuleEngine, RuleSet
from clinical_compass.domain.state import (
    Alert,
    LabResult,
    MedicationIntake,
    PatientState,
    QuestionnaireResponse,
    QuestionnaireSchedule,
    RiskSignal,
    RoutingDecision,
    SymptomEvent,
)

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
T0 = datetime(2026, 10, 1, 9, tzinfo=UTC)


@pytest.fixture(scope="module")
def contracts() -> Contracts:
    return load_contracts(CONTRACTS_DIR)


@pytest.fixture(scope="module")
def engine(contracts: Contracts) -> RuleEngine:
    return RuleEngine(contracts.rules)


def q(
    fid: str, instrument: Instrument, total: int, *, delta: int | None = None, item9: int = 0, day: int = 0
) -> QuestionnaireResponse:
    return QuestionnaireResponse(
        id=fid,
        instrument=instrument,
        administered_at=T0 + timedelta(days=day),
        item_scores=(0,) * (7 if instrument is Instrument.GAD7 else 9),
        completion_status=CompletionStatus.COMPLETE,
        total_score=total,
        delta_from_previous=delta,
        phq9_item9=item9 if instrument is Instrument.PHQ9 else None,
        source=FactSource.FORM,
    )


def sym(
    fid: str,
    kind: SymptomType,
    impact: Tri = Tri.UNKNOWN,
    polarity: Polarity = Polarity.PRESENT,
    experiencer: Experiencer = Experiencer.PATIENT,
) -> SymptomEvent:
    return SymptomEvent(
        id=fid,
        normalized_type=kind,
        polarity=polarity,
        experiencer=experiencer,
        temporality=Temporality.CURRENT,
        affects_daily_life=impact,
        source=FactSource.FORM,
        confirmation=Confirmation.PATIENT_CONFIRMED,
    )


def missed(fid: str, reason: MissedReason) -> MedicationIntake:
    return MedicationIntake(
        id=fid,
        slot_date=date(2026, 10, 1),
        slot=IntakeSlot.MORNING,
        status=IntakeStatus.MISSED,
        missed_reason=reason,
        marked_at=T0,
        source=FactSource.FORM,
        confirmation=Confirmation.PATIENT_CONFIRMED,
    )


def lab(fid: str, analyte: LabAnalyte, value: float, unit: str, high: float | None = None) -> LabResult:
    return LabResult(
        id=fid,
        analyte=analyte,
        value=value,
        unit=unit,
        reference_high=high,
        sample_date=date(2026, 10, 1),
        entered_by="doctor",
        doctor_verified=True,
    )


def risk(kind: RiskSignalType) -> RiskSignal:
    return RiskSignal(
        id=kind.value,
        type=kind,
        source=FactSource.TEXT_LEXICON,
        confirmation=Confirmation.PENDING,
        created_at=T0,
    )


def state(**facts: object) -> PatientState:
    return PatientState(patient_id="p1", doctor_id="d1", updated_at=T0, **facts)


def rule_ids(engine: RuleEngine, s: PatientState, ctx: RuleContext | None = None) -> set[str]:
    return {r.rule_id for r in engine.evaluate(s, ctx)}


# ---------------------------------------------------------------- config


def test_frozen_config_loads_all_rules(contracts: Contracts) -> None:
    rules = contracts.rules
    assert rules.rule_version == "0.2.0"
    assert len(rules.rules) == 16
    assert rules.questionnaire_default_days == {Instrument.GAD7: 14, Instrument.PHQ9: 14}
    assert rules.personal_push_default is False
    assert rules.urgent_pinned_until_acknowledged is True


@pytest.mark.parametrize(
    ("needle", "replacement"),
    [
        ("op: gte", "op: roughly"),
        ("field: lab.cpk", "field: horoscope.sign"),
        ('schema_version: "0.2.0"', 'schema_version: "0.1.0"'),
    ],
)
def test_invalid_config_is_rejected(needle: str, replacement: str) -> None:
    text = (CONTRACTS_DIR / "alert_rules_v0.2.yaml").read_text(encoding="utf-8")
    with pytest.raises(RuleConfigError):
        RuleSet.parse(parse_yaml(text.replace(needle, replacement, 1)))


# ---------------------------------------------------------------- rules


def test_gad_worsening_plus_four(engine: RuleEngine) -> None:
    [r] = engine.evaluate(state(questionnaires=(q("g", Instrument.GAD7, 12, delta=4),)))
    assert r.rule_id == "R_GAD_WORSENING"
    assert r.doctor_priority is DoctorPriority.NORMAL
    assert r.patient_action is PatientAction.INFORM_AT_NEXT_CONTACT
    assert r.source_fact_ids == ("g",)


@pytest.mark.parametrize("delta", [3, -4, None])
def test_gad_without_significant_worsening(engine: RuleEngine, delta: int | None) -> None:
    assert engine.evaluate(state(questionnaires=(q("g", Instrument.GAD7, 11, delta=delta),))) == []


def test_phq_positive_screen(engine: RuleEngine) -> None:
    [r] = engine.evaluate(state(questionnaires=(q("p", Instrument.PHQ9, 10),)))
    assert (r.rule_id, r.doctor_priority, r.patient_action) == (
        "R_PHQ_SCREEN_POSITIVE",
        DoctorPriority.HIGH,
        PatientAction.CONTACT_DOCTOR_SOON,
    )
    assert engine.evaluate(state(questionnaires=(q("p", Instrument.PHQ9, 9),))) == []


def test_phq_item9_is_a_safety_signal_even_with_low_total(engine: RuleEngine) -> None:
    [r] = engine.evaluate(state(questionnaires=(q("p", Instrument.PHQ9, 3, item9=1),)))
    assert (r.rule_id, r.doctor_priority, r.patient_action) == (
        "R_SELF_HARM",
        DoctorPriority.URGENT,
        PatientAction.RECOMMEND_AMBULANCE,
    )


@pytest.mark.parametrize(
    ("symptom", "expected"),
    [
        (sym("s", SymptomType.DIZZINESS, Tri.YES), {"R_AE_IMPACT"}),
        (sym("s", SymptomType.NAUSEA, Tri.NO), {"R_AE_NO_IMPACT"}),
        (sym("s", SymptomType.NAUSEA, Tri.UNKNOWN), set()),
        (sym("s", SymptomType.ANXIETY_INCREASED, Tri.YES), {"R_ANXIETY_INCREASED", "R_AE_IMPACT"}),
        (sym("s", SymptomType.HEADACHE, Tri.YES, polarity=Polarity.ABSENT), set()),
        (sym("s", SymptomType.HEADACHE, Tri.YES, experiencer=Experiencer.OTHER), set()),
    ],
    ids=["ae-impact", "ae-no-impact", "unknown-is-not-no", "anxiety", "negated", "other-person"],
)
def test_symptom_rules(engine: RuleEngine, symptom: SymptomEvent, expected: set[str]) -> None:
    assert rule_ids(engine, state(symptoms=(symptom,))) == expected


def test_out_of_scope_does_not_classify_urgency(engine: RuleEngine) -> None:
    [r] = engine.evaluate(state(symptoms=(sym("s", SymptomType.OTHER_UNLISTED, Tri.YES),)))
    assert r.rule_id == "R_OUT_OF_SCOPE"
    assert r.doctor_priority is DoctorPriority.HIGH
    assert r.patient_action is PatientAction.NEUTRAL_OUT_OF_LEAFLET
    assert r.medical_urgency_classified is False


@pytest.mark.parametrize(
    ("reason", "expected"),
    [
        (MissedReason.ADVERSE_EVENT, {"R_MISSED_ADVERSE_EVENT"}),
        (MissedReason.DECIDED_TO_STOP, {"R_INTENTION_TO_STOP"}),
        (MissedReason.FORGOT, set()),
    ],
)
def test_missed_dose_reasons(engine: RuleEngine, reason: MissedReason, expected: set[str]) -> None:
    assert rule_ids(engine, state(medication_intakes=(missed("i", reason),))) == expected


def test_text_risk_signals(engine: RuleEngine) -> None:
    signals = tuple(
        risk(k)
        for k in (
            RiskSignalType.SELF_HARM_OR_SUICIDAL,
            RiskSignalType.POSSIBLE_OVERDOSE,
            RiskSignalType.POSSIBLE_ALLERGIC_REACTION,
            RiskSignalType.OTHER_CONCERN,
        )
    )
    assert rule_ids(engine, state(risk_signals=signals)) == {
        "R_SELF_HARM",
        "R_OVERDOSE",
        "R_ALLERGY",
        "R_OUT_OF_SCOPE",
    }


def test_hemoglobin_threshold_depends_on_sex_and_units(engine: RuleEngine) -> None:
    s = state(labs=(lab("hb", LabAnalyte.HEMOGLOBIN, 125, "g/L"),))
    assert rule_ids(engine, s, RuleContext(sex="male")) == {"R_HB_LOW_MALE"}
    assert rule_ids(engine, s, RuleContext(sex="female")) == set()
    assert rule_ids(engine, s) == set()
    low = state(labs=(lab("hb", LabAnalyte.HEMOGLOBIN, 11.5, "g/dL"),))
    assert rule_ids(engine, low, RuleContext(sex="female")) == {"R_HB_LOW_FEMALE"}


def test_egfr_and_cpk(engine: RuleEngine) -> None:
    [r] = engine.evaluate(state(labs=(lab("e", LabAnalyte.EGFR, 55, "mL/min/1.73m2"),)))
    assert (r.rule_id, r.patient_action) == ("R_EGFR_LOW", PatientAction.CONTACT_CLINIC_TODAY)
    assert rule_ids(engine, state(labs=(lab("c", LabAnalyte.CPK, 300, "U/L", high=190),))) == {"R_CPK_HIGH"}
    assert rule_ids(engine, state(labs=(lab("c", LabAnalyte.CPK, 300, "U/L"),))) == set()


def test_routing_review_fires_once_from_profile(engine: RuleEngine) -> None:
    [r] = engine.evaluate(state(), RuleContext(route_review_needed=True))
    assert r.rule_id == "R_ROUTING_REVIEW"
    assert r.patient_action is PatientAction.NONE


def test_evaluation_is_deterministic(engine: RuleEngine) -> None:
    s = state(
        questionnaires=(q("p", Instrument.PHQ9, 12, item9=2),),
        symptoms=(sym("s", SymptomType.OTHER_UNLISTED),),
    )
    assert [r.to_json() for r in engine.evaluate(s)] == [r.to_json() for r in engine.evaluate(s)]


# ---------------------------------------------------------------- contract


def test_patient_state_matches_json_schema(contracts: Contracts) -> None:
    s = state(
        questionnaire_schedules=(
            QuestionnaireSchedule(
                instrument=Instrument.GAD7,
                interval_days=14,
                configured_by="system_default",
                active=True,
                next_due_at=T0,
            ),
        ),
        questionnaires=(q("g", Instrument.GAD7, 12, delta=4), q("p", Instrument.PHQ9, 10, item9=1)),
        symptoms=(sym("s", SymptomType.DIZZINESS, Tri.YES),),
        medication_intakes=(missed("i", MissedReason.FORGOT),),
        labs=(lab("c", LabAnalyte.CPK, 300, "U/L", high=190),),
        routing=RoutingDecision(),
        alerts=(
            Alert(
                id="a",
                rule_id="R_GAD_WORSENING",
                doctor_priority=DoctorPriority.NORMAL,
                patient_action=PatientAction.INFORM_AT_NEXT_CONTACT,
                created_at=T0,
                status=AlertStatus.DELIVERED_TO_WORKPLACE,
                rule_version="0.2.0",
                source_fact_ids=("g",),
            ),
        ),
    )
    document = s.to_schema()
    assert contracts.schema_errors(document) == []
    assert PatientState.from_schema(document).to_schema() == document


def test_schema_rejects_wrong_item_count(contracts: Contracts) -> None:
    document = state(questionnaires=(q("g", Instrument.GAD7, 3),)).to_schema()
    document["questionnaires"][0]["item_scores"] = [1, 2]
    assert contracts.schema_errors(document)


# ---------------------------------------------------------------- scoring & derived


def test_scoring_ranges_and_validation(contracts: Contracts) -> None:
    gad, phq = contracts.instruments[Instrument.GAD7], contracts.instruments[Instrument.PHQ9]
    assert score_items(gad, [3] * 7).total == 21
    assert score_items(phq, [3] * 9).total == 27
    assert score_items(phq, [0] * 8 + [2]).phq9_item9 == 2
    for bad in ([1, 1], [4] * 7):
        with pytest.raises(ScoringError):
            score_items(gad, bad)


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (4, "Минимальный"),
        (5, "Умеренный"),
        (9, "Умеренный"),
        (10, "Средний"),
        (14, "Средний"),
        (15, "Высокий"),
        (21, "Высокий"),
    ],
)
def test_gad7_band_boundaries_follow_the_source(contracts: Contracts, score: int, label: str) -> None:
    assert contracts.instruments[Instrument.GAD7].band_for(score).label == label


def test_signed_deltas() -> None:
    d = deltas_for(Instrument.GAD7, 6, [q("a", Instrument.GAD7, 8), q("b", Instrument.GAD7, 10, day=14)])
    assert (d.baseline, d.from_previous, d.from_baseline) == (8, -4, -2)
    assert deltas_for(Instrument.GAD7, 6, []).from_previous is None


def test_schedule_is_14_days_and_doctor_configurable() -> None:
    schedule = QuestionnaireSchedule(
        instrument=Instrument.GAD7, interval_days=14, configured_by="system_default", active=True
    )
    responses = [q("a", Instrument.GAD7, 8)]

    def status(sch: QuestionnaireSchedule, days: int) -> DueStatus:
        return schedule_status(sch, responses, T0, T0 + timedelta(days=days)).status

    assert status(schedule, 13) is DueStatus.UPCOMING
    assert status(schedule, 14) is DueStatus.DUE
    assert status(schedule.model_copy(update={"interval_days": 7}), 7) is DueStatus.DUE


def test_adherence_separates_missed_and_unmarked() -> None:
    def mark(
        day: int, slot: IntakeSlot, st: IntakeStatus, reason: MissedReason | None = None
    ) -> MedicationIntake:
        return MedicationIntake(
            id=f"{day}{slot}",
            slot_date=date(2026, 10, day),
            slot=slot,
            status=st,
            missed_reason=reason,
            marked_at=T0,
            source=FactSource.FORM,
            confirmation=Confirmation.PATIENT_CONFIRMED,
        )

    a = adherence(
        [
            mark(3, IntakeSlot.MORNING, IntakeStatus.TAKEN),
            mark(3, IntakeSlot.EVENING, IntakeStatus.MISSED, MissedReason.FORGOT),
            mark(2, IntakeSlot.MORNING, IntakeStatus.MISSED, MissedReason.ADVERSE_EVENT),
        ],
        plan_slots=[IntakeSlot.MORNING, IntakeSlot.EVENING],
        plan_start=date(2026, 10, 2),
        today=date(2026, 10, 4),
        days=7,
    )
    # Сегодня (4-е) без отметок не считается; 2-е вечер — без отметки.
    assert (a.taken, a.missed, a.unknown, a.scheduled) == (1, 2, 1, 4)
    assert a.ratio == 0.25
    assert a.consecutive_missed == 1
    assert a.missed_reasons == {MissedReason.FORGOT: 1, MissedReason.ADVERSE_EVENT: 1}


# ---------------------------------------------------------------- mock extraction


def _extract(text: str) -> FreeTextExtraction:
    return MockLexiconExtractor().extract(message_id="m", patient_id="p1", timestamp=T0, text=text)


def test_mock_extraction_detects_red_flag_with_evidence() -> None:
    ex = _extract("Последние дни я не хочу жить")
    [entity] = ex.entities
    assert entity.value == {"type": "self_harm_or_suicidal"}
    assert entity.evidence_span.text == "не хочу жить"
    [signal] = facts_from_extraction(ex, lambda p: f"{p}_1").risk_signals
    assert (signal.source, signal.confirmation) == (FactSource.TEXT_LEXICON, Confirmation.PENDING)


@pytest.mark.parametrize("text", ["Я никогда не хочу умереть, просто устал", "У друга были мысли про суицид"])
def test_mock_extraction_ignores_negation_and_other_people(text: str) -> None:
    assert facts_from_extraction(_extract(text), lambda p: p).risk_signals == ()


def test_vague_abdominal_pain_asks_for_localization_not_urgency() -> None:
    ex = _extract("Болит живот второй день")
    assert ex.entities == ()
    assert ex.clarifying_questions


def test_extraction_contract_round_trips() -> None:
    ex = _extract("Хочу прекратить лечение")
    back = FreeTextExtraction.model_validate(ex.model_dump(mode="json"))
    assert back.entities[0].value["type"] == "intention_to_stop_treatment"
    assert back.schema_version == "0.2.0"


def test_settings_refuse_dev_internal_token_outside_demo() -> None:
    with pytest.raises(ValueError, match="CC_INTERNAL_TOKEN"):
        Settings(demo_auth=False)
    assert (
        Settings(demo_auth=False, internal_token="a-real-secret-token").internal_token
        == "a-real-secret-token"
    )
