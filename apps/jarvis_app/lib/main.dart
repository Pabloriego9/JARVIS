import 'dart:async';
import 'dart:io';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:window_manager/window_manager.dart';
import 'package:tray_manager/tray_manager.dart';

import 'api.dart';
import 'screens.dart';
import 'remote_worker.dart';

const cyan = Color(0xFF63E3FA);
const background = Color(0xFF080F1A);
const panel = Color(0xFF101D2D);

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  if (Platform.isWindows) {
    await windowManager.ensureInitialized();
    await windowManager.waitUntilReadyToShow(
      const WindowOptions(
        size: Size(1280, 820),
        minimumSize: Size(700, 580),
        title: 'JARVIS',
        center: true,
        backgroundColor: background,
      ),
      () async {
        await windowManager.show();
      },
    );
    await trayManager.setIcon('assets/jarvis.ico');
    await trayManager.setToolTip('JARVIS');
  }
  final api = JarvisApi();
  try {
    await api.load();
  } catch (_) {
    /* First launch continues without stored credentials. */
  }
  runApp(JarvisApp(api: api));
}

class JarvisApp extends StatelessWidget {
  final JarvisApi api;
  const JarvisApp({super.key, required this.api});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'JARVIS',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      scaffoldBackgroundColor: background,
      colorScheme: const ColorScheme.dark(
        primary: cyan,
        secondary: Color(0xFF7E9AFF),
        surface: panel,
      ),
      textTheme: const TextTheme(
        bodyMedium: TextStyle(height: 1.5),
        titleLarge: TextStyle(fontWeight: FontWeight.w600),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: background,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
        contentPadding: const EdgeInsets.all(16),
      ),
      cardTheme: CardThemeData(
        color: panel,
        elevation: 0,
        margin: const EdgeInsets.symmetric(vertical: 6),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: const BorderSide(color: Color(0xFF213348)),
        ),
      ),
      filledButtonTheme: FilledButtonThemeData(
        style: FilledButton.styleFrom(minimumSize: const Size(48, 48)),
      ),
      outlinedButtonTheme: OutlinedButtonThemeData(
        style: OutlinedButton.styleFrom(minimumSize: const Size(48, 48)),
      ),
    ),
    home: JarvisHome(api: api),
  );
}

class JarvisHome extends StatefulWidget {
  final JarvisApi api;
  const JarvisHome({super.key, required this.api});
  @override
  State<JarvisHome> createState() => _JarvisHomeState();
}

