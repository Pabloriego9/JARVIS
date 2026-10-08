import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:record/record.dart';
import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import 'package:file_picker/file_picker.dart';

import 'api.dart';
import 'main.dart';
part 'files_screen.dart';
part 'management_screens.dart';

void toast(BuildContext context, String text) =>
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(text)));
String pretty(dynamic value) =>
    const JsonEncoder.withIndent('  ').convert(value);
String taskLabel(String? value) =>
    const {
      'pending': 'Pendiente',
      'planning': 'Pensando',
      'running': 'Ejecutando',
      'awaiting_approval': 'Esperando tu confirmación',
      'completed': 'Completada',
      'failed': 'Fallida',
      'cancelled': 'Cancelada',
      'uncertain': 'Requiere comprobar el resultado',
    }[value] ??
    value ??
    'En espera';

Future<String?> askText(
  BuildContext context,
  String title, {
  String initial = '',
  bool multiline = false,
}) async {
  final controller = TextEditingController(text: initial);
  final result = await showDialog<String>(
    context: context,
    builder: (context) => AlertDialog(
      title: Text(title),
      content: SizedBox(
        width: 520,
        child: TextField(
          controller: controller,
          autofocus: true,
          minLines: multiline ? 4 : 1,
          maxLines: multiline ? 12 : 1,
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, controller.text),
          child: const Text('Continuar'),
        ),
      ],
    ),
  );
  controller.dispose();
  return result;
}

Future<bool> confirm(
  BuildContext context,
  String title,
  String content,
) async =>
    await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: SingleChildScrollView(child: SelectableText(content)),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirmar esta operación'),
          ),
        ],
      ),
    ) ??
    false;

class PageBody extends StatelessWidget {
  final String title, subtitle;
  final Widget child;
  final List<Widget> actions;
  const PageBody({
    super.key,
    required this.title,
    this.subtitle = '',
    required this.child,
    this.actions = const [],
  });
  @override
  Widget build(BuildContext context) => Padding(
    padding: EdgeInsets.all(MediaQuery.sizeOf(context).width < 700 ? 16 : 30),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 20,
          runSpacing: 12,
          children: [
            Text(
              title,
              style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w600),
            ),
            ...actions,
          ],
        ),
        if (subtitle.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(top: 7),
            child: Text(
              subtitle,
              style: const TextStyle(color: Color(0xFF8CA3BB)),
            ),
          ),
        const SizedBox(height: 22),
        Expanded(child: child),
      ],
    ),
  );
}

class ChatScreen extends StatefulWidget {
  final JarvisApi api;
  final bool connected;
  final VoidCallback onSettings;
  const ChatScreen({
    super.key,
    required this.api,
    required this.connected,
    required this.onSettings,
  });
  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final input = TextEditingController();
  final scroll = ScrollController();
  List<Map<String, dynamic>> messages = [];
  String? conversation, taskId, state;
  Timer? timer;
  int cursor = 0;
  String draft = '';
  bool sending = false;
  @override
  void initState() {
    super.initState();
    restore();
  }

  Future<void> restore() async {
    try {
      conversation = await widget.api.storage.read(key: 'conversation');
      if (conversation != null) {
        final result = await widget.api.request(
          'GET',
          '/v1/conversations/$conversation/messages',
        );
        if (mounted) {
          setState(() => messages = List<Map<String, dynamic>>.from(result));
        }
      }
    } catch (_) {
      /* Conversation remains available when the server reconnects. */
    }
  }

  Future<void> send() async {
    final text = input.text.trim();
    if (text.isEmpty || sending) return;
    setState(() {
      sending = true;
      messages.add({'role': 'user', 'content': text});
      input.clear();
      draft = '';
      state = 'pending';
    });
    try {
      final result = await widget.api.request('POST', '/v1/chat', {
        'message': text,
        'conversation_id': conversation,
        'device_id': 'local',
        'idempotency_key': 'chat-${DateTime.now().microsecondsSinceEpoch}',
      });
      conversation = result['conversation_id'];
      taskId = result['task_id'];
      cursor = 0;
      await widget.api.storage.write(key: 'conversation', value: conversation);
      timer?.cancel();
      timer = Timer.periodic(const Duration(milliseconds: 450), (_) => poll());
    } catch (e) {
      if (mounted) {
        setState(() {
          sending = false;
          state = 'failed';
          messages.add({'role': 'error', 'content': e.toString()});
        });
      }
    }
  }

