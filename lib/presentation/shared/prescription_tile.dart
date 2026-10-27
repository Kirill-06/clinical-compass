import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/json.dart';

/// Одно назначение: препарат, дозировка, как принимать, срок и кто выписал.
/// Общий вид для карточки врача и списка пациента.
class PrescriptionTile extends StatelessWidget {
  const PrescriptionTile({super.key, required this.rx, this.trailing});

  final Json rx;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final cancelled = rx['cancelled_at'] != null;
    final created = DateTime.parse(rx['created_at']! as String);
    final duration = rx['duration'] as String?;
    final note = rx['note'] as String?;
    final doctor = rx['doctor'] as String?;
    final muted = cancelled ? AppColors.textMuted : null;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Space.x3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(top: 2),
            child: Icon(Icons.medication_outlined, size: 20, color: muted ?? AppColors.accent),
          ),
          const SizedBox(width: Space.x3),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${rx['drug']} · ${rx['dosage']}',
                  style: AppType.bodyStrong.copyWith(
                    color: muted,
                    decoration: cancelled ? TextDecoration.lineThrough : null,
                  ),
                ),
                const SizedBox(height: 2),
                Text(rx['regimen']! as String, style: AppType.body.copyWith(color: muted)),
                if (duration != null) Text(duration, style: AppType.small.copyWith(color: muted)),
                if (note != null) ...[
                  const SizedBox(height: Space.x1),
                  Text(note, style: AppType.small.copyWith(color: muted ?? AppColors.textSecondary)),
                ],
                const SizedBox(height: Space.x1),
                Text(
                  [
                    ?doctor,
                    'назначено ${Fmt.date(created)}',
                    if (cancelled) 'отменено ${Fmt.date(DateTime.parse(rx['cancelled_at']! as String))}',
                  ].join(' · '),
                  style: AppType.caption,
                ),
              ],
            ),
          ),
          ?trailing,
        ],
      ),
    );
  }
}
