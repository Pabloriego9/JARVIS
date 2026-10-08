part of 'screens.dart';

class SettingsScreen extends StatefulWidget {
  final JarvisApi api;
  final Future<void> Function() onSaved;
  const SettingsScreen({super.key, required this.api, required this.onSaved});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final url = TextEditingController(text: widget.api.baseUrl),
      token = TextEditingController(text: widget.api.token);
  final code = TextEditingController();
  String message = '';
  bool receiveRemote = false;
  @override
  void initState() {
    super.initState();
    widget.api.storage.read(key: 'receive_remote').then((v) {
      if (mounted) setState(() => receiveRemote = v == 'true');
    });
  }

  Future<void> save() async {
    try {
      await widget.api.configure(url.text, token.text);
      await widget.onSaved();
      final status = await widget.api.request('GET', '/v1/status');
      setState(
        () =>
            message = 'Conectado · ${status['model']} · ${status['platform']}',
      );
    } catch (e) {
      setState(() => message = e.toString());
    }
  }

  Future<void> pair() async {
    try {
      await widget.api.configure(url.text, '');
      final result = await widget.api.request('POST', '/v1/pair', {
        'code': code.text.trim(),
        'name': Platform.isAndroid ? 'Mi Android' : 'Mi Windows',
        'capabilities': Platform.isAndroid
            ? ['files.saf', 'memory.local', 'intents']
            : ['desktop'],
      });
      token.text = result['token'];
      await save();
    } catch (e) {
      setState(() => message = e.toString());
    }
  }

  @override
  void dispose() {
    url.dispose();
    token.dispose();
    code.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Conexión y ajustes',
    subtitle: 'Elegí un servidor local en Windows o un backend privado disponible para tu teléfono.',
    child: ListView(
      children: [
        if (Platform.isAndroid)
          SwitchListTile(
            title: const Text('Recibir tareas mientras JARVIS está abierto'),
            subtitle: const Text(
              'Cada solicitud remota se confirma en este teléfono.',
            ),
            value: receiveRemote,
            onChanged: (value) async {
              await widget.api.storage.write(
                key: 'receive_remote',
                value: '$value',
              );
              setState(() => receiveRemote = value);
            },
          ),
        const Text('1. Conectá tu backend', style: TextStyle(fontSize: 18)),
        const SizedBox(height: 12),
        TextField(
          controller: url,
          decoration: const InputDecoration(
            labelText: 'Dirección del servidor',
            hintText: 'https://jarvis.tudominio.com',
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: token,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'Sesión del dispositivo (no es la clave de OpenAI)',
          ),
        ),
        const SizedBox(height: 12),
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton(
            onPressed: save,
            child: const Text('Guardar y comprobar'),
          ),
        ),
        const SizedBox(height: 28),
        const Text(
          '2. O emparejá con un código',
          style: TextStyle(fontSize: 18),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: code,
          decoration: const InputDecoration(
            labelText: 'Código de un solo uso del administrador',
          ),
        ),
        const SizedBox(height: 12),
        Align(
          alignment: Alignment.centerLeft,
          child: OutlinedButton(
            onPressed: pair,
            child: const Text('Emparejar este dispositivo'),
          ),
        ),
        const SizedBox(height: 24),
        const Text(
          '3. Probá el modelo y el audio; después concedé carpetas desde Permisos. La clave de IA se configura únicamente en el servidor.',
        ),
        const SizedBox(height: 12),
        OutlinedButton(
          onPressed: () async {
            try {
              final r = await widget.api.request(
                'POST',
                '/v1/provider/diagnose',
              );
              setState(() => message = pretty(r));
            } catch (e) {
              setState(() => message = e.toString());
            }
          },
          child: const Text('Probar conexión real con el modelo'),
        ),
        const SizedBox(height: 20),
        SelectableText(message),
        const SizedBox(height: 20),
        const Text(
          'Sin conexión: Android conserva sus memorias y el acceso concedido a archivos. La inferencia en nube requiere un backend disponible. No hay escucha permanente ni acciones remotas automáticas en esta versión.',
          style: TextStyle(color: Color(0xFF8CA3BB)),
        ),
      ],
    ),
  );
}

