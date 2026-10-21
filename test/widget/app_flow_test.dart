import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/presentation/shared/demo_accounts.dart';

import '../support/backend.dart';

Future<void> tapText(WidgetTester tester, String text) async {
  final f = find.text(text).last;
  await tester.ensureVisible(f);
  await tester.pump();
  await tester.tap(f);
  await settle(tester);
}

Future<void> switchTo(WidgetTester tester, String name) async {
  await tester.tap(find.byType(DemoAccountButton).first);
  await settle(tester);
  await tapText(tester, name);
}

void main() {
  useRealBackend();

  testWidgets('entry screen lists demo accounts from the server', (tester) async {
    await pumpApp(tester);
    expect(find.text('Демо-вход без пароля'), findsOneWidget);
    expect(find.text('Миронова Анна Сергеевна'), findsOneWidget);
    expect(find.text('Кузнецова Мария Петровна'), findsOneWidget);
    await unmount(tester);
  });

  testWidgets('doctor queue: urgent safety events are pinned first', (tester) async {
    await pumpApp(tester);
    await tapText(tester, 'Миронова Анна Сергеевна');
    expect(find.text('Очередь'), findsWidgets);
    expect(find.text('Закреплено до принятия'), findsWidgets);
    expect(find.text('Сигнал о мыслях о смерти или самоповреждении'), findsOneWidget);
    await tester.tap(find.text('Почему?').first);
    await settle(tester);
    expect(find.textContaining('Правило R_SELF_HARM'), findsOneWidget);
    await unmount(tester);
  });

  testWidgets('doctor B does not see doctor A patients', (tester) async {
    await pumpApp(tester);
    await tapText(tester, 'Ланской Олег Викторович');
    await tapText(tester, 'Пациенты');
    expect(find.text('Лапина Дарья Олеговна'), findsOneWidget);
    expect(find.text('Корнилова Елена Андреевна'), findsNothing);
    await unmount(tester);
  });

  testWidgets('patient GAD-7 worsening reaches the doctor queue', (tester) async {
    await pumpApp(tester, size: const Size(390, 844));
    await tapText(tester, 'Корнилова Елена Андреевна');
    expect(find.text('Здравствуйте, Елена'), findsOneWidget);

    await tapText(tester, 'Заполнить GAD-7');
    await tapText(tester, 'Начать');
    await tapText(tester, 'Далее');
    expect(find.text('Выберите один вариант ответа'), findsOneWidget);
    for (var i = 1; i <= 7; i++) {
      await tapText(tester, 'Почти каждый день');
      await tapText(tester, i == 7 ? 'Проверить ответы' : 'Далее');
    }
    expect(find.text('Проверьте ответы'), findsOneWidget);
    await tapText(tester, 'Отправить врачу');
    expect(find.text('Ответы отправлены врачу'), findsOneWidget);
    expect(find.text('Результат передан врачу'), findsOneWidget);
    expect(find.text('Результат скрининга не является диагнозом. Оценку проводит врач.'), findsOneWidget);
    await tapText(tester, 'На главную');

    tester.view.physicalSize = const Size(1440, 900);
    await settle(tester);
    await switchTo(tester, 'Миронова Анна Сергеевна');
    await tapText(tester, 'Обычный');
    expect(find.text('Корнилова Елена Андреевна · P-1001'), findsOneWidget);
    expect(find.text('GAD-7: рост на 4 и более балла'), findsWidgets);
    await unmount(tester);
  });

  testWidgets('missed dose with a reason shows the approved-template notice', (tester) async {
    await pumpApp(tester, size: const Size(390, 844));
    await tapText(tester, 'Корнилова Елена Андреевна');
    await tapText(tester, 'Пропустил');
    expect(find.text('Почему приём пропущен?'), findsOneWidget);
    await tapText(tester, 'Решил(а) прекратить приём');
    expect(find.text('Обсудите решение с врачом'), findsWidgets);
    await tapText(tester, 'Понятно');
    await unmount(tester);
  });

  testWidgets('out-of-scope complaint gets the neutral text only', (tester) async {
    await pumpApp(tester, size: const Size(390, 844));
    await tapText(tester, 'Корнилова Елена Андреевна');
    await tapText(tester, 'Отметить самочувствие');
    await tapText(tester, 'Другое — опишу сам(а)');
    await tester.enterText(find.byType(TextField).first, 'Звенит в левом ухе');
    await tapText(tester, 'Отправить врачу');
    expect(find.text('Сообщение сохранено'), findsOneWidget);
    expect(find.textContaining('вне области оценки данного инструмента'), findsOneWidget);
    await unmount(tester);
  });

  group('layouts without overflow', () {
    const sizes = [Size(320, 640), Size(390, 844), Size(768, 1024), Size(1024, 768), Size(1440, 900)];
    for (final size in sizes) {
      testWidgets('patient home at ${size.width.toInt()}', (tester) async {
        await pumpApp(tester, size: size);
        await tapText(tester, 'Соловьёва Ирина Павловна');
        expect(find.text('Здравствуйте, Ирина'), findsOneWidget);
        await unmount(tester);
      });

      testWidgets('doctor queue, patients and card at ${size.width.toInt()}', (tester) async {
        await pumpApp(tester, size: size);
        await tapText(tester, 'Миронова Анна Сергеевна');
        expect(find.text('Очередь'), findsWidgets);
        final router = GoRouter.of(tester.element(find.byType(Scaffold).first));
        router.go('/doctor/patients');
        await settle(tester);
        expect(find.text('Соловьёва Ирина Павловна'), findsOneWidget);
        router.go('/doctor/patients/p_a3');
        await settle(tester);
        expect(find.text('Шкалы и динамика'), findsOneWidget);
        router.go('/doctor/rules');
        await settle(tester);
        expect(find.text('R_OUT_OF_SCOPE'), findsOneWidget);
        await unmount(tester);
      });
    }

    testWidgets('patient home and questionnaire with 2x text at 320', (tester) async {
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await pumpApp(tester, size: const Size(320, 640));
      await tapText(tester, 'Корнилова Елена Андреевна');
      await tapText(tester, 'Заполнить PHQ-9');
      await tapText(tester, 'Начать');
      expect(find.text('Вопрос 1 из 9'), findsOneWidget);
      await unmount(tester);
    });
  });
}
