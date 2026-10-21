# Клинический компас — техническая спецификация v0.2

**Статус:** зафиксированная рабочая спецификация (medical/data/technical contract).  
**Дата фиксации:** 20.10.2026  
**Основание:** требования кейса, клинические рекомендации по ГТР, листок-вкладыш АВИАНДР®, медицинская разметка и правила алертов команды, согласованные правки медицинского эксперта.  
**Назначение:** единый контракт для медицины, аналитики данных, AI/NLP, backend/frontend и тестирования.

> **Правило версии:** v0.2 считается замороженной базой. Изменения медицинской логики вносятся только новой версией после конкретного замечания врача/ментора или результата тестирования.

## 0. Что изменилось относительно v0.1

1. GAD-7 и PHQ-9 по умолчанию назначаются раз в **14 дней**; врач может изменить интервал.
2. Явно описана политика **out of scope / вне компетенции инструмента**.
3. Маршрутизация к психиатру сначала является рекомендацией врачу; после подтверждения врачом пациенту можно показать `обязательно` / `желательно` и следующий шаг.
4. Зафиксированы действия по лабораторным рискам: Hb и eGFR — высокий приоритет очереди (`urgent`) с рекомендацией связаться с клиникой в тот же день; CPK — только по референсу лаборатории, `info`.
5. GAD-7: значимое ухудшение считается **со знаком**; `delta >= +4` -> уведомление врачу `normal`, пациенту `inform_at_next_contact`; снижение отображается только в динамике.
6. Боль в животе не считается автоматически экстренной. Для неспецифичной жалобы задаётся уточняющий вопрос; система не выполняет дифференциальную диагностику.
7. Уточнён workflow врача: алерты создаются сразу в рабочей системе и попадают в приоритизированную очередь; личные устройства врача по умолчанию не используются.
8. Добавлена минимальная роль администратора: только контакт пациента и срок записи, без клинических данных.

---

## 1. Цель и границы системы

«Клинический компас» — цифровой контур сопровождения пациента с тревожной/депрессивной симптоматикой между визитами к врачу.

Система:

- собирает структурированные данные пациента;
- хранит динамику GAD-7 / PHQ-9, приёма препарата, симптомов и нежелательных явлений;
- превращает свободный текст в структурированные факты через AI/NLP;
- применяет детерминированный Rule Engine;
- формирует приоритизированную очередь для врача;
- показывает врачу происхождение факта и причину срабатывания правила;
- после решения врача может сформировать задачу на запись пациента.

Система **не**:

- ставит диагноз;
- самостоятельно оценивает эффективность лечения как клинический исход;
- назначает, отменяет или меняет терапию;
- автоматически принимает решение о маршрутизации;
- вызывает скорую помощь;
- генерирует свободные медицинские рекомендации пациенту;
- определяет срочность жалоб вне утверждённой области правил.

АВИАНДР® в основном сценарии считается **уже назначенным врачом**.

C-SSRS в v0.2 **не используется**: система не стратифицирует степень суицидального риска. Любое явное/возможное упоминание суицидальных мыслей или самоповреждения является safety signal.

---

## 2. Архитектура высокого уровня

```text
PATIENT UI / CHAT / FILES
        |
        +-- Structured forms -------------------+
        |                                        |
        +-- Free text --> AI/NLP Extraction -----+
                                                 v
                                          PATIENT STATE
                                                 |
                     +---------------------------+------------------------+
                     |                           |                        |
                     v                           v                        v
              Questionnaire                Rule Engine              Evidence/RAG*
                 scoring                   + Alerts                (later phase)
                     |                           |                        |
                     +---------------------------+------------------------+
                                                 v
                                         DOCTOR DASHBOARD
                                                 |
                                          Doctor decides
                                                 |
                                     +-----------+-----------+
                                     |                       |
                                     v                       v
                             Patient routing          Admin booking task
```

`*` RAG не участвует в safety-critical решениях. Его роль — кнопка «Почему?», поиск по закрытой базе источников и справочные ответы врачу.

### 2.1. Слои

