import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/shared/brand.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

/// Только закреплённые за врачом пациенты (фильтрует сервер).
class PatientsScreen extends StatefulWidget {
  const PatientsScreen({super.key});

  @override
  State<PatientsScreen> createState() => _PatientsScreenState();
}

class _PatientsScreenState extends State<PatientsScreen> {
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final user = context.user;
    return LiveFuture<List<Json>>(
      reloadKey: user.id,
      pollEvery: const Duration(seconds: 30),
      loadingLabel: 'Загружаем пациентов…',
      load: () => context.api.doctorPatients(),
      builder: (context, rows) {
        final q = _search.text.trim().toLowerCase();
        final visible = rows.where((r) {
          final p = asJson(r['patient']);
          return q.isEmpty || '${p['full_name']} ${p['display_id']}'.toLowerCase().contains(q);
        }).toList();
        final now = context.services.clock.now();
        return SingleChildScrollView(
          padding: doctorPagePadding(context),
          child: ContentWidth(
            maxWidth: 1400,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const DemoModeStrip(),
                const SizedBox(height: Space.x3),
                PageHeader(
                  title: 'Пациенты',
                  subtitle:
                      'Закреплённые за вами · ${Fmt.weekdayLong(now)}, ${Fmt.dateLong(now)} · сортировка по приоритету в очереди',
                ),
                const SizedBox(height: Space.x4),
                Align(
                  alignment: Alignment.centerLeft,
                  child: SizedBox(
                    width: 320,
                    child: TextField(
                      controller: _search,
                      onChanged: (_) => setState(() {}),
                      decoration: const InputDecoration(
                        hintText: 'Поиск по фамилии или ID',
                        prefixIcon: Icon(Icons.search, size: 20),
                        prefixIconConstraints: BoxConstraints(minWidth: 40, minHeight: 40),
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: Space.x4),
                if (rows.isEmpty)
                  const Panel(
                    child: EmptyState(icon: Icons.group_off_outlined, title: 'За вами пока не закреплены пациенты'),
                  )
                else if (visible.isEmpty)
                  Panel(
                    child: EmptyState(
                      icon: Icons.search_off,
                      title: 'Ничего не найдено по запросу «${_search.text.trim()}»',
                    ),
                  )
                else
                  _Table(rows: visible, now: now),
                const SizedBox(height: Space.x3),
                const Text('Баллы и изменения показаны без клинической интерпретации.', style: AppType.caption),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Table extends StatelessWidget {
  const _Table({required this.rows, required this.now});

  final List<Json> rows;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (context, c) {
        final wide = c.maxWidth >= 980;
        return DecoratedBox(
          decoration: BoxDecoration(
            color: AppColors.surface,
            borderRadius: Radii.mdAll,
            border: Border.all(color: AppColors.border),
          ),
          child: ClipRRect(
            borderRadius: Radii.mdAll,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                if (wide)
                  Container(
                    color: AppColors.surfaceSubtle,
                    padding: const EdgeInsets.symmetric(horizontal: Space.x4, vertical: Space.x2 + 2),
                    child: const Row(
                      children: [
                        Expanded(flex: 18, child: Text('Пациент', style: AppType.columnHeader)),
                        Expanded(flex: 13, child: Text('GAD-7', style: AppType.columnHeader)),
                        Expanded(flex: 13, child: Text('PHQ-9', style: AppType.columnHeader)),
                        Expanded(flex: 15, child: Text('Приём, 7 дней', style: AppType.columnHeader)),
                        Expanded(flex: 13, child: Text('Опросники', style: AppType.columnHeader)),
                        Expanded(flex: 20, child: Text('Очередь', style: AppType.columnHeader)),
                        SizedBox(width: 20),
                      ],
                    ),
                  ),
                for (final (i, r) in rows.indexed) ...[
                  if (i > 0 || wide) const Divider(),
                  _Row(row: r, wide: wide, now: now),
                ],
              ],
            ),
          ),
        );
      },
    );
  }
}

class _Row extends StatelessWidget {
  const _Row({required this.row, required this.wide, required this.now});

  final Json row;
  final bool wide;
  final DateTime now;

  @override
  Widget build(BuildContext context) {
    final p = asJson(row['patient']);
    final unread = row['unread_messages'] as int? ?? 0;
    final cells = <Widget>[
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(p['full_name']! as String, style: AppType.bodyStrong, maxLines: 2, overflow: TextOverflow.ellipsis),
          Text('${p['display_id']} · ${p['birth_year']} г. р.', style: AppType.numericSmall),
          if (unread > 0) ...[
            const SizedBox(height: Space.x1),
            StatusBadge(
              label: 'Новых сообщений: $unread',
              tone: StatusTone.accent,
              icon: Icons.mark_chat_unread_outlined,
              dense: true,
            ),
          ],
        ],
      ),
      _Score(data: row['GAD7'] is Map ? asJson(row['GAD7']) : null),
      _Score(data: row['PHQ9'] is Map ? asJson(row['PHQ9']) : null, phq: true),
      _Adherence(data: row['adherence_7d'] is Map ? asJson(row['adherence_7d']) : null),
      _Schedules(list: [for (final s in row['schedules'] as List? ?? const []) asJson(s)]),
      _TopAlert(row: row),
    ];
    final link = Semantics(
      button: true,
      label: '${p['full_name']}, открыть карточку',
      child: Material(
        color: AppColors.surface,
        child: InkWell(
          hoverColor: AppColors.accentSofter,
          onTap: () => context.go('/doctor/patients/${p['id']}'),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: Space.x4, vertical: Space.x3),
            child: wide
                ? Row(
                    children: [
                      for (final (i, c) in cells.indexed)
                        Expanded(
                          flex: const [18, 13, 13, 15, 13, 20][i],
                          child: Padding(
                            padding: const EdgeInsets.only(right: Space.x3),
                            child: c,
                          ),
                        ),
                      const Icon(Icons.chevron_right, size: 20, color: AppColors.textMuted),
                    ],
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(child: cells[0]),
                          const Icon(Icons.chevron_right, color: AppColors.textMuted),
                        ],
                      ),
                      const SizedBox(height: Space.x2),
                      cells[5],
                      const SizedBox(height: Space.x2),
                      Wrap(
                        spacing: Space.x6,
                        runSpacing: Space.x3,
                        children: [
                          _Labeled('GAD-7', cells[1]),
                          _Labeled('PHQ-9', cells[2]),
                          _Labeled('Приём, 7 дней', cells[3]),
                        ],
                      ),
                    ],
                  ),
          ),
        ),
      ),
    );
    return link;
  }
}

