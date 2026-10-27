import 'package:flutter/material.dart';

import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/core/design/loader.dart';
import 'package:clinical_compass/data/api_client.dart';

/// Показывает экраны только после загрузки шкал и справочников (`GET /meta`).
class MetaGate extends StatefulWidget {
  const MetaGate({super.key, required this.api, required this.child});

  final ApiClient api;
  final Widget child;

  @override
  State<MetaGate> createState() => _MetaGateState();
}

class _MetaGateState extends State<MetaGate> {
  late Future<void> _loading = widget.api.loadMeta();

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<void>(
      future: _loading,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.done && !snapshot.hasError) return widget.child;
        return Scaffold(
          body: snapshot.hasError
              ? ErrorState(
                  message: '${snapshot.error}',
                  onRetry: () => setState(() => _loading = widget.api.loadMeta()),
                )
              : const SplashLoader(label: 'Подключаемся к серверу…'),
        );
      },
    );
  }
}
