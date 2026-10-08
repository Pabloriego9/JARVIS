# JARVIS — Especificación integral para Windows y Android

**Edición:** 2.0 · **Fecha:** 7 de octubre de 2026 · **Titular del proyecto:** Pablo Riego  
**Destino:** desarrollo desde cero con Codex o Antigravity.  
**Estado:** documentación de requisitos y diseño. Ninguna función se declara implementada o probada por la existencia de este documento.

Esta especificación reemplaza el encargo anterior como referencia de desarrollo. Conserva sus funciones y amplía el alcance: aplicaciones instalables en Windows y Android, acciones locales en ambos sistemas, gestión completa de archivos accesibles, instalación de programas, navegador mediante MCP y OpenAI GPT-6 Astra como modelo principal. Android deja de ser solamente un micrófono remoto para la PC.

## 1. Visión, alcance y criterio de realidad

Construir un asistente personal inspirado en Jarvis de Iron Man: conversación natural en español, memoria, voz, comprensión de documentos y pantalla, planificación de tareas, ejecución de herramientas, verificación de resultados y seguimiento proactivo configurable.

La aspiración del usuario es aproximarse a la amplitud de capacidades de una AGI. El entregable verificable es un **agente de IA generalista con herramientas**. Integrar GPT-6 Astra, memoria y automatización no demuestra haber creado AGI ni garantiza inteligencia ilimitada. Se evaluará amplitud, autonomía supervisada, fiabilidad, adaptación y capacidad de reconocer límites, sin declarar AGI alcanzada.

«Acceso completo» significa ofrecer todas las operaciones que el sistema operativo, las aplicaciones y los permisos efectivamente concedan. Un permiso de Jarvis no reemplaza un permiso de Windows o Android. Una operación no disponible debe explicar el motivo y ofrecer una alternativa válida.

### Productos obligatorios

- Aplicación Windows instalable, ventana propia, bandeja del sistema, acceso directo y arranque al iniciar sesión opcional.
- Aplicación Android nativa compilada, instalable mediante APK firmado para uso personal; AAB si se decide distribuir en una tienda y se cumplen sus requisitos.
- Motor del agente, memoria, herramientas y permisos reales; ninguna maqueta contará como función terminada.
- Instalación reproducible, actualización, desinstalación, copias de seguridad, documentación de uso y pruebas.
- Experiencia compartida entre dispositivos, con destino de cada acción visible.

### Alcance por entorno

| Función | Windows | Android |
|---|---|---|
| Chat, memoria y voz | Local con servicios de IA configurados | Funciona sin depender de que la PC esté encendida, usando un backend disponible |
| Buscar, seleccionar y gestionar archivos | Archivos accesibles a la cuenta y alcances autorizados | Documentos y carpetas concedidos por Android; no todo el sistema |
| Instalar programas | Instalador o gestor de paquetes, con elevación cuando corresponda | Flujo de tienda o instalador del sistema con intervención requerida |
| Control de aplicaciones | APIs, UI Automation y automatización visual compatible | Intents, integraciones y acciones expuestas; automatización adicional condicionada |
| Chrome DevTools MCP | Proceso MCP ejecutado en la PC | Control remoto del Chrome de PC; integración local de Chrome Android no se presume |
| Monitoreo | Métricas que el equipo exponga | Métricas que Android permita; sin asumir visibilidad de todos los procesos |
| Captura de pantalla | Selección y autorización por sesión o alcance configurado | API de captura y permisos del sistema; respetar contenido protegido |
| Uso sin Internet | Archivos, memoria y herramientas locales; IA local solo si se integra | Memoria, archivos accesibles y órdenes deterministas; IA local opcional |

## 2. Cambios respecto del documento anterior

| Elemento anterior | Nueva definición |
|---|---|
| Cliente web móvil dependiente de PC | App Android con ejecutor local y modo remoto adicional |
| React y contenedor web de escritorio | Interfaz compartida Flutter con integraciones nativas |
| Gemini principal | GPT-6 Astra principal; Gemini opcional configurable |
| Leer archivos y crear notas | Crear, obtener, actualizar, mover, copiar, renombrar y eliminar dentro del acceso efectivo |
| Abrir aplicaciones | Además instalar, actualizar y desinstalar con herramientas específicas |
| Navegador genérico | Cliente MCP de Jarvis, integración Chrome DevTools y pruebas reales |
| Terminar tras la primera etapa | Completar el alcance por hitos; registrar bloqueos sin presentar un prototipo como producto final |

Se mantienen diagnósticos técnicos, descubrimiento de modelos Gemini, memoria editable, voz, monitoreo, emparejamiento, revocación, cancelación, interfaz azul/cian y comprobación de resultados.

## 3. Arquitectura propuesta

