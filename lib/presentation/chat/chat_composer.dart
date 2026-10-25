import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

const _maxFiles = 5;
const _maxBytes = 10 * 1024 * 1024;

typedef ChatFile = ({String filename, String mimeType, List<int> bytes});

/// Отправка сообщения. Исключение — ошибка: поле покажет её и сохранит текст и файлы.
typedef ChatSend = Future<void> Function(String text, List<ChatFile> files);

String? _mimeFor(String name) => switch (name.contains('.') ? name.split('.').last.toLowerCase() : '') {
  'pdf' => 'application/pdf',
  'jpg' || 'jpeg' => 'image/jpeg',
  'png' => 'image/png',
  'heic' => 'image/heic',
  'txt' => 'text/plain',
  _ => null,
};

/// Поле сообщения. Текст и файлы остаются на месте, если отправка не удалась.
class ChatComposer extends StatefulWidget {
  const ChatComposer({
    super.key,
    required this.onSend,
    required this.sendLabel,
    required this.hint,
    this.allowFiles = false,
  });

  final ChatSend onSend;
  final String sendLabel;
  final String hint;
  final bool allowFiles;

  @override
  State<ChatComposer> createState() => _ChatComposerState();
}

class _ChatComposerState extends State<ChatComposer> {
  final _text = TextEditingController();
  final List<ChatFile> _files = [];
  bool _picking = false;
  bool _sending = false;
  String? _error;

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final text = _text.text.trim();
    if (text.isEmpty && _files.isEmpty) {
      setState(() => _error = widget.allowFiles ? 'Напишите сообщение или приложите файл.' : 'Напишите сообщение.');
      return;
    }
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      await widget.onSend(text, List.of(_files));
      if (!mounted) return;
      _text.clear();
      setState(_files.clear);
    } on Exception catch (e) {
      if (mounted) setState(() => _error = '${describeError(e)} Сообщение осталось в поле — можно повторить.');
    } finally {
      if (mounted) setState(() => _sending = false);
    }
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

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    mainAxisSize: MainAxisSize.min,
    children: [
      for (final (i, f) in _files.indexed)
        Padding(
          padding: const EdgeInsets.only(bottom: Space.x2),
          child: InputChip(
            avatar: const Icon(Icons.description_outlined, size: 18),
            label: Text('${f.filename} · ${Fmt.fileSize(f.bytes.length)}', overflow: TextOverflow.ellipsis),
            onDeleted: _sending ? null : () => setState(() => _files.removeAt(i)),
            deleteButtonTooltipMessage: 'Убрать файл ${f.filename}',
          ),
        ),
      if (_error != null)
        Padding(
          padding: const EdgeInsets.only(bottom: Space.x2),
          child: Semantics(
            liveRegion: true,
            child: InlineNotice(tone: StatusTone.danger, icon: Icons.error_outline, body: _error!),
          ),
        ),
      Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (widget.allowFiles)
            IconButton(
              tooltip: 'Приложить файл: PDF, JPG, PNG, HEIC или TXT, до 10 МБ',
              onPressed: _sending || _picking || _files.length >= _maxFiles ? null : () => unawaited(_pick()),
              icon: const Icon(Icons.attach_file),
            ),
          Expanded(
            child: TextField(
              controller: _text,
              minLines: 1,
              maxLines: 6,
              maxLength: 2000,
              enabled: !_sending,
              textInputAction: TextInputAction.newline,
              onChanged: (_) => setState(() => _error = null),
              decoration: InputDecoration(hintText: widget.hint, counterText: ''),
            ),
          ),
          const SizedBox(width: Space.x2),
          // На телефоне — круглая кнопка, чтобы полю ввода хватило места.
          if (MediaQuery.sizeOf(context).width < Breakpoints.compact)
            IconButton.filled(
              tooltip: widget.sendLabel,
              onPressed: _sending ? null : () => unawaited(_send()),
              icon: _sending
                  ? const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2))
                  : const Icon(Icons.send),
            )
          else
            FilledButton.icon(
              onPressed: _sending ? null : () => unawaited(_send()),
              icon: const Icon(Icons.send, size: 18),
              label: Text(_sending ? 'Отправляем…' : widget.sendLabel),
            ),
        ],
      ),
    ],
  );
}

/// Подпись под полем: чат не экстренный канал.
class ChatNotEmergencyNote extends StatelessWidget {
  const ChatNotEmergencyNote({super.key, required this.forPatient});

  final bool forPatient;

  @override
  Widget build(BuildContext context) => Text(
    forPatient
        ? 'Врач отвечает в рабочее время. Если вам плохо прямо сейчас — звоните 112.'
        : 'Ответ видит только этот пациент. Чат не заменяет звонок при срочной ситуации.',
    style: AppType.caption,
  );
}
