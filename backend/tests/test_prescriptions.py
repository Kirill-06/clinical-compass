"""Назначения препаратов: врач выписывает и отменяет, пациент видит список для аптеки."""

from typing import Any

from conftest import Api

RX = {
    "drug": "Магне B6",
    "dosage": "  1 таблетка ",
    "regimen": "3 раза в день во время еды",
    "duration": "1 месяц",
    "note": "Можно заменить аналогом",
}


def _patient_list(api: Api, patient_id: str) -> list[dict[str, Any]]:
    status, body = api.call("GET", f"/patients/{patient_id}/history", as_=patient_id)
    assert status == 200, body
    return list(body["prescriptions"])


def test_doctor_prescribes_and_patient_sees_it_in_the_list(api: Api) -> None:
    status, rx = api.call("POST", "/doctor/patients/p_a1/prescriptions", as_="doc_a", body=RX)
    assert status == 201, rx
    assert rx["dosage"] == "1 таблетка"
    assert rx["doctor"] == "Миронова А. С."

    drugs = [p["drug"] for p in _patient_list(api, "p_a1")]
    assert drugs[0] == "Магне B6"
    assert "Авиандр" in drugs

    _, dossier = api.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_a")
    assert dossier["prescriptions"][0]["id"] == rx["id"]


def test_cancelled_prescription_leaves_the_patient_list_but_stays_for_the_doctor(api: Api) -> None:
    _, rx = api.call("POST", "/doctor/patients/p_a1/prescriptions", as_="doc_a", body=RX)
    status, cancelled = api.call("POST", f"/doctor/prescriptions/{rx['id']}/cancel", as_="doc_a")
    assert status == 200, cancelled
    assert cancelled["cancelled_at"] is not None

    assert rx["id"] not in {p["id"] for p in _patient_list(api, "p_a1")}
    _, all_rx = api.call("GET", "/doctor/patients/p_a1/prescriptions", as_="doc_a")
    assert rx["id"] in {p["id"] for p in all_rx}

    _, audit = api.call("GET", "/doctor/patients/p_a1/audit", as_="doc_a")
    assert {"prescription.created", "prescription.cancelled"} <= {e["action"] for e in audit}


def test_only_the_attending_doctor_can_prescribe_or_cancel(api: Api) -> None:
    status, _ = api.call("POST", "/doctor/patients/p_a1/prescriptions", as_="doc_b", body=RX)
    assert status == 403
    status, _ = api.call("POST", "/doctor/patients/p_a1/prescriptions", as_="p_a1", body=RX)
    assert status == 403

    _, rx = api.call("POST", "/doctor/patients/p_a1/prescriptions", as_="doc_a", body=RX)
    status, _ = api.call("POST", f"/doctor/prescriptions/{rx['id']}/cancel", as_="doc_b")
    assert status == 403
    status, _ = api.call("POST", "/doctor/prescriptions/rx_missing/cancel", as_="doc_a")
    assert status == 404


def test_patient_sees_only_own_prescriptions(api: Api) -> None:
    status, _ = api.call("GET", "/patients/p_a1/history", as_="p_a2")
    assert status == 403


def test_blank_fields_are_rejected(api: Api) -> None:
    status, body = api.call(
        "POST", "/doctor/patients/p_a1/prescriptions", as_="doc_a", body={**RX, "regimen": "   "}
    )
    assert status == 400, body
    assert "как принимать" in body["message"]
    status, _ = api.call("POST", "/doctor/patients/p_a1/prescriptions", as_="doc_a", body={**RX, "drug": ""})
    assert status == 400
