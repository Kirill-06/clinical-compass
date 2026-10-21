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
import 'package:clinical_compass/presentation/doctor/alert_card.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/doctor/patient_detail_parts.dart';
import 'package:clinical_compass/presentation/shared/adherence_view.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

class PatientDetailScreen extends StatelessWidget {
  const PatientDetailScreen({super.key, required this.patientId});

  final String patientId;

  @override
  Widget build(BuildContext context) {
    return LiveFuture<Json>(
      reloadKey: patientId,
      pollEvery: const Duration(seconds: 30),
      loadingLabel: 'Загружаем карточку пациента…',
      load: () => context.api.dossier(patientId),
      builder: (context, d) => _Dossier(d: d, now: context.services.clock.now()),
    );
  }
}

class _Dossier extends StatelessWidget {
  const _Dossier({required this.d, required this.now});

  final Json d;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final patient = asJson(d['patient']);
    final pid = patient['id']! as String;
    final alerts = [for (final a in d['alerts']! as List) asJson(a)];
    final open = alerts.where((a) => AlertStatus.fromWire(asJson(a['alert'])['status']! as String).isOpen).toList();
    final twoCols = width >= 1180;
    final scores = ScoresPanel(responses: [for (final r in d['questionnaires']! as List) asJson(r)]);
    final side = Column(
      children: [
        SchedulesPanel(patientId: pid, schedules: [for (final s in d['schedules']! as List) asJson(s)]),
        const SizedBox(height: Space.x5),
        _AdherencePanel(d: d),
      ],
    );
    return SingleChildScrollView(
      padding: doctorPagePadding(context),
      child: ContentWidth(
        maxWidth: 1400,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Wrap(
              spacing: Space.x4,
              runSpacing: Space.x2,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                TextButton.icon(
                  onPressed: () => context.go('/doctor/patients'),
                  icon: const Icon(Icons.arrow_back, size: 18),
                  label: const Text('Пациенты'),
                ),
                const DemoModeStrip(),
              ],
            ),
            const SizedBox(height: Space.x3),
            _Header(d: d),
            const SizedBox(height: Space.x5),
            SectionHeader(
              title: 'Открытые события: ${open.length}',
              subtitle: 'Сначала срочные; «Почему?» показывает правило и факты',
            ),
            const SizedBox(height: Space.x3),
            if (open.isEmpty)
              const Panel(child: Text('Открытых событий нет.', style: AppType.bodySecondary))
            else
              DecoratedBox(
                decoration: BoxDecoration(
                  color: AppColors.surface,
                  borderRadius: Radii.mdAll,
                  border: Border.all(color: AppColors.border),
                ),
                child: ClipRRect(
                  borderRadius: Radii.mdAll,
                  child: Column(
                    children: [
                      for (final (i, a) in _sorted(open).indexed) ...[
                        if (i > 0) const Divider(),
                        AlertCard(key: ValueKey(asJson(a['alert'])['id']), view: a, showPatient: false, now: now),
                      ],
                    ],
                  ),
                ),
              ),
            const SizedBox(height: Space.x6),
            if (twoCols)
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(flex: 7, child: scores),
                  const SizedBox(width: Space.x5),
                  Expanded(flex: 5, child: side),
                ],
              )
            else ...[
              scores,
              const SizedBox(height: Space.x5),
              side,
            ],
            const SizedBox(height: Space.x8),
            DetailTabs(d: d, now: now),
          ],
        ),
      ),
    );
  }

  static List<Json> _sorted(List<Json> list) => [...list]
    ..sort((a, b) {
      final pa = DoctorPriority.fromWire(asJson(a['alert'])['doctor_priority']! as String).rank;
      final pb = DoctorPriority.fromWire(asJson(b['alert'])['doctor_priority']! as String).rank;
      return pb.compareTo(pa);
    });
}

class _Header extends StatelessWidget {
  const _Header({required this.d});

  final Json d;

