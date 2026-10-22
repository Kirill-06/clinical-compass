# Adjudication cases перед extractor_prompt_v1.2

Источник: `generated_annotations.v1.1.jsonl`, сохранённые `predictions.jsonl` и `error_analysis.md`. Сопоставление primary labels выполнено **внутри каждого message_id**; evidence span и optional fields не входят в TP/FP/FN. Решения ниже — предложения к медицинской/annotation проверке, не изменения gold. GigaChat не вызывался.

## A. Правдоподобные сущности вне gold — 13

Все решения остаются `pending_adjudication`; `needs_medical_review` не означает автоматического добавления в gold. Полные entity objects находятся в JSONL.

| message_id | исходный text | gold entities | prediction | дополнительная сущность | клиническая правдоподобность | proposed decision |
|---|---|---|---|---|---|---|
| gen_089 | Пропустил утреннюю дозу, потому что с утра совсем разбитый. | medication/missed (morning, reason=felt_unwell; «Пропустил утреннюю дозу») | medication/missed (morning, reason=felt_unwell; «Пропустил утреннюю дозу»); symptom/asthenia (present, current; «разбитый») | symptom/asthenia (present, current; «разбитый») | «разбитый» прямо обозначает выраженную слабость. | needs_medical_review |
| gen_095 | Случайно выпила двойную дозу препарата. | risk/possible_overdose («выпила двойную дозу препарата») | medication/taken (unknown, reason=unknown; «двойную дозу препарата»); risk/possible_overdose («Случайно выпила двойную дозу») | medication/taken (unknown, reason=unknown; «двойную дозу препарата») | «выпила двойную дозу» прямо сообщает о приёме; требуется решить, аннотировать ли его одновременно с риском передозировки. | needs_medical_review |
| gen_096 | После таблетки отекли губы и стало трудно дышать. | risk/possible_allergic_reaction («отекли губы и стало трудно дышать») | symptom/other_unlisted (present, current; «отекли губы»); symptom/other_unlisted (present, current; «стало трудно дышать»); medication/taken (unknown, reason=unknown; «таблетки») | symptom/other_unlisted (present, current; «отекли губы») | Отёк губ после таблетки является явным физическим признаком реакции. | needs_medical_review |
| gen_096 | После таблетки отекли губы и стало трудно дышать. | risk/possible_allergic_reaction («отекли губы и стало трудно дышать») | symptom/other_unlisted (present, current; «отекли губы»); symptom/other_unlisted (present, current; «стало трудно дышать»); medication/taken (unknown, reason=unknown; «таблетки») | symptom/other_unlisted (present, current; «стало трудно дышать») | Затруднение дыхания после таблетки является явным физическим признаком реакции. | needs_medical_review |
| gen_097 | После лекарства появилась сыпь и зуд по всему телу. | risk/possible_allergic_reaction («появилась сыпь и зуд по всему телу») | symptom/other_unlisted (present, current; «сыпь»); symptom/other_unlisted (present, current; «зуд») | symptom/other_unlisted (present, current; «сыпь») | Сыпь после лекарства является явным физическим признаком реакции. | needs_medical_review |
| gen_097 | После лекарства появилась сыпь и зуд по всему телу. | risk/possible_allergic_reaction («появилась сыпь и зуд по всему телу») | symptom/other_unlisted (present, current; «сыпь»); symptom/other_unlisted (present, current; «зуд») | symptom/other_unlisted (present, current; «зуд») | Зуд после лекарства является явным физическим признаком реакции. | needs_medical_review |
| gen_100 | Пока принимаю назначенное, но думаю бросить лечение. | risk/intention_to_stop_treatment («думаю бросить лечение») | medication/taken (unknown, reason=∅; «Пока принимаю назначенное»); medication/unknown (unknown, reason=∅; «думаю бросить лечение»); risk/intention_to_stop_treatment («думаю бросить лечение») | medication/taken (unknown, reason=∅; «Пока принимаю назначенное») | «Пока принимаю» явно описывает продолжающееся лечение; схема medication может требовать отдельной записи. | needs_medical_review |
| gen_103 | После новой таблетки язык опух и появилась крапивница. | risk/possible_allergic_reaction («язык опух и появилась крапивница») | symptom/other_unlisted (present, current; «язык опух»); symptom/other_unlisted (present, current; «крапивница») | symptom/other_unlisted (present, current; «язык опух») | Опухший язык после новой таблетки является явным физическим признаком реакции. | needs_medical_review |
| gen_103 | После новой таблетки язык опух и появилась крапивница. | risk/possible_allergic_reaction («язык опух и появилась крапивница») | symptom/other_unlisted (present, current; «язык опух»); symptom/other_unlisted (present, current; «крапивница») | symptom/other_unlisted (present, current; «крапивница») | Крапивница после новой таблетки является явным физическим признаком реакции. | needs_medical_review |
| gen_109 | Заложило правое ухо и шумит. | symptom/other_unlisted (present, current; «Заложило правое ухо») | symptom/other_unlisted (present, current; «Заложило правое ухо»); symptom/other_unlisted (present, current; «шумит») | symptom/other_unlisted (present, current; «шумит») | «шумит» описывает отдельное ощущение в ухе рядом с заложенностью. | needs_medical_review |
| gen_144 | Принимаю антидепрессант вместе с ибупрофеном от боли в спине. | risk/concomitant_drug_mention («вместе с ибупрофеном») | medication/taken (unknown, reason=unknown; «антидепрессант»); medication/taken (unknown, reason=unknown; «ибупрофеном»); symptom/back_pain (present, current; «боли в спине») | medication/taken (unknown, reason=unknown; «антидепрессант») | «Принимаю антидепрессант» явно описывает употребление препарата, хотя gold содержит только риск сочетания. | needs_medical_review |
| gen_144 | Принимаю антидепрессант вместе с ибупрофеном от боли в спине. | risk/concomitant_drug_mention («вместе с ибупрофеном») | medication/taken (unknown, reason=unknown; «антидепрессант»); medication/taken (unknown, reason=unknown; «ибупрофеном»); symptom/back_pain (present, current; «боли в спине») | medication/taken (unknown, reason=unknown; «ибупрофеном») | «вместе с ибупрофеном» явно описывает второй препарат, хотя gold содержит только риск сочетания. | needs_medical_review |
| gen_144 | Принимаю антидепрессант вместе с ибупрофеном от боли в спине. | risk/concomitant_drug_mention («вместе с ибупрофеном») | medication/taken (unknown, reason=unknown; «антидепрессант»); medication/taken (unknown, reason=unknown; «ибупрофеном»); symptom/back_pain (present, current; «боли в спине») | symptom/back_pain (present, current; «боли в спине») | «боли в спине» прямо обозначает симптом помимо риска сочетания препаратов. | needs_medical_review |

