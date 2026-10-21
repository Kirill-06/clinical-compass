import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';

/// Смысловой тон статуса. Цвет никогда не единственный носитель смысла:
/// каждый бейдж содержит текст и, как правило, иконку.
enum StatusTone { ok, warn, danger, info, neutral, accent }

extension StatusToneColors on StatusTone {
  Color get fg => switch (this) {
    StatusTone.ok => AppColors.okFg,
    StatusTone.warn => AppColors.warnFg,
    StatusTone.danger => AppColors.dangerFg,
    StatusTone.info => AppColors.infoFg,
    StatusTone.neutral => AppColors.neutralFg,
    StatusTone.accent => AppColors.accent,
  };

  Color get bg => switch (this) {
    StatusTone.ok => AppColors.okBg,
    StatusTone.warn => AppColors.warnBg,
    StatusTone.danger => AppColors.dangerBg,
    StatusTone.info => AppColors.infoBg,
    StatusTone.neutral => AppColors.neutralBg,
    StatusTone.accent => AppColors.accentSoft,
  };
}

class StatusBadge extends StatelessWidget {
  const StatusBadge({super.key, required this.label, required this.tone, this.icon, this.tooltip, this.dense = false});

  final String label;
  final StatusTone tone;
  final IconData? icon;
  final String? tooltip;
  final bool dense;

  @override
  Widget build(BuildContext context) {
    final badge = Container(
      padding: EdgeInsets.symmetric(horizontal: dense ? 6 : Space.x2, vertical: dense ? 1 : 3),
      decoration: BoxDecoration(color: tone.bg, borderRadius: Radii.smAll),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (icon != null) ...[Icon(icon, size: dense ? 13 : 15, color: tone.fg), const SizedBox(width: 5)],
          Flexible(
            child: Text(
              label,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(fontSize: dense ? 12 : 13, height: 18 / 13, fontWeight: FontWeight.w600, color: tone.fg),
            ),
          ),
        ],
      ),
    );
    if (tooltip == null) return badge;
    return Tooltip(message: tooltip, child: badge);
  }
}

/// Явная маркировка демо-функций и тестовых данных.
class DemoTag extends StatelessWidget {
  const DemoTag({super.key, this.label = 'ДЕМО', this.tooltip});

  final String label;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final tag = Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: const BoxDecoration(color: AppColors.demoBg, borderRadius: Radii.smAll),
      child: Text(
        label,
        style: const TextStyle(
          fontSize: 11,
          height: 14 / 11,
          fontWeight: FontWeight.w700,
          letterSpacing: 0.6,
          color: AppColors.demoFg,
        ),
      ),
    );
    return Semantics(
      label: 'Демонстрационные данные',
      child: tooltip == null ? tag : Tooltip(message: tooltip, child: tag),
    );
  }
}

/// Блок-уведомление в духе NHS «inset text / warning callout»:
/// тонкая цветная полоса слева, без заливки всей карточки.
class InlineNotice extends StatelessWidget {
  const InlineNotice({super.key, required this.body, this.title, this.tone = StatusTone.info, this.icon, this.action});

  final String? title;
  final String body;
  final StatusTone tone;
  final IconData? icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: tone == StatusTone.neutral ? AppColors.surfaceSubtle : tone.bg.withValues(alpha: 0.55),
        borderRadius: Radii.smAll,
        border: Border(left: BorderSide(color: tone.fg, width: 4)),
      ),
      padding: const EdgeInsets.fromLTRB(Space.x4, Space.x3, Space.x4, Space.x3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null) ...[
            Padding(
              padding: const EdgeInsets.only(top: 2),
              child: Icon(icon, size: 18, color: tone.fg),
            ),
            const SizedBox(width: Space.x3),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (title != null) ...[Text(title!, style: AppType.bodyStrong), const SizedBox(height: 2)],
                Text(body, style: AppType.bodySecondary),
                if (action != null) ...[const SizedBox(height: Space.x2), action!],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Белая поверхность с тонкой границей. Используется для крупных
/// смысловых блоков, а не для каждого элемента.
class Panel extends StatelessWidget {
  const Panel({super.key, required this.child, this.padding = const EdgeInsets.all(Space.x5)});

  final Widget child;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) {
    return DecoratedBox(
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: Radii.mdAll,
        border: Border.all(color: AppColors.border),
      ),
      child: Padding(padding: padding, child: child),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.title, this.subtitle, this.trailing, this.level = 1});

  final String title;
  final String? subtitle;
  final Widget? trailing;

  /// 1 — заголовок раздела, 2 — подраздела.
  final int level;

  @override
  Widget build(BuildContext context) {
    final titleWidget = Semantics(
      header: true,
      child: Text(title, style: level == 1 ? AppType.sectionTitle : AppType.subsectionTitle),
    );
    final titleBlock = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        titleWidget,
        if (subtitle != null) ...[const SizedBox(height: 2), Text(subtitle!, style: AppType.small)],
      ],
    );
    final action = trailing;
    if (action == null) return titleBlock;
    return LayoutBuilder(
      builder: (context, c) {
        // На узкой ширине действие уходит под заголовок, а не сжимает его.
        if (c.maxWidth < 460) {
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              titleBlock,
              const SizedBox(height: Space.x3),
              action,
            ],
          );
        }
        return Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Expanded(child: titleBlock),
            const SizedBox(width: Space.x3),
            action,
          ],
        );
      },
    );
  }
}

