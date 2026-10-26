import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/doctor/export_button.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

/// Нежелательные явления по пациентам врача. Эффекты вне листка-вкладыша — отдельно:
/// это кандидаты в новые свойства препарата, о которых стоит сообщить.
class AdverseEventsScreen extends StatelessWidget {
  const AdverseEventsScreen({super.key});

  @override
  Widget build(BuildContext context) => LiveFuture<Json>(
    load: () => context.api.adverseEvents(),
    loadingLabel: 'Собираем сводку…',
    builder: (context, data) {
      final effects = [for (final e in data['effects']! as List) asJson(e)];
      final outside = [for (final e in data['outside_leaflet']! as List) asJson(e)];
      final reports = effects.fold<int>(0, (sum, e) => sum + (e['reports']! as int));
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
                title: 'Побочные эффекты',
                subtitle:
                    'Что пациенты сообщают о нежелательных явлениях — формой самочувствия и в чате. '
                    'Эффекты вне листка-вкладыша могут оказаться новыми свойствами препарата.',
                actions: [ExportPatientsButton()],
              ),
              const SizedBox(height: Space.x5),
              Wrap(
                spacing: Space.x8,
                runSpacing: Space.x3,
                children: [
                  KeyValue(label: 'Пациентов', value: '${data['patients_total']}'),
                  KeyValue(label: 'Сообщений о побочных эффектах', value: '$reports'),
                  KeyValue(label: 'Вне листка-вкладыша', value: '${outside.length}'),
                  KeyValue(
                    label: 'Пропусков приёма из-за эффектов',
                    value: '${data['missed_doses_due_to_adverse_event']}',
                  ),
                ],
              ),
              const SizedBox(height: Space.x6),
              SectionHeader(
                title: 'Вне листка-вкладыша: ${outside.length}',
                subtitle: 'Описания пациентов. Проверьте и при подтверждении сообщите в фармаконадзор.',
              ),
              const SizedBox(height: Space.x3),
              if (outside.isEmpty)
                const Panel(child: Text('Таких сообщений нет.', style: AppType.bodySecondary))
              else
                Panel(
                  padding: EdgeInsets.zero,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (final (i, e) in outside.indexed) ...[if (i > 0) const Divider(), _NewEffect(effect: e)],
                    ],
                  ),
                ),
              const SizedBox(height: Space.x6),
              const SectionHeader(title: 'По эффектам', subtitle: 'Сколько раз и у скольких пациентов'),
              const SizedBox(height: Space.x3),
              if (effects.isEmpty)
                const Panel(child: Text('Пациенты пока не сообщали о побочных эффектах.', style: AppType.bodySecondary))
              else
                Panel(
                  padding: EdgeInsets.zero,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (final (i, e) in effects.indexed) ...[
                        if (i > 0) const Divider(),
                        _EffectRow(effect: e, maxReports: effects.first['reports']! as int),
                      ],
                    ],
                  ),
                ),
            ],
          ),
        ),
      );
    },
  );
}

class _NewEffect extends StatelessWidget {
  const _NewEffect({required this.effect});

  final Json effect;

  @override
  Widget build(BuildContext context) {
    final patient = asJson(effect['patient']);
    final at = effect['reported_at'] as String?;
    return InkWell(
      onTap: () => context.go('/doctor/patients/${patient['id']}'),
      child: Padding(
        padding: const EdgeInsets.all(Space.x4),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              spacing: Space.x2,
              runSpacing: Space.x1,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                Text('${patient['display_id']} · ${patient['birth_year']} г. р.', style: AppType.bodyStrong),
                if (at != null) Text(Fmt.dateTime(DateTime.parse(at)), style: AppType.caption),
                if (effect['affects_daily_life'] == 'yes')
                  const StatusBadge(label: 'Мешает обычным делам', tone: StatusTone.warn, dense: true),
              ],
            ),
            const SizedBox(height: Space.x1),
            Text('«${effect['description'] ?? 'без описания'}»', style: AppType.body),
          ],
        ),
      ),
    );
  }
}

class _EffectRow extends StatelessWidget {
  const _EffectRow({required this.effect, required this.maxReports});

  final Json effect;
  final int maxReports;

  @override
  Widget build(BuildContext context) {
    final reports = effect['reports']! as int;
    final inLeaflet = effect['in_leaflet'] == true;
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: Space.x4, vertical: Space.x3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: Space.x2,
            runSpacing: Space.x1,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(effect['label']! as String, style: AppType.bodyStrong),
              StatusBadge(
                label: inLeaflet ? 'в листке-вкладыше' : 'вне листка-вкладыша',
                tone: inLeaflet ? StatusTone.neutral : StatusTone.warn,
                dense: true,
              ),
            ],
          ),
          const SizedBox(height: Space.x2),
          Row(
            children: [
              Expanded(
                child: ClipRRect(
                  borderRadius: Radii.smAll,
                  child: LinearProgressIndicator(
                    value: maxReports == 0 ? 0 : reports / maxReports,
                    minHeight: 8,
                    color: inLeaflet ? AppColors.accent : AppColors.warnFg,
                    backgroundColor: AppColors.surfaceSubtle,
                  ),
                ),
              ),
              const SizedBox(width: Space.x3),
              Text(
                'сообщений: $reports · пациентов: ${effect['patients']} · '
                'мешает жизни: ${effect['affects_daily_life']}',
                style: AppType.small,
              ),
            ],
          ),
        ],
      ),
    );
  }
}
