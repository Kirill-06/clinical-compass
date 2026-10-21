import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/tokens.dart';

/// Знак продукта: стрелка компаса, нарисованная кодом.
class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.size = 28});

  final double size;

  @override
  Widget build(BuildContext context) => ExcludeSemantics(
    child: SizedBox.square(
      dimension: size,
      child: CustomPaint(painter: _BrandPainter()),
    ),
  );
}

class _BrandPainter extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final r = size.width / 2;
    canvas.drawRRect(
      RRect.fromRectAndRadius(Offset.zero & size, Radius.circular(size.width * 0.22)),
      Paint()..color = AppColors.accent,
    );
    final north = Path()
      ..moveTo(r, r * 0.38)
      ..lineTo(r * 1.26, r)
      ..lineTo(r * 0.74, r)
      ..close();
    final south = Path()
      ..moveTo(r, r * 1.62)
      ..lineTo(r * 1.26, r)
      ..lineTo(r * 0.74, r)
      ..close();
    canvas.drawPath(north, Paint()..color = Colors.white);
    canvas.drawPath(south, Paint()..color = Colors.white.withValues(alpha: 0.45));
    canvas.drawCircle(Offset(r, r), r * 0.09, Paint()..color = AppColors.accent);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Метка демо-режима в шапке страниц.
class DemoModeStrip extends StatelessWidget {
  const DemoModeStrip({super.key});

  @override
  Widget build(BuildContext context) => Row(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
        decoration: const BoxDecoration(color: AppColors.demoBg, borderRadius: Radii.smAll),
        child: const Text(
          'ДЕМО',
          style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, letterSpacing: 0.6, color: AppColors.demoFg),
        ),
      ),
      const SizedBox(width: Space.x2),
      const Flexible(
        child: Text(
          'Вымышленные данные · демо-вход без пароля',
          style: TextStyle(fontSize: 12, color: AppColors.textMuted),
          overflow: TextOverflow.ellipsis,
        ),
      ),
    ],
  );
}
