import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

/// Кто смотрит переписку: от этого зависит, какие сообщения «мои» и что показать врачу.
enum ChatViewer {
  patient(Role.patient, 'patient', 'doctor'),
  doctor(Role.doctor, 'doctor', 'patient');

  const ChatViewer(this.role, this.ownSender, this.counterpart);

  final Role role;
  final String ownSender;
  final String counterpart;
}

/// Загрузить переписку и отметить прочитанными сообщения собеседника.
///
/// Экран, оставшийся от прошлого аккаунта (смена пользователя в демо), ничего не
/// запрашивает: иначе пациент «прочитал» бы сообщения за врача или наоборот.
Future<Json> loadChat(BuildContext context, String patientId, ChatViewer viewer) async {
  final api = context.api;
  if (api.user?.role != viewer.role) return const {'messages': <Object?>[]};
  final chat = await api.chat(patientId);
  final unread = [
    for (final m in chat['messages'] as List? ?? const [])
      if (asJson(m)['sender'] == viewer.counterpart && asJson(m)['read_at'] == null) m,
  ];
  if (unread.isNotEmpty && api.user?.role == viewer.role) {
    unawaited(api.markChatRead(patientId).catchError((Object _) {}));
  }
  return chat;
}

/// Лента переписки: пузыри по дням, время, «прочитано», вложения.
/// Не прокручивается сама — её кладут в экран или вкладку.
class ChatMessages extends StatelessWidget {
  const ChatMessages({super.key, required this.patientId, required this.messages, required this.viewer});

  final String patientId;
  final List<Json> messages;
  final ChatViewer viewer;

  @override
  Widget build(BuildContext context) {
    if (messages.isEmpty) {
      return EmptyState(
        compact: true,
        icon: Icons.forum_outlined,
        title: 'Сообщений пока нет',
        message: viewer == ChatViewer.patient
            ? 'Напишите врачу о самочувствии или приложите документ.'
            : 'Пациент ещё не писал. Можно написать первым.',
      );
    }
    final today = DateUtils.dateOnly(context.services.clock.now());
    final children = <Widget>[];
    DateTime? day;
    for (final m in messages) {
      final at = DateTime.parse(m['created_at']! as String).toLocal();
      final messageDay = DateUtils.dateOnly(at);
      if (messageDay != day) {
        day = messageDay;
        children.add(_DaySeparator(label: _dayLabel(messageDay, today)));
      }
      children.add(_Bubble(patientId: patientId, message: m, viewer: viewer, at: at));
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children);
  }

  static String _dayLabel(DateTime day, DateTime today) {
    final diff = today.difference(day).inDays;
    if (diff == 0) return 'Сегодня';
    if (diff == 1) return 'Вчера';
    return Fmt.dayMonth(day);
  }
}

class _DaySeparator extends StatelessWidget {
  const _DaySeparator({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: Space.x3),
    child: Center(
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: Space.x3, vertical: 2),
        decoration: const BoxDecoration(color: AppColors.surfaceSubtle, borderRadius: Radii.smAll),
        child: Text(label, style: AppType.caption),
      ),
    ),
  );
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.patientId, required this.message, required this.viewer, required this.at});

  final String patientId;
  final Json message;
  final ChatViewer viewer;
  final DateTime at;

  bool get _mine => message['sender'] == viewer.ownSender;

  @override
  Widget build(BuildContext context) {
    final mine = _mine;
    final text = message['text'] as String?;
    final attachments = [for (final a in message['attachments'] as List? ?? const []) asJson(a)];
    final questions = [for (final q in message['clarifying_questions'] as List? ?? const []) q as String];
    final author = mine ? 'Вы' : (viewer == ChatViewer.patient ? 'Врач' : 'Пациент');
    return Semantics(
      label: '$author, ${Fmt.time(at)}',
      child: Align(
        alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 520),
          child: Padding(
            padding: const EdgeInsets.only(bottom: Space.x2),
            child: Column(
              crossAxisAlignment: mine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: mine ? AppColors.accentSoft : AppColors.surface,
                    border: mine ? null : Border.all(color: AppColors.border),
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(14),
                      topRight: const Radius.circular(14),
                      bottomLeft: Radius.circular(mine ? 14 : 4),
                      bottomRight: Radius.circular(mine ? 4 : 14),
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.fromLTRB(Space.x3, Space.x2, Space.x3, Space.x2),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        if (text != null) SelectableText(text, style: AppType.body),
                        for (final a in attachments) _AttachmentChip(patientId: patientId, attachment: a),
                        const SizedBox(height: 2),
                        _Meta(at: at, mine: mine, read: message['read_at'] != null),
                      ],
                    ),
                  ),
                ),
                if (viewer == ChatViewer.doctor && !mine) ...[
                  if (message['extraction_status'] == 'failed')
                    const Padding(
                      padding: EdgeInsets.only(top: Space.x1),
                      child: StatusBadge(
                        label: 'ИИ недоступен — сообщение сохранено, красные флаги проверены словарём',
                        tone: StatusTone.warn,
                        dense: true,
                      ),
                    ),
                  for (final q in questions)
                    Padding(
                      padding: const EdgeInsets.only(top: Space.x1),
                      child: Text('Уточняющий вопрос пациенту: $q', style: AppType.caption),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Meta extends StatelessWidget {
  const _Meta({required this.at, required this.mine, required this.read});

  final DateTime at;
  final bool mine;
  final bool read;

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Text(Fmt.time(at), style: AppType.caption),
      if (mine) ...[
        const SizedBox(width: Space.x1),
        Tooltip(
          message: read ? 'Прочитано' : 'Доставлено',
          child: Icon(
            read ? Icons.done_all : Icons.done,
            size: 14,
            color: read ? AppColors.accent : AppColors.textMuted,
          ),
        ),
      ],
    ],
  );
}

class _AttachmentChip extends StatelessWidget {
  const _AttachmentChip({required this.patientId, required this.attachment});

  final String patientId;
  final Json attachment;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: Space.x1),
    child: OutlinedButton.icon(
      onPressed: () => unawaited(_download(context)),
      icon: const Icon(Icons.download_outlined, size: 18),
      label: Text('${attachment['filename']} · ${Fmt.fileSize(attachment['size']! as int)}'),
    ),
  );

  Future<void> _download(BuildContext context) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final bytes = await context.api.attachment(patientId, attachment['id']! as String);
      final uri = await FilePicker.saveFile(
        fileName: attachment['filename']! as String,
        bytes: bytes,
        mimeType: attachment['mime_type']! as String,
      );
      if (uri != null) {
        messenger.showSnackBar(SnackBar(content: Text('Файл «${attachment['filename']}» сохранён')));
      }
    } on Exception catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Не удалось скачать: ${describeError(e)}')));
    }
  }
}

/// «Сообщения приходят сразу» или «обновляется раз в 20 секунд» — честно о доставке.
class ChatDeliveryHint extends StatelessWidget {
  const ChatDeliveryHint({super.key});

  @override
  Widget build(BuildContext context) => ValueListenableBuilder<bool>(
    valueListenable: context.services.realtime.live,
    builder: (context, live, _) => Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(Icons.circle, size: 8, color: live ? AppColors.okFg : AppColors.textMuted),
        const SizedBox(width: Space.x1),
        Flexible(
          child: Text(live ? 'Сообщения приходят сразу' : 'Обновляется раз в 20 секунд', style: AppType.caption),
        ),
      ],
    ),
  );
}
