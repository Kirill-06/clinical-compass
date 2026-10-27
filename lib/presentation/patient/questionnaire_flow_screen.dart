import 'dart:async';

import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/loader.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/domain/meta.dart';
import 'package:clinical_compass/presentation/patient/patient_shell.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/notices.dart';

enum _Phase { intro, question, review, result }

/// Опросник по одному вопросу на шаг (паттерн GOV.UK question pages),
/// проверка ответов, отправка на сервер с ключом идемпотентности.
class QuestionnaireFlowScreen extends StatefulWidget {
  const QuestionnaireFlowScreen({super.key, required this.instrument});

  final Instrument instrument;

  @override
  State<QuestionnaireFlowScreen> createState() => _QuestionnaireFlowScreenState();
}

class _QuestionnaireFlowScreenState extends State<QuestionnaireFlowScreen> {
  late final InstrumentDefinition _def = context.meta.instrument(widget.instrument);
  late final List<int?> _answers = List<int?>.filled(_def.itemCount, null);
  String? _idempotencyKey;
  _Phase _phase = _Phase.intro;
  int _index = 0;
  bool _showError = false;
  bool _returnToReview = false;
  bool _submitting = false;
  String? _submitError;
  Json? _result;

  bool get _dirty => _answers.any((a) => a != null) && _result == null;

  void _next() {
    if (_answers[_index] == null) {
      setState(() => _showError = true);
      return;
    }
    setState(() {
      _showError = false;
      if (_returnToReview || _index == _def.itemCount - 1) {
        _returnToReview = false;
        _phase = _Phase.review;
      } else {
        _index++;
      }
    });
  }

  void _back() => setState(() {
    _showError = false;
    if (_phase == _Phase.review) {
      _phase = _Phase.question;
      _index = _def.itemCount - 1;
    } else if (_index == 0) {
      _phase = _Phase.intro;
    } else {
      _index--;
    }
  });