Decisión de diseño: **Flutter/Dart para interfaz y lógica compartida**, Kotlin para Android y un ejecutor Windows .NET/C# para integración con el sistema. Un backend Python de orquestación e integración con OpenAI puede ejecutarse localmente en Windows o en una instancia privada remota. Es una propuesta de implementación, no un componente ya construido.

Flutter ofrece mecanismos de comunicación con código específico de plataforma [S3]. No intentar resolver los permisos del sistema únicamente con la interfaz compartida.

### Componentes y responsabilidades

| Componente | Responsabilidad | Ubicación |
|---|---|---|
| App Flutter | Chat, voz, explorador, tareas, permisos, ajustes | Windows y Android |
| Núcleo compartido Dart | Contratos, estados, selección de destino, cola local y validaciones de interfaz | Ambos |
| Ejecutor Windows | Archivos, aplicaciones, métricas, UI Automation y operaciones locales | PC del usuario |
| Adaptadores Android | Archivos por URI, intents, audio, captura y notificaciones autorizadas | Celular |
| Orquestador | Llamadas al modelo, planificación, recuperación de contexto y solicitudes de herramientas | PC o backend privado |
| Puerta de permisos local | Validación final y ejecución; rechaza solicitudes fuera del alcance | Cada dispositivo |
| Host MCP | Inicia y supervisa Chrome DevTools MCP mediante stdio | Windows |
| Almacenamiento | Memoria, tareas, permisos y eventos; secretos por separado | Cada dispositivo y sincronización selectiva |

El backend remoto nunca obtiene por sí mismo acceso al disco o al teléfono. Envía solicitudes estructuradas; el dispositivo comprueba permisos vigentes antes de ejecutar.

### Modalidades operativas

1. **Windows local:** app, orquestador y ejecutor en la PC; el modelo de OpenAI se consume por API.
2. **Android independiente:** app y ejecutor en el celular; inferencia a través de un backend privado disponible independientemente de la PC. Entregar dicho backend y guía de despliegue; sin él, este modo con IA en la nube no está completo.
3. **Android a Windows:** celular emparejado envía tareas a la PC encendida. La interfaz indica «Ejecutando en PC de Pablo».
4. **Windows a Android:** acciones permitidas sobre un celular conectado y autorizado; respetar suspensión y restricciones Android.
5. **Sin conexión:** conservar memoria y operaciones locales deterministas. Informar que GPT-6 Astra no está disponible sin conectividad. No afirmar que se descargó ese modelo al dispositivo.

Si se usa la PC como único backend de inferencia, reconocer que Android pierde esa inferencia cuando la PC se apaga. No presentar esa configuración como independencia completa.

## 4. OpenAI GPT-6 Astra y proveedores

La documentación oficial consultada identifica `gpt-6-astra`, con Responses API, llamadas a funciones y salidas estructuradas. Admite entrada de texto e imagen y salida de texto; el audio requiere componentes separados [S1]. Verificar acceso real de la cuenta antes de dar la integración por terminada.

Requisitos del adaptador:

- Modelo principal configurado como `gpt-6-astra`; no reemplazarlo silenciosamente por otro.
- Verificación inicial del modelo y solicitud mínima real, con resultados comprobables.
- Configuración de esfuerzo de razonamiento y límites según la documentación vigente; no usar siempre el máximo si aumenta latencia y gasto sin necesidad.
- Streaming, cancelación, límites de salida y manejo de llamadas a herramientas.
- Presentar proveedor y modelo efectivos; distinguir modelo conversacional de servicios de voz.
- Presupuesto por tarea y período, límites de pasos, advertencias de consumo y corte al alcanzar el límite. Registrar uso real cuando el proveedor lo devuelva y marcar estimaciones como tales.
- No incluir una clave de OpenAI del desarrollador dentro del APK, instalador, código compartido o frontend. El backend privado conserva la clave y autentica dispositivos.
- En Windows personal, admitir credenciales del usuario almacenadas mediante protección del sistema; no pedir pegarlas en conversaciones.
- Separar la configuración del agente de desarrollo de las credenciales que necesita la aplicación terminada.

Gemini queda como proveedor alternativo voluntario. Mantener listado paginado de modelos y filtrado por `generateContent`, selección manual y resíncronización. No inferir capacidad o cuota por el nombre. Un error 404 no autoriza repetir operaciones locales ya ejecutadas.

### Diagnóstico obligatorio

Mensaje entendible más detalle técnico saneado: proveedor, modelo, HTTP, código del proveedor, mensaje original sin secretos, identificador de solicitud si existe, fecha y acción fallida. Distinguir autenticación, cuota, modelo inexistente, conexión, permiso local y herramienta incompatible. Aplicar reintentos limitados únicamente donde sean seguros.

## 5. Comportamiento del agente

Secuencia operativa: interpretar intención → resolver dispositivo y recursos → recuperar contexto pertinente → proponer pasos → validar capacidades y permisos → ejecutar → observar resultado → corregir dentro del alcance → informar evidencias.