1. **Structured data:** формы, опросники, приём препарата, лабораторные результаты.
2. **Patient State:** единое нормализованное состояние пациента.
3. **Rule Engine:** полностью воспроизводимые правила, не вызывающие LLM.
4. **AI/NLP:** только extraction/normalization свободного текста и документов.
5. **Doctor workflow:** очередь, подтверждение фактов, решение о действиях и маршрутизации.

---

## 3. Роли и доступ

| Роль | Доступ |
|---|---|
| Patient | Только собственные данные, опросники, журнал приёма, сообщения, подтверждение извлечённых фактов, утверждённые patient_action. |
| Doctor | Только закреплённые пациенты; Patient State, динамика, алерты, подтверждение клинических фактов, маршрутизация, срок следующего контакта. |
| Administrator | Только минимальные данные для записи: patient_id/контакт, requested_by_doctor, срок/приоритет записи. Без шкал, диагнозов, симптомов и медицинского текста. |
| System/AI | Вычисляет derived-поля, извлекает кандидаты-факты, применяет правила; клинических решений не принимает. |

Связь `DoctorPatientLink` обязательна: врач не видит пациентов, которые к нему не закреплены.

---

## 4. Общие инварианты данных

### 4.1. Core enums

```text
source = form | text_llm | text_lexicon | clinician | lab | derived
answer_status = answered | skipped | not_asked
confirmation = pending | patient_confirmed | doctor_verified | corrected | rejected
clinical_state = suspected | patient_confirmed | doctor_verified | rejected

doctor_priority = info | normal | high | urgent
patient_action = none | inform_at_next_contact | contact_doctor_soon |
                 contact_clinic_today | recommend_ambulance |
                 neutral_out_of_leaflet

polarity = present | absent | uncertain
experiencer = patient | other
temporality = current | recent_past | earlier | hypothetical
```

### 4.2. Правила качества данных

- `unknown != no`.
- Если факт не указан явно, AI не достраивает его.
- Для каждого AI-факта хранится `evidence_span`.
- Для каждого клинически значимого факта хранятся `source`, `confirmation`, `schema_version`, timestamps.
- Нормализованные типы берутся только из закрытых справочников.
- Несопоставимое значение -> `other_unlisted` + исходная фраза пациента.
- Confidence модели не является медицинской вероятностью и не определяет patient_action.

---

## 5. Core entities backend

| Entity | Ключевые поля |
|---|---|
| Patient | id, contacts, doctor_id, consents, profile metadata |
| DoctorPatientLink | doctor_id, patient_id, active_from, active_to |
| QuestionnaireSchedule | patient_id, instrument, interval_days, configured_by, next_due_at, active |
| QuestionnaireResponse | instrument, item_scores, total_score, severity_band, baseline, signed deltas, administered_at, completion_status |
| MedicationIntake | drug/regimen, slot_date, slot, status, missed_reason, marked_at, derived adherence |
| SymptomEvent | normalized_type, patient_phrase, modifiers, onset, impact, source, confirmation |
| RiskSignal | type, subtype/value, source, confirmation, timestamps |
| ClinicalProfile | diagnosis, prescription, previous therapy, contraindications, cautions, concomitant meds, psychiatric context |
| LabResult | analyte, value, unit, reference range, sample date, source, doctor verification |
| FreeTextExtraction | original text, entities, unknown_fields, clarification, model/schema version |
| Alert | rule results, aggregated doctor_priority, patient_action, lifecycle, audit |
| RoutingDecision | recommendation_to_doctor, doctor_decision, patient_visible_route, confirmed_at |
| ChatMessage | sender, recipient, text, extraction status, timestamps |
| AdminBookingTask | patient contact, requested deadline, status; no clinical payload |
| EvidenceSource | source type, title, section/version, identifier |

---

## 6. Опросники и расписание

### 6.1. GAD-7

- `total_score`: 0..21.
- `delta_from_previous = current_score - previous_score`.
- `delta_from_baseline = current_score - baseline_score`.
- Рост `delta_from_previous >= +4` считается значимым ухудшением для продуктового warning.
- Снижение на 4 и более отображается в динамике без симметричного warning.
- GAD-7 является patient-reported screening, а не диагнозом и не автоматической оценкой эффективности терапии.

