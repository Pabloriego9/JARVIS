import asyncio
import json
import platform
import re
import shutil
from urllib.parse import urlparse

import psutil
from jsonschema import ValidationError, validate

from .contracts import ToolError, ToolResult
from .files import Files


def schema(properties, required=()):
    return {
        "type": "object",
        "properties": properties,
        "required": list(required),
        "additionalProperties": False,
    }


S = {"type": "string"}
INTEGER = {"type": "integer"}
FILE = {"grant_id": S, "path": S}
CATALOG = {
    "files.list": ("Listar una carpeta autorizada.", schema(FILE, ["grant_id", "path"])),
    "files.search": (
        "Buscar nombres o contenido en una carpeta autorizada.",
        schema(
            {**FILE, "query": S, "content": S, "min_size": INTEGER, "max_size": INTEGER}, ["grant_id", "path"]
        ),
    ),
    "files.read": ("Leer texto y obtener SHA256 antes de editar.", schema(FILE, ["grant_id", "path"])),
    "files.document": (
        "Extraer PDF, DOCX o texto con referencias de ubicación.",
        schema(FILE, ["grant_id", "path"]),
    ),
    "files.write": (
        "Crear o editar texto. Una edición requiere expected_resource_version.",
        schema({**FILE, "content": S}, ["grant_id", "path", "content"]),
    ),
    "files.mkdir": ("Crear una carpeta.", schema(FILE, ["grant_id", "path"])),
    "files.copy": (
        "Copiar un archivo a un destino nuevo, verificando hash.",
        schema({**FILE, "destination": S, "destination_grant_id": S}, ["grant_id", "path", "destination"]),
    ),
    "files.move": (
        "Mover un archivo con verificación.",
        schema({**FILE, "destination": S, "destination_grant_id": S}, ["grant_id", "path", "destination"]),
    ),
    "files.trash": ("Enviar un archivo a cuarentena recuperable.", schema(FILE, ["grant_id", "path"])),
    "files.restore": (
        "Restaurar una copia sin sobrescribir.",
        schema({**FILE, "trash_id": S}, ["grant_id", "path", "trash_id"]),
    ),
    "memory.search": ("Consultar recuerdos explícitos.", schema({"query": S})),
    "memory.save": (
        "Guardar un hecho que el usuario pidió recordar.",
        schema(
            {"content": S, "kind": {"enum": ["fact", "project", "preference", "procedure"]}},
            ["content", "kind"],
        ),
    ),
    "memory.forget": (
        "Olvidar un recuerdo identificado y su revisión.",
        schema({"id": S, "revision": INTEGER}, ["id", "revision"]),
    ),
    "system.metrics": ("Obtener métricas reales del servidor actual.", schema({})),
    "system.capabilities": ("Consultar herramientas disponibles y plataforma.", schema({})),
    "apps.list": ("Listar programas instalados en Windows mediante winget.", schema({})),
    "apps.install": (
        "Instalar un identificador exacto de winget con confirmación.",
        schema({"package_id": S}, ["package_id"]),
    ),
    "apps.update": (
        "Actualizar un identificador exacto de winget.",
        schema({"package_id": S}, ["package_id"]),
    ),
    "apps.uninstall": (
        "Desinstalar un identificador exacto de winget.",
        schema({"package_id": S}, ["package_id"]),
    ),
    "system.windows": (
        "Control Windows mediante acciones estructuradas.",
        schema(
            {
                "action": {
                    "enum": [
                        "windows",
                        "focus",
                        "inspect",
                        "invoke",
                        "volume_up",
                        "volume_down",
                        "mute",
                        "screenshot",
                    ]
                },
                "window": S,
                "element_id": S,
            },
            ["action"],
        ),
    ),
    "browser.catalog": ("Descubrir las herramientas del host Chrome MCP propio.", schema({})),
    "browser.call": (
        "Solicitar una herramienta MCP del navegador. Requiere permiso de sitio y confirmación exacta.",
        schema(
            {"site_grant_id": S, "name": S, "arguments": {"type": "object"}},
            ["site_grant_id", "name", "arguments"],
        ),
    ),
}

