"""Сквозная цепочка P0 через HTTP: пациент → backend → Patient State → rule engine → очередь врача."""

import base64
from datetime import datetime
from pathlib import Path

from clinical_compass.domain.enums import DoctorPriority
from clinical_compass.seed import answers_for
from conftest import INTERNAL_TOKEN, Api, ApiFactory, find_alert, rule_ids

DOCTOR_A_PATIENTS = {"p_a1", "p_a2", "p_a3", "p_a4", "p_a5", "p_a6"}


class FailingExtractor:
    model_version = "failing"

    def extract(self, *, message_id: str, patient_id: str, timestamp: datetime, text: str) -> object:
        raise RuntimeError("LLM недоступна")


# --- Доступ и привязка ---------------------------------------------------------------------------


def test_doctor_sees_only_linked_patients(api: Api) -> None:
    _, a = api.call("GET", "/doctor/patients", as_="doc_a")
    _, b = api.call("GET", "/doctor/patients", as_="doc_b")
    assert {r["patient"]["id"] for r in a} == DOCTOR_A_PATIENTS
    assert {r["patient"]["id"] for r in b} == {"p_b1", "p_b2", "p_b3"}


def test_foreign_doctor_other_patient_and_admin_are_denied(api: Api) -> None:
    assert api.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_b")[0] == 403
    assert api.call("GET", "/patients/p_a2/dashboard", as_="p_a1")[0] == 403
    assert api.call("GET", "/patients/p_a1/state", as_="adm_1")[0] == 403
    assert api.call("GET", "/doctor/queue", as_="p_a1")[0] == 403
    assert api.call("GET", "/admin/booking-tasks", as_="doc_a")[0] == 403
    status, body = api.call("GET", "/doctor/patients")
    assert status == 401
    assert set(body) == {"error", "message"}


# --- Пациент → очередь врача ---------------------------------------------------------------------


def test_gad7_worsening_creates_normal_alert_and_patient_notice(api: Api) -> None:
    status, body = api.call(
        "POST",
        "/patients/p_a1/questionnaires",
        as_="p_a1",
        body={"instrument": "GAD7", "item_scores": answers_for(16, 7)},
    )
    assert status == 201
    assert body["response"]["total_score"] == 16
    assert body["response"]["delta_from_previous"] == 4
    assert [n["template"]["id"] for n in body["patient_notices"]] == ["gad_worsening_v1"]

    alert = find_alert(api.queue("doc_a"), "R_GAD_WORSENING", "p_a1")
    assert alert["alert"]["doctor_priority"] == "normal"
    assert alert["alert"]["patient_action"] == "inform_at_next_contact"
    assert alert["alert"]["status"] == "delivered_to_workplace"
    assert alert["why"]
    assert rule_ids(api.queue("doc_b"), "p_a1") == []


def test_phq9_item9_is_urgent_pinned_and_recommends_ambulance(api: Api) -> None:
    _, body = api.call(
        "POST",
        "/patients/p_a1/questionnaires",
        as_="p_a1",
        body={"instrument": "PHQ9", "item_scores": answers_for(6, 9, item9=1)},
    )
    assert "recommend_ambulance" in [n["patient_action"] for n in body["patient_notices"]]
    queue = api.queue("doc_a")
    assert queue[0]["alert"]["doctor_priority"] == "urgent"
    assert queue[0]["pinned"] is True
    assert "R_SELF_HARM" in rule_ids(queue, "p_a1")


def test_same_idempotency_key_is_not_duplicated(api: Api) -> None:
    key = {"Idempotency-Key": "gad-a1-1"}
    body = {"instrument": "GAD7", "item_scores": answers_for(10, 7)}
    s1, r1 = api.call("POST", "/patients/p_a1/questionnaires", as_="p_a1", body=body, headers=key)
    s2, r2 = api.call("POST", "/patients/p_a1/questionnaires", as_="p_a1", body=body, headers=key)
    assert (s1, s2) == (201, 201)
    assert r2["duplicate"] is True
    assert r2["response"]["id"] == r1["response"]["id"]
    _, history = api.call("GET", "/patients/p_a1/history", as_="p_a1")
    assert len([q for q in history["questionnaires"] if q["instrument"] == "GAD7"]) == 2


def test_questionnaire_not_due_and_incomplete_answers_are_rejected(api: Api) -> None:
    status, body = api.call(
        "POST",
        "/patients/p_a2/questionnaires",
        as_="p_a2",
        body={"instrument": "GAD7", "item_scores": answers_for(5, 7)},
    )
    assert status == 409
    assert "пока не назначен" in body["message"]
    status, _ = api.call(
        "POST",
        "/patients/p_a1/questionnaires",
        as_="p_a1",
        body={"instrument": "GAD7", "item_scores": [1, 1]},
    )
    assert status == 400


