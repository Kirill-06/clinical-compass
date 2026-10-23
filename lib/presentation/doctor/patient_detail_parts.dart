import 'dart:async';
import 'dart:convert';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/response_detail.dart';
import 'package:clinical_compass/presentation/shared/score_chart.dart';

/// GAD-7 и PHQ-9: последний/предыдущий, изменение со знаком, график по датам.
class ScoresPanel extends StatefulWidget {
  const ScoresPanel({super.key, required this.responses});

  final List<Json> responses;

  @override
  State<ScoresPanel> createState() => _ScoresPanelState();
}

class _ScoresPanelState extends State<ScoresPanel> {
  Instrument _instrument = Instrument.gad7;

  @override
  Widget build(BuildContext context) {
    final def = context.meta.instrument(_instrument);
    final list = widget.responses.where((r) => r['instrument'] == _instrument.wire).toList()
      ..sort((a, b) => (a['administered_at']! as String).compareTo(b['administered_at']! as String));
    final last = list.isEmpty ? null : list.last;
    final prev = list.length < 2 ? null : list[list.length - 2];
    final points = pointsFrom(list, _instrument);
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionHeader(
            title: 'Шкалы и динамика',
            subtitle: 'Скрининг, не диагноз. Изменение — со знаком (текущий − предыдущий).',
            trailing: FilterSegment<Instrument>(
              semanticLabel: 'Шкала',
              options: Instrument.values,
              value: _instrument,
              onChanged: (i) => setState(() => _instrument = i),
              labelOf: (i) => i.label,
              countOf: (i) => widget.responses.where((r) => r['instrument'] == i.wire).length,
            ),
          ),
          const SizedBox(height: Space.x4),
          if (last == null)
            const EmptyState(compact: true, icon: Icons.insert_chart_outlined, title: 'Опросник ещё не заполнялся')
          else ...[
            Wrap(
              spacing: Space.x10,
              runSpacing: Space.x4,
              children: [
                _Big(label: 'Последний', r: last, max: def.maxScore),
                _Big(label: 'Предыдущий', r: prev, max: def.maxScore, muted: true),
                KeyValue(
                  label: 'Изменение',
                  value: '',
                  valueWidget: Text(signed(last['delta_from_previous'] as int?), style: AppType.numericLarge),
                ),
                KeyValue(label: 'От исходного', value: signed(last['delta_from_baseline'] as int?)),
                if (_instrument == Instrument.phq9)
                  KeyValue(
                    label: 'Вопрос 9 (последний)',
                    value: '',
                    valueWidget: Text(
                      '${last['phq9_item9'] ?? '—'}',
                      style: AppType.numericLarge.copyWith(
                        color: (last['phq9_item9'] as int? ?? 0) > 0 ? AppColors.dangerFg : null,
                      ),
                    ),
                  ),
              ],
            ),
            const SizedBox(height: Space.x4),
            ScoreChart(
              points: points,
              definition: def,
              onOpen: (p) {
                final r = list.firstWhere((x) => x['id'] == p.id, orElse: () => last);
                unawaited(showResponseDialog(context, r));
              },
            ),
            const SizedBox(height: Space.x2),
            Text(
              points.length == 1
                  ? 'Одно измерение — динамика появится после следующего.'
                  : 'Точки — фактические даты. Повторное нажатие на точку открывает ответы.',
              style: AppType.caption,
            ),
            const SizedBox(height: Space.x3),
            for (final r in list.reversed)
              InkWell(
                onTap: () => unawaited(showResponseDialog(context, r)),
                child: Padding(
                  padding: const EdgeInsets.symmetric(vertical: Space.x2),
                  child: Row(
                    children: [
                      SizedBox(
                        width: 150,
                        child: Text(
                          Fmt.dateTime(DateTime.parse(r['administered_at']! as String)),
                          style: AppType.small,
                        ),
                      ),
                      Expanded(
                        child: Text(
                          '${r['total_score']} · ${r['severity_label']}',
                          style: AppType.body.copyWith(fontSize: 14),
                        ),
                      ),
                      Text(signed(r['delta_from_previous'] as int?), style: AppType.numericSmall),
                      const SizedBox(width: Space.x2),
                      const Icon(Icons.chevron_right, size: 18, color: AppColors.textMuted),
                    ],
                  ),
                ),
              ),
          ],
          if (def.wordingNote != null) ...[
            const SizedBox(height: Space.x2),
            Text(def.wordingNote!, style: AppType.caption),
          ],
        ],
      ),
    );
  }
}

class _Big extends StatelessWidget {
  const _Big({required this.label, required this.r, required this.max, this.muted = false});