## B. Все message-level risk FN — 12

`possible_allergic_reaction`: **3/3 пропущено** (gen_096, gen_097, gen_103). Для этих сообщений модель выделила признаки как симптомы, но не вернула требуемый risk signal.

| message_id | text | gold risk type | predicted entities | error category | formulation | suggested prompt lesson |
|---|---|---|---|---|---|---|
| gen_091 | Иногда думаю о самоубийстве и не знаю, что делать. | self_harm_or_suicidal | ∅ | explicit_suicidal_ideation | explicit | Распознавать «думаю о самоубийстве» как self_harm_or_suicidal. |
| gen_094 | Я боюсь, что могу принять слишком много таблеток. | possible_overdose | ∅ | possible_overdose_framed_as_fear | implicit | Сохранять possible_overdose при страхе возможной передозировки, даже без факта приёма. |
| gen_096 | После таблетки отекли губы и стало трудно дышать. | possible_allergic_reaction | symptom/other_unlisted (present, current; «отекли губы»); symptom/other_unlisted (present, current; «стало трудно дышать»); medication/taken (unknown, reason=unknown; «таблетки») | allergic_signs_split_into_symptoms | implicit | Добавлять risk_signal при отёке и затруднении дыхания после препарата, даже если признаки выделены как симптомы. |
| gen_097 | После лекарства появилась сыпь и зуд по всему телу. | possible_allergic_reaction | symptom/other_unlisted (present, current; «сыпь»); symptom/other_unlisted (present, current; «зуд») | allergic_signs_split_into_symptoms | implicit | Связывать сыпь и зуд после лекарства с possible_allergic_reaction. |
| gen_098 | Я больше не хочу продолжать лечение и собираюсь отменить препарат. | intention_to_stop_treatment | ∅ | explicit_intent_to_stop | explicit | Распознавать «собираюсь отменить препарат» как intention_to_stop_treatment. |
| gen_101 | У меня мысли навредить себе сегодня вечером. | self_harm_or_suicidal | ∅ | explicit_self_harm_ideation | explicit | Распознавать «мысли навредить себе» как self_harm_or_suicidal независимо от указания времени. |
| gen_102 | Я принял несколько лишних таблеток, чем было назначено. | possible_overdose | ∅ | actual_extra_dose_missed | explicit | Распознавать приём лишних таблеток как possible_overdose. |
| gen_103 | После новой таблетки язык опух и появилась крапивница. | possible_allergic_reaction | symptom/other_unlisted (present, current; «язык опух»); symptom/other_unlisted (present, current; «крапивница») | allergic_signs_split_into_symptoms | implicit | Связывать отёк языка и крапивницу после новой таблетки с possible_allergic_reaction. |
| gen_105 | Иногда думаю сделать себе больно, чтобы стало легче. | self_harm_or_suicidal | ∅ | indirect_self_harm_ideation | explicit | Распознавать «сделать себе больно» как self_harm_or_suicidal. |
| gen_115 | Я переживаю из-за конфликта на работе. | other_concern | symptom/anxiety_increased (present, current; «переживаю») | broad_other_concern_gold_scope | implicit | Уточнить границу other_concern и ситуативного переживания после adjudication gold. |
| gen_143 | Я беременна, можно ли продолжать пить эти таблетки? | pregnancy_or_lactation | ∅ | explicit_pregnancy_missed | explicit | Распознавать явное «Я беременна» как pregnancy_or_lactation. |
| gen_144 | Принимаю антидепрессант вместе с ибупрофеном от боли в спине. | concomitant_drug_mention | medication/taken (unknown, reason=unknown; «антидепрессант»); medication/taken (unknown, reason=unknown; «ибупрофеном»); symptom/back_pain (present, current; «боли в спине») | concomitant_drugs_split_into_medications | explicit | Извлекать concomitant_drug_mention для одновременного приёма двух препаратов. |