**Rule:** GAD-7 `+4` -> `doctor_priority=normal`, `patient_action=inform_at_next_contact`.

### 6.2. PHQ-9

- `total_score`: 0..27.
- `PHQ-9 >= 10` -> «положительный скрининг на депрессию, требуется оценка врача».
- Вывод о выборе/смене терапии не формируется.
- `PHQ-9 item 9 > 0` -> safety signal `self_harm_or_suicidal`.

### 6.3. Расписание

По умолчанию:

```text
GAD-7: каждые 14 дней
PHQ-9: каждые 14 дней
```

Врач может изменить интервал отдельно для каждого инструмента.

`QuestionnaireSchedule`:

```text
patient_id
instrument = GAD7 | PHQ9
interval_days = integer
default_interval_days = 14
configured_by = system_default | doctor
next_due_at
active
```

Интервал не связывается автоматически с HARS. HARS остаётся врачебной шкалой и не является частью patient self-report flow.

---

## 7. Журнал приёма препарата

```text
status = taken | missed | unknown
slot = morning | evening
missed_reason = forgot | adverse_event | felt_unwell | ran_out |
                decided_to_stop | other | unknown
```

Derived:

- `consecutive_missed`;
- `adherence_7d`;
- `adherence_14d`;
- `day_completion_status = complete | partial | skipped`.

Свободный текст может предложить `status/slot/reason`, но обычные факты подтверждаются пациентом кнопкой.

---

## 8. Симптомы и нежелательные явления

### 8.1. SymptomEvent

```text
normalized_type
patient_phrase / evidence_span
polarity
experiencer
temporality
onset_date + precision
existed_before_medication
worsened_since_start
affects_daily_life
severity
status
interferes_with_driving
reported_via
confirmation
leaflet_category
```

### 8.2. Closed vocabulary v0.2

```text
somnolence
headache
dizziness
asthenia
paresthesia
insomnia
poor_sleep_quality
anxiety_increased
attention_disturbance
slowed_reaction
dysgeusia
nausea
upper_abdominal_pain
constipation
back_pain
muscle_rigidity
trismus
hyperhidrosis
other_unlisted
```

### 8.3. Боль в животе

Система **не делает дифференциальную диагностику** и не считает любую боль в животе экстренной.

1. Если пациент явно сообщает о боли в верхней части живота -> `upper_abdominal_pain` как возможное НЯ из инструкции и обычная логика НЯ.
2. Если написано только «болит живот» -> утверждённый уточняющий вопрос о локализации.
3. Если жалоба не сопоставляется со справочником -> `other_unlisted`.
4. Срочность не повышается только из-за того, что система теоретически не может исключить инфаркт/аппендицит.
5. Отдельный набор emergency red flags может быть добавлен новой версией только после врачебной валидации.

---

## 9. Out-of-scope policy

Если жалоба/факт находится вне утверждённой области инструмента:

```text
normalized_type = other_unlisted
patient_action = neutral_out_of_leaflet
doctor_priority = high   # выделяется для просмотра, но срочность медицински не классифицируется
```

Пациенту показывается только утверждённый нейтральный шаблон по смыслу:

> «Эта жалоба находится вне области оценки данного инструмента. Мы передали ваше сообщение врачу. Система не может определить причину или срочность этой жалобы.»

Дополнительный общий safety-net текст может быть утверждён медицинским экспертом отдельно.

Важно:

- out-of-scope не означает «безопасно»;
- out-of-scope не означает `urgent`;
- система не ставит предполагаемый диагноз;
- исходный текст всегда сохраняется и передаётся врачу.

---

## 10. Risk signals

```text
self_harm_or_suicidal
possible_overdose
possible_allergic_reaction
pregnancy_or_lactation
concomitant_drug_mention
alcohol_use_mention
intention_to_stop_treatment
other_concern
```

### 10.1. State machine AI-факта