class MemoryScreen extends StatefulWidget {
  final JarvisApi api;
  const MemoryScreen({super.key, required this.api});
  @override
  State<MemoryScreen> createState() => _MemoryScreenState();
}

class _MemoryScreenState extends State<MemoryScreen> {
  List<dynamic> rows = [];
  String? error;
  bool local = Platform.isAndroid;
  final search = TextEditingController();
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final r = local
          ? await LocalDevice.call('memory.list', {'query': search.text})
          : await widget.api.request(
              'GET',
              '/v1/memories?q=${Uri.encodeComponent(search.text)}',
            );
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

  Future<void> edit([dynamic row]) async {
    final text = await askText(
      context,
      row == null ? '¿Qué querés recordar?' : 'Editar recuerdo',
      initial: row?['content'] ?? '',
      multiline: true,
    );
    if (text == null || text.trim().isEmpty) return;
    try {
      if (local) {
        await LocalDevice.call('memory.save', {
          'content': text,
          'id': row?['id'],
          'revision': row?['revision'],
        });
      } else {
        await widget.api.request(
          row == null ? 'POST' : 'PUT',
          row == null ? '/v1/memories' : '/v1/memories/${row['id']}',
          {
            'content': text,
            'kind': row?['kind'] ?? 'fact',
            'expected_revision': row?['revision'],
          },
        );
      }
      await load();
    } catch (e) {
      if (mounted) toast(context, e.toString());
    }
  }

  Future<void> remove(dynamic row) async {
    if (!await confirm(context, 'Olvidar recuerdo', row['content'])) return;
    try {
      if (local) {
        await LocalDevice.call('memory.delete', {
          'id': row['id'],
          'revision': row['revision'],
        });
      } else {
        await widget.api.request(
          'DELETE',
          '/v1/memories/${row['id']}?revision=${row['revision']}',
        );
      }
      await load();
    } catch (e) {
      if (mounted) toast(context, e.toString());
    }
  }

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Memoria',
    subtitle: local
        ? 'Recuerdos guardados en este teléfono, disponibles sin conexión.'
        : 'Recuerdos explícitos guardados en el servidor.',
    actions: [
      if (Platform.isAndroid)
        FilterChip(
          label: Text(local ? 'Este teléfono' : 'Servidor'),
          selected: local,
          onSelected: (v) {
            setState(() => local = v);
            load();
          },
        ),
      FilledButton.icon(
        onPressed: () => edit(),
        icon: const Icon(Icons.add),
        label: const Text('Recordar algo'),
      ),
    ],
    child: Column(
      children: [
        TextField(
          controller: search,
          onChanged: (_) => load(),
          decoration: const InputDecoration(
            hintText: 'Buscar recuerdos',
            prefixIcon: Icon(Icons.search),
          ),
        ),
        const SizedBox(height: 12),
        Expanded(
          child: error != null
              ? Center(child: Text(error!))
              : rows.isEmpty
              ? const Center(
                  child: Text('Tus preferencias y proyectos aparecerán acá.'),
                )
              : ListView(
                  children: [
                    for (final r in rows)
                      Card(
                        child: ListTile(
                          minVerticalPadding: 16,
                          title: Text(r['content']),
                          subtitle: Text(
                            'Revisión ${r['revision']} · ${local ? 'Este teléfono' : r['kind']}',
                          ),
                          onTap: () => edit(r),
                          trailing: IconButton(
                            tooltip: 'Olvidar',
                            onPressed: () => remove(r),
                            icon: const Icon(Icons.delete_outline),
                          ),
                        ),
                      ),
                  ],
                ),
        ),
      ],
    ),
  );
}