  bool polling = false;
  Future<void> poll() async {
    if (polling || taskId == null) return;
    polling = true;
    try {
      final rows = await widget.api.request(
        'GET',
        '/v1/events?task_id=$taskId&after=$cursor',
      ) as List;
      if (!mounted) return;
      setState(() {
        for (final event in rows) {
          cursor = event['seq'];
          final data = event['data'];
          if (event['kind'] == 'text_delta') draft += data['text'] as String;
          if (event['kind'] == 'message') {
            messages.add({'role': 'assistant', 'content': data['text']});
            draft = '';
          }
          if (event['kind'] == 'task_status') state = data['status'];
          if (event['kind'] == 'error') {
            messages.add({
              'role': 'error',
              'content': data['user_message'] ?? data['message'] ?? 'Error',
            });
          }
        }
        if ([
          'completed',
          'failed',
          'cancelled',
          'uncertain',
          'awaiting_approval',
        ].contains(state)) {
          sending = false;
          timer?.cancel();
        }
      });
    } catch (e) {
      timer?.cancel();
      if (mounted) {
        setState(() {
          sending = false;
          state = 'uncertain';
          messages.add({
            'role': 'error',
            'content': 'Conexión interrumpida. Revisá Tareas antes de repetir.',
          });
        });
      }
    } finally {
      polling = false;
    }
  }

  @override
  void dispose() {
    input.dispose();
    scroll.dispose();
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Tu espacio, bajo control.',
    subtitle: 'Conversá, organizá y actuá con JARVIS.',
    actions: [
      TextButton.icon(
        onPressed: () async {
          await widget.api.storage.delete(key: 'conversation');
          setState(() {
            conversation = null;
            messages = [];
          });
        },
        icon: const Icon(Icons.add, size: 16),
        label: const Text('Nueva conversación'),
      ),
    ],
    child: Column(
      children: [
        Expanded(
          child: messages.isEmpty
              ? SingleChildScrollView(
                  child: Center(
                    child: Column(
                      children: [
                        const SizedBox(height: 20),
                        CoreOrb(active: sending, size: 200),
                        const SizedBox(height: 26),
                        const Text(
                          '¿En qué trabajamos hoy?',
                          style: TextStyle(
                            fontSize: 26,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'Un lugar para tus ideas, tus archivos y tus próximas acciones.',
                          textAlign: TextAlign.center,
                          style: TextStyle(color: Color(0xFF8CA3BB)),
                        ),
                        const SizedBox(height: 26),
                        Wrap(
                          spacing: 12,
                          runSpacing: 12,
                          alignment: WrapAlignment.center,
                          children: [
                            for (final hint in [
                              '¿Qué recordás de mí?',
                              'Mostrame el estado del sistema',
                              'Ayudame a organizar mis archivos',
                            ])
                              OutlinedButton(
                                onPressed: () =>
                                    setState(() => input.text = hint),
                                child: Text(hint),
                              ),
                          ],
                        ),
                        if (!widget.connected)
                          Padding(
                            padding: const EdgeInsets.only(top: 24),
                            child: FilledButton.tonalIcon(
                              onPressed: widget.onSettings,
                              icon: const Icon(Icons.link),
                              label: const Text('Configurar conexión'),
                            ),
                          ),
                      ],
                    ),
                  ),
                )
              : ListView.builder(
                  controller: scroll,
                  itemCount: messages.length + (draft.isEmpty ? 0 : 1),
                  itemBuilder: (_, i) {
                    final m = i < messages.length
                        ? messages[i]
                        : {'role': 'assistant', 'content': draft};
                    final mine = m['role'] == 'user';
                    return Align(
                      alignment: mine
                          ? Alignment.centerRight
                          : Alignment.centerLeft,
                      child: Container(
                        constraints: const BoxConstraints(maxWidth: 740),
                        margin: const EdgeInsets.only(bottom: 16),
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: mine ? const Color(0xFF173149) : panel,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              mine
                                  ? 'VOS'
                                  : m['role'] == 'error'
                                  ? 'DIAGNÓSTICO'
                                  : 'JARVIS',
                              style: TextStyle(
                                fontSize: 10,
                                letterSpacing: 1.5,
                                color: m['role'] == 'error'
                                    ? Colors.orangeAccent
                                    : cyan,
                              ),
                            ),
                            const SizedBox(height: 8),
                            SelectableText('${m['content']}'),
                          ],
                        ),
                      ),
                    );
                  },
                ),
        ),
        if (state != null)
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Row(
              children: [
                Expanded(
                  child: Text(
                    taskLabel(state),
                    style: const TextStyle(color: cyan, fontSize: 12),
                  ),
                ),
                if (state == 'awaiting_approval')
                  TextButton(
                    onPressed: () => showTask(context, widget.api, taskId!),
                    child: const Text('Revisar operación'),
                  ),
                if (sending)
                  TextButton(
                    onPressed: () =>
                        widget.api.request('POST', '/v1/tasks/$taskId/cancel'),
                    child: const Text('Cancelar'),
                  ),
              ],
            ),
          ),
        TextField(
          controller: input,
          minLines: 1,
          maxLines: 5,
          onSubmitted: (_) => send(),
          textInputAction: TextInputAction.send,
          decoration: InputDecoration(
            hintText: 'Escribile a JARVIS…',
            suffixIcon: IconButton(
              onPressed: sending ? null : send,
              tooltip: 'Enviar mensaje al servidor',
              icon: const Icon(Icons.arrow_upward, color: cyan),
            ),
          ),
        ),
        const Padding(
          padding: EdgeInsets.only(top: 10),
          child: Text(
            'Destino: servidor conectado · Las acciones sensibles requieren confirmación.',
            style: TextStyle(fontSize: 11, color: Color(0xFF6B829B)),
          ),
        ),
      ],
    ),
  );
}

