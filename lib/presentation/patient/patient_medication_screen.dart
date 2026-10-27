import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/patient/intake_slots.dart';
import 'package:clinical_compass/presentation/patient/patient_shell.dart';
import 'package:clinical_compass/presentation/patient/prescription_list.dart';
import 'package:clinical_compass/presentation/shared/adherence_view.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

class PatientMedicationScreen extends StatelessWidget {
  const PatientMedicationScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.user;
    return LiveFuture<(Json, Json)>(
      reloadKey: user.id,
      load: () async {
        final api = context.api;
        final (d, h) = await (api.dashboard(user.id), api.history(user.id)).wait;
        return (d, h);
      },
      builder: (context, data) {
        final (d, h) = data;
        final plan = d['plan'] is Map ? asJson(d['plan']) : null;
        final adherence = h['adherence'] is Map ? asJson(h['adherence']) : null;
        final prescriptions = [for (final p in h['prescriptions'] as List? ?? const []) asJson(p)];
        return PatientPage(
          children: [
            Semantics(header: true, child: const Text('Приём препарата', style: AppType.pageTitle)),
            const SizedBox(height: Space.x2),
            const Text(
              'Вы отмечаете только факт приёма. Схему лечения назначает и меняет врач.',
              style: AppType.bodySecondary,
            ),
            const SizedBox(height: Space.x5),
            PrescriptionList(prescriptions: prescriptions),
            const SizedBox(height: Space.x6),
            if (plan == null)
              const Panel(child: Text('Врач пока не назначил план приёма.', style: AppType.bodySecondary))
            else ...[
              TodayIntakePanel(patientId: user.id, plan: plan, today: asJson(d['today'])),
              const SizedBox(height: Space.x6),
              if (adherence != null) ...[
                const SectionHeader(title: 'За последние 14 дней', level: 2),
                const SizedBox(height: Space.x3),
                Panel(child: AdherenceSummaryView(data: adherence)),
                const SizedBox(height: Space.x4),
                Panel(child: SlotGrid(slots: [for (final s in adherence['slots'] as List? ?? const []) asJson(s)])),
              ],
            ],
          ],
        );
      },
    );
  }
}
