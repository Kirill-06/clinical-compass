import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/tokens.dart';

/// Типографическая шкала. Используется системный шрифт платформы
/// (SF Pro на Apple, Roboto на Android и Web) — оба с полноценной кириллицей.
/// Числа выводятся моноширинными цифрами, чтобы колонки баллов не «прыгали».
abstract final class AppType {
  static const _tabular = [FontFeature.tabularFigures()];

  static const pageTitle = TextStyle(
    fontSize: 24,
    height: 32 / 24,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.2,
    color: AppColors.text,
  );

  static const sectionTitle = TextStyle(
    fontSize: 17,
    height: 24 / 17,
    fontWeight: FontWeight.w600,
    color: AppColors.text,
  );

  static const subsectionTitle = TextStyle(
    fontSize: 15,
    height: 22 / 15,
    fontWeight: FontWeight.w600,
    color: AppColors.text,
  );

  static const body = TextStyle(fontSize: 15, height: 22 / 15, fontWeight: FontWeight.w400, color: AppColors.text);

  static const bodyStrong = TextStyle(
    fontSize: 15,
    height: 22 / 15,
    fontWeight: FontWeight.w600,
    color: AppColors.text,
  );

  static const bodySecondary = TextStyle(
    fontSize: 15,
    height: 22 / 15,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  static const small = TextStyle(
    fontSize: 13,
    height: 18 / 13,
    fontWeight: FontWeight.w400,
    color: AppColors.textSecondary,
  );

  static const smallStrong = TextStyle(
    fontSize: 13,
    height: 18 / 13,
    fontWeight: FontWeight.w600,
    color: AppColors.text,
  );

  static const label = TextStyle(
    fontSize: 13,
    height: 18 / 13,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
  );

  /// Заголовки колонок таблиц.
  static const columnHeader = TextStyle(
    fontSize: 12,
    height: 16 / 12,
    fontWeight: FontWeight.w600,
    letterSpacing: 0.2,
    color: AppColors.textMuted,
  );

  static const caption = TextStyle(
    fontSize: 12,
    height: 16 / 12,
    fontWeight: FontWeight.w400,
    color: AppColors.textMuted,
  );

  static const numeric = TextStyle(
    fontSize: 15,
    height: 22 / 15,
    fontWeight: FontWeight.w600,
    color: AppColors.text,
    fontFeatures: _tabular,
  );

  static const numericLarge = TextStyle(
    fontSize: 32,
    height: 38 / 32,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.5,
    color: AppColors.text,
    fontFeatures: _tabular,
  );

  static const numericSmall = TextStyle(
    fontSize: 13,
    height: 18 / 13,
    fontWeight: FontWeight.w500,
    color: AppColors.textSecondary,
    fontFeatures: _tabular,
  );

  /// Крупный вопрос в опроснике (мобильный сценарий пациента).
  static const question = TextStyle(
    fontSize: 22,
    height: 30 / 22,
    fontWeight: FontWeight.w600,
    letterSpacing: -0.2,
    color: AppColors.text,
  );
}