Future<void> showTask(BuildContext context, JarvisApi api, String id) async {
  try {
    final task = await api.request('GET', '/v1/tasks/$id');
    if (!context.mounted) return;
    final actions = task['actions'] as List;
    final index = task['index'] as int;
    final waiting =
        task['status'] == 'awaiting_approval' && index < actions.length;
    final text =
        'Destino: ${task['device_id']}\nEstado: ${taskLabel(task['status'])}\n\n${pretty(waiting ? actions[index] : task['steps'])}${task['error'] == null ? '' : '\n${task['error']}'}';
    if (waiting) {
      if (await confirm(context, 'Revisar ${task['title']}', text)) {
        await api.request(
          'POST',
          '/v1/approvals/${actions[index]['approval_id']}',
        );
        if (context.mounted) {
          toast(context, 'Confirmación enviada. La tarea continúa.');
        }
      }
    } else {
      await showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(task['title']),
          content: SizedBox(
            width: 700,
            child: SingleChildScrollView(child: SelectableText(text)),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cerrar'),
            ),
            if (![
              'completed',
              'failed',
              'cancelled',
              'uncertain',
            ].contains(task['status']))
              TextButton(
                onPressed: () async {
                  await api.request('POST', '/v1/tasks/$id/cancel');
                  if (context.mounted) Navigator.pop(context);
                },
                child: const Text('Cancelar tarea'),
              ),
          ],
        ),
      );
    }
  } catch (e) {
    if (context.mounted) toast(context, e.toString());
  }
}

class TasksScreen extends StatefulWidget {
  final JarvisApi api;
  const TasksScreen({super.key, required this.api});
  @override
  State<TasksScreen> createState() => _TasksScreenState();
}

class _TasksScreenState extends State<TasksScreen> {
  List<dynamic> rows = [];
  String? error;
  Timer? timer;
  @override
  void initState() {
    super.initState();
    load();
    timer = Timer.periodic(const Duration(seconds: 2), (_) => load());
  }

