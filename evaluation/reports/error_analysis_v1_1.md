# Error analysis: GigaChat-3-Ultra / extractor_prompt_v1.1

Baseline: `evaluation/data/generated_annotations.v1.1.jsonl` (155 messages, 172 gold entities), `predictions.jsonl` (206 predicted entities), `metrics.json`. No inference was rerun. This is an analysis of the saved output, not a clinical validation.

## How matching was checked

I read the JSONL records and `backend/src/clinical_compass/evaluation.py` before classifying errors. The evaluator's `_primary_label` compares symptom `(type, normalized_type, polarity, experiencer, temporality)`, medication `(type, status, slot, missed_reason)`, risk `(type, risk_type)`, and lab `(type, analyte, value, unit)`. Drug, dose, other optional fields, and evidence span **do not affect** TP/FP/FN. Evidence exact match is calculated separately by pairing labels **within each message**. In contrast, `_counter_metrics` receives counters accumulated **across all messages**, so a prediction in the wrong message can cancel an FN elsewhere.

Run `python evaluation/out_gigachat_v1_1/error_analysis_check.py` from the repository root to reproduce the count bridge and text/span integrity checks. It loads both JSONL files with `json.loads`, computes `_primary_label` for each entity as above, and sums `Counter(predicted_labels) - Counter(gold_labels)` and the reverse **for each row**. It pairs equal labels once per row for span comparison. The manual groups in subsequent sections partition the row-local residuals; IDs locate each original JSONL record. The saved `metrics.json` is the source of the official figures.

| Entity type | Official TP | FP | FN | Precision | Recall | F1 | Row-local TP / FP / FN |
|---|---:|---:|---:|---:|---:|---:|---:|
| symptom | 94 | 54 | 23 | 0.635135 | 0.803419 | 0.709434 | 88 / 60 / 29 |
| medication | 28 | 19 | 3 | 0.595745 | 0.903226 | 0.717949 | 28 / 19 / 3 |
| risk_signal | 10 | 0 | 9 | 1.000000 | 0.526316 | 0.689655 | 7 / 3 / 12 |
| lab_mention | 1 | 0 | 4 | 1.000000 | 0.200000 | 0.333333 | 1 / 0 / 4 |
| **Total** | **133** | **73** | **39** | **0.645631** | **0.773256** | **0.703704** | **124 / 82 / 48** |

The official 54 symptom FP/23 FN and 9 risk FN cannot be assigned one-to-one to messages: global counting cancels six symptom FP/FN pairs and three risk FP/FN pairs across different messages. The row-local inventory below covers **every** concrete discrepancy: 60 symptom FP + 29 FN, 19 medication FP + 3 FN, 3 risk FP + 12 FN, and 4 lab FN. This is an evaluator accounting problem, not a claim that the model made fewer errors. Do not tune the prompt against the official “hallucination rate” as though it were a per-message hallucination measure.

## Symptom: 60 row-local FP and 29 FN

All 29 row-local FN have a same-message symptom prediction representing the apparent concept. They are predominantly attribute errors, not wholly missed symptom mentions. Each paired mismatch generates one row-local FP and one FN:

| Paired cause | FP / FN | Message IDs and observation |
|---|---:|---|
| Temporality: `recent_past` predicted, gold `current` | 10 / 10 | gen_004, 008, 014, 020, 049 (other experiencer preserved), 071 **twice**, 078, 088, 112. “Последние дни”, “уже третий день”, “несколько дней”, “вчера” trigger the difference. Some gold `current` labels for retrospective wording deserve annotation review. |
| Polarity `present` vs gold `uncertain` | 8 / 8 | gen_036, 037, 039, 040, 041, 042, 044, 045. Hedges such as “кажется”, “вроде”, “возможно”, “как будто” were treated as certainty. |
| Hypothetical: `uncertain` vs gold `present` | 9 / 9 | gen_056, 057, 058, 059, 060, 061, 062, 064, 065. |
| Hypothetical with both polarity and temporality wrong | 1 / 1 | gen_063: gold `present/hypothetical`, predicted `uncertain/current`. |
| Wrong normalized type | 1 / 1 | gen_106: gold `other_unlisted` for half-face numbness, predicted `paresthesia`. Ontology boundary, not an absent clinical mention. |

For exact accounting of the 18 polarity-related pairs: **8** hedged-current IDs (036, 037, 039, 040, 041, 042, 044, 045), **9** hypothetical IDs (056–062, 064, 065), and **1** combined polarity/temporality ID (063). That is 18 FP + 18 FN.

