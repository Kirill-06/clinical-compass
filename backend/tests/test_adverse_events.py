"""Сводка нежелательных явлений для врача и обезличенная выгрузка сводки по пациентам."""

import csv
import io
from typing import Any

from conftest import Api


def _summary(api: Api, doctor: str = "doc_a") -> dict[str, Any]:
    status, body = api.call("GET", "/doctor/adverse-events", as_=doctor)
    assert status == 200, body
    return dict(body)


def test_summary_groups_reports_by_effect_across_the_doctors_patients(api: Api) -> None:
    api.call(
        "POST",
        "/patients/p_a1/symptoms",
        as_="p_a1",
        body={"normalized_type": "dizziness", "affects_daily_life": "no", "severity": "mild"},
    )
    summary = _summary(api)
    by_type = {row["type"]: row for row in summary["effects"]}

    dizziness = by_type["dizziness"]
    assert dizziness["label"] == "Головокружение"
    assert dizziness["in_leaflet"] is True
    assert (dizziness["reports"], dizziness["patients"], dizziness["affects_daily_life"]) == (2, 2, 1)
    assert summary["patients_total"] == 6
    assert summary["missed_doses_due_to_adverse_event"] == 1


def test_effects_outside_the_leaflet_are_listed_with_patient_descriptions(api: Api) -> None:
    summary = _summary(api)
    [new_effect] = summary["outside_leaflet"]
    assert new_effect["patient"]["display_id"] == "P-1004"
    assert new_effect["description"] == "Шумит в ушах по вечерам"
    assert "full_name" not in new_effect["patient"]


def test_doctor_sees_only_own_patients_and_others_are_denied(api: Api) -> None:
    summary_b = _summary(api, "doc_b")
    assert summary_b["patients_total"] == 3
    assert summary_b["outside_leaflet"] == []
    assert api.call("GET", "/doctor/adverse-events", as_="p_a1")[0] == 403
    assert api.call("GET", "/doctor/adverse-events", as_="adm_1")[0] == 403


def test_patient_summary_export_is_a_pseudonymised_table(api: Api) -> None:
    res = api.client.get(
        "/doctor/exports/patients.csv", headers={"Authorization": f"Bearer {api.token('doc_a')}"}
    )
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    text = res.content.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text), delimiter=";"))

    assert [r["patient_id"] for r in rows] == [f"P-100{i}" for i in range(1, 7)]
    header = set(rows[0])
    # Без ФИО и телефона: таблица уходит на анализ, а не в медкарту.
    assert not header & {"full_name", "first_name", "phone"}
    assert "Корнилова" not in text
    assert "+7" not in text

    soloveva = next(r for r in rows if r["patient_id"] == "P-1003")
    assert (soloveva["gad7_last"], soloveva["gad7_change"], soloveva["phq9_last"]) == ("14", "4", "12")
    assert soloveva["missed_adverse_event"] == "1"
    assert soloveva["ae_reports"] == "1"
    assert soloveva["ae_outside_leaflet"] == "0"
    belov = next(r for r in rows if r["patient_id"] == "P-1004")
    assert belov["ae_outside_leaflet"] == "1"

    _, audit = api.call("GET", "/doctor/patients/p_a3/audit", as_="doc_a")
    assert "export.patients_csv" in {e["action"] for e in audit}


def test_export_is_only_for_doctors(api: Api) -> None:
    for user in ("p_a1", "adm_1"):
        res = api.client.get(
            "/doctor/exports/patients.csv", headers={"Authorization": f"Bearer {api.token(user)}"}
        )
        assert res.status_code == 403
