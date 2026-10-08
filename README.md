# JARVIS

Asistente personal en español, creado a partir de [la especificación multiplataforma](docs/ESPECIFICACION.md).

**Versión de desarrollo 0.1.0.** Hay código funcional y pruebas para el backend, Flutter, Android y el ejecutor Windows. El alcance integral de la especificación **todavía no está completado**. Consultá [ESTADO_IMPLEMENTACION.md](ESTADO_IMPLEMENTACION.md) para distinguir implementación, validación y trabajo pendiente.

## Empezar con el backend

Requiere Python 3.12+, [uv](https://docs.astral.sh/uv/), Node.js 24 LTS si se usa Chrome MCP, y Chrome instalado para automatizar el navegador.

```bash
uv sync --frozen --extra dev
npm ci --ignore-scripts
uv run jarvis serve
```

El servidor escucha en loopback, puerto 8765. Guarda datos fuera del repositorio en el directorio de usuario de JARVIS (`platformdirs`), o en `JARVIS_DATA_DIR` si se configura. Al iniciar crea allí `admin.token` con permisos restringidos; la app de Windows puede leer esa sesión local automáticamente. No es una clave de OpenAI ni debe compartirse por chat. Android se empareja con un código de un solo uso generado por la sesión administradora.

Configurá `JARVIS_OPENAI_API_KEY` en el **servidor** para conversar. Para descartar conflictos de nombres en el gestor de secretos de Codex se admite también `JARVIS_OPENAI_API_KEY_2`: si contiene un valor, tiene prioridad sobre el nombre original. No se cambia de credencial automáticamente cuando una solicitud falla. El modelo predeterminado es `gpt-6-astra`; no hay sustitución automática si la cuenta no tiene acceso. `.env.example` documenta las variables; el runtime lee el entorno del proceso y **no carga `.env` automáticamente**. Las operaciones locales, memoria y permisos funcionan sin una clave de IA.

En Windows PowerShell se puede iniciar el backend con `uv run jarvis serve`. La guía de compilación explica cómo empaquetarlo para usuarios sin herramientas de desarrollo.

## Aplicación Flutter

Herramientas verificadas en desarrollo: Flutter 3.47.6 / Dart 3.13.5, JDK 21, Android SDK 36, .NET SDK 8.0.425. Los lockfiles están incluidos.

```bash
cd apps/jarvis_app
flutter pub get --enforce-lockfile
flutter run -d windows      # En Windows con Visual Studio C++ Desktop
flutter run -d <device-id>  # En Android con ADB y permiso del teléfono
```

En **Ajustes** configurá el backend y la sesión, o emparejá con un código. Para Android independiente de la PC, desplegá el backend privado con TLS según [DEPLOYMENT.md](docs/DEPLOYMENT.md). La clave de IA permanece en el servidor.

Android dispone de memoria SQLite local y exploración/edición de carpetas seleccionadas mediante el diálogo nativo. En **Archivos**, el selector «Este teléfono» indica el destino. La recepción de tareas remotas es optativa, requiere la app abierta y confirmación local. Windows usa su backend local para archivos y su ejecutor .NET para integración con el escritorio.

## Comprobar

```bash
uv run ruff check backend tests scripts
uv run pytest -q
cd apps/jarvis_app
flutter analyze
flutter test
```

Prueba real de MCP, desde la raíz, con Chrome instalado:

```bash
uv run python scripts/smoke_mcp.py
```

Opcionalmente `JARVIS_CHROME_EXECUTABLE` fija la ubicación de Chrome/Chromium. La prueba crea un formulario HTTP temporal en loopback y lo opera mediante la API de JARVIS, sus confirmaciones y su cliente MCP. `JARVIS_CHROME_NO_SANDBOX=true` se utilizó exclusivamente para la prueba de Chromium dentro del contenedor aislado; no es la configuración predeterminada del producto ni debe activarse en un equipo personal.

## Estructura

- `apps/jarvis_app`: app Flutter y adaptador Android Kotlin.
- `backend/jarvis`: API, orquestador, proveedores, permisos, memoria, archivos, tareas y host MCP.
- `native/windows/Jarvis.Executor`: ejecutor .NET Windows con winget y UI Automation.
- `tests`: pruebas de contratos, seguridad, persistencia, recuperación y proveedores simulados.
- `scripts`: arranque, compilación y aceptación MCP real.
- `deploy`: backend privado con TLS e instalador Windows reproducible.
- `docs`: arquitectura, permisos, compilación y manual.

## Documentación

[Uso](docs/USO.md) · [Compilación](docs/COMPILACION.md) · [Backend privado](docs/DEPLOYMENT.md) · [Arquitectura y permisos](docs/ARQUITECTURA.md) · [Estado y evidencias](ESTADO_IMPLEMENTACION.md)

No se incluye ninguna credencial de proveedor. El archivo de sesión local, las claves de firma, los datos personales y las copias de seguridad están fuera del control de versiones. Crear código y artefactos locales no publica cambios en GitHub ni despliega un servidor.