def test_decided_to_stop_is_high_and_reason_counts_in_adherence(api: Api) -> None:
    status, _ = api.call(
        "POST",
        "/patients/p_a1/intakes",
        as_="p_a1",
        body={
            "slot_date": "2026-10-21",
            "slot": "morning",
            "status": "missed",
            "missed_reason": "decided_to_stop",
        },
    )
    assert status == 201
    assert find_alert(api.queue("doc_a"), "R_INTENTION_TO_STOP", "p_a1")["alert"]["doctor_priority"] == "high"
    _, dossier = api.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_a")
    assert dossier["adherence_14d"]["missed_reasons"]["decided_to_stop"] == 1


def test_correcting_todays_intake_replaces_the_mark(api: Api) -> None:
    body = {"slot_date": "2026-10-21", "slot": "evening", "status": "missed", "missed_reason": "forgot"}
    api.call("POST", "/patients/p_a1/intakes", as_="p_a1", body=body)
    _, corrected = api.call(
        "POST", "/patients/p_a1/intakes", as_="p_a1", body={**body, "status": "taken", "missed_reason": None}
    )
    assert corrected["corrected"] is True
    _, dashboard = api.call("GET", "/patients/p_a1/dashboard", as_="p_a1")
    evening = next(s for s in dashboard["today"]["slots"] if s["slot"] == "evening")
    assert evening["intake"]["status"] == "taken"
    assert (
        api.call("POST", "/patients/p_a1/intakes", as_="p_a1", body={**body, "slot_date": "2026-10-10"})[0]
        == 400
    )


def test_out_of_scope_complaint_is_high_neutral_and_not_classified(api: Api) -> None:
    _, body = api.call(
        "POST",
        "/patients/p_a1/symptoms",
        as_="p_a1",
        body={
            "normalized_type": "other_unlisted",
            "patient_phrase": "Немеет мизинец",
            "affects_daily_life": "unknown",
        },
    )
    assert [n["template"]["id"] for n in body["patient_notices"]] == ["out_of_scope_v1"]
    alert = find_alert(api.queue("doc_a"), "R_OUT_OF_SCOPE", "p_a1")
    assert alert["alert"]["doctor_priority"] == "high"
    assert alert["medical_urgency_classified"] is False
    assert "Немеет мизинец" in alert["why"][0]["summary"]


def test_free_text_is_saved_and_mock_extraction_flags_safety_signal(api: Api) -> None:
    status, body = api.call(
        "POST", "/patients/p_a1/messages", as_="p_a1", body={"text": "Последние дни не хочу жить"}
    )
    assert status == 201
    assert body["message"]["extraction_status"] == "extracted"
    alert = find_alert(api.queue("doc_a"), "R_SELF_HARM", "p_a1")
    assert alert["why"][0]["confirmation"] == "ожидает подтверждения"
    _, dossier = api.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_a")
    assert dossier["messages"][0]["text"] == "Последние дни не хочу жить"


def test_negated_phrase_does_not_raise_safety_alert(api: Api) -> None:
    api.call(
        "POST",
        "/patients/p_a1/messages",
        as_="p_a1",
        body={"text": "Я никогда не хочу умереть, просто устала"},
    )
    assert "R_SELF_HARM" not in rule_ids(api.queue("doc_a"), "p_a1")


def test_ai_failure_keeps_the_message(make_api: ApiFactory) -> None:
    api = make_api(extractor=FailingExtractor())
    status, body = api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"text": "Тошнит по утрам"})
    assert status == 201
    assert body["message"]["extraction_status"] == "failed"
    _, dossier = api.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_a")
    assert dossier["messages"][0]["text"] == "Тошнит по утрам"


def test_attachments_are_readable_only_by_patient_and_their_doctor(api: Api) -> None:
    pdf = base64.b64encode(b"%PDF").decode()
    _, body = api.call(
        "POST",
        "/patients/p_a1/messages",
        as_="p_a1",
        body={
            "text": "Выписка",
            "attachments": [{"filename": "scan.pdf", "mime_type": "application/pdf", "data_base64": pdf}],
        },
    )
    attachment_id = body["message"]["attachments"][0]["id"]
    path = f"/patients/p_a1/attachments/{attachment_id}"
    status, content = api.call("GET", path, as_="doc_a")
    assert (status, content) == (200, b"%PDF")
    assert api.call("GET", path, as_="p_a1")[0] == 200
    assert api.call("GET", path, as_="doc_b")[0] == 403
    exe = {
        "filename": "run.exe",
        "mime_type": "application/x-msdownload",
        "data_base64": base64.b64encode(b"x").decode(),
    }
    assert api.call("POST", "/patients/p_a1/messages", as_="p_a1", body={"attachments": [exe]})[0] == 400