```text
LLM/lexicon detects
      |
      v
   suspected
      |
      +--> safety signal: alert создаётся сразу
      |
      v
patient confirmation (если применимо)
      |
      v
patient_confirmed
      |
      v
doctor_verified | rejected
```

AI не ставит окончательный флаг противопоказания. Подтверждённый пациентом факт может сразу повысить приоритет/создать safety action, но клинический профиль и решение по терапии подтверждает врач.

---

## 11. Лабораторные данные

### 11.1. Структура

```text
analyte
value
unit
reference_low
reference_high
sample_date
entered_by = patient | doctor | imported
doctor_verified = true | false
egfr_source = lab | calculated | null
```

### 11.2. Зафиксированные правила v0.2

| Показатель | Условие | Doctor priority | Patient action | Примечание |
|---|---|---|---|---|
| Hemoglobin | <120 г/л (женщины), <130 г/л (мужчины) | urgent | contact_clinic_today | Порог хранится вместе с источником/версией. |
| eGFR | <60 мл/мин/1,73 м² | urgent | contact_clinic_today | Соответствует ограничению инструкции; врач подтверждает профильный риск. |
| CPK | выше reference_high конкретной лаборатории | info | none | Не использовать единый числовой порог. |

Для CPK референсные значения зависят от лаборатории, поэтому система хранит и использует `reference_low/reference_high` из конкретного результата.

---

## 12. Rule Engine

Rule Engine принимает **только структурированный Patient State**. Он не вызывает LLM и не пишет свободные рекомендации.

```json
{
  "rule_id": "R_GAD_WORSENING",
  "matched": true,
  "doctor_priority": "normal",
  "patient_action": "inform_at_next_contact",
  "clinical_state": "doctor_verified",
  "message_template_id": "gad_worsening_v1",
  "source_fact_ids": ["..."],
  "evidence_source_id": "...",
  "rule_version": "0.2.0"
}
```

### 12.1. Объединение правил

- `doctor_priority` определяет порядок/заметность в очереди врача, а не прерывание текущего приёма.
- `patient_action` рассчитывается отдельно.
- `urgent` у врача **не означает автоматически** `recommend_ambulance`.
- Все сработавшие правила сохраняются и аудитируются.
- UI показывает агрегированный верхний `doctor_priority`, но через «Почему?» доступны все rule_id и источники.
- Unknown/skipped никогда не понижает приоритет.
- Утверждённые patient texts берутся только из template registry.

### 12.2. Стабильные правила v0.2

| Rule | Условие | Doctor priority | Patient action |
|---|---|---|---|
| R_SELF_HARM | PHQ-9 item 9 > 0 или suicidal/self-harm signal | urgent | recommend_ambulance |
| R_OVERDOSE | possible_overdose | urgent | recommend_ambulance |
| R_ALLERGY | possible_allergic_reaction | urgent | recommend_ambulance |
| R_HB_LOW | Hb ниже порога | urgent | contact_clinic_today |
| R_EGFR_LOW | eGFR < 60 | urgent | contact_clinic_today |
| R_CPK_HIGH | CPK > lab reference_high | info | none |
| R_GAD_WORSENING | GAD-7 delta >= +4 | normal | inform_at_next_contact |
| R_PHQ_SCREEN_POSITIVE | PHQ-9 >= 10 впервые/актуально | high | contact_doctor_soon |
| R_AE_IMPACT | listed AE + affects_daily_life=yes | normal | contact_doctor_soon |
| R_AE_NO_IMPACT | listed AE + affects_daily_life=no | info | inform_at_next_contact |
| R_ANXIETY_INCREASED | anxiety_increased | normal | contact_doctor_soon |
| R_MISSED_AE | missed_reason=adverse_event | normal | contact_doctor_soon |
| R_INTEND_STOP | decided_to_stop/intention_to_stop_treatment | high | contact_doctor_soon |
| R_OUT_OF_SCOPE | other_unlisted/other_concern | high | neutral_out_of_leaflet |

Полный конфиг передаётся отдельно в `alert_rules_v0.2.yaml`.

