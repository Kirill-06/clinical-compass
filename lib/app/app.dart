import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/app/meta_gate.dart';
import 'package:clinical_compass/app/router.dart';
import 'package:clinical_compass/core/design/theme.dart';
import 'package:clinical_compass/presentation/patient/emergency_alert.dart';

class ClinicalCompassApp extends StatefulWidget {
  const ClinicalCompassApp({super.key, required this.services});

  final AppServices services;

  @override
  State<ClinicalCompassApp> createState() => _ClinicalCompassAppState();
}

class _ClinicalCompassAppState extends State<ClinicalCompassApp> {
  late final GoRouter _router = buildRouter(widget.services);

  @override
  void dispose() {
    _router.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AppScope(
      services: widget.services,
      child: MaterialApp.router(
        title: 'Клинический компас',
        debugShowCheckedModeBanner: false,
        theme: buildAppTheme(),
        routerConfig: _router,
        builder: (context, child) => MetaGate(
          api: widget.services.api,
          child: EmergencyAlertHost(
            api: widget.services.api,
            navigatorKey: _router.routerDelegate.navigatorKey,
            child: child ?? const SizedBox.shrink(),
          ),
        ),
        locale: const Locale('ru', 'RU'),
        supportedLocales: const [Locale('ru', 'RU')],
        localizationsDelegates: const [
          GlobalMaterialLocalizations.delegate,
          GlobalWidgetsLocalizations.delegate,
          GlobalCupertinoLocalizations.delegate,
        ],
      ),
    );
  }
}
