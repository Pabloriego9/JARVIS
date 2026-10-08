# Backend privado independiente de la PC

Para que Android converse con IA cuando la PC esté apagada, ejecutar este backend en una máquina Linux privada que permanezca encendida. El APK no contiene una clave de IA ni un modelo descargado.

## Despliegue con Docker y TLS

La máquina debe tener Docker Compose, un dominio bajo control del usuario, DNS configurado y acceso entrante a 80/443. El despliegue y su costo requieren decidir dónde alojarlo; no se aprovisionó un servicio externo desde esta tarea.

Configurar `JARVIS_DOMAIN` y `JARVIS_OPENAI_API_KEY` mediante el gestor de secretos del servidor. No poner el valor de la clave en Git, capturas o conversaciones. Desde la raíz:

```bash
docker compose -f deploy/compose.yaml up -d --build
```

El backend solo se publica hacia el contenedor TLS; el puerto 8765 no se expone al host. Caddy obtiene/renueva el certificado para el dominio. El volumen `jarvis_data` conserva SQLite y la sesión local. Hacer copias cifradas y verificar su restauración antes de confiar datos importantes.

Generar un código de emparejamiento desde la consola administradora del servidor:

```bash
docker compose -f deploy/compose.yaml exec backend .venv/bin/jarvis pair
```

En Android: Ajustes → dirección `https://<dominio>` → código → Emparejar. El código dura tres minutos y solo sirve una vez. Las sesiones duran 24 horas; volver a emparejar al vencer. El teléfono guarda su sesión en el almacenamiento protegido del sistema.

## Operación y límites

`/health` solo devuelve versión y estado general. Toda API de datos requiere autenticación. No hay frontend web ni exposición de DevTools. El contenedor de inferencia no incluye un Chrome ni un ejecutor Windows: para controlar la PC, se usa el backend y ejecutor instalados en esa PC. No se abren puertos del router automáticamente.

El ejecutor Android recibe tareas solo en primer plano, con recepción activada y confirmación local. Si se desconecta tras retirar una solicitud, no se reenvía la operación: el estado queda incierto hasta revisar la evidencia. No hay servicio Android de escucha permanente.

Probar desde Ajustes la solicitud mínima al modelo y comprobar proveedor/modelo efectivos. Un error 404 conserva `gpt-6-astra` y pide corregir el acceso; no cambia a otro modelo. Validar HTTP 401/403/429, expiración de sesión y revocación antes de abrir el servicio a dispositivos adicionales.

Esta configuración de despliegue se entrega como código reproducible; no equivale a un servidor publicado ni a una prueba real con el dominio y la credencial del usuario.