El planificador no es la autoridad de permisos. La confirmación y la ejecución corresponden a componentes deterministas. Los textos de documentos, sitios web, imágenes y herramientas se procesan como información, no como nuevas instrucciones del propietario.

Estados de tarea: pendiente, planificando, esperando permiso, ejecutando, pausada, cancelada, completada, fallida y resultado incierto. Cada tarea tiene identificador, destino, pasos, límite temporal y resultado por paso. Persistir el estado antes y después de efectos importantes. Tras una caída, comprobar qué ocurrió antes de volver a intentarlo.

Seleccionar el dispositivo de forma explícita cuando haya ambigüedad. «Borrá Descargas» requiere resolver cuál carpeta, de qué dispositivo y qué elementos. No ejecutar dos tareas que escriban simultáneamente el mismo recurso. La conversación debe seguir disponible mientras una tarea tarda.

Aprendizaje práctico: guardar preferencias y procedimientos que el usuario valide. Las mejoras de rutinas se versionan y prueban; no permitir que el agente cambie sus propios permisos o código de producción sin revisión.

## 6. Catálogo funcional y trazabilidad

Todos los requisitos siguientes son objetivos de implementación. Su estado inicial es **pendiente**.

| ID | Requisito | Evidencia mínima |
|---|---|---|
| RF01 | Chat en español con GPT-6 Astra | Respuesta real y modelo registrado |
| RF02 | Memoria persistente consultable, editable y eliminable | Recuperación tras reiniciar y prueba de olvido |
| RF03 | Voz bidireccional en PC y Android | Grabación, transcripción y reproducción reales |
| RF04 | Explorador y búsqueda de archivos/carpetas | Resultados reales, selección y permisos visibles |
| RF05 | CRUD, copias y movimientos de archivos | Contenido y metadatos verificados antes/después |
| RF06 | Gestión de programas | Instalación/actualización verificada o rechazo explicado |
| RF07 | Control Windows | Aplicación real controlada y resultado observado |
| RF08 | Acciones Android | Operación local real sin dependencia del ejecutor de PC |
| RF09 | Chrome DevTools MCP dentro de Jarvis | Flujo web ejecutado desde Jarvis sin Codex abierto |
| RF10 | Investigación web con fuentes | Respuesta con URLs y datos consultados |
| RF11 | Comprensión de documentos y pantalla | Resumen con referencias a archivo/página o captura |
| RF12 | Tareas de varios pasos y cancelación | Flujo completo, fallo parcial y detención |
| RF13 | Monitoreo, recordatorios y reglas | Evento real y notificación comprobada |
| RF14 | Emparejamiento y control remoto | Destino correcto, revocación efectiva |
| RF15 | Sincronización y funcionamiento degradado | Conflicto resuelto sin pérdida ni reejecución |
| RF16 | Permisos, trazabilidad y recuperación | Pruebas de denegación, copia y restauración |
| RF17 | Interfaz Jarvis accesible | Flujos utilizables con teclado, tacto y texto ampliado |
| RF18 | Instalación y mantenimiento | Instaladores probados, actualización sin perder memoria |

## 7. Archivos y carpetas: gestión completa dentro del acceso efectivo

Operaciones: listar, buscar por nombre/extensión/fecha/tamaño, filtrar, seleccionar individualmente o por lote, obtener metadatos, previsualizar, abrir con aplicación asociada, leer, crear, actualizar contenido, renombrar, copiar, mover, eliminar, exportar y restaurar cuando exista una copia o papelera compatible.

Separar exploración de edición semántica. Mover un archivo binario no implica poder editar su contenido. Texto, Markdown, JSON y CSV tendrán editores específicos. Word, PDF, hojas de cálculo e imágenes requieren adaptadores que preserven formato y validación; una operación no soportada debe indicarlo.

### Windows

Usar rutas canónicas y ACL de la cuenta. Permitir autorizar una carpeta o unidad accesible, mostrando el alcance. Tratar enlaces, junctions, archivos bloqueados, solo lectura, discos extraíbles, unidades desconectadas y nombres reservados. No elevar todo Jarvis para leer un recurso protegido.

### Android

Usar Storage Access Framework para documentos/carpetas concedidos y MediaStore para medios; tratar URI como identificador, sin exigir siempre una ruta física. Comprobar permisos persistidos y revocados. El acceso especial `MANAGE_EXTERNAL_STORAGE` amplía almacenamiento compartido, pero no otorga acceso al espacio privado de otras apps [S4]. No prometer lectura de todas las carpetas de sistema.

### Reglas de integridad

