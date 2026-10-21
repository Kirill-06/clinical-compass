# Backend «Клинического компаса»

FastAPI-сервис: хранит данные пациента, строит Patient State v0.2, применяет правила из
`contracts/alert_rules_v0.2.yaml` и ведёт рабочую очередь врача.

## Запуск

```bash
uv sync
```

```bash
PYTHONPATH=src uv run clinical-compass serve
```

http://localhost:8080/docs — интерактивная документация API. Команды CLI:

| Команда | Что делает |
|---|---|
| `clinical-compass serve [--host --port]` | API; при старте применяет миграции и (если включено) демо-данные |
| `clinical-compass migrate` | миграции Alembic до последней версии |
| `clinical-compass seed` | вымышленные демо-данные в пустую базу (повторный запуск ничего не меняет) |
| `clinical-compass check-contracts` | проверить согласованность `contracts/` (правила, шаблоны, шкалы) |

`PYTHONPATH=src` нужен только на macOS, где editable-установка иногда не подхватывается; в Docker и CI —
не нужен. Настройки — переменные `CC_*` (см. `src/clinical_compass/config.py` и `../.env.example`).

## Устройство

```
src/clinical_compass/
  domain/         чистая логика, без БД и HTTP
    enums.py        перечисления схемы v0.2 (wire-значения)
    state.py        сущности Patient State; to_schema() — ровно по JSON Schema
    instruments.py  GAD-7 / PHQ-9 из contracts/instruments_v0.2.yaml, подсчёт баллов
    derived.py      расписание опросников, дельты, приверженность
    rules.py        rule engine по YAML (детерминированный, без LLM)
    extraction.py   контракт FreeTextExtraction + протокол Extractor + заглушка-лексикон
    contracts.py    загрузка и проверка contracts/
  db/             модели SQLAlchemy, сессии, миграции Alembic (db/alembic/versions)
  repositories/   запросы к БД, преобразование строк ↔ доменные объекты
  services/       сценарии: доступ (access.py), Patient State и правила (state.py),
                  пациент, врач, администратор, внутренний AI-слой, вход; presenter.py — формат ответов;
                  integrations.py + fhir.py — окно в ЕМИАС / 1С и FHIR-сводка; safety.py — экстренный экран
  api/            роутеры FastAPI, схемы запросов, обработчики ошибок, зависимости (сессия, пользователь)
  main.py         фабрика приложения create_app()
  seed.py         демо-данные — создаются теми же сервисами «в прошлом»
  cli.py          командная строка
```

Правила зависимостей: `api → services → repositories → db`, и все слои могут использовать `domain`.
`domain` ничего не импортирует из остальных слоёв, поэтому его можно тестировать без БД (`tests/test_domain.py`).

Проверка доступа — в сервисах (`services/access.py`), а не в роутерах: любой новый вход (HTTP, очередь задач,
CLI) получает те же ограничения. Роутеры только разбирают запрос и вызывают сервис.

Транзакция = запрос: `api/deps.py:get_deps` коммитит после успешного ответа и откатывает при ошибке.

## Как сделать типовые изменения

**Новое правило алерта.** Добавить его в `contracts/alert_rules_v0.2.yaml` (операторы и поля — в
`domain/rules.py:OPERATORS` и кадрах `RuleEngine`), подпись — в `contracts/vocabulary_v0.2.yaml: rule_titles`,
текст пациенту (если `patient_action` не `none`) — в шаблоны. Тест — в `tests/test_domain.py`.
`clinical-compass check-contracts` проверит согласованность.

**Новый эндпоинт.** Схема запроса — `api/schemas.py`, сценарий с проверкой доступа — в сервисе, маршрут — в
соответствующем `api/routers/*.py`. Сквозной тест — `tests/test_api.py`.

**Изменение таблиц.** Поменять `db/models.py`, затем:

```bash
PYTHONPATH=src uv run alembic revision --autogenerate -m "описание"
```

Проверить сгенерированный файл в `db/alembic/versions/` (типы колонок времени — `sa.DateTime(timezone=True)`).

**Настоящий ИИ.** Реализовать протокол `Extractor` и передать экземпляр в `Runtime.build(settings, extractor=…)`
(`api/runtime.py`), либо присылать факты в `POST /internal/patients/{id}/facts`.

## Проверки

```bash
uv run ruff check src tests && uv run ruff format --check src tests
```

```bash
uv run mypy src tests
```

```bash
uv run pytest
```

API-тесты используют SQLite: демо-база создаётся один раз, каждый тест работает со своей копией.
Совместимость с PostgreSQL проверяется в CI (миграции + демо-данные на настоящем PostgreSQL).