  Future<void> _submit() async {
    if (_submitting || _result != null) return;
    final api = context.api;
    final user = context.user;
    // Один ключ на попытку: повтор после сбоя сети не создаст дубль.
    final key = _idempotencyKey ??= api.newIdempotencyKey('q-${widget.instrument.wire}');
    setState(() {
      _submitting = true;
      _submitError = null;
    });
    try {
      final r = await api.submitQuestionnaire(user.id, widget.instrument, [
        for (final a in _answers) a!,
      ], idempotencyKey: key);
      if (!mounted) return;
      setState(() {
        _result = r;
        _phase = _Phase.result;
      });
    } on Exception catch (e) {
      if (mounted) setState(() => _submitError = describeError(e));
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<bool> _confirmLeave() async {
    final leave = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Прервать опрос?'),
        content: const Text('Ответы не сохранятся. Незавершённый опрос врачу не отправляется.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Продолжить опрос')),
          OutlinedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Выйти')),
        ],
      ),
    );
    return leave ?? false;
  }

  void _leave() => context.canPop() ? context.pop() : context.go('/patient');

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: !_dirty,
      onPopInvokedWithResult: (didPop, _) async {
        if (!didPop && await _confirmLeave() && mounted) _leave();
      },
      child: Scaffold(
        appBar: AppBar(
          automaticallyImplyLeading: false,
          leading: _phase == _Phase.result
              ? null
              : IconButton(
                  tooltip: 'Закрыть опрос',
                  icon: const Icon(Icons.close),
                  onPressed: () async {
                    if (!_dirty || await _confirmLeave()) {
                      if (mounted) _leave();
                    }
                  },
                ),
          title: Text(_phase == _Phase.result ? 'Опрос отправлен' : 'Опрос ${widget.instrument.label}'),
        ),
        body: PatientFormPage(
          children: [
            switch (_phase) {
              _Phase.intro => _intro(),
              _Phase.question => _question(),
              _Phase.review => _review(),
              _Phase.result => _resultView(),
            },
          ],
        ),
      ),
    );
  }

  Widget _intro() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Text(_def.title, style: AppType.label),
      const SizedBox(height: Space.x2),
      Semantics(
        header: true,
        child: const Text('Как вы себя чувствовали последние 2 недели', style: AppType.pageTitle),
      ),
      const SizedBox(height: Space.x3),
      Text(
        'В опросе ${_def.itemCount} вопросов, на каждый — один из четырёх ответов. Обычно это занимает 2–3 минуты. '
        'Ответы увидит ваш врач.',
        style: AppType.bodySecondary,
      ),
      const SizedBox(height: Space.x2),
      const Text('Если закрыть опрос до отправки, ответы не сохранятся.', style: AppType.small),
      const SizedBox(height: Space.x8),
      SizedBox(
        height: 52,
        child: FilledButton(onPressed: () => setState(() => _phase = _Phase.question), child: const Text('Начать')),
      ),
    ],
  );

  Widget _question() {
    final total = _def.itemCount;
    final value = _answers[_index];
    return Column(
      key: ValueKey(_index),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          label: 'Вопрос ${_index + 1} из $total',
          excludeSemantics: true,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text('Вопрос ${_index + 1} из $total', style: AppType.label),
              const SizedBox(height: Space.x2),
              ClipRRect(
                borderRadius: BorderRadius.circular(2),
                child: LinearProgressIndicator(value: (_index + 1) / total, minHeight: 4),
              ),
            ],
          ),
        ),
        const SizedBox(height: Space.x6),
        Text(_def.instruction, style: AppType.bodySecondary),
        const SizedBox(height: Space.x2),
        Semantics(header: true, child: Text(_def.items[_index], style: AppType.question)),
        const SizedBox(height: Space.x5),
        if (_showError) ...[
          Semantics(
            liveRegion: true,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: Space.x3, vertical: Space.x2),
              decoration: const BoxDecoration(
                border: Border(left: BorderSide(color: AppColors.dangerFg, width: 4)),
              ),
              child: const Text(
                'Выберите один вариант ответа',
                style: TextStyle(color: AppColors.dangerFg, fontWeight: FontWeight.w600, fontSize: 15),
              ),
            ),
          ),
          const SizedBox(height: Space.x3),
        ],
        RadioGroup<int>(
          groupValue: value,
          onChanged: (v) {
            if (v != null) setState(() => _answers[_index] = v);
          },
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (final o in _def.options) ...[
                _OptionTile(
                  option: o,
                  selected: value == o.value,
                  error: _showError,
                  onTap: () => setState(() {
                    _answers[_index] = o.value;
                    _showError = false;
                  }),
                ),
                const SizedBox(height: Space.x2),
              ],
            ],
          ),
        ),
        const SizedBox(height: Space.x6),
        SizedBox(
          height: 52,
          child: FilledButton(
            onPressed: _next,
            child: Text(
              _returnToReview
                  ? 'Сохранить и вернуться к проверке'
                  : _index == total - 1
                  ? 'Проверить ответы'
                  : 'Далее',
            ),
          ),
        ),
        const SizedBox(height: Space.x2),
        TextButton.icon(onPressed: _back, icon: const Icon(Icons.arrow_back, size: 18), label: const Text('Назад')),
      ],
    );
  }

  Widget _review() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Semantics(header: true, child: const Text('Проверьте ответы', style: AppType.pageTitle)),
      const SizedBox(height: Space.x2),
      const Text('Перед отправкой можно изменить любой ответ.', style: AppType.bodySecondary),
      const SizedBox(height: Space.x5),
      Panel(
        padding: EdgeInsets.zero,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            for (var i = 0; i < _def.itemCount; i++) ...[
              if (i > 0) const Divider(),
              Padding(
                padding: const EdgeInsets.fromLTRB(Space.x4, Space.x3, Space.x2, Space.x3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('${i + 1}. ${_def.items[i]}', style: AppType.small),
                          const SizedBox(height: 2),
                          Text(_def.optionLabel(_answers[i] ?? -1) ?? 'Нет ответа', style: AppType.bodyStrong),
                        ],
                      ),
                    ),
                    TextButton(
                      onPressed: _submitting
                          ? null
                          : () => setState(() {
                              _index = i;
                              _returnToReview = true;
                              _phase = _Phase.question;
                            }),
                      child: Text('Изменить', semanticsLabel: 'Изменить ответ на вопрос ${i + 1}'),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
      if (_submitError != null) ...[
        const SizedBox(height: Space.x4),
        InlineNotice(
          tone: StatusTone.danger,
          icon: Icons.error_outline,
          title: 'Ответы не отправлены',
          body: '$_submitError Ответы сохранены на этом экране.',
        ),
      ],
      const SizedBox(height: Space.x6),
      SizedBox(
        height: 52,
        child: FilledButton(
          onPressed: _submitting ? null : () => unawaited(_submit()),
          child: _submitting
              ? const Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    CompassSpinner(size: 20, badge: false),
                    SizedBox(width: Space.x3),
                    Text('Отправляем…'),
                  ],
                )
              : Text(_submitError == null ? 'Отправить врачу' : 'Повторить отправку'),
        ),
      ),
      const SizedBox(height: Space.x2),
      TextButton.icon(
        onPressed: _submitting ? null : _back,
        icon: const Icon(Icons.arrow_back, size: 18),
        label: const Text('Назад'),
      ),
    ],
  );

  Widget _resultView() {
    final r = _result!;
    final response = asJson(r['response']);
    final notices = [for (final n in r['patient_notices'] as List? ?? const []) asJson(n)];
    final at = DateTime.parse(response['administered_at']! as String);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.check_circle_outline, color: AppColors.okFg, size: 32),
        const SizedBox(height: Space.x3),
        Semantics(
          header: true,
          liveRegion: true,
          child: Text(
            r['duplicate'] == true ? 'Этот опрос уже был отправлен' : 'Ответы отправлены врачу',
            style: AppType.pageTitle,
          ),
        ),
        const SizedBox(height: Space.x2),
        Text(
          'Сохранено ${Fmt.dayMonth(at)} в ${Fmt.time(at)}. Ответы доступны вашему врачу.',
          style: AppType.bodySecondary,
        ),
        const SizedBox(height: Space.x5),
        Panel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Результат ${widget.instrument.label}', style: AppType.label),
              Text.rich(
                TextSpan(
                  children: [
                    TextSpan(text: '${response['total_score']}', style: AppType.numericLarge),
                    TextSpan(text: ' из ${response['max_score']} баллов', style: AppType.bodySecondary),
                  ],
                ),
              ),
              Text('Категория по шкале: ${response['severity_label']}', style: AppType.bodyStrong),
            ],
          ),
        ),
        const SizedBox(height: Space.x4),
        const InlineNotice(
          tone: StatusTone.info,
          icon: Icons.info_outline,
          body: 'Результат скрининга не является диагнозом. Оценку проводит врач.',
        ),
        if (notices.isNotEmpty) ...[const SizedBox(height: Space.x4), NoticeList(notices: notices)],
        const SizedBox(height: Space.x6),
        SizedBox(
          height: 52,
          child: FilledButton(onPressed: () => context.go('/patient'), child: const Text('На главную')),
        ),
        const SizedBox(height: Space.x3),
        SizedBox(
          height: 48,
          child: OutlinedButton(onPressed: () => context.go('/patient/results'), child: const Text('Мои результаты')),
        ),
      ],
    );
  }
}

class _OptionTile extends StatelessWidget {
  const _OptionTile({required this.option, required this.selected, required this.error, required this.onTap});

  final AnswerOption option;
  final bool selected;
  final bool error;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final border = selected
        ? AppColors.accent
        : error
        ? AppColors.dangerFg
        : AppColors.borderStrong;
    return Material(
      color: selected ? AppColors.accentSofter : AppColors.surface,
      shape: RoundedRectangleBorder(
        borderRadius: Radii.mdAll,
        side: BorderSide(color: border, width: selected ? 2 : 1),
      ),
      child: InkWell(
        borderRadius: Radii.mdAll,
        onTap: onTap,
        child: ConstrainedBox(
          constraints: const BoxConstraints(minHeight: 56),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: Space.x2, vertical: Space.x1),
            child: Row(
              children: [
                Radio<int>(value: option.value),
                const SizedBox(width: Space.x1),
                Expanded(
                  child: Text(
                    option.label,
                    style: AppType.body.copyWith(
                      fontSize: 16,
                      fontWeight: selected ? FontWeight.w600 : FontWeight.w400,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
