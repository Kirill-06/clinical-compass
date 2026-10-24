import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/presentation/shared/labels.dart';

/// Ответы на все вопросы шкалы, итог, дельты и источник формулировок.
class ResponseDetail extends StatelessWidget {
  const ResponseDetail({super.key, required this.response});

  final Json response;

  @override
  Widget build(BuildContext context) {
    final def = context.meta.instrument(Instrument.fromWire(response['instrument']! as String));
    final items = (response['item_scores']! as List).cast<int>();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Wrap(
          spacing: Space.x8,
          runSpacing: Space.x3,
          children: [
            KeyValue(label: 'Итог', value: scoreLine(response['total_score'] as int?, def.maxScore)),
            KeyValue(label: 'Категория по шкале', value: response['severity_label'] as String? ?? '—'),
            KeyValue(label: 'Изменение от предыдущего', value: signed(response['delta_from_previous'] as int?)),
            KeyValue(label: 'От исходного', value: signed(response['delta_from_baseline'] as int?)),
            KeyValue(label: 'Дата', value: Fmt.dateTime(DateTime.parse(response['administered_at']! as String))),
          ],
        ),
        const SizedBox(height: Space.x4),
        Text(def.instruction, style: AppType.small),
        const SizedBox(height: Space.x2),
        DecoratedBox(
          decoration: BoxDecoration(
            borderRadius: Radii.mdAll,
            border: Border.all(color: AppColors.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              for (var i = 0; i < def.itemCount; i++) ...[
                if (i > 0) const Divider(),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: Space.x4, vertical: Space.x3),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('${i + 1}. ${def.items[i]}', style: AppType.body.copyWith(fontSize: 14)),
                      const SizedBox(height: 2),
                      Text(
                        i < items.length ? '${def.optionLabel(items[i]) ?? '—'} · ${items[i]}' : 'Нет ответа',
                        style: AppType.bodyStrong.copyWith(fontSize: 14),
                      ),
                    ],
                  ),
                ),
              ],
            ],
          ),
        ),
        const SizedBox(height: Space.x3),
        Text('${def.title}, версия ${def.version}. Источник: ${def.source}.', style: AppType.caption),
        if (def.wordingNote != null) Text(def.wordingNote!, style: AppType.caption),
      ],
    );
  }
}

Future<void> showResponseDialog(BuildContext context, Json response) {
  final def = context.meta.instrument(Instrument.fromWire(response['instrument']! as String));
  final title = '${def.instrument.label} от ${Fmt.date(DateTime.parse(response['administered_at']! as String))}';
  final body = ResponseDetail(response: response);
  if (MediaQuery.sizeOf(context).width < Breakpoints.compact) {
    return Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (ctx) => Scaffold(
          appBar: AppBar(title: Text(title)),
          body: SingleChildScrollView(padding: const EdgeInsets.all(Space.x4), child: body),
        ),
      ),
    );
  }
  return showDialog<void>(
    context: context,
    builder: (ctx) => Dialog(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 720, maxHeight: 760),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(Space.x6, Space.x5, Space.x3, Space.x2),
              child: Row(
                children: [
                  Expanded(child: Text(title, style: AppType.sectionTitle)),
                  IconButton(tooltip: 'Закрыть', onPressed: () => Navigator.pop(ctx), icon: const Icon(Icons.close)),
                ],
              ),
            ),
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(Space.x6, 0, Space.x6, Space.x6),
                child: body,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}
