"""Перечисления контракта v0.2 (Technical Spec §4.1, patient_state_v0.2.schema.json).

Значение каждого члена — ровно то, что лежит в JSON и YAML.
"""

from enum import StrEnum


class DoctorPriority(StrEnum):
    """Приоритет в рабочей очереди врача. Не push-уведомление и не диагноз."""

    INFO = "info"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

    @property
    def rank(self) -> int:
        return _PRIORITY_RANK[self]


_PRIORITY_RANK = {
    DoctorPriority.INFO: 0,
    DoctorPriority.NORMAL: 1,
    DoctorPriority.HIGH: 2,
    DoctorPriority.URGENT: 3,
}


class PatientAction(StrEnum):
    """Что показывается пациенту. Независимо от doctor_priority (§12.1)."""

    NONE = "none"
    INFORM_AT_NEXT_CONTACT = "inform_at_next_contact"
    CONTACT_DOCTOR_SOON = "contact_doctor_soon"
    CONTACT_CLINIC_TODAY = "contact_clinic_today"
    RECOMMEND_AMBULANCE = "recommend_ambulance"
    NEUTRAL_OUT_OF_LEAFLET = "neutral_out_of_leaflet"


class FactSource(StrEnum):
    FORM = "form"
    TEXT_LLM = "text_llm"
    TEXT_LEXICON = "text_lexicon"
    CLINICIAN = "clinician"
    LAB = "lab"
    DERIVED = "derived"


class Confirmation(StrEnum):
    PENDING = "pending"
    PATIENT_CONFIRMED = "patient_confirmed"
    DOCTOR_VERIFIED = "doctor_verified"
    CORRECTED = "corrected"
    REJECTED = "rejected"


class Instrument(StrEnum):
    GAD7 = "GAD7"
    PHQ9 = "PHQ9"


class CompletionStatus(StrEnum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    SKIPPED = "skipped"


class IntakeSlot(StrEnum):
    MORNING = "morning"
    EVENING = "evening"
    UNKNOWN = "unknown"


class IntakeStatus(StrEnum):
    """`unknown` — отметки нет. Это не то же самое, что `missed` (§4.2)."""

    TAKEN = "taken"
    MISSED = "missed"
    UNKNOWN = "unknown"


class MissedReason(StrEnum):
    FORGOT = "forgot"
    ADVERSE_EVENT = "adverse_event"
    FELT_UNWELL = "felt_unwell"
    RAN_OUT = "ran_out"
    DECIDED_TO_STOP = "decided_to_stop"
    OTHER = "other"
    UNKNOWN = "unknown"


class SymptomType(StrEnum):
    """Закрытый справочник симптомов v0.2 (§8.2)."""

    SOMNOLENCE = "somnolence"
    HEADACHE = "headache"
    DIZZINESS = "dizziness"
    ASTHENIA = "asthenia"
    PARESTHESIA = "paresthesia"
    INSOMNIA = "insomnia"
    POOR_SLEEP_QUALITY = "poor_sleep_quality"
    ANXIETY_INCREASED = "anxiety_increased"
    ATTENTION_DISTURBANCE = "attention_disturbance"
    SLOWED_REACTION = "slowed_reaction"
    DYSGEUSIA = "dysgeusia"
    NAUSEA = "nausea"
    UPPER_ABDOMINAL_PAIN = "upper_abdominal_pain"
    CONSTIPATION = "constipation"
    BACK_PAIN = "back_pain"
    MUSCLE_RIGIDITY = "muscle_rigidity"
    TRISMUS = "trismus"
    HYPERHIDROSIS = "hyperhidrosis"
    OTHER_UNLISTED = "other_unlisted"

    @property
    def in_leaflet_set(self) -> bool:
        """Входит ли тип в закрытый список нежелательных явлений листка-вкладыша."""
        return self is not SymptomType.OTHER_UNLISTED


class Polarity(StrEnum):
    PRESENT = "present"
    ABSENT = "absent"
    UNCERTAIN = "uncertain"


class Experiencer(StrEnum):
    PATIENT = "patient"
    OTHER = "other"


class Temporality(StrEnum):
    CURRENT = "current"
    RECENT_PAST = "recent_past"
    EARLIER = "earlier"
    HYPOTHETICAL = "hypothetical"


class Tri(StrEnum):
    """Да / нет / неизвестно. `unknown != no` (§4.2)."""

    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class Severity(StrEnum):
    MILD = "mild"
    MODERATE = "moderate"
    SEVERE = "severe"
    UNKNOWN = "unknown"


class RiskSignalType(StrEnum):
    SELF_HARM_OR_SUICIDAL = "self_harm_or_suicidal"
    POSSIBLE_OVERDOSE = "possible_overdose"
    POSSIBLE_ALLERGIC_REACTION = "possible_allergic_reaction"
    PREGNANCY_OR_LACTATION = "pregnancy_or_lactation"
    CONCOMITANT_DRUG_MENTION = "concomitant_drug_mention"
    ALCOHOL_USE_MENTION = "alcohol_use_mention"
    INTENTION_TO_STOP_TREATMENT = "intention_to_stop_treatment"
    OTHER_CONCERN = "other_concern"


class LabAnalyte(StrEnum):
    HEMOGLOBIN = "hemoglobin"
    CREATININE = "creatinine"
    EGFR = "egfr"
    CPK = "cpk"
    ALT = "alt"
    AST = "ast"
    BILIRUBIN_TOTAL = "bilirubin_total"
    BILIRUBIN_DIRECT = "bilirubin_direct"
    GLUCOSE = "glucose"
    TSH = "tsh"
    T3 = "t3"
    T4 = "t4"
    OTHER = "other"


class RouteDecision(StrEnum):
    PENDING = "pending"
    NONE = "none"
    PREFERRED = "preferred"
    REQUIRED = "required"


class AlertStatus(StrEnum):
    """Жизненный цикл алерта (§13.2)."""

    CREATED = "created"
    DELIVERED_TO_WORKPLACE = "delivered_to_workplace"
    VIEWED = "viewed"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"

    @property
    def is_open(self) -> bool:
        return self is not AlertStatus.RESOLVED


class Role(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    ADMIN = "admin"


class BookingStatus(StrEnum):
    OPEN = "open"
    CONTACTED = "contacted"
    SCHEDULED = "scheduled"
    CANCELLED = "cancelled"


class ExternalSystem(StrEnum):
    """Внешние медицинские информационные системы, в которых открывается окно сервиса."""

    EMIAS = "emias"
    ONEC = "onec"

    @property
    def display_name(self) -> str:
        return {ExternalSystem.EMIAS: "ЕМИАС", ExternalSystem.ONEC: "1С:Медицина"}[self]


class IdentityKind(StrEnum):
    PATIENT = "patient"
    DOCTOR = "doctor"


class SafetyAction(StrEnum):
    """Что пациент сделал с экстренным предупреждением (экран «Позвоните 112»)."""

    SHOWN = "shown"
    CALL_112 = "call_112"
    CALL_103 = "call_103"
    MESSAGE_DOCTOR = "message_doctor"
    DISMISSED = "dismissed"
