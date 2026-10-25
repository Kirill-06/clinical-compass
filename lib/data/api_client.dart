import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import 'package:clinical_compass/domain/contract.dart';
import 'package:clinical_compass/domain/json.dart';
import 'package:clinical_compass/domain/meta.dart';

/// Ответ транспорта: статус и тело (JSON или байты).
class ApiResponse {
  const ApiResponse(this.status, this.bytes, this.contentType);

  final int status;
  final Uint8List bytes;
  final String contentType;

  Object? get json => bytes.isEmpty ? null : jsonDecode(utf8.decode(bytes));
}

/// Способ доставки запроса к backend (HTTP; в тестах можно подменить).
abstract interface class ApiTransport {
  Future<ApiResponse> send(String method, String path, {Object? body, Map<String, String> headers});
}

class HttpTransport implements ApiTransport {
  HttpTransport(this.baseUrl, {http.Client? client}) : _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;

  @override
  Future<ApiResponse> send(String method, String path, {Object? body, Map<String, String> headers = const {}}) async {
    final request = http.Request(method, Uri.parse('$baseUrl$path'))
      ..headers.addAll({'content-type': 'application/json', ...headers});
    if (body != null) request.body = jsonEncode(body);
    final streamed = await _client.send(request).timeout(const Duration(seconds: 30));
    final res = await http.Response.fromStream(streamed);
    return ApiResponse(res.statusCode, res.bodyBytes, res.headers['content-type'] ?? '');
  }
}

class ApiException implements Exception {
  const ApiException(this.status, this.message);

  final int status;
  final String message;

  bool get isNetwork => status == 0;

  @override
  String toString() => message;
}

class SessionUser {
  const SessionUser({required this.id, required this.role, required this.name});

  final String id;
  final Role role;
  final String name;

  factory SessionUser.fromJson(Json j) =>
      SessionUser(id: reqString(j, 'id'), role: Role.fromWire(reqString(j, 'role')), name: reqString(j, 'name'));
}

/// Типизированный клиент API v0.2. После каждой записи оповещает
/// подписчиков, чтобы открытые экраны перезагрузили данные.
class ApiClient extends ChangeNotifier {
  ApiClient(this.transport);

  final ApiTransport transport;
  String? _token;
  SessionUser? _user;
  ContractMeta? _meta;
  String? _embeddedFrom;
  int _requestCounter = 0;
  final _emergencies = StreamController<Json>.broadcast();
  final _announcedEmergencies = <String>{};

  /// Экстренные предупреждения пациенту (`recommend_ambulance`) из ответов сервера —
  /// каждое один раз за сессию приложения.
  Stream<Json> get emergencies => _emergencies.stream;

  /// Название МИС, если приложение открыто окном внутри неё (ЕМИАС, 1С).
  String? get embeddedFrom => _embeddedFrom;

  SessionUser? get user => _user;

  /// Шкалы и справочники; доступны после [loadMeta].
  ContractMeta get meta => _meta ?? (throw StateError('Справочники ещё не загружены'));
  bool get isSignedIn => _user != null;

  Future<Object?> _call(String method, String path, {Object? body, bool write = false, String? idempotencyKey}) async {
    final headers = <String, String>{
      if (_token != null) 'authorization': 'Bearer $_token',
      'idempotency-key': ?idempotencyKey,
    };
    final ApiResponse res;
    try {
      res = await transport.send(method, path, body: body, headers: headers);
    } on TimeoutException {
      throw const ApiException(0, 'Сервер не ответил. Проверьте соединение и повторите.');
    } on http.ClientException {
      throw const ApiException(0, 'Нет связи с сервером. Проверьте, что backend запущен.');
    }
    if (res.status >= 400) {
      final j = res.json;
      final message = j is Map && j['message'] is String ? j['message'] as String : 'Ошибка сервера (${res.status})';
      if (res.status == 401) {
        _token = null;
        _user = null;
        notifyListeners();
      }
      throw ApiException(res.status, message);
    }
    final json = res.json;
    if (json is Map && json['patient_notices'] is List) {
      _announceEmergencies([for (final n in json['patient_notices'] as List) asJson(n)]);
    }
    if (write) notifyListeners();
    return json;
  }

