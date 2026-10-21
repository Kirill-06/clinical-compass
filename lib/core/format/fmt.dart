import 'package:clinical_compass/core/time/dates.dart';

/// Форматирование дат, чисел и размеров для русского интерфейса.
/// Все моменты времени выводятся в локальном часовом поясе.
abstract final class Fmt {
  static const _monthsShort = [
    'янв.',
    'февр.',
    'марта',
    'апр.',
    'мая',
    'июня',
    'июля',
    'авг.',
    'сент.',
    'окт.',
    'нояб.',
    'дек.',
  ];

  static const _monthsLong = [
    'января',
    'февраля',
    'марта',
    'апреля',
    'мая',
    'июня',
    'июля',
    'августа',
    'сентября',
    'октября',
    'ноября',
    'декабря',
  ];

  static const _weekdaysShort = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс'];
  static const _weekdaysLong = ['понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота', 'воскресенье'];

  static DateTime _local(DateTime d) => d.isUtc ? d.toLocal() : d;

  /// 17 окт. 2026
  static String date(DateTime d) {
    final l = _local(d);
    return '${l.day} ${_monthsShort[l.month - 1]} ${l.year}';
  }

  /// 17 окт.
  static String dateShort(DateTime d) {
    final l = _local(d);
    return '${l.day} ${_monthsShort[l.month - 1]}';
  }

  /// 17 октября 2026
  static String dateLong(DateTime d) {
    final l = _local(d);
    return '${l.day} ${_monthsLong[l.month - 1]} ${l.year}';
  }

  /// «Миронова А. С.» без переноса между фамилией и инициалами.
  static String noBreak(String s) => s.replaceAll(' ', '\u00A0');

  /// 17 октября
  static String dayMonth(DateTime d) {
    final l = _local(d);
    return '${l.day} ${_monthsLong[l.month - 1]}';
  }

  /// 09:05
  static String time(DateTime d) {
    final l = _local(d);
    final hh = l.hour.toString().padLeft(2, '0');
    final mm = l.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }

  /// 17 окт. 2026, 09:05
  static String dateTime(DateTime d) => '${date(d)}, ${time(d)}';

  static String weekdayShort(DateTime d) => _weekdaysShort[_local(d).weekday - 1];

  static String weekdayLong(DateTime d) => _weekdaysLong[_local(d).weekday - 1];

  /// «сегодня», «вчера», «завтра» или короткая дата.
  static String relativeDay(DateTime day, DateTime today) {
    final diff = daysBetween(today, day);
    if (diff == 0) return 'сегодня';
    if (diff == -1) return 'вчера';
    if (diff == 1) return 'завтра';
    if (_local(day).year != _local(today).year) return date(day);
    return dateShort(day);
  }

  /// «сегодня, 09:05», «вчера, 18:30», «12 окт., 10:00».
  static String relativeMoment(DateTime moment, DateTime now) => '${relativeDay(moment, now)}, ${time(moment)}';

  /// Разница в баллах с типографским минусом: +3, −2, 0.
  static String delta(int value) {
    if (value > 0) return '+$value';
    if (value < 0) return '−${value.abs()}';
    return '0';
  }

  static String fileSize(int bytes) {
    if (bytes < 1024) return '$bytes Б';
    final kb = bytes / 1024;
    if (kb < 1024) return '${_decimal(kb)} КБ';
    return '${_decimal(kb / 1024)} МБ';
  }

  static String _decimal(double v) {
    final s = v >= 10 ? v.toStringAsFixed(0) : v.toStringAsFixed(1);
    return s.replaceAll('.', ',');
  }

  /// Русское склонение: plural(3, 'день', 'дня', 'дней') → «дня».
  static String plural(int n, String one, String few, String many) {
    final mod10 = n.abs() % 10;
    final mod100 = n.abs() % 100;
    if (mod10 == 1 && mod100 != 11) return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
    return many;
  }

  static String days(int n) => '$n ${plural(n, 'день', 'дня', 'дней')}';
}
