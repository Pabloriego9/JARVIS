# Estado de implementación — JARVIS 0.1.0

Fecha de verificación: 8 de octubre de 2026. Esta es una entrega de desarrollo. **No cumple todavía la definición de terminado de la especificación.** Compilar una plataforma no demuestra que funcione en un dispositivo real.

## Entrega disponible

- Código del backend Python, aplicación Flutter para Windows/Android, adaptador Android Kotlin y ejecutor Windows .NET.
- `artifacts/JARVIS-Android-arm64-debug.apk`: APK de prueba para ARM64, Android 8/API 26 o superior. Compilado y firma de depuración verificada; no instalado en un teléfono durante esta sesión.
- `artifacts/JARVIS-Windows-executor-x64.zip`: ejecutor nativo con runtime .NET incluido. Compilado para Windows x64; no es el instalador de la aplicación completa y no se ejecutó en Windows.
- `artifacts/JARVIS-codigo-fuente.zip`: fuentes, lockfiles, pruebas, scripts y documentación. No contiene credenciales, datos personales ni dependencias descargadas.
- Scripts de compilación, workflow de CI y definición de instalador Windows. Su ejecución completa en Windows está pendiente.
- Backend iniciado y comprobado en esta máquina de desarrollo; no hay un servidor público desplegado. Los cambios no se publicaron en GitHub.

## Evidencia obtenida

| Verificación | Resultado y alcance |
|---|---|
| Instalación de dependencias | `scripts/setup.sh` completado con lockfiles congelados. |
| Backend | 24 pruebas aprobadas. Incluyen persistencia, permisos, conflictos, recuperación, tareas, límites y transporte remoto. Las respuestas del proveedor se simulan en estas pruebas. |
| HTTP real del backend | Salud y sesión autenticada; crear, leer, editar y olvidar memoria; métricas reales. Comprobado contra el proceso iniciado, además de los tests. |
| Flutter | Cuatro pruebas aprobadas: contrato de tareas, HTTPS, estado desconectado y pantalla móvil con texto ampliado. `flutter analyze` sin incidencias. |
| Chrome DevTools MCP | Formulario real operado desde la API de JARVIS mediante su cliente MCP: abrir, observar, rellenar, pulsar y observar «Guardado: Egiverso3D». MCP 1.10.1 y Chromium en Linux. |
| Android | `flutter build apk --debug --target-platform android-arm64` completado; `apksigner verify` correcto. |
| Windows .NET | Compilación y publicación autocontenida win-x64 correctas, sin ejecutar el binario en Linux. |
| OpenAI real | Bloqueado: el diagnóstico devuelve `missing_credential`. Ni `JARVIS_OPENAI_API_KEY` ni `OPENAI_API_KEY` están disponibles en el proceso; el secreto del entorno no tiene valor vinculado. |
| Docker | Compilación pendiente: el contenedor de compilación no pudo resolver el servidor proxy para descargar dependencias. El backend sí funciona directamente en esta máquina. |

Los logs de las verificaciones completadas están en `docs/validacion/`. La prueba de Chrome necesitó desactivar su sandbox exclusivamente dentro del contenedor aislado de desarrollo; esa opción no se activa por defecto en la aplicación. No se desactivó la verificación TLS ni se omitieron verificaciones de artefactos para instalar las herramientas.

Herramientas utilizadas: Python 3.12.14, Node.js 24.19, Flutter 3.47.6, Dart 3.13.5, .NET SDK 8.0.425, JDK 21.0.12.1, Android SDK 36 y NDK 28.2.13676358.

## Trazabilidad funcional

«Parcial» significa que quedan funciones por implementar o pruebas de aceptación por ejecutar. La evidencia de una capa no se extiende automáticamente a las demás plataformas.

