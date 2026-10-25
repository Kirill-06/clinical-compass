import 'dart:async';
import 'dart:convert';

import 'package:centrifuge/centrifuge.dart' as centrifuge;
import 'package:flutter/foundation.dart';

import 'package:clinical_compass/data/api_client.dart';
import 'package:clinical_compass/domain/json.dart';

/// Событие из Centrifugo: в канале что-то изменилось (новое сообщение, прочтение, алерт).
///
/// Это только сигнал. Данные экраны перечитывают через API, где доступ
/// проверяется как обычно.
class RealtimeEvent {
  const RealtimeEvent(this.channel, this.data);

  final String channel;
  final Json data;

  String get kind => data['kind'] as String? ?? '';
}

/// Подключение к Centrifugo для текущего пользователя.
///
/// Каналы выбирает сервер и вшивает в токен, поэтому подписок на клиенте нет.
/// Если Centrifugo не настроен или недоступен, экраны продолжают обновляться
/// опросом, а [live] остаётся `false`.
class RealtimeLink {
  RealtimeLink(this._api);

  final ApiClient _api;
  final _events = StreamController<RealtimeEvent>.broadcast();
  final live = ValueNotifier<bool>(false);

  centrifuge.Client? _client;
  final _subscriptions = <StreamSubscription<Object?>>[];
  String? _userId;

  Stream<RealtimeEvent> get events => _events.stream;

  /// Подключиться за пользователя, который сейчас вошёл; при смене пользователя — переподключиться.
  Future<void> syncWithSession() async {
    final userId = _api.user?.id;
    if (userId == _userId) return;
    await _disconnect();
    _userId = userId;
    if (userId == null) return;
    try {
      final connection = await _api.realtimeConnection();
      if (connection['enabled'] != true || _userId != userId) return;
      final client = centrifuge.createClient(
        connection['url']! as String,
        centrifuge.ClientConfig(
          token: connection['token']! as String,
          // Токен живёт час; клиент сам попросит новый.
          getToken: (_) async => (await _api.realtimeConnection())['token']! as String,
          name: 'clinical-compass',
        ),
      );
      _client = client;
      _subscriptions
        ..add(client.connected.listen((_) => live.value = true))
        ..add(client.disconnected.listen((_) => live.value = false))
        ..add(client.publication.listen(_onPublication));
      await client.connect();
    } on Exception catch (e) {
      debugPrint('Centrifugo недоступен, остаёмся на опросе: $e');
    }
  }

  void _onPublication(centrifuge.ServerPublicationEvent e) {
    final Json data;
    try {
      data = asJson(jsonDecode(utf8.decode(e.data)));
    } on FormatException {
      return;
    }
    _events.add(RealtimeEvent(e.channel, data));
    // Открытые экраны (чат, очередь, карточка) перечитают данные.
    _api.refresh();
  }

  Future<void> _disconnect() async {
    for (final s in _subscriptions) {
      await s.cancel();
    }
    _subscriptions.clear();
    final client = _client;
    _client = null;
    live.value = false;
    if (client != null) await client.disconnect();
  }

  Future<void> dispose() async {
    await _disconnect();
    await _events.close();
    live.dispose();
  }
}
