import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';

/// Светлая профессиональная тема. Material 3 используется как каркас
/// (доступность, фокус, семантика), но визуально переопределён:
/// умеренные радиусы, тонкие границы, без теней и тонировки поверхностей.
ThemeData buildAppTheme() {
  const scheme = ColorScheme(
    brightness: Brightness.light,
    primary: AppColors.accent,
    onPrimary: AppColors.textOnAccent,
    primaryContainer: AppColors.accentSoft,
    onPrimaryContainer: AppColors.accentPressed,
    secondary: AppColors.textSecondary,
    onSecondary: AppColors.surface,
    secondaryContainer: AppColors.surfaceSubtle,
    onSecondaryContainer: AppColors.text,
    tertiary: AppColors.infoFg,
    onTertiary: AppColors.surface,
    error: AppColors.dangerFg,
    onError: AppColors.surface,
    errorContainer: AppColors.dangerBg,
    onErrorContainer: AppColors.dangerFg,
    surface: AppColors.surface,
    onSurface: AppColors.text,
    onSurfaceVariant: AppColors.textSecondary,
    surfaceContainerLowest: AppColors.surface,
    surfaceContainerLow: AppColors.canvas,
    surfaceContainer: AppColors.surfaceSubtle,
    surfaceContainerHigh: AppColors.surfaceSunken,
    surfaceContainerHighest: AppColors.surfaceSunken,
    outline: AppColors.borderStrong,
    outlineVariant: AppColors.border,
    shadow: Color(0x1A17212B),
    scrim: Color(0x6617212B),
    inverseSurface: AppColors.demoBg,
    onInverseSurface: AppColors.demoFg,
    inversePrimary: AppColors.accentSoft,
    surfaceTint: Colors.transparent,
  );

  const buttonShape = RoundedRectangleBorder(borderRadius: Radii.smAll);
  const buttonPadding = EdgeInsets.symmetric(horizontal: Space.x4, vertical: 10);
  const buttonMinSize = Size(64, kMinTapTarget);
  const buttonText = TextStyle(fontSize: 15, fontWeight: FontWeight.w600, height: 20 / 15);

  final base = ThemeData(
    useMaterial3: true,
    colorScheme: scheme,
    scaffoldBackgroundColor: AppColors.canvas,
    visualDensity: VisualDensity.standard,
    splashFactory: InkRipple.splashFactory,
  );

  return base.copyWith(
    textTheme: base.textTheme.copyWith(
      headlineSmall: AppType.pageTitle,
      titleLarge: AppType.sectionTitle,
      titleMedium: AppType.subsectionTitle,
      titleSmall: AppType.smallStrong,
      bodyLarge: AppType.body,
      bodyMedium: AppType.body,
      bodySmall: AppType.small,
      labelLarge: buttonText,
      labelMedium: AppType.label,
      labelSmall: AppType.caption,
    ),
    dividerTheme: const DividerThemeData(color: AppColors.border, thickness: 1, space: 1),
    appBarTheme: const AppBarTheme(
      backgroundColor: AppColors.surface,
      foregroundColor: AppColors.text,
      elevation: 0,
      scrolledUnderElevation: 0,
      surfaceTintColor: Colors.transparent,
      centerTitle: false,
      titleTextStyle: AppType.subsectionTitle,
      shape: Border(bottom: BorderSide(color: AppColors.border)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(buttonMinSize),
        padding: const WidgetStatePropertyAll(buttonPadding),
        shape: const WidgetStatePropertyAll(buttonShape),
        textStyle: const WidgetStatePropertyAll(buttonText),
        elevation: const WidgetStatePropertyAll(0),
        backgroundColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) return AppColors.surfaceSunken;
          if (states.contains(WidgetState.pressed)) return AppColors.accentPressed;
          if (states.contains(WidgetState.hovered)) return AppColors.accentHover;
          return AppColors.accent;
        }),
        foregroundColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) return AppColors.textMuted;
          return AppColors.textOnAccent;
        }),
        overlayColor: const WidgetStatePropertyAll(Colors.transparent),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(buttonMinSize),
        padding: const WidgetStatePropertyAll(buttonPadding),
        shape: const WidgetStatePropertyAll(buttonShape),
        textStyle: const WidgetStatePropertyAll(buttonText),
        foregroundColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) return AppColors.textMuted;
          return AppColors.text;
        }),
        backgroundColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.pressed)) return AppColors.surfaceSunken;
          if (states.contains(WidgetState.hovered)) return AppColors.surfaceSubtle;
          return AppColors.surface;
        }),
        side: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) {
            return const BorderSide(color: AppColors.border);
          }
          return const BorderSide(color: AppColors.borderStrong);
        }),
        overlayColor: const WidgetStatePropertyAll(Colors.transparent),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(44, kMinTapTarget)),
        padding: const WidgetStatePropertyAll(EdgeInsets.symmetric(horizontal: Space.x3)),
        shape: const WidgetStatePropertyAll(buttonShape),
        textStyle: const WidgetStatePropertyAll(buttonText),
        foregroundColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.disabled)) return AppColors.textMuted;
          if (states.contains(WidgetState.hovered)) return AppColors.accentHover;
          return AppColors.accent;
        }),
        overlayColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.pressed)) return AppColors.accentSoft;
          if (states.contains(WidgetState.hovered)) return AppColors.accentSofter;
          return Colors.transparent;
        }),
      ),
    ),
    iconButtonTheme: IconButtonThemeData(
      style: ButtonStyle(
        minimumSize: const WidgetStatePropertyAll(Size(kMinTapTarget, kMinTapTarget)),
        shape: const WidgetStatePropertyAll(buttonShape),
        foregroundColor: const WidgetStatePropertyAll(AppColors.textSecondary),
        overlayColor: WidgetStateProperty.resolveWith((states) {
          if (states.contains(WidgetState.pressed)) return AppColors.surfaceSunken;
          if (states.contains(WidgetState.hovered)) return AppColors.surfaceSubtle;
          return Colors.transparent;
        }),
      ),
    ),
    inputDecorationTheme: const InputDecorationTheme(
      isDense: true,
      filled: true,
      fillColor: AppColors.surface,
      contentPadding: EdgeInsets.symmetric(horizontal: Space.x3, vertical: Space.x3),
      hintStyle: TextStyle(color: AppColors.textMuted, fontSize: 15),
      labelStyle: AppType.label,
      helperStyle: AppType.caption,
      errorStyle: TextStyle(color: AppColors.dangerFg, fontSize: 13, fontWeight: FontWeight.w600),
      border: OutlineInputBorder(
        borderRadius: Radii.smAll,
        borderSide: BorderSide(color: AppColors.borderStrong),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: Radii.smAll,
        borderSide: BorderSide(color: AppColors.borderStrong),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: Radii.smAll,
        borderSide: BorderSide(color: AppColors.focusRing, width: 2),
      ),
      errorBorder: OutlineInputBorder(
        borderRadius: Radii.smAll,
        borderSide: BorderSide(color: AppColors.dangerFg, width: 2),
      ),
      focusedErrorBorder: OutlineInputBorder(
        borderRadius: Radii.smAll,
        borderSide: BorderSide(color: AppColors.dangerFg, width: 2),
      ),
    ),
    tabBarTheme: const TabBarThemeData(
      labelColor: AppColors.text,
      unselectedLabelColor: AppColors.textSecondary,
      labelStyle: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      unselectedLabelStyle: TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
      indicatorColor: AppColors.accent,
      indicatorSize: TabBarIndicatorSize.label,
      dividerColor: AppColors.border,
      tabAlignment: TabAlignment.start,
      overlayColor: WidgetStatePropertyAll(AppColors.accentSofter),
    ),
    tooltipTheme: const TooltipThemeData(
      waitDuration: Duration(milliseconds: 350),
      decoration: BoxDecoration(color: AppColors.demoBg, borderRadius: Radii.smAll),
      textStyle: TextStyle(color: AppColors.demoFg, fontSize: 13, height: 18 / 13),
      padding: EdgeInsets.symmetric(horizontal: Space.x3, vertical: Space.x2),
      preferBelow: true,
    ),
    dialogTheme: const DialogThemeData(
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      shape: RoundedRectangleBorder(borderRadius: Radii.lgAll),
      titleTextStyle: AppType.sectionTitle,
      contentTextStyle: AppType.body,
    ),
    bottomSheetTheme: const BottomSheetThemeData(
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      showDragHandle: true,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(Radii.lg))),
    ),
    snackBarTheme: const SnackBarThemeData(
      behavior: SnackBarBehavior.floating,
      backgroundColor: AppColors.demoBg,
      contentTextStyle: TextStyle(color: AppColors.demoFg, fontSize: 14),
      shape: RoundedRectangleBorder(borderRadius: Radii.smAll),
      width: 420,
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return AppColors.surface;
        return AppColors.textMuted;
      }),
      trackColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return AppColors.accent;
        return AppColors.surfaceSunken;
      }),
      trackOutlineColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return AppColors.accent;
        return AppColors.borderStrong;
      }),
    ),
    radioTheme: RadioThemeData(
      fillColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return AppColors.accent;
        return AppColors.textSecondary;
      }),
    ),
    checkboxTheme: CheckboxThemeData(
      fillColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return AppColors.accent;
        return Colors.transparent;
      }),
      side: const BorderSide(color: AppColors.textSecondary, width: 1.5),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(3))),
    ),
    progressIndicatorTheme: const ProgressIndicatorThemeData(
      color: AppColors.accent,
      linearTrackColor: AppColors.surfaceSunken,
    ),
    popupMenuTheme: const PopupMenuThemeData(
      color: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      elevation: 3,
      shape: RoundedRectangleBorder(
        borderRadius: Radii.mdAll,
        side: BorderSide(color: AppColors.border),
      ),
      textStyle: AppType.body,
    ),
    menuTheme: const MenuThemeData(
      style: MenuStyle(
        backgroundColor: WidgetStatePropertyAll(AppColors.surface),
        surfaceTintColor: WidgetStatePropertyAll(Colors.transparent),
        shape: WidgetStatePropertyAll(
          RoundedRectangleBorder(
            borderRadius: Radii.mdAll,
            side: BorderSide(color: AppColors.border),
          ),
        ),
      ),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: AppColors.surface,
      surfaceTintColor: Colors.transparent,
      indicatorColor: AppColors.accentSoft,
      height: 64,
      labelTextStyle: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return TextStyle(
          fontSize: 12,
          fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
          color: selected ? AppColors.text : AppColors.textSecondary,
        );
      }),
      iconTheme: WidgetStateProperty.resolveWith((states) {
        final selected = states.contains(WidgetState.selected);
        return IconThemeData(color: selected ? AppColors.accent : AppColors.textSecondary, size: 22);
      }),
    ),
    chipTheme: const ChipThemeData(
      backgroundColor: AppColors.surface,
      selectedColor: AppColors.accentSoft,
      side: BorderSide(color: AppColors.borderStrong),
      shape: RoundedRectangleBorder(borderRadius: Radii.smAll),
      labelStyle: TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: AppColors.text),
      checkmarkColor: AppColors.accent,
      padding: EdgeInsets.symmetric(horizontal: Space.x1),
    ),
  );
}