| ID | Estado | Implementado, evidencia y pendiente |
|---|---|---|
| RF01 | Parcial; API real bloqueada | Chat persistente, streaming, herramientas y diagnóstico. Falta conversación real con Astra y comprobar acceso del proyecto al modelo. |
| RF02 | Backend verificado; cliente parcial | Memoria SQLite, corrección, borrado lógico, revisiones y recuperación tras reabrir. Android dispone de memoria local; falta sincronización automática con el servidor. |
| RF03 | Parcial, sin aceptación real | Grabación, transcripción OpenAI y reproducción TTS conectadas en código. Falta probar audio y permisos en PC/teléfono, interrupción y bloqueo. |
| RF04 | Parcial | Explorador y búsqueda del backend; selector SAF nativo Android. Falta aceptación física y ampliar operaciones sobre árboles grandes. |
| RF05 | Parcial | Ciclo de archivos, versiones, colisiones, copia previa, cuarentena y restauración verificados en backend. SAF compilado sin prueba física. No hay gestión completa de carpetas por lotes ni edición binaria general. |
| RF06 | Parcial, requiere Windows | Ejecutor winget con argumentos estructurados y verificación posterior. Falta instalar, actualizar y desinstalar en un Windows real. |
| RF07 | Parcial, requiere Windows | UI Automation, foco, inspección, invocación, volumen y captura implementados. Falta prueba de una aplicación real y percepción visual completa. |
| RF08 | Parcial, requiere Android | SAF, memoria local, métricas y flujo del instalador/tienda compilados. Falta probar permisos y resultados en teléfono. |
| RF09 | Subconjunto verificado | Host MCP propio con permisos y formulario real. Catálogo limitado; falta verificar todas las capacidades requeridas y uso en Windows. |
| RF10 | Parcial | El agente puede consultar observaciones del navegador. Falta un flujo de investigación con proveedor real y referencias comprobadas. |
| RF11 | Parcial | Lectura de texto, extracción PDF/DOCX y referencias; captura Windows. Falta aceptación de documentos y razonamiento visual sobre capturas. |
| RF12 | Backend verificado; integración parcial | Tareas persistentes, confirmaciones, resultados, cancelación y recuperación incierta probados. El flujo del agente usa un doble del proveedor; falta aceptación con IA real. |
| RF13 | Parcial | Métricas y recordatorios persistentes con deduplicación. Faltan reglas proactivas completas, notificaciones de sistema/segundo plano y aceptación en ambos dispositivos. |
| RF14 | Parcial | Emparejamiento, revocación, destino exacto y buzón remoto probados en backend. Android requiere primer plano y confirmación local; falta el flujo físico entre dispositivos y control remoto Windows completo. |
| RF15 | Parcial | Revisiones, conflictos, tombstones y no reejecución de solicitudes. Falta sincronización bidireccional automática, interfaz de resolución y reconciliación completa tras desconexión. |
| RF16 | Parcial | Scopes, aprobaciones vinculadas a argumentos, protección de rutas, conflictos y backup cifrado verificados. Faltan retención configurable y revisión integral; el navegador no aísla todo el tráfico de red por origen. |
| RF17 | Parcial | UI adaptable con estados reales, teclado, detención y texto ampliado probado. Faltan lector de pantalla, teclado completo y aceptación táctil física. |
| RF18 | Parcial | APK de depuración y ejecutor .NET compilados. Faltan instalador Windows completo, firma de distribución, instalación limpia y actualización preservando datos. |

## Pruebas de aceptación de la especificación

| ID | Evidencia actual |
|---|---|
| PA01 | Pendiente: credencial no vinculada; no hubo solicitud real a Astra. |
| PA02 | Persistencia al reabrir SQLite aprobada en backend; falta cerrar y abrir la app instalada. |
| PA03 | Corrección, olvido y tombstone aprobados en backend. |
| PA04 | Pendiente en ambos dispositivos: micrófono, transcripción y salida audible. |
| PA05 | Ciclo de archivos aprobado en backend; pendiente en Android y Windows físicos. |
| PA06 | Revocar carpeta y rechazar operaciones aprobado en backend. |
| PA07 | Cambio de versión después de vista previa detectado antes de sobrescribir, aprobado. |
| PA08 | Pendiente: instalación real mediante winget y UAC. |
| PA09 | Pendiente: instalación Android y resultado real del instalador del sistema. |
| PA10 | Aprobada en Linux con formulario local real, JARVIS API y MCP propio. |
| PA11 | El proceso usa MCP propio sin herramientas de navegador de Codex; falta repetir fuera de esta sesión y en instalación final. |
| PA12 | Rechazo de scripts y URLs fuera del permiso probado; falta ataque de prompt injection con proveedor y página reales. |
| PA13 | Funciones locales Android implementadas; falta teléfono con PC apagada y backend independiente desplegado. |
| PA14 | Contrato exige dispositivo, permiso y ruta explícitos; falta conversación real para desambiguar. |
| PA15 | Revocación de dispositivo y rechazo posterior aprobados en backend. |
| PA16 | Deduplicación y recuperación incierta aprobadas en backend; falta desconexión física durante una acción. |
| PA17 | Pendiente: bloqueo y ahorro de batería, tiempos y consumo reales. |
| PA18 | Zona horaria, persistencia y deduplicación del planificador aprobadas; falta notificación real al usuario y cambio desde la app. |
| PA19 | 401/403/404/429 diagnosticados con HTTP simulado; presupuesto probado. Falta aceptación con red real, timeout y UI durante fallos. |
| PA20 | Backup cifrado y restauración íntegra probados; falta actualización de una instalación anterior y migraciones entre versiones publicadas. |
| PA21 | Cancelación multietapa aprobada: conserva el efecto completado e impide el siguiente. |
| PA22 | UI desconectada y operaciones locales implementadas; falta prueba física sin Internet. |
| PA23 | Conflictos de revisión rechazados sin sobreescritura silenciosa en backend; falta resolución completa entre dos clientes. |
| PA24 | Pendiente: instalación limpia sin herramientas de desarrollo. |

## Próximos pasos necesarios

1. Vincular `JARVIS_OPENAI_API_KEY` en los ajustes seguros del entorno y guardar. Reiniciar el backend con el entorno actualizado y ejecutar el diagnóstico y una conversación real. La clave permanece en el servidor, nunca en el APK.
2. Probar el APK en un Android ARM64 con carpetas y documentos de prueba. Para chat desde el teléfono hace falta un backend accesible por HTTPS y emparejamiento; esta máquina de desarrollo no es un servicio público permanente.
3. Ejecutar `scripts/build-windows.ps1` en Windows con las herramientas indicadas en `docs/COMPILACION.md`; probar el paquete y el instalador antes de distribuirlos.
4. Completar las funciones y aceptaciones parciales indicadas arriba: especialmente sincronización, notificaciones, automatización y percepción; no son tareas resueltas por añadir la API key.

La configuración de instalación y arranque del entorno se guarda como borrador revisable. Guardar ese borrador no publica el código, no despliega el backend y no demuestra que una nueva máquina restaure correctamente el entorno.
