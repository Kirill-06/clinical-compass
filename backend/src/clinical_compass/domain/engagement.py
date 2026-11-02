"""Немедицинский показатель ведения дневника — не оценка здоровья и не adherence.

Награда только за наличие записи в день. Не оцениваем симптомы,
ответы опросников или статус taken/missed (оба считаются записью).
"""

from collections.abc import Iterable
from datetime import date, timedelta
from typing import Any

WINDOW_DAYS = 7


def weekly_engagement(*, today: date, record_dates: Iterable[date]) -> dict[str, Any]:
    """7 календарных дней клиники, включая сегодня; повторы не увеличивают прогресс."""
    first = today - timedelta(days=WINDOW_DAYS - 1)
    active = {day for day in record_dates if first <= day <= today}
    count = len(active)
    if count >= 5:
        achievement = {"id": "five_days", "title": "Пять дней с записями"}
    elif count >= 3:
        achievement = {"id": "three_days", "title": "Три дня с записями"}
    elif count >= 1:
        achievement = {"id": "first_entry", "title": "Первая запись"}
    else:
        achievement = None
    return {
        "window_days": WINDOW_DAYS,
        "days_with_entries": count,
        "days": [
            {
                "date": (first + timedelta(days=i)).isoformat(),
                "has_entry": first + timedelta(days=i) in active,
            }
            for i in range(WINDOW_DAYS)
        ],
        "achievement": achievement,
        "explanation": "Считаем только дни с записями, а не состояние здоровья или соблюдение лечения.",
    }
