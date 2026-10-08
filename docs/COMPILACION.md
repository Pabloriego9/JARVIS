# Compilación, firma y actualización

## Android

Instalar Flutter 3.47.6, JDK 21 completo, Android SDK Platform 36, Build Tools 36.0.0 y NDK 28.2.13676358. Algunas dependencias también compilan contra SDK 35; Gradle solicita instalarlo. No desactivar TLS ni las verificaciones de checksum.

```bash
cd apps/jarvis_app
flutter pub get --enforce-lockfile
flutter analyze
flutter test
flutter build apk --debug --target-platform android-arm64
```

El APK se genera en `build/app/outputs/flutter-apk/app-debug.apk`, firmado con la clave de desarrollo local. Puede instalarse en un teléfono ARM64 con Android 8+ mediante `adb install -r <archivo.apk>` o abriendo el archivo en el dispositivo. El usuario acepta la instalación. **Firma de prueba**, sin publicación en Play ni validación física implícita.

La clave de desarrollo se guarda fuera del repositorio, en el directorio de usuario de Android (`ANDROID_USER_HOME` en este entorno). Preservarla si se necesita actualizar el APK de prueba sin cambiar la identidad de firma. No utilizarla para distribución pública. Desinstalar para cambiar de firma elimina datos locales salvo exportación previa.

Para una distribución personal mantenida, crear una clave propia fuera del repositorio y usar variables de entorno `JARVIS_SIGNING_STORE`, `JARVIS_SIGNING_STORE_PASSWORD`, `JARVIS_SIGNING_KEY_ALIAS`, `JARVIS_SIGNING_KEY_PASSWORD`. Guardar el keystore y sus contraseñas en un lugar seguro, con copia independiente. La compilación release falla si no se proporcionan. Luego ejecutar `flutter build apk --release` o `flutter build appbundle --release`. La firma y una prueba de instalación/actualización física son parte del proceso de entrega, no consecuencia automática de compilar.

## Windows

Requiere Windows x64, Visual Studio 2022 con Desktop Development with C++, Flutter 3.47.6, .NET SDK 8, Python 3.12, uv y Node.js 24. Inno Setup 6 es opcional para generar el instalador.

```powershell
./scripts/build-windows.ps1
```

Construye la interfaz, publica el ejecutor con runtime .NET incluido, empaqueta el backend Python, incorpora Node y el servidor MCP fijado por lockfile y prepara un ZIP portátil. Si `ISCC.exe` está disponible, genera `artifacts/JARVIS-Setup-0.1.0.exe`.

`scripts/launch-windows.vbs` inicia `launch-windows.ps1`, que verifica/arranca el backend en la sesión del usuario y abre la interfaz. La política de PowerShell del equipo se conserva: no se desactiva ni se eleva todo JARVIS. Si impide ejecutar un script local, el administrador debe revisar y firmar el lanzador o ejecutar los binarios manualmente. Chrome debe estar instalado; JARVIS usa su propio perfil.

El ejecutor nativo también puede publicarse por separado en Linux:

```bash
dotnet publish native/windows/Jarvis.Executor -c Release -r win-x64 --self-contained true -o artifacts/windows-executor
```

Esta compilación cruzada **no prueba** UI Automation, winget, UAC ni una sesión Windows. La app Flutter Windows y el instalador completo no se compilan en Linux. El workflow GitHub incluye un job Windows que aún necesita ejecutarse en un runner autorizado tras publicar los archivos del repositorio.

## Mantenimiento

- Antes de actualizar: `jarvis backup <archivo.jbackup>`; el comando solicita una frase de cifrado en la consola sin mostrarla.
- Los datos están fuera del directorio de instalación. El desinstalador Windows conserva esos datos; borrarlos requiere una decisión separada.
- Restaurar con el servidor detenido en un directorio **nuevo**: `jarvis restore <archivo.jbackup> --destination <carpeta>`. Luego apuntar `JARVIS_DATA_DIR` allí.
- Tras restaurar, volver a emparejar dispositivos. Las aprobaciones anteriores no se reutilizan.
- Dependencias de Python: `uv.lock`; Node/MCP: `package-lock.json`; Flutter: `pubspec.lock`; .NET: `packages.lock.json`; Gradle Wrapper con SHA256 oficial. Actualizar cada grupo de forma explícita y volver a validar.
- Las pruebas de actualización, desinstalación y migración en hardware Windows/Android todavía están pendientes.

## Entorno Linux de desarrollo

El script `scripts/cloud-env.sh` expone las herramientas instaladas bajo `/workspace/.toolchains` y redirige las cachés a `/workspace/.cache`. No redefine HOME. Flutter/Dart utilizan las opciones oficiales para desactivar telemetría. Java usa el proxy del entorno y el almacén de certificados del sistema mediante la configuración local de Gradle; esa configuración no contiene credenciales y no se distribuye en la app.
