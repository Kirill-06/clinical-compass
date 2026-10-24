# Сервис AI-извлечения «Клинического компаса»

Сервис преобразует свободный текст пациента в `FreeTextExtraction` v0.2 для backend. Он не принимает
клинических решений, не задаёт приоритет врачу и действие пациенту, не составляет рекомендаций. Провайдер
подключается через совместимый с OpenAI Chat Completions API; извлечение и проверка результата отделены
от HTTP-транспорта.

## Запуск

Из корня репозитория:

```bash
cd ai_service
export AI_MODEL='GigaChat-3-Ultra'
export AI_API_KEY='<действующий access token>'
export AI_BASE_URL='<адрес OpenAI-compatible API GigaChat с суффиксом /v1>'
UV_CACHE_DIR=/tmp/uv-cache uv run uvicorn clinical_compass_ai.main:app --host 127.0.0.1 --port 8090
```

Access token получите по действующей процедуре GigaChat для своего аккаунта. `AI_API_KEY` принимает именно
access token, а не Authorization Key: сервис передаёт его как Bearer token. Не сохраняйте оба ключа в файлах
проекта и не добавляйте в git. Если для HTTPS нужен собственный CA bundle, задайте `SSL_CERT_FILE` с путём
к читаемому файлу. `AI_MODEL` и `AI_API_KEY` нужны для `/extract`; `GET /health` работает и без них.
`AI_TIMEOUT_SECONDS` по умолчанию равен 15 секундам. Если задан `AI_SERVICE_TOKEN` (не короче 16 символов),
`/extract` принимает только запросы с `Authorization: Bearer <токен>`; backend передаёт тот же токен из
`CC_EXTRACTOR_TOKEN`. `/health` токена не требует. Скрипт `scripts/run-local-demo.sh` генерирует общий токен сам.

Проверка:

```bash
curl http://127.0.0.1:8090/health
```

Пример запроса к `/extract`:

```bash
curl -X POST http://127.0.0.1:8090/extract -H 'Content-Type: application/json' -d '{"message_id":"m1","patient_id":"p1","timestamp":"2026-10-22T12:00:00Z","text":"Болит голова","schema_version":"0.2.0"}'
```

Ответ — полный `FreeTextExtraction`. Для сущностей нужны точные позиции фрагментов в исходном тексте.
Неоднозначные или отсутствующие подтверждения приводят к ошибке. При некорректном ответе модели сервис
делает одну попытку исправления, затем возвращает HTTP 502. Ошибки провайдера тоже дают HTTP 502,
отсутствие настроек — HTTP 503. Словарь сущностей соответствует разметке v0.2.

Для подключения backend задайте `CC_EXTRACTOR_MODE=remote` и
`CC_EXTRACTOR_URL=http://127.0.0.1:8090/extract`. Локальный запуск обоих процессов описан в
[основном README](../README.md#локальный-стенд-с-gigachat). Backend сохраняет сообщение до извлечения,
проверяет структуру ответа и переносит факты в Patient State. Правила срабатывают отдельно от LLM.
При ошибке внешнего extractor локальный лексикон проверяет только критические red-flag фразы.
Полученные из текста факты могут оставаться в статусе `pending`; этот контур не является клинически
валидированной системой.

## Тесты

```bash
cd ai_service
UV_CACHE_DIR=/tmp/uv-cache uv run pytest
cd ../backend
PYTHONPATH=src uv run pytest
```

## Оценка с моделью

При работающем сервисе на порту 8090:

```bash
cd backend
export CC_EXTRACTOR_MODE=remote
export CC_EXTRACTOR_URL=http://127.0.0.1:8090/extract
PYTHONPATH=src uv run clinical-compass evaluate-extractor ../evaluation/data/generated_annotations.v1.1.jsonl --out-dir ../evaluation/out
```

Существующий оценщик записывает `evaluation/out/predictions.jsonl` и `evaluation/out/metrics.json`.
Это оценка извлечения на наборе сообщений, не клиническая валидация. Для запуска нужны доступный
провайдер и поддержка JSON response format в совместимом API.

## Особенность контракта

Схема разметки не содержит `polarity`, `experiencer` и `temporality` для лекарств, сигналов риска и
анализов, хотя `ExtractedEntity` требует эти поля. Адаптер заполняет их значениями `present`, `patient`
и `current` после извлечения. Это поля транспортного контракта, а не эталонные метки. Patient State
принимает `slot=unknown` для лекарства без догадки об утреннем или вечернем приёме.
