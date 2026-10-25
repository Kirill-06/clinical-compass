import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/chat/chat_composer.dart';
import 'package:clinical_compass/presentation/chat/chat_messages.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

/// Переписка с пациентом в карточке врача. Открытие отмечает сообщения пациента прочитанными.
class DoctorChatPanel extends StatelessWidget {
  const DoctorChatPanel({super.key, required this.patientId});

  final String patientId;

  @override
  Widget build(BuildContext context) => Panel(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Align(alignment: Alignment.centerRight, child: ChatDeliveryHint()),
        const SizedBox(height: Space.x2),
        LiveFuture<Json>(
          reloadKey: patientId,
          pollEvery: const Duration(seconds: 20),
          loadingLabel: 'Загружаем переписку…',
          load: () => loadChat(context, patientId, ChatViewer.doctor),
          builder: (context, chat) => ChatMessages(
            patientId: patientId,
            messages: [for (final m in chat['messages']! as List) asJson(m)],
            viewer: ChatViewer.doctor,
          ),
        ),
        const Divider(height: Space.x6),
        ChatComposer(
          sendLabel: 'Ответить',
          hint: 'Ответ пациенту',
          onSend: (text, _) => context.api.sendDoctorMessage(patientId, text),
        ),
        const SizedBox(height: Space.x1),
        const ChatNotEmergencyNote(forPatient: false),
      ],
    ),
  );
}
