import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/patient/patient_shell.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/notices.dart';

/// Форма симптома / нежелательного явления (§8). Выбор из закрытого
/// справочника; «Другое» → other_unlisted + исходная фраза пациента.
class SymptomScreen extends StatefulWidget {
  const SymptomScreen({super.key});

  @override
  State<SymptomScreen> createState() => _SymptomScreenState();
}

class _SymptomScreenState extends State<SymptomScreen> {
  final _phrase = TextEditingController();
  SymptomType? _type;
  Tri _impact = Tri.unknown;
  Severity _severity = Severity.unknown;
  String? _error;
  bool _sending = false;
  String? _key;
  Json? _result;

  @override
  void dispose() {
    _phrase.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final type = _type;
    if (type == null) {
      setState(() => _error = 'Выберите, что вас беспокоит');
      return;
    }
    final phrase = _phrase.text.trim();
    if (type == SymptomType.otherUnlisted && phrase.isEmpty) {
      setState(() => _error = 'Опишите своими словами, что вас беспокоит');
      return;
    }
    final api = context.api;
    final user = context.user;
    final key = _key ??= api.newIdempotencyKey('sym');
    setState(() {
      _sending = true;
      _error = null;
    });
    try {
      final r = await api.reportSymptom(
        user.id,
        type: type,
        phrase: phrase.isEmpty ? null : phrase,
        affectsDailyLife: _impact,
        severity: _severity,
        idempotencyKey: key,
      );
      if (mounted) setState(() => _result = r);
    } on Exception catch (e) {
      if (mounted) setState(() => _error = describeError(e));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Самочувствие')),
      body: PatientFormPage(children: [_result == null ? _form() : _done(_result!)]),
    );
  }

  Widget _form() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(header: true, child: const Text('Что вас беспокоит?', style: AppType.pageTitle)),
        const SizedBox(height: Space.x2),
        const Text(
          'Выберите один пункт. Если подходящего нет — «Другое» и опишите своими словами. Врач увидит ваш ответ.',
          style: AppType.bodySecondary,
        ),
        const SizedBox(height: Space.x4),
        RadioGroup<SymptomType>(
          groupValue: _type,
          onChanged: (v) => setState(() {
            _type = v;
            _error = null;
          }),
          child: Panel(
            padding: const EdgeInsets.symmetric(vertical: Space.x1),
            child: Column(
              children: [
                for (final t in SymptomType.values)
                  InkWell(
                    onTap: () => setState(() {
                      _type = t;
                      _error = null;
                    }),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: Space.x2),
                      child: Row(
                        children: [
                          Radio<SymptomType>(value: t),
                          Expanded(child: Text(context.meta.symptom(t), style: AppType.body)),
                        ],
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: Space.x4),
        TextField(
          controller: _phrase,
          minLines: 2,
          maxLines: 5,
          maxLength: 1000,
          decoration: InputDecoration(
            labelText: _type == SymptomType.otherUnlisted
                ? 'Опишите, что беспокоит (обязательно)'
                : 'Комментарий (необязательно)',
            alignLabelWithHint: true,
          ),
        ),
        const SizedBox(height: Space.x3),
        const Text('Мешает ли это обычным делам?', style: AppType.subsectionTitle),
        const SizedBox(height: Space.x2),
        Wrap(
          spacing: Space.x2,
          runSpacing: Space.x2,
          children: [
            for (final (v, l) in [(Tri.yes, 'Да'), (Tri.no, 'Нет'), (Tri.unknown, 'Не знаю')])
              ChoiceChip(label: Text(l), selected: _impact == v, onSelected: (_) => setState(() => _impact = v)),
          ],
        ),
        const SizedBox(height: Space.x4),
        const Text('Насколько выражено?', style: AppType.subsectionTitle),
        const SizedBox(height: Space.x2),
        Wrap(
          spacing: Space.x2,
          runSpacing: Space.x2,
          children: [
            for (final s in Severity.values)
              ChoiceChip(
                label: Text(context.meta.severity(s)),
                selected: _severity == s,
                onSelected: (_) => setState(() => _severity = s),
              ),
          ],
        ),
        if (_error != null) ...[
          const SizedBox(height: Space.x4),
          Semantics(
            liveRegion: true,
            child: InlineNotice(tone: StatusTone.danger, icon: Icons.error_outline, body: _error!),
          ),
        ],
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
  }

  Widget _done(Json r) {
    final notices = [for (final n in r['patient_notices'] as List? ?? const []) asJson(n)];
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.check_circle_outline, color: AppColors.okFg, size: 32),
        const SizedBox(height: Space.x3),
        Semantics(header: true, liveRegion: true, child: const Text('Сообщение сохранено', style: AppType.pageTitle)),
        const SizedBox(height: Space.x2),
        const Text('Ваш врач увидит его в карточке.', style: AppType.bodySecondary),
        const SizedBox(height: Space.x4),
        if (notices.isNotEmpty) NoticeList(notices: notices),
        const SizedBox(height: Space.x4),
        SizedBox(
          height: 52,
          child: FilledButton(onPressed: () => context.go('/patient'), child: const Text('На главную')),
        ),
      ],
    );
  }
}
