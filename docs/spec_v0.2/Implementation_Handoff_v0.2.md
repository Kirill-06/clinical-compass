# Clinical Compass — Implementation Handoff v0.2

## Рома — Data / Analytics

### Сейчас

1. Принять `annotation_guideline_v0.2.md` как контракт разметки.
2. Переделать dataset list в audit-таблицу по двум задачам:
   - clinical NLP/extraction;
   - longitudinal predictive ML (отдельный трек, не blocker MVP).
3. Для каждого источника указать, какие поля v0.2 реально покрываются.
4. Собрать первые 100–150 seed messages для проверки схемы.
5. Обязательно включить hard cases: negation, other person, hypothetical, idioms, multiple symptoms, out-of-scope, labs in text.
6. Подготовить формат clinician review/hold-out.

### Не делать пока

- не обучать predictive model без явного target;
- не смешивать social-media depression classification с clinical patient monitoring;
- не считать synthetic data доказательством clinical validity.

### Output

- `dataset_audit_v0.2.csv/md`;
- `seed_annotations_v0.2.jsonl`;
- список gaps: какие labels невозможно получить из внешних данных.

---

## Кирилл — Application / Backend / Frontend

### P0: end-to-end

1. RBAC: Patient / Doctor / Admin.
2. DoctorPatientLink.
3. GAD-7 + PHQ-9 persistence/scoring.
4. QuestionnaireSchedule: default 14 days, doctor-configurable.
5. Medication intake: morning/evening, missed reason.
6. Symptom/adverse-event form.
7. Patient free-text/chat persistence.
8. Doctor patient list + timeline + priority queue.
9. Alert object with `doctor_priority`, `patient_action`, rule/source metadata.
10. Out-of-scope flow: no invented diagnosis/urgency.
11. Routing: hidden from patient until doctor confirms; then `preferred|required` can be shown.
12. Doctor can set contact deadline -> AdminBookingTask.
13. Admin sees only contact + deadline/status, no clinical details.

### AI integration boundary

На P0 AI можно мокать. Нужен стабильный контракт:

```text
POST /internal/extract
-> FreeTextExtraction v0.2

POST /internal/evaluate-rules
-> RuleResult[]
```

Не зашивать NLP logic во frontend/backend handlers.

### UI priority

- Patient: mobile-first responsive.
- Doctor: desktop-first responsive, usable on mobile.
- Native doctor app не требуется сейчас.

### Definition of Done

Patient submits -> persisted -> linked doctor sees -> rule alert appears -> doctor acts -> optional routing/booking -> audit trail retained.

---

## Борис — AI/Data/Technical integration

1. Поддерживать `patient_state_v0.2.schema.json`.
2. Поддерживать versioned `alert_rules_v0.2.yaml`.
3. Сделать baseline structured extraction (LLM/mock) и schema validation.
4. Подготовить deterministic rule evaluator/tests.
5. С Ромой определить evaluation report.
6. С Кириллом согласовать API payloads.
7. Перед v0.3 прогнать 10–20 E2E scenarios и собрать error log.

---

## Давлет — Medical review

Medical logic v0.2 считается зафиксированной. Новые изменения — только точечно:

- review disputed scenarios;
- check patient-facing templates;
- review clinician hold-out;
- validate any new emergency/red-flag rule before it enters config.