class _JarvisHomeState extends State<JarvisHome>
    with TrayListener, WidgetsBindingObserver {
  int selected = 0;
  Map<String, dynamic>? status;
  Timer? timer;
  Timer? eventTimer;
  late final remote = RemoteWorker(widget.api);
  bool foreground = true, pollingEvents = false;
  static const labels = [
    'Inicio',
    'Voz',
    'Archivos',
    'Tareas',
    'Memoria',
    'Dispositivos',
    'Navegador',
    'Programas',
    'Monitoreo',
    'Recordatorios',
    'Permisos',
    'Consumo',
    'Ajustes',
  ];
  static const icons = [
    Icons.blur_circular,
    Icons.graphic_eq,
    Icons.folder_outlined,
    Icons.checklist_rounded,
    Icons.auto_awesome_outlined,
    Icons.devices,
    Icons.language,
    Icons.apps,
    Icons.monitor_heart_outlined,
    Icons.notifications_none,
    Icons.shield_outlined,
    Icons.pie_chart_outline,
    Icons.tune,
  ];
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    if (Platform.isWindows) trayManager.addListener(this);
    refresh();
    timer = Timer.periodic(const Duration(seconds: 15), (_) => refresh());
    eventTimer = Timer.periodic(
      const Duration(seconds: 3),
      (_) => pollEvents(),
    );
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    foreground = state == AppLifecycleState.resumed;
  }

  Future<void> pollEvents() async {
    if (!foreground || pollingEvents || status == null) return;
    pollingEvents = true;
    try {
      await remote.poll();
      final cursor = await widget.api.storage.read(key: 'events_cursor') ?? '0';
      final rows =
          await widget.api.request('GET', '/v1/events?after=$cursor') as List;
      for (final row in rows) {
        if (row['kind'] == 'reminder' && mounted) {
          toast(context, 'Recordatorio: ${row['data']['title']}');
        }
      }
      if (rows.isNotEmpty) {
        await widget.api.storage.write(
          key: 'events_cursor',
          value: '${rows.last['seq']}',
        );
      }
    } catch (_) {
      /* Show connection health in the header; never replay an effect here. */
    } finally {
      pollingEvents = false;
    }
  }

  Future<void> refresh() async {
    try {
      final data = await widget.api.request('GET', '/v1/status');
      if (mounted) setState(() => status = Map<String, dynamic>.from(data));
    } catch (_) {
      if (mounted) setState(() => status = null);
    }
  }

  @override
  void onTrayIconMouseDown() {
    windowManager.show();
    windowManager.focus();
  }

  @override
  void dispose() {
    timer?.cancel();
    eventTimer?.cancel();
    WidgetsBinding.instance.removeObserver(this);
    if (Platform.isWindows) trayManager.removeListener(this);
    super.dispose();
  }

  Future<void> stop() async {
    try {
      await widget.api.request('POST', '/v1/stop');
      if (mounted) {
        toast(
          context,
          'Detención solicitada. Revisá los efectos iniciados en Tareas.',
        );
      }
    } catch (e) {
      if (mounted) toast(context, e.toString());
    }
  }

  Widget navigation(bool compact) => Container(
    width: compact ? 76 : 236,
    decoration: const BoxDecoration(
      color: Color(0xFF0B1522),
      border: Border(right: BorderSide(color: Color(0xFF1B2D41))),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 30, horizontal: 20),
          child: Row(
            children: [
              const Icon(Icons.blur_circular, color: cyan, size: 32),
              if (!compact)
                const Padding(
                  padding: EdgeInsets.only(left: 12),
                  child: Text(
                    'J A R V I S',
                    style: TextStyle(fontSize: 19, fontWeight: FontWeight.bold),
                  ),
                ),
            ],
          ),
        ),
        if (!compact)
          const Padding(
            padding: EdgeInsets.fromLTRB(24, 8, 0, 14),
            child: Text(
              'ESPACIO PERSONAL',
              style: TextStyle(
                fontSize: 10,
                letterSpacing: 2,
                color: Color(0xFF738AA4),
              ),
            ),
          ),
        Expanded(
          child: ListView(
            children: [
              for (var i = 0; i < labels.length; i++)
                Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 10,
                    vertical: 2,
                  ),
                  child: Tooltip(
                    message: labels[i],
                    child: Material(
                      color: selected == i
                          ? const Color(0xFF153247)
                          : Colors.transparent,
                      borderRadius: BorderRadius.circular(12),
                      child: InkWell(
                        borderRadius: BorderRadius.circular(12),
                        onTap: () {
                          setState(() => selected = i);
                          if (MediaQuery.sizeOf(context).width < 700) {
                            Navigator.of(context).pop();
                          }
                        },
                        child: Padding(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 15,
                            vertical: 14,
                          ),
                          child: Row(
                            children: [
                              Icon(
                                icons[i],
                                size: 21,
                                color: selected == i
                                    ? cyan
                                    : const Color(0xFF859BB3),
                              ),
                              if (!compact) ...[
                                const SizedBox(width: 14),
                                Expanded(
                                  child: Text(
                                    labels[i],
                                    style: const TextStyle(fontSize: 14),
                                  ),
                                ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                  ),
                ),
            ],
          ),
        ),
        if (!compact)
          const Padding(
            padding: EdgeInsets.all(22),
            child: Text(
              'TU ASISTENTE. TUS REGLAS.\nv0.1 · Desarrollo',
              style: TextStyle(
                fontSize: 10,
                height: 2,
                letterSpacing: 1,
                color: Color(0xFF5F7994),
              ),
            ),
          ),
      ],
    ),
  );

  Widget content() => switch (selected) {
    0 => ChatScreen(
      api: widget.api,
      connected: status != null,
      onSettings: () => setState(() => selected = 12),
    ),
    1 => VoiceScreen(api: widget.api),
    2 => FilesScreen(api: widget.api),
    3 => TasksScreen(api: widget.api),
    4 => MemoryScreen(api: widget.api),
    5 => DevicesScreen(api: widget.api),
    6 => BrowserScreen(api: widget.api),
    7 => ProgramsScreen(api: widget.api),
    8 => MonitorScreen(api: widget.api),
    9 => RemindersScreen(api: widget.api),
    10 => PermissionsScreen(api: widget.api),
    11 => DataScreen(
      api: widget.api,
      endpoint: '/v1/usage',
      title: 'Consumo y límites',
      description: 'Tokens informados por el proveedor. Las reservas se identifican como estimadas.',
    ),
    _ => SettingsScreen(api: widget.api, onSaved: refresh),
  };

  @override
  Widget build(BuildContext context) => CallbackShortcuts(
    bindings: {
      const SingleActivator(LogicalKeyboardKey.escape, control: true): stop,
    },
    child: Focus(
      autofocus: true,
      child: LayoutBuilder(
        builder: (context, bounds) {
          final mobile = bounds.maxWidth < 700;
          return Scaffold(
            drawer: mobile ? Drawer(child: navigation(false)) : null,
            appBar: mobile
                ? AppBar(
                    title: const Text('JARVIS'),
                    actions: [
                      IconButton(
                        onPressed: stop,
                        tooltip: 'Detener todo',
                        icon: const Icon(Icons.stop_circle_outlined),
                      ),
                    ],
                  )
                : null,
            body: SafeArea(
              child: Row(
                children: [
                  if (!mobile) navigation(bounds.maxWidth < 1050),
                  Expanded(
                    child: Column(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 24,
                            vertical: 17,
                          ),
                          decoration: const BoxDecoration(
                            border: Border(
                              bottom: BorderSide(color: Color(0xFF1B2D41)),
                            ),
                          ),
                          child: Row(
                            children: [
                              Icon(
                                status != null
                                    ? Icons.circle
                                    : Icons.circle_outlined,
                                size: 8,
                                color: status != null
                                    ? const Color(0xFF70DEAA)
                                    : Colors.orangeAccent,
                              ),
                              const SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  status != null
                                      ? 'Servidor conectado · ${status!['platform']}'
                                      : 'Modo local · backend sin conexión',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: Color(0xFFADC0D4),
                                  ),
                                ),
                              ),
                              if (!mobile)
                                Text(
                                  '${status?['model'] ?? 'gpt-6-astra'}  ',
                                  style: const TextStyle(
                                    fontSize: 12,
                                    color: cyan,
                                  ),
                                ),
                              if (!mobile)
                                OutlinedButton.icon(
                                  onPressed: stop,
                                  icon: const Icon(
                                    Icons.stop_circle_outlined,
                                    size: 17,
                                  ),
                                  label: const Text('Detener todo'),
                                ),
                            ],
                          ),
                        ),
                        Expanded(
                          child: KeyedSubtree(
                            key: ValueKey(selected),
                            child: content(),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          );
        },
      ),
    ),
  );
}

class CoreOrb extends StatefulWidget {
  final bool active;
  final double size;
  const CoreOrb({super.key, this.active = false, this.size = 180});
  @override
  State<CoreOrb> createState() => _CoreOrbState();
}

class _CoreOrbState extends State<CoreOrb> with SingleTickerProviderStateMixin {
  late final controller = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 9),
  );
  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    animate();
  }

  @override
  void didUpdateWidget(CoreOrb oldWidget) {
    super.didUpdateWidget(oldWidget);
    animate();
  }

  void animate() {
    if (widget.active && !MediaQuery.of(context).disableAnimations) {
      controller.repeat();
    } else {
      controller.stop();
    }
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Semantics(
    label: widget.active ? 'JARVIS trabajando' : 'JARVIS en espera',
    child: SizedBox(
      width: widget.size,
      height: widget.size,
      child: AnimatedBuilder(
        animation: controller,
        builder: (_, _) => CustomPaint(
          painter: OrbPainter(controller.value, widget.active),
          child: const Center(
            child: Icon(Icons.graphic_eq, color: cyan, size: 48),
          ),
        ),
      ),
    ),
  );
}

