import 'package:flutter/material.dart' hide Durations;

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/json.dart';

/// Вовлечение = регулярность ведения дневника, НЕ состояние здоровья и НЕ adherence.
/// Никаких очков за принятие лекарства или «хорошие» ответы опросника.
class EngagementCard extends StatelessWidget {
  const EngagementCard({super.key, required this.progress});

  final Json progress;

  @override
  Widget build(BuildContext context) {
    final count = progress['days_with_entries'] as int? ?? 0;
    final days = [for (final item in progress['days'] as List? ?? const []) asJson(item)];
    final achievement = progress['achievement'] is Map ? asJson(progress['achievement']) : null;
    final explanation = progress['explanation'] as String? ?? '';
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Icon(Icons.auto_awesome_outlined, color: AppColors.accent, size: 23),
              const SizedBox(width: Space.x3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('Мой прогресс', style: AppType.subsectionTitle),
                    const SizedBox(height: Space.x1),
                    AnimatedSwitcher(
                      duration: MediaQuery.of(context).disableAnimations ? Duration.zero : Durations.normal,
                      child: Text('Дни с записями: $count из 7', key: ValueKey(count), style: AppType.body),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: Space.x3),
          Semantics(
            label: 'Дневник заполнен в $count из последних семи дней',
            child: LinearProgressIndicator(
              value: count / 7,
              minHeight: 7,
              borderRadius: Radii.smAll,
              color: AppColors.accent,
              backgroundColor: AppColors.surfaceSunken,
            ),
          ),
          const SizedBox(height: Space.x3),
          if (days.length == 7)
            Row(
              children: [
                for (final (i, day) in days.indexed)
                  Expanded(
                    child: Padding(
                      padding: EdgeInsets.only(right: i == 6 ? 0 : Space.x1),
                      child: _DayEntry(day: day),
                    ),
                  ),
              ],
            ),
          if (achievement != null) ...[
            const SizedBox(height: Space.x3),
            Row(
              children: [
                const Icon(Icons.stars_outlined, size: 18, color: AppColors.accent),
                const SizedBox(width: Space.x2),
                Flexible(child: Text(achievement['title'] as String? ?? '', style: AppType.smallStrong)),
              ],
            ),
          ],
          const SizedBox(height: Space.x2),
          Text(explanation, style: AppType.caption),
        ],
      ),
    );
  }
}

class _DayEntry extends StatelessWidget {
  const _DayEntry({required this.day});

  final Json day;

  @override
  Widget build(BuildContext context) {
    final date = DateTime.parse(day['date'] as String);
    final hasEntry = day['has_entry'] == true;
    const labels = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
    final label = labels[date.weekday - 1];
    return Semantics(
      label: '$label, ${date.day}.${date.month}: ${hasEntry ? 'есть запись' : 'нет записи'}',
      child: Column(
        children: [
          Container(
            height: 40,
            decoration: BoxDecoration(
              color: hasEntry ? AppColors.accentSoft : AppColors.surfaceSubtle,
              borderRadius: Radii.smAll,
            ),
            alignment: Alignment.center,
            child: Icon(
              hasEntry ? Icons.check_rounded : Icons.remove_rounded,
              size: 18,
              color: hasEntry ? AppColors.accent : AppColors.textMuted,
            ),
          ),
          const SizedBox(height: Space.x1),
          Text(label, style: AppType.caption),
        ],
      ),
    );
  }
}