# --- Рабочее место врача -------------------------------------------------------------------------


def test_queue_pins_urgent_first_then_orders_by_priority(api: Api) -> None:
    queue = api.queue("doc_a")
    pinned = len([a for a in queue if a.get("pinned")])
    assert pinned > 0
    assert all(a.get("pinned") for a in queue[:pinned])
    ranks = [DoctorPriority(a["alert"]["doctor_priority"]).rank for a in queue[pinned:]]
    assert ranks == sorted(ranks, reverse=True)
    assert all(a["alert"]["status"] != "resolved" for a in queue)


def test_alert_lifecycle_keeps_timestamps_and_acting_doctor(api: Api) -> None:
    alert_id = api.queue("doc_a")[0]["alert"]["id"]
    api.call("POST", f"/doctor/alerts/{alert_id}/view", as_="doc_a")
    _, ack = api.call("POST", f"/doctor/alerts/{alert_id}/acknowledge", as_="doc_a")
    assert ack["alert"]["status"] == "acknowledged"
    assert ack["alert"]["viewed_at"] is not None
    assert ack["acknowledged_by"] == "Миронова А. С."
    _, resolved = api.call("POST", f"/doctor/alerts/{alert_id}/resolve", as_="doc_a")
    assert resolved["alert"]["status"] == "resolved"
    assert all(a["alert"]["id"] != alert_id for a in api.queue("doc_a"))
    assert api.call("POST", f"/doctor/alerts/{alert_id}/resolve", as_="doc_b")[0] == 403
    _, audit = api.call("GET", f"/doctor/patients/{resolved['patient']['id']}/audit", as_="doc_a")
    assert {"alert.view", "alert.acknowledge", "alert.resolve"} <= {e["action"] for e in audit}


def test_questionnaire_interval_defaults_to_14_days_and_is_configurable(api: Api) -> None:
    _, dossier = api.call("GET", "/doctor/patients/p_a2/timeline", as_="doc_a")
    gad = next(s for s in dossier["schedules"] if s["instrument"] == "GAD7")
    assert (gad["interval_days"], gad["configured_by"]) == (14, "system_default")
    status, updated = api.call(
        "PUT", "/doctor/patients/p_a2/questionnaire-schedules/GAD7", as_="doc_a", body={"interval_days": 3}
    )
    assert status == 200
    assert (updated["interval_days"], updated["configured_by"]) == (3, "doctor")
    assert updated["due_status"] != "upcoming"
    body = {"instrument": "GAD7", "item_scores": answers_for(6, 7)}
    assert api.call("POST", "/patients/p_a2/questionnaires", as_="p_a2", body=body)[0] == 201


def test_routing_is_hidden_from_patient_until_doctor_confirms(api: Api) -> None:
    _, before = api.call("GET", "/patients/p_b1/dashboard", as_="p_b1")
    assert before["routing"] is None
    assert "R_ROUTING_REVIEW" in rule_ids(api.queue("doc_b"), "p_b1")
    status, routing = api.call(
        "POST", "/doctor/patients/p_b1/routing", as_="doc_b", body={"decision": "required"}
    )
    assert status == 200
    assert routing["patient_visible"] is True
    _, after = api.call("GET", "/patients/p_b1/dashboard", as_="p_b1")
    assert after["routing"]["doctor_decision"] == "required"
    assert after["routing"]["template"]["id"] == "routing_required_v1"
    api.call("POST", "/doctor/patients/p_b1/routing", as_="doc_b", body={"decision": "none"})
    assert api.call("GET", "/patients/p_b1/dashboard", as_="p_b1")[1]["routing"] is None


def test_contact_deadline_creates_admin_task_without_clinical_data(api: Api) -> None:
    body = {"deadline": "2026-10-23T12:00:00Z"}
    assert api.call("POST", "/doctor/patients/p_a3/contact-deadline", as_="doc_a", body=body)[0] == 201
    status, tasks = api.call("GET", "/admin/booking-tasks", as_="adm_1")
    assert status == 200
    [task] = tasks
    assert set(task) == {
        "id", "patient_id", "patient_name", "patient_phone", "requested_by",
        "deadline", "status", "created_at", "updated_at",
    }  # fmt: skip
    status, updated = api.call(
        "PATCH", f"/admin/booking-tasks/{task['id']}", as_="adm_1", body={"status": "scheduled"}
    )
    assert (status, updated["status"]) == (200, "scheduled")


