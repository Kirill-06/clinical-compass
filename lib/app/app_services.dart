import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';

import 'package:clinical_compass/core/time/clock.dart';
import 'package:clinical_compass/data/api_client.dart';
import 'package:clinical_compass/data/realtime.dart';
import 'package:clinical_compass/domain/meta.dart';

/// Корень зависимостей: клиент API, доставка событий и часы (для подписей «сегодня/вчера»).
class AppServices {
  AppServices({required this.api, this.clock = const SystemClock()}) : realtime = RealtimeLink(api) {
    // Вход, выход и смена аккаунта — переподключить Centrifugo под нового пользователя.
    api.addListener(() => unawaited(realtime.syncWithSession()));
  }

  /// Адрес backend задаётся при сборке: `--dart-define=CC_API_BASE_URL=...`.
  /// В web без явного адреса используется тот же origin, с которого открыто
  /// приложение (backend отдаёт сборку сам).
  factory AppServices.http() {
    const configured = String.fromEnvironment('CC_API_BASE_URL');
    final base = configured.isNotEmpty
        ? configured
        : kIsWeb
        ? Uri.base.origin
        : 'http://localhost:8080';
    return AppServices(api: ApiClient(HttpTransport(base)));
  }

  final ApiClient api;
  final Clock clock;
  final RealtimeLink realtime;
}

/// Подписка на клиента API: экраны перестраиваются при входе/выходе и
/// перезагружают данные после любой записи.
class AppScope extends InheritedNotifier<ApiClient> {
  AppScope({super.key, required this.services, required super.child}) : super(notifier: services.api);

  final AppServices services;

  static AppServices of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope не найден');
    return scope!.services;
  }

  static AppServices read(BuildContext context) {
    final scope = context.getInheritedWidgetOfExactType<AppScope>();
    assert(scope != null, 'AppScope не найден');
    return scope!.services;
  }
}

extension AppScopeContext on BuildContext {
  /// Для `build`: виджет перестроится при смене аккаунта.
  AppServices get services => AppScope.of(this);

  /// Шкалы и справочники с сервера (загружаются до показа экранов).
  ContractMeta get meta => AppScope.read(this).api.meta;

  /// Для обработчиков событий: без подписки.
  ApiClient get api => AppScope.read(this).api;

  SessionUser get user {
    final u = AppScope.of(this).api.user;
    if (u == null) throw StateError('Не выполнен вход');
    return u;
  }
}
