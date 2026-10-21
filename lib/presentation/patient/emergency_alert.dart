import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/data/api_client.dart';
import 'package:clinical_compass/domain/json.dart';

/// Показывает экстренное предупреждение поверх любого экрана пациента.
///
/// Сервис не вызывает скорую сам: пациент нажимает кнопку, и звонок начинает
/// его телефон. Что пациент сделал (открыл, позвонил, написал врачу, закрыл),
/// уходит врачу в карточку события.
class EmergencyAlertHost extends StatefulWidget {
  const EmergencyAlertHost({super.key, required this.api, required this.navigatorKey, required this.child});

  final ApiClient api;
  final GlobalKey<NavigatorState> navigatorKey;
  final Widget child;

  @override
  State<EmergencyAlertHost> createState() => _EmergencyAlertHostState();
}

class _EmergencyAlertHostState extends State<EmergencyAlertHost> {
  late final StreamSubscription<Json> _sub;
  final _queue = <Json>[];
  bool _showing = false;

  @override
  void initState() {
    super.initState();
    _sub = widget.api.emergencies.listen(_enqueue);
  }

  @override
  void dispose() {
    _sub.cancel();
    super.dispose();
  }

  void _enqueue(Json notice) {
    _queue.add(notice);
    _next();
  }

  Future<void> _next() async {
    final context = widget.navigatorKey.currentContext;
    final user = widget.api.user;
    if (_showing || _queue.isEmpty || context == null || user == null) return;
    _showing = true;
    final notice = _queue.removeAt(0);
    await showEmergencyAlert(context, api: widget.api, patientId: user.id, notice: notice);
    _showing = false;
    unawaited(_next());
  }

  @override
  Widget build(BuildContext context) => widget.child;
}

Future<void> showEmergencyAlert(
  BuildContext context, {
  required ApiClient api,
  required String patientId,
  required Json notice,
}) {
  return showGeneralDialog<void>(
    context: context,
    barrierDismissible: false,
    barrierLabel: 'Экстренное предупреждение',
    barrierColor: Colors.black.withValues(alpha: 0.45),
    transitionDuration: const Duration(milliseconds: 280),
    pageBuilder: (_, _, _) => _EmergencyPanel(api: api, patientId: patientId, notice: notice),
    transitionBuilder: (_, animation, _, child) => SlideTransition(
      position: Tween(
        begin: const Offset(0, -1),
        end: Offset.zero,
      ).animate(CurvedAnimation(parent: animation, curve: Curves.easeOutCubic)),
      child: child,
    ),
  );
}

class _EmergencyPanel extends StatefulWidget {
  const _EmergencyPanel({required this.api, required this.patientId, required this.notice});

  final ApiClient api;
  final String patientId;
  final Json notice;

  @override
  State<_EmergencyPanel> createState() => _EmergencyPanelState();
}

class _EmergencyPanelState extends State<_EmergencyPanel> {
  String? _dialHint;

  String get _alertId => widget.notice['alert_id']! as String;

  @override
  void initState() {
    super.initState();
    _record('shown');
  }

  /// Журнал действий не должен мешать звонку: ошибки сети здесь не показываем.
  void _record(String action) =>
      unawaited(widget.api.safetyAction(widget.patientId, _alertId, action).catchError((Object _) {}));

  Future<void> _call(String number) async {
    _record(number == '112' ? 'call_112' : 'call_103');
    final started = await launchUrl(Uri(scheme: 'tel', path: number)).catchError((Object _) => false);
    if (!started && mounted) {
      setState(() => _dialHint = 'Звонок не начался на этом устройстве — наберите $number с телефона.');
    }
  }

  void _close(String action) {
    _record(action);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final template = widget.notice['template'] is Map ? asJson(widget.notice['template']) : null;
    return SafeArea(
      child: Align(
        alignment: Alignment.topCenter,
        child: Padding(
          padding: const EdgeInsets.all(Space.x3),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 560),
            child: Material(
              color: AppColors.surface,
              elevation: 8,
              shape: const RoundedRectangleBorder(borderRadius: Radii.mdAll),
              clipBehavior: Clip.antiAlias,
              child: DecoratedBox(
                decoration: const BoxDecoration(
                  border: Border(top: BorderSide(color: AppColors.dangerFg, width: 4)),
                ),
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(Space.x5),
                  child: Semantics(
                    liveRegion: true,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.emergency_outlined, color: AppColors.dangerFg),
                            SizedBox(width: Space.x2),
                            Expanded(child: Text('Нужна срочная помощь?', style: AppType.sectionTitle)),
                          ],
                        ),
                        const SizedBox(height: Space.x3),
                        Text(template?['title'] as String? ?? 'Ваш врач увидит этот ответ', style: AppType.bodyStrong),
                        const SizedBox(height: Space.x1),
                        Text(
                          template?['body'] as String? ??
                              'Если вы сейчас в опасности, позвоните по номеру 112 или 103.',
                          style: AppType.body,
                        ),
                        if (template != null && template['status'] != 'approved') ...[
                          const SizedBox(height: Space.x2),
                          const Row(
                            children: [
                              DemoTag(
                                label: 'ЧЕРНОВИК ТЕКСТА',
                                tooltip: 'Текст ожидает утверждения медицинским экспертом',
                              ),
                            ],
                          ),
                        ],
                        const SizedBox(height: Space.x5),
                        FilledButton.icon(
                          style: FilledButton.styleFrom(
                            backgroundColor: AppColors.dangerFg,
                            minimumSize: const Size.fromHeight(56),
                            textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                          ),
                          onPressed: () => _call('112'),
                          icon: const Icon(Icons.call),
                          label: const Text('Позвонить 112'),
                        ),
                        const SizedBox(height: Space.x2),
                        OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(minimumSize: const Size.fromHeight(48)),
                          onPressed: () => _call('103'),
                          icon: const Icon(Icons.local_hospital_outlined, size: 18),
                          label: const Text('Скорая помощь — 103'),
                        ),
                        if (_dialHint != null) ...[
                          const SizedBox(height: Space.x2),
                          Text(_dialHint!, style: AppType.small.copyWith(color: AppColors.dangerFg)),
                        ],
                        const SizedBox(height: Space.x4),
                        const Divider(),
                        const SizedBox(height: Space.x2),
                        Wrap(
                          alignment: WrapAlignment.spaceBetween,
                          spacing: Space.x2,
                          runSpacing: Space.x2,
                          children: [
                            TextButton.icon(
                              onPressed: () {
                                _close('message_doctor');
                                GoRouter.of(context).push('/patient/message');
                              },
                              icon: const Icon(Icons.chat_bubble_outline, size: 18),
                              label: const Text('Написать врачу'),
                            ),
                            TextButton(
                              onPressed: () => _close('dismissed'),
                              child: const Text('Я в безопасности, закрыть'),
                            ),
                          ],
                        ),
                        const Text(
                          'Сообщения врач читает в рабочее время — это не экстренная связь.',
                          style: AppType.caption,
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
