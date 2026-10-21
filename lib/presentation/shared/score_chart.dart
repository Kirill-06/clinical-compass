import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';
import 'package:clinical_compass/core/format/fmt.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/domain/meta.dart';

class ScorePoint {
  const ScorePoint({required this.at, required this.score, required this.label, this.id});

  final DateTime at;
  final int score;
  final String label;
  final String? id;
}

/// График шкалы по датам реальных измерений. Y — полный диапазон шкалы,
/// X — время; промежуточные значения не достраиваются.
class ScoreChart extends StatefulWidget {
  const ScoreChart({super.key, required this.points, required this.definition, this.height = 220, this.onOpen});

  final List<ScorePoint> points;
  final InstrumentDefinition definition;
  final double height;
  final ValueChanged<ScorePoint>? onOpen;

  @override
  State<ScoreChart> createState() => _ScoreChartState();
}

class _ScoreChartState extends State<ScoreChart> {
  int? _active;
  bool _focused = false;
  static const _left = 32.0;
  static const _top = 12.0;
  static const _bottom = 28.0;

  double _right(double w) => w >= 520 ? 112 : 12;

  List<Offset> _offsets(Size size) {
    final pts = widget.points;
    if (pts.isEmpty) return const [];
    final plotW = size.width - _left - _right(size.width);
    final plotH = size.height - _top - _bottom;
    final min = pts.first.at.millisecondsSinceEpoch.toDouble();
    final span = pts.last.at.millisecondsSinceEpoch - min;
    const inset = 18.0;
    return [
      for (final p in pts)
        Offset(
          span == 0
              ? _left + plotW / 2
              : _left + inset + (p.at.millisecondsSinceEpoch - min) / span * (plotW - inset * 2),
          _top + plotH - p.score / widget.definition.maxScore * plotH,
        ),
    ];
  }

  int? _nearest(Offset local, Size size) {
    final pts = _offsets(size);
    int? best;
    var d = double.infinity;
    for (var i = 0; i < pts.length; i++) {
      final x = (pts[i].dx - local.dx).abs();
      if (x < d) {
        d = x;
        best = i;
      }
    }
    return d <= 40 ? best : null;
  }

  KeyEventResult _onKey(FocusNode node, KeyEvent e) {
    if (e is! KeyDownEvent && e is! KeyRepeatEvent) return KeyEventResult.ignored;
    final n = widget.points.length;
    if (n == 0) return KeyEventResult.ignored;
    final cur = _active ?? n - 1;
    if (e.logicalKey == LogicalKeyboardKey.arrowRight) {
      setState(() => _active = math.min(n - 1, cur + 1));
      return KeyEventResult.handled;
    }
    if (e.logicalKey == LogicalKeyboardKey.arrowLeft) {
      setState(() => _active = math.max(0, cur - 1));
      return KeyEventResult.handled;
    }
    if ((e.logicalKey == LogicalKeyboardKey.enter || e.logicalKey == LogicalKeyboardKey.space) &&
        widget.onOpen != null) {
      widget.onOpen!(widget.points[cur]);
      return KeyEventResult.handled;
    }
    return KeyEventResult.ignored;
  }

