import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/tokens.dart';
import 'package:clinical_compass/core/design/typography.dart';

/// Optional, non-clinical encouragement. The choice to hide it persists locally.
class SupportNote extends StatefulWidget {
  const SupportNote({super.key});

  @override
  State<SupportNote> createState() => _SupportNoteState();
}

class _SupportNoteState extends State<SupportNote> {
  static const _hiddenKey = 'patient_support_note_hidden_v03';
  bool _hidden = true;

  @override
  void initState() {
    super.initState();
    SharedPreferences.getInstance().then((prefs) {
      if (mounted) setState(() => _hidden = prefs.getBool(_hiddenKey) ?? false);
    });
  }

  Future<void> _hide() async {
    setState(() => _hidden = true);
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool(_hiddenKey, true);
  }

  @override
  Widget build(BuildContext context) {
    if (_hidden) return const SizedBox.shrink();
    return Panel(
      child: Row(
        children: [
          const Icon(Icons.waving_hand_outlined, color: AppColors.accent, size: 24),
          const SizedBox(width: Space.x3),
          const Expanded(child: Text('Рады видеть вас. Записывайте то, что считаете важным.', style: AppType.small)),
          IconButton(tooltip: 'Скрыть подсказку', onPressed: _hide, icon: const Icon(Icons.close, size: 20)),
        ],
      ),
    );
  }
}
