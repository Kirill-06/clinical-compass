import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:clinical_compass/presentation/patient/support_note.dart';

void main() {
  testWidgets('Подсказку можно скрыть, и выбор сохраняется', (tester) async {
    SharedPreferences.setMockInitialValues({});
    Widget page() => const MaterialApp(home: Scaffold(body: SupportNote()));

    await tester.pumpWidget(page());
    await tester.pumpAndSettle();
    expect(find.textContaining('Рады видеть вас'), findsOneWidget);
    await tester.tap(find.byTooltip('Скрыть подсказку'));
    await tester.pumpAndSettle();
    expect(find.textContaining('Рады видеть вас'), findsNothing);

    await tester.pumpWidget(const SizedBox.shrink());
    await tester.pumpWidget(page());
    await tester.pumpAndSettle();
    expect(find.textContaining('Рады видеть вас'), findsNothing);
  });
}