class OrbPainter extends CustomPainter {
  final double phase;
  final bool active;
  OrbPainter(this.phase, this.active);
  @override
  void paint(Canvas canvas, Size size) {
    final center = size.center(Offset.zero), radius = size.width / 2;
    canvas.drawCircle(
      center,
      radius * .75,
      Paint()
        ..shader = RadialGradient(
          colors: [
            cyan.withValues(alpha: active ? .20 : .09),
            Colors.transparent,
          ],
        ).createShader(Rect.fromCircle(center: center, radius: radius)),
    );
    for (var i = 0; i < 3; i++) {
      final r = radius * (.66 + i * .13);
      final paint = Paint()
        ..color = cyan.withValues(alpha: .55 - i * .14)
        ..style = PaintingStyle.stroke
        ..strokeWidth = i == 1 ? 2 : 1;
      for (var arc = 0; arc < 3; arc++) {
        canvas.drawArc(
          Rect.fromCircle(center: center, radius: r),
          phase * math.pi * 2 * (i.isEven ? 1 : -1) + arc * 2.094,
          i == 1 ? 1.5 : 1.9,
          false,
          paint,
        );
      }
    }
    for (var i = 0; i < 48; i++) {
      final a = i * math.pi / 24,
          p = Offset(math.cos(i * math.pi / 24), math.sin(i * math.pi / 24));
      canvas.drawLine(
        center + p * radius * .97,
        center + Offset(math.cos(a), math.sin(a)) * radius,
        Paint()
          ..color = cyan.withValues(alpha: .3)
          ..strokeWidth = 1,
      );
    }
  }

  @override
  bool shouldRepaint(OrbPainter oldDelegate) =>
      oldDelegate.phase != phase || oldDelegate.active != active;
}