## C. Medication mismatches — все 3 FN

Это три same-message несовпадения `missed_reason`; `status` и `slot` совпали.

| message_id | формулировка текста | gold missed_reason | predicted missed_reason | потенциальное уточнение prompt |
|---|---|---|---|---|
| gen_084 | Сегодня пропустил утреннюю таблетку, весь день было нехорошо. | felt_unwell | unknown | Связывать «было нехорошо» с felt_unwell только при достаточной причинной связи с пропуском; иначе согласовать gold/unknown. |
| gen_088 | Утром не принимала таблетку, от неё вчера кружилась голова. | adverse_event | unknown | Если пропуск объяснён прошлым нежелательным эффектом препарата, выбирать adverse_event, а не unknown. |
| gen_139 | Не выпила лекарство, настроения не было совсем. | decided_to_stop | other | Не выводить decided_to_stop без явного решения прекратить лечение; gold reason направить на adjudication. |

Для gen_139 gold `decided_to_stop` требует отдельной проверки: явного решения прекратить лечение в тексте нет.

## D. Symptom normalization — 29 FN

Группы причин: 1 wrong normalized_type + 18 polarity + 10 чистых temporality = 29. Один из 18 polarity случаев (gen_063) также имеет ошибку temporality, поэтому в строке temporality показано 11 затронутых случаев; группы причин пересекаются.

| группа | count | representative examples | замечание |
|---|---:|---|---|
| wrong_normalized_type | 1 | gen_106 «У меня внезапно онемела половина лица.»; gold: symptom/other_unlisted (present, current; «онемела половина лица»); pred: symptom/paresthesia (present, current; «онемела половина лица») | Граница other_unlisted / paresthesia для онемения лица. |
| polarity | 18 | gen_036 «Кажется, меня немного подташнивает.»; gold: symptom/nausea (uncertain, current; «немного подташнивает»); pred: symptom/nausea (present, current; «подташнивает»)<br>gen_056 «Боюсь, что после новой дозы начнёт тошнить.»; gold: symptom/nausea (present, hypothetical; «начнёт тошнить»); pred: symptom/nausea (uncertain, hypothetical; «тошнить»)<br>gen_063 «Боюсь, что совсем не смогу сосредоточиться.»; gold: symptom/attention_disturbance (present, hypothetical; «не смогу сосредоточиться»); pred: symptom/attention_disturbance (uncertain, current; «не смогу сосредоточиться») | 8 текущих симптомов с hedge, 9 гипотетических и 1 сочетанный случай; gen_063 также имеет ошибку temporality. |
| experiencer | 0 | — | В 29 symptom FN нет расхождений experiencer. |
| temporality | 11 | gen_020 «Утром было головокружение.»; gold: symptom/dizziness (present, current; «головокружение»); pred: symptom/dizziness (present, recent_past; «головокружение»)<br>gen_071 «Запор и боль в верхней части живота появились вчера.»; gold: symptom/constipation (present, current; «Запор»); symptom/upper_abdominal_pain (present, current; «боль в верхней части живота»); pred: symptom/constipation (present, recent_past; «Запор»); symptom/upper_abdominal_pain (present, recent_past; «боль в верхней части живота»)<br>gen_063 «Боюсь, что совсем не смогу сосредоточиться.»; gold: symptom/attention_disturbance (present, hypothetical; «не смогу сосредоточиться»); pred: symptom/attention_disturbance (uncertain, current; «не смогу сосредоточиться») | 10 чистых расхождений current / recent_past и 1 сочетанное с polarity; проверить gold для ретроспективных формулировок. |
| other_attribute_mismatch | 0 | — | Опциональные поля и evidence span не входят в primary label; 25 несовпадений symptom evidence учитываются отдельно. |

