import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/data/api_client.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';

/// Вход из МИС: одноразовый код из адреса окна → сессия врача → карточка пациента.
class EmbedLaunchScreen extends StatefulWidget {
  const EmbedLaunchScreen({super.key, required this.code});

  final String code;

  @override
  State<EmbedLaunchScreen> createState() => _EmbedLaunchScreenState();
}

class _EmbedLaunchScreenState extends State<EmbedLaunchScreen> {
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _open());
  }

  Future<void> _open() async {
    final api = context.api;
    try {
      final patientId = await api.openFromMis(widget.code);
      if (!mounted) return;
      context.go('/embed/patient/$patientId');
      api.refresh();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: _error == null
        ? const LoadingState(label: 'Открываем карточку пациента…')
        : EmptyState(icon: Icons.link_off, title: 'Не удалось открыть окно', message: '$_error'),
  );
}

/// Окно внутри МИС: только карточка пациента, без навигации рабочего места.
class EmbedShell extends StatelessWidget {
  const EmbedShell({super.key, required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) {
    final source = context.services.api.embeddedFrom;
    return Scaffold(
      body: Column(
        children: [
          Material(
            color: AppColors.surface,
            child: Container(
              height: 44,
              padding: const EdgeInsets.symmetric(horizontal: Space.x4),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: AppColors.border)),
              ),
              child: Row(
                children: [
                  const BrandMark(size: 22),
                  const SizedBox(width: Space.x2),
                  const Text('Клинический компас', style: AppType.bodyStrong),
                  if (source != null) ...[
                    const SizedBox(width: Space.x3),
                    StatusBadge(
                      label: 'открыто из $source',
                      tone: StatusTone.neutral,
                      icon: Icons.open_in_new,
                      dense: true,
                      tooltip: 'Окно открыто из МИС; доступ — по правам врача в «Клиническом компасе»',
                    ),
                  ],
                  const Spacer(),
                  const Flexible(child: DemoModeStrip()),
                ],
              ),
            ),
          ),
          Expanded(child: child),
        ],
      ),
    );
  }
}
