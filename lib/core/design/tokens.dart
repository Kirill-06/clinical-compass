import 'package:flutter/material.dart';

/// Цветовые токены. Нейтральная палитра + один сине-зелёный акцент.
/// Красный/янтарный/зелёный применяются только для смысловых статусов
/// и всегда дублируются текстом и иконкой.
abstract final class AppColors {
  static const canvas = Color(0xFFF6F7F9);
  static const surface = Color(0xFFFFFFFF);
  static const surfaceSubtle = Color(0xFFF1F3F6);
  static const surfaceSunken = Color(0xFFEAEDF1);
  static const border = Color(0xFFDFE3E8);
  static const borderStrong = Color(0xFFC3CAD3);

  static const text = Color(0xFF17212B);
  static const textSecondary = Color(0xFF4F5B67);
  static const textMuted = Color(0xFF66717D);
  static const textOnAccent = Color(0xFFFFFFFF);

  static const accent = Color(0xFF0D5966);
  static const accentHover = Color(0xFF094651);
  static const accentPressed = Color(0xFF07373F);
  static const accentSoft = Color(0xFFE3EEF0);
  static const accentSofter = Color(0xFFF0F6F7);

  static const focusRing = Color(0xFF1D6FB8);

  static const okFg = Color(0xFF1C6A43);
  static const okBg = Color(0xFFE5F2EA);
  static const warnFg = Color(0xFF83500A);
  static const warnBg = Color(0xFFFBF0DC);
  static const dangerFg = Color(0xFFA42619);
  static const dangerBg = Color(0xFFFBE9E7);
  static const infoFg = Color(0xFF235A8C);
  static const infoBg = Color(0xFFE7EFF8);
  static const neutralFg = Color(0xFF46515C);
  static const neutralBg = Color(0xFFECEEF1);

  /// Маркировка демо-режима: тёмный графит, чтобы не путать со статусами.
  static const demoBg = Color(0xFF29323C);
  static const demoFg = Color(0xFFFFFFFF);
  static const demoSoft = Color(0xFFF2F0E9);
  static const demoBorder = Color(0xFF8B8576);

  static const chartLine = accent;
  static const chartGrid = Color(0xFFE6E9ED);
  static const chartBandAlt = Color(0xFFF7F8FA);
}

/// Сетка отступов 4/8.
abstract final class Space {
  static const double x1 = 4;
  static const double x2 = 8;
  static const double x3 = 12;
  static const double x4 = 16;
  static const double x5 = 20;
  static const double x6 = 24;
  static const double x8 = 32;
  static const double x10 = 40;
  static const double x12 = 48;
  static const double x16 = 64;
}

abstract final class Radii {
  static const double sm = 6;
  static const double md = 8;
  static const double lg = 10;

  static const BorderRadius smAll = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius mdAll = BorderRadius.all(Radius.circular(md));
  static const BorderRadius lgAll = BorderRadius.all(Radius.circular(lg));
}

/// Контрольные точки адаптивной вёрстки.
abstract final class Breakpoints {
  static const double compact = 600;
  static const double medium = 900;
  static const double expanded = 1200;
}

abstract final class Durations {
  static const fast = Duration(milliseconds: 120);
  static const normal = Duration(milliseconds: 200);
}

/// Минимальная интерактивная зона (WCAG 2.5.8 / Material).
const double kMinTapTarget = 44;
