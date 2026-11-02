"""Геймификация наблюдений никогда не влияет на клинические правила."""

from datetime import date, timedelta

from clinical_compass.domain.engagement import weekly_engagement
from conftest import Api


def test_weekly_engagement_deduplicates_entries_and_ignores_outside_window() -> None:
    today = date(2026, 11, 2)
    p = weekly_engagement(
        today=today,
        record_dates=[
            today,
            today,
            today - timedelta(days=1),
            today - timedelta(days=7),
            today + timedelta(days=1),
        ],
    )
    assert p["window_days"] == 7
    assert p["days_with_entries"] == 2
    assert [d["has_entry"] for d in p["days"]] == [False] * 5 + [True, True]
    assert p["achievement"]["id"] == "first_entry"


def test_no_entries_no_achievement() -> None:
    p = weekly_engagement(today=date(2026, 11, 2), record_dates=[])
    assert p["achievement"] is None
    assert p["days_with_entries"] == 0


def test_achievement_only_depends_on_days_not_clinical_values() -> None:
    today = date(2026, 11, 2)
    dates = [today - timedelta(days=days_back) for days_back in range(5)]
    p = weekly_engagement(today=today, record_dates=dates)
    assert p["achievement"] == {"id": "five_days", "title": "Пять дней с записями"}


def test_dashboard_engagement_is_patient_private_and_read_only(api: Api) -> None:
    status, dashboard = api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")
    assert status == 200
    progress = dashboard["engagement"]
    assert len(progress["days"]) == 7
    assert 0 <= progress["days_with_entries"] <= 7
    assert progress["days_with_entries"] == sum(d["has_entry"] for d in progress["days"])
    assert api.call("GET", "/patients/p_a1/dashboard", as_="p_a2")[0] == 403
    # Чтение прогресса не создаёт алертов и не меняет очередь врача.
    queue_before = api.queue("doc_a")
    api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")
    assert api.queue("doc_a") == queue_before


def test_a_missed_medication_is_counted_as_record_not_as_failure(api: Api) -> None:
    _, before = api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")
    _, marked = api.call(
        "POST",
        "/patients/p_a1/intakes",
        as_="p_a1",
        body={"slot_date": "2026-10-21", "slot": "evening", "status": "missed", "missed_reason": "forgot"},
    )
    assert marked["intake"]["status"] == "missed"
    _, after = api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")
    assert after["engagement"]["days_with_entries"] >= before["engagement"]["days_with_entries"]
    assert after["engagement"]["days_with_entries"] <= 7
    _, corrected = api.call(
        "POST",
        "/patients/p_a1/intakes",
        as_="p_a1",
        body={"slot_date": "2026-10-21", "slot": "evening", "status": "taken"},
    )
    assert corrected["intake"]["status"] == "taken"
    _, after_correction = api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")
    assert after_correction["engagement"] == after["engagement"]
