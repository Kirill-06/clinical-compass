import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/demo_accounts.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

class _NavItem {
  const _NavItem(this.path, this.label, this.icon, this.selectedIcon);

  final String path;
  final String label;
  final IconData icon;
  final IconData selectedIcon;
}

const _items = [
  _NavItem('/doctor/queue', 'Очередь', Icons.inbox_outlined, Icons.inbox),
  _NavItem('/doctor/patients', 'Пациенты', Icons.groups_outlined, Icons.groups),
  _NavItem('/doctor/adverse-events', 'Побочные эффекты', Icons.report_outlined, Icons.report),
  _NavItem('/doctor/rules', 'Правила', Icons.rule_outlined, Icons.rule),
];

/// Кабинет врача: навигация слева, контент справа; на узком экране — меню.
class DoctorShell extends StatelessWidget {
  const DoctorShell({super.key, required this.location, required this.child});

  final String location;
  final Widget child;

  int get _selected {
    final i = _items.indexWhere((it) => location.startsWith(it.path));
    return i < 0 ? 1 : i;
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    if (width >= Breakpoints.medium) {
      final collapsed = width < 1100;
      return Scaffold(
        body: Row(
          children: [
            Container(
              width: collapsed ? 76 : 248,
              color: AppColors.surface,
              child: SafeArea(
                child: _Nav(selected: _selected, collapsed: collapsed),
              ),
            ),
            const VerticalDivider(width: 1),
            Expanded(child: child),
          ],
        ),
      );
    }
    return Scaffold(
      appBar: AppBar(
        titleSpacing: 0,
        title: Row(
          children: [
            const BrandMark(size: 22),
            const SizedBox(width: Space.x2),
            Flexible(child: Text(_items[_selected].label, overflow: TextOverflow.ellipsis)),
          ],
        ),
        actions: const [
          DemoAccountButton(compact: true),
          SizedBox(width: Space.x2),
        ],
      ),
      drawer: Drawer(
        backgroundColor: AppColors.surface,
        shape: const RoundedRectangleBorder(),
        child: SafeArea(child: _Nav(selected: _selected, collapsed: false, inDrawer: true)),
      ),
      body: child,
    );
  }
}

class _Nav extends StatelessWidget {
  const _Nav({required this.selected, required this.collapsed, this.inDrawer = false});

  final int selected;
  final bool collapsed;
  final bool inDrawer;

  @override
  Widget build(BuildContext context) {
    final user = context.user;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(Space.x5, Space.x5, Space.x4, Space.x6),
          child: Row(
            children: [
              const BrandMark(size: 28),
              if (!collapsed) ...[
                const SizedBox(width: Space.x3),
                const Expanded(
                  child: Text('Клинический компас', style: AppType.subsectionTitle, overflow: TextOverflow.ellipsis),
                ),
              ],
            ],
          ),
        ),
        for (final (i, item) in _items.indexed)
          _NavTile(
            item: item,
            selected: i == selected,
            collapsed: collapsed,
            badge: item.path == '/doctor/queue' ? const _QueueBadge() : null,
            onTap: () {
              if (inDrawer) Navigator.of(context).pop();
              context.go(item.path);
            },
          ),
        const Spacer(),
        const Divider(),
        Padding(
          padding: const EdgeInsets.all(Space.x4),
          child: collapsed
              ? const Center(child: DemoAccountButton(compact: true))
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(user.name, style: AppType.smallStrong),
                    const Text('Врач', style: AppType.caption),
                    const SizedBox(height: Space.x3),
                    const DemoAccountButton(),
                  ],
                ),
        ),
      ],
    );
  }
}

class _NavTile extends StatelessWidget {
  const _NavTile({
    required this.item,
    required this.selected,
    required this.collapsed,
    required this.onTap,
    this.badge,
  });

  final _NavItem item;
  final bool selected;
  final bool collapsed;
  final VoidCallback onTap;
  final Widget? badge;

