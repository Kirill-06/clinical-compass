import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

String homeFor(Role role) => switch (role) {
  Role.doctor => '/doctor/queue',
  Role.patient => '/patient',
  Role.admin => '/admin',
};

/// Демо-вход: сервер выдаёт сессию по id без пароля (режим демо).
Future<void> demoSignIn(BuildContext context, String userId) async {
  final api = context.api;
  final router = GoRouter.of(context);
  final messenger = ScaffoldMessenger.of(context);
  try {
    final user = await api.demoLogin(userId, notify: false);
    router.go(homeFor(user.role));
    api.refresh();
  } on Exception catch (e) {
    messenger.showSnackBar(SnackBar(content: Text(describeError(e))));
  }
}

Future<void> showDemoAccountPicker(BuildContext context) async {
  final wide = MediaQuery.sizeOf(context).width >= Breakpoints.compact;
  final picked = wide
      ? await showDialog<String>(
          context: context,
          builder: (ctx) => Dialog(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 520, maxHeight: 680),
              child: const AccountList(),
            ),
          ),
        )
      : await showModalBottomSheet<String>(
          context: context,
          isScrollControlled: true,
          builder: (ctx) => ConstrainedBox(
            constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(ctx).height * 0.85),
            child: const AccountList(),
          ),
        );
  if (picked != null && context.mounted) await demoSignIn(context, picked);
}

/// Список демо-аккаунтов с сервера. Возвращает выбранный id через Navigator.pop.
class AccountList extends StatelessWidget {
  const AccountList({super.key, this.onPick});

  /// Если задан — вызывается вместо закрытия диалога (стартовый экран).
  final ValueChanged<String>? onPick;

  @override
  Widget build(BuildContext context) {
    final current = context.services.api.user;
    return LiveFuture<Json>(
      load: () => context.api.demoAccounts(),
      loadingLabel: 'Получаем список аккаунтов…',
      builder: (context, data) {
        final groups = [
          ('Врачи', Icons.medical_services_outlined, data['doctors']),
          ('Пациенты', Icons.person_outline, data['patients']),
          ('Администратор записи', Icons.event_available_outlined, data['admins']),
        ];
        return ListView(
          shrinkWrap: true,
          physics: onPick == null ? null : const NeverScrollableScrollPhysics(),
          padding: const EdgeInsets.symmetric(vertical: Space.x2),
          children: [
            if (onPick == null)
              const Padding(
                padding: EdgeInsets.fromLTRB(Space.x5, Space.x3, Space.x5, Space.x2),
                child: Row(
                  children: [
                    DemoTag(),
                    SizedBox(width: Space.x2),
                    Expanded(child: Text('Сменить демо-аккаунт', style: AppType.sectionTitle)),
                  ],
                ),
              ),
            for (final (title, icon, list) in groups) ...[
              Padding(
                padding: const EdgeInsets.fromLTRB(Space.x5, Space.x4, Space.x5, Space.x1),
                child: Text(title, style: AppType.columnHeader),
              ),
              for (final a in (list as List).cast<Map>())
                _Tile(
                  icon: icon,
                  title: a['name'] as String,
                  subtitle: a['subtitle'] as String,
                  selected: current?.id == a['id'],
                  onTap: () {
                    final id = a['id'] as String;
                    if (onPick != null) {
                      onPick!(id);
                    } else {
                      Navigator.of(context).pop(id);
                    }
                  },
                ),
            ],
          ],
        );
      },
    );
  }
}

class _Tile extends StatelessWidget {
  const _Tile({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: Space.x5, vertical: Space.x3),
          child: Row(
            children: [
              Icon(icon, size: 20, color: AppColors.textSecondary),
              const SizedBox(width: Space.x3),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: AppType.bodyStrong),
                    Text(subtitle, style: AppType.small),
                  ],
                ),
              ),
              if (selected)
                const Icon(Icons.check, size: 20, color: AppColors.accent)
              else
                const Icon(Icons.chevron_right, color: AppColors.textMuted),
            ],
          ),
        ),
      ),
    );
  }
}

/// Кнопка в шапке: «ДЕМО · имя ▾».
class DemoAccountButton extends StatelessWidget {
  const DemoAccountButton({super.key, this.compact = false});

  final bool compact;

  @override
  Widget build(BuildContext context) {
    final user = context.services.api.user;
    return Tooltip(
      message: 'Демо-режим: сменить аккаунт',
      child: OutlinedButton(
        onPressed: () => unawaited(showDemoAccountPicker(context)),
        style: OutlinedButton.styleFrom(
          padding: const EdgeInsets.symmetric(horizontal: Space.x2),
          minimumSize: const Size(0, 40),
        ),
        child: FittedBox(
          fit: BoxFit.scaleDown,
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              const DemoTag(),
              if (!compact) ...[
                const SizedBox(width: Space.x2),
                ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 200),
                  child: Text(
                    user?.name ?? 'Выбрать аккаунт',
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                  ),
                ),
              ],
              const SizedBox(width: 2),
              const Icon(Icons.expand_more, size: 18),
            ],
          ),
        ),
      ),
    );
  }
}
