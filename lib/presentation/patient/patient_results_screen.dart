import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/patient/patient_shell.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/response_detail.dart';
import 'package:clinical_compass/presentation/shared/score_chart.dart';

/// Собственные результаты пациента по обеим шкалам. Сервер отдаёт только
/// данные владельца сессии.
class PatientResultsScreen extends StatelessWidget {
  const PatientResultsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.user;
    return LiveFuture<Json>(
      reloadKey: user.id,
      load: () => context.api.history(user.id),
      builder: (context, h) {
        final responses = [for (final r in h['questionnaires']! as List) asJson(r)];
        return PatientPage(
          children: [
            Semantics(header: true, child: const Text('Мои результаты', style: AppType.pageTitle)),
            const SizedBox(height: Space.x2),
            const Text(
              'Результат скрининга не является диагнозом. Оценку проводит врач.',
              style: AppType.bodySecondary,
            ),
            const SizedBox(height: Space.x5),
            for (final i in Instrument.values) ...[
              _InstrumentBlock(instrument: i, responses: responses.where((r) => r['instrument'] == i.wire).toList()),
              const SizedBox(height: Space.x6),
            ],
          ],
        );
      },
    );
  }
}

class _InstrumentBlock extends StatelessWidget {
  const _InstrumentBlock({required this.instrument, required this.responses});

  final Instrument instrument;
  final List<Json> responses;

  @override
  Widget build(BuildContext context) {
    final def = context.meta.instrument(instrument);
    final points = pointsFrom(responses, instrument);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(title: def.title, subtitle: '0–${def.maxScore} баллов', level: 2),
        const SizedBox(height: Space.x3),
        if (responses.isEmpty)
          const Panel(
            child: EmptyState(compact: true, icon: Icons.insights_outlined, title: 'Результатов пока нет'),
          )
        else ...[
          if (points.length > 1) ...[
            Panel(
              padding: const EdgeInsets.fromLTRB(Space.x3, Space.x4, Space.x3, Space.x2),
              child: ScoreChart(points: points, definition: def, height: 200),
            ),
            const SizedBox(height: Space.x3),
          ],
          Panel(
            padding: EdgeInsets.zero,
            child: Column(
              children: [
                for (final (i, r) in responses.indexed) ...[
                  if (i > 0) const Divider(),
                  InkWell(
                    onTap: () => unawaited(showResponseDialog(context, r)),
                    child: Padding(
                      padding: const EdgeInsets.all(Space.x4),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              Fmt.dateLong(DateTime.parse(r['administered_at']! as String)),
                              style: AppType.bodyStrong,
                            ),
                          ),
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text('${r['total_score']} из ${def.maxScore}', style: AppType.numeric),
                              Text(r['severity_label'] as String? ?? '', style: AppType.small),
                            ],
                          ),
                          const SizedBox(width: Space.x2),
                          const Icon(Icons.chevron_right, color: AppColors.textMuted),
                        ],
                      ),
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ],
    );
  }
}
