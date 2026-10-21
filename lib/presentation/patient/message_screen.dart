import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/patient/patient_shell.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/notices.dart';

const _maxFiles = 5;
const _maxBytes = 10 * 1024 * 1024;

String? _mimeFor(String name) => switch (name.contains('.') ? name.split('.').last.toLowerCase() : '') {
  'pdf' => 'application/pdf',
  'jpg' || 'jpeg' => 'image/jpeg',
  'png' => 'image/png',
  'heic' => 'image/heic',
  'txt' => 'text/plain',
  _ => null,
};

typedef _File = ({String filename, String mimeType, List<int> bytes});

/// Свободный текст и файлы для врача. Текст сохраняется на сервере до
/// обработки ИИ (сейчас — заглушка), файлы — как вложения без анализа.
class MessageScreen extends StatefulWidget {
  const MessageScreen({super.key});

  @override
  State<MessageScreen> createState() => _MessageScreenState();
}

class _MessageScreenState extends State<MessageScreen> {
  final _text = TextEditingController();
  final List<_File> _files = [];
  bool _picking = false;
  bool _sending = false;
  String? _error;
  String? _key;
  Json? _sent;

  bool get _dirty => (_text.text.trim().isNotEmpty || _files.isNotEmpty) && _sent == null;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    if (_picking) return;
    setState(() {
      _picking = true;
      _error = null;
    });
    try {
      final picked = await FilePicker.pickFiles(
        dialogTitle: 'Выберите файл для врача',
        type: FileType.custom,
        allowedExtensions: const ['pdf', 'jpg', 'jpeg', 'png', 'heic', 'txt'],
      );
      final errors = <String>[];
      for (final f in picked) {
        if (_files.length >= _maxFiles) {
          errors.add('Можно приложить не более $_maxFiles файлов.');
          break;
        }
        final mime = _mimeFor(f.name);
        final size = f.lengthSync() ?? await f.length() ?? 0;
        if (mime == null) {
          errors.add('Формат «${f.name}» не поддерживается.');
        } else if (size > _maxBytes) {
          errors.add('«${f.name}» больше 10 МБ.');
        } else {
          final bytes = await f.readAsBytes();
          if (mounted) setState(() => _files.add((filename: f.name, mimeType: mime, bytes: bytes)));
        }
      }
      if (errors.isNotEmpty && mounted) setState(() => _error = errors.join(' '));
    } on Exception catch (e) {
      if (mounted) setState(() => _error = 'Не удалось открыть файл: ${describeError(e)}');
    } finally {
      if (mounted) setState(() => _picking = false);
    }
  }

  Future<void> _send() async {
    final text = _text.text.trim();
    if (text.isEmpty && _files.isEmpty) {
      setState(() => _error = 'Напишите сообщение или приложите файл.');
      return;
    }
    final api = context.api;
    final user = context.user;
    final key = _key ??= api.newIdempotencyKey('msg');
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final r = await api.sendMessage(
        user.id,
        text: text.isEmpty ? null : text,
        files: List.of(_files),
        idempotencyKey: key,
      );
      if (mounted) setState(() => _sent = r);
    } on Exception catch (e) {
      if (mounted) setState(() => _error = '${describeError(e)} Текст и файлы остались на экране — можно повторить.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  Future<bool> _confirmLeave() async =>
      await showDialog<bool>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Не отправлять сообщение?'),
          content: const Text('Текст и выбранные файлы не сохранятся.'),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Вернуться')),
            OutlinedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Не отправлять')),
          ],
        ),
      ) ??
      false;

  void _leave() => context.canPop() ? context.pop() : context.go('/patient');

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop && await _confirmLeave() && mounted) _leave();
      },
      child: Scaffold(
        appBar: AppBar(title: Text(_sent == null ? 'Сообщение врачу' : 'Отправлено')),
        body: PatientFormPage(children: [_sent == null ? _form() : _done(_sent!)]),
      ),
    );
  }

  Widget _form() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Semantics(header: true, child: const Text('Сообщение или файл для врача', style: AppType.pageTitle)),
      const SizedBox(height: Space.x2),
      const Text(
        'Напишите своими словами. Сообщение сохраняется и передаётся врачу; система не ставит диагноз '
        'и не определяет срочность вне утверждённых правил.',
        style: AppType.bodySecondary,
      ),
      const SizedBox(height: Space.x5),
      TextField(
        controller: _text,
        minLines: 5,
        maxLines: 12,
        maxLength: 2000,
        enabled: !_sending,
        onChanged: (_) => setState(() => _error = null),
        decoration: const InputDecoration(labelText: 'Сообщение', alignLabelWithHint: true),
      ),
      const SizedBox(height: Space.x3),
      const Text('Файлы: PDF, JPG, PNG, HEIC или TXT, до 10 МБ, не более 5.', style: AppType.small),
      const SizedBox(height: Space.x2),
      for (final (i, f) in _files.indexed) ...[
        Container(
          padding: const EdgeInsets.fromLTRB(Space.x3, Space.x1, Space.x1, Space.x1),
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: Radii.smAll,
            border: Border.all(color: AppColors.borderStrong),
          ),
          child: Row(
            children: [
              const Icon(Icons.description_outlined, size: 20, color: AppColors.textSecondary),
              const SizedBox(width: Space.x2),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(f.filename, style: AppType.smallStrong, overflow: TextOverflow.ellipsis),
                    Text(Fmt.fileSize(f.bytes.length), style: AppType.caption),
                  ],
                ),
              ),
              IconButton(
                tooltip: 'Убрать файл ${f.filename}',
                onPressed: _sending ? null : () => setState(() => _files.removeAt(i)),
                icon: const Icon(Icons.close, size: 18),
              ),
            ],
          ),
        ),
        const SizedBox(height: Space.x2),
      ],
      OutlinedButton.icon(
        onPressed: _sending || _picking || _files.length >= _maxFiles ? null : () => unawaited(_pick()),
        icon: const Icon(Icons.attach_file, size: 18),
        label: Text(_files.isEmpty ? 'Выбрать файл' : 'Добавить ещё файл'),
      ),
      if (_error != null) ...[
        const SizedBox(height: Space.x4),
        Semantics(
          liveRegion: true,
          child: InlineNotice(tone: StatusTone.danger, icon: Icons.error_outline, body: _error!),
        ),
      ],
      const SizedBox(height: Space.x4),
      const InlineNotice(
        tone: StatusTone.neutral,
        icon: Icons.science_outlined,
        title: 'Демо',
        body: 'Данные хранятся на демо-сервере без шифрования. Не отправляйте реальные медицинские документы.',
      ),
      const SizedBox(height: Space.x6),
      SizedBox(
        height: 52,
        child: FilledButton(
          onPressed: _sending ? null : () => unawaited(_send()),
          child: Text(_sending ? 'Отправляем…' : 'Отправить врачу'),
        ),
      ),
    ],
  );

  Widget _done(Json r) {
    final notices = [for (final n in r['patient_notices'] as List? ?? const []) asJson(n)];
    final questions = [for (final q in r['clarifying_questions'] as List? ?? const []) q as String];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.check_circle_outline, color: AppColors.okFg, size: 32),
        const SizedBox(height: Space.x3),
        Semantics(
          header: true,
          liveRegion: true,
          child: const Text('Сообщение отправлено врачу', style: AppType.pageTitle),
        ),
        const SizedBox(height: Space.x2),
        const Text('Врач увидит его в вашей карточке.', style: AppType.bodySecondary),
        if (questions.isNotEmpty) ...[
          const SizedBox(height: Space.x4),
          InlineNotice(
            tone: StatusTone.neutral,
            icon: Icons.help_outline,
            title: 'Уточните, пожалуйста',
            body: '${questions.join(' ')} Ответьте новым сообщением или отметьте в «Самочувствии».',
          ),
        ],
        if (notices.isNotEmpty) ...[const SizedBox(height: Space.x4), NoticeList(notices: notices)],
        const SizedBox(height: Space.x6),
        SizedBox(
          height: 52,
          child: FilledButton(onPressed: () => context.go('/patient'), child: const Text('На главную')),
        ),
      ],
    );
  }
}
