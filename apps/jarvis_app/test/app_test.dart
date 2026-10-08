import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:jarvis_app/api.dart';
import 'package:jarvis_app/main.dart';

void main() {
  setUp(() => FlutterSecureStorage.setMockInitialValues({}));
  test('remote connections require HTTPS and reject credential URLs', () {
    expect(
      JarvisApi.validateUrl('http://127.0.0.1:8765'),
      'http://127.0.0.1:8765',
    );
    expect(
      JarvisApi.validateUrl('https://jarvis.example/'),
      'https://jarvis.example',
    );
    for (final url in [
      'http://192.168.1.5:8765',
      'https://user:secret@host.example',
      'https://host.example?token=secret',
    ]) {
      expect(() => JarvisApi.validateUrl(url), throwsA(isA<ApiException>()));
    }
  });
  test('action includes target, version and a deduplication key', () async {
    late Map<String, dynamic> body;
    final api = JarvisApi(
      client: MockClient((r) async {
        body = jsonDecode(r.body);
        return http.Response('{"task_id":"t"}', 200);
      }),
    );
    await api.action('files.write', {
      'path': 'note.md',
      'content': 'new',
    }, version: 'hash');
    expect(body['device_id'], 'local');
    expect(body['actions'][0]['expected_resource_version'], 'hash');
    expect(body['idempotency_key'], isNotEmpty);
  });
  testWidgets('home exposes setup and never invents a connected model', (
    tester,
  ) async {
    final api = JarvisApi(
      client: MockClient(
        (_) async => http.Response('{"detail":"No conectado"}', 401),
      ),
    );
    await tester.pumpWidget(JarvisApp(api: api));
    await tester.pumpAndSettle();
    expect(find.text('Modo local · backend sin conexión'), findsOneWidget);
    expect(find.text('Configurar conexión'), findsOneWidget);
    await tester.ensureVisible(find.text('Configurar conexión'));
    await tester.tap(find.text('Configurar conexión'));
    await tester.pumpAndSettle();
    expect(find.text('Guardar y comprobar'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
  testWidgets('mobile layout supports large text without overflow', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    final api = JarvisApi(
      client: MockClient(
        (_) async => http.Response('{"detail":"offline"}', 401),
      ),
    );
    await tester.pumpWidget(
      MediaQuery(
        data: const MediaQueryData(textScaler: TextScaler.linear(1.4)),
        child: JarvisApp(api: api),
      ),
    );
    await tester.pumpAndSettle();
    expect(find.byTooltip('Open navigation menu'), findsOneWidget);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });
}
