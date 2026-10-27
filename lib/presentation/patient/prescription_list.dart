import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/prescription_tile.dart';

const _notAPrescription =
    'Это список назначений, а не рецепт. Рецептурные препараты отпускают по рецепту, который выдаёт врач.';

/// Препараты, которые выписал врач. С этим списком пациент может пойти в аптеку.
class PrescriptionList extends StatelessWidget {
  const PrescriptionList({super.key, required this.prescriptions});

  final List<Json> prescriptions;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeader(
          title: 'Мои назначения',
          level: 2,
          trailing: prescriptions.isEmpty
              ? null
              : OutlinedButton.icon(
                  onPressed: () => unawaited(_showForPharmacy(context)),
                  icon: const Icon(Icons.local_pharmacy_outlined, size: 18),
                  label: const Text('Для аптеки'),
                ),
        ),
        const SizedBox(height: Space.x3),
        Panel(
          child: prescriptions.isEmpty
              ? const Text('Врач пока ничего не назначил.', style: AppType.bodySecondary)
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    for (final (i, rx) in prescriptions.indexed) ...[
                      if (i > 0) const Divider(),
                      PrescriptionTile(rx: rx),
                    ],
                  ],
                ),
        ),
        if (prescriptions.isNotEmpty) ...[
          const SizedBox(height: Space.x2),
          const Text(_notAPrescription, style: AppType.caption),
        ],
      ],
    );
  }

  /// Крупный список на весь экран — показать фармацевту с телефона.
  Future<void> _showForPharmacy(BuildContext context) => showDialog<void>(
    context: context,
    builder: (ctx) => Dialog.fullscreen(
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Список для аптеки'),
          leading: IconButton(tooltip: 'Закрыть', icon: const Icon(Icons.close), onPressed: () => Navigator.pop(ctx)),
        ),
        body: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(Space.x5),
            children: [
              Text('Список от ${Fmt.date(DateTime.now())}', style: AppType.bodySecondary),
              const SizedBox(height: Space.x4),
              for (final (i, rx) in prescriptions.indexed) ...[
                if (i > 0) const Divider(height: Space.x8),
                Text('${i + 1}. ${rx['drug']}', style: AppType.pageTitle),
                const SizedBox(height: Space.x1),
                Text(rx['dosage']! as String, style: AppType.question),
                const SizedBox(height: Space.x1),
                Text(rx['regimen']! as String, style: AppType.bodySecondary.copyWith(fontSize: 17)),
                if (rx['duration'] != null)
                  Text(rx['duration']! as String, style: AppType.bodySecondary.copyWith(fontSize: 17)),
              ],
              const SizedBox(height: Space.x8),
              const Text(_notAPrescription, style: AppType.small),
            ],
          ),
        ),
      ),
    ),
  );
}