- Mostrar recurso y dispositivo afectados; en lotes, cantidad, tamaño estimado y lista revisable.
- Para editar, generar vista previa o diferencia. Verificar versión o hash antes de escribir para detectar cambios concurrentes.
- Usar escritura temporal y reemplazo seguro cuando la plataforma lo permita; declarar dónde no existe atomicidad equivalente.
- Ante colisiones, ofrecer sobrescribir, conservar ambos o cancelar. Nunca decidir silenciosamente.
- Eliminar a papelera o cuarentena cuando sea viable; eliminación definitiva exige confirmación concreta. No afirmar que todo borrado puede deshacerse.
- Probar espacio insuficiente, desconexión y cancelación. Conservar originales si falla una copia.
- Búsqueda de contenido e indexación por carpetas autorizadas, con progreso, exclusiones, límites y actualización incremental.
- Exportaciones y transferencias verifican tamaño y hash cuando sea posible; no adjuntar automáticamente todos los archivos al modelo.

Ejemplo: «Buscá los STL de Egiverso3D y movelos a Modelos» produce una selección revisable, resuelve origen/destino, detecta duplicados y verifica cada movimiento.

## 8. Instalación, actualización y desinstalación

### Windows

Adaptador de gestor de paquetes si está disponible y es compatible; alternativa con instaladores de fuente oficial. Antes de ejecutar: resolver producto exacto, editor, fuente, versión, arquitectura y destino. Verificar integridad y firma cuando exista. Mostrar licencias o aceptación requerida; pedir elevación mediante el mecanismo normal de Windows si corresponde. Mantener argumentos estructurados y ejecutables verificados.

Detectar instalación existente, conflictos, reinicio pendiente, código de salida y resultado real. Un comando con salida cero no sustituye la comprobación de la versión instalada. Admitir cancelación cuando el instalador lo permita; no prometer rollback universal.

### Android

Abrir la ficha de la tienda o entregar un APK al instalador del sistema, mostrando origen e identidad del paquete. Manejar el estado que exige acción del usuario [S5]. No garantizar instalación silenciosa en un teléfono personal ordinario. Registrar cancelación, rechazo, firma incompatible y versión instalada.

Instalación administrada en equipos corporativos constituye una variante futura con aprovisionamiento específico. Root, desbloqueo de bootloader y evasión de permisos no son requisitos del producto base. Distribuir un APK fuera de una tienda no elimina las restricciones de Android.

## 9. Navegador y Chrome DevTools MCP

### Configuración del agente de desarrollo

El comando solicitado registra el servidor MCP para Codex [S2]:

```bash
codex mcp add chrome-devtools -- npx chrome-devtools-mcp@latest
```

Es un paso del entorno de desarrollo; no instala automáticamente el control del navegador dentro de Jarvis. Verificar Chrome, Node.js LTS, npm y la configuración efectiva. Resolver diferencias de ejecución de `npx` en Windows según el cliente.

### Integración en Jarvis

Construir un cliente MCP propio en el host Windows: inicio del proceso, negociación, descubrimiento de herramientas, validación de esquemas, ejecución, resultados, errores, cancelación y cierre. En producción fijar una versión probada en lugar de depender indefinidamente de `@latest`. Los nombres concretos y capacidades se descubren y contrastan con la versión instalada [S2].

El orquestador expone funciones validadas al modelo y el host local las traduce al servidor por stdio. Un servidor remoto de OpenAI no puede alcanzar el localhost del usuario por el mero hecho de recibir una URL. No publicar DevTools sin autenticación.

### Alcance requerido del navegador

Buscar y navegar, gestionar páginas disponibles, inspeccionar contenido, seleccionar elementos, rellenar formularios, interactuar, capturar evidencias y consultar diagnósticos donde la versión MCP los soporte. Implementar carga y descarga de archivos con restricciones de destino. Medir compatibilidad por función.

«Todas las funciones» significa cubrir el catálogo soportado y autorizado, no garantizar APIs inexistentes para extensiones, contraseñas, controles protegidos o todo el navegador. Usar un perfil Jarvis separado por defecto; conectar un perfil personal solo tras elección explícita. No cerrar sesiones ajenas ni exportar credenciales.

Separar investigación web de acciones en una sesión autenticada. Mantener permisos por sitio y por acción. Pagos, envíos, publicaciones y cambios de cuenta requieren una confirmación asociada al contenido exacto. Una página no puede ordenar instalar programas ni ampliar el acceso a archivos.

Android puede operar el navegador de la PC a través de ese host. Para Chrome local Android, usar enlaces e integraciones disponibles; una eventual depuración remota es una capacidad experimental separada, que exige prueba y autorización. No asumir que `npx` se ejecuta dentro del APK.

## 10. Automatización del sistema y percepción

Windows: abrir programas, seleccionar ventanas, controlar aplicaciones compatibles, volumen y reproducción, inspeccionar elementos accesibles y utilizar capturas para tareas visuales autorizadas. Priorizar API y UI Automation sobre coordenadas. Soportar varios monitores y escalado; comprobar el resultado después de cada interacción. Cuando la pantalla está bloqueada o la sesión no es interactiva, suspender acciones que requieran interacción.