## E. Duplicates / overlaps — 14

| pattern | count | message_ids | пример / смысл |
|---|---:|---|---|
| duplicate_same_entity | 4 | gen_121, gen_127, gen_128, gen_130 | Повтор одной и той же нормализованной сущности в одном сообщении. Например gen_121: «Чёт башка раскалывается с утра.» |
| overlapping_evidence_or_concept | 2 | gen_016, gen_033 | Близкие описания одной проблемы или повтор с иной temporality. Например gen_016: «Шея будто затекла, мышцы напряжены.» |
| symptom_plus_redundant_broad_symptom | 2 | gen_037, gen_060 | Узкая и широкая symptom-метки для одной формулировки. Например gen_037: «Вроде бы стала хуже спать.» |
| resolved_symptom_repeated_as_absent | 2 | gen_146, gen_148 | К прошлому симптому добавлена лишняя текущая absence-сущность. Например gen_146: «Вчера весь день болела голова, сейчас уже лучше.» |
| duplicate_medication_event | 3 | gen_077, gen_080, gen_085 | Причина пропуска или решение прекратить лечение превращены во второе medication-событие. Например gen_077: «Вечернюю дозу не приняла, потому что закончились таблетки.» |
| duplicate_risk_signal | 1 | gen_093 | Одна суицидальная мысль представлена двумя risk entities. Например gen_093: «Мне хочется умереть, такие мысли не отпускают.» |

## Приоритеты

`data problem?` и `prompt problem?` обозначают гипотезы для проверки, а не утверждённые причины. Количества строк пересекаются между разделами и не суммируются.

| issue | count | data problem? | prompt problem? | code problem? | priority |
|---|---:|---|---|---|---|
| Message-level risk FN | 12 | Да, проверить `other_concern` gen_115 | Да, 11 явных/косвенных safety и контекстных сигналов | Нет для extraction; прежние global metrics маскируют 3 FN | P0 |
| `possible_allergic_reaction` FN (подмножество risk FN) | 3/3 | Проверить политику двойной symptom/risk разметки | Да, связь лекарства с признаками реакции | Нет | P0 |
| Plausible entities outside gold | 13 | Да, границы multi-label annotation | Возможно, после adjudication | Нет | P1 |
| Symptom primary-label FN | 29 | Да, часть temporality и ontology | Да, polarity/hypothetical | Нет | P1 |
| Medication `missed_reason` FN | 3 | Да, gen_139 | Да, причинная связь в gen_084/088 | Нет | P1 |
| Duplicate / overlapping entities | 14 | Возможна неоднозначность единицы annotation | Да, дедупликация | Нет | P1 |
| Lab mention FN (контекст из error_analysis.md) | 4/5 | Не выявлено | Да, analyte + value + unit | Нет | P1 |
| Evidence span mismatch при semantic match | 39 | Возможно, границы span | Возможно, выбор evidence | Нет подтверждения | P2 |
| Global evaluator accounting (уже исправленная message-level логика для этой выборки) | 9 межсообщенческих отмен | Нет | Нет | Да, в старых global metrics | P1 |

## Минимальные изменения для extractor_prompt_v1.2 после adjudication

1. Явно требовать `risk_signal` при self-harm ideation, фактической или возможной передозировке, признаках реакции после лекарства, беременности, одновременном приёме препаратов и намерении отменить лечение. Разрешить risk вместе с подтверждёнными symptom/medication сущностями по согласованной annotation policy.
2. Развести hedge текущего симптома (`uncertain/current`) и страх будущего симптома (`present/hypothetical` по текущему gold); уточнить temporality только после проверки спорных ретроспективных gold.
3. Для `missed_reason` использовать явную причину пропуска: нежелательный эффект → `adverse_event`, плохое самочувствие → `felt_unwell`; не выводить `decided_to_stop` из одного лишь отсутствия настроения.
4. Требовать самостоятельное событие приёма/пропуска для medication; не превращать причину, план или исправленное утверждение во второе событие. Убирать дубли и symptom-фрагменты без самостоятельного признака.
5. Явно возвращать lab mention при analyte + числовом значении + единице.

Prompt, evaluator, extractor, модель и gold dataset не изменены.
