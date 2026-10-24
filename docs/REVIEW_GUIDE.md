# Гид для проверяющих

Как быстро найти в репозитории то, что оценивается. Для каждого пункта: что посмотреть на стенде,
где это в коде и какие тесты это доказывают.

**Стенд:** https://compass.lamagate.com · окно в МИС: https://compass.lamagate.com/mis-demo.html
(все люди вымышлены, вход по выбору аккаунта без пароля).

**Проверить всё одной командой** (то же, что CI на каждый push и PR):

```bash
make check
```

## 1. Сквозная цепочка P0: пациент → backend → правила → очередь врача

| Что | Где |
|---|---|
| На стенде | Войти «Корнилова Е. А.» → заполнить GAD-7 с ростом ≥ 4 → войти «Миронова А. С.» → событие в очереди, «Почему?» показывает правило и факты |
| Patient State v0.2 | `backend/src/clinical_compass/domain/state.py`, схема `contracts/patient_state_v0.2.schema.json` |
| Правила из YAML, без хардкода | `contracts/alert_rules_v0.2.yaml` → `backend/src/clinical_compass/domain/rules.py` |
| Сценарии пациента и врача | `backend/src/clinical_compass/services/patients.py`, `services/doctors.py` |
| Тесты | `backend/tests/test_domain.py` (все 16 правил), `test_api.py` (25 сквозных HTTP-сценариев), `test/widget/app_flow_test.dart` (UI поверх настоящего backend) |

Инварианты контракта и где они проверяются:

- `doctor_priority` и `patient_action` — разные поля: `domain/rules.py`, `test_domain.py`.
- `urgent` — это рабочая очередь, а не push: закрепление в `services/doctors.py::queue`, тест `test_queue_pins_urgent_first_then_orders_by_priority`.
- Out-of-scope без выдуманной срочности: `R_OUT_OF_SCOPE`, тест `test_out_of_scope_complaint_is_high_neutral_and_not_classified`.
- Маршрутизация видна пациенту только после решения врача: тест `test_routing_is_hidden_from_patient_until_doctor_confirms`.

## 2. Кроссплатформенность и интеграция с ЕМИАС / 1С

| Что | Где |
|---|---|
| На стенде | `mis-demo.html` → система «ЕМИАС» или «1С:Медицина» → пациент → «Открыть «Клинический компас»» |
| Один Flutter-код: iOS / Android / web | `lib/`, точка входа `lib/main.dart`; адрес backend — `--dart-define=CC_API_BASE_URL` |
| Окно в МИС по одноразовому коду (SMART on FHIR launch) | `backend/src/clinical_compass/services/integrations.py`, роутер `api/routers/integrations.py`, экран `lib/presentation/embed/` |
| Сводка в МИС — HL7 FHIR R4 | `backend/src/clinical_compass/services/fhir.py` |
| Описание и пример для 1С | [INTEGRATIONS.md](INTEGRATIONS.md) |
| Тесты | `backend/tests/test_integrations.py`, виджет-тест `MIS launch code opens the patient card in the embedded window` |

## 3. Срочные случаи: экран «Позвонить 112»

| Что | Где |
|---|---|
| На стенде | Пациент → «Написать врачу» → «Последние дни не хочу жить» → сверху выезжает экран с кнопкой 112; у врача событие закреплено и видно, что нажал пациент |
| Экран и запуск звонка | `lib/presentation/patient/emergency_alert.dart` |
| Журнал действий пациента | `backend/src/clinical_compass/services/safety.py` |
| Разбор альтернатив (автовызов, обратный звонок, доверенное лицо) | [EMERGENCY.md](EMERGENCY.md) |
| Тесты | `test_integrations.py::test_emergency_notice_and_patient_actions_reach_the_doctor`, виджет-тест `red-flag message slides in the emergency screen` |

## 4. AI-извлечение из свободного текста

| Что | Где |
|---|---|
| Граница: LLM только структурирует текст, решения — у детерминированных правил | `backend/src/clinical_compass/domain/extraction.py` (протокол `Extractor`) |
| Отдельный сервис (GigaChat через OpenAI-совместимый API) | `ai_service/` |
| HTTP-адаптер backend → сервис | `backend/src/clinical_compass/domain/remote_extraction.py` |
| Сбой AI не теряет сообщение и не скрывает красные флаги | `services/patients.py::_extract_facts` (страховка встроенным словарём) |
| Оценка качества: 155 сообщений, risk recall 0.842 | `evaluation/final_model_report.md` |
| Тесты | `ai_service/tests/` (39), `backend/tests/test_extraction_resilience.py`, `test_remote_extraction.py`, `test_medication_extraction.py` |

## 5. Поддерживаемость и качество кода

- **Слои с зависимостями сверху вниз:** `api → services → repositories → db`; `domain` — чистая логика без БД и HTTP. Подробно — [backend/README.md](../backend/README.md).
- **Контракты как данные:** правила, шаблоны текстов, шкалы и справочники лежат в `contracts/` и проверяются при старте (`clinical-compass check-contracts`); приложение получает их через `GET /meta`, тексты не дублируются в коде.
- **Статическая проверка:** ruff (строгий набор правил) и `mypy --strict` для backend и AI-сервиса, `flutter analyze` — в CI на каждый PR.
- **Тесты:** backend 96, AI-сервис 39, Flutter 19 — UI-тесты работают поверх настоящего Python-backend, а не моков.
- **Миграции БД:** Alembic, `backend/src/clinical_compass/db/alembic/versions/`.
- **Решения и открытые вопросы:** [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md).

## 6. Развёртывание и безопасность

| Что | Где |
|---|---|
| Одна команда: PostgreSQL + API + веб | `docker compose up --build` ([README](../README.md#быстрый-старт)) |
| Образ без root, порт только на `127.0.0.1` | `Dockerfile`, `docker-compose.yml` |
| Как обновлять стенд | [DEPLOY.md](DEPLOY.md) |
| Секреты только из окружения; dev-ключи запрещены вне демо-режима | `backend/src/clinical_compass/config.py`, тест `test_settings_refuse_dev_internal_token_outside_demo` |
| Доступ проверяется в сервисах, а не в роутерах | `backend/src/clinical_compass/services/access.py`, тесты RBAC в `test_api.py` |
| Встраивание окна только в разрешённые МИС | заголовок `frame-ancestors` в `main.py`, тест `test_embedding_is_restricted_by_frame_ancestors` |
