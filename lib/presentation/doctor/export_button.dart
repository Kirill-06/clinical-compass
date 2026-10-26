import 'dart:async';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/live_future.dart';

/// Обезличенная таблица по пациентам врача (CSV) — для анализа, в том числе фармкомпанией.
class ExportPatientsButton extends StatefulWidget {
  const ExportPatientsButton({super.key});

  @override
  State<ExportPatientsButton> createState() => _ExportPatientsButtonState();
}

class _ExportPatientsButtonState extends State<ExportPatientsButton> {
  bool _busy = false;

  Future<void> _export() async {
    final api = context.api;
    final messenger = ScaffoldMessenger.of(context);
    final today = dateKey(context.services.clock.now());
    setState(() => _busy = true);
    try {
      final bytes = await api.exportPatientsCsv();
      final saved = await FilePicker.saveFile(
        fileName: 'clinical-compass-patients-$today.csv',
        bytes: bytes,
        mimeType: 'text/csv',
      );
      if (saved != null) {
        messenger.showSnackBar(const SnackBar(content: Text('Таблица сохранена: без ФИО и телефонов пациентов')));
      }
    } on Exception catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('Не удалось выгрузить: ${describeError(e)}')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Tooltip(
    message: 'CSV для Excel: шкалы, приём препарата, побочные эффекты. Без ФИО и телефонов.',
    child: OutlinedButton.icon(
      onPressed: _busy ? null : () => unawaited(_export()),
      icon: const Icon(Icons.table_view_outlined, size: 18),
      label: Text(_busy ? 'Готовим таблицу…' : 'Выгрузить таблицу'),
    ),
  );
}