The other **31 symptom FP** have no unmatched gold symptom partner after pairing. These groups are mutually exclusive:

| Cause | Count | IDs / evidence |
|---|---:|---|
| Duplicate or overlapping concept | 10 | gen_016 (neck stiffness alongside `muscle_rigidity`), 033 (second constipation with different temporality), 037 (insomnia alongside poor sleep), 060 (second asthenia), 121, 127, 128, 130 (repeated same symptom), 146, 148 (extra “absent/current” after resolved past symptom). |
| Fragment without independent symptom evidence | 7 | gen_012 “После еды”; 042 “в кистях”; 044 “во рту”; 053 “смены питания”; 107 “С утра”; 108 “на подбородке”; 112 “два дня”. These spans are exact substrings but do not support a separate symptom. |
| Unsupported symptom interpretation | 5 | gen_007 “Сплю вроде достаточно” → somnolence; 084 “было нехорошо” → `other_unlisted`; 115 work-conflict worry → increased anxiety; 123 “стрёмно” → increased anxiety; 139 “настроения не было” → `other_unlisted`. |
| Plausible explicit mention absent from gold / ontology overlap | 9 | gen_089 “разбитый” → asthenia; gen_096, 097, 103: two physical signs each (6) encoded in gold only as allergic-reaction risk; gen_109 “шумит” (ear noise beside blocked ear); gen_144 back pain beside concomitant-drug risk. These require annotation-policy review before being called hallucinations. |

No row-local symptom FN is due solely to evidence-span mismatch, because spans are excluded from semantic matching. There is no row-local `experiencer` mismatch in the 29 paired symptom errors; the model did mark gen_049 as `other`.

## Medication: 19 FP and 3 FN

Three same-message pairs differ only in `missed_reason`: gen_084 gold `felt_unwell`, predicted `unknown`; gen_088 gold `adverse_event`, predicted `unknown`; gen_139 gold `decided_to_stop`, predicted `other`. In gen_084 and 088, drug values are also speculative (`"unknown"` and generic “таблетка”), but they do not affect the evaluator key. No unmatched pair is caused by `status` or `slot` alone. The gold reason for gen_139 (“настроения не было”) may itself warrant review: `decided_to_stop` is not explicit in the sentence.

The other **16 FP** have no gold medication entity in the row:

