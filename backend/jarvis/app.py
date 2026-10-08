import asyncio
import json
import platform
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import Depends, FastAPI, Header, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import Field

from .config import Settings
from .contracts import (
    ChatCreate,
    GrantCreate,
    MemoryWrite,
    ReminderCreate,
    StrictModel,
    TaskCreate,
    ToolError,
    ToolResult,
)
from .engine import Engine
from .mcp_host import McpHost
from .providers import Provider
from .security import Security
from .store import Store, encode, uid
from .tools import Tools


class PairRequest(StrictModel):
    code: str = Field(min_length=10, max_length=10)
    name: str = Field(min_length=1, max_length=80)
    capabilities: list[str] = Field(default_factory=list, max_length=30)


class SpeechRequest(StrictModel):
    text: str = Field(min_length=1, max_length=4000)


def fire_reminders(store, now):
    with store.transaction() as db:
        due = db.execute("SELECT * FROM reminders WHERE enabled=1 AND due<=?", (now,)).fetchall()
        for item in due:
            db.execute(
                "INSERT INTO events(task_id,kind,data,created) VALUES(NULL,?,?,?)",
                (
                    "reminder",
                    encode(
                        {
                            "id": item["id"],
                            "title": item["title"],
                            "due": item["due"],
                            "delivery": "in_app",
                            "overdue": now - item["due"] > 60,
                        }
                    ),
                    now,
                ),
            )
            if item["interval_seconds"]:
                next_due = (
                    item["due"]
                    + (int((now - item["due"]) // item["interval_seconds"]) + 1) * item["interval_seconds"]
                )
                db.execute("UPDATE reminders SET last_fired=?,due=? WHERE id=?", (now, next_due, item["id"]))
            else:
                db.execute("UPDATE reminders SET last_fired=?,enabled=0 WHERE id=?", (now, item["id"]))


def create_app(settings=None, provider=None):
    settings = settings or Settings()
    settings.prepare()
    store = Store(settings.data_dir / "jarvis.sqlite3")
    security = Security(store, settings)
    mcp = McpHost(settings)
    provider = provider or Provider(settings)
    tools = Tools(store, security, settings, mcp)
    engine = Engine(store, settings, security, tools, provider)

    async def reminders():
        while True:
            fire_reminders(store, time.time())
            await asyncio.sleep(1)

    @asynccontextmanager
    async def lifespan(app):
        security.bootstrap()
        store.recover()
        ticker = asyncio.create_task(reminders())
        yield
        ticker.cancel()
        await asyncio.gather(ticker, return_exceptions=True)
        await engine.close()
        await mcp.close()
        await provider.close()
        store.close()

    app = FastAPI(
        title="JARVIS", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None
    )
    app.state.store, app.state.engine, app.state.security = store, engine, security
    app.state.settings, app.state.tools = settings, tools

    @app.exception_handler(ToolError)
    async def tool_error(request, error):
        status = (
            401
            if error.result.error_code == "unauthenticated"
            else 403
            if error.result.status == "denied"
            else 409
        )
        return JSONResponse(status_code=status, content=error.result.model_dump())

    @app.exception_handler(FileNotFoundError)
    async def file_missing(request, error):
        return JSONResponse(status_code=404, content={"user_message": "Recurso no encontrado."})

    def auth(authorization: str = Header(default="")):
        if not authorization.startswith("Bearer "):
            raise HTTPException(401, "Falta la sesión del dispositivo.")
        return security.authenticate(authorization[7:])

    def admin(device=Depends(auth)):
        if device["role"] != "admin":
            raise HTTPException(403, "Esta acción requiere la sesión administradora local.")
        return device

    def owned(task_id, device):
        task = store.one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not task:
            raise HTTPException(404, "Tarea no encontrada.")
        if task["owner"] != device["id"] and device["role"] != "admin":
            raise HTTPException(403, "La tarea pertenece a otro dispositivo.")
        return task

    @app.get("/health")
    def health():
        return {"status": "ok", "version": "0.1.0"}

    @app.get("/v1/status")
    def status(device=Depends(auth)):
        return {
            "device_id": device["id"],
            "role": device["role"],
            "provider": settings.provider,
            "model": settings.effective_model,
            "ai_configured": bool(settings.api_key if settings.provider == "openai" else settings.gemini_key),
            "platform": platform.system(),
            "mcp_enabled": settings.mcp_enabled,
            "timezone": settings.timezone,
            "remote_execution": "android_foreground_with_local_confirmation",
            "speech": "native_or_openai",
            "version": "0.1.0",
        }

    @app.post("/v1/provider/diagnose")
    async def diagnose(device=Depends(admin)):
        return await provider.diagnose()

    @app.get("/v1/provider/gemini/models")
    async def models(device=Depends(admin)):
        return await provider.gemini_models()

    @app.post("/v1/voice/transcribe")
    async def transcribe(file: UploadFile, device=Depends(auth)):
        if not settings.api_key:
            raise ToolError(
                "missing_credential", "La transcripción en nube necesita la credencial del servidor."
            )
        audio = await file.read(10 * 1024 * 1024 + 1)
        if len(audio) > 10 * 1024 * 1024:
            raise HTTPException(413, "Audio demasiado largo (máximo 10 MiB).")
        if file.content_type not in ("audio/wav", "audio/x-wav", "audio/mpeg", "audio/mp4", "audio/webm"):
            raise HTTPException(415, "Formato de audio no admitido.")
        r = await provider.client.post(
            "https://api.openai.com/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.api_key}"},
            files={"file": (file.filename or "voice.wav", audio, file.content_type)},
            data={"model": "gpt-4o-mini-transcribe", "language": "es"},
        )
        if r.is_error:
            raise provider.error(r)
        return {"text": r.json()["text"], "model": "gpt-4o-mini-transcribe", "audio_retained": False}

    @app.post("/v1/voice/speak")
    async def speak(body: SpeechRequest, device=Depends(auth)):
        if not settings.api_key:
            raise ToolError("missing_credential", "La voz en nube necesita la credencial del servidor.")
        r = await provider.client.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization": f"Bearer {settings.api_key}"},
            json={
                "model": "gpt-4o-mini-tts",
                "voice": "onyx",
                "input": body.text,
                "instructions": "Hablá en español con tono tranquilo, preciso y natural.",
                "response_format": "mp3",
            },
        )
        if r.is_error:
            raise provider.error(r)
        return Response(
            r.content, media_type="audio/mpeg", headers={"X-Jarvis-Voice-Model": "gpt-4o-mini-tts"}
        )

    @app.post("/v1/pairing")
    def pairing(device=Depends(admin)):
        return security.pairing()

    attempts = {}

    @app.post("/v1/pair")
    def pair(body: PairRequest, request: Request):
        host = request.client.host if request.client else "unknown"
        now = time.monotonic()
        recent = [t for t in attempts.get(host, []) if now - t < 60]
        if len(recent) >= 5:
            raise HTTPException(429, "Demasiados intentos. Esperá un minuto.")
        attempts[host] = recent + [now]
        return security.pair(body.code, body.name, body.capabilities)

    @app.get("/v1/devices")
    def devices(device=Depends(auth)):
        return store.all("SELECT id,name,role,capabilities,expires,revoked FROM devices")

    @app.post("/v1/executor/poll")
    def executor_poll(device=Depends(auth)):
        return engine.remote.poll(device["id"])

    @app.post("/v1/executor/results/{request_id}")
    def executor_result(request_id: str, body: ToolResult, device=Depends(auth)):
        engine.remote.result(device["id"], request_id, body)
        return {"stored": True}

    @app.delete("/v1/devices/{device_id}")
    def revoke_device(device_id: str, device=Depends(admin)):
        if device_id == "local":
            raise HTTPException(400, "La sesión local se rota desde la CLI.")
        store.execute("UPDATE devices SET revoked=1 WHERE id=?", (device_id,))
        for task in store.all("SELECT id FROM tasks WHERE owner=?", (device_id,)):
            engine.cancel(task["id"])
        return {"revoked": device_id}

    @app.get("/v1/grants")
    def grants(device=Depends(auth)):
        return store.all("SELECT * FROM grants WHERE revoked=0")

    @app.post("/v1/grants")
    def grant(body: GrantCreate, device=Depends(admin)):
        return security.grant(body)

    @app.delete("/v1/grants/{grant_id}")
    def revoke_grant(grant_id: str, device=Depends(admin)):
        store.execute("UPDATE grants SET revoked=1 WHERE id=?", (grant_id,))
        return {"revoked": grant_id}

    @app.get("/v1/memories")
    def memories(q: str = "", device=Depends(auth)):
        return store.memories(q)

    @app.post("/v1/memories")
    def save_memory(body: MemoryWrite, device=Depends(auth)):
        return store.memory_write(body.content, body.kind, device["id"])

    @app.put("/v1/memories/{memory_id}")
    def edit_memory(memory_id: str, body: MemoryWrite, device=Depends(auth)):
        return store.memory_write(body.content, body.kind, device["id"], memory_id, body.expected_revision)

    @app.delete("/v1/memories/{memory_id}")
    def forget(memory_id: str, revision: int, device=Depends(auth)):
        store.memory_delete(memory_id, revision)
        return {"deleted": memory_id}

    @app.get("/v1/sync/memories")
    def sync_memories(since: float = 0, device=Depends(auth)):
        rows = store.all("SELECT * FROM memories WHERE updated>? ORDER BY updated LIMIT 500", (since,))
        return {
            "changes": rows,
            "cursor": rows[-1]["updated"] if rows else since,
            "has_more": len(rows) == 500,
        }

    @app.post("/v1/tasks")
    async def task_create(body: TaskCreate, device=Depends(auth)):
        task_id = engine.create(
            body.title, body.device_id, device["id"], body.actions, body.idempotency_key, body.timeout_seconds
        )
        return {"task_id": task_id}

    @app.get("/v1/tasks")
    def tasks(device=Depends(auth)):
        where, args = ("", ()) if device["role"] == "admin" else ("WHERE owner=?", (device["id"],))
        return store.all(
            f"SELECT id,title,device_id,status,created,updated,error FROM tasks {where} ORDER BY created DESC LIMIT 100",
            args,
        )

    @app.get("/v1/tasks/{task_id}")
    def task_detail(task_id: str, device=Depends(auth)):
        task = owned(task_id, device)
        context = json.loads(task.pop("context"))
        task["actions"], task["index"] = context["actions"], context["index"]
        task["steps"] = store.all("SELECT * FROM steps WHERE task_id=? ORDER BY position", (task_id,))
        task["approvals"] = store.all(
            "SELECT id,expires,approved,used FROM approvals WHERE task_id=?", (task_id,)
        )
        return task

    @app.post("/v1/tasks/{task_id}/cancel")
    def cancel(task_id: str, device=Depends(auth)):
        owned(task_id, device)
        engine.cancel(task_id)
        return {"requested": "cancelled"}

    @app.post("/v1/stop")
    def stop(device=Depends(admin)):
        for task in store.all(
            "SELECT id FROM tasks WHERE status NOT IN ('completed','failed','uncertain','cancelled')"
        ):
            engine.cancel(task["id"])
        return {"stopped": True}

    @app.post("/v1/approvals/{approval_id}")
    async def approve(approval_id: str, device=Depends(admin)):
        row = store.one(
            "SELECT * FROM approvals WHERE id=? AND used=0 AND expires>?", (approval_id, time.time())
        )
        if not row:
            raise HTTPException(409, "Confirmación utilizada o vencida.")
        task = owned(row["task_id"], device)
        if task["status"] != "awaiting_approval":
            raise HTTPException(409, "La tarea ya no espera esta confirmación.")
        store.execute("UPDATE approvals SET approved=1,actor=? WHERE id=?", (device["id"], approval_id))
        engine.launch(row["task_id"])
        return {"approved": approval_id}

    @app.post("/v1/chat")
    async def chat(body: ChatCreate, device=Depends(auth)):
        existing = store.one(
            "SELECT id,context FROM tasks WHERE owner=? AND idempotency_key=?",
            (device["id"], body.idempotency_key),
        )
        if existing:
            return {
                "task_id": existing["id"],
                "conversation_id": json.loads(existing["context"])["chat"]["conversation_id"],
            }
        conversation_id = body.conversation_id or uid()
        store.execute("INSERT OR IGNORE INTO conversations VALUES(?,?)", (conversation_id, time.time()))
        store.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?)",
            (uid(), conversation_id, "user", body.message, time.time()),
        )
        messages = store.all(
            "SELECT role,content FROM (SELECT role,content,created FROM messages WHERE conversation_id=? ORDER BY created DESC LIMIT 20) ORDER BY created",
            (conversation_id,),
        )
        task_id = engine.create(
            body.message[:100],
            body.device_id,
            device["id"],
            [],
            body.idempotency_key,
            chat={"conversation_id": conversation_id, "input": messages},
        )
        return {"task_id": task_id, "conversation_id": conversation_id}

    @app.get("/v1/conversations")
    def conversations(device=Depends(auth)):
        return store.all("SELECT * FROM conversations ORDER BY created DESC LIMIT 50")

    @app.get("/v1/conversations/{conversation_id}/messages")
    def messages(conversation_id: str, device=Depends(auth)):
        return store.all(
            "SELECT * FROM messages WHERE conversation_id=? ORDER BY created", (conversation_id,)
        )

    @app.delete("/v1/conversations/{conversation_id}")
    def forget_conversation(conversation_id: str, device=Depends(auth)):
        # Conversation erasure also removes retained provider input in completed tasks.
        for task in store.all("SELECT id,context FROM tasks"):
            context = json.loads(task["context"])
            if (
                context.get("chat", {}).get("conversation_id") == conversation_id
                if context.get("chat")
                else False
            ):
                engine.cancel(task["id"])
                context["chat"] = None
                store.execute("UPDATE tasks SET context=? WHERE id=?", (encode(context), task["id"]))
        store.execute("DELETE FROM messages WHERE conversation_id=?", (conversation_id,))
        store.execute("DELETE FROM conversations WHERE id=?", (conversation_id,))
        return {"deleted": conversation_id}

    @app.get("/v1/events")
    def events(after: int = 0, task_id: str | None = None, device=Depends(auth)):
        if task_id:
            owned(task_id, device)
            rows = store.all(
                "SELECT * FROM events WHERE seq>? AND task_id=? ORDER BY seq LIMIT 200", (after, task_id)
            )
        elif device["role"] == "admin":
            rows = store.all("SELECT * FROM events WHERE seq>? ORDER BY seq LIMIT 200", (after,))
        else:
            rows = store.all(
                "SELECT e.* FROM events e JOIN tasks t ON t.id=e.task_id WHERE e.seq>? AND t.owner=? ORDER BY e.seq LIMIT 200",
                (after, device["id"]),
            )
        return [{**row, "data": json.loads(row["data"])} for row in rows]

    @app.get("/v1/tasks/{task_id}/stream")
    async def stream(task_id: str, request: Request, after: int = 0, device=Depends(auth)):
        owned(task_id, device)

        async def generate():
            cursor = after
            while not await request.is_disconnected():
                current_device = store.one("SELECT revoked,expires FROM devices WHERE id=?", (device["id"],))
                if current_device["revoked"] or (
                    current_device["expires"] and current_device["expires"] < time.time()
                ):
                    break
                rows = store.all(
                    "SELECT * FROM events WHERE task_id=? AND seq>? ORDER BY seq LIMIT 200", (task_id, cursor)
                )
                for row in rows:
                    cursor = row["seq"]
                    yield f"id: {cursor}\nevent: {row['kind']}\ndata: {row['data']}\n\n"
                state = store.one("SELECT status FROM tasks WHERE id=?", (task_id,))["status"]
                if (
                    state in ("completed", "cancelled", "failed", "uncertain", "awaiting_approval")
                    and not rows
                ):
                    break
                if not rows:
                    yield ": keepalive\n\n"
                await asyncio.sleep(0.15)

        return StreamingResponse(
            generate(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
        )

    @app.get("/v1/reminders")
    def reminder_list(device=Depends(auth)):
        return store.all("SELECT * FROM reminders ORDER BY due")

    @app.post("/v1/reminders")
    def reminder(body: ReminderCreate, device=Depends(auth)):
        if body.due_at.tzinfo is None:
            raise HTTPException(400, "Incluí la zona horaria en la fecha.")
        try:
            ZoneInfo(body.timezone)
        except ZoneInfoNotFoundError:
            raise HTTPException(400, "Zona horaria desconocida.") from None
        rid = uid()
        store.execute(
            "INSERT INTO reminders VALUES(?,?,?,?,?,NULL,1)",
            (rid, body.title, body.due_at.timestamp(), body.timezone, body.interval_seconds),
        )
        return {"id": rid}

    @app.delete("/v1/reminders/{reminder_id}")
    def remove_reminder(reminder_id: str, device=Depends(auth)):
        store.execute("UPDATE reminders SET enabled=0 WHERE id=?", (reminder_id,))
        return {"disabled": reminder_id}

    @app.get("/v1/usage")
    def usage(device=Depends(auth)):
        return {
            "limits": {
                "daily_tokens": settings.daily_tokens,
                "task_tokens": settings.task_tokens,
                "max_steps": settings.max_steps,
            },
            "records": store.all("SELECT * FROM usage ORDER BY created DESC LIMIT 200"),
        }

    @app.get("/v1/metrics")
    async def metrics(device=Depends(auth)):
        from .contracts import ToolCall

        return (await tools.run(ToolCall(tool_name="system.metrics"))).model_dump()

    @app.get("/v1/diagnostics")
    def diagnostics(device=Depends(admin)):
        return {
            "version": "0.1.0",
            "platform": platform.system(),
            "provider": settings.provider,
            "model": settings.effective_model,
            "time": datetime.now(UTC).isoformat(),
            "database_integrity": store.one("PRAGMA integrity_check"),
            "tasks": store.all("SELECT status,count(*) as count FROM tasks GROUP BY status"),
            "mcp": {
                "enabled": settings.mcp_enabled,
                "running": bool(mcp.process and mcp.process.returncode is None),
            },
        }

    return app