  void _announceEmergencies(Iterable<Json> notices) {
    for (final n in notices) {
      final id = n['alert_id'];
      if (n['patient_action'] == PatientAction.recommendAmbulance.wire &&
          id is String &&
          _announcedEmergencies.add(id)) {
        _emergencies.add(n);
      }
    }
  }

  @override
  void dispose() {
    _emergencies.close();
    super.dispose();
  }

  Json _obj(Object? v) => asJson(v, 'ответ сервера');
  List<Json> _list(Object? v) => [for (final e in (v as List? ?? const [])) asJson(e)];

  /// Ключ идемпотентности: повторная отправка того же действия не создаёт дубль.
  String newIdempotencyKey(String scope) => '$scope-${DateTime.now().microsecondsSinceEpoch}-${++_requestCounter}';

  // -------------------------------------------------------------- contracts

  Future<ContractMeta> loadMeta() async => _meta ??= ContractMeta.fromJson(_obj(await _call('GET', '/meta')));

  // -------------------------------------------------------------- auth (demo)

  Future<Json> demoAccounts() async => _obj(await _call('GET', '/demo/accounts'));

  /// [notify] = false позволяет сначала уйти на экран новой роли и лишь
  /// затем оповестить подписчиков (иначе старые экраны успеют запросить
  /// чужие разделы с новым токеном).
  Future<SessionUser> demoLogin(String userId, {bool notify = true}) async {
    final j = _obj(await _call('POST', '/auth/demo-login', body: {'user_id': userId}));
    _token = reqString(j, 'token');
    final user = SessionUser.fromJson(asJson(j['user']));
    _user = user;
    if (notify) notifyListeners();
    return user;
  }

  /// Окно внутри МИС: обменять одноразовый код запуска на сессию врача.
  /// Возвращает id пациента, карточку которого открыла МИС.
  Future<String> openFromMis(String code) async {
    final j = _obj(await _call('POST', '/integrations/launch/exchange', body: {'code': code}));
    _token = reqString(j, 'token');
    _user = SessionUser.fromJson(asJson(j['user']));
    _embeddedFrom = reqString(j, 'system_title');
    return reqString(j, 'patient_id');
  }

  /// Оповестить экраны о смене состояния (после навигации).
  void refresh() => notifyListeners();

  void signOut() {
    _token = null;
    _user = null;
    _embeddedFrom = null;
    notifyListeners();
  }

  // -------------------------------------------------------------- patient

  Future<Json> dashboard(String pid) async {
    final d = _obj(await _call('GET', '/patients/$pid/dashboard'));
    final pending = {for (final id in d['emergency_alert_ids'] as List? ?? const []) id as String};
    _announceEmergencies([
      for (final n in d['notices'] as List? ?? const [])
        if (pending.contains(asJson(n)['alert_id'])) asJson(n),
    ]);
    return d;
  }

  Future<Json> history(String pid) async => _obj(await _call('GET', '/patients/$pid/history'));

  Future<Json> submitQuestionnaire(String pid, Instrument i, List<int> items, {required String idempotencyKey}) async =>
      _obj(
        await _call(
          'POST',
          '/patients/$pid/questionnaires',
          body: {'instrument': i.wire, 'item_scores': items},
          write: true,
          idempotencyKey: idempotencyKey,
        ),
      );

  Future<Json> markIntake(
    String pid, {
    required String slotDate,
    required IntakeSlot slot,
    required IntakeStatus status,
    MissedReason? reason,
  }) async => _obj(
    await _call(
      'POST',
      '/patients/$pid/intakes',
      body: {'slot_date': slotDate, 'slot': slot.wire, 'status': status.wire, 'missed_reason': ?reason?.wire},
      write: true,
    ),
  );

  Future<Json> reportSymptom(
    String pid, {
    required SymptomType type,
    String? phrase,
    required Tri affectsDailyLife,
    required Severity severity,
    required String idempotencyKey,
  }) async => _obj(
    await _call(
      'POST',
      '/patients/$pid/symptoms',
      body: {
        'normalized_type': type.wire,
        'patient_phrase': phrase,
        'affects_daily_life': affectsDailyLife.wire,
        'severity': severity.wire,
      },
      write: true,
      idempotencyKey: idempotencyKey,
    ),
  );

