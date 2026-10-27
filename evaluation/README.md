# Оценка извлечения фактов из текста

Здесь проверяется только слой, который превращает свободный текст пациента в факты. Клинические правила
детерминированные и проверяются отдельно, тестами backend.

| Что | Где |
|---|---|
| Размеченный набор: 155 сообщений, 172 факта | `data/generated_annotations.v1.1.jsonl`, схема разметки — `data/annotation_v0.2.schema.json` |
| Итоговое сравнение промптов v1.1 и v1.2 | [final_model_report.md](final_model_report.md) |
| Разбор ошибок и спорной разметки | [reports/error_analysis_v1_1.md](reports/error_analysis_v1_1.md), [reports/adjudication_v1_1.md](reports/adjudication_v1_1.md) |
| Сохранённые метрики прогонов GigaChat | `results/gigachat_v1_1.json`, `results/gigachat_v1_2.json` |
| Графики для презентации | `../docs/presentation/`, строятся `../scripts/plot_metrics.py` |

## Как запустить

Оценка идёт тем же экстрактором, что и в приложении:

```bash
cd backend
PYTHONPATH=src uv run clinical-compass evaluate-extractor ../evaluation/data/generated_annotations.v1.1.jsonl --out-dir ../evaluation/out
```

Результат — `evaluation/out/metrics.json` и `evaluation/out/predictions.jsonl` (папка в git не попадает).

По умолчанию (`CC_EXTRACTOR_MODE=mock`) оценивается встроенный словарь. Чтобы оценить модель, задайте
`CC_EXTRACTOR_MODE=remote` и `CC_EXTRACTOR_URL` с адресом запущенного `ai_service` (см. `../ai_service/README.md`).