---

## 13. Очередь врача и нагрузка

### 13.1. Workplace-only by default

- alert создаётся немедленно после Rule Engine;
- alert появляется в рабочем кабинете врача без ожидания следующего визита;
- очередь сортируется по `doctor_priority`, затем по времени;
- urgent закрепляется в верхней части очереди до просмотра/обработки;
- личные push/SMS/мессенджеры врача по умолчанию не используются;
- система не требует от врача реагировать вне рабочего времени;
- экстренная помощь пациенту не перекладывается на амбулаторного врача.

### 13.2. Alert lifecycle

```text
created -> delivered_to_workplace -> viewed -> acknowledged -> resolved
```

Сохраняются timestamps каждого этапа.

---

## 14. Маршрутизация к психиатру

Система может сформировать **рекомендацию врачу рассмотреть маршрутизацию**, но не принимает окончательного решения.

```text
system recommendation
      |
      v
doctor reviews
      |
      +--> none
      +--> preferred (желательно)
      +--> required  (обязательно)
              |
              v
      doctor confirmation
              |
              v
patient can see confirmed route + next step
```

До подтверждения врачом пациент маршрутизацию не видит.

После подтверждения пациенту можно показать:

- `желательно`;
- `обязательно`;
- утверждённый следующий шаг по записи/контакту.

---

## 15. Администратор и запись

Если врач решил, что пациенту нужен контакт/визит:

1. врач указывает срок/окно связи;
2. создаётся `AdminBookingTask`;
3. администратор видит только контакт пациента, срок и служебный статус;
4. клинические данные, причина алерта, диагноз, ответы шкал и сообщения пациенту администратору не раскрываются.

---

## 16. AI/NLP Extraction contract

AI нужен для структуризации свободного текста пациента/чата и позднее документов.

```json
{
  "message_id": "...",
  "patient_id": "...",
  "timestamp": "2026-10-20T10:00:00Z",
  "channel": "chat",
  "original_text": "Вчера вечером таблетку пропустил, потому что кружилась голова",
  "entities": [
    {
      "type": "symptom",
      "value": {"normalized_type": "dizziness"},
      "evidence_span": {"start": 43, "end": 59, "text": "кружилась голова"},
      "polarity": "present",
      "experiencer": "patient",
      "temporality": "recent_past",
      "source": "llm"
    },
    {
      "type": "medication",
      "value": {"status": "missed", "slot": "evening", "missed_reason": "adverse_event"},
      "evidence_span": {"start": 0, "end": 42, "text": "Вчера вечером таблетку пропустил, потому что"},
      "polarity": "present",
      "experiencer": "patient",
      "temporality": "recent_past",
      "source": "llm"
    }
  ],
  "unknown_fields": ["dizziness.affects_daily_life"],
  "clarifying_questions": ["Мешает ли головокружение обычным делам?"],
  "schema_validation": "valid",
  "confirmation": "pending",
  "model_version": "...",
  "schema_version": "0.2.0"
}
```

### 16.1. Extraction rules

- AI извлекает только то, что имеет evidence в исходном тексте.
- `polarity`, `experiencer`, `temporality` обязательны для текстовых сущностей.
- `evidence_span` обязателен.
- Если информации нет -> `unknown`, а не догадка.
- Для обычного факта пациенту предлагается подтверждение «Мы поняли так... Верно?».
- Safety signals создают alert сразу, но источник остаётся `suspected/text_llm` до подтверждения.
- При отказе LLM исходное сообщение сохраняется; red-flag lexicon продолжает работать.

---

## 17. Dataset / annotation contract

Датасет нужен **сначала для оценки качества extraction**, а не обязательно для fine-tuning.

### 17.1. Что размечаем

- `entity_type`;
- `normalized_type/value`;
- `evidence_span`;
- `polarity`;
- `experiencer`;
- `temporality`;
- medication `status/slot/missed_reason`;
- risk signals;
- явные temporal/impact fields;
- `other_unlisted`;
- `unknown` там, где поле невозможно заполнить по тексту.

