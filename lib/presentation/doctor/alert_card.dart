import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';

/// Алерт в рабочей очереди: приоритет, правило, «Почему?» (rule_id,
/// источник, факты Patient State), текст пациенту и действия врача.
class AlertCard extends StatefulWidget {
  const AlertCard({super.key, required this.view, this.showPatient = true, this.now});

  final Json view;
  final bool showPatient;
  final DateTime? now;

  @override
  State<AlertCard> createState() => _AlertCardState();
}

class _AlertCardState extends State<AlertCard> {
  bool _open = false;

  Json get _alert => asJson(widget.view['alert']);

  void _toggle() {
    setState(() => _open = !_open);
    final status = AlertStatus.fromWire(_alert['status']! as String);
    if (_open && status == AlertStatus.deliveredToWorkplace) {
      unawaited(context.api.alertAction(_alert['id']! as String, 'view').then((_) {}, onError: (Object _) {}));
    }
  }

  @override
  Widget build(BuildContext context) {
    final a = _alert;
    final v = widget.view;
    final priority = DoctorPriority.fromWire(a['doctor_priority']! as String);
    final status = AlertStatus.fromWire(a['status']! as String);
    final action = PatientAction.fromWire(a['patient_action']! as String);
    final patient = asJson(v['patient']);
    final created = DateTime.parse(a['created_at']! as String);
    final pinned = v['pinned'] == true;
    final why = [for (final f in v['why'] as List? ?? const []) asJson(f)];
    final template = v['patient_template'] is Map ? asJson(v['patient_template']) : null;
    final safety = [for (final e in v['patient_safety_actions'] as List? ?? const []) asJson(e)];
    final now = widget.now ?? DateTime.now();

    return Container(
      decoration: BoxDecoration(
        color: pinned ? AppColors.dangerBg.withValues(alpha: 0.35) : AppColors.surface,
        border: Border(
          left: BorderSide(
            color: priority == DoctorPriority.urgent ? AppColors.dangerFg : Colors.transparent,
            width: 4,
          ),
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.fromLTRB(Space.x4, Space.x4, Space.x4, Space.x3),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: Space.x2,
              runSpacing: Space.x1,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                priorityBadge(priority),
                alertStatusBadge(status),
                if (pinned)
                  const StatusBadge(
                    label: 'Закреплено до принятия',
                    tone: StatusTone.danger,
                    icon: Icons.push_pin_outlined,
                    dense: true,
                  ),
                if (v['medical_urgency_classified'] == false)
                  const StatusBadge(
                    label: 'Вне области инструмента',
                    tone: StatusTone.neutral,
                    icon: Icons.help_outline,
                    dense: true,
                    tooltip: 'Система не определяет причину и срочность этой жалобы',
                  ),
                Text(Fmt.relativeMoment(created, now), style: AppType.caption),
              ],
            ),
            const SizedBox(height: Space.x2),
            if (widget.showPatient)
              Text('${patient['full_name']} · ${patient['display_id']}', style: AppType.bodyStrong),
            Text(v['rule_title']! as String, style: AppType.body.copyWith(fontSize: 14)),
            if (why.isNotEmpty)
              Text(why.first['summary']! as String, style: AppType.small, maxLines: 2, overflow: TextOverflow.ellipsis),
            if (safety.isNotEmpty) ...[const SizedBox(height: Space.x2), PatientSafetyActions(events: safety)],
            const SizedBox(height: Space.x2),
            Wrap(
              spacing: Space.x2,
              runSpacing: Space.x1,
              children: [
                TextButton.icon(
                  onPressed: _toggle,
                  icon: Icon(_open ? Icons.expand_less : Icons.help_outline, size: 18),
                  label: Text(_open ? 'Скрыть' : 'Почему?'),
                ),
                if (widget.showPatient)
                  TextButton(
                    onPressed: () => context.go('/doctor/patients/${patient['id']}'),
                    child: const Text('Карточка пациента'),
                  ),
                if (status != AlertStatus.acknowledged && status != AlertStatus.resolved)
                  OutlinedButton(
                    onPressed: () => unawaited(
                      runDoctorAction(
                        context,
                        () => context.api.alertAction(a['id']! as String, 'acknowledge'),
                        'Принято в работу',
                      ),
                    ),
                    child: const Text('Принять в работу'),
                  ),
                if (status != AlertStatus.resolved)
                  TextButton(
                    onPressed: () => unawaited(
                      runDoctorAction(
                        context,
                        () => context.api.alertAction(a['id']! as String, 'resolve'),
                        'Алерт закрыт',
                      ),
                    ),
                    child: const Text('Закрыть'),
                  ),
              ],
            ),
            if (_open) ...[
              const SizedBox(height: Space.x2),
              Container(
                padding: const EdgeInsets.all(Space.x3),
                decoration: BoxDecoration(
                  color: AppColors.surfaceSubtle,
                  borderRadius: Radii.smAll,
                  border: Border.all(color: AppColors.border),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Правило ${a['rule_id']} · версия ${a['rule_version']} · источник: ${v['rule_source']}',
                      style: AppType.smallStrong,
                    ),
                    const SizedBox(height: Space.x2),
                    const Text('Факты Patient State:', style: AppType.caption),
                    for (final f in why)
                      Padding(
                        padding: const EdgeInsets.only(top: 2),
                        child: Text(
                          '• ${f['summary']}${f['source'] == null ? '' : ' (${f['source']}${f['confirmation'] == null ? '' : ', ${f['confirmation']}'})'}',
                          style: AppType.small,
                        ),
                      ),
                    const SizedBox(height: Space.x2),
                    Text(patientActionLabel(action), style: AppType.small),
                    if (template != null)
                      Text(
                        'Шаблон ${template['id']} (${template['status']}): «${template['title']}»',
                        style: AppType.caption,
                      ),
                    const SizedBox(height: Space.x2),
                    Text(
                      [
                        'Создан ${Fmt.dateTime(created)}',
                        if (a['delivered_to_workplace_at'] != null) 'в очереди сразу',
                        if (a['viewed_at'] != null)
                          'просмотрен ${Fmt.dateTime(DateTime.parse(a['viewed_at']! as String))}',
                        if (v['acknowledged_at'] != null) 'принят ${v['acknowledged_by']}',
                        if (v['resolved_at'] != null)
                          'закрыт ${v['resolved_by']} ${Fmt.dateTime(DateTime.parse(v['resolved_at']! as String))}',
                      ].join(' · '),
                      style: AppType.caption,
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Что пациент сделал с экстренным предупреждением: увидел, позвонил 112/103, закрыл.
class PatientSafetyActions extends StatelessWidget {
  const PatientSafetyActions({super.key, required this.events});

  final List<Json> events;

  static (String, IconData, StatusTone) _visual(String action) => switch (action) {
    'shown' => ('увидел(а) экран «Позвоните 112»', Icons.visibility_outlined, StatusTone.neutral),
    'call_112' => ('нажал(а) «Позвонить 112»', Icons.call, StatusTone.danger),
    'call_103' => ('нажал(а) «Скорая — 103»', Icons.local_hospital_outlined, StatusTone.danger),
    'message_doctor' => ('перешёл(ла) к сообщению врачу', Icons.chat_bubble_outline, StatusTone.info),
    'dismissed' => ('закрыл(а): «Я в безопасности»', Icons.check, StatusTone.ok),
    _ => (action, Icons.info_outline, StatusTone.neutral),
  };

  @override
  Widget build(BuildContext context) => Wrap(
    spacing: Space.x2,
    runSpacing: Space.x1,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      const Text('Пациент:', style: AppType.caption),
      for (final e in events)
        Builder(
          builder: (context) {
            final (label, icon, tone) = _visual(e['action']! as String);
            return StatusBadge(
              label: '$label · ${Fmt.time(DateTime.parse(e['at']! as String))}',
              tone: tone,
              icon: icon,
              dense: true,
            );
          },
        ),
    ],
  );
}
