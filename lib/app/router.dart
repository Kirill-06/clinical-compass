import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/presentation/admin/admin_screen.dart';
import 'package:clinical_compass/presentation/doctor/doctor_shell.dart';
import 'package:clinical_compass/presentation/doctor/patient_detail_screen.dart';
import 'package:clinical_compass/presentation/doctor/patients_screen.dart';
import 'package:clinical_compass/presentation/doctor/queue_screen.dart';
import 'package:clinical_compass/presentation/doctor/rules_screen.dart';
import 'package:clinical_compass/presentation/embed/embed_screens.dart';
import 'package:clinical_compass/presentation/entry/entry_screen.dart';
import 'package:clinical_compass/presentation/patient/patient_chat_screen.dart';
import 'package:clinical_compass/presentation/patient/patient_home_screen.dart';
import 'package:clinical_compass/presentation/patient/patient_medication_screen.dart';
import 'package:clinical_compass/presentation/patient/patient_results_screen.dart';
import 'package:clinical_compass/presentation/patient/patient_shell.dart';
import 'package:clinical_compass/presentation/patient/questionnaire_flow_screen.dart';
import 'package:clinical_compass/presentation/patient/symptom_screen.dart';
import 'package:clinical_compass/presentation/shared/demo_accounts.dart';

Page<void> _page(GoRouterState s, Widget child) => NoTransitionPage<void>(key: s.pageKey, child: child);

/// Навигация по ролям. Это удобство интерфейса; доступ к данным
/// проверяет backend на каждом запросе.
GoRouter buildRouter(AppServices services) {
  final rootKey = GlobalKey<NavigatorState>();
  return GoRouter(
    navigatorKey: rootKey,
    initialLocation: '/',
    refreshListenable: services.api,
    redirect: (context, state) {
      final user = services.api.user;
      final path = state.matchedLocation;
      // Окно из МИС входит по одноразовому коду, без экрана выбора аккаунта.
      if (path.startsWith('/embed/launch/')) return null;
      if (user == null) return path == '/' ? null : '/';
      final home = homeFor(user.role);
      if (path == '/') return home;
      final allowed = switch (user.role) {
        Role.doctor => path.startsWith('/doctor') || path.startsWith('/embed/patient/'),
        Role.patient => path.startsWith('/patient'),
        Role.admin => path.startsWith('/admin'),
      };
      return allowed ? null : home;
    },
    routes: [
      GoRoute(path: '/', pageBuilder: (c, s) => _page(s, const EntryScreen())),
      ShellRoute(
        builder: (c, s, child) => DoctorShell(location: s.matchedLocation, child: child),
        routes: [
          GoRoute(path: '/doctor', redirect: (_, _) => '/doctor/queue'),
          GoRoute(path: '/doctor/queue', pageBuilder: (c, s) => _page(s, const QueueScreen())),
          GoRoute(
            path: '/doctor/patients',
            pageBuilder: (c, s) => _page(s, const PatientsScreen()),
            routes: [
              GoRoute(
                path: ':id',
                pageBuilder: (c, s) => _page(s, PatientDetailScreen(patientId: s.pathParameters['id'] ?? '')),
              ),
            ],
          ),
          GoRoute(path: '/doctor/rules', pageBuilder: (c, s) => _page(s, const RulesScreen())),
        ],
      ),
      ShellRoute(
        builder: (c, s, child) => PatientShell(location: s.matchedLocation, child: child),
        routes: [
          GoRoute(path: '/patient', pageBuilder: (c, s) => _page(s, const PatientHomeScreen())),
          GoRoute(path: '/patient/results', pageBuilder: (c, s) => _page(s, const PatientResultsScreen())),
          GoRoute(path: '/patient/medication', pageBuilder: (c, s) => _page(s, const PatientMedicationScreen())),
          GoRoute(path: '/patient/chat', pageBuilder: (c, s) => _page(s, const PatientChatScreen())),
        ],
      ),
      GoRoute(
        path: '/patient/questionnaire/:instrument',
        parentNavigatorKey: rootKey,
        builder: (c, s) {
          final raw = s.pathParameters['instrument'] ?? '';
          final instrument = Instrument.values.where((i) => i.wire == raw).firstOrNull;
          if (instrument == null) return const _NotFound();
          return QuestionnaireFlowScreen(instrument: instrument);
        },
      ),
      GoRoute(path: '/patient/symptom', parentNavigatorKey: rootKey, builder: (c, s) => const SymptomScreen()),
      // Старый адрес «Сообщение врачу» — теперь это чат.
      GoRoute(path: '/patient/message', redirect: (_, _) => '/patient/chat'),
      GoRoute(path: '/admin', pageBuilder: (c, s) => _page(s, const AdminScreen())),
      GoRoute(
        path: '/embed/launch/:code',
        pageBuilder: (c, s) => _page(s, EmbedLaunchScreen(code: s.pathParameters['code'] ?? '')),
      ),
      GoRoute(
        path: '/embed/patient/:id',
        pageBuilder: (c, s) =>
            _page(s, EmbedShell(child: PatientDetailScreen(patientId: s.pathParameters['id'] ?? '', embedded: true))),
      ),
    ],
    errorBuilder: (c, s) => const _NotFound(),
  );
}

class _NotFound extends StatelessWidget {
  const _NotFound();

  @override
  Widget build(BuildContext context) => Scaffold(
    body: Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text('Страница не найдена'),
          const SizedBox(height: 12),
          OutlinedButton(onPressed: () => context.go('/'), child: const Text('На стартовую')),
        ],
      ),
    ),
  );
}