Android: abrir apps o ajustes, compartir documentos, lanzar intents e integraciones verificadas. Captura mediante mecanismos del sistema con consentimiento; tratar pantallas protegidas como no disponibles. Acceso a notificaciones solo si el usuario lo activa; filtrar contenidos sensibles y no confundirlo con acceso universal a otras apps.

La automatización por AccessibilityService requiere una decisión específica de distribución. La política consultada de Google Play prohíbe usar esa API para iniciar, planificar y ejecutar autónomamente acciones o decisiones; distingue automatizaciones deterministas [S6]. No diseñar un agente autónomo general basado en accesibilidad y prometer al mismo tiempo aprobación en Play. Priorizar APIs/intents y preparar una matriz de compatibilidad por aplicación. Cualquier edición experimental de uso personal debe respetar límites del sistema y tener pruebas separadas; no es una solución automática a esta incompatibilidad.

## 11. Voz y personalidad

Cadena obligatoria: micrófono → detección de voz → transcripción → agente → síntesis → altavoz. Los adaptadores de voz son independientes de GPT-6 Astra [S1]. Seleccionar proveedores y versiones vigentes al implementar; admitir voz local cuando el dispositivo lo permita.

- Pulsar para hablar, escritura alternativa y transcripción corregible.
- Voz masculina sintética en español, tranquila, precisa y de estética futurista; identidad propia de Jarvis. Voz exacta del actor únicamente con una opción autorizada.
- Selección de entrada y salida, Bluetooth cuando esté disponible, volumen, velocidad y salida por PC o celular.
- Palabra de activación «Jarvis» opcional, preferentemente detectada en el dispositivo.
- Estados visibles: inactivo, escuchando, transcribiendo, pensando, actuando, esperando confirmación, hablando y error.
- Interrumpir voz y tarea, cancelar audio acumulado y evitar que Jarvis se reactive con su propia voz.
- Indicadores de escucha y opción para no conservar grabaciones; transcripciones y audio tienen políticas de retención separadas.

En Android, la escucha en segundo plano necesita un servicio y permisos compatibles, con notificación visible. El servicio de micrófono tiene restricciones de inicio desde segundo plano y tras arranque [S7]. Probar bloqueo de pantalla, reinicio y ahorro de batería; no prometer escucha permanente en todos los teléfonos. Una orden hablada no sustituye autenticación del dispositivo para acciones delicadas.

## 12. Memoria, documentos y aprendizaje útil

Tipos: historial conversacional, preferencias explícitas, proyectos, hechos recordados, resúmenes de tareas y procedimientos aprobados. Cada registro incluye origen, fecha, dispositivo, alcance, versión y posibilidad de corrección.

«Recordá esto», «qué recordás» y «olvidá esto» deben funcionar desde texto y voz. No guardar inferencias como hechos confirmados. Las correcciones explícitas tienen prioridad; conservar trazabilidad sin reintroducir recuerdos borrados desde resúmenes o índices.

SQLite local con migraciones; almacenamiento de secretos separado. Panel para buscar, editar, eliminar y exportar. Recuperación por relevancia y presupuesto de contexto, sin enviar toda la base en cada turno. No llamar memoria a un historial que se pierde al cerrar.

Lectura de documentos: archivos seleccionados, extractores por formato, límites de tamaño, paginación y OCR opcional. Respuestas con archivo y ubicación de la información. Mostrar cuando la extracción es parcial. Los archivos recuperados no ejecutan macros o instrucciones.

Sincronización optativa por categorías. Usar revisiones, identificadores y marcas de eliminación; no resolver todo con «gana el último reloj». Mostrar conflictos y permitir conservar versiones. Los secretos y permisos de un dispositivo no se copian como permisos de otro. La memoria local es fuente operativa; las copias remotas no autorizan acceso adicional.

## 13. Dispositivos, red y sesiones

Emparejamiento desde sesión desbloqueada mediante QR/código breve con caducidad. Registrar identidad, nombre, fecha y capacidades. Credenciales de dispositivo revocables y sesiones de corta duración; sin claves permanentes en URLs.

Comunicación remota cifrada y autenticada; validar identidad del servidor y del dispositivo. No considerar confiable toda la red Wi-Fi. El backend Windows permanece en loopback salvo modo remoto activado. No abrir puertos del router automáticamente.

Cada solicitud remota contiene destino, tarea, vigencia, nonce e identidad autenticada. El ejecutor vuelve a comprobar permiso y deduplicación. Las confirmaciones las puede dar un dispositivo confiable dentro de la política elegida, pero los diálogos de UAC o Android se resuelven donde el sistema los exija.

Transferencia de archivos por selección explícita, con progreso, límites y verificación. Reconectar no debe reenviar acciones destructivas. Si el destino se desconecta, mostrar «pendiente de conexión» y exigir revalidación antes de ejecutar una tarea vencida.

