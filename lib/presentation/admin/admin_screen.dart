import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/demo_accounts.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

const _statusLabels = {'open': 'Новая', 'contacted': 'Связались', 'scheduled': 'Записан', 'cancelled': 'Отменена'};

/// Администратор записи (§15): только контакт пациента и срок — без шкал,
/// симптомов, причин алертов и сообщений.
class AdminScreen extends StatelessWidget {
  const AdminScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.sizeOf(context).width < Breakpoints.compact;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: Space.x4,
        title: const Row(
          children: [
            BrandMark(size: 24),
            SizedBox(width: Space.x2),
            Flexible(child: Text('Запись пациентов', overflow: TextOverflow.ellipsis)),
          ],
        ),
        actions: [
          DemoAccountButton(compact: narrow),
          const SizedBox(width: Space.x3),
        ],
      ),
      body: LiveFuture<List<Json>>(
        pollEvery: const Duration(seconds: 30),
        load: () => context.api.bookingTasks(),
        builder: (context, tasks) => SingleChildScrollView(
          padding: EdgeInsets.all(narrow ? Space.x4 : Space.x8),
          child: ContentWidth(
            maxWidth: 900,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const DemoModeStrip(),
                const SizedBox(height: Space.x3),
                Semantics(header: true, child: const Text('Задачи на запись', style: AppType.pageTitle)),
                const Text(
                  'Врач указал срок, до которого нужно связаться с пациентом. Клинические данные здесь не показываются.',
                  style: AppType.bodySecondary,
                ),
                const SizedBox(height: Space.x5),
                if (tasks.isEmpty)
                  const Panel(
                    child: EmptyState(icon: Icons.event_available_outlined, title: 'Задач нет'),
                  )
                else
                  Panel(
                    padding: EdgeInsets.zero,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        for (final (i, t) in tasks.indexed) ...[if (i > 0) const Divider(), _TaskRow(task: t)],
                      ],
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _TaskRow extends StatelessWidget {
  const _TaskRow({required this.task});

  final Json task;

  @override
  Widget build(BuildContext context) {
    final deadline = DateTime.parse(task['deadline']! as String);
    final status = task['status']! as String;
    return Padding(
      padding: const EdgeInsets.all(Space.x4),
      child: Wrap(
        spacing: Space.x4,
        runSpacing: Space.x2,
        alignment: WrapAlignment.spaceBetween,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(task['patient_name']! as String, style: AppType.bodyStrong),
              Text('${task['patient_phone']} · запросил ${task['requested_by']}', style: AppType.small),
              Text('Связаться до ${Fmt.dateTime(deadline)}', style: AppType.small),
            ],
          ),
          PopupMenuButton<String>(
            tooltip: 'Статус задачи',
            initialValue: status,
            onSelected: (s) => unawaited(_update(context, s)),
            itemBuilder: (_) => [
              for (final e in _statusLabels.entries) PopupMenuItem(value: e.key, child: Text(e.value)),
            ],
            child: StatusBadge(
              label: '${_statusLabels[status] ?? status} ▾',
              tone: switch (status) {
                'scheduled' => StatusTone.ok,
                'cancelled' => StatusTone.neutral,
                'contacted' => StatusTone.accent,
                _ => StatusTone.info,
              },
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _update(BuildContext context, String status) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      await context.api.updateBooking(task['id']! as String, status);
    } on Exception catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Не удалось: ${describeError(e)}')));
    }
  }
}