  final String label;
  final Json? r;
  final int max;
  final bool muted;

  @override
  Widget build(BuildContext context) {
    final x = r;
    return ConstrainedBox(
      constraints: const BoxConstraints(minWidth: 130),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: AppType.caption),
          if (x == null)
            const Text('Нет данных', style: AppType.bodySecondary)
          else ...[
            Text.rich(
              TextSpan(
                children: [
                  TextSpan(
                    text: '${x['total_score']}',
                    style: AppType.numericLarge.copyWith(color: muted ? AppColors.textSecondary : null),
                  ),
                  TextSpan(text: ' / $max', style: AppType.small),
                ],
              ),
            ),
            Text(x['severity_label'] as String? ?? '', style: AppType.bodyStrong.copyWith(fontSize: 14)),
            Text(Fmt.date(DateTime.parse(x['administered_at']! as String)), style: AppType.caption),
          ],
        ],
      ),
    );
  }
}

/// Интервалы опросников: по умолчанию 14 дней, врач может изменить (§6.3).
class SchedulesPanel extends StatelessWidget {
  const SchedulesPanel({super.key, required this.patientId, required this.schedules});

  final String patientId;
  final List<Json> schedules;

  @override
  Widget build(BuildContext context) {
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SectionHeader(
            title: 'График опросников',
            subtitle: 'По умолчанию раз в 14 дней; интервал задаёт врач',
            level: 2,
          ),
          const SizedBox(height: Space.x2),
          for (final (i, s) in schedules.indexed) ...[
            if (i > 0) const Divider(),
            Padding(
              padding: const EdgeInsets.symmetric(vertical: Space.x3),
              child: Row(
                children: [
                  SizedBox(width: 64, child: Text(s['label']! as String, style: AppType.smallStrong)),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Каждые ${Fmt.days(s['interval_days']! as int)} · ${s['configured_by'] == 'doctor' ? 'задано врачом' : 'по умолчанию'}',
                          style: AppType.body.copyWith(fontSize: 14),
                        ),
                        Text(
                          s['active'] == true
                              ? 'Следующий: ${Fmt.date(DateTime.parse(s['next_due_at']! as String))}'
                              : 'Не назначен',
                          style: AppType.caption,
                        ),
                        if (s['active'] == true) ...[const SizedBox(height: 4), dueBadge(s['due_status']! as String)],
                      ],
                    ),
                  ),
                  IconButton(
                    tooltip: 'Изменить интервал ${s['label']}',
                    icon: const Icon(Icons.edit_outlined, size: 18),
                    onPressed: () => unawaited(_editInterval(context, s)),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _editInterval(BuildContext context, Json s) async {
    final controller = TextEditingController(text: '${s['interval_days']}');
    var active = s['active'] == true;
    final result = await showDialog<(int, bool)?>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setState) => AlertDialog(
          title: Text('Интервал ${s['label']}'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: controller,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Каждые N дней (1–180)'),
              ),
              SwitchListTile(
                value: active,
                onChanged: (v) => setState(() => active = v),
                title: const Text('Опросник назначен'),
                contentPadding: EdgeInsets.zero,
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Отмена')),
            FilledButton(
              onPressed: () {
                final n = int.tryParse(controller.text.trim());
                if (n == null || n < 1 || n > 180) return;
                Navigator.pop(ctx, (n, active));
              },
              child: const Text('Сохранить'),
            ),
          ],
        ),
      ),
    );
    controller.dispose();
    if (result == null || !context.mounted) return;
    await runDoctorAction(
      context,
      () => context.api.setSchedule(
        patientId,
        Instrument.fromWire(s['instrument']! as String),
        intervalDays: result.$1,
        active: result.$2,
      ),
      'Интервал сохранён',
    );
  }
}

/// Вкладки: жалобы, сообщения, анализы, история, Patient State, аудит.
class DetailTabs extends StatefulWidget {
  const DetailTabs({super.key, required this.d, required this.now});

  final Json d;
  final DateTime now;

  @override
  State<DetailTabs> createState() => _DetailTabsState();
}

