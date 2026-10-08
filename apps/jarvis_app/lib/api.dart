import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;

class ApiException implements Exception {
  final String message;
  final Map<String, dynamic> details;
  ApiException(this.message, [this.details = const {}]);
  @override
  String toString() => message;
}

class JarvisApi {
  String baseUrl = 'http://127.0.0.1:8765';
  String token = '';
  final storage = const FlutterSecureStorage();
  final http.Client client;
  JarvisApi({http.Client? client}) : client = client ?? http.Client();

  Future<void> load() async {
    baseUrl = await storage.read(key: 'backend') ?? baseUrl;
    token = await storage.read(key: 'device_session') ?? '';
    if (Platform.isWindows && token.isEmpty) {
      final local = Platform.environment['LOCALAPPDATA'];
      if (local != null) {
        final file = File('$local/JARVIS/JARVIS/admin.token');
        final alternate = File('$local/JARVIS/admin.token');
        if (await file.exists()) token = (await file.readAsString()).trim();
        if (token.isEmpty && await alternate.exists()) {
          token = (await alternate.readAsString()).trim();
        }
      }
    }
  }

  static String validateUrl(String value) {
    final uri = Uri.parse(value.trim());
    if (uri.userInfo.isNotEmpty ||
        uri.query.isNotEmpty ||
        uri.fragment.isNotEmpty ||
        (uri.path.isNotEmpty && uri.path != '/')) {
      throw ApiException(
        'Usá la dirección del servidor, sin credenciales ni rutas.',
      );
    }
    final loopback = ['127.0.0.1', 'localhost', '::1'].contains(uri.host);
    if (uri.scheme != 'https' && !(uri.scheme == 'http' && loopback)) {
      throw ApiException('Las conexiones remotas requieren HTTPS.');
    }
    return value.trim().replaceAll(RegExp(r'/$'), '');
  }

  Future<void> configure(String url, String session) async {
    baseUrl = validateUrl(url);
    token = session.trim();
    await storage.write(key: 'backend', value: baseUrl);
    await storage.write(key: 'device_session', value: token);
  }

  Future<dynamic> request(String method, String path, [Object? body]) async {
    final request = http.Request(method, Uri.parse('$baseUrl$path'));
    request.headers.addAll({
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    });
    if (body != null) request.body = jsonEncode(body);
    final response = await http.Response.fromStream(
      await client.send(request).timeout(const Duration(seconds: 30)),
    );
    final dynamic data = response.body.isEmpty
        ? null
        : jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode >= 400) {
      throw ApiException(
        data is Map
            ? '${data['user_message'] ?? data['detail'] ?? 'Error del servidor'}'
            : 'Error ${response.statusCode}',
        data is Map ? Map<String, dynamic>.from(data) : {},
      );
    }
    return data;
  }

  Future<Map<String, dynamic>> action(
    String name,
    Map<String, dynamic> arguments, {
    String? version,
    String deviceId = 'local',
  }) async {
    return Map<String, dynamic>.from(
      await request('POST', '/v1/tasks', {
        'title': name,
        'device_id': deviceId,
        'idempotency_key': 'app-${DateTime.now().microsecondsSinceEpoch}',
        'actions': [
          {
            'tool_name': name,
            'arguments': arguments,
            'expected_resource_version': version,
          },
        ],
      }),
    );
  }

  Future<dynamic> readTool(String name, Map<String, dynamic> arguments) async {
    final result = await action(name, arguments);
    for (var i = 0; i < 100; i++) {
      final task = await request('GET', '/v1/tasks/${result['task_id']}');
      if (task['status'] == 'completed') {
        final steps = task['steps'] as List;
        return jsonDecode(steps.last['result']);
      }
      if ([
        'failed',
        'uncertain',
        'cancelled',
        'awaiting_approval',
      ].contains(task['status'])) {
        throw ApiException(
          '${task['error'] ?? 'La operación requiere revisión en Tareas.'}',
        );
      }
      await Future<void>.delayed(const Duration(milliseconds: 100));
    }
    throw ApiException(
      'La operación sigue en curso. Podés revisarla en Tareas.',
    );
  }

  Future<String> transcribe(String path) async {
    final request = http.MultipartRequest(
      'POST',
      Uri.parse('$baseUrl/v1/voice/transcribe'),
    );
    request.headers['Authorization'] = 'Bearer $token';
    // The server validates the actual supported format; record produces a WAV file.
    final bytes = await File(path).readAsBytes();
    request.files.add(
      http.MultipartFile.fromBytes(
        'file',
        bytes,
        filename: 'voice.wav',
        contentType: http.MediaType('audio', 'wav'),
      ),
    );
    final response = await http.Response.fromStream(await client.send(request));
    final data = jsonDecode(utf8.decode(response.bodyBytes));
    if (response.statusCode >= 400) {
      throw ApiException('${data['user_message'] ?? data['detail']}');
    }
    return data['text'];
  }

  Future<List<int>> speech(String text) async {
    final r = await client.post(
      Uri.parse('$baseUrl/v1/voice/speak'),
      headers: {
        'Authorization': 'Bearer $token',
        'Content-Type': 'application/json',
      },
      body: jsonEncode({'text': text}),
    );
    if (r.statusCode >= 400) {
      throw ApiException('La síntesis de voz no está disponible.');
    }
    return r.bodyBytes;
  }
}

class LocalDevice {
  static const channel = MethodChannel('jarvis/device');
  static Future<dynamic> call(
    String method, [
    Map<String, dynamic>? arguments,
  ]) async {
    if (!Platform.isAndroid) {
      throw ApiException('Esta acción local corresponde al teléfono Android.');
    }
    return await channel.invokeMethod(method, arguments);
  }
}
