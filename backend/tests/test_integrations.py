"""Окно в МИС (ЕМИАС, 1С), выгрузка FHIR и экстренные предупреждения пациенту."""

from typing import Any

import pytest

from clinical_compass.config import DEV_INTEGRATION_KEYS
from clinical_compass.seed import answers_for
from conftest import Api, find_alert

EMIAS_KEY = {"X-Integration-Key": DEV_INTEGRATION_KEYS["emias"]}
ONEC_KEY = {"X-Integration-Key": DEV_INTEGRATION_KEYS["onec"]}
DOC_A = {"emias": "DEMO-EMIAS-DOC-A", "onec": "DEMO-1C-DOC-A"}


def _launch(api: Api, system: str, doctor: str, patient: str, key: dict[str, str]) -> tuple[int, Any]:
    body = {"doctor_external_id": doctor, "patient_external_id": patient}
    return api.call("POST", f"/integrations/{system}/launch", body=body, headers=key)


@pytest.mark.parametrize(("system", "key"), [("emias", EMIAS_KEY), ("onec", ONEC_KEY)])
def test_mis_opens_doctor_window_for_linked_patient(api: Api, system: str, key: dict[str, str]) -> None:
    prefix = "DEMO-EMIAS" if system == "emias" else "DEMO-1C"
    status, launch = _launch(api, system, DOC_A[system], f"{prefix}-1006", key)
    assert status == 201
    assert launch["launch_path"] == f"/#/embed/launch/{launch['code']}"

    status, session = api.call("POST", "/integrations/launch/exchange", body={"code": launch["code"]})
    assert status == 200
    assert (session["patient_id"], session["user"]["id"], session["system"]) == ("p_a6", "doc_a", system)

    auth = {"Authorization": f"Bearer {session['token']}"}
    status, dossier = api.call("GET", "/doctor/patients/p_a6/timeline", headers=auth)
    assert status == 200
    assert dossier["patient"]["id"] == "p_a6"
    assert api.call("GET", "/doctor/patients/p_b1/timeline", headers=auth)[0] == 403
    _, audit = api.call("GET", "/doctor/patients/p_a6/audit", headers=auth)
    assert f"integration.opened_from_{system}" in {e["action"] for e in audit}


def test_launch_code_is_single_use(api: Api) -> None:
    _, launch = _launch(api, "emias", DOC_A["emias"], "DEMO-EMIAS-1001", EMIAS_KEY)
    assert api.call("POST", "/integrations/launch/exchange", body={"code": launch["code"]})[0] == 200
    status, body = api.call("POST", "/integrations/launch/exchange", body={"code": launch["code"]})
    assert status == 401
    assert "устарела" in body["message"]


def test_launch_requires_system_key_and_linked_patient(api: Api) -> None:
    assert _launch(api, "emias", DOC_A["emias"], "DEMO-EMIAS-1001", ONEC_KEY)[0] == 403
    assert _launch(api, "emias", DOC_A["emias"], "DEMO-EMIAS-1001", {})[0] == 403
    status, body = _launch(api, "emias", DOC_A["emias"], "DEMO-EMIAS-2001", EMIAS_KEY)
    assert status == 403
    assert "не закреплён" in body["message"]
    assert _launch(api, "emias", DOC_A["emias"], "UNKNOWN-1", EMIAS_KEY)[0] == 404


def test_fhir_summary_for_mis(api: Api) -> None:
    status, bundle = api.call(
        "GET", "/integrations/emias/patients/DEMO-EMIAS-1006/summary", headers=EMIAS_KEY
    )
    assert status == 200
    assert bundle["resourceType"] == "Bundle"
    resources = [e["resource"] for e in bundle["entry"]]
    kinds = {r["resourceType"] for r in resources}
    assert {"Patient", "Observation", "Flag"} <= kinds
    patient = next(r for r in resources if r["resourceType"] == "Patient")
    assert {"system": "urn:clinical-compass:emias:patient", "value": "DEMO-EMIAS-1006"} in patient[
        "identifier"
    ]
    phq = [
        r
        for r in resources
        if r["resourceType"] == "Observation" and r["code"]["coding"][0]["code"] == "44261-6"
    ]
    assert [o["valueInteger"] for o in phq] == [7, 11]
    flags = {r["code"]["coding"][0]["code"] for r in resources if r["resourceType"] == "Flag"}
    assert "R_SELF_HARM" in flags
    assert api.call("GET", "/integrations/emias/patients/DEMO-EMIAS-1006/summary")[0] == 403


def test_demo_directory_lists_only_own_patients(api: Api) -> None:
    status, directory = api.call("GET", "/integrations/demo/onec/directory")
    assert status == 200
    doctor_a = next(d for d in directory["doctors"] if d["external_id"] == "DEMO-1C-DOC-A")
    assert len(doctor_a["patients"]) == 6
    assert all(p["external_id"].startswith("DEMO-1C-10") for p in doctor_a["patients"])


def test_embedding_is_restricted_by_frame_ancestors(api: Api) -> None:
    res = api.client.get("/health")
    assert res.headers["content-security-policy"] == "frame-ancestors 'self'"
    assert res.headers["x-content-type-options"] == "nosniff"


# --- Экстренное предупреждение пациенту ---------------------------------------------------------


def test_emergency_notice_and_patient_actions_reach_the_doctor(api: Api) -> None:
    body = {"instrument": "PHQ9", "item_scores": answers_for(6, 9, item9=1)}
    api.call("POST", "/patients/p_a1/questionnaires", as_="p_a1", body=body)
    _, dashboard = api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")
    [alert_id] = dashboard["emergency_alert_ids"]

    for action in ("shown", "call_112"):
        status, _ = api.call(
            "POST", "/patients/p_a1/safety-actions", as_="p_a1", body={"alert_id": alert_id, "action": action}
        )
        assert status == 201
    alert = find_alert(api.queue("doc_a"), "R_SELF_HARM", "p_a1")
    assert [a["action"] for a in alert["patient_safety_actions"]] == ["shown", "call_112"]

    api.call(
        "POST",
        "/patients/p_a1/safety-actions",
        as_="p_a1",
        body={"alert_id": alert_id, "action": "dismissed"},
    )
    assert api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")[1]["emergency_alert_ids"] == []


def test_safety_actions_only_for_own_emergency_alerts(api: Api) -> None:
    queue = api.queue("doc_a")
    self_harm = find_alert(queue, "R_SELF_HARM", "p_a6")["alert"]["id"]
    body = {"alert_id": self_harm, "action": "call_112"}
    assert api.call("POST", "/patients/p_a1/safety-actions", as_="p_a1", body=body)[0] == 404
    assert api.call("POST", "/patients/p_a6/safety-actions", as_="p_a1", body=body)[0] == 403
    not_urgent = find_alert(queue, "R_CPK_HIGH", "p_a6")["alert"]["id"]
    body = {"alert_id": not_urgent, "action": "call_112"}
    assert api.call("POST", "/patients/p_a6/safety-actions", as_="p_a6", body=body)[0] == 400
