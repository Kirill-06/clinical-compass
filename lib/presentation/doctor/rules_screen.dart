import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

/// Активная конфигурация правил (alert_rules_v0.2.yaml) — только чтение.
/// Правила меняются новой версией конфига, а не в интерфейсе.
class RulesScreen extends StatelessWidget {
  const RulesScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return LiveFuture<Json>(
      load: () => context.api.rulesSummary(),
      builder: (context, r) {
        final rules = [for (final x in r['rules']! as List) asJson(x)];
        final days = asJson(r['questionnaire_default_days']);
        return SingleChildScrollView(
          padding: doctorPagePadding(context),
          child: ContentWidth(
            maxWidth: 1100,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const DemoModeStrip(),
                const SizedBox(height: Space.x3),
                PageHeader(
                  title: 'Правила',
                  subtitle:
                      'Версия правил ${r['rule_version']} (${r['status']}), схема ${r['schema_version']}, '
                      'шаблоны ${r['templates_version']}. Изменяются только новой версией конфига.',
                ),
                const SizedBox(height: Space.x5),
                Wrap(
                  spacing: Space.x10,
                  runSpacing: Space.x3,
                  children: [
                    KeyValue(label: 'GAD-7 по умолчанию', value: 'раз в ${days['GAD7']} дней'),
                    KeyValue(label: 'PHQ-9 по умолчанию', value: 'раз в ${days['PHQ9']} дней'),
                    KeyValue(
                      label: 'Интервал меняет врач',
                      value: r['doctor_configurable_schedule'] == true ? 'да' : 'нет',
                    ),
                    KeyValue(
                      label: 'Push на личный телефон',
                      value: r['personal_push_default'] == true ? 'да' : 'нет — только рабочая очередь',
                    ),
                    KeyValue(
                      label: 'Срочные закреплены',
                      value: r['urgent_pinned_until_acknowledged'] == true ? 'до принятия в работу' : 'нет',
                    ),
                  ],
                ),
                const SizedBox(height: Space.x5),
                const InlineNotice(
                  tone: StatusTone.neutral,
                  icon: Icons.info_outline,
                  body:
                      'doctor_priority управляет порядком в очереди врача, patient_action — текстом пациенту; '
                      'это независимые поля. Система не вызывает скорую и не принимает решений о терапии.',
                ),
                const SizedBox(height: Space.x5),
                Panel(
                  padding: EdgeInsets.zero,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      for (final (i, x) in rules.indexed) ...[
                        if (i > 0) const Divider(),
                        Padding(
                          padding: const EdgeInsets.all(Space.x4),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Wrap(
                                spacing: Space.x2,
                                runSpacing: Space.x1,
                                crossAxisAlignment: WrapCrossAlignment.center,
                                children: [
                                  Text(
                                    x['id']! as String,
                                    style: AppType.numericSmall.copyWith(
                                      fontWeight: FontWeight.w600,
                                      color: AppColors.text,
                                    ),
                                  ),
                                  priorityBadge(DoctorPriority.fromWire(x['doctor_priority']! as String)),
                                  if (x['medical_urgency_classified'] == false)
                                    const StatusBadge(
                                      label: 'Срочность не классифицируется',
                                      tone: StatusTone.neutral,
                                      dense: true,
                                    ),
                                ],
                              ),
                              const SizedBox(height: 2),
                              Text(x['title']! as String, style: AppType.body),
                              Text(
                                patientActionLabel(PatientAction.fromWire(x['patient_action']! as String)),
                                style: AppType.small,
                              ),
                              Text(
                                'Источник: ${x['source']}'
                                '${x['message_template_id'] == null ? '' : ' · шаблон ${x['message_template_id']} (${x['template_status'] ?? 'нет в реестре'})'}',
                                style: AppType.caption,
                              ),
                            ],
                          ),
                        ),
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
}
