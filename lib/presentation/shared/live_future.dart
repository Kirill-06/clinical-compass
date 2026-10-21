import 'dart:async';

import 'package:flutter/material.dart';

import 'package:clinical_compass/app/app_services.dart';
import 'package:clinical_compass/core/design/components.dart';
import 'package:clinical_compass/data/api_client.dart';

/// Загружает данные с сервера и перезагружает их после любой записи
/// и (по желанию) периодически — так очередь врача видит новые события
/// от пациентов без ручного обновления. Прежние данные не мигают.
class LiveFuture<T> extends StatefulWidget {
  const LiveFuture({
    super.key,
    required this.load,
    required this.builder,
    this.reloadKey,
    this.loadingLabel = 'Загрузка…',
    this.placeholder,
    this.pollEvery,
  });

  final Future<T> Function() load;
  final Widget Function(BuildContext context, T data) builder;
  final Object? reloadKey;
  final String loadingLabel;
  final Widget? placeholder;

  /// Период фонового обновления (рабочая очередь врача).
  final Duration? pollEvery;

  @override
  State<LiveFuture<T>> createState() => _LiveFutureState<T>();
}

class _LiveFutureState<T> extends State<LiveFuture<T>> {
  ApiClient? _api;
  T? _data;
  bool _hasData = false;
  Object? _error;
  int _generation = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    final every = widget.pollEvery;
    if (every != null) _timer = Timer.periodic(every, (_) => unawaited(_reload()));
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final api = AppScope.read(context).api;
    if (!identical(api, _api)) {
      _api?.removeListener(_onChange);
      _api = api..addListener(_onChange);
      unawaited(_reload());
    }
  }

  @override
  void didUpdateWidget(covariant LiveFuture<T> old) {
    super.didUpdateWidget(old);
    if (old.reloadKey != widget.reloadKey) {
      _hasData = false;
      unawaited(_reload());
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _api?.removeListener(_onChange);
    super.dispose();
  }

  void _onChange() {
    if (_api?.isSignedIn ?? false) unawaited(_reload());
  }

  Future<void> _reload() async {
    final generation = ++_generation;
    try {
      final data = await widget.load();
      if (!mounted || generation != _generation) return;
      setState(() {
        _data = data;
        _hasData = true;
        _error = null;
      });
    } on Exception catch (e) {
      if (!mounted || generation != _generation) return;
      setState(() => _error = e);
    }
  }

  @override
  Widget build(BuildContext context) {
    final error = _error;
    if (!_hasData) {
      if (widget.placeholder != null) return widget.placeholder!;
      if (error != null) {
        return Center(
          child: ErrorState(message: describeError(error), onRetry: () => unawaited(_reload())),
        );
      }
      return Center(child: LoadingState(label: widget.loadingLabel));
    }
    return widget.builder(context, _data as T);
  }
}

String describeError(Object error) => switch (error) {
  ApiException(:final message) => message,
  FormatException(:final message) => 'Некорректный ответ сервера: $message',
  _ => error.toString().replaceFirst('Exception: ', ''),
};
