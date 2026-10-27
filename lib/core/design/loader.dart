import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/tokens.dart';

/// Фирменный индикатор загрузки: стрелка компаса поворачивается и замирает.
/// Тот же рисунок показывает `web/index.html`, пока Flutter ещё не запустился.
///
/// [badge] — со значком-квадратом, как в логотипе; без него рисуется одна стрелка
/// цвета [color] (для кнопок).
class CompassSpinner extends StatefulWidget {
  const CompassSpinner({super.key, this.size = 40, this.badge = true, this.color});

  final double size;
  final bool badge;
  final Color? color;

  @override
  State<CompassSpinner> createState() => _CompassSpinnerState();
}

class _CompassSpinnerState extends State<CompassSpinner> with SingleTickerProviderStateMixin {
  static const _period = Duration(milliseconds: 1600);
  static final _turn = CurveTween(curve: const Interval(0, 0.7, curve: Curves.easeInOutCubic));

  late final AnimationController _c = AnimationController(vsync: this, duration: _period);

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (MediaQuery.disableAnimationsOf(context)) {
      _c.stop();
    } else if (!_c.isAnimating) {
      _c.repeat();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final color = widget.color ?? IconTheme.of(context).color ?? AppColors.accent;
    return ExcludeSemantics(
      child: SizedBox.square(
        dimension: widget.size,
        child: AnimatedBuilder(
          animation: _c,
          builder: (context, _) => CustomPaint(
            painter: _CompassPainter(angle: _turn.transform(_c.value) * math.pi * 2, badge: widget.badge, color: color),
          ),
        ),
      ),
    );
  }
}

class _CompassPainter extends CustomPainter {
  _CompassPainter({required this.angle, required this.badge, required this.color});

  final double angle;
  final bool badge;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final r = size.width / 2;
    final needle = badge ? Colors.white : color;
    if (badge) {
      canvas.drawRRect(
        RRect.fromRectAndRadius(Offset.zero & size, Radius.circular(size.width * 0.22)),
        Paint()..color = AppColors.accent,
      );
    }
    final reach = badge ? 0.62 : 0.9;
    final half = badge ? 0.26 : 0.34;
    canvas
      ..save()
      ..translate(r, r)
      ..rotate(angle);
    final north = Path()
      ..moveTo(0, -r * reach)
      ..lineTo(r * half, 0)
      ..lineTo(-r * half, 0)
      ..close();
    final south = Path()
      ..moveTo(0, r * reach)
      ..lineTo(r * half, 0)
      ..lineTo(-r * half, 0)
      ..close();
    canvas
      ..drawPath(north, Paint()..color = needle)
      ..drawPath(south, Paint()..color = needle.withValues(alpha: 0.45))
      ..restore();
    if (badge) canvas.drawCircle(Offset(r, r), r * 0.09, Paint()..color = AppColors.accent);
  }

  @override
  bool shouldRepaint(_CompassPainter old) => old.angle != angle || old.color != color || old.badge != badge;
}

/// Экран целиком на время первой загрузки — продолжение HTML-заставки из `web/index.html`.
class SplashLoader extends StatelessWidget {
  const SplashLoader({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) => ColoredBox(
    color: AppColors.canvas,
    child: Center(
      child: Semantics(
        label: label,
        liveRegion: true,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CompassSpinner(size: 56),
            const SizedBox(height: Space.x4),
            const Text(
              'Клинический компас',
              style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600, color: AppColors.text),
            ),
            const SizedBox(height: Space.x1),
            Text(label, style: const TextStyle(fontSize: 14, color: AppColors.textMuted)),
          ],
        ),
      ),
    ),
  );
}
