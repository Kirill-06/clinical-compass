import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/doctor/alert_card.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

/// Рабочая очередь врача (§13): алерты появляются сразу после rule engine,
/// срочные закреплены сверху до принятия; личные push не используются.
class QueueScreen extends StatefulWidget {
  const QueueScreen({super.key});

  @override
  State<QueueScreen> createState() => _QueueScreenState();
}

class _QueueScreenState extends State<QueueScreen> {
  DoctorPriority? _priority;
  bool _withResolved = false;

  @override
  Widget build(BuildContext context) {
    final user = context.user;
    return LiveFuture<List<Json>>(
      reloadKey: '${user.id}|$_withResolved',
      pollEvery: const Duration(seconds: 15),
      loadingLabel: 'Загружаем очередь…',
      load: () => context.api.doctorQueue(includeResolved: _withResolved),
      builder: (context, all) {
        final counts = {
          for (final p in DoctorPriority.values)
            p: all.where((a) => asJson(a['alert'])['doctor_priority'] == p.wire).length,
        };
        final visible = _priority == null
            ? all
            : all.where((a) => asJson(a['alert'])['doctor_priority'] == _priority!.wire).toList();
        final now = context.services.clock.now();
        return SingleChildScrollView(
          padding: doctorPagePadding(context),
          child: ContentWidth(
            maxWidth: 1100,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const DemoModeStrip(),
                const SizedBox(height: Space.x3),
                const PageHeader(
                  title: 'Очередь',
                  subtitle:
                      'События по вашим пациентам после правил v0.2. Приоритет определяет порядок в очереди, '
                      'а не прерывание приёма. Обновляется автоматически.',
                ),
                const SizedBox(height: Space.x5),
                Wrap(
                  spacing: Space.x3,
                  runSpacing: Space.x3,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    FilterSegment<DoctorPriority?>(
                      semanticLabel: 'Приоритет',
                      options: const [
                        null,
                        DoctorPriority.urgent,
                        DoctorPriority.high,
                        DoctorPriority.normal,
                        DoctorPriority.info,
                      ],
                      value: _priority,
                      onChanged: (p) => setState(() => _priority = p),
                      labelOf: (p) => p == null ? 'Все' : priorityLabel(p),
                      countOf: (p) => p == null ? all.length : counts[p],
                    ),
                    FilterChip(
                      label: const Text('Показать закрытые'),
                      selected: _withResolved,
                      onSelected: (v) => setState(() => _withResolved = v),
                    ),
                  ],
                ),
                const SizedBox(height: Space.x4),
                if (visible.isEmpty)
                  const Panel(
                    child: EmptyState(
                      icon: Icons.inbox_outlined,
                      title: 'В очереди нет событий',
                      message: 'Когда данные пациента совпадут с правилом, событие появится здесь сразу.',
                    ),
                  )
                else
                  DecoratedBox(
                    decoration: BoxDecoration(
                      borderRadius: Radii.mdAll,
                      border: Border.all(color: AppColors.border),
                      color: AppColors.surface,
                    ),
                    child: ClipRRect(
                      borderRadius: Radii.mdAll,
                      child: Column(
                        children: [
                          for (final (i, a) in visible.indexed) ...[
                            if (i > 0) const Divider(),
                            AlertCard(key: ValueKey(asJson(a['alert'])['id']), view: a, now: now),
                          ],
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: Space.x3),
                const Text(
                  'Срочные события закреплены сверху, пока врач не примет их в работу. Далее — по приоритету, '
                  'внутри приоритета — по времени поступления.',
                  style: AppType.caption,
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}
