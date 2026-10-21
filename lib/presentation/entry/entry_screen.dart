import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/demo_accounts.dart';

/// Стартовый экран: демо-вход по выбору аккаунта (без пароля).
class EntryScreen extends StatelessWidget {
  const EntryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.sizeOf(context).width < Breakpoints.compact;
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.symmetric(horizontal: narrow ? Space.x4 : Space.x8, vertical: Space.x8),
          child: ContentWidth(
            maxWidth: 720,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                Row(
                  children: [
                    const BrandMark(size: 36),
                    const SizedBox(width: Space.x3),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Semantics(header: true, child: const Text('Клинический компас', style: AppType.pageTitle)),
                          const Text('Сопровождение пациента между визитами · v0.2', style: AppType.bodySecondary),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: Space.x6),
                const InlineNotice(
                  tone: StatusTone.neutral,
                  icon: Icons.science_outlined,
                  title: 'Демо-вход без пароля',
                  body:
                      'Все люди вымышлены. Выбор аккаунта — демонстрационный вход: сервер выдаёт сессию, '
                      'и дальше доступ к данным проверяет backend по роли и закреплению пациента за врачом.',
                ),
                const SizedBox(height: Space.x6),
                Panel(
                  padding: EdgeInsets.zero,
                  child: AccountList(onPick: (id) => unawaited(demoSignIn(context, id))),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
