# Итоговое сравнение GigaChat extractor_prompt_v1.1 и v1.2

Источник: сохранённые `out_gigachat_v1_1/metrics_message_level.json`, `out_gigachat_v1_2/metrics.json` и соответствующие `predictions.jsonl`; 155 одинаковых сообщений, 172 gold entities. Сопоставление сущностей — внутри каждого сообщения. Это сравнение двух сохранённых прогонов, не клиническая валидация.

| Метрика | v1.1 | v1.2 |
|---|---:|---:|
| Overall precision | 0.602 | 0.631 |
| Overall recall | 0.721 | 0.797 |
| Overall F1 | **0.656** | **0.704** |
| Risk recall | **0.368** (7/19) | **0.842** (16/19) |
| Symptom F1 | 0.664 | 0.703 |
| Medication F1 | 0.718 | 0.635 |
| Risk signal F1 | 0.483 | 0.842 |
| Lab mention F1 | 0.333 | 0.800 |
| Schema pass | 100% | 100% |
| Failed messages | 0 | 0 |
| Evidence span exact match | 0.685 | 0.635 |
| Latency P50 | 2249.51 ms | 1843.82 ms |
| Latency P95 | 4501.87 ms | 3199.66 ms |

Risk recall вырос **0.368 → 0.842**, overall F1 — **0.656 → 0.704**. В обоих прогонах **failed messages = 0** и **schema pass = 100%**. Снижение exact evidence match (0.685 → 0.635) относится к границам span, а не к schema pass или semantic TP.

## Medication regression

Message-level medication: TP **28 → 27**, FP **19 → 27**, FN **3 → 4**. В v1.2 появилось девять новых FP и исчез один FP (`gen_096`); новый FN — `gen_154`. Полное разбиение **27 FP v1.2** ниже; категории взаимоисключающие. Это разбор сохранённых предсказаний, без изменения gold.

| Категория | FP v1.2 | Сообщения и причина |
|---|---:|---|
| True extra entity | 11 | `gen_010`, `047`, `056`, `098`, `099`, `100` (план бросить), `103`, `122`, `125`, `147`, `152`: контекст таблетки/дозы, план отмены или исправленное «выпил» представлены самостоятельным medication event без соответствующего gold-события. `gen_047` также относится к другому человеку. |
| Attribute mismatch | 4 | `gen_084`, `088`, `139`, `154`: тот же факт, но иной `missed_reason`; каждая пара даёт один FP и один FN. В `gen_154` v1.2 опустила `unknown`, а gold содержит `unknown`: strict key различает отсутствие поля и значение `unknown`. |
| Duplicate | 8 | `gen_077`, `080`, `082`, `085`, `086`, `087`, `136`, `138`: причина пропуска, решение прекратить, «вспомнил», «ничего не пропустил» или повтор той же фразы превратились во второе событие. |
| Annotation disagreement | 4 | `gen_095` (фактическая двойная доза), `gen_100` (текущий приём), `gen_144` (два одновременно принимаемых препарата): явные medication mentions, тогда как gold содержит только risk. Их статус требует annotation adjudication. |
| Optional field issue | 0 semantic FP/FN | Удаление фиктивного `drug="unknown"` и названий вроде «таблетка» заметно в predictions, но `drug`/`dose_mg` не входят в primary matching key и **не объясняют** рост FP/FN. |

Четыре FN v1.2: `gen_084` gold `felt_unwell` vs prediction `unknown`; `gen_088` gold `adverse_event` vs `unknown`; `gen_139` gold `decided_to_stop` vs `unknown` (сам gold reason спорен: решение прекратить не сказано явно); `gen_154` gold `unknown` vs поле `missed_reason` отсутствует. Первые три FN уже были в v1.1. Новый `gen_154` — расхождение optional/enum representation, не пропущенное сообщение о препарате.

## Оставшиеся risk FN v1.2 — все 3

| Сообщение | Gold risk | Prediction | Интерпретация |
|---|---|---|---|
| `gen_094`: «Я боюсь, что могу принять слишком много таблеток.» | `possible_overdose` | нет entities | Возможная передозировка сформулирована как страх будущего действия; risk отсутствует. |
| `gen_115`: «Я переживаю из-за конфликта на работе.» | `other_concern` | `symptom/anxiety_increased` | Переживание интерпретировано как симптом. Граница gold `other_concern` для обычного рабочего конфликта требует annotation review. |
| `gen_144`: «Принимаю антидепрессант вместе с ибупрофеном от боли в спине.» | `concomitant_drug_mention` | две medication entities + `back_pain` | Оба препарата найдены, но relation «вместе» не преобразовано в отдельный risk signal. |

Все три gold случая `possible_allergic_reaction`, пропущенные в v1.1, в v1.2 извлечены (3/3). Prompt v1.3 в рамках этого отчёта не создаётся.

**Recommendation: freeze extractor_prompt_v1.2 for MVP.** Сохранить перечисленные medication и risk случаи для следующей ручной annotation/medical проверки и отдельного этапа улучшений.

## Тезисы для слайдов

- Сравнение на тех же 155 сообщениях и 172 gold entities; message-level matching.
- Risk recall: **0.368 → 0.842**; найдено 16 из 19 risk signals вместо 7.
- `possible_allergic_reaction`: **0/3 → 3/3** найденных gold случаев.
- Overall F1: **0.656 → 0.704**; schema pass 100%, failed messages 0 в обоих прогонах.
- Medication F1 снизился **0.718 → 0.635**: FP 19 → 27, FN 3 → 4; основная часть FP — лишние события и дубли, а не optional `drug`.
- Остались три risk FN: потенциальная передозировка, `other_concern` с неоднозначной gold-границей и одновременный приём двух препаратов.
- **Freeze extractor_prompt_v1.2 for MVP**; дальнейшие изменения после ручной проверки спорных случаев.