class PermissionsScreen extends StatefulWidget {
  final JarvisApi api;
  const PermissionsScreen({super.key, required this.api});
  @override
  State<PermissionsScreen> createState() => _PermissionsScreenState();
}

class _PermissionsScreenState extends State<PermissionsScreen> {
  List<dynamic> rows = [];
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final r = await widget.api.request('GET', '/v1/grants');
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

  Future<void> add() async {
    try {
      String? path;
      if (Platform.isWindows) {
        path = await FilePicker.getDirectoryPath();
      } else {
        path = await askText(context, 'Ruta de una carpeta en el servidor');
      }
      if (path == null || path.isEmpty || !mounted) return;
      if (!await confirm(
        context,
        'Autorizar carpeta del servidor',
        '$path\n\nLectura, búsqueda, creación, edición, copia, movimiento y cuarentena. Cada modificación pide confirmación.',
      )) {
        return;
      }
      await widget.api.request('POST', '/v1/grants', {
        'resource': path,
        'operations': [
          'list',
          'read',
          'search',
          'write',
          'mkdir',
          'copy',
          'move',
          'trash',
          'restore',
          'document',
        ],
      });
      await load();
    } catch (e) {
      if (mounted) toast(context, e.toString());
    }
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Permisos',
    subtitle: 'Los permisos del servidor son revocables. Android concede sus carpetas desde Archivos.',
    actions: [
      FilledButton.icon(
        onPressed: add,
        icon: const Icon(Icons.create_new_folder_outlined),
        label: const Text('Autorizar carpeta'),
      ),
    ],
    child: error != null
        ? Text(error!)
        : ListView(
            children: [
              for (final r in rows)
                Card(
                  child: ListTile(
                    title: Text(r['resource']),
                    subtitle: Text(
                      '${r['kind']} · ${r['mode']} · ${r['device_id']}',
                    ),
                    trailing: TextButton(
                      onPressed: () async {
                        if (await confirm(
                          context,
                          'Revocar permiso',
                          r['resource'],
                        )) {
                          try {
                            await widget.api.request(
                              'DELETE',
                              '/v1/grants/${r['id']}',
                            );
                            await load();
                          } catch (e) {
                            if (context.mounted) toast(context, e.toString());
                          }
                        }
                      },
                      child: const Text('Revocar'),
                    ),
                  ),
                ),
            ],
          ),
  );
}

class DevicesScreen extends StatefulWidget {
  final JarvisApi api;
  const DevicesScreen({super.key, required this.api});
  @override
  State<DevicesScreen> createState() => _DevicesScreenState();
}

class _DevicesScreenState extends State<DevicesScreen> {
  List<dynamic> rows = [];
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final r = await widget.api.request('GET', '/v1/devices');
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
  Widget build(BuildContext context) => PageBody(
    title: 'Tus dispositivos',
    subtitle: 'Android puede recibir tareas con la app abierta, recepción activada y confirmación en el teléfono.',
    actions: [
      OutlinedButton(onPressed: load, child: const Text('Actualizar')),
      FilledButton(
        onPressed: () async {
          try {
            final r = await widget.api.request('POST', '/v1/pairing');
            if (context.mounted) {
              await showDialog<void>(
                context: context,
                builder: (context) => AlertDialog(
                  title: const Text('Emparejar dispositivo'),
                  content: SelectableText(
                    '${r['code']}\nVence en ${r['expires_in']} segundos.\nIngresalo en Ajustes del otro dispositivo.',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Cerrar'),
                    ),
                  ],
                ),
              );
            }
          } catch (e) {
            if (context.mounted) toast(context, e.toString());
          }
        },
        child: const Text('Generar código'),
      ),
    ],
    child: error != null
        ? Text(error!)
        : ListView(
            children: [
              for (final r in rows)
                Card(
                  child: ListTile(
                    leading: Icon(
                      r['id'] == 'local' ? Icons.computer : Icons.phone_android,
                      color: cyan,
                    ),
                    title: Text(r['name']),
                    subtitle: Text(
                      r['revoked'] == 1 ? 'Revocado' : 'Sesión ${r['role']}',
                    ),
                    trailing: r['id'] == 'local'
                        ? null
                        : TextButton(
                            onPressed: () async {
                              if (await confirm(
                                context,
                                'Revocar dispositivo',
                                r['name'],
                              )) {
                                try {
                                  await widget.api.request(
                                    'DELETE',
                                    '/v1/devices/${r['id']}',
                                  );
                                  await load();
                                } catch (e) {
                                  if (context.mounted) {
                                    toast(context, e.toString());
                                  }
                                }
                              }
                            },
                            child: const Text('Revocar'),
                          ),
                  ),
                ),
            ],
          ),
  );
}

