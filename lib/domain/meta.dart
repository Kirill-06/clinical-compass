/// Справочники и шкалы, которые backend отдаёт по `GET /meta`.
///
/// Тексты вопросов, варианты ответов, категории баллов и подписи значений
/// хранятся в `contracts/` и не дублируются в коде приложения.
library;

import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';

class AnswerOption {
  const AnswerOption(this.value, this.label);

  factory AnswerOption.fromJson(Json j) => AnswerOption(reqInt(j, 'value'), reqString(j, 'label'));

  final int value;
  final String label;
}

class SeverityBand {
  const SeverityBand(this.code, this.min, this.max, this.label);

  factory SeverityBand.fromJson(Json j) =>
      SeverityBand(reqString(j, 'code'), reqInt(j, 'min'), reqInt(j, 'max'), reqString(j, 'label'));

  final String code;
  final int min;
  final int max;
  final String label;

  bool contains(int score) => score >= min && score <= max;
}

class InstrumentDefinition {
  const InstrumentDefinition({
    required this.instrument,
    required this.version,
    required this.title,
    required this.instruction,
    required this.items,
    required this.options,
    required this.bands,
    required this.source,
    this.wordingNote,
  });

  factory InstrumentDefinition.fromJson(Json j) => InstrumentDefinition(
    instrument: Instrument.fromWire(reqString(j, 'instrument')),
    version: reqString(j, 'version'),
    title: reqString(j, 'title'),
    instruction: reqString(j, 'instruction'),
    items: List.unmodifiable([for (final item in j['items'] as List? ?? const []) item as String]),
    options: listOf(j, 'options', AnswerOption.fromJson),
    bands: listOf(j, 'bands', SeverityBand.fromJson),
    source: reqString(j, 'source'),
    wordingNote: optString(j, 'wording_note'),
  );

  final Instrument instrument;
  final String version;
  final String title;
  final String instruction;
  final List<String> items;
  final List<AnswerOption> options;
  final List<SeverityBand> bands;
  final String source;
  final String? wordingNote;

  int get itemCount => items.length;
  int get maxScore => items.length * 3;

  SeverityBand bandFor(int score) =>
      bands.firstWhere((b) => b.contains(score), orElse: () => throw RangeError.range(score, 0, maxScore, 'score'));

  String? optionLabel(int value) {
    for (final o in options) {
      if (o.value == value) return o.label;
    }
    return null;
  }
}

/// Содержимое `GET /meta`.
class ContractMeta {
  ContractMeta._(this.schemaVersion, this.ruleVersion, this._instruments, this._vocabulary);

  factory ContractMeta.fromJson(Json j) {
    final instruments = {for (final d in listOf(j, 'instruments', InstrumentDefinition.fromJson)) d.instrument: d};
    final missing = Instrument.values.where((i) => !instruments.containsKey(i));
    if (missing.isNotEmpty) {
      throw FormatException('Сервер не прислал описание шкал: ${missing.map((i) => i.label).join(', ')}');
    }
    final vocabulary = {
      for (final MapEntry(:key, :value) in asJson(j['vocabulary'], 'справочники').entries)
        key: asJson(value).map((k, v) => MapEntry(k, v.toString())),
    };
    return ContractMeta._(reqString(j, 'schema_version'), reqString(j, 'rule_version'), instruments, vocabulary);
  }

  final String schemaVersion;
  final String ruleVersion;
  final Map<Instrument, InstrumentDefinition> _instruments;
  final Map<String, Map<String, String>> _vocabulary;

  InstrumentDefinition instrument(Instrument i) => _instruments[i]!;

  String symptom(SymptomType t) => _label('symptom_types', t.wire);
  String missedReason(MissedReason r) => _label('missed_reasons', r.wire);
  String slot(IntakeSlot s) => _label('intake_slots', s.wire);
  String severity(Severity s) => _label('severity', s.wire);

  /// Неизвестный код показывается как есть — новый код на сервере не ломает экран.
  String _label(String group, String wire) => _vocabulary[group]?[wire] ?? wire;
}