### 17.2. Hard cases

Обязательные сценарии набора:

- отрицание;
- неуверенность;
- гипотетическая жалоба;
- симптом другого человека;
- неточное время;
- несколько симптомов в одном сообщении;
- шутки/идиомы с red-flag словами;
- конфликт формы и текста;
- лабораторные значения в тексте;
- out-of-scope жалобы;
- опечатки, разговорный русский, жаргон;
- пустые/бессодержательные сообщения.

### 17.3. Рекомендуемый старт

1. 100–150 seed-сообщений для проверки schema/annotation guideline.
2. После стабилизации — 300–500 development/synthetic сообщений.
3. Отдельный clinician-reviewed hold-out порядка 100 сообщений, не используемый при prompt/model tuning.
4. Реальные пациентские данные — только в пилоте при наличии законного основания, защиты данных и согласованного процесса.

---

## 18. Метрики AI/NLP

| Метрика | Назначение |
|---|---|
| Entity Precision / Recall / F1 | normalized_type и типы сущностей |
| Modifier F1 | polarity / experiencer / temporality |
| Risk-signal Recall | главная safety-метрика; отдельно по red flag |
| Hallucination rate | поле заполнено без evidence в тексте |
| Evidence-span quality | overlap/exact match с gold span |
| Valid JSON/schema pass rate | доля extraction без repair |
| Unknown correctness | модель не додумывает отсутствующие поля |
| Latency P50/P95 | скорость ответа AI-layer |
| Rule consistency | одинаковый Patient State -> одинаковый RuleResult |

---

## 19. Минимальные API-контракты

```text
POST /patients/{id}/questionnaires
POST /patients/{id}/questionnaire-schedules
POST /patients/{id}/intakes
POST /patients/{id}/symptoms
POST /patients/{id}/messages
POST /patients/{id}/labs

POST /internal/extract
POST /internal/evaluate-rules

GET  /doctor/patients
GET  /doctor/queue
GET  /doctor/patients/{id}/timeline
POST /doctor/patients/{id}/routing
POST /doctor/patients/{id}/contact-deadline

GET  /admin/booking-tasks
PATCH /admin/booking-tasks/{id}
```

AI endpoints могут быть заглушкой в первом E2E. Контракт данных должен быть готов до подключения модели.

---

## 20. UI / user flows

### 20.1. Patient flow

```text
Login
 -> Dashboard
 -> Due questionnaire (GAD-7 / PHQ-9)
 -> Medication intake
 -> Symptom / free text / chat
 -> AI confirmation (если есть extraction)
 -> Approved patient_action
 -> Own history / next due date
```

### 20.2. Doctor flow

```text
Login
 -> Priority queue
 -> Patient card
 -> Scores + dynamics + adherence + symptoms + source
 -> Why? (rule_id + source)
 -> Confirm/correct facts
 -> Decide routing/contact
 -> Set deadline if appointment needed
```

### 20.3. Platform strategy

- patient UI: mobile-first responsive web;
- doctor UI: desktop-first responsive web;
- отдельное нативное мобильное приложение врача не является приоритетом v0.2.

---

## 21. Нефункциональные требования

- RBAC и минимально необходимые права доступа.
- Audit trail для изменения клинически значимых полей.
- `schema_version`, `rule_version`, `model_version`, `evidence_source_version`.
- Исходный текст/ответ сохраняется **до** AI-processing.
- Сбой AI не должен терять сообщение.
- Red-flag lexicon/fallback не зависит от LLM availability.
- Alert delivery в рабочую систему аудитируется.
- Responsive web для cross-platform.
- Правила/шкалы/справочники конфигурационные и не требуют переписывания ядра.
- Patient-facing medical text хранится в versioned template registry.

---

## 22. Приоритет реализации

### P0 — E2E application

- doctor/patient RBAC и linkage;
- persistence;
- GAD-7 / PHQ-9 + schedules;
- medication intake;
- symptom/adverse-event form;
- doctor timeline/dashboard;
- alert queue;
- out-of-scope flow;
- routing confirmation;
- audit/source fields;
- admin booking task (минимально).