class _DetailTabsState extends State<DetailTabs> with SingleTickerProviderStateMixin {
  late final TabController _tabs = TabController(length: 6, vsync: this)..addListener(() => setState(() {}));

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final d = widget.d;
    final symptoms = [for (final s in d['symptoms']! as List) asJson(s)];
    final messages = [for (final m in d['messages']! as List) asJson(m)];
    final labs = [for (final l in d['labs']! as List) asJson(l)];
    final pid = asJson(d['patient'])['id']! as String;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        TabBar(
          controller: _tabs,
          isScrollable: true,
          tabs: [
            Tab(text: 'Жалобы и симптомы (${symptoms.length})', height: 44),
            Tab(text: 'Сообщения и файлы (${messages.length})', height: 44),
            Tab(text: 'Анализы (${labs.length})', height: 44),
            const Tab(text: 'История', height: 44),
            const Tab(text: 'Patient State', height: 44),
            const Tab(text: 'Аудит', height: 44),
          ],
        ),
        const SizedBox(height: Space.x4),
        switch (_tabs.index) {
          0 => _Symptoms(symptoms: symptoms),
          1 => _Messages(patientId: pid, messages: messages),
          2 => _Labs(labs: labs),
          3 => _Timeline(events: [for (final e in d['timeline']! as List) asJson(e)], now: widget.now),
          4 => _StateView(state: asJson(d['patient_state']), valid: d['schema_valid'] == true),
          _ => _Audit(patientId: pid),
        },
      ],
    );
  }
}

class _Symptoms extends StatelessWidget {
  const _Symptoms({required this.symptoms});

  final List<Json> symptoms;