# --- Контракты и граница AI-слоя -----------------------------------------------------------------


def test_patient_state_of_every_seeded_patient_matches_schema(api: Api) -> None:
    for patient_id in sorted(DOCTOR_A_PATIENTS):
        status, body = api.call("GET", f"/patients/{patient_id}/state", as_="doc_a")
        assert status == 200
        assert body["schema_errors"] == [], patient_id
        assert body["patient_state"]["schema_version"] == "0.2.0"


def test_evaluate_rules_is_pure_schema_checked_and_token_protected(api: Api) -> None:
    _, state = api.call("GET", "/patients/p_a3/state", as_="doc_a")
    payload = {"patient_state": state["patient_state"], "context": {"sex": "female"}}
    assert api.call("POST", "/internal/evaluate-rules", body=payload)[0] == 403
    queue_before = api.queue("doc_a")
    status, results = api.internal("/internal/evaluate-rules", payload)
    assert status == 200
    assert {"R_GAD_WORSENING", "R_PHQ_SCREEN_POSITIVE"} <= {r["rule_id"] for r in results}
    assert api.queue("doc_a") == queue_before
    bad = {"patient_state": {"schema_version": "0.2.0", "patient_id": "x", "updated_at": "now", "foo": 1}}
    assert api.internal("/internal/evaluate-rules", bad)[0] == 400


def test_ai_layer_facts_are_accepted_in_schema_form(api: Api) -> None:
    symptom = {
        "id": "llm_sym_1",
        "normalized_type": "nausea",
        "polarity": "present",
        "experiencer": "patient",
        "temporality": "current",
        "affects_daily_life": "yes",
        "source": "text_llm",
        "confirmation": "pending",
    }
    status, body = api.internal("/internal/patients/p_a5/facts", {"symptoms": [symptom]})
    assert status == 201
    assert [a["alert"]["rule_id"] for a in body["alerts"]] == ["R_AE_IMPACT"]
    unknown = {**symptom, "id": "x", "normalized_type": "flu"}
    assert api.internal("/internal/patients/p_a5/facts", {"symptoms": [unknown]})[0] == 400

    status, extraction = api.internal(
        "/internal/extract", {"patient_id": "p_a5", "text": "Брошу принимать таблетки"}
    )
    assert status == 200
    assert extraction["schema_version"] == "0.2.0"
    assert api.internal("/internal/patients/p_a5/facts", {"extraction": extraction})[0] == 201
    assert "R_INTENTION_TO_STOP" in rule_ids(api.queue("doc_a"), "p_a5")


def test_internal_endpoints_reject_wrong_token(api: Api) -> None:
    headers = {"X-Internal-Token": INTERNAL_TOKEN + "x"}
    assert (
        api.call("POST", "/internal/extract", body={"patient_id": "p_a5", "text": "т"}, headers=headers)[0]
        == 403
    )


def test_data_persists_across_restarts(make_api: ApiFactory) -> None:
    first = make_api()
    first.call(
        "POST",
        "/patients/p_a1/symptoms",
        as_="p_a1",
        body={"normalized_type": "headache", "affects_daily_life": "no"},
    )
    db_url = first.client.app.state.runtime.settings.database_url  # type: ignore[attr-defined]
    second = make_api(db_file=_path_of(db_url))
    _, dossier = second.call("GET", "/doctor/patients/p_a1/timeline", as_="doc_a")
    assert "headache" in [s["normalized_type"] for s in dossier["symptoms"]]


def _path_of(sqlite_url: str) -> Path:
    return Path(sqlite_url.removeprefix("sqlite:///"))


# --- Справочники для клиентов --------------------------------------------------------------------


def test_meta_exposes_instruments_and_vocabulary_from_contracts(api: Api) -> None:
    status, meta = api.call("GET", "/meta")
    assert status == 200
    instruments = {i["instrument"]: i for i in meta["instruments"]}
    assert instruments["GAD7"]["item_count"] == 7
    assert instruments["PHQ9"]["item_count"] == 9
    assert meta["vocabulary"]["missed_reasons"]["forgot"]
    assert api.call("GET", "/health")[0] == 200


def test_openapi_schema_is_published(api: Api) -> None:
    status, schema = api.call("GET", "/openapi.json")
    assert status == 200
    assert "/patients/{patient_id}/questionnaires" in schema["paths"]