READ_ONLY = {
    "files.list",
    "files.search",
    "files.read",
    "files.document",
    "memory.search",
    "system.metrics",
    "system.capabilities",
    "apps.list",
    "browser.catalog",
}


class Tools:
    def __init__(self, store, security, settings, mcp):
        self.store, self.security, self.settings, self.mcp = store, security, settings, mcp
        self.files = Files(store, security)
        self.write_lock = asyncio.Lock()

    def schemas(self):
        result = []
        for name, (description, params) in CATALOG.items():
            wrapped = schema(
                {"arguments": params, "expected_resource_version": {"type": ["string", "null"]}},
                ["arguments"],
            )
            result.append(
                {
                    "type": "function",
                    "name": name.replace(".", "__"),
                    "description": description,
                    "parameters": wrapped,
                    "strict": False,
                }
            )
        return result

    def preflight(self, call, device_id):
        if device_id != "local":
            raise ToolError(
                "remote_executor_unavailable",
                "El ejecutor remoto aún no está habilitado. Usá las acciones locales de la app.",
                "unsupported",
            )
        if call.tool_name not in CATALOG:
            raise ToolError("unknown_tool", "Herramienta fuera del catálogo.", "denied")
        try:
            validate(call.arguments, CATALOG[call.tool_name][1])
        except ValidationError:
            raise ToolError(
                "invalid_arguments", "Argumentos incompatibles con el contrato de la herramienta.", "denied"
            ) from None
        family, operation = call.tool_name.split(".")
        if family == "files":
            path, _ = self.security.folder(call.arguments["grant_id"], call.arguments["path"], operation)
            if operation in ("copy", "move"):
                self.security.folder(
                    call.arguments.get("destination_grant_id", call.arguments["grant_id"]),
                    call.arguments["destination"],
                    operation,
                )
            if operation in ("copy", "move", "trash") or (operation == "write" and path.exists()):
                self.files.check_version(path, call.expected_resource_version)
        if family == "apps" or call.tool_name == "system.windows":
            if platform.system() != "Windows" or not self.settings.windows_executor:
                raise ToolError(
                    "windows_required",
                    "Esta función necesita el ejecutor en una sesión Windows.",
                    "unsupported",
                )
        if call.tool_name == "browser.call":
            self.browser_permission(call.arguments)

    def browser_permission(self, args):
        grant = self.store.one(
            "SELECT * FROM grants WHERE id=? AND kind='site' AND revoked=0 AND device_id='local'",
            (args["site_grant_id"],),
        )
        if not grant or args["name"] not in json.loads(grant["operations"]):
            raise ToolError("site_denied", "Falta el permiso para este sitio y acción.", "denied")
        # General JavaScript, arbitrary network, upload and download paths are deliberately excluded.
        allowed = {
            "list_pages",
            "new_page",
            "navigate_page",
            "select_page",
            "close_page",
            "take_snapshot",
            "click",
            "fill",
            "fill_form",
            "press_key",
            "wait_for",
            "take_screenshot",
            "handle_dialog",
        }
        if args["name"] not in allowed:
            raise ToolError(
                "browser_unsupported",
                "Esta herramienta MCP aún no tiene un adaptador de permisos validado.",
                "unsupported",
            )
        if grant["mode"] == "consult" and args["name"] not in {"list_pages", "take_snapshot"}:
            raise ToolError("consult_mode", "El permiso de sitio es solo consulta.", "denied")
        params = args["arguments"]
        if "filePath" in params:
            raise ToolError(
                "browser_file_path",
                "La exportación de capturas a rutas arbitrarias no está habilitada.",
                "denied",
            )
        if "url" in params:
            url = urlparse(params["url"])
            if f"{url.scheme}://{url.netloc}" != grant["resource"] or url.username or url.password:
                raise ToolError("site_denied", "La dirección no coincide con el sitio autorizado.", "denied")
        return grant

    async def run(self, call):
        name, args = call.tool_name, call.arguments
        # A single writer serializes all effects in this local runtime, including approvals.
        async with self.write_lock:
            self.preflight(call, "local")
            if name.startswith("files."):
                execution = asyncio.create_task(
                    asyncio.to_thread(
                        self.files.run, name.split(".")[1], args, call.expected_resource_version
                    )
                )
                try:
                    return await asyncio.shield(execution)
                except asyncio.CancelledError:
                    # Keep the writer lock until the OS operation has stopped; never overlap a cancelled writer.
                    await execution
                    raise
            if name == "memory.search":
                return ToolResult(data=self.store.memories(args.get("query", "")))
            if name == "memory.save":
                return ToolResult(
                    data=self.store.memory_write(args["content"], args["kind"], "local"),
                    side_effects=["memory_saved"],
                )
            if name == "memory.forget":
                self.store.memory_delete(args["id"], args["revision"])
                return ToolResult(side_effects=["memory_deleted"])
            if name == "system.metrics":
                disk = shutil.disk_usage(self.settings.data_dir)
                return ToolResult(
                    data={
                        "device": "local",
                        "platform": platform.system(),
                        "cpu_percent": psutil.cpu_percent(),
                        "memory_percent": psutil.virtual_memory().percent,
                        "disk_total": disk.total,
                        "disk_free": disk.free,
                    }
                )
            if name == "system.capabilities":
                return ToolResult(
                    data={
                        "platform": platform.system(),
                        "tools": list(CATALOG),
                        "windows_executor": platform.system() == "Windows"
                        and bool(self.settings.windows_executor),
                        "mcp_enabled": self.settings.mcp_enabled,
                        "remote_execution": False,
                    }
                )
            if name.startswith("apps.") or name == "system.windows":
                return await self.native(name, args)
            if name == "browser.catalog":
                await self.mcp.start()
                return ToolResult(data=list(self.mcp.catalog.values()))
            if name == "browser.call":
                grant = self.browser_permission(args)
                if args["name"] not in ("new_page", "list_pages"):
                    page_id = args["arguments"].get("pageId")
                    if page_id is None:
                        raise ToolError(
                            "page_required", "La operación debe identificar una página concreta.", "denied"
                        )
                    pages = await self.mcp.call("list_pages", {})
                    text = "\n".join(c.get("text", "") for c in pages.get("content", []))
                    match = re.search(rf"(?m)^{int(page_id)}: .*\((https?://\S+)\)(?: \[selected\])?$", text)
                    if not match:
                        raise ToolError(
                            "page_unknown", "No se pudo comprobar el sitio de la página.", "denied"
                        )
                    actual = urlparse(match[1])
                    if f"{actual.scheme}://{actual.netloc}" != grant["resource"]:
                        raise ToolError(
                            "site_denied", "La página cambió a un sitio sin este permiso.", "denied"
                        )
                result = await self.mcp.call(args["name"], args["arguments"])
                return ToolResult(
                    status="failed" if result.get("isError") else "completed",
                    data=result,
                    evidence=[{"host": "chrome-devtools-mcp", "version": "1.10.1"}],
                    side_effects=[args["name"]],
                )
            raise ToolError("unsupported", "Herramienta no implementada.", "unsupported")

    async def native(self, name, args):
        process = await asyncio.create_subprocess_exec(
            self.settings.windows_executor,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, _ = await asyncio.wait_for(
                process.communicate(json.dumps({"tool": name, "arguments": args}).encode()), 180
            )
            if process.returncode:
                raise ToolError("native_error", "El ejecutor Windows no completó la operación.", "uncertain")
            return ToolResult.model_validate_json(out)
        except (TimeoutError, asyncio.CancelledError):
            process.kill()
            await process.wait()
            raise