class BrowserScreen extends StatefulWidget {
  final JarvisApi api;
  const BrowserScreen({super.key, required this.api});
  @override
  State<BrowserScreen> createState() => _BrowserScreenState();
}

class _BrowserScreenState extends State<BrowserScreen> {
  final url = TextEditingController(text: 'https://example.com');
  String output = '';
  Future<void> open() async {
    try {
      final uri = Uri.parse(url.text);
      if (!['http', 'https'].contains(uri.scheme)) {
        throw ApiException('Usá una URL HTTP/HTTPS.');
      }
      final origin = '${uri.scheme}://${uri.authority}';
      if (!await confirm(
        context,
        'Autorizar sitio del navegador',
        '$origin\nPerfil separado de JARVIS. Cada interacción requiere confirmación.',
      )) {
        return;
      }
      final g = await widget.api.request('POST', '/v1/grants', {
        'kind': 'site',
        'resource': origin,
        'operations': [
          'new_page',
          'list_pages',
          'take_snapshot',
          'navigate_page',
          'click',
          'fill',
          'fill_form',
          'press_key',
          'wait_for',
          'take_screenshot',
        ],
      });
      final t = await widget.api.action('browser.call', {
        'site_grant_id': g['id'],
        'name': 'new_page',
        'arguments': {'url': url.text},
      });
      if (mounted) await showTask(context, widget.api, t['task_id']);
    } catch (e) {
      setState(() => output = e.toString());
    }
  }

  @override
  void dispose() {
    url.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Navegador JARVIS',
    subtitle: 'Chrome DevTools MCP propio · perfil aislado en el servidor o PC Windows.',
    child: ListView(
      children: [
        TextField(
          controller: url,
          decoration: const InputDecoration(
            labelText: 'Sitio para abrir',
            prefixIcon: Icon(Icons.language),
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            FilledButton(
              onPressed: open,
              child: const Text('Abrir sitio con permiso'),
            ),
            OutlinedButton(
              onPressed: () async {
                try {
                  final r = await widget.api.readTool('browser.catalog', {});
                  setState(
                    () => output = (r['data'] as List)
                        .map((t) => '${t['name']} · ${t['description']}')
                        .join('\n\n'),
                  );
                } catch (e) {
                  setState(() => output = e.toString());
                }
              },
              child: const Text('Consultar capacidades'),
            ),
          ],
        ),
        const SizedBox(height: 24),
        const Text(
          'Después de autorizar un sitio, podés pedir acciones desde el chat. Las herramientas disponibles se descubren en el host instalado.',
        ),
        const SizedBox(height: 20),
        SelectableText(output),
      ],
    ),
  );
}

class ProgramsScreen extends StatefulWidget {
  final JarvisApi api;
  const ProgramsScreen({super.key, required this.api});
  @override
  State<ProgramsScreen> createState() => _ProgramsScreenState();
}

