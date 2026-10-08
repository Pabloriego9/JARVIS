"""Real JARVIS -> MCP -> Chromium -> local form acceptance check (no provider)."""

import json
import os
import re
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from fastapi.testclient import TestClient
from jarvis.app import create_app
from jarvis.config import Settings


class Page(BaseHTTPRequestHandler):
    def do_GET(self):
        html = b"""<html lang="es"><title>JARVIS MCP acceptance</title>
        <label>Nombre<input aria-label="Nombre" id="name"></label>
        <button onclick="document.getElementById('result').textContent='Guardado: '+document.getElementById('name').value">Guardar</button>
        <p id="result" role="status"></p></html>"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html)

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{server.server_port}"
    with tempfile.TemporaryDirectory() as temp:
        app = create_app(Settings(data_dir=Path(temp), api_key="", mcp_enabled=True, mcp_headless=True))
        with TestClient(app) as client:
            client.headers["Authorization"] = "Bearer " + (Path(temp) / "admin.token").read_text()
            grant = client.post(
                "/v1/grants",
                json={
                    "kind": "site",
                    "resource": origin,
                    "operations": ["new_page", "take_snapshot", "fill", "click"],
                },
            ).json()["id"]

            def tool(name, args):
                task_id = client.post(
                    "/v1/tasks",
                    json={
                        "title": name,
                        "idempotency_key": str(time.time_ns()),
                        "actions": [
                            {
                                "tool_name": "browser.call",
                                "arguments": {"site_grant_id": grant, "name": name, "arguments": args},
                            }
                        ],
                    },
                ).json()["task_id"]
                for _ in range(300):
                    task = client.get(f"/v1/tasks/{task_id}").json()
                    if task["status"] == "awaiting_approval":
                        aid = task["actions"][task["index"]]["approval_id"]
                        assert client.post(f"/v1/approvals/{aid}").status_code == 200
                    if task["status"] == "completed":
                        result = json.loads(task["steps"][-1]["result"])
                        assert result["status"] == "completed", result
                        return "\n".join(c.get("text", "") for c in result["data"].get("content", []))
                    if task["status"] in ("failed", "uncertain"):
                        raise AssertionError(task)
                    time.sleep(0.1)
                raise TimeoutError(name)

            opened = tool("new_page", {"url": origin})
            match = re.search(r"(?m)^(\d+): .*\(" + re.escape(origin), opened)
            assert match, opened
            page_id = int(match[1])
            snapshot = tool("take_snapshot", {"pageId": page_id})
            textbox = re.search(r'uid=(\S+) textbox "Nombre"', snapshot)[1]
            button = re.search(r'uid=(\S+) button "Guardar"', snapshot)[1]
            tool("fill", {"pageId": page_id, "uid": textbox, "value": "Egiverso3D"})
            tool("click", {"pageId": page_id, "uid": button})
            final = tool("take_snapshot", {"pageId": page_id})
            assert "Guardado: Egiverso3D" in final, final
            print(
                json.dumps(
                    {
                        "status": "passed",
                        "flow": "JARVIS API → approvals → MCP → form → snapshot",
                        "mcp_version": "1.10.1",
                        "observed": "Guardado: Egiverso3D",
                        "sandbox_disabled_for_container_test": os.getenv("JARVIS_CHROME_NO_SANDBOX")
                        == "true",
                    }
                )
            )
    server.shutdown()


if __name__ == "__main__":
    main()
