import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/chat/chat_composer.dart';
import 'package:clinical_compass/presentation/chat/chat_messages.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/notices.dart';

/// Переписка пациента с лечащим врачом.
///
/// Сообщение пациента уходит тем же путём, что и раньше: сохраняется до обработки ИИ,
/// из него извлекаются факты, а красный флаг сразу показывает экран 112.
class PatientChatScreen extends StatelessWidget {
  const PatientChatScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final user = context.user;
    final narrow = MediaQuery.sizeOf(context).width < Breakpoints.compact;
    final gutter = narrow ? Space.x4 : Space.x6;
    return Column(
      children: [
        Expanded(
          child: LiveFuture<Json>(
            reloadKey: user.id,
            pollEvery: const Duration(seconds: 20),
            loadingLabel: 'Загружаем переписку…',
            load: () => loadChat(context, user.id, ChatViewer.patient),
            builder: (context, chat) => SingleChildScrollView(
              reverse: true,
              padding: EdgeInsets.fromLTRB(gutter, Space.x4, gutter, Space.x2),
              child: _Width(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const _Header(),
                    const SizedBox(height: Space.x3),
                    ChatMessages(
                      patientId: user.id,
                      messages: [for (final m in chat['messages']! as List) asJson(m)],
                      viewer: ChatViewer.patient,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
        Material(
          color: AppColors.surface,
          child: Container(
            decoration: const BoxDecoration(
              border: Border(top: BorderSide(color: AppColors.border)),
            ),
            padding: EdgeInsets.fromLTRB(gutter, Space.x3, gutter, Space.x3),
            child: _Width(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  ChatComposer(
                    allowFiles: true,
                    sendLabel: 'Отправить врачу',
                    hint: 'Сообщение врачу',
                    onSend: (text, files) => _send(context, text, files),
                  ),
                  const SizedBox(height: Space.x1),
                  const ChatNotEmergencyNote(forPatient: true),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _send(BuildContext context, String text, List<ChatFile> files) async {
    final api = context.api;
    final result = await api.sendMessage(
      context.user.id,
      text: text.isEmpty ? null : text,
      files: files,
      idempotencyKey: api.newIdempotencyKey('msg'),
    );
    // Экстренные предупреждения показывает EmergencyAlertHost; остальные тексты — здесь.
    final notices = [
      for (final n in result['patient_notices'] as List? ?? const [])
        if (asJson(n)['patient_action'] != 'recommend_ambulance') asJson(n),
    ];
    if (notices.isNotEmpty && context.mounted) await showNoticesSheet(context, notices);
  }
}

class _Header extends StatelessWidget {
  const _Header();

  @override
  Widget build(BuildContext context) => Wrap(
    alignment: WrapAlignment.spaceBetween,
    crossAxisAlignment: WrapCrossAlignment.center,
    spacing: Space.x3,
    runSpacing: Space.x1,
    children: [
      Semantics(header: true, child: const Text('Чат с врачом', style: AppType.sectionTitle)),
      const ChatDeliveryHint(),
    ],
  );
}

class _Width extends StatelessWidget {
  const _Width({required this.child});

  final Widget child;

  @override
  Widget build(BuildContext context) => Align(
    alignment: Alignment.topCenter,
    child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 640), child: child),
  );
}
