"""Производные поля: расписание опросников, дельты, приверженность (§6, §7)."""

from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from typing import Any

from clinical_compass.domain.enums import CompletionStatus, Instrument, IntakeSlot, IntakeStatus, MissedReason
from clinical_compass.domain.state import MedicationIntake, QuestionnaireResponse, QuestionnaireSchedule

OVERDUE_AFTER_DAYS = 3
"""Через сколько дней после срока опрос показывается как просроченный (только отображение)."""


_EPOCH = datetime.min.replace(tzinfo=UTC)


class DueStatus(StrEnum):
    UPCOMING = "upcoming"
    DUE = "due"
    OVERDUE = "overdue"


@dataclass(frozen=True)
class ScheduleStatus:
    schedule: QuestionnaireSchedule
    next_due_at: datetime
    status: DueStatus
    last_at: datetime | None

    def to_json(self) -> dict[str, Any]:
        return {
            **self.schedule.model_copy(update={"next_due_at": self.next_due_at}).to_schema(),
            "due_status": self.status.value,
            "last_administered_at": self.last_at.isoformat() if self.last_at else None,
        }


def _completed(
    responses: Iterable[QuestionnaireResponse], instrument: Instrument
) -> list[QuestionnaireResponse]:
    return sorted(
        (
            r
            for r in responses
            if r.instrument is instrument and r.completion_status is CompletionStatus.COMPLETE
        ),
        key=lambda r: r.administered_at,
    )


def schedule_status(
    schedule: QuestionnaireSchedule,
    responses: Iterable[QuestionnaireResponse],
    observation_start: datetime,
    now: datetime,
) -> ScheduleStatus:
    """Следующий срок = последнее завершённое заполнение + интервал; без заполнений — начало наблюдения."""
    done = _completed(responses, schedule.instrument)
    last = done[-1].administered_at if done else None
    next_due = last + timedelta(days=schedule.interval_days) if last else observation_start
    if now < next_due:
        status = DueStatus.UPCOMING
    elif (now - next_due).days >= OVERDUE_AFTER_DAYS:
        status = DueStatus.OVERDUE
    else:
        status = DueStatus.DUE
    return ScheduleStatus(schedule=schedule, next_due_at=next_due, status=status, last_at=last)


@dataclass(frozen=True)
class Deltas:
    baseline: int
    from_previous: int | None
    from_baseline: int | None


def deltas_for(instrument: Instrument, total: int, previous: Iterable[QuestionnaireResponse]) -> Deltas:
    """Подписанные дельты (§6.1): первый ответ становится baseline."""
    prior = [r for r in _completed(previous, instrument) if r.total_score is not None]
    if not prior:
        return Deltas(baseline=total, from_previous=None, from_baseline=None)
    baseline = prior[0].total_score or 0
    last = prior[-1].total_score or 0
    return Deltas(baseline=baseline, from_previous=total - last, from_baseline=total - baseline)


def latest_by_slot(intakes: Iterable[MedicationIntake]) -> dict[tuple[date, IntakeSlot], MedicationIntake]:
    """Последняя отметка за каждый слот: исправление заменяет исходную."""
    result: dict[tuple[date, IntakeSlot], MedicationIntake] = {}
    for intake in intakes:
        key = (intake.slot_date, intake.slot)
        current = result.get(key)
        if current is None or (intake.marked_at or _EPOCH) >= (current.marked_at or _EPOCH):
            result[key] = intake
    return result


@dataclass(frozen=True)
class SlotMark:
    date: date
    slot: IntakeSlot
    status: IntakeStatus
    intake: MedicationIntake | None


@dataclass(frozen=True)
class Adherence:
    """Доля принятых доз от назначенных; пропуски и отсутствие отметок — раздельно."""

    window_days: int
    slots: tuple[SlotMark, ...]

    def _count(self, status: IntakeStatus) -> int:
        return sum(1 for s in self.slots if s.status is status)

    @property
    def taken(self) -> int:
        return self._count(IntakeStatus.TAKEN)

    @property
    def missed(self) -> int:
        return self._count(IntakeStatus.MISSED)

    @property
    def unknown(self) -> int:
        return self._count(IntakeStatus.UNKNOWN)

    @property
    def scheduled(self) -> int:
        return len(self.slots)

    @property
    def ratio(self) -> float | None:
        return self.taken / self.scheduled if self.scheduled else None

    @property
    def consecutive_missed(self) -> int:
        count = 0
        for s in self.slots:
            if s.status is not IntakeStatus.MISSED:
                break
            count += 1
        return count

    @property
    def missed_reasons(self) -> dict[MissedReason, int]:
        reasons = Counter(
            (s.intake.missed_reason if s.intake and s.intake.missed_reason else MissedReason.UNKNOWN)
            for s in self.slots
            if s.status is IntakeStatus.MISSED
        )
        return dict(reasons)

    def to_json(self, *, include_slots: bool = False) -> dict[str, Any]:
        data: dict[str, Any] = {
            "window_days": self.window_days,
            "scheduled": self.scheduled,
            "taken": self.taken,
            "missed": self.missed,
            "unknown": self.unknown,
            "adherence": self.ratio,
            "consecutive_missed": self.consecutive_missed,
            "missed_reasons": {k.value: v for k, v in self.missed_reasons.items()},
        }
        if include_slots:
            data["slots"] = [
                {
                    "date": s.date.isoformat(),
                    "slot": s.slot.value,
                    "status": s.status.value,
                    "missed_reason": s.intake.missed_reason.value
                    if s.intake and s.intake.missed_reason
                    else None,
                    "marked_at": s.intake.marked_at.isoformat() if s.intake and s.intake.marked_at else None,
                }
                for s in self.slots
            ]
        return data


def adherence(
    intakes: Iterable[MedicationIntake],
    plan_slots: Sequence[IntakeSlot],
    plan_start: date,
    today: date,
    days: int,
) -> Adherence:
    """Приверженность за `days` дней, включая сегодня, от новых к старым.

    Сегодняшние слоты без отметки не учитываются — их ещё можно отметить.
    """
    latest = latest_by_slot(intakes)
    marks: list[SlotMark] = []
    for back in range(days):
        day = today - timedelta(days=back)
        if day < plan_start:
            break
        for slot in reversed(plan_slots):
            intake = latest.get((day, slot))
            if back == 0 and intake is None:
                continue
            status = intake.status if intake else IntakeStatus.UNKNOWN
            marks.append(SlotMark(date=day, slot=slot, status=status, intake=intake))
    return Adherence(window_days=days, slots=tuple(marks))
