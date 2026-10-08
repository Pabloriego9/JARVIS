part of 'screens.dart';

class FilesScreen extends StatefulWidget {
  final JarvisApi api;
  const FilesScreen({super.key, required this.api});
  @override
  State<FilesScreen> createState() => _FilesScreenState();
}

class _FilesScreenState extends State<FilesScreen> {
  bool local = Platform.isAndroid;
  List<dynamic> grants = [], rows = [];
  String? root, error;
  String path = '.';
  final search = TextEditingController();
  @override
  void initState() {
    super.initState();
    loadGrants();
  }

  Future<void> loadGrants() async {
    try {
      final result = local
          ? await LocalDevice.call('files.grants')
          : await widget.api.request('GET', '/v1/grants');
      if (!mounted) return;
      setState(() {
        grants = (result as List)
            .where((g) => local || g['kind'] == 'folder')
            .toList();
        root = grants.isEmpty ? null : grants.first[local ? 'uri' : 'id'];
        path = local ? (root ?? '.') : '.';
        error = null;
      });
      if (root != null) await load();
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> load() async {
    if (root == null) return;
    try {
      final result = local
          ? await LocalDevice.call('files.list', {'tree': root, 'uri': path})
          : await widget.api.readTool('files.list', {
              'grant_id': root,
              'path': path,
            });
      if (mounted) {
        setState(() {
          rows = local ? result : result['data'];
          error = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> searchFiles() async {
    if (root == null) return;
    try {
      if (local) {
        await load();
        if (mounted) {
          setState(
            () => rows = rows
                .where(
                  (r) => r['name'].toString().toLowerCase().contains(
                    search.text.toLowerCase(),
                  ),
                )
                .toList(),
          );
        }
      } else {
        final r = await widget.api.readTool('files.search', {
          'grant_id': root,
          'path': '.',
          'query': search.text,
        });
        if (mounted) setState(() => rows = r['data']['items']);
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    }
  }

  Future<void> edit([dynamic row]) async {
    if (root == null) return;
    try {
      var name = row?['path'] ?? row?['uri'];
      String content = '';
      String? version;
      if (row != null) {
        final r = local
            ? await LocalDevice.call('files.read', {
                'tree': root,
                'uri': row['uri'],
              })
            : await widget.api.readTool('files.read', {
                'grant_id': root,
                'path': row['path'],
              });
        content = local ? r['content'] : r['data']['content'];
        version = local ? r['version'] : r['resource_version'];
      } else {
        if (!mounted) return;
        name = await askText(
          context,
          'Nombre del nuevo archivo',
          initial: 'nota.md',
        );
        if (name == null || name.isEmpty) return;
        if (!local && path != '.') name = '$path/$name';
      }
      if (!mounted) return;
      final text = await askText(
        context,
        row == null ? 'Crear $name' : 'Editar ${row['name']}',
        initial: content,
        multiline: true,
      );
      if (text == null || !mounted) return;
      if (!await confirm(
        context,
        'Revisar contenido antes de guardar',
        'Destino: ${local ? 'Este teléfono' : 'Servidor'}\nArchivo: $name\n\n$text',
      )) {
        return;
      }
      if (local) {
        await LocalDevice.call(row == null ? 'files.create' : 'files.write', {
          'tree': root,
          'uri': row?['uri'] ?? path,
          'name': name,
          'content': text,
          'version': version,
        });
        await load();
      } else {
        final t = await widget.api.action('files.write', {
          'grant_id': root,
          'path': name,
          'content': text,
        }, version: version);
        await Future<void>.delayed(const Duration(milliseconds: 150));
        if (mounted) await showTask(context, widget.api, t['task_id']);
      }
    } catch (e) {
      if (mounted) toast(context, e.toString());
    }
  }

  Future<void> operate(String operation, dynamic row) async {
    try {
      String? destination;
      if (['copy', 'move', 'rename'].contains(operation)) {
        destination = await askText(
          context,
          local
              ? 'Nombre en la misma carpeta'
              : 'Ruta destino dentro de la carpeta autorizada',
          initial: row['name'],
        );
        if (destination == null || destination.isEmpty) return;
      }
      if (!mounted) return;
      if (!await confirm(
        context,
        '${{'copy': 'Copiar', 'move': 'Mover', 'rename': 'Renombrar', 'trash': 'Enviar a cuarentena'}[operation]} archivo',
        'Destino: ${local ? 'Este teléfono' : 'Servidor'}\n${row['name']}${destination == null ? '' : ' → $destination'}',
      )) {
        return;
      }
      if (local) {
        await LocalDevice.call('files.$operation', {
          'tree': root,
          'uri': row['uri'],
          'parent': path,
          'name': destination,
          'version': row['version'],
        });
        await load();
      } else {
        final t = await widget.api.action(
          'files.${operation == 'rename' ? 'move' : operation}',
          {'grant_id': root, 'path': row['path'], 'destination': ?destination},
          version: row['version'],
        );
        await Future<void>.delayed(const Duration(milliseconds: 150));
        if (mounted) await showTask(context, widget.api, t['task_id']);
      }
    } catch (e) {
      if (mounted) toast(context, e.toString());
    }
  }

  Future<void> recovery() async {
    if (!local) {
      toast(
        context,
        'Los identificadores de copias se guardan en el detalle de la tarea. Podés pedir su restauración en el chat.',
      );
      return;
    }
    try {
      final copies = await LocalDevice.call('files.recovery') as List;
      if (!mounted) return;
      await showDialog<void>(
        context: context,
        builder: (ctx) => AlertDialog(
          title: const Text('Copias recuperables'),
          content: SizedBox(
            width: 500,
            child: ListView(
              shrinkWrap: true,
              children: [
                for (final r in copies)
                  ListTile(
                    title: Text(r['name']),
                    subtitle: Text(r['created'].toString()),
                    onTap: () async {
                      Navigator.pop(ctx);
                      try {
                        await LocalDevice.call('files.restore', {
                          'id': r['id'],
                        });
                        await load();
                      } catch (e) {
                        if (mounted) toast(context, e.toString());
                      }
                    },
                  ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(ctx),
              child: const Text('Cerrar'),
            ),
          ],
        ),
      );
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
    title: 'Archivos',
    subtitle: local
        ? 'Este teléfono · carpetas concedidas por Android'
        : 'Servidor · carpetas autorizadas',
    actions: [
      if (Platform.isAndroid)
        FilterChip(
          label: const Text('Este teléfono'),
          selected: local,
          onSelected: (v) {
            setState(() => local = v);
            loadGrants();
          },
        ),
      if (local)
        OutlinedButton(
          onPressed: () async {
            try {
              await LocalDevice.call('files.chooseTree');
              await loadGrants();
            } catch (e) {
              if (context.mounted) toast(context, e.toString());
            }
          },
          child: const Text('Conceder carpeta'),
        ),
      FilledButton.icon(
        onPressed: root == null ? null : () => edit(),
        icon: const Icon(Icons.note_add_outlined),
        label: const Text('Nuevo archivo'),
      ),
    ],
    child: Column(
      children: [
        if (grants.isNotEmpty)
          DropdownButtonFormField<String>(
            initialValue: root,
            decoration: const InputDecoration(labelText: 'Carpeta autorizada'),
            items: [
              for (final g in grants)
                DropdownMenuItem(
                  value: g[local ? 'uri' : 'id'] as String,
                  child: SizedBox(
                    width: 240,
                    child: Text(
                      '${g[local ? 'name' : 'resource']}',
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ),
            ],
            onChanged: (v) {
              setState(() {
                root = v;
                path = local ? v! : '.';
              });
              load();
            },
          ),
        const SizedBox(height: 12),
        Row(
          children: [
            IconButton(
              onPressed: () {
                setState(() => path = local ? root! : '.');
                load();
              },
              tooltip: 'Raíz',
              icon: const Icon(Icons.home_outlined),
            ),
            Expanded(
              child: Text(path, maxLines: 1, overflow: TextOverflow.ellipsis),
            ),
            IconButton(
              onPressed: load,
              tooltip: 'Actualizar',
              icon: const Icon(Icons.refresh),
            ),
            IconButton(
              onPressed: recovery,
              tooltip: 'Copias recuperables',
              icon: const Icon(Icons.restore),
            ),
          ],
        ),
        TextField(
          controller: search,
          onSubmitted: (_) => searchFiles(),
          decoration: InputDecoration(
            hintText: local
                ? 'Filtrar esta carpeta'
                : 'Buscar en la carpeta autorizada',
            suffixIcon: IconButton(
              onPressed: searchFiles,
              tooltip: 'Buscar',
              icon: const Icon(Icons.search),
            ),
          ),
        ),
        const SizedBox(height: 12),
        if (error != null)
          Padding(
            padding: const EdgeInsets.all(12),
            child: Text(
              error!,
              style: const TextStyle(color: Colors.orangeAccent),
            ),
          ),
        Expanded(
          child: rows.isEmpty
              ? const Center(
                  child: Text(
                    'Seleccioná una carpeta autorizada para ver sus archivos.',
                  ),
                )
              : ListView(
                  children: [
                    for (final r in rows)
                      Card(
                        child: ListTile(
                          leading: Icon(
                            r['directory'] == true
                                ? Icons.folder_outlined
                                : Icons.description_outlined,
                            color: cyan,
                          ),
                          title: Text(r['name']),
                          subtitle: Text('${r['size'] ?? 0} bytes'),
                          onTap: () {
                            if (r['directory'] == true) {
                              setState(() => path = r[local ? 'uri' : 'path']);
                              load();
                            } else {
                              edit(r);
                            }
                          },
                          trailing: r['directory'] == true
                              ? const Icon(Icons.chevron_right)
                              : PopupMenuButton<String>(
                                  tooltip: 'Operaciones de archivo',
                                  onSelected: (op) => operate(op, r),
                                  itemBuilder: (_) => [
                                    const PopupMenuItem(
                                      value: 'copy',
                                      child: Text('Copiar'),
                                    ),
                                    const PopupMenuItem(
                                      value: 'move',
                                      child: Text('Mover'),
                                    ),
                                    const PopupMenuItem(
                                      value: 'rename',
                                      child: Text('Renombrar'),
                                    ),
                                    const PopupMenuItem(
                                      value: 'trash',
                                      child: Text('Enviar a cuarentena'),
                                    ),
                                  ],
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
