/// Источник текущего времени. Позволяет детерминированно тестировать
/// расписания check-in и технические правила.
abstract class Clock {
  DateTime now();
}

class SystemClock implements Clock {
  const SystemClock();

  @override
  DateTime now() => DateTime.now();
}

/// Часы с фиксированным временем — только для тестов и демо-сценариев.
class FixedClock implements Clock {
  FixedClock(this._now);

  DateTime _now;

  @override
  DateTime now() => _now;

  void advance(Duration duration) => _now = _now.add(duration);
}