class _Labeled extends StatelessWidget {
  const _Labeled(this.label, this.child);

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) => ConstrainedBox(
    constraints: const BoxConstraints(minWidth: 110, maxWidth: 220),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: AppType.caption),
        child,
      ],
    ),
  );
}

class _Score extends StatelessWidget {
  const _Score({required this.data, this.phq = false});

  final Json? data;
  final bool phq;

  @override
  Widget build(BuildContext context) {
    final d = data;
    if (d == null) return const Text('Нет данных', style: AppType.small);
    final delta = d['delta_from_previous'] as int?;
    final item9 = d['phq9_item9'] as int?;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text.rich(
          TextSpan(
            children: [
              TextSpan(text: '${d['score']}', style: AppType.numeric),
              TextSpan(text: ' / ${d['max_score']}', style: AppType.small),
              if (delta != null) TextSpan(text: '   ${signed(delta)}', style: AppType.numeric.copyWith(fontSize: 14)),
            ],
          ),
        ),
        Text(
          [
            Fmt.dateShort(DateTime.parse(d['administered_at']! as String)),
            if (phq && item9 != null && item9 > 0) 'п. 9: $item9',
          ].join(' · '),
          style: AppType.caption.copyWith(color: phq && (item9 ?? 0) > 0 ? AppColors.dangerFg : null),
        ),
      ],
    );
  }
}

class _Adherence extends StatelessWidget {
  const _Adherence({required this.data});

  final Json? data;

  @override
  Widget build(BuildContext context) {
    final d = data;
    if (d == null) return const Text('Нет плана', style: AppType.small);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(percent(d['adherence'] as num?), style: AppType.numeric),
        Text('пропущено ${d['missed']} · без отметки ${d['unknown']}', style: AppType.caption),
      ],
    );
  }
}

class _Schedules extends StatelessWidget {
  const _Schedules({required this.list});

  final List<Json> list;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (final s in list)
          Text(
            '${s['label']}: ${s['due_status'] == 'upcoming' ? Fmt.dateShort(DateTime.parse(s['next_due_at']! as String)) : dueLabel(s['due_status']! as String).toLowerCase()}',
            style: AppType.small,
          ),
      ],
    );
  }
}

class _TopAlert extends StatelessWidget {
  const _TopAlert({required this.row});

  final Json row;

  @override
  Widget build(BuildContext context) {
    final top = row['top_alert'] is Map ? asJson(row['top_alert']) : null;
    if (top == null) {
      return const StatusBadge(label: 'Нет открытых событий', tone: StatusTone.ok, icon: Icons.check, dense: true);
    }
    final a = asJson(top['alert']);
    final count = row['open_alerts'] as int? ?? 1;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: Space.x2,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            priorityBadge(DoctorPriority.fromWire(a['doctor_priority']! as String)),
            if (count > 1) Text('+${count - 1}', style: AppType.caption),
          ],
        ),
        const SizedBox(height: 2),
        Text(top['rule_title']! as String, style: AppType.caption, maxLines: 2, overflow: TextOverflow.ellipsis),
      ],
    );
  }
}