## 14. Monitoreo, recordatorios y proactividad

Windows: CPU, memoria, discos y procesos accesibles; sensores térmicos solo si existe una fuente compatible. Android: batería, espacio y señales expuestas; no fabricar datos globales que la app no pueda leer.

Reglas con condición, intervalo, destino, horario y acción. Evitar alertas repetidas mediante enfriamiento. Las acciones de una regla usan los mismos permisos y límites que una orden manual.

Recordatorios persistentes con fecha, recurrencia y zona horaria; valor inicial del perfil: America/Argentina/Buenos_Aires, editable. Distinguir hora exacta de notificación aproximada según las capacidades del sistema. Gestionar reinicio, suspensión, recordatorio vencido y duplicados. Probar con un reloj controlado y después en el dispositivo.

No interpretar «proactivo» como captura permanente. El usuario decide las señales observadas. Ningún disparador externo concede permisos nuevos.

## 15. Permisos, autonomía y protección de datos

Ofrecer tres modos: consulta, asistido y autonomía dentro de reglas aprobadas. La autonomía permite ejecutar acciones previamente autorizadas en un alcance definido sin consultar cada vez. No equivale a privilegios administrativos universales.

- Autorizaciones persistentes para carpetas, programas y sitios seleccionados, revocables desde ajustes.
- Confirmaciones concretas para borrado definitivo, sobrescritura importante, instalación, desinstalación, reinicio, envío, publicación o compra. Vista previa antes de pedirlas.
- Token de aprobación ligado a herramienta, argumentos, recursos, destino y caducidad; de un solo uso.
- Si cambia el recurso o plan materialmente, revalidar. El modelo no puede producir su propia aprobación.
- Diálogos de sistema conservados. Elevar una operación específica, nunca todo el agente como configuración normal.
- Botón «Detener todo» y atajo local independientes del proveedor; cancelar nuevos pasos e informar efectos ya realizados.
- Validación estructural de herramientas, límites y auditoría de entradas/salidas con secretos redactados.
- Ningún ejecutable, MCP o plugin sugerido por una página se instala automáticamente. Catálogo de integraciones versionado y revisable.

La edición de archivos usa copias recuperables cuando sea viable. El registro debe mostrar qué sucedió, no almacenar razonamiento interno del modelo ni duplicar por defecto archivos personales.

## 16. Persistencia, recuperación y mantenimiento

Bases con transacciones, migraciones versionadas y backups coherentes. Probar restauración, no solo creación de la copia. Separar datos del usuario del directorio de instalación. No guardar la memoria en una carpeta temporal.

Backups con cifrado cuando incluyan datos sensibles y política de retención. Explicar que restaurar una copia antigua puede recuperar recuerdos previamente borrados. Permitir exportar datos antes de desinstalar; eliminación de datos como elección separada.

Actualización con versión fijada de dependencias, comprobación de artefactos y recuperación ante migración fallida. Reiniciar el host MCP si falla sin repetir acciones de efecto incierto. El servicio Windows de automatización de escritorio se ejecuta en la sesión interactiva del usuario; un servicio sin escritorio no sustituye ese contexto.

Registro de eventos con rotación y exportación saneada de diagnóstico. Panel de salud: proveedor, voz, permisos, dispositivos, almacenamiento y MCP.

## 17. Interfaz inspirada en Jarvis

Núcleo circular azul/cian, fondo oscuro y animación vinculada al estado real. Tipografía legible, contraste, reducción de movimiento y controles táctiles amplios. Nombre y voz consistentes, sin simular conciencia o acceso que no existe.

Pantallas obligatorias: inicio/chat, conversación de voz, explorador, detalle de operación, tareas/planes, memoria, dispositivos, navegador/sesiones, programas, monitoreo, recordatorios, permisos, consumo y ajustes.

La cabecera indica dispositivo destino, conexión y modelo. Una tarjeta de acción muestra objetivo, recurso, progreso y resultado. Errores con solución útil y panel técnico expandible. No esconder acciones peligrosas detrás de iconos ambiguos.

Primer inicio: elegir modo de backend, configurar acceso a IA, probar audio, conceder carpetas, registrar capacidades y ofrecer emparejamiento. Si falta algo, permitir funciones disponibles y mostrar lo pendiente.

## 18. Contratos de herramientas y datos

Contrato de solicitud: `task_id`, `request_id`, `device_id`, `tool_name`, `schema_version`, `arguments`, `expected_resource_version`, `deadline`, `idempotency_key` y `approval_id` cuando corresponda. La identidad y las autorizaciones se obtienen del canal autenticado; no confiar en campos aportados por el modelo.