  Future<Json> sendMessage(
    String pid, {
    String? text,
    List<({String filename, String mimeType, List<int> bytes})> files = const [],
    required String idempotencyKey,
  }) async => _obj(
    await _call(
      'POST',
      '/patients/$pid/messages',
      body: {
        'text': text,
        'attachments': [
          for (final f in files)
            {'filename': f.filename, 'mime_type': f.mimeType, 'data_base64': base64Encode(f.bytes)},
        ],
      },
      write: true,
      idempotencyKey: idempotencyKey,
    ),
  );

  Future<Uint8List> attachment(String pid, String attachmentId) async {
    final res = await transport.send(
      'GET',
      '/patients/$pid/attachments/$attachmentId',
      headers: {if (_token != null) 'authorization': 'Bearer $_token'},
    );
    if (res.status >= 400) {
      final j = res.json;
      throw ApiException(res.status, j is Map ? (j['message'] as String? ?? 'Файл недоступен') : 'Файл недоступен');
    }
    return res.bytes;
  }

  /// Действие пациента с экстренным предупреждением — врач увидит его в карточке события.
  Future<void> safetyAction(String pid, String alertId, String action) async =>
      await _call('POST', '/patients/$pid/safety-actions', body: {'alert_id': alertId, 'action': action});

  Future<Json> patientState(String pid) async => _obj(await _call('GET', '/patients/$pid/state'));

  // -------------------------------------------------------------- chat

  /// Переписка с врачом по порядку; сообщения собеседника отмечаются прочитанными.
  Future<Json> chat(String pid) async => _obj(await _call('GET', '/patients/$pid/chat'));

  /// Сообщения собеседника прочитаны — переписка на экране. Без оповещения экранов, чтобы не зациклить перезагрузку.
  Future<void> markChatRead(String pid) async => await _call('POST', '/patients/$pid/chat/read');

  /// Ответ врача пациенту. Пациент пишет через [sendMessage]: там извлечение фактов и экран 112.
  Future<Json> sendDoctorMessage(String pid, String text) async =>
      _obj(await _call('POST', '/doctor/patients/$pid/messages', body: {'text': text}, write: true));

  /// Адрес Centrifugo и токен с разрешёнными каналами; `{"enabled": false}`, если не настроен.
  Future<Json> realtimeConnection() async => _obj(await _call('GET', '/realtime/connection'));

  // -------------------------------------------------------------- doctor

  Future<List<Json>> doctorPatients() async => _list(await _call('GET', '/doctor/patients'));
  Future<List<Json>> doctorQueue({bool includeResolved = false}) async =>
      _list(await _call('GET', '/doctor/queue${includeResolved ? '?include_resolved=true' : ''}'));
  Future<Json> dossier(String pid) async => _obj(await _call('GET', '/doctor/patients/$pid/timeline'));
  Future<List<Json>> audit(String pid) async => _list(await _call('GET', '/doctor/patients/$pid/audit'));
  Future<Json> rulesSummary() async => _obj(await _call('GET', '/contracts/rules'));

  Future<Json> alertAction(String alertId, String action) async =>
      _obj(await _call('POST', '/doctor/alerts/$alertId/$action', write: true));

  Future<Json> setSchedule(String pid, Instrument i, {int? intervalDays, bool? active}) async => _obj(
    await _call(
      'PUT',
      '/doctor/patients/$pid/questionnaire-schedules/${i.wire}',
      body: {'interval_days': ?intervalDays, 'active': ?active},
      write: true,
    ),
  );

  Future<Json> setRouting(String pid, RouteDecision d) async =>
      _obj(await _call('POST', '/doctor/patients/$pid/routing', body: {'decision': d.wire}, write: true));

  Future<Json> setContactDeadline(String pid, DateTime deadline) async => _obj(
    await _call('POST', '/doctor/patients/$pid/contact-deadline', body: {'deadline': iso(deadline)}, write: true),
  );

  // -------------------------------------------------------------- admin

  Future<List<Json>> bookingTasks() async => _list(await _call('GET', '/admin/booking-tasks'));
  Future<Json> updateBooking(String id, String status) async =>
      _obj(await _call('PATCH', '/admin/booking-tasks/$id', body: {'status': status}, write: true));
}
