import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';

/// Сводка приверженности: доля принятых доз, пропуски с причинами и дни без
/// отметки — по отдельности (`unknown != missed`).
class AdherenceSummaryView extends StatelessWidget {
  const AdherenceSummaryView({super.key, required this.data, this.title});

  final Json data;
  final String? title;

  @override
  Widget build(BuildContext context) {
    final reasons = asJson(data['missed_reasons'] ?? const <String, Object?>{});
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (title != null) Text(title!, style: AppType.caption),
        Wrap(
          spacing: Space.x8,
          runSpacing: Space.x3,
          children: [
            KeyValue(label: 'Доля принятых доз', value: percent(data['adherence'] as num?)),
            KeyValue(label: 'Принято', value: '${data['taken']} из ${data['scheduled']}'),
            KeyValue(label: 'Пропущено', value: '${data['missed']}'),
            KeyValue(label: 'Без отметки', value: '${data['unknown']}'),
            KeyValue(label: 'Пропусков подряд', value: '${data['consecutive_missed']}'),
          ],
        ),
        if (reasons.isNotEmpty) ...[
          const SizedBox(height: Space.x3),
          Text('Причины пропусков', style: AppType.caption),
          const SizedBox(height: 2),
          Wrap(
            spacing: Space.x2,
            runSpacing: Space.x1,
            children: [
              for (final e in reasons.entries)
                StatusBadge(
                  label: '${context.meta.missedReason(MissedReason.fromWire(e.key))}: ${e.value}',
                  tone: e.key == 'adverse_event' || e.key == 'decided_to_stop' ? StatusTone.warn : StatusTone.neutral,
                  dense: true,
                ),
            ],
          ),
        ],
      ],
    );
  }
}

/// Сетка доз по дням: строка — день, ячейки — утро/вечер с глифами.
class SlotGrid extends StatelessWidget {
  const SlotGrid({super.key, required this.slots, this.now});

  final List<Json> slots;
  final DateTime? now;

  @override
  Widget build(BuildContext context) {
    final byDate = <String, Map<String, Json>>{};
    for (final s in slots) {
      (byDate[s['date']! as String] ??= {})[s['slot']! as String] = s;
    }
    final dates = byDate.keys.toList()..sort((a, b) => b.compareTo(a));
    return Column(
      children: [
        for (final (i, d) in dates.indexed) ...[
          if (i > 0) const Divider(),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: Space.x2),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  width: 96,
                  child: Text(
                    '${Fmt.dateShort(DateTime.parse(d))}, ${Fmt.weekdayShort(DateTime.parse(d))}',
                    style: AppType.small,
                  ),
                ),
                Expanded(
                  child: Wrap(
                    spacing: Space.x3,
                    runSpacing: Space.x1,
                    children: [
                      for (final slot in IntakeSlot.values)
                        if (byDate[d]![slot.wire] case final s?) _SlotChip(slot: slot, data: s),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }
}

class _SlotChip extends StatelessWidget {
  const _SlotChip({required this.slot, required this.data});

  final IntakeSlot slot;
  final Json data;

  @override
  Widget build(BuildContext context) {
    final status = IntakeStatus.fromWire(data['status']! as String);
    final (tone, icon, label) = intakeVisual(status);
    final reason = data['missed_reason'] == null ? null : MissedReason.fromWire(data['missed_reason']! as String);
    return StatusBadge(
      label:
          '${context.meta.slot(slot)}: ${label.toLowerCase()}${reason == null ? '' : ' — ${context.meta.missedReason(reason).toLowerCase()}'}',
      tone: tone,
      icon: icon,
      dense: true,
    );
  }
}