| Cause | Count | IDs / observation |
|---|---:|---|
| Duplicate extraction from a message already containing a matched missed intake | 3 | gen_077 (ran out), 080 (stopping treatment), 085 (stopping treatment). Each invents a second status/slot event. |
| Unsupported intake event or corrected assertion treated as intake | 9 | gen_010 and 047 (“после таблетки”; 047 is husband's tablet), 096 (“после таблетки”), 099 (intention to stop), gen_100 second entity (“думаю бросить”), 122 (“после таблы”), 125 (“после лекарства”), 147 (“после таблеток”), 152 (“выпил таблетку” explicitly corrected by “на самом деле забыл”). |
| Explicit exposure/ongoing medication mention outside gold intake scope | 4 | gen_095 double dose (gold overdose risk), gen_100 first entity (“Пока принимаю назначенное”), gen_144 two named concurrent drugs (gold concomitant-drug risk). These are not invented mentions; policy must say whether they also merit medication annotation. |

The model emitted literal `drug="unknown"` in **14 of 47** medication predictions. Annotation schema permits optional `drug` to be absent; this value is not a genuine drug and should be omitted. It does **not** explain the 19 FP because `drug` is outside the matching key. No predicted `dose_mg` was present. `missed_reason="unknown"` appears in 13 predictions; unlike `drug`, this is an allowed enum value, but its presence differs from omission under the strict key (`None` vs `unknown`). The 3 paired FN above concern explicit reasons, not an omission-vs-unknown pair. Nine matched medication semantic labels have nonexact evidence spans.

## Risk signal: safety-critical row-local inventory

Official global risk FN is **9**, but **12 gold risk entities are absent in their own messages**. All 12 need review. “Prediction” lists the relevant saved entities; absence of a risk entity is explicit. Causes are hypotheses from the text/output, not observed model reasoning.

| Message | Patient text | Gold risk | Prediction | Likely failure mode |
|---|---|---|---|---|
| gen_091 | Иногда думаю о самоубийстве и не знаю, что делать. | self_harm_or_suicidal | none | Explicit suicidal ideation missed. |
| gen_094 | Я боюсь, что могу принять слишком много таблеток. | possible_overdose | none | Potential overdose phrased as fear/possibility was dropped. |
| gen_096 | После таблетки отекли губы и стало трудно дышать. | possible_allergic_reaction | two `other_unlisted` symptoms + medication | Reaction signs split into symptoms; risk ontology not applied. |
| gen_097 | После лекарства появилась сыпь и зуд по всему телу. | possible_allergic_reaction | two `other_unlisted` symptoms | Rash/itching split into symptoms; risk ontology not applied. |
| gen_098 | Я больше не хочу продолжать лечение и собираюсь отменить препарат. | intention_to_stop_treatment | none | Intention to stop not recognized. |
| gen_101 | У меня мысли навредить себе сегодня вечером. | self_harm_or_suicidal | none | Self-harm ideation missed despite explicit intent language. |
| gen_102 | Я принял несколько лишних таблеток, чем было назначено. | possible_overdose | none | Actual extra dose missed. |
| gen_103 | После новой таблетки язык опух и появилась крапивница. | possible_allergic_reaction | two `other_unlisted` symptoms | Swelling/urticaria split into symptoms; risk ontology not applied. |
| gen_105 | Иногда думаю сделать себе больно, чтобы стало легче. | self_harm_or_suicidal | none | Less literal self-harm phrasing missed. |
| gen_115 | Я переживаю из-за конфликта на работе. | other_concern | `anxiety_increased` symptom | General concern mapped to symptom. Gold `other_concern` breadth merits review. |
| gen_143 | Я беременна, можно ли продолжать пить эти таблетки? | pregnancy_or_lactation | none | Explicit pregnancy missed. |
| gen_144 | Принимаю антидепрессант вместе с ибупрофеном от боли в спине. | concomitant_drug_mention | two medication entities + back-pain symptom | Concomitant use split into two drugs; risk relation missed. |

| Risk type | Gold | Same-message TP | Same-message FN | Systematic observation |
|---|---:|---:|---:|---|
| self_harm_or_suicidal | 5 | 2 | 3 | Three explicit ideation variants missed. |
| possible_overdose | 3 | 1 | 2 | One potential and one actual extra-dose case missed. |
| possible_allergic_reaction | 3 | 0 | 3 | **All three** reaction cases missed; symptoms substituted. |
| pregnancy_or_lactation | 1 | 0 | 1 | One explicit case missed; sample too small for trend. |
| concomitant_drug_mention | 1 | 0 | 1 | Relation between two drugs missed. |
| alcohol_use_mention | 1 | 1 | 0 | Detected. |
| intention_to_stop_treatment | 4 | 3 | 1 | One explicit intention missed. |
| other_concern | 1 | 0 | 1 | Gold scope may be broad. |

Three row-local risk FP explain the global masking: gen_093 duplicates `self_harm_or_suicidal`; gen_059 labels fear of future dizziness as `other_concern`; gen_145 labels concern about alcohol/drug interaction as `concomitant_drug_mention` without a second drug. Those three labels cancel the global FN for one self-harm, one other-concern, and one concomitant-drug message. This makes official risk FP=0 and risk FN=9 despite three extra risk predictions and 12 missed-message risk entities.

## Lab mention: four FN (n=5)

| Message | Text | Gold lab | Prediction | Observation |
|---|---|---|---|---|
| gen_116 | В анализе гемоглобин 128 г/л. | hemoglobin 128 г/л | none | Explicit numeric result + unit missed. |
| gen_117 | В бланке eGFR указан 92 мл/мин/1,73 м². | egfr 92 мл/мин/1,73 м² | none | Explicit eGFR result missed. |
| gen_118 | CPK в результате анализа — 145 Ед/л. | cpk 145 Ед/л | none | Explicit CPK result missed. |
| gen_120 | В анализах написано CPK 210 U/L. | cpk 210 U/L | none | Second CPK notation missed. |

One of five lab mentions was detected. This sample is too small for strong analyte-level conclusions, although both CPK examples failed.

## Evidence and text integrity

All 155 `predictions.text` values equal their corresponding gold `text` **character for character**. All **206 predicted** and **172 gold** spans have in-bounds offsets and satisfy `text[start:end] == evidence_span.text`. The saved prediction format has **no `original_text` field**, so the original `FreeTextExtraction.original_text` cannot be independently byte-compared from these files. For these UTF-8 JSONL records, comparing parsed strings establishes character equality; a raw-byte identity claim about the transient HTTP payload would require capturing it.

Among **124 same-message semantic matches**, **39** evidence spans differ: symptom 25, medication 9, risk 5, lab 0. None of the 39 becomes equal after trimming ends or collapsing whitespace; there is no observed whitespace-normalization pattern. Examples: gen_002 gold “болит голова” vs prediction “С утра сильно болит голова”; gen_022 gold “не тошнит” vs prediction “тошнит” (negation omitted from evidence although polarity is correct); gen_079 medication gold “не стала принимать препарат” vs predicted longer “Утром не стала принимать препарат”; gen_093 risk gold “хочется умереть” vs prediction “Мне хочется умереть”. These are boundary/coverage differences in valid substrings. They do not show that span repair changed whitespace. Because model raw completions are not saved, this audit cannot prove whether repair ran; the saved spans themselves are valid and do not indicate an implementation bug.

## Hallucination-rate interpretation

The published `hallucination_rate=73/206=35.4369%` counts **global strict-label FP**, not necessarily invented facts. The more defensible row-local partition is:

| Category of 82 row-local FP | Count | Interpretation |
|---|---:|---|
| Same concept, wrong strict attribute/type | 32 | 29 symptom pairs (10 temporality, 18 polarity-related, 1 normalized type) + 3 medication reason pairs. |
| Duplicate/overlapping entity | 14 | 10 symptom + 3 medication + 1 risk. |
| Clearly unsupported or evidence-only fragment | 23 | 12 symptom (7 fragments + 5 unsupported), 9 medication unsupported intake events, 2 risk extras. |
| Explicit/plausible mention outside gold scope | 13 | 9 symptom + 4 medication; needs annotation-policy review. |

A conservative **semantic_extra_entity_rate** is **23/206 = 11.17%**: clearly unsupported independent entities among all predictions. An upper bound counting all 13 gold-scope ambiguities as extras is **36/206 = 17.48%**. Duplicates are reported separately (14/206 = 6.80%). These are analyst categories, not evaluator metrics, and they should not replace gold review. Wrong attributes can still carry safety risk even though they are not extra entities. Evidence mismatches are separate and contribute zero to semantic FP in this evaluator.

## Hard cases for prompt tuning

| ID | Why useful |
|---|---|
| gen_091 | Direct suicidal ideation missed. |
| gen_094 | Potential overdose framed as fear missed. |
| gen_096 | Allergy signs split into symptoms; risk missed and intake inferred from “после таблетки”. |
| gen_101 | Self-harm ideation with time phrase missed. |
| gen_102 | Actual extra tablets missed. |
| gen_103 | Swelling plus urticaria split into symptoms. |
| gen_143 | Explicit pregnancy missed. |
| gen_144 | Two concomitant drugs split into separate medication events; risk missed. |
| gen_036 | “Кажется” converted from uncertain to present. |
| gen_056 | Hypothetical nausea marked uncertain instead of gold present/hypothetical. |
| gen_063 | Hypothetical attention issue marked uncertain/current. |
| gen_047 | Husband's tablet converted into patient's intake. |
| gen_084 | Missed reason `felt_unwell` lost; vague `other_unlisted` added. |
| gen_088 | Adverse-event reason lost; “вчера” shifted dizziness temporality. |
| gen_152 | Corrected “выпил” assertion still emitted as extra taken event. |

## Minimal recommendations before extractor_prompt_v1.2

1. **Fix evaluator accounting first**: key semantic matches by message ID as well as label, while retaining the current per-row evidence-span pairing. Keep the old baseline file untouched; publish a new metric version or an auxiliary diagnostic so scores remain comparable. This is warranted by 9 cross-message cancellations, including 3 safety-critical risk cases.
2. Clarify symptom polarity vs temporality: hedges about a *current* symptom are `uncertain`; a possible *future* symptom remains `present/hypothetical` under this gold policy. Ask annotators to resolve current-vs-recent-past examples such as gen_020/071/078/088 before changing temporal wording.
3. Prioritize risk ontology explicitly: allergic signs after medication, overdose (actual and possible), self-harm ideation, pregnancy, and concurrent drugs. Treat risk relations as entities even when their words also describe symptoms or medications. Review whether `other_concern` covers routine situational worry (gen_115).
4. Require an explicit intake action for medication events; a tablet mentioned as context, a plan to stop, or a corrected assertion is not an intake. Do not output a literal `drug="unknown"` when the field can be omitted. Keep the evidence span sufficient for negation and corrections.
5. Suppress duplicate/fragment symptom entities. `other_unlisted` needs a symptom phrase, not a time, location, or cause fragment. For lab mentions, spell out that a stated analyte + number + unit must be returned; validate on more than five examples before broad claims.

No extractor, prompt, model, gold, evaluator, or clinical rules were modified for this report.
