"""Демо-данные. ВСЕ ЛЮДИ И ТЕЛЕФОНЫ ВЫМЫШЛЕНЫ.

События создаются сервисами «в прошлом» (те же сервисы с остановленными
часами), поэтому дельты, алерты и журнал аудита получаются тем же путём,
что и в рабочем сценарии.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from functools import partial

from clinical_compass.db.models import (
    AdminRow,
    DoctorPatientLinkRow,
    DoctorRow,
    MedicationPlanRow,
    PatientRow,
)
from clinical_compass.domain.enums import (
    Instrument,
    IntakeSlot,
    IntakeStatus,
    MissedReason,
    Severity,
    SymptomType,
    Tri,
)
from clinical_compass.services.auth import AuthService
from clinical_compass.services.context import Deps, Principal
from clinical_compass.services.doctors import DoctorService
from clinical_compass.services.internal import InternalService
from clinical_compass.services.patients import PatientService, SymptomReport, Upload

DRUG = "Авиандр"


@dataclass(frozen=True)
class _PatientSpec:
    id: str
    display_id: str
    full_name: str
    first_name: str
    birth_year: int
    sex: str
    doctor_id: str
    start_offset: int
    """Начало наблюдения: сегодня + start_offset дней."""
    gad: tuple[tuple[int, int], ...] = ()
    """(день от начала, баллы)."""
    phq: tuple[tuple[int, int, int], ...] = ()
    """(день от начала, баллы, ответ на вопрос 9)."""
    missed: dict[tuple[int, IntakeSlot], MissedReason] = field(default_factory=dict)
    """Пропуски: (дней назад, слот) → причина."""
    unmarked: frozenset[tuple[int, IntakeSlot]] = frozenset()
    """Слоты без отметки: (дней назад, слот)."""


_M, _E = IntakeSlot.MORNING, IntakeSlot.EVENING

_PATIENTS = (
    _PatientSpec("p_a1", "P-1001", "Корнилова Елена Андреевна", "Елена", 1986, "female", "doc_a", -14,
                 gad=((0, 12),), phq=((0, 9, 0),), missed={(4, _E): MissedReason.FORGOT}),
    _PatientSpec("p_a2", "P-1002", "Дорофеев Михаил Игоревич", "Михаил", 1979, "male", "doc_a", -60,
                 gad=((0, 16), (14, 13), (28, 11), (42, 9), (56, 8)),
                 phq=((0, 11, 0), (14, 9, 0), (28, 7, 0), (42, 6, 0), (56, 5, 0)),
                 unmarked=frozenset({(3, _E)})),
    _PatientSpec("p_a3", "P-1003", "Соловьёва Ирина Павловна", "Ирина", 1992, "female", "doc_a", -31,
                 gad=((0, 9), (14, 10), (28, 14)), phq=((0, 8, 0), (14, 9, 0), (28, 12, 0)),
                 missed={(2, _E): MissedReason.ADVERSE_EVENT, (5, _M): MissedReason.FORGOT}),
    _PatientSpec("p_a4", "P-1004", "Белов Артём Константинович", "Артём", 1998, "male", "doc_a", -5,
                 gad=((0, 7),), phq=((0, 6, 0),), unmarked=frozenset({(1, _E)})),
    _PatientSpec("p_a5", "P-1005", "Гаврилова Нина Сергеевна", "Нина", 1969, "female", "doc_a", -1,
                 unmarked=frozenset({(1, _M), (1, _E)})),
    _PatientSpec("p_a6", "P-1006", "Ковалёв Сергей Дмитриевич", "Сергей", 1983, "male", "doc_a", -20,
                 gad=((0, 8), (14, 10)), phq=((0, 7, 0), (14, 11, 1)),
                 missed={(1, _M): MissedReason.FORGOT, (1, _E): MissedReason.FORGOT}),
    _PatientSpec("p_b1", "P-2001", "Лапина Дарья Олеговна", "Дарья", 1990, "female", "doc_b", -40,
                 gad=((0, 13), (14, 12), (28, 12)), phq=((0, 8, 0), (14, 8, 0), (28, 7, 0))),
    _PatientSpec("p_b2", "P-2002", "Рябов Константин Алексеевич", "Константин", 1975, "male", "doc_b", -8,
                 gad=((0, 11),), phq=((0, 8, 0),), missed={(1, _M): MissedReason.DECIDED_TO_STOP}),
    _PatientSpec("p_b3", "P-2003", "Яхина Полина Рустамовна", "Полина", 2001, "female", "doc_b", -29,
                 gad=((0, 9), (14, 8)), phq=((0, 6, 0), (14, 6, 0))),
)  # fmt: skip


def answers_for(total: int, count: int, item9: int | None = None) -> list[int]:
    """Ответы, дающие ровно `total` баллов (и заданный ответ на вопрос 9 PHQ-9)."""
    values = [0] * count
    rest = total
    if item9 is not None:
        values[8] = item9
        rest -= item9
    for i in range(count):
        if rest <= 0:
            break
        if item9 is not None and i == 8:
            continue
        values[i] = min(3, rest)
        rest -= values[i]
    return values


def synthetic_pdf(title: str) -> bytes:
    """Маленький валидный PDF с латинским текстом — синтетический документ, не медицинские данные."""
    stream = (
        f"BT /F1 14 Tf 56 780 Td ({title}) Tj 0 -20 Td (Synthetic demo document, not patient data.) Tj ET\n"
    )
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> "
        "/Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}endstream",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(out.encode("latin-1")))
        out += f"{i} 0 obj\n{obj}\nendobj\n"
    xref = len(out.encode("latin-1"))
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    out += "".join(f"{o:010d} 00000 n \n" for o in offsets)
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    return out.encode("latin-1")


def seed_if_empty(deps: Deps) -> bool:
    """Заполнить пустую базу. Возвращает True, если данные были загружены."""
    if deps.repos.people.all_doctors():
        return False
    seed_demo(deps)
    return True


def seed_demo(deps: Deps) -> None:
    today = deps.clock.today()
    offset = timedelta(hours=deps.clock.utc_offset_hours)
    utc = deps.clock.now().tzinfo

    def at(day: int, hour: int, minute: int = 0) -> datetime:
        """Момент «день `day` от сегодня, hh:mm по времени клиники» в UTC."""
        local = datetime.combine(today + timedelta(days=day), datetime.min.time()) + timedelta(
            hours=hour, minutes=minute
        )
        return (local - offset).replace(tzinfo=utc)

    def on(moment: datetime) -> Deps:
        return deps.with_clock(deps.clock.at(moment))

    _people(deps, today, at)
    deps.session.flush()

    for spec in _PATIENTS:
        _history(spec, deps, today, at, on)

    auth = AuthService(deps)
    a2, a3, a4, b1 = (auth.principal_for(p) for p in ("p_a2", "p_a3", "p_a4", "p_b1"))
    PatientService(on(at(-4, 19, 40))).send_message(
        a2, "p_a2", "Прикладываю результаты анализов, которые сдавал по направлению терапевта.",
        [Upload("Анализы_сентябрь.pdf", "application/pdf", synthetic_pdf("Synthetic lab report (DEMO)"))],
    )  # fmt: skip
    PatientService(on(at(-2, 20, 10))).report_symptom(
        a3, "p_a3",
        SymptomReport(SymptomType.DIZZINESS, "Кружится голова по вечерам, из-за этого пропустила приём",
                      Tri.YES, Severity.MODERATE),
    )  # fmt: skip
    PatientService(on(at(-1, 20, 15))).send_message(
        a4, "p_a4", "Сплю немного лучше, но днём напряжение. Иногда думаю, что хочу бросить лечение.", []
    )
    PatientService(on(at(-1, 20, 20))).report_symptom(
        a4, "p_a4", SymptomReport(SymptomType.OTHER_UNLISTED, "Шумит в ушах по вечерам", Tri.NO)
    )
    PatientService(on(at(-9, 22, 10))).send_message(
        b1, "p_b1", "Дневник сна за две недели.",
        [Upload("Дневник_сна.pdf", "application/pdf", synthetic_pdf("Synthetic sleep diary (DEMO)"))],
    )  # fmt: skip
    # Клинический профиль (в будущем — от AI/врача): нужна оценка маршрутизации.
    InternalService(on(at(-3, 11))).set_clinical_profile("p_b1", route_review_needed=True)

    doctor_a = auth.principal_for("doc_a")
    sample = (today - timedelta(days=2)).isoformat()
    PatientService(on(at(-1, 15))).add_lab(
        doctor_a, "p_a6",
        {"analyte": "hemoglobin", "value": 125, "unit": "g/L", "reference_low": 130, "reference_high": 170,
         "sample_date": sample},
    )  # fmt: skip
    PatientService(on(at(-1, 15, 5))).add_lab(
        doctor_a,
        "p_a6",
        {"analyte": "cpk", "value": 260, "unit": "U/L", "reference_high": 190, "sample_date": sample},
    )
    # Ранее обработанные врачом алерты — для истории и журнала.
    for alert in deps.repos.alerts.for_patient("p_a2"):
        DoctorService(on(at(-58, 11))).alert_action(doctor_a, alert.id, "resolve")
    deps.session.flush()


def _people(deps: Deps, today: date, at: Callable[[int, int], datetime]) -> None:
    deps.repos.people.add(
        DoctorRow(id="doc_a", full_name="Миронова Анна Сергеевна", short_name="Миронова А. С.",
                  specialty="Врач-психотерапевт"),
        DoctorRow(id="doc_b", full_name="Ланской Олег Викторович", short_name="Ланской О. В.",
                  specialty="Врач-психиатр"),
        AdminRow(id="adm_1", full_name="Кузнецова Мария Петровна"),
    )  # fmt: skip
    for n, spec in enumerate(_PATIENTS, start=1):
        start = at(spec.start_offset, 9)
        deps.repos.people.add(
            PatientRow(
                id=spec.id,
                display_id=spec.display_id,
                full_name=spec.full_name,
                first_name=spec.first_name,
                birth_year=spec.birth_year,
                sex=spec.sex,
                phone=f"+7 (900) 000-00-{n:02d}",  # вымышленный номер
                observation_start=start,
            ),
            DoctorPatientLinkRow(
                id=f"link_{spec.id}",
                doctor_id=spec.doctor_id,
                patient_id=spec.id,
                active_from=start - timedelta(days=1),
                active_to=None,
            ),
            MedicationPlanRow(
                id=f"plan_{spec.id}",
                patient_id=spec.id,
                drug=DRUG,
                instructions="Утром и вечером, по схеме, назначенной врачом",
                slots=[IntakeSlot.MORNING.value, IntakeSlot.EVENING.value],
                start_date=today + timedelta(days=spec.start_offset),
                created_by=spec.doctor_id,
                active=True,
            ),
        )


def _history(
    spec: _PatientSpec,
    deps: Deps,
    today: date,
    at: Callable[..., datetime],
    on: Callable[[datetime], Deps],
) -> None:
    principal = AuthService(deps).principal_for(spec.id)
    events: list[tuple[datetime, _Event]] = []

    for day, total in spec.gad:
        answers = answers_for(total, 7)
        events.append(
            (at(spec.start_offset + day, 10, 15), partial(_questionnaire, Instrument.GAD7, answers))
        )
    for day, total, item9 in spec.phq:
        answers = answers_for(total, 9, item9)
        events.append(
            (at(spec.start_offset + day, 10, 25), partial(_questionnaire, Instrument.PHQ9, answers))
        )
    for back in range(-spec.start_offset, 0, -1):
        for slot in IntakeSlot:
            if (back, slot) in spec.unmarked:
                continue
            hour = 9 if slot is IntakeSlot.MORNING else 21
            mark = partial(_intake, today - timedelta(days=back), slot, spec.missed.get((back, slot)))
            events.append((at(-back, hour, 5 + back % 40), mark))

    for moment, run in sorted(events, key=lambda e: e[0]):
        run(_Actor(PatientService(on(moment)), principal, spec.id))
        deps.session.flush()


@dataclass(frozen=True)
class _Actor:
    """Пациент, действующий через сервис с часами, остановленными на моменте события."""

    service: PatientService
    principal: Principal
    patient_id: str


_Event = Callable[[_Actor], None]


def _questionnaire(instrument: Instrument, answers: list[int], actor: _Actor) -> None:
    actor.service.submit_questionnaire(actor.principal, actor.patient_id, instrument, answers)


def _intake(slot_date: date, slot: IntakeSlot, reason: MissedReason | None, actor: _Actor) -> None:
    actor.service.mark_intake(
        actor.principal,
        actor.patient_id,
        slot_date=slot_date,
        slot=slot,
        status=IntakeStatus.MISSED if reason else IntakeStatus.TAKEN,
        missed_reason=reason,
    )
