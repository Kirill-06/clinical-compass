/// Небольшие помощники для разбора JSON ответов API с понятными ошибками.
library;

typedef Json = Map<String, Object?>;

Json asJson(Object? v, [String what = 'объект']) {
  if (v is Map) return v.cast<String, Object?>();
  throw FormatException('Ожидался $what');
}

String reqString(Json j, String key) {
  final v = j[key];
  if (v is String && v.isNotEmpty) return v;
  throw FormatException('Поле «$key» обязательно');
}

String? optString(Json j, String key) {
  final v = j[key];
  if (v == null) return null;
  if (v is String) return v;
  throw FormatException('Поле «$key» должно быть строкой');
}

int reqInt(Json j, String key) {
  final v = j[key];
  if (v is int) return v;
  if (v is num && v == v.roundToDouble()) return v.toInt();
  throw FormatException('Поле «$key» должно быть целым числом');
}

int? optInt(Json j, String key) => j[key] == null ? null : reqInt(j, key);

num reqNum(Json j, String key) {
  final v = j[key];
  if (v is num) return v;
  throw FormatException('Поле «$key» должно быть числом');
}

num? optNum(Json j, String key) => j[key] == null ? null : reqNum(j, key);

bool reqBool(Json j, String key) {
  final v = j[key];
  if (v is bool) return v;
  throw FormatException('Поле «$key» должно быть true/false');
}

DateTime reqTime(Json j, String key) => DateTime.parse(reqString(j, key)).toUtc();

DateTime? optTime(Json j, String key) {
  final s = optString(j, key);
  return s == null ? null : DateTime.parse(s).toUtc();
}

List<T> listOf<T>(Json j, String key, T Function(Json) parse) {
  final v = j[key];
  if (v == null) return const [];
  if (v is! List) throw FormatException('Поле «$key» должно быть массивом');
  return List.unmodifiable(v.map((e) => parse(asJson(e))));
}

String iso(DateTime t) => t.toUtc().toIso8601String();

/// Календарная дата `yyyy-MM-dd` без времени.
String dateKey(DateTime d) {
  final mm = d.month.toString().padLeft(2, '0');
  final dd = d.day.toString().padLeft(2, '0');
  return '${d.year}-$mm-$dd';
}

DateTime parseDateKey(String s) {
  final p = s.split('-');
  if (p.length != 3) throw FormatException('Неверная дата: $s');
  return DateTime.utc(int.parse(p[0]), int.parse(p[1]), int.parse(p[2]));
}
