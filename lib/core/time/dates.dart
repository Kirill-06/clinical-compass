/// Работа с календарными днями (без времени).
///
/// Моменты времени (`createdAt`, `updatedAt`) хранятся в UTC и выводятся
/// в локальном времени. Календарные даты (`intakeDate`, `dueDate`) — это
/// локальный день пользователя, хранятся строкой `yyyy-MM-dd`.
library;

DateTime dateOnly(DateTime value) {
  final local = value.isUtc ? value.toLocal() : value;
  return DateTime(local.year, local.month, local.day);
}

DateTime addDays(DateTime day, int days) => DateTime(day.year, day.month, day.day + days);

/// Разница в календарных днях, устойчивая к переходу на летнее время.
int daysBetween(DateTime from, DateTime to) {
  final a = dateOnly(from);
  final b = dateOnly(to);
  final ua = DateTime.utc(a.year, a.month, a.day);
  final ub = DateTime.utc(b.year, b.month, b.day);
  return ub.difference(ua).inDays;
}

bool isSameDay(DateTime a, DateTime b) => daysBetween(a, b) == 0;

String dayKey(DateTime day) {
  final d = dateOnly(day);
  final mm = d.month.toString().padLeft(2, '0');
  final dd = d.day.toString().padLeft(2, '0');
  return '${d.year}-$mm-$dd';
}

DateTime parseDayKey(String key) {
  final parts = key.split('-');
  if (parts.length != 3) {
    throw FormatException('Неверный формат даты: $key');
  }
  return DateTime(int.parse(parts[0]), int.parse(parts[1]), int.parse(parts[2]));
}

DateTime parseUtc(String iso) => DateTime.parse(iso).toUtc();