class _ProgramsScreenState extends State<ProgramsScreen> {
  final package = TextEditingController();
  String output = '';
  Future<void> action(String name) async {
    try {
      final t = await widget.api.action(
        name,
        name == 'apps.list' ? {} : {'package_id': package.text.trim()},
      );
      if (mounted) await showTask(context, widget.api, t['task_id']);
    } catch (e) {
      setState(() => output = e.toString());
    }
  }

  @override
  void dispose() {
    package.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Programas',
    subtitle: 'Windows: identificadores exactos de winget. Android: instalación mediante el sistema.',
    child: ListView(
      children: [
        TextField(
          controller: package,
          decoration: InputDecoration(
            labelText: Platform.isAndroid
                ? 'Paquete Android o ID de winget'
                : 'Identificador winget (ej. VideoLAN.VLC)',
          ),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            for (final entry in {
              'apps.list': 'Ver instalados en PC',
              'apps.install': 'Instalar en PC',
              'apps.update': 'Actualizar en PC',
              'apps.uninstall': 'Desinstalar en PC',
            }.entries)
              OutlinedButton(
                onPressed: () => action(entry.key),
                child: Text(entry.value),
              ),
            if (Platform.isAndroid)
              FilledButton(
                onPressed: () async {
                  try {
                    await LocalDevice.call('apps.store', {
                      'package': package.text.trim(),
                    });
                  } catch (e) {
                    setState(() => output = e.toString());
                  }
                },
                child: const Text('Abrir tienda del teléfono'),
              ),
            if (Platform.isAndroid)
              OutlinedButton(
                onPressed: () async {
                  try {
                    await LocalDevice.call('apps.installApk');
                  } catch (e) {
                    setState(() => output = e.toString());
                  }
                },
                child: const Text('Elegir APK para instalar'),
              ),
          ],
        ),
        const SizedBox(height: 24),
        SelectableText(output),
      ],
    ),
  );
}

class MonitorScreen extends StatefulWidget {
  final JarvisApi api;
  const MonitorScreen({super.key, required this.api});
  @override
  State<MonitorScreen> createState() => _MonitorScreenState();
}

class _MonitorScreenState extends State<MonitorScreen> {
  Map<dynamic, dynamic>? data;
  String? error;
  Timer? timer;
  bool local = Platform.isAndroid;
  @override
  void initState() {
    super.initState();
    load();
    timer = Timer.periodic(const Duration(seconds: 3), (_) => load());
  }

