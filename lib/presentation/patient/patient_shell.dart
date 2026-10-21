import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/demo_accounts.dart';

class _Dest {
  const _Dest(this.path, this.label, this.icon, this.selectedIcon);

  final String path;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

const _dests = [
  _Dest('/patient', 'Главная', Icons.home_outlined, Icons.home),
  _Dest('/patient/results', 'Результаты', Icons.insights_outlined, Icons.insights),
  _Dest('/patient/medication', 'Приём', Icons.medication_outlined, Icons.medication),
];

/// Кабинет пациента: mobile-first, нижняя навигация на телефоне.
class PatientShell extends StatelessWidget {
  const PatientShell({super.key, required this.location, required this.child});

  final String location;
  final Widget child;

  int get _index {
    for (var i = _dests.length - 1; i >= 0; i--) {
      if (location.startsWith(_dests[i].path)) return i;
    }
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= Breakpoints.medium;
    return Scaffold(
      appBar: AppBar(
        titleSpacing: Space.x4,
        title: Row(
          children: [
            const BrandMark(size: 24),
            const SizedBox(width: Space.x2),
            if (!wide)
              const Flexible(
                child: Text('Клинический компас', overflow: TextOverflow.ellipsis, style: AppType.subsectionTitle),
              )
            else ...[
              const Text('Клинический компас', style: AppType.subsectionTitle),
              const SizedBox(width: Space.x6),
              Flexible(
                child: SingleChildScrollView(
                  scrollDirection: Axis.horizontal,
                  child: Row(
                    children: [
                      for (final (i, d) in _dests.indexed)
                        Padding(
                          padding: const EdgeInsets.only(right: Space.x1),
                          child: TextButton(
                            onPressed: () => context.go(d.path),
                            style: TextButton.styleFrom(
                              foregroundColor: i == _index ? AppColors.text : AppColors.textSecondary,
                              backgroundColor: i == _index ? AppColors.accentSoft : null,
                            ),
                            child: Text(d.label),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ],
        ),
        actions: [
          DemoAccountButton(compact: !wide),
          const SizedBox(width: Space.x3),
        ],
      ),
      body: child,
      bottomNavigationBar: wide
          ? null
          : NavigationBar(
              selectedIndex: _index,
              onDestinationSelected: (i) => context.go(_dests[i].path),
              destinations: [
                for (final d in _dests)
                  NavigationDestination(icon: Icon(d.icon), selectedIcon: Icon(d.selectedIcon), label: d.label),
              ],
            ),
    );
  }
}

/// Узкая колонка контента пациента.
class PatientPage extends StatelessWidget {
  const PatientPage({super.key, required this.children, this.maxWidth = 640});

  final List<Widget> children;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.sizeOf(context).width < Breakpoints.compact;
    return SingleChildScrollView(
      padding: EdgeInsets.fromLTRB(
        narrow ? Space.x4 : Space.x6,
        narrow ? Space.x5 : Space.x8,
        narrow ? Space.x4 : Space.x6,
        Space.x10,
      ),
      child: Align(
        alignment: Alignment.topCenter,
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children),
        ),
      ),
    );
  }
}

/// Полноэкранная форма пациента (опросник, самочувствие, сообщение).
class PatientFormPage extends StatelessWidget {
  const PatientFormPage({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final narrow = MediaQuery.sizeOf(context).width < Breakpoints.compact;
    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.fromLTRB(narrow ? Space.x4 : Space.x6, Space.x5, narrow ? Space.x4 : Space.x6, Space.x10),
        child: Align(
          alignment: Alignment.topCenter,
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 600),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children),
          ),
        ),
      ),
    );
  }
}
