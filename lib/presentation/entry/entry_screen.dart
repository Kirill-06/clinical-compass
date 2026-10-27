import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/demo_accounts.dart';

/// Стартовый экран: что делает сервис и демо-вход по выбору аккаунта (без пароля).
class EntryScreen extends StatelessWidget {
  const EntryScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final narrow = width < Breakpoints.compact;
    final twoColumns = width >= 1024;
    const header = _Header();
    const about = _About();
    final accounts = Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const InlineNotice(
          tone: StatusTone.neutral,
          icon: Icons.science_outlined,
          title: 'Демо-вход без пароля',
          body:
              'Все люди вымышлены. Выберите, под кем войти. Врач видит только своих пациентов, '
              'администратор — только задачи на запись.',
        ),
        const SizedBox(height: Space.x4),
        Panel(
          padding: EdgeInsets.zero,
          child: AccountList(onPick: (id) => unawaited(demoSignIn(context, id))),
        ),
      ],
    );
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: EdgeInsets.symmetric(horizontal: narrow ? Space.x4 : Space.x8, vertical: Space.x8),
          child: ContentWidth(
            maxWidth: twoColumns ? 1180 : 720,
            child: twoColumns
                ? Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Expanded(
                        flex: 5,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.stretch,
                          children: [
                            header,
                            SizedBox(height: Space.x6),
                            about,
                          ],
                        ),
                      ),
                      const SizedBox(width: Space.x8),
                      Expanded(flex: 6, child: accounts),
                    ],
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    // На телефоне сначала вход, описание сервиса — ниже.
                    children: [
                      header,
                      const SizedBox(height: Space.x6),
                      accounts,
                      const SizedBox(height: Space.x8),
                      about,
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) => Row(
    children: [
      const BrandMark(size: 40),
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
  );
}

class _About extends StatelessWidget {
  const _About();

  @override
  Widget build(BuildContext context) => const Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(
        'Пациент заполняет опросники, отмечает приём препарата и пишет о самочувствии. Если что-то '
        'требует внимания, врач увидит это в своей очереди. Диагнозов система не ставит.',
        style: AppType.body,
      ),
      SizedBox(height: Space.x5),
      _Step(
        icon: Icons.phone_iphone,
        title: 'Пациент',
        body: 'GAD-7 и PHQ-9 раз в две недели, отметки приёма утром и вечером, жалобы и файлы.',
      ),
      _Step(
        icon: Icons.rule,
        title: 'Правила',
        body: '16 правил решают, насколько срочно событие для врача и что показать пациенту.',
      ),
      _Step(
        icon: Icons.inbox_outlined,
        title: 'Врач',
        body: 'Срочное всегда сверху. Кнопка «Почему?» показывает, какое правило сработало и на чём.',
      ),
      _Step(
        icon: Icons.emergency_outlined,
        title: 'Срочные случаи',
        body: 'Пациенту сразу показывается кнопка «Позвонить 112», врачу — была ли она нажата.',
      ),
      SizedBox(height: Space.x4),
      _MisCard(),
    ],
  );
}

class _Step extends StatelessWidget {
  const _Step({required this.icon, required this.title, required this.body});

  final IconData icon;
  final String title;
  final String body;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: Space.x3),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 32,
          height: 32,
          decoration: const BoxDecoration(color: AppColors.accentSoft, borderRadius: Radii.smAll),
          child: Icon(icon, size: 18, color: AppColors.accent),
        ),
        const SizedBox(width: Space.x3),
        Expanded(
          child: Text.rich(
            TextSpan(
              children: [
                TextSpan(text: '$title. ', style: AppType.bodyStrong),
                TextSpan(text: body, style: AppType.bodySecondary),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}

/// Ссылка на демо-стенд, где окно сервиса открывается внутри МИС.
class _MisCard extends StatelessWidget {
  const _MisCard();

  @override
  Widget build(BuildContext context) => Panel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Row(
          children: [
            Icon(Icons.open_in_new, size: 18, color: AppColors.accent),
            SizedBox(width: Space.x2),
            Expanded(child: Text('Окно в ЕМИАС и 1С:Медицина', style: AppType.subsectionTitle)),
          ],
        ),
        const SizedBox(height: Space.x1),
        const Text(
          'Врач открывает карточку пациента прямо из медкарты МИС — без отдельного входа. '
          'Сводка (шкалы, приверженность, события) уходит в МИС в формате FHIR.',
          style: AppType.small,
        ),
        if (kIsWeb) ...[
          const SizedBox(height: Space.x3),
          Align(
            alignment: Alignment.centerLeft,
            child: OutlinedButton.icon(
              onPressed: () => unawaited(launchUrl(Uri.parse('mis-demo.html'), webOnlyWindowName: '_self')),
              icon: const Icon(Icons.desktop_windows_outlined, size: 18),
              label: const Text('Открыть демо-стенд МИС'),
            ),
          ),
        ],
      ],
    ),
  );
}
