import asyncio
import json
import os
from pathlib import Path

from jsonschema import validate

from .contracts import ToolError


class McpHost:
    """An independent stdio MCP client; no Codex process/configuration is involved."""

    def __init__(self, settings):
        self.settings = settings
        self.process = None
        self.reader_task = None
        self.stderr_task = None
        self.pending = {}
        self.catalog = {}
        self.counter = 0
        self.start_lock = asyncio.Lock()

    async def start(self):
        async with self.start_lock:
            if self.process and self.process.returncode is None:
                return
            if not self.settings.mcp_enabled:
                raise ToolError(
                    "mcp_disabled", "Activá el host MCP en el servidor para usar Chrome.", "unsupported"
                )
            runtime_dir = Path(os.getenv("JARVIS_RUNTIME_DIR", str(Path(__file__).resolve().parents[2])))
            entry = runtime_dir / "node_modules/chrome-devtools-mcp/build/src/bin/chrome-devtools-mcp.js"
            if not entry.is_file():
                raise ToolError("mcp_missing", "Ejecutá npm ci en la raíz del proyecto.", "unsupported")
            args = [
                "node",
                str(entry),
                "--isolated",
                "--no-usage-statistics",
                "--no-performance-crux",
                "--no-javascript-evaluation",
                "--redact-network-headers",
            ]
            if self.settings.mcp_headless:
                args += ["--headless"]
            chrome = os.getenv("JARVIS_CHROME_EXECUTABLE")
            if chrome:
                args += ["--executablePath", chrome]
            # Explicit testing switch; never silently disable Chromium sandboxing.
            if os.getenv("JARVIS_CHROME_NO_SANDBOX") == "true":
                args += ["--chromeArg=--no-sandbox"]
            self.process = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.reader_task = asyncio.create_task(self._read())
            self.stderr_task = asyncio.create_task(self._drain_stderr())
            await self.rpc(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "jarvis", "version": "0.1.0"},
                },
            )
            await self.notify("notifications/initialized", {})
            catalog, cursor = {}, None
            while True:
                result = await self.rpc("tools/list", {"cursor": cursor} if cursor else {})
                for tool in result["tools"]:
                    catalog[tool["name"]] = tool
                cursor = result.get("nextCursor")
                if not cursor:
                    break
            self.catalog = catalog

    async def _drain_stderr(self):
        while await self.process.stderr.readline():
            pass  # Do not place browser content or credentials in the audit stream.

    async def _read(self):
        try:
            while line := await self.process.stdout.readline():
                try:
                    message = json.loads(line)
                    future = self.pending.pop(message.get("id"), None)
                    if future and not future.done():
                        if "error" in message:
                            future.set_exception(
                                ToolError(
                                    "mcp_error",
                                    "Chrome MCP devolvió un error.",
                                    details={"code": message["error"].get("code")},
                                )
                            )
                        else:
                            future.set_result(message.get("result", {}))
                except (ValueError, TypeError):
                    continue
        finally:
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(
                        ToolError(
                            "mcp_disconnected",
                            "MCP se desconectó. Verificá el efecto antes de repetir.",
                            "uncertain",
                        )
                    )
            self.pending.clear()

    async def notify(self, method, params):
        self.process.stdin.write(
            (json.dumps({"jsonrpc": "2.0", "method": method, "params": params}) + "\n").encode()
        )
        await self.process.stdin.drain()

    async def rpc(self, method, params, timeout=45):
        self.counter += 1
        request_id = self.counter
        future = asyncio.get_running_loop().create_future()
        self.pending[request_id] = future
        self.process.stdin.write(
            (
                json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}) + "\n"
            ).encode()
        )
        await self.process.stdin.drain()
        try:
            return await asyncio.wait_for(future, timeout)
        except (TimeoutError, asyncio.CancelledError):
            await self.notify(
                "notifications/cancelled", {"requestId": request_id, "reason": "cancelled_or_timeout"}
            )
            self.pending.pop(request_id, None)
            raise

    async def call(self, name, arguments):
        await self.start()
        if name not in self.catalog:
            raise ToolError("mcp_tool_missing", "Herramienta ausente del catálogo instalado.", "unsupported")
        validate(arguments, self.catalog[name]["inputSchema"])
        return await self.rpc("tools/call", {"name": name, "arguments": arguments})

    async def close(self):
        if self.process and self.process.returncode is None:
            self.process.terminate()
            try:
                await asyncio.wait_for(self.process.wait(), 5)
            except TimeoutError:
                self.process.kill()
                await self.process.wait()
        for task in (self.reader_task, self.stderr_task):
            if task:
                task.cancel()
        self.process = None
