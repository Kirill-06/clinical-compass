import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';

/// Отображение перечислений контракта: текст + иконка + тон.
/// Категории тяжести шкал цветом не кодируются.

String priorityLabel(DoctorPriority p) => switch (p) {
  DoctorPriority.urgent => 'Срочно',
  DoctorPriority.high => 'Высокий',
  DoctorPriority.normal => 'Обычный',
  DoctorPriority.info => 'Информация',
};

StatusBadge priorityBadge(DoctorPriority p, {bool dense = true}) {
  final (tone, icon) = switch (p) {
    DoctorPriority.urgent => (StatusTone.danger, Icons.priority_high),
    DoctorPriority.high => (StatusTone.warn, Icons.flag_outlined),
    DoctorPriority.normal => (StatusTone.info, Icons.label_outline),
    DoctorPriority.info => (StatusTone.neutral, Icons.info_outline),
  };
  return StatusBadge(
    label: priorityLabel(p),
    tone: tone,
    icon: icon,
    dense: dense,
    tooltip: 'Приоритет в рабочей очереди врача. Не push-уведомление и не диагноз.',
  );
}

String patientActionLabel(PatientAction a) => switch (a) {
  PatientAction.none => 'Пациенту ничего не показывается',
  PatientAction.informAtNextContact => 'Обсудить при следующем контакте',
  PatientAction.contactDoctorSoon => 'Пациенту: связаться с врачом в ближайшее время',
  PatientAction.contactClinicToday => 'Пациенту: связаться с клиникой сегодня',
  PatientAction.recommendAmbulance => 'Пациенту: рекомендация вызвать скорую (текст-шаблон)',
  PatientAction.neutralOutOfLeaflet => 'Пациенту: нейтральный текст «вне области инструмента»',
};

String alertStatusLabel(AlertStatus s) => switch (s) {
  AlertStatus.created => 'Создан',
  AlertStatus.deliveredToWorkplace => 'Новый',
  AlertStatus.viewed => 'Просмотрен',
  AlertStatus.acknowledged => 'В работе',
  AlertStatus.resolved => 'Закрыт',
};

StatusBadge alertStatusBadge(AlertStatus s) {
  final (tone, icon) = switch (s) {
    AlertStatus.created || AlertStatus.deliveredToWorkplace => (StatusTone.info, Icons.fiber_manual_record),
    AlertStatus.viewed => (StatusTone.neutral, Icons.visibility_outlined),
    AlertStatus.acknowledged => (StatusTone.accent, Icons.assignment_ind_outlined),
    AlertStatus.resolved => (StatusTone.ok, Icons.done_all),
  };
  return StatusBadge(label: alertStatusLabel(s), tone: tone, icon: icon, dense: true);
}

String dueLabel(String status) => switch (status) {
  'due' => 'Пора заполнить',
  'overdue' => 'Срок прошёл',
  _ => 'Предстоит',
};

StatusBadge dueBadge(String status) {
  final (tone, icon) = switch (status) {
    'due' => (StatusTone.accent, Icons.edit_calendar_outlined),
    'overdue' => (StatusTone.warn, Icons.event_busy_outlined),
    _ => (StatusTone.neutral, Icons.event_outlined),
  };
  return StatusBadge(label: dueLabel(status), tone: tone, icon: icon, dense: true);
}

(StatusTone, IconData, String) intakeVisual(IntakeStatus s) => switch (s) {
  IntakeStatus.taken => (StatusTone.ok, Icons.check, 'Принят'),
  IntakeStatus.missed => (StatusTone.warn, Icons.close, 'Пропущен'),
  IntakeStatus.unknown => (StatusTone.neutral, Icons.remove, 'Нет отметки'),
};

String routeLabel(RouteDecision d) => switch (d) {
  RouteDecision.pending => 'Решение не принято',
  RouteDecision.none => 'Не требуется',
  RouteDecision.preferred => 'Желательно',
  RouteDecision.required => 'Обязательно',
};

String scoreLine(int? score, int? max) => score == null ? 'Нет данных' : '$score из $max';

String signed(int? v) => v == null ? '—' : Fmt.delta(v);

String percent(num? ratio) => ratio == null ? '—' : '${(ratio * 100).round()}%';
