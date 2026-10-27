import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/shared/prescription_tile.dart';

/// Препараты, которые врач выписал пациенту. Активные пациент видит на вкладке «Приём».
class PrescriptionsPanel extends StatefulWidget {
  const PrescriptionsPanel({super.key, required this.patientId, required this.prescriptions});

  final String patientId;
  final List<Json> prescriptions;

  @override
  State<PrescriptionsPanel> createState() => _PrescriptionsPanelState();
}

class _PrescriptionsPanelState extends State<PrescriptionsPanel> {
  bool _showCancelled = false;

  @override
  Widget build(BuildContext context) {
    final active = widget.prescriptions.where((p) => p['cancelled_at'] == null).toList();
    final cancelled = widget.prescriptions.where((p) => p['cancelled_at'] != null).toList();
    return Panel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          SectionHeader(
            title: 'Назначения',
            subtitle: 'Пациент видит активные назначения списком для аптеки',
            level: 2,
            trailing: FilledButton.tonalIcon(
              onPressed: () => unawaited(_prescribe(context)),
              icon: const Icon(Icons.add, size: 18),
              label: const Text('Назначить'),
            ),
          ),
          const SizedBox(height: Space.x2),
          if (active.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: Space.x3),
              child: Text('Активных назначений нет.', style: AppType.bodySecondary),
            ),
          for (final (i, rx) in active.indexed) ...[
            if (i > 0) const Divider(),
            PrescriptionTile(
              rx: rx,
              trailing: IconButton(
                tooltip: 'Отменить назначение ${rx['drug']}',
                icon: const Icon(Icons.close, size: 18),
                onPressed: () => unawaited(_cancel(context, rx)),
              ),
            ),
          ],
          if (cancelled.isNotEmpty) ...[
            const SizedBox(height: Space.x2),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton(
                onPressed: () => setState(() => _showCancelled = !_showCancelled),
                child: Text(_showCancelled ? 'Скрыть отменённые' : 'Отменённые: ${cancelled.length}'),
              ),
            ),
            if (_showCancelled)
              for (final rx in cancelled) PrescriptionTile(rx: rx),
          ],
        ],
      ),
    );
  }

  Future<void> _prescribe(BuildContext context) async {
    final draft = await showDialog<_Draft>(context: context, builder: (_) => const _PrescribeDialog());
    if (draft == null || !context.mounted) return;
    await runDoctorAction(
      context,
      () => context.api.prescribe(
        widget.patientId,
        drug: draft.drug,
        dosage: draft.dosage,
        regimen: draft.regimen,
        duration: draft.duration,
        note: draft.note,
      ),
      'Назначение сохранено — пациент видит его в приложении',
    );
  }

  Future<void> _cancel(BuildContext context, Json rx) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Отменить ${rx['drug']}?'),
        content: const Text('Препарат пропадёт из списка пациента. В карточке он останется в отменённых.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Не отменять')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Отменить назначение')),
        ],
      ),
    );
    if (ok != true || !context.mounted) return;
    await runDoctorAction(context, () => context.api.cancelPrescription(rx['id']! as String), 'Назначение отменено');
  }
}

typedef _Draft = ({String drug, String dosage, String regimen, String? duration, String? note});

class _PrescribeDialog extends StatefulWidget {
  const _PrescribeDialog();

  @override
  State<_PrescribeDialog> createState() => _PrescribeDialogState();
}

class _PrescribeDialogState extends State<_PrescribeDialog> {
  final _drug = TextEditingController();
  final _dosage = TextEditingController();
  final _regimen = TextEditingController();
  final _duration = TextEditingController();
  final _note = TextEditingController();
  bool _tried = false;

  @override
  void dispose() {
    for (final c in [_drug, _dosage, _regimen, _duration, _note]) {
      c.dispose();
    }
    super.dispose();
  }

  String? _required(TextEditingController c) => _tried && c.text.trim().isEmpty ? 'Заполните поле' : null;

  String? _optional(TextEditingController c) => c.text.trim().isEmpty ? null : c.text.trim();

  void _submit() {
    setState(() => _tried = true);
    if ([_drug, _dosage, _regimen].any((c) => c.text.trim().isEmpty)) return;
    Navigator.pop<_Draft>(context, (
      drug: _drug.text.trim(),
      dosage: _dosage.text.trim(),
      regimen: _regimen.text.trim(),
      duration: _optional(_duration),
      note: _optional(_note),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Назначить препарат'),
      content: SizedBox(
        width: 460,
        child: SingleChildScrollView(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: _drug,
                autofocus: true,
                maxLength: 200,
                textCapitalization: TextCapitalization.sentences,
                decoration: InputDecoration(labelText: 'Препарат', counterText: '', errorText: _required(_drug)),
              ),
              const SizedBox(height: Space.x3),
              TextField(
                controller: _dosage,
                maxLength: 200,
                decoration: InputDecoration(
                  labelText: 'Дозировка',
                  hintText: 'Например, 1 таблетка 50 мг',
                  counterText: '',
                  errorText: _required(_dosage),
                ),
              ),
              const SizedBox(height: Space.x3),
              TextField(
                controller: _regimen,
                maxLength: 300,
                decoration: InputDecoration(
                  labelText: 'Как принимать',
                  hintText: 'Например, 2 раза в день после еды',
                  counterText: '',
                  errorText: _required(_regimen),
                ),
              ),
              const SizedBox(height: Space.x3),
              TextField(
                controller: _duration,
                maxLength: 100,
                decoration: const InputDecoration(
                  labelText: 'Срок (необязательно)',
                  hintText: 'Например, 4 недели',
                  counterText: '',
                ),
              ),
              const SizedBox(height: Space.x3),
              TextField(
                controller: _note,
                maxLength: 1000,
                minLines: 2,
                maxLines: 4,
                decoration: const InputDecoration(labelText: 'Комментарий для пациента (необязательно)'),
              ),
            ],
          ),
        ),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: const Text('Отмена')),
        FilledButton(onPressed: _submit, child: const Text('Назначить')),
      ],
    );
  }
}