### P1 — AI extraction

- patient chat;
- JSON Schema;
- LLM + lexicon extraction;
- confirmation flow;
- annotation/evaluation set;
- quality metrics;
- clarifying questions.

### P1 — Rule Engine hardening

- versioned YAML config;
- deterministic tests;
- patient template registry;
- «Почему?»;
- clinician scenario review.

### P2 — Documents / RAG

- extraction from uploaded documents;
- closed evidence base;
- RAG only for evidence/reference support.

### P2 — Predictive ML

Только при наличии подходящего longitudinal dataset и заранее определённого target. Не является обязательным компонентом v0.2.

---

## 23. Definition of Done v0.2

### Кирилл / application

Готово, если:

1. пациент проходит GAD-7/PHQ-9, отмечает приём и отправляет сообщение;
2. данные сохраняются и принадлежат правильному patient_id/doctor_id;
3. врач видит их в карточке и timeline;
4. alerts появляются в очереди и сортируются по приоритету;
5. questionnaire schedule по умолчанию 14 дней и редактируется врачом;
6. out-of-scope complaint не получает выдуманный диагноз/срочность;
7. routing становится видимой пациенту только после doctor confirmation;
8. admin получает booking task без клинических данных;
9. API готов принять future AI extraction по schema v0.2.

### Рома / data & evaluation

Готово, если:

1. составлен dataset audit по **конкретным задачам** (clinical NLP vs longitudinal predictive ML);
2. каждый источник описан по input/labels/size/language/license/clinical relevance/limitations;
3. создан seed annotation set по guideline v0.2;
4. в наборе присутствуют hard cases;
5. есть отдельный hold-out plan для медицинской проверки;
6. данные/labels маппятся непосредственно на поля `patient_state_v0.2.schema.json`.

### AI/Data lead

Готово, если:

1. JSON Schema валидируется;
2. `alert_rules_v0.2.yaml` проходит parser/tests;
3. есть baseline extraction (prompted LLM или mock) с schema validation;
4. определены evaluation metrics и отчётный формат;
5. Rule Engine детерминированно воспроизводит ожидаемые сценарии.

---

## 24. Тестирование перед следующей заморозкой

Перед v0.3 прогнать не менее 10–20 end-to-end сценариев, включая:

- обычное улучшение;
- GAD-7 +4;
- PHQ-9 >=10;
- PHQ-9 item 9 >0;
- обычное НЯ без влияния на жизнь;
- НЯ, мешающее повседневной жизни;
- пропуск препарата;
- намерение прекратить терапию;
- Hb ниже порога;
- eGFR <60;
- CPK выше лабораторной нормы;
- неясную боль в животе;
- out-of-scope complaint;
- симптом другого человека;
- отрицание симптома;
- конфликт формы и текста;
- AI failure / invalid JSON;
- routing recommended -> doctor confirmed -> patient visible;
- booking task -> admin without clinical data.

Для каждого сценария фиксировать expected Patient State, RuleResult, doctor UI и patient UI.

---

## 25. Артефакты версии v0.2

Эта спецификация должна использоваться вместе с:

- `patient_state_v0.2.schema.json` — machine-readable data contract;
- `alert_rules_v0.2.yaml` — versioned Rule Engine config;
- `annotation_guideline_v0.2.md` — инструкция для разметки/evaluation;
- `Implementation_Handoff_v0.2.md` — задачи Роме и Кириллу.

---

## 26. Источники

1. Требования кейса «Цифровой ассистент врача для ведения пациента с тревожной и депрессивной симптоматикой».
2. Клинические рекомендации «Генерализованное тревожное расстройство» (версия, предоставленная команде).
3. Листок-вкладыш АВИАНДР®, 20 мг, действующее вещество маритупирдин.
4. «Разметка параметров и правила алертов v2» и последующие согласованные правки медицинского эксперта команды.
5. Источники по GAD-7/PHQ-9/лабораторным порогам, перечисленные в медицинской спецификации; точная версия каждого источника должна храниться рядом с rule config.