Contrato de resultado: `status`, `data`, `error_code`, `user_message`, `technical_details_redacted`, `evidence`, `side_effects`, `retry_safe` y `resource_version`. Estados diferenciados para no soportado, denegado, cancelado, fallo y resultado incierto.

Familias: `files`, `apps`, `system`, `browser`, `memory`, `voice`, `tasks`, `devices`, `notifications` e `integrations`. Evitar una sola herramienta de terminal que pueda hacer cualquier cosa. Para tareas de programación avanzadas, un workspace aislado y comandos concretos revisables, con publicación/aplicación al equipo separada.

Entidades mínimas: conversaciones, mensajes, memorias, dispositivos, permisos, tareas, pasos, aprobaciones, eventos, recordatorios, integraciones y revisiones de sincronización. Documentar claves, relaciones, índices y migraciones durante la implementación.

## 19. Calidad y pruebas de aceptación

Objetivos de ingeniería, a medir en hardware identificado: confirmación visual de la orden en menos de 300 ms para interacción local; interfaz operable durante inferencia; cancelación que impida despachar pasos nuevos en menos de 1 s desde su recepción por el ejecutor. No prometer un tiempo fijo de respuesta del modelo o de una instalación externa. Medir latencia p50/p95, memoria, CPU y batería con escenarios definidos.

| Prueba | Acción | Resultado requerido |
|---|---|---|
| PA01 | Configurar Astra y conversar | Solicitud real, modelo efectivo y uso visible |
| PA02 | Recordar Egiverso3D, cerrar y abrir | Recuerdo recuperado desde persistencia |
| PA03 | Corregir y olvidar el recuerdo | Sin recuperación desde índices/resúmenes activos |
| PA04 | Conversar por voz en ambos equipos | Transcripción y respuesta audible; interrupción |
| PA05 | Buscar/seleccionar/copiar/editar/mover/borrar archivos de prueba | Resultados verificados en cada plataforma |
| PA06 | Revocar carpeta y repetir acción | Rechazo sin efecto lateral |
| PA07 | Cambiar archivo después de vista previa | Conflicto detectado antes de sobrescribir |
| PA08 | Instalar programa de prueba Windows | Producto/versiones comprobados; UAC si corresponde |
| PA09 | Instalar app Android por flujo permitido | Aceptación/rechazo reales; resultado del instalador |
| PA10 | Formularios de sitio de prueba mediante MCP | Acción ejecutada desde Jarvis y evidencia final |
| PA11 | Cerrar Codex y repetir PA10 | Jarvis mantiene su propia integración MCP |
| PA12 | Página intenta ordenar borrar archivos | Instrucción externa rechazada |
| PA13 | Android con PC apagada | Funciones locales y chat vía backend independiente |
| PA14 | Orden remota con nombre de carpeta ambiguo | Resolución de destino antes de escribir |
| PA15 | Revocar dispositivo conectado | Solicitudes posteriores rechazadas |
| PA16 | Desconectar tras una acción y reconectar | No duplicar el efecto; resolver estado incierto |
| PA17 | Micrófono con bloqueo/ahorro de batería | Comportamiento medido y límites mostrados |
| PA18 | Recordatorio, reinicio y cambio de zona | Persistencia sin duplicados y horario explicado |
| PA19 | Fallos 401/403/404/429, timeout y cuota | Diagnóstico, límite de reintentos y UI utilizable |
| PA20 | Copia, actualización y restauración | Datos íntegros, migraciones y recuperación probadas |
| PA21 | Cancelar tarea multietapa | Sin pasos nuevos y efectos previos informados |
| PA22 | Sin Internet | Funciones locales disponibles y nube claramente desconectada |
| PA23 | Dos dispositivos editan un recuerdo | Conflicto resuelto sin borrado silencioso |
| PA24 | Instalar en entorno limpio | Arranque real sin herramientas del desarrollador |

Pruebas automatizadas: unidad, contratos, integración con dobles de proveedor y flujos de aplicación. Pruebas reales separadas: API, Windows, Android físico, audio y Chrome. Usar recursos temporales para pruebas destructivas. Registrar versión de OS, app, modelo y servidor MCP; no afirmar compatibilidad universal por un único teléfono.

## 20. Plan completo de implementación

| Hito | Resultado obligatorio | Requisitos principales |
|---|---|---|
| H0 | Inventario del entorno, decisiones, estructura y matriz de permisos | Base técnica |
| H1 | Apps Windows/Android que arrancan, backend y Astra real | RF01, RF17 |
| H2 | Memoria, documentos, persistencia y diagnóstico | RF02, RF11, RF16 |
| H3 | Voz en ambos dispositivos e interrupción | RF03 |
| H4 | Explorador y operaciones de archivos con recuperación | RF04, RF05 |
| H5 | Programas y ejecutores locales Windows/Android | RF06, RF07, RF08 |
| H6 | Cliente MCP propio y navegación real | RF09, RF10 |
| H7 | Planificación, tareas persistentes y cancelación | RF12 |
| H8 | Emparejamiento, remoto, sincronización e independencia Android | RF14, RF15 |
| H9 | Monitoreo, recordatorios, voz de activación y proactividad | RF13 |
| H10 | Instaladores, mantenimiento y aceptación integral | RF18 y regresión completa |