  @override
  Widget build(BuildContext context) {
    if (symptoms.isEmpty) {
      return const Panel(
        child: EmptyState(compact: true, icon: Icons.healing_outlined, title: 'Жалоб нет'),
      );
    }
    return Panel(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          for (final (i, s) in symptoms.indexed) ...[
            if (i > 0) const Divider(),
            Padding(
              padding: const EdgeInsets.all(Space.x4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: Space.x2,
                    runSpacing: Space.x1,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(s['label']! as String, style: AppType.bodyStrong),
                      if (s['out_of_scope'] == true)
                        const StatusBadge(
                          label: 'Вне области инструмента',
                          tone: StatusTone.neutral,
                          icon: Icons.help_outline,
                          dense: true,
                        ),
                      StatusBadge(label: s['source_label'] as String? ?? '', tone: StatusTone.neutral, dense: true),
                      StatusBadge(
                        label: s['confirmation_label'] as String? ?? '',
                        tone: StatusTone.neutral,
                        dense: true,
                      ),
                    ],
                  ),
                  if (s['patient_phrase'] != null) ...[
                    const SizedBox(height: 2),
                    Text('«${s['patient_phrase']}»', style: AppType.body),
                  ],
                  Text(
                    'Мешает обычным делам: ${_tri(s['affects_daily_life'])} · выраженность: ${context.meta.severity(Severity.fromWire(s['severity']! as String)).toLowerCase()}',
                    style: AppType.caption,
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  static String _tri(Object? v) => switch (v) {
    'yes' => 'да',
    'no' => 'нет',
    _ => 'неизвестно',
  };
}

class _Messages extends StatelessWidget {
  const _Messages({required this.patientId, required this.messages});

  final String patientId;
  final List<Json> messages;

  @override
  Widget build(BuildContext context) {
    if (messages.isEmpty) {
      return const Panel(
        child: EmptyState(compact: true, icon: Icons.chat_bubble_outline, title: 'Сообщений нет'),
      );
    }
    return Panel(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          for (final (i, m) in messages.indexed) ...[
            if (i > 0) const Divider(),
            Padding(
              padding: const EdgeInsets.all(Space.x4),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Wrap(
                    spacing: Space.x2,
                    crossAxisAlignment: WrapCrossAlignment.center,
                    children: [
                      Text(Fmt.dateTime(DateTime.parse(m['created_at']! as String)), style: AppType.caption),
                      if (m['extraction_status'] != null)
                        StatusBadge(
                          label: switch (m['extraction_status']) {
                            'extracted' => 'Обработано ИИ',
                            'failed' => 'ИИ недоступен — сообщение сохранено',
                            'pending' => 'Ожидает обработки',
                            _ => 'Без текста',
                          },
                          tone: m['extraction_status'] == 'failed' ? StatusTone.warn : StatusTone.neutral,
                          dense: true,
                        ),
                    ],
                  ),
                  if (m['text'] != null) ...[
                    const SizedBox(height: Space.x1),
                    SelectableText(m['text']! as String, style: AppType.body),
                  ],
                  for (final q in m['clarifying_questions'] as List? ?? const [])
                    Text('Уточняющий вопрос пациенту: $q', style: AppType.caption),
                  for (final a in m['attachments'] as List? ?? const [])
                    Padding(
                      padding: const EdgeInsets.only(top: Space.x2),
                      child: OutlinedButton.icon(
                        onPressed: () => unawaited(_download(context, asJson(a))),
                        icon: const Icon(Icons.download_outlined, size: 18),
                        label: Text('${asJson(a)['filename']} · ${Fmt.fileSize(asJson(a)['size']! as int)}'),
                      ),
                    ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }

  Future<void> _download(BuildContext context, Json a) async {
    final messenger = ScaffoldMessenger.of(context);
    try {
      final bytes = await context.api.attachment(patientId, a['id']! as String);
      final uri = await FilePicker.saveFile(
        fileName: a['filename']! as String,
        bytes: bytes,
        mimeType: a['mime_type']! as String,
      );
      if (uri != null) messenger.showSnackBar(SnackBar(content: Text('Файл «${a['filename']}» сохранён')));
    } on Exception catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Не удалось скачать: ${describeError(e)}')));
    }
  }
}

class _Labs extends StatelessWidget {
  const _Labs({required this.labs});

  final List<Json> labs;

  @override
  Widget build(BuildContext context) {
    if (labs.isEmpty) {
      return const Panel(
        child: EmptyState(
          compact: true,
          icon: Icons.biotech_outlined,
          title: 'Анализов нет',
          message: 'Результаты принимаются через API (POST /patients/{id}/labs) и проходят правила v0.2.',
        ),
      );
    }
    return Panel(
      padding: EdgeInsets.zero,
      child: Column(
        children: [
          for (final (i, l) in labs.indexed) ...[
            if (i > 0) const Divider(),
            Padding(
              padding: const EdgeInsets.all(Space.x4),
              child: Row(
                children: [
                  Expanded(child: Text('${l['analyte']}: ${l['value']} ${l['unit']}', style: AppType.bodyStrong)),
                  Text(
                    'реф. ${l['reference_low'] ?? '—'}–${l['reference_high'] ?? '—'} · проба ${l['sample_date']} · '
                    '${l['doctor_verified'] == true ? 'проверено врачом' : 'не проверено'}',
                    style: AppType.caption,
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Timeline extends StatelessWidget {
  const _Timeline({required this.events, required this.now});

  final List<Json> events;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    return Panel(
      padding: const EdgeInsets.symmetric(vertical: Space.x2),
      child: Column(
        children: [
          for (final e in events)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: Space.x4, vertical: Space.x2),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SizedBox(
                    width: 120,
                    child: Text(Fmt.relativeMoment(DateTime.parse(e['at']! as String), now), style: AppType.caption),
                  ),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(e['title']! as String, style: AppType.body.copyWith(fontSize: 14)),
                        if (e['detail'] != null)
                          Text(
                            e['detail']! as String,
                            style: AppType.small,
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                        Text(e['author']! as String, style: AppType.caption),
                      ],
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

class _StateView extends StatelessWidget {
  const _StateView({required this.state, required this.valid});

  final Json state;
  final bool valid;

  @override
  Widget build(BuildContext context) {
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: Space.x2,
            children: [
              StatusBadge(
                label: valid ? 'Соответствует patient_state_v0.2.schema.json' : 'Не соответствует схеме',
                tone: valid ? StatusTone.ok : StatusTone.danger,
                icon: valid ? Icons.check : Icons.error_outline,
                dense: true,
              ),
            ],
          ),
          const SizedBox(height: Space.x2),
          const Text('Единственный вход rule engine. Технический вид для проверки контракта.', style: AppType.caption),
          const SizedBox(height: Space.x3),
          Container(
            constraints: const BoxConstraints(maxHeight: 420),
            padding: const EdgeInsets.all(Space.x3),
            decoration: BoxDecoration(
              color: AppColors.surfaceSubtle,
              borderRadius: Radii.smAll,
              border: Border.all(color: AppColors.border),
            ),
            child: SingleChildScrollView(
              child: SelectableText(
                const JsonEncoder.withIndent('  ').convert(state),
                style: const TextStyle(fontFamily: 'monospace', fontSize: 12, height: 1.4),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _Audit extends StatelessWidget {
  const _Audit({required this.patientId});

  final String patientId;

  @override
  Widget build(BuildContext context) {
    return LiveFuture<List<Json>>(
      reloadKey: patientId,
      load: () => context.api.audit(patientId),
      builder: (context, events) => Panel(
        padding: const EdgeInsets.symmetric(vertical: Space.x2),
        child: Column(
          children: [
            for (final e in events.take(200))
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: Space.x4, vertical: 6),
                child: Row(
                  children: [
                    SizedBox(
                      width: 150,
                      child: Text(Fmt.dateTime(DateTime.parse(e['at']! as String)), style: AppType.caption),
                    ),
                    SizedBox(
                      width: 120,
                      child: Text(e['actor']! as String, style: AppType.caption, overflow: TextOverflow.ellipsis),
                    ),
                    Expanded(
                      child: Text(
                        '${e['action']} · ${e['kind']}/${e['id']}',
                        style: AppType.small,
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}
