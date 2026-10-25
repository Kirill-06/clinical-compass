import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/patient/intake_slots.dart';
import 'package:clinical_compass/presentation/patient/patient_shell.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/notices.dart';

class PatientHomeScreen extends StatelessWidget {
  const PatientHomeScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.user;
    return LiveFuture<Json>(
      reloadKey: user.id,
      load: () => context.api.dashboard(user.id),
      builder: (context, d) {
        final now = context.services.clock.now();
        final patient = asJson(d['patient']);
        final schedules = [for (final s in d['schedules']! as List) asJson(s)];
        final notices = [for (final n in d['notices']! as List) asJson(n)];
        final plan = d['plan'] is Map ? asJson(d['plan']) : null;
        final routing = d['routing'] is Map ? asJson(d['routing']) : null;
        final doctor = d['doctor'] is Map ? asJson(d['doctor']) : null;
        final unread = d['unread_messages'] as int? ?? 0;
        return PatientPage(
          children: [
            Semantics(header: true, child: Text('Здравствуйте, ${patient['first_name']}', style: AppType.pageTitle)),
            const SizedBox(height: 2),
            Text(
              '${_cap(Fmt.weekdayLong(now))}, ${Fmt.dayMonth(now)}${doctor == null ? '' : ' · ваш врач — ${Fmt.noBreak(doctor['short_name']! as String)}'}',
              style: AppType.bodySecondary,
            ),
            const SizedBox(height: Space.x5),
            if (routing != null) ...[_RoutingCard(routing: routing), const SizedBox(height: Space.x4)],
            if (notices.isNotEmpty) ...[
              const NoticesHeader(),
              NoticeList(notices: notices),
              const SizedBox(height: Space.x2),
            ],
            const SectionHeader(title: 'Опросники', level: 2),
            const SizedBox(height: Space.x2),
            for (final s in schedules) ...[_QuestionnaireCard(schedule: s, now: now), const SizedBox(height: Space.x3)],
            const SizedBox(height: Space.x2),
            if (plan != null)
              TodayIntakePanel(patientId: user.id, plan: plan, today: asJson(d['today']))
            else
              const Panel(child: Text('Врач пока не назначил план приёма препарата.', style: AppType.bodySecondary)),
            const SizedBox(height: Space.x4),
            Panel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SectionHeader(title: 'Сообщить врачу', level: 2),
                  const SizedBox(height: Space.x1),
                  const Text(
                    'Отметьте симптом из списка или напишите своими словами. Можно приложить документ.',
                    style: AppType.small,
                  ),
                  const SizedBox(height: Space.x3),
                  OutlinedButton.icon(
                    onPressed: () => context.push('/patient/symptom'),
                    icon: const Icon(Icons.healing_outlined, size: 18),
                    label: const Text('Отметить самочувствие'),
                  ),
                  const SizedBox(height: Space.x2),
                  OutlinedButton.icon(
                    onPressed: () => context.go('/patient/chat'),
                    icon: const Icon(Icons.chat_bubble_outline, size: 18),
                    label: const Text('Написать врачу или приложить файл'),
                  ),
                  if (unread > 0) ...[
                    const SizedBox(height: Space.x2),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: StatusBadge(
                        label: 'Новых ответов врача: $unread',
                        tone: StatusTone.accent,
                        icon: Icons.mark_chat_unread_outlined,
                        dense: true,
                      ),
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: Space.x6),
            _Recent(events: [for (final e in d['recent']! as List) asJson(e)], now: now),
            const SizedBox(height: Space.x6),
            const Text(
              'Приложение не заменяет обращение за медицинской помощью. Если вам стало значительно хуже, '
              'свяжитесь с врачом или позвоните 103 / 112.',
              style: AppType.caption,
            ),
          ],
        );
      },
    );
  }

  static String _cap(String s) => s.isEmpty ? s : s[0].toUpperCase() + s.substring(1);
}

class _QuestionnaireCard extends StatelessWidget {
  const _QuestionnaireCard({required this.schedule, required this.now});

  final Json schedule;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    final status = schedule['due_status']! as String;
    final next = DateTime.parse(schedule['next_due_at']! as String);
    final last = schedule['last_administered_at'] == null
        ? null
        : DateTime.parse(schedule['last_administered_at']! as String);
    final actionable = status != 'upcoming';
    final instrument = Instrument.fromWire(schedule['instrument']! as String);
    return Container(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: Radii.mdAll,
        border: Border.all(color: actionable ? AppColors.accent.withValues(alpha: 0.5) : AppColors.border),
      ),
      padding: const EdgeInsets.all(Space.x4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: Space.x2,
            runSpacing: Space.x1,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text('${schedule['label']}', style: AppType.subsectionTitle),
              dueBadge(status),
            ],
          ),
          const SizedBox(height: 2),
          Text(
            [
              '${schedule['item_count']} вопросов, раз в ${Fmt.days(schedule['interval_days']! as int)}',
              if (last != null) 'последний раз ${Fmt.dayMonth(last)}',
              if (!actionable) 'следующий — ${Fmt.dayMonth(next)}',
            ].join(' · '),
            style: AppType.small,
          ),
          if (actionable) ...[
            const SizedBox(height: Space.x3),
            SizedBox(
              height: 48,
              child: FilledButton(
                onPressed: () => context.push('/patient/questionnaire/${instrument.wire}'),
                child: Text('Заполнить ${instrument.label}'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _RoutingCard extends StatelessWidget {
  const _RoutingCard({required this.routing});

  final Json routing;

  @override
  Widget build(BuildContext context) {
    final t = routing['template'] is Map ? asJson(routing['template']) : null;
    final decision = RouteDecision.fromWire(routing['doctor_decision']! as String);
    return InlineNotice(
      tone: decision == RouteDecision.required ? StatusTone.warn : StatusTone.info,
      icon: Icons.alt_route,
      title: t?['title'] as String? ?? 'Решение врача: ${routeLabel(decision).toLowerCase()}',
      body: t?['body'] as String? ?? 'Подробности сообщит клиника.',
      action: t != null && t['status'] != 'approved'
          ? const Row(children: [DemoTag(label: 'ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ')])
          : null,
    );
  }
}

class _Recent extends StatelessWidget {
  const _Recent({required this.events, required this.now});

  final List<Json> events;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeader(title: 'Недавние действия', level: 2),
        const SizedBox(height: Space.x2),
        if (events.isEmpty)
          const Text('Здесь появятся ваши отметки, опросы и сообщения.', style: AppType.small)
        else
          for (final (i, e) in events.indexed) ...[
            if (i > 0) const Divider(),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: Space.x3),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(e['title']! as String, style: AppType.body),
                  Text(Fmt.relativeMoment(DateTime.parse(e['at']! as String), now), style: AppType.caption),
                ],
              ),
            ),
          ],
      ],
    );
  }
}
