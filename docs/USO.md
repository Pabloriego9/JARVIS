# Manual de la versión 0.1.0

## Primer inicio

1. Iniciar el backend. En Windows empaquetado, usar el acceso directo JARVIS. En desarrollo, `uv run jarvis serve`.
2. Windows personal: `uv run jarvis configure-openai` guarda la credencial en Windows Credential Manager. En un servidor privado, configurar `JARVIS_OPENAI_API_KEY` mediante su gestor de secretos. Reiniciar el backend después de cambiarla.
3. En la app, abrir Ajustes, conectar al servidor y pulsar «Probar conexión real con el modelo». Para Android remoto se usa HTTPS y un código generado con `jarvis pair`.
4. Probar voz, conceder una carpeta de prueba y verificar una operación antes de utilizar documentos propios.

## Conversación y tareas

Escribir en Inicio. El encabezado indica conexión y modelo. Las respuestas se muestran por fragmentos mientras llegan. Las tarjetas de Tareas muestran estado, destino, pasos y evidencias. Las operaciones sensibles esperan confirmación. Abrir la tarea, leer los argumentos y confirmar exactamente esa operación. Un cambio en el archivo invalida la vista previa.

«Detener todo» o Ctrl+Escape cancela nuevos pasos en el backend. La pantalla Voz también permite interrumpir reproducción, grabación y la tarea de voz. Revisar las acciones ya despachadas: no se promete deshacer una instalación, envío o escritura en curso. Un estado incierto requiere observar el recurso; no reintentar ciegamente.

## Memoria

Memoria permite agregar, buscar, corregir y olvidar recuerdos. Android puede seleccionar «Este teléfono» para memoria local SQLite sin conexión o «Servidor» para la base compartida. El servidor detecta revisiones concurrentes y rechaza sobrescribir una versión distinta.

Olvidar en Memoria quita ese registro del conjunto activo y genera un tombstone. No borra automáticamente mensajes anteriores que contengan el mismo texto ni copias cifradas antiguas. El borrado de conversaciones está disponible en la API; su panel dedicado y una política completa de retención permanecen pendientes. La sincronización automática entre memoria local Android y servidor también está pendiente.

## Archivos

Servidor: primero autorizar la carpeta en Permisos. Android: pulsar Conceder carpeta y elegirla con el selector del sistema. Navegar por carpetas; abrir archivos de texto para editar; el menú ofrece copiar, mover, renombrar o enviar a cuarentena. Las ediciones locales Android requieren otro diálogo nativo. El máximo actual es 10 MiB por archivo.

La operación del servidor se registra como tarea; revisarla y actualizar el explorador al terminar. El detalle contiene el hash verificado y, cuando corresponde, `backup_id` o `trash_id`. El chat o la API `files.restore` permiten restaurar una copia del servidor. Android muestra sus copias en el botón de recuperación. Las colisiones conservan el archivo existente.

## Voz

Pulsar para hablar, terminar la grabación, corregir la transcripción y enviar. Se usan servicios de voz separados de Astra. La grabación temporal se borra después de transcribir. La salida es voz sintética de identidad propia, no una imitación autorizada de un actor. Selección avanzada de micrófono, Bluetooth, palabra de activación y escucha en segundo plano están pendientes de implementación/pruebas físicas.

## Programas y navegador

Windows usa identificadores exactos de winget; las licencias y UAC se resuelven con mecanismos del sistema. Android abre una ficha de tienda o entrega un APK al instalador. Abrir el instalador no significa que la instalación se completó: verificar el resultado en Android.

El navegador usa un host MCP propio, Chrome y un perfil temporal separado. Activar `JARVIS_MCP_ENABLED=true` en el backend local. Autorizar el sitio desde Navegador; cada acción requiere confirmación. El chat puede descubrir el catálogo y operar páginas identificadas. Carga/descarga de archivos y control de Chrome local Android no están disponibles.

## Recordatorios y monitoreo

Monitoreo muestra métricas reales disponibles. El servidor registra recordatorios con fecha, zona y recurrencia; los eventos se muestran cuando la app está conectada y abierta. No se promete notificación exacta en segundo plano. Las reglas automáticas y notificaciones de sistema requieren trabajo adicional.

## Diagnóstico

Falta de credencial: las funciones locales siguen disponibles. Error de cuota: revisar el proveedor y el presupuesto. Permiso revocado: volver a conceder solo el recurso necesario. Archivo cambiado: releer y revisar. Dispositivo desconectado: no repetir operaciones con resultado incierto. MCP desactivado: revisar Node, Chrome, `npm ci` y la variable de habilitación.

Las credenciales nunca se piden en el chat. Exportar el diagnóstico desde `/v1/diagnostics` devuelve versiones y estados, sin valores de claves. La base SQLite y los resultados de tareas sí pueden contener datos personales: proteger sus backups.
