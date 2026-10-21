import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:clinical_compass/app/app.dart';
import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/time/clock.dart';
import 'package:clinical_compass/data/api_client.dart';

/// 21 октября 2026, 09:00 UTC (12:00 в клинике) — «сейчас» и для backend, и для приложения.
final testNow = DateTime.utc(2026, 10, 21, 9);

/// Настоящий Python-backend (`backend/`) в отдельном процессе.
///
/// Демо-база заполняется один раз ([prepareTemplate]); каждый тест запускает
/// сервер на своей копии файла SQLite, поэтому тесты не влияют друг на друга.
class TestBackend {
  TestBackend._(this._process, this.baseUrl);

  final Process _process;
  final String baseUrl;

  static final Directory _root = Directory.systemTemp.createTempSync('cc_flutter_test_');
  static File get _template => File('${_root.path}/template.sqlite');

  static Map<String, String> _env(File db) => {
    ...Platform.environment,
    'PYTHONPATH': 'src',
    'CC_DATABASE_URL': 'sqlite:///${db.path}',
    'CC_STORAGE_DIR': '${_root.path}/files',
    'CC_FIXED_NOW': testNow.toIso8601String(),
    'CC_SEED_DEMO_DATA': 'true',
  };

  static Future<void> prepareTemplate() async {
    final result = await Process.run(
      'uv',
      ['run', '--no-sync', 'clinical-compass', 'seed'],
      workingDirectory: 'backend',
      environment: _env(_template),
    );
    if (result.exitCode != 0) {
      throw StateError('Не удалось подготовить демо-базу:\n${result.stdout}\n${result.stderr}');
    }
  }

  static Future<TestBackend> start() async {
    final db = _template.copySync('${_root.path}/db_${DateTime.now().microsecondsSinceEpoch}.sqlite');
    final port = await _freePort();
    final process = await Process.start(
      'uv',
      ['run', '--no-sync', 'clinical-compass', 'serve', '--port', '$port'],
      workingDirectory: 'backend',
      environment: _env(db),
    );
    final log = StringBuffer();
    process.stdout.transform(utf8.decoder).listen(log.write);
    process.stderr.transform(utf8.decoder).listen(log.write);
    final backend = TestBackend._(process, 'http://127.0.0.1:$port');
    await backend._waitHealthy(log);
    return backend;
  }

  /// Код запуска окна, как его получила бы МИС (демо-эндпоинт без ключа).
  Future<String> demoLaunch(String system, {required String doctor, required String patient}) async {
    final client = HttpClient();
    try {
      final req = await client.postUrl(Uri.parse('$baseUrl/integrations/demo/$system/launch'));
      req.headers.contentType = ContentType.json;
      req.write(jsonEncode({'doctor_external_id': doctor, 'patient_external_id': patient}));
      final res = await req.close();
      final body = jsonDecode(await res.transform(utf8.decoder).join()) as Map<String, Object?>;
      return body['code']! as String;
    } finally {
      client.close();
    }
  }

  Future<void> stop() async {
    _process.kill();
    await _process.exitCode;
  }

  Future<void> _waitHealthy(StringBuffer log) async {
    final client = HttpClient();
    try {
      for (var attempt = 0; attempt < 150; attempt++) {
        try {
          final res = await (await client.getUrl(Uri.parse('$baseUrl/health'))).close();
          await res.drain<void>();
          if (res.statusCode == 200) return;
        } on SocketException {
          // Сервер ещё стартует.
        }
        await Future<void>.delayed(const Duration(milliseconds: 100));
      }
    } finally {
      client.close();
    }
    _process.kill();
    throw StateError('Backend не запустился:\n$log');
  }

  static Future<int> _freePort() async {
    final socket = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
    final port = socket.port;
    await socket.close();
    return port;
  }
}

/// Выполняет запросы в корневой зоне: реальный ввод-вывод не зависит от
/// fake-async таймеров виджет-теста. Считает незавершённые запросы для [settle].
class RootZoneTransport implements ApiTransport {
  RootZoneTransport(this._inner);

  final ApiTransport _inner;
  static int inFlight = 0;

  @override
  Future<ApiResponse> send(String method, String path, {Object? body, Map<String, String> headers = const {}}) {
    inFlight++;
    return Zone.root.run(() => _inner.send(method, path, body: body, headers: headers).whenComplete(() => inFlight--));
  }
}

void useRealBackend() {
  setUpAll(() async {
    // flutter_test по умолчанию запрещает настоящие HTTP-запросы.
    HttpOverrides.global = null;
    await TestBackend.prepareTemplate();
  });
}

/// Поднять приложение поверх настоящего backend.
Future<TestBackend> pumpApp(WidgetTester tester, {Size size = const Size(1440, 900)}) async {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  final backend = (await tester.runAsync(TestBackend.start))!;
  addTearDown(() => tester.runAsync(backend.stop));
  final services = AppServices(
    api: ApiClient(RootZoneTransport(HttpTransport(backend.baseUrl))),
    clock: FixedClock(testNow.toLocal()),
  );
  await tester.pumpWidget(ClinicalCompassApp(services: services));
  await settle(tester);
  return backend;
}

/// Дождаться ответов backend и перерисовки (с продвижением времени анимаций).
Future<void> settle(WidgetTester tester) async {
  for (var i = 0; i < 200; i++) {
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 10)));
    await tester.pump(const Duration(milliseconds: 60));
    if (i >= 6 && RootZoneTransport.inFlight == 0) return;
  }
  throw StateError('Backend не ответил вовремя');
}

/// Снять дерево виджетов, чтобы остановить периодические обновления.
Future<void> unmount(WidgetTester tester) async {
  await tester.pumpWidget(const SizedBox());
  await tester.pump();
}