/// Пара «подпись — значение» для шапок и деталей.
class KeyValue extends StatelessWidget {
  const KeyValue({super.key, required this.label, required this.value, this.valueWidget});

  final String label;
  final String value;
  final Widget? valueWidget;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(label, style: AppType.caption),
        const SizedBox(height: 2),
        valueWidget ?? Text(value, style: AppType.bodyStrong),
      ],
    );
  }
}

class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.title,
    this.message,
    this.icon = Icons.inbox_outlined,
    this.action,
    this.compact = false,
  });

  final String title;
  final String? message;
  final IconData icon;
  final Widget? action;
  final bool compact;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: EdgeInsets.symmetric(vertical: compact ? Space.x6 : Space.x12, horizontal: Space.x4),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: compact ? 24 : 32, color: AppColors.textMuted),
          const SizedBox(height: Space.x3),
          Text(title, style: AppType.bodyStrong, textAlign: TextAlign.center),
          if (message != null) ...[
            const SizedBox(height: Space.x1),
            ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Text(message!, style: AppType.small, textAlign: TextAlign.center),
            ),
          ],
          if (action != null) ...[const SizedBox(height: Space.x4), action!],
        ],
      ),
    );
  }
}

class ErrorState extends StatelessWidget {
  const ErrorState({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    return EmptyState(
      icon: Icons.error_outline,
      title: 'Не удалось загрузить данные',
      message: message,
      action: onRetry == null
          ? null
          : OutlinedButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh, size: 18),
              label: const Text('Повторить'),
            ),
    );
  }
}

class LoadingState extends StatelessWidget {
  const LoadingState({super.key, this.label = 'Загрузка…'});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: Space.x12),
      child: Semantics(
        label: label,
        liveRegion: true,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.4)),
            const SizedBox(height: Space.x3),
            Text(label, style: AppType.small),
          ],
        ),
      ),
    );
  }
}

/// Ограничение ширины контента с центрированием.
class ContentWidth extends StatelessWidget {
  const ContentWidth({super.key, required this.child, this.maxWidth = 1240});

  final Widget child;
  final double maxWidth;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.topCenter,
      child: ConstrainedBox(
        constraints: BoxConstraints(maxWidth: maxWidth),
        child: child,
      ),
    );
  }
}

/// Сегмент выбора с явной текстовой подписью (используется вместо
/// «таблеток» Material для фильтров).
class FilterSegment<T> extends StatelessWidget {
  const FilterSegment({
    super.key,
    required this.options,
    required this.value,
    required this.onChanged,
    required this.labelOf,
    this.countOf,
    this.semanticLabel,
  });

  final List<T> options;
  final T value;
  final ValueChanged<T> onChanged;
  final String Function(T) labelOf;
  final int? Function(T)? countOf;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: semanticLabel,
      container: true,
      child: Container(
        padding: const EdgeInsets.all(2),
        decoration: BoxDecoration(
          color: AppColors.surfaceSubtle,
          borderRadius: Radii.mdAll,
          border: Border.all(color: AppColors.border),
        ),
        child: Wrap(
          spacing: 2,
          runSpacing: 2,
          children: [
            for (final option in options)
              _SegmentButton(
                label: labelOf(option),
                count: countOf?.call(option),
                selected: option == value,
                onTap: () => onChanged(option),
              ),
          ],
        ),
      ),
    );
  }
}

class _SegmentButton extends StatelessWidget {
  const _SegmentButton({required this.label, required this.selected, required this.onTap, this.count});

  final String label;
  final int? count;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      selected: selected,
      child: Material(
        color: selected ? AppColors.surface : Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: Radii.smAll,
          side: selected ? const BorderSide(color: AppColors.border) : BorderSide.none,
        ),
        child: InkWell(
          borderRadius: Radii.smAll,
          onTap: onTap,
          hoverColor: AppColors.surfaceSunken.withValues(alpha: 0.6),
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 36),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: Space.x3, vertical: 7),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    label,
                    style: TextStyle(
                      fontSize: 13,
                      height: 18 / 13,
                      fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
                      color: selected ? AppColors.text : AppColors.textSecondary,
                    ),
                  ),
                  if (count != null) ...[
                    const SizedBox(width: 6),
                    Text(
                      '$count',
                      style: AppType.numericSmall.copyWith(
                        fontSize: 12,
                        color: selected ? AppColors.accent : AppColors.textMuted,
                      ),
                    ),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