  Future<void> load() async {
    try {
      final r = local
          ? await LocalDevice.call('system.metrics')
          : (await widget.api.request('GET', '/v1/metrics'))['data'];
      if (mounted) {
        setState(() {
          data = r;
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
    title: 'Monitoreo',
    subtitle:
        'Datos reales · ${local ? 'Este teléfono' : 'Servidor conectado'}',
    actions: [
      if (Platform.isAndroid)
        FilterChip(
          label: const Text('Este teléfono'),
          selected: local,
          onSelected: (v) {
            setState(() => local = v);
            load();
          },
        ),
    ],
    child: error != null
        ? Text(error!)
        : data == null
        ? const Center(child: CircularProgressIndicator())
        : ListView(
            children: [
              Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  for (final item in data!.entries)
                    SizedBox(
                      width: 245,
                      child: Card(
                        child: Padding(
                          padding: const EdgeInsets.all(24),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                '${item.key}',
                                style: const TextStyle(
                                  color: Color(0xFF8CA3BB),
                                ),
                              ),
                              const SizedBox(height: 12),
                              Text(
                                '${item.value}',
                                style: const TextStyle(
                                  fontSize: 22,
                                  color: cyan,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ),
                ],
              ),
            ],
          ),
  );
}

class RemindersScreen extends StatefulWidget {
  final JarvisApi api;
  const RemindersScreen({super.key, required this.api});
  @override
  State<RemindersScreen> createState() => _RemindersScreenState();
}

class _RemindersScreenState extends State<RemindersScreen> {
  List<dynamic> rows = [];
  String? error;
  @override
  void initState() {
    super.initState();
    load();
  }

  Future<void> load() async {
    try {
      final r = await widget.api.request('GET', '/v1/reminders');
      if (mounted) setState(() => rows = r);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> add() async {
    final title = await askText(context, '¿Qué querés recordar?');
    if (title == null || !mounted) return;
    final now = DateTime.now();
    final day = await showDatePicker(
      context: context,
      firstDate: now,
      lastDate: now.add(const Duration(days: 3650)),
      initialDate: now,
    );
    if (day == null || !mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.now(),
    );
    if (time == null) return;
    try {
      await widget.api.request('POST', '/v1/reminders', {
        'title': title,
        'due_at': DateTime(
          day.year,
          day.month,
          day.day,
          time.hour,
          time.minute,
        ).toUtc().toIso8601String(),
        'timezone': 'America/Argentina/Buenos_Aires',
      });
      await load();
    } catch (e) {
      if (mounted) toast(context, e.toString());
    }
  }

  @override
  Widget build(BuildContext context) => PageBody(
    title: 'Recordatorios',
    subtitle: 'Persisten en el backend. Entrega en la app; el servidor debe estar activo.',
    actions: [
      FilledButton.icon(
        onPressed: add,
        icon: const Icon(Icons.add),
        label: const Text('Crear recordatorio'),
      ),
      OutlinedButton(onPressed: load, child: const Text('Actualizar')),
    ],
    child: error != null
        ? Text(error!)
        : ListView(
            children: [
              for (final r in rows)
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.notifications_none, color: cyan),
                    title: Text(r['title']),
                    subtitle: Text(
                      '${DateTime.fromMillisecondsSinceEpoch((r['due'] * 1000).round()).toLocal()} · ${r['enabled'] == 1 ? 'Activo' : 'Entregado o desactivado'}',
                    ),
                    trailing: IconButton(
                      tooltip: 'Desactivar',
                      onPressed: () async {
                        try {
                          await widget.api.request(
                            'DELETE',
                            '/v1/reminders/${r['id']}',
                          );
                          await load();
                        } catch (e) {
                          if (context.mounted) toast(context, e.toString());
                        }
                      },
                      icon: const Icon(Icons.close),
                    ),
                  ),
                ),
            ],
          ),
  );
}

class DataScreen extends StatefulWidget {
  final JarvisApi api;
  final String endpoint, title, description;
  const DataScreen({
    super.key,
    required this.api,
    required this.endpoint,
    required this.title,
    required this.description,
  });
  @override
  State<DataScreen> createState() => _DataScreenState();
}

class _DataScreenState extends State<DataScreen> {
  late Future<dynamic> future = widget.api.request('GET', widget.endpoint);
  @override
  Widget build(BuildContext context) => PageBody(
    title: widget.title,
    subtitle: widget.description,
    actions: [
      OutlinedButton(
        onPressed: () =>
            setState(() => future = widget.api.request('GET', widget.endpoint)),
        child: const Text('Actualizar'),
      ),
    ],
    child: FutureBuilder<dynamic>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.hasError) return Text(snapshot.error.toString());
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final data = snapshot.data as Map;
        final records = data['records'] as List;
        return ListView(
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Text(
                  'Límite diario: ${data['limits']['daily_tokens']} tokens\nPor tarea: ${data['limits']['task_tokens']} tokens\nMáximo: ${data['limits']['max_steps']} pasos',
                ),
              ),
            ),
            for (final row in records)
              Card(
                child: ListTile(
                  title: Text(
                    '${row['tokens']} tokens · ${row['estimated'] == 1 ? 'Estimación' : 'Uso informado'}',
                  ),
                  subtitle: Text('${row['model']} · ${row['provider']}'),
                ),
              ),
          ],
        );
      },
    ),
  );
}
