import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';
import 'package:clinical_compass/presentation/shared/notices.dart';

/// Отметка приёма за сегодня по слотам схемы (утро/вечер).
/// Пропуск требует причины — она нужна врачу и правилам (§7).
class TodayIntakePanel extends StatelessWidget {
  const TodayIntakePanel({super.key, required this.patientId, required this.plan, required this.today});

  final String patientId;
  final Json plan;
  final Json today;

  @override
  Widget build(BuildContext context) {
    final slots = (today['slots']! as List).cast<Map>();
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SectionHeader(title: 'Приём препарата сегодня', level: 2),
          const SizedBox(height: Space.x1),
          Text('${plan['drug']} · ${plan['instructions']}', style: AppType.small),
          const SizedBox(height: Space.x3),
          for (final (i, s) in slots.indexed) ...[
            if (i > 0) const Divider(),
            _SlotRow(patientId: patientId, date: today['date']! as String, slot: s.cast<String, Object?>()),
          ],
          const SizedBox(height: Space.x2),
          const Text('Отметку за сегодня можно исправить. Схему приёма меняет только врач.', style: AppType.caption),
        ],
      ),
    );
  }
}

class _SlotRow extends StatefulWidget {
  const _SlotRow({required this.patientId, required this.date, required this.slot});

  final String patientId;
  final String date;
  final Json slot;

  @override
  State<_SlotRow> createState() => _SlotRowState();
}

class _SlotRowState extends State<_SlotRow> {
  bool _busy = false;

  Future<void> _mark(IntakeStatus status) async {
    MissedReason? reason;
    if (status == IntakeStatus.missed) {
      reason = await _askReason(context);
      if (reason == null) return;
    }
    if (!mounted) return;
    final api = context.api;
    final messenger = ScaffoldMessenger.of(context);
    setState(() => _busy = true);
    try {
      final r = await api.markIntake(
        widget.patientId,
        slotDate: widget.date,
        slot: IntakeSlot.fromWire(widget.slot['slot']! as String),
        status: status,
        reason: reason,
      );
      final notices = [for (final n in (r['patient_notices'] as List? ?? const [])) asJson(n)];
      if (notices.isNotEmpty && mounted) await _showNotices(context, notices);
    } on Exception catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Отметка не сохранена: ${describeError(e)}')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final intake = widget.slot['intake'] is Map ? asJson(widget.slot['intake']) : null;
    final status = intake == null ? IntakeStatus.unknown : IntakeStatus.fromWire(intake['status']! as String);
    final (tone, icon, label) = intakeVisual(status);
    final reason = intake?['missed_reason'] == null ? null : MissedReason.fromWire(intake!['missed_reason']! as String);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Space.x3),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Wrap(
            spacing: Space.x3,
            runSpacing: Space.x1,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              Text(widget.slot['label']! as String, style: AppType.bodyStrong),
              StatusBadge(label: intake == null ? 'Ещё не отмечено' : label, tone: tone, icon: icon, dense: true),
              if (intake?['marked_at'] != null)
                Text('в ${Fmt.time(DateTime.parse(intake!['marked_at']! as String))}', style: AppType.caption),
            ],
          ),
          if (reason != null) Text('Причина: ${context.meta.missedReason(reason).toLowerCase()}', style: AppType.small),
          const SizedBox(height: Space.x2),
          Row(
            children: [
              Expanded(
                child: _Choice(
                  label: 'Принял',
                  icon: Icons.check,
                  selected: status == IntakeStatus.taken,
                  onPressed: _busy ? null : () => unawaited(_mark(IntakeStatus.taken)),
                ),
              ),
              const SizedBox(width: Space.x3),
              Expanded(
                child: _Choice(
                  label: 'Пропустил',
                  icon: Icons.close,
                  selected: status == IntakeStatus.missed,
                  onPressed: _busy ? null : () => unawaited(_mark(IntakeStatus.missed)),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Choice extends StatelessWidget {
  const _Choice({required this.label, required this.icon, required this.selected, required this.onPressed});

  final String label;
  final IconData icon;
  final bool selected;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final child = Row(
      mainAxisAlignment: MainAxisAlignment.center,
      mainAxisSize: MainAxisSize.min,
      children: [
        Icon(icon, size: 18),
        const SizedBox(width: Space.x2),
        Flexible(child: Text(label, overflow: TextOverflow.ellipsis)),
      ],
    );
    return Semantics(
      selected: selected,
      child: SizedBox(
        height: 48,
        child: selected
            ? FilledButton(onPressed: onPressed, child: child)
            : OutlinedButton(onPressed: onPressed, child: child),
      ),
    );
  }
}

Future<MissedReason?> _askReason(BuildContext context) => showModalBottomSheet<MissedReason>(
  context: context,
  isScrollControlled: true,
  builder: (ctx) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(Space.x4, 0, Space.x4, Space.x4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text('Почему приём пропущен?', style: AppType.sectionTitle),
          const SizedBox(height: Space.x1),
          const Text('Ответ увидит ваш врач.', style: AppType.small),
          const SizedBox(height: Space.x3),
          for (final r in MissedReason.values.where((r) => r != MissedReason.unknown))
            Padding(
              padding: const EdgeInsets.only(bottom: Space.x2),
              child: OutlinedButton(
                style: OutlinedButton.styleFrom(
                  alignment: Alignment.centerLeft,
                  minimumSize: const Size.fromHeight(48),
                ),
                onPressed: () => Navigator.pop(ctx, r),
                child: Text(ctx.meta.missedReason(r)),
              ),
            ),
        ],
      ),
    ),
  ),
);

Future<void> _showNotices(BuildContext context, List<Json> notices) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  builder: (ctx) => SafeArea(
    child: SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(Space.x4, 0, Space.x4, Space.x4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          NoticeList(notices: notices),
          FilledButton(onPressed: () => Navigator.pop(ctx), child: const Text('Понятно')),
        ],
      ),
    ),
  ),
);