  @override
  Widget build(BuildContext context) {
    final pts = widget.points;
    final summary = pts.map((p) => '${Fmt.date(p.at)}: ${p.score}, ${p.label}').join('; ');
    return Semantics(
      label: 'График ${widget.definition.instrument.label}. $summary',
      child: Focus(
        onKeyEvent: _onKey,
        onFocusChange: (f) => setState(() {
          _focused = f;
          if (f) _active ??= pts.isEmpty ? null : pts.length - 1;
        }),
        child: SizedBox(
          height: widget.height,
          child: LayoutBuilder(
            builder: (context, c) {
              final size = Size(c.maxWidth, widget.height);
              final offsets = _offsets(size);
              final active = _active;
              return MouseRegion(
                onHover: (e) => setState(() => _active = _nearest(e.localPosition, size)),
                onExit: (_) => setState(() {
                  if (!_focused) _active = null;
                }),
                child: GestureDetector(
                  behavior: HitTestBehavior.opaque,
                  onTapUp: (d) {
                    final i = _nearest(d.localPosition, size);
                    if (i == null) {
                      setState(() => _active = null);
                    } else if (i == _active && widget.onOpen != null) {
                      widget.onOpen!(pts[i]);
                    } else {
                      setState(() => _active = i);
                    }
                  },
                  child: Stack(
                    clipBehavior: Clip.none,
                    children: [
                      CustomPaint(
                        size: size,
                        painter: _Painter(
                          points: pts,
                          offsets: offsets,
                          definition: widget.definition,
                          active: active,
                          right: _right(size.width),
                          focused: _focused,
                        ),
                      ),
                      if (active != null && active < offsets.length) _tooltip(offsets[active], size.width, pts[active]),
                    ],
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _tooltip(Offset anchor, double width, ScorePoint p) {
    const w = 196.0;
    final left = (anchor.dx - w / 2).clamp(0.0, math.max(0.0, width - w)).toDouble();
    final above = anchor.dy > 90;
    return Positioned(
      left: left,
      top: above ? anchor.dy - 84 : anchor.dy + 14,
      width: w,
      child: IgnorePointer(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: Space.x3, vertical: Space.x2),
          decoration: const BoxDecoration(color: AppColors.demoBg, borderRadius: Radii.smAll),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(Fmt.dateTime(p.at), style: const TextStyle(color: Color(0xFFC9D1DA), fontSize: 12)),
              Text(
                '${p.score} из ${widget.definition.maxScore} · ${p.label}',
                style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w600),
              ),
              if (widget.onOpen != null)
                const Text('Нажмите ещё раз — ответы', style: TextStyle(color: Color(0xFFC9D1DA), fontSize: 11)),
            ],
          ),
        ),
      ),
    );
  }
}

class _Painter extends CustomPainter {
  _Painter({
    required this.points,
    required this.offsets,
    required this.definition,
    required this.active,
    required this.right,
    required this.focused,
  });

  final List<ScorePoint> points;
  final List<Offset> offsets;
  final InstrumentDefinition definition;
  final int? active;
  final double right;
  final bool focused;

  @override
  void paint(Canvas canvas, Size size) {
    const left = 32.0;
    final plot = Rect.fromLTRB(left, 12, size.width - right, size.height - 28);
    final max = definition.maxScore.toDouble();
    double y(num s) => plot.bottom - s / max * plot.height;
    final bands = definition.bands;
    for (final (i, b) in bands.indexed) {
      final top = y(i == bands.length - 1 ? b.max : b.max + 1);
      final rect = Rect.fromLTRB(plot.left, top, plot.right, y(b.min));
      if (i.isOdd) canvas.drawRect(rect, Paint()..color = AppColors.chartBandAlt);
      if (right > 20 && rect.height >= 14) {
        _text(
          canvas,
          '${b.label} ${b.min}–${b.max}',
          Offset(plot.right + 8, rect.center.dy - 7),
          AppType.caption.copyWith(fontSize: 11),
          width: right - 10,
        );
      }
    }
    final grid = Paint()
      ..color = AppColors.chartGrid
      ..strokeWidth = 1;
    for (final t in {0, for (final b in bands.skip(1)) b.min, definition.maxScore}) {
      canvas.drawLine(Offset(plot.left, y(t)), Offset(plot.right, y(t)), grid);
      _text(canvas, '$t', Offset(0, y(t) - 8), AppType.caption, width: left - 8, align: TextAlign.right);
    }
    canvas.drawLine(plot.bottomLeft, plot.bottomRight, Paint()..color = AppColors.borderStrong);
    if (offsets.isEmpty) return;
    var lastRight = -1000.0;
    for (var i = 0; i < offsets.length; i++) {
      final x = offsets[i].dx;
      if (x - 30 < lastRight + 6) continue;
      _text(
        canvas,
        Fmt.dateShort(points[i].at),
        Offset(x - 30, plot.bottom + 8),
        AppType.caption,
        width: 60,
        align: TextAlign.center,
      );
      lastRight = x + 30;
    }
    if (offsets.length > 1) {
      final path = Path()..moveTo(offsets.first.dx, offsets.first.dy);
      for (final o in offsets.skip(1)) {
        path.lineTo(o.dx, o.dy);
      }
      canvas.drawPath(
        path,
        Paint()
          ..color = AppColors.chartLine
          ..strokeWidth = 2
          ..style = PaintingStyle.stroke,
      );
    }
    for (var i = 0; i < offsets.length; i++) {
      final on = i == active;
      canvas.drawCircle(offsets[i], on ? 6.5 : 4.5, Paint()..color = AppColors.surface);
      canvas.drawCircle(
        offsets[i],
        on ? 6.5 : 4.5,
        Paint()
          ..color = AppColors.chartLine
          ..style = PaintingStyle.stroke
          ..strokeWidth = 2,
      );
      if (on && focused) {
        canvas.drawCircle(
          offsets[i],
          10,
          Paint()
            ..color = AppColors.focusRing
            ..style = PaintingStyle.stroke
            ..strokeWidth = 2,
        );
      }
    }
  }

  void _text(Canvas c, String s, Offset at, TextStyle style, {double? width, TextAlign align = TextAlign.left}) {
    final tp = TextPainter(
      text: TextSpan(text: s, style: style),
      textDirection: TextDirection.ltr,
      textAlign: align,
      maxLines: 1,
      ellipsis: '…',
    )..layout(minWidth: width ?? 0, maxWidth: width ?? 200);
    tp.paint(c, at);
  }

  @override
  bool shouldRepaint(covariant _Painter old) =>
      old.points != points || old.active != active || old.focused != focused || old.right != right;
}

/// Точки графика из ответов сервера (по возрастанию даты).
List<ScorePoint> pointsFrom(List<Json> responses, Instrument instrument) {
  final list = responses.where((r) => r['instrument'] == instrument.wire && r['total_score'] != null).toList()
    ..sort((a, b) => (a['administered_at']! as String).compareTo(b['administered_at']! as String));
  return [
    for (final r in list)
      ScorePoint(
        id: r['id'] as String?,
        at: DateTime.parse(r['administered_at']! as String),
        score: r['total_score']! as int,
        label: (r['severity_label'] as String?) ?? '',
      ),
  ];
}
