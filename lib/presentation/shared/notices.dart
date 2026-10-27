import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/patient/emergency_alert.dart';

/// Тексты для пациента по `patient_action` — только из реестра шаблонов.
class NoticeList extends StatelessWidget {
  const NoticeList({super.key, required this.notices});

  final List<Json> notices;

  @override
  Widget build(BuildContext context) {
    final unique = <String, Json>{};
    for (final n in notices) {
      final t = n['template'];
      final id = t is Map ? t['id'] as String : n['alert_id'] as String;
      unique.putIfAbsent(id, () => n);
    }
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        for (final n in unique.values) ...[NoticeCard(notice: n), const SizedBox(height: Space.x3)],
      ],
    );
  }
}

class NoticeCard extends StatelessWidget {
  const NoticeCard({super.key, required this.notice});

  final Json notice;

  @override
  Widget build(BuildContext context) {
    final action = PatientAction.fromWire(notice['patient_action']! as String);
    final template = notice['template'] is Map ? asJson(notice['template']) : null;
    final tone = switch (action) {
      PatientAction.recommendAmbulance || PatientAction.contactClinicToday => StatusTone.danger,
      PatientAction.contactDoctorSoon => StatusTone.warn,
      _ => StatusTone.info,
    };
    final icon = switch (action) {
      PatientAction.recommendAmbulance => Icons.emergency_outlined,
      PatientAction.contactClinicToday => Icons.call_outlined,
      PatientAction.contactDoctorSoon => Icons.chat_outlined,
      _ => Icons.info_outline,
    };
    final draft = template != null && template['status'] != 'approved';
    final patient = context.services.api.user;
    return Semantics(
      liveRegion: true,
      child: InlineNotice(
        tone: tone,
        icon: icon,
        title: template?['title'] as String? ?? 'Сообщение передано врачу',
        body: template?['body'] as String? ?? 'Ваш врач увидит эту информацию.',
        action: draft || action == PatientAction.recommendAmbulance
            ? Wrap(
                spacing: Space.x3,
                runSpacing: Space.x2,
                crossAxisAlignment: WrapCrossAlignment.center,
                children: [
                  if (action == PatientAction.recommendAmbulance && patient != null)
                    FilledButton.icon(
                      style: FilledButton.styleFrom(backgroundColor: AppColors.dangerFg),
                      onPressed: () => unawaited(
                        showEmergencyAlert(context, api: context.api, patientId: patient.id, notice: notice),
                      ),
                      icon: const Icon(Icons.call, size: 18),
                      label: const Text('Позвонить 112'),
                    ),
                  if (draft)
                    const DemoTag(
                      label: 'ТРЕБУЕТ ПОДТВЕРЖДЕНИЯ',
                      tooltip: 'Текст ожидает утверждения медицинским экспертом',
                    ),
                ],
              )
            : null,
      ),
    );
  }
}

/// Подпись к блоку текстов от системы.
class NoticesHeader extends StatelessWidget {
  const NoticesHeader({super.key});

  @override
  Widget build(BuildContext context) => const Padding(
    padding: EdgeInsets.only(bottom: Space.x2),
    child: Text('Важное', style: AppType.subsectionTitle),
  );
}

/// Тексты по итогам отправки (кроме экстренных — их показывает EmergencyAlertHost).
Future<void> showNoticesSheet(BuildContext context, List<Json> notices) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  builder: (ctx) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(Space.x4, 0, Space.x4, Space.x4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          NoticeList(notices: notices),
          FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('Понятно')),
        ],
      ),
    ),
  ),
);