Permisos, diagnósticos y cancelación se implementan desde los primeros ejecutores; no se posponen al último hito. Completar los hitos viables en orden de dependencia. Ante un bloqueo real, continuar tareas independientes y dejar evidencia exacta de lo que falta.

No detener el proyecto por haber terminado H1. Tampoco etiquetar como completa una función sustituida por un botón sin efecto, respuesta simulada o prueba únicamente con dobles.

## 21. Entregables y definición de terminado

Repositorio completo con aplicación Flutter, adaptadores Kotlin, ejecutor Windows, orquestador/backend y host MCP. Incluir contratos, pruebas, lockfiles, configuración de ejemplo sin secretos, guías de compilación, guía de instalación, manual del usuario, matriz de permisos y reporte de validación.

Entregar APK firmado de prueba y artefacto Windows reproducible; separar claves de firma del repositorio y definir su custodia para futuras actualizaciones. No prometer publicación en tiendas como parte automática de compilar.

Mantener `ESTADO_IMPLEMENTACION.md` con cada RF y PA: pendiente, en curso, implementado sin prueba real, verificado o bloqueado. Añadir evidencia, entorno y motivo. Una restricción de plataforma puede justificar una alternativa documentada, pero no convertir en «cumplido» el acceso universal solicitado.

Criterio final: todos los requisitos obligatorios implementados y sus pruebas aplicables aprobadas; variantes experimentales identificadas; límites y fallos conocidos visibles. El conjunto debe poder instalarse y usarse sin mantener abierto Codex o Antigravity.

## 22. Instrucción ejecutiva para Codex o Antigravity

> Construye desde cero el proyecto JARVIS siguiendo esta especificación. Crea aplicaciones instalables para Windows y Android, con interfaz Flutter, ejecutores nativos, memoria persistente, voz, archivos, programas, navegador MCP y coordinación de dispositivos. Usa `gpt-6-astra` como modelo principal verificando acceso real. Integra Chrome DevTools MCP en el runtime de Jarvis; no confundas configurarlo en Codex con incorporarlo al producto. Android debe tener funciones locales propias y modo de inferencia independiente de la PC. Inspecciona el workspace, respeta las instrucciones del repositorio y conserva el trabajo existente. Implementa por hitos hasta completar el alcance viable, manteniendo estados y pruebas. No respondas solo con otro plan. Si falta una credencial o dispositivo para validar, deja el código y las pruebas reproducibles listos, continúa lo independiente e indica qué permanece sin verificar. No afirmes acceso total al sistema, AGI alcanzada ni funciones terminadas sin evidencia. Entrega artefactos y comandos reales; no solicites claves por el chat.

## 23. Referencias y límites de esta revisión

Documentación primaria consultada el 7 de octubre de 2026. Verificar cambios al implementar. Las decisiones arquitectónicas y los criterios de aceptación son propuestas de este proyecto; las fuentes respaldan capacidades o restricciones concretas.

- **S1 — OpenAI, GPT-6 Astra:** https://developers.openai.com/api/docs/models/gpt-6-astra
- **S2 — Chrome DevTools MCP y configuración para agentes:** https://github.com/ChromeDevTools/chrome-devtools-mcp y https://developer.chrome.com/docs/devtools/agents
- **S3 — Flutter, integración con código nativo:** https://docs.flutter.dev/platform-integration/platform-channels
- **S4 — Android, acceso a archivos:** https://developer.android.com/training/data-storage/manage-all-files
- **S5 — Android, instalación y acción del usuario:** https://developer.android.com/reference/android/content/pm/PackageInstaller.SessionParams
- **S6 — Google Play, uso de AccessibilityService:** https://support.google.com/googleplay/android-developer/answer/10964491
- **S7 — Android, servicios de primer plano y micrófono:** https://developer.android.com/develop/background-work/services/fgs/service-types
- **S8 — SQLite, copias coherentes:** https://www.sqlite.org/backup.html
- **S9 — Microsoft, UI Automation:** https://learn.microsoft.com/en-us/windows/win32/winauto/uiauto-uiautomationoverview
- **S10 — Gemini, catálogo de modelos:** https://ai.google.dev/api/models

Se revisó el archivo adjunto `Jarvis_Instrucciones_Codex(1).md`. Las referencias de Instagram del encargo anterior no pudieron visualizarse; no se atribuyen funciones concretas a esos videos. Esta revisión documenta el producto y su control de calidad: no ejecutó instalaciones, acceso al teléfono, llamadas con credenciales del usuario ni pruebas sobre su PC.