  @override
  Widget build(BuildContext context) {
    final p = asJson(d['patient']);
    final pid = p['id']! as String;
    final routing = asJson(d['routing']);
    final decision = RouteDecision.fromWire(routing['doctor_decision']! as String);
    final bookings = [for (final b in d['bookings'] as List? ?? const []) asJson(b)];
    final openBooking = bookings.where((b) => b['status'] == 'open' || b['status'] == 'contacted').toList();
    final plan = d['plan'] is Map ? asJson(d['plan']) : null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(header: true, child: Text(p['full_name']! as String, style: AppType.pageTitle)),
        Text(
          '${p['display_id']} · ${p['birth_year']} г. р. · наблюдение с ${Fmt.date(DateTime.parse(p['observation_start']! as String))}',
          style: AppType.bodySecondary,
        ),
        const SizedBox(height: Space.x4),
        Wrap(
          spacing: Space.x10,
          runSpacing: Space.x4,
          children: [
            KeyValue(
              label: 'Препарат',
              value: plan == null ? 'Не назначен' : '${plan['drug']} · ${(plan['slots'] as List).length} приёма в день',
            ),
            KeyValue(
              label: 'Маршрутизация к психиатру',
              value: '',
              valueWidget: Wrap(
                spacing: Space.x2,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  Text(routeLabel(decision), style: AppType.bodyStrong),
                  if (routing['system_recommendation'] == 'review_needed' && decision == RouteDecision.pending)
                    const StatusBadge(
                      label: 'Система рекомендует рассмотреть',
                      tone: StatusTone.warn,
                      icon: Icons.alt_route,
                      dense: true,
                    ),
                  if (routing['patient_visible'] == true)
                    const StatusBadge(
                      label: 'Видно пациенту',
                      tone: StatusTone.info,
                      icon: Icons.visibility_outlined,
                      dense: true,
                    ),
                ],
              ),
            ),
            KeyValue(
              label: 'Задача на запись',
              value: openBooking.isEmpty
                  ? 'Нет'
                  : 'До ${Fmt.dateTime(DateTime.parse(openBooking.last['deadline']! as String))} · ${openBooking.last['status']}',
            ),
            KeyValue(
              label: 'Правила',
              value:
                  'v${d['rule_version']} · Patient State ${d['schema_valid'] == true ? 'соответствует схеме' : 'НЕ соответствует схеме'}',
            ),
          ],
        ),
        const SizedBox(height: Space.x4),
        Wrap(
          spacing: Space.x2,
          runSpacing: Space.x2,
          children: [
            OutlinedButton.icon(
              onPressed: () => unawaited(_routingDialog(context, pid, decision)),
              icon: const Icon(Icons.alt_route, size: 18),
              label: const Text('Решение по маршрутизации'),
            ),
            OutlinedButton.icon(
              onPressed: () => unawaited(_deadlineDialog(context, pid)),
              icon: const Icon(Icons.event_available_outlined, size: 18),
              label: const Text('Назначить срок контакта'),
            ),
          ],
        ),
      ],
    );
  }
}

Future<void> _routingDialog(BuildContext context, String pid, RouteDecision current) async {
  var choice = current == RouteDecision.pending ? RouteDecision.none : current;
  final ok = await showDialog<bool>(
    context: context,
    builder: (ctx) => StatefulBuilder(
      builder: (ctx, setState) => AlertDialog(
        title: const Text('Маршрутизация к психиатру'),
        content: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Решение принимает врач. Пациент увидит «желательно» или «обязательно» и следующий шаг только после подтверждения.',
                style: AppType.small,
              ),
              const SizedBox(height: Space.x3),
              RadioGroup<RouteDecision>(
                groupValue: choice,
                onChanged: (v) => setState(() => choice = v ?? choice),
                child: Column(
                  children: [
                    for (final r in const [RouteDecision.none, RouteDecision.preferred, RouteDecision.required])
                      RadioListTile<RouteDecision>(
                        value: r,
                        title: Text(routeLabel(r)),
                        contentPadding: EdgeInsets.zero,
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Отмена')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Подтвердить')),
        ],
      ),
    ),
  );
  if (ok != true || !context.mounted) return;
  await runDoctorAction(context, () => context.api.setRouting(pid, choice), 'Решение сохранено');
}

Future<void> _deadlineDialog(BuildContext context, String pid) async {
  final now = DateTime.now();
  final date = await showDatePicker(
    context: context,
    firstDate: now,
    lastDate: now.add(const Duration(days: 90)),
    initialDate: now.add(const Duration(days: 1)),
    helpText: 'Связаться с пациентом до',
  );
  if (date == null || !context.mounted) return;
  final deadline = DateTime(date.year, date.month, date.day, 18);
  await runDoctorAction(
    context,
    () => context.api.setContactDeadline(pid, deadline),
    'Задача администратору создана: связаться до ${Fmt.dateShort(deadline)}',
  );
}

class _AdherencePanel extends StatelessWidget {
  const _AdherencePanel({required this.d});

  final Json d;

  @override
  Widget build(BuildContext context) {
    final a7 = d['adherence_7d'] is Map ? asJson(d['adherence_7d']) : null;
    final a14 = d['adherence_14d'] is Map ? asJson(d['adherence_14d']) : null;
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SectionHeader(
            title: 'Приверженность лечению',
            subtitle: 'Доля принятых доз от назначенных; пропуски с причинами и дни без отметки — отдельно',
            level: 2,
          ),
          const SizedBox(height: Space.x3),
          if (a7 == null)
            const Text('План приёма не назначен.', style: AppType.bodySecondary)
          else ...[
            AdherenceSummaryView(data: a7, title: '7 дней'),
            if (a14 != null) ...[
              const SizedBox(height: Space.x4),
              AdherenceSummaryView(data: a14, title: '14 дней'),
              const SizedBox(height: Space.x3),
              SlotGrid(slots: [for (final s in a14['slots'] as List? ?? const []) asJson(s)]),
            ],
          ],
        ],
      ),
    );
  }
}