  @override
  Widget build(BuildContext context) {
    final tile = Padding(
      padding: const EdgeInsets.symmetric(horizontal: Space.x3, vertical: 1),
      child: Semantics(
        selected: selected,
        button: true,
        label: item.label,
        excludeSemantics: true,
        child: Material(
          color: selected ? AppColors.accentSoft : Colors.transparent,
          borderRadius: Radii.smAll,
          child: InkWell(
            borderRadius: Radii.smAll,
            onTap: onTap,
            child: SizedBox(
              height: kMinTapTarget,
              child: Row(
                mainAxisAlignment: collapsed ? MainAxisAlignment.center : MainAxisAlignment.start,
                children: [
                  if (!collapsed) const SizedBox(width: Space.x3),
                  Stack(
                    clipBehavior: Clip.none,
                    children: [
                      Icon(
                        selected ? item.selectedIcon : item.icon,
                        size: 20,
                        color: selected ? AppColors.accent : AppColors.textSecondary,
                      ),
                      if (collapsed && badge != null) Positioned(right: -8, top: -6, child: badge!),
                    ],
                  ),
                  if (!collapsed) ...[
                    const SizedBox(width: Space.x3),
                    Expanded(
                      child: Text(
                        item.label,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                          color: selected ? AppColors.text : AppColors.textSecondary,
                        ),
                      ),
                    ),
                    ?badge,
                    const SizedBox(width: Space.x3),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
    return collapsed ? Tooltip(message: item.label, child: tile) : tile;
  }
}

/// Счётчик открытых алертов; срочные выделены отдельно.
class _QueueBadge extends StatelessWidget {
  const _QueueBadge();

  @override
  Widget build(BuildContext context) {
    return LiveFuture<List<Json>>(
      load: () => context.api.doctorQueue(),
      placeholder: const SizedBox.shrink(),
      pollEvery: const Duration(seconds: 20),
      builder: (context, q) {
        if (q.isEmpty) return const SizedBox.shrink();
        final urgent = q.where((a) => asJson(a['alert'])['doctor_priority'] == 'urgent').length;
        return Semantics(
          label: 'открытых: ${q.length}, срочных: $urgent',
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
            decoration: BoxDecoration(
              color: urgent > 0 ? AppColors.dangerFg : AppColors.infoFg,
              borderRadius: Radii.smAll,
            ),
            child: Text(
              '${q.length}',
              style: const TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w700),
            ),
          ),
        );
      },
    );
  }
}

/// Заголовок страницы кабинета врача.
class PageHeader extends StatelessWidget {
  const PageHeader({super.key, required this.title, this.subtitle, this.actions = const []});

  final String title;
  final String? subtitle;
  final List<Widget> actions;

  @override
  Widget build(BuildContext context) {
    final block = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Semantics(header: true, child: Text(title, style: AppType.pageTitle)),
        if (subtitle != null) ...[const SizedBox(height: 2), Text(subtitle!, style: AppType.bodySecondary)],
      ],
    );
    if (actions.isEmpty) return block;
    return Wrap(
      spacing: Space.x4,
      runSpacing: Space.x3,
      crossAxisAlignment: WrapCrossAlignment.end,
      alignment: WrapAlignment.spaceBetween,
      children: [
        ConstrainedBox(constraints: const BoxConstraints(maxWidth: 720), child: block),
        Wrap(spacing: Space.x2, runSpacing: Space.x2, children: actions),
      ],
    );
  }
}

EdgeInsets doctorPagePadding(BuildContext context) {
  final w = MediaQuery.sizeOf(context).width;
  if (w < Breakpoints.compact) return const EdgeInsets.fromLTRB(Space.x4, Space.x5, Space.x4, Space.x8);
  if (w < Breakpoints.expanded) return const EdgeInsets.fromLTRB(Space.x6, Space.x6, Space.x6, Space.x10);
  return const EdgeInsets.fromLTRB(Space.x8, Space.x8, Space.x8, Space.x12);
}

/// Обработка ошибки действия врача снэкбаром.
Future<void> runDoctorAction(BuildContext context, Future<void> Function() action, String done) async {
  final messenger = ScaffoldMessenger.of(context);
  try {
    await action();
    messenger.showSnackBar(SnackBar(content: Text(done)));
  } on Exception catch (e) {
    messenger.showSnackBar(SnackBar(content: Text('Не удалось: ${describeError(e)}')));
  }
}
