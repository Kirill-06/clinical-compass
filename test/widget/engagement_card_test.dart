import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clinical_compass/presentation/patient/engagement_card.dart';

void main() {
  testWidgets('Показывает дни с записями без оценки здоровья', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: EngagementCard(
            progress: {
              'days_with_entries': 2,
              'days': [
                for (var day = 1; day <= 7; day++) {'date': '2026-11-0$day', 'has_entry': day <= 2},
              ],
              'achievement': {'id': 'first_entry', 'title': 'Первая запись'},
              'explanation': 'Считаем только дни с записями, а не состояние здоровья или соблюдение лечения.',
            },
          ),
        ),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.text('Мой прогресс'), findsOneWidget);
    expect(find.text('Дни с записями: 2 из 7'), findsOneWidget);
    expect(find.text('Первая запись'), findsOneWidget);
    expect(find.byType(LinearProgressIndicator), findsOneWidget);
    expect(find.textContaining('состояние здоровья'), findsOneWidget);
  });

  testWidgets('Нет награды, когда записей нет', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: EngagementCard(progress: {'days_with_entries': 0, 'days': [], 'achievement': null, 'explanation': ''}),
        ),
      ),
    );
    expect(find.text('Дни с записями: 0 из 7'), findsOneWidget);
    expect(find.byIcon(Icons.stars_outlined), findsNothing);
  });
}