  Future<void> load() async {
    try {
      final r = await widget.api.request('GET', '/v1/tasks');
      if (mounted) {
        setState(() {
          rows = r;
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Tareas y planes',
    subtitle: 'Cada paso tiene un destino, un resultado y una evidencia.',
    child: error != null
        ? Center(child: Text(error!))
        : rows.isEmpty
        ? const Center(
            child: Text('Las tareas aparecerán acá cuando envíes una orden.'),
          )
        : ListView(
            children: [
              for (final r in rows)
                Card(
                  child: ListTile(
                    minVerticalPadding: 18,
                    leading: Icon(
                      r['status'] == 'completed'
                          ? Icons.check_circle_outline
                          : Icons.pending_outlined,
                      color: cyan,
                    ),
                    title: Text(r['title']),
                    subtitle: Text(
                      '${taskLabel(r['status'])} · ${r['device_id']}',
                    ),
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => showTask(context, widget.api, r['id']),
                  ),
                ),
            ],
          ),
  );
}

class VoiceScreen extends StatefulWidget {
  final JarvisApi api;
  const VoiceScreen({super.key, required this.api});
  @override
  State<VoiceScreen> createState() => _VoiceScreenState();
}

class _VoiceScreenState extends State<VoiceScreen> {
  final recorder = AudioRecorder(), player = AudioPlayer();
  final transcript = TextEditingController();
  String state = 'Pulsá para hablar', response = '';
  bool recording = false, busy = false;
  String? voiceTask;
  Future<void> toggle() async {
    try {
      if (recording) {
        final path = await recorder.stop();
        setState(() {
          recording = false;
          busy = true;
          state = 'Transcribiendo…';
        });
        if (path != null) {
          try {
            transcript.text = await widget.api.transcribe(path);
          } finally {
            await File(path).delete();
          }
        }
        if (mounted) {
          setState(() {
            state = 'Revisá la transcripción antes de enviar';
            busy = false;
          });
        }
      } else {
        await player.stop();
        if (!await recorder.hasPermission()) {
          throw ApiException(
            'Concedé permiso al micrófono desde Android o Windows.',
          );
        }
        final dir = await getTemporaryDirectory();
        await recorder.start(
          const RecordConfig(encoder: AudioEncoder.wav, numChannels: 1),
          path: '${dir.path}/jarvis-voice.wav',
        );
        setState(() {
          recording = true;
          state = 'Escuchando · pulsá para terminar';
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          busy = false;
          state = e.toString();
        });
      }
    }
  }

  Future<void> send() async {
    setState(() {
      busy = true;
      state = 'Pensando…';
    });
    try {
      final task = await widget.api.request('POST', '/v1/chat', {
        'message': transcript.text,
        'idempotency_key': 'voice-${DateTime.now().microsecondsSinceEpoch}',
      });
      voiceTask = task['task_id'];
      for (var i = 0; i < 180 && mounted && busy; i++) {
        final row = await widget.api.request('GET', '/v1/tasks/$voiceTask');
        if (row['status'] == 'completed') {
          final messages = await widget.api.request(
            'GET',
            '/v1/conversations/${task['conversation_id']}/messages',
          ) as List;
          response = messages.last['content'];
          final audio = await widget.api.speech(
            response.substring(0, response.length.clamp(0, 4000)),
          );
          if (!mounted || !busy) return;
          await player.play(BytesSource(Uint8List.fromList(audio)));
          setState(() {
            state = 'Respuesta · voz sintética';
            busy = false;
          });
          return;
        }
        if ([
          'failed',
          'cancelled',
          'uncertain',
          'awaiting_approval',
        ].contains(row['status'])) {
          throw ApiException('${taskLabel(row['status'])}. Revisá Tareas.');
        }
        await Future<void>.delayed(const Duration(seconds: 1));
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          state = e.toString();
          busy = false;
        });
      }
    }
  }

  Future<void> stop() async {
    busy = false;
    await player.stop();
    await recorder.cancel();
    if (voiceTask != null) {
      await widget.api.request('POST', '/v1/tasks/$voiceTask/cancel');
    }
    if (mounted) {
      setState(() {
        recording = false;
        state = 'Detenido';
      });
    }
  }

  @override
  void dispose() {
    busy = false;
    recorder.dispose();
    player.dispose();
    transcript.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Conversación de voz',
    subtitle: 'Audio temporal · voz y transcripción independientes del modelo conversacional.',
    child: SingleChildScrollView(
      child: Column(
        children: [
          CoreOrb(active: recording || busy, size: 190),
          const SizedBox(height: 20),
          Text(state, textAlign: TextAlign.center),
          const SizedBox(height: 18),
          Wrap(
            spacing: 12,
            children: [
              FilledButton.icon(
                onPressed: busy ? null : toggle,
                icon: Icon(recording ? Icons.stop : Icons.mic),
                label: Text(
                  recording ? 'Terminar grabación' : 'Pulsar para hablar',
                ),
              ),
              OutlinedButton(
                onPressed: stop,
                child: const Text('Interrumpir voz y tarea'),
              ),
            ],
          ),
          const SizedBox(height: 24),
          TextField(
            controller: transcript,
            minLines: 3,
            maxLines: 8,
            decoration: const InputDecoration(
              labelText: 'Transcripción editable',
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: busy ? null : send,
            child: const Text('Enviar al agente'),
          ),
          if (response.isNotEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: SelectableText(response),
              ),
            ),
        ],
      ),
    ),
  );
}
