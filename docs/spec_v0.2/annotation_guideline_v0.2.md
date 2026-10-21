# Клинический компас — Annotation Guideline v0.2

**Для:** аналитики данных / NLP evaluation  
**Основание:** Technical Spec v0.2  
**Цель:** единообразно размечать сообщения пациента так, чтобы gold-разметка напрямую превращалась в `Patient State`.

## 1. Главный принцип

Мы размечаем **факты, явно содержащиеся в тексте**, а не медицинские выводы.

Нельзя:

- ставить диагноз;
- додумывать дату/выраженность/влияние на жизнь;
- считать отсутствие упоминания отрицанием;
- по слову «болит» автоматически назначать срочность;
- размечать симптомы другого человека как симптомы пациента.

Если информации недостаточно — поле остаётся `unknown`.

## 2. Единица разметки

Основная единица — одно сообщение пациента + служебный контекст, если он известен:

```json
{
  "message_id": "...",
  "patient_id": "...",
  "timestamp": "...",
  "channel": "chat",
  "text": "..."
}
```

## 3. Entity labels

### symptom

Поля:

```text
normalized_type
span_start / span_end / span_text
polarity
experiencer
temporality
onset_date (если явно)
affects_daily_life (если явно)
severity (если явно и словарь допускает)
```

Closed vocabulary:

`somnolence, headache, dizziness, asthenia, paresthesia, insomnia, poor_sleep_quality, anxiety_increased, attention_disturbance, slowed_reaction, dysgeusia, nausea, upper_abdominal_pain, constipation, back_pain, muscle_rigidity, trismus, hyperhidrosis, other_unlisted`

### medication

```text
status = taken | missed | unknown
slot = morning | evening | unknown
missed_reason = forgot | adverse_event | felt_unwell | ran_out | decided_to_stop | other | unknown
```

### risk_signal

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

### lab_mention

Размечаем факт упоминания показателя/значения/единицы. Не интерпретируем результат в тексте.

## 4. Semantic modifiers

### polarity

- `present`: «кружится голова»
- `absent`: «голова не кружится»
- `uncertain`: «кажется, немного кружится»

### experiencer

- `patient`: «у меня кружится голова»
- `other`: «у мамы кружится голова»

### temporality

- `current`: происходит сейчас/актуально;
- `recent_past`: было недавно и относится к текущему периоду;
- `earlier`: историческое/давнее;
- `hypothetical`: «боюсь, что начнёт тошнить».

## 5. Evidence span

Каждая текстовая сущность должна иметь точный фрагмент исходного сообщения.

Плохо:

```json
{"normalized_type":"dizziness"}
```

Хорошо:

```json
{
  "normalized_type":"dizziness",
  "evidence_span":{"text":"кружилась голова","start":42,"end":58}
}
```

## 6. Out of scope

Если жалоба не относится к закрытому справочнику:

```text
normalized_type = other_unlisted
```

Не назначаем диагноз и не размечаем медицинскую срочность.

Пример:

> «У меня внезапно онемела половина лица»

Gold: `other_unlisted` + исходный span. Отдельный emergency label возможен только после добавления утверждённого rule set в новую версию.

## 7. Боль в животе

> «Болит верх живота» -> `upper_abdominal_pain`.

> «Болит живот» -> недостаточно для нормализации; `other_unlisted` или clarification-needed в зависимости от annotation format.

Не размечать автоматически как инфаркт/аппендицит/urgent.

## 8. Suicide/self-harm

Любое реальное упоминание пациента о мыслях/самоповреждении -> `self_harm_or_suicidal`.

Важно различать:

- «хочу умереть» -> positive;
- «никогда не хотел умереть» -> polarity absent;
- «у друга мысли о суициде» -> experiencer other;
- «убиться можно от этой очереди» -> идиома/hard negative, не маркировать автоматически как positive без контекста.

C-SSRS labels не создаются.

## 9. Unknown vs no

> «Кружится голова»

`affects_daily_life = unknown`, а не `no`.

> «Кружится голова, из-за этого не могу работать»

`affects_daily_life = yes`.

## 10. Hard cases, обязательные в датасете

- negation;
- uncertain wording;
- hypothetical;
- other experiencer;
- approximate time;
- multi-entity message;
- slang/typos;
- jokes/idioms;
- form/text conflict;
- labs in text;
- out-of-scope complaints;
- empty/noisy messages.

## 11. Dataset audit для Ромы

Для каждого внешнего датасета фиксировать:

```text
name
source
language
clinical / social / synthetic
modality
size
input X
target/labels y
longitudinal yes/no
license/access
which v0.2 fields can be mapped
which fields cannot be mapped
domain shift / limitations
verdict = use_now | evaluate_later | not_fit
```

Отдельно вести два трека:

1. **Clinical NLP / extraction** — тексты -> поля schema.
2. **Predictive ML** — longitudinal data -> заранее определённый future target.

Не использовать dataset для predictive ML только потому, что в нём есть слово depression/anxiety.

## 12. Стартовый evaluation set

Этап 1: 100–150 сообщений — проверка схемы и guideline.  
Этап 2: 300–500 development/synthetic сообщений.  
Этап 3: отдельный clinician-reviewed hold-out около 100 сообщений.

Hold-out не использовать при prompt/model tuning.

## 13. Метрики

- entity Precision/Recall/F1;
- modifier F1;
- risk-signal Recall;
- hallucination rate;
- evidence-span match;
- valid JSON/schema pass rate;
- unknown correctness;
- P50/P95 latency.

Для safety signals основной акцент — Recall, но false positives анализируются отдельно.

## 14. Формат handoff

Рекомендуемый JSONL: один объект на сообщение с `gold_entities[]` и `metadata`.

Каждое поле должно маппиться на `patient_state_v0.2.schema.json` или быть явно помечено как annotation-only metadata.
