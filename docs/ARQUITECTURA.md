# Arquitectura y límites

## Recorrido de una orden

Flutter envía una intención a FastAPI con una sesión de dispositivo. El backend registra una tarea SQLite antes de inferir. El adaptador Responses API consume `gpt-6-astra` mediante HTTPS y streaming. Las funciones publicadas tienen esquemas cerrados: no existe terminal libre ni herramienta que conceda permisos. El planificador solicita; la puerta determinista valida el destino, los argumentos y los permisos. La app muestra la operación exacta antes de aprobarla.

Las aprobaciones son de un solo uso, vencen en cinco minutos y contienen un digest de tarea, herramienta, argumentos, dispositivo y versión del recurso. Cambiar cualquiera de ellos invalida la aprobación. Las herramientas vuelven a comprobar el permiso justo antes de actuar. Cada efecto tiene un paso persistido antes y después de ejecutarse. Un reinicio marca el trabajo interrumpido como incierto; no lo repite.

El agente continúa con las observaciones reales hasta completar la tarea, requerir confirmación o alcanzar límites. El botón Detener todo cancela el despacho de pasos nuevos. Una escritura ya iniciada en un hilo del sistema termina manteniendo el bloqueo del escritor; el resultado se informa como incierto si no pudo persistirse. No se promete deshacer una instalación o una interacción ya despachada.

## Dispositivos

Sesión administradora local: token aleatorio de 48 bytes en el directorio privado de datos. Dispositivos: código aleatorio de un solo uso, tres minutos de vigencia, límites de intentos, token almacenado como hash en el servidor y sesión de 24 horas. No hay renovación automática silenciosa. En Flutter, las sesiones se guardan mediante almacenamiento protegido del sistema.

El transporte remoto utiliza TLS. La app rechaza HTTP remoto y URLs con credenciales. El backend solo escucha fuera de loopback al activar explícitamente el modo remoto y TLS o un proxy TLS. Las comprobaciones de certificado no se desactivan.

La cola remota registra `request_id`, `task_id`, `device_id`, argumentos, esquema, vencimiento y clave de deduplicación. Solo el dispositivo destino puede retirar y responder. El retiro es único; una desconexión posterior produce incertidumbre, no reenvío automático. Android debe tener la app abierta y recepción activada. Presenta una confirmación local, valida su SAF y guarda el estado antes de actuar. Windows remoto se atiende a través del backend que se ejecuta en esa PC. La coordinación de múltiples backends Windows y la recepción Android en segundo plano requieren trabajo adicional.

## Matriz de permisos

| Operación | Puerta | Alcance | Confirmación |
|---|---|---|---|
| Crear/revocar carpetas y sitios del servidor | Sesión administradora | Recurso exacto | Acción explícita de la interfaz |
| Leer/buscar archivos del servidor | Permiso activo | Carpeta canónica, sin enlaces | Permiso de lectura previo |
| Crear/editar/copiar/mover/cuarentena | Permiso activo + aprobación | Rutas relativas, hash previo si existe | Tarea y argumentos exactos |
| Archivo Android | SAF persistido | URI perteneciente al árbol elegido | Diálogo nativo al modificar |
| Tarea remota Android | Sesión destino + SAF local | Catálogo nativo acotado | Cada solicitud en el teléfono |
| Chrome | Permiso de sitio/acción + aprobación | Perfil aislado y página identificada | Cada interacción |
| winget / UI Automation | Windows interactivo + aprobación | Argumentos estructurados, sin shell | Tarea exacta; UAC sigue siendo del SO |
| Memoria manual | Sesión autenticada | Base local o compartida elegida | Acción explícita de usuario |
| Memoria solicitada por modelo | Aprobación | Registro concreto | Antes de guardar u olvidar |

No se solicita `MANAGE_EXTERNAL_STORAGE`, root ni AccessibilityService. Las carpetas privadas de otras apps Android no son accesibles. No hay elevación permanente del backend Windows.

## Persistencia

SQLite WAL, transacciones y migración inicial. Tablas: `devices`, `pairings`, `memories`, `conversations`, `messages`, `grants`, `tasks`, `steps`, `approvals`, `events`, `usage`, `reminders`, `integrations`, `sync_revisions`, `trash`, `remote_requests` y `migrations`. Tareas y pasos usan identificadores UUID; `(owner,idempotency_key)` y `(task_id,position)` son únicos. Las memorias usan revisión optimista y tombstones. La sincronización completa Android/servidor no está activada automáticamente.

Android mantiene otra SQLite para memoria, recuperación y deduplicación nativa. Las memorias locales y las del servidor se muestran separadas. Los secretos no se sincronizan y los permisos de una máquina no conceden permisos en otra.

Las copias del servidor se crean con `sqlite3.backup` y se cifran con Fernet y una clave derivada mediante scrypt. La restauración verifica integridad, invalida aprobaciones y revoca dispositivos, y se hace en un directorio nuevo. Las claves de proveedores están fuera de la base. Una copia antigua puede recuperar memorias eliminadas. El historial conversacional y el registro de tareas tienen retención separada del panel de memoria.

## Archivos y navegador

Límite actual: 10 MiB por archivo y 500 entradas por listado; búsqueda de hasta 10.000 entradas/200 resultados. Edición UTF-8 y validación JSON/CSV. Extracción PDF y DOCX con ubicaciones, límites y marca de resultado parcial. Las imágenes y documentos con macros no se ejecutan. No hay OCR ni editor binario de Office.

En el backend, se usan temporales, sincronización de contenido, copia previa, hash y publicación exclusiva para archivos nuevos. Rechazo de rutas absolutas, `..` y enlaces. Una aplicación externa que cambie enlaces/directorios durante la llamada del sistema conserva un riesgo residual de carrera; no se presenta como aislamiento frente a un usuario local hostil. Las operaciones sobre carpetas completas o archivos grandes todavía no están soportadas.

SAF depende del proveedor Android: una escritura puede no ser atómica. Se crea una copia recuperable antes de editar y se verifica el resultado. Cambiar nombre/mover en Android actualmente funciona dentro de la carpeta mostrada; transferencias entre proveedores necesitan una implementación adicional.

MCP 1.10.1 se inicia como proceso independiente por stdio, negocia el protocolo, descubre el catálogo y valida argumentos. No depende de que Codex esté abierto. Se desactiva JavaScript arbitrario, telemetría y consulta CrUX. Los archivos de salida arbitrarios y cargas/descargas aún no están expuestos. Cada acción que opera una página verifica su origen actual. Los redirects y subrecursos de navegación no tienen un filtro de red completo por sitio en esta versión; por eso no se afirma aislamiento de navegación a nivel de red ni compatibilidad total con el catálogo.

## Presupuestos y modelos

El backend registra tokens reales cuando el proveedor los entrega y marca como estimada una reserva si la conexión se interrumpe. Hay límites por tarea, día y pasos. Las reservas de tokens son estimaciones conservadoras, no una promesa de costo monetario máximo; la inferencia/voz puede cobrarse aunque se cancele. Los diagnósticos y servicios de audio requieren integrar todavía un presupuesto común. Configurá también límites de gasto en la cuenta del proveedor.

No se verificó una llamada real a Astra por falta de credencial de la aplicación. La documentación pública confirma el identificador; la cuenta debe pasar la comprobación real desde Ajustes. Gemini es una alternativa explícita con listado paginado de modelos; su adaptador actual admite chat, sin paridad de herramientas ni streaming.
