import asyncio
import json
import time

from .contracts import ToolError, ToolResult
from .store import encode, uid

REMOTE_METHODS = {
    "files.list",
    "files.read",
    "files.create",
    "files.write",
    "files.copy",
    "files.move",
    "files.rename",
    "files.trash",
    "files.restore",
    "memory.list",
    "memory.save",
    "memory.delete",
    "system.metrics",
}


class Remote:
    """Durable mailbox. A disconnected executor never receives an automatic replay."""

    def __init__(self, store):
        self.store = store
        store.execute(
            "CREATE TABLE IF NOT EXISTS remote_requests(id TEXT PRIMARY KEY, task_id TEXT NOT NULL, "
            "device_id TEXT NOT NULL, envelope TEXT NOT NULL, state TEXT NOT NULL, deadline REAL NOT NULL, result TEXT)"
        )

    def validate(self, call, target):
        device = self.store.one("SELECT * FROM devices WHERE id=? AND revoked=0", (target,))
        if not device or not device["expires"] or device["expires"] < time.time():
            raise ToolError(
                "device_unavailable", "El dispositivo destino no tiene una sesión vigente.", "denied"
            )
        if call.tool_name not in REMOTE_METHODS:
            raise ToolError(
                "remote_unsupported",
                "Esta herramienta no está disponible en el ejecutor Android.",
                "unsupported",
            )
        if "files.saf" not in json.loads(device["capabilities"]):
            raise ToolError(
                "capability_missing", "El dispositivo no registró un ejecutor Android.", "unsupported"
            )

    async def execute(self, task, call):
        self.validate(call, task["device_id"])
        rid = uid()
        envelope = {
            "request_id": rid,
            "task_id": task["id"],
            "device_id": task["device_id"],
            "tool_name": call.tool_name,
            "arguments": call.arguments,
            "schema_version": 1,
            "expected_resource_version": call.expected_resource_version,
            "deadline": task["deadline"],
            "idempotency_key": rid,
        }
        self.store.execute(
            "INSERT INTO remote_requests VALUES(?,?,?,?,?,?,NULL)",
            (rid, task["id"], task["device_id"], encode(envelope), "pending", task["deadline"]),
        )
        self.store.event(
            "pending_connection", {"device_id": task["device_id"], "request_id": rid}, task["id"]
        )
        try:
            while time.time() < task["deadline"]:
                self.validate(call, task["device_id"])
                row = self.store.one("SELECT * FROM remote_requests WHERE id=?", (rid,))
                if row["state"] == "completed":
                    return ToolResult.model_validate_json(row["result"])
                await asyncio.sleep(0.1)
            raise ToolError(
                "remote_timeout", "El destino no confirmó el resultado antes del vencimiento.", "uncertain"
            )
        finally:
            self.store.execute(
                "UPDATE remote_requests SET state=CASE WHEN state='pending' THEN 'cancelled' ELSE 'uncertain' END "
                "WHERE id=? AND state NOT IN ('completed','cancelled')",
                (rid,),
            )

    def poll(self, device_id):
        with self.store.transaction() as db:
            rows = db.execute(
                "SELECT r.* FROM remote_requests r JOIN tasks t ON t.id=r.task_id WHERE r.device_id=? "
                "AND r.state='pending' AND r.deadline>? AND t.status='running' ORDER BY r.rowid LIMIT 1",
                (device_id, time.time()),
            ).fetchall()
            for row in rows:
                db.execute("UPDATE remote_requests SET state='dispatched' WHERE id=?", (row["id"],))
        return [json.loads(row["envelope"]) for row in rows]

    def result(self, device_id, request_id, result):
        row = self.store.one(
            "SELECT * FROM remote_requests WHERE id=? AND device_id=?", (request_id, device_id)
        )
        if not row:
            raise ToolError("unknown_request", "La solicitud no pertenece a este dispositivo.", "denied")
        if row["state"] == "completed":
            if json.loads(row["result"]) != result.model_dump():
                raise ToolError("result_conflict", "Ya hay otro resultado registrado para esta solicitud.")
            return
        if row["state"] != "dispatched" or row["deadline"] < time.time():
            raise ToolError(
                "expired_request", "La solicitud venció o fue detenida. Conservá la evidencia local."
            )
        self.store.execute(
            "UPDATE remote_requests SET state='completed',result=? WHERE id=?",
            (result.model_dump_json(), request_id),
        )
