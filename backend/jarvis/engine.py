import asyncio
import json
import time

from .contracts import ToolCall, ToolError
from .providers import SYSTEM
from .remote import Remote
from .store import encode, uid
from .tools import READ_ONLY

TERMINAL = {"completed", "cancelled", "failed", "uncertain"}


class Engine:
    def __init__(self, store, settings, security, tools, provider):
        self.store, self.settings, self.security, self.tools, self.provider = (
            store,
            settings,
            security,
            tools,
            provider,
        )
        self.workers = {}
        self.budget_lock = asyncio.Lock()
        self.remote = Remote(store)

    def create(self, title, device_id, owner, actions, key, timeout=300, chat=None):
        existing = self.store.one("SELECT * FROM tasks WHERE owner=? AND idempotency_key=?", (owner, key))
        if existing:
            return existing["id"]
        task_id = uid()
        context = {
            "actions": [a.model_dump() for a in actions],
            "index": 0,
            "chat": chat,
            "tokens": 0,
            "rounds": 0,
        }
        now = time.time()
        self.store.execute(
            "INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?,?,?,NULL)",
            (task_id, title, device_id, owner, "pending", encode(context), now, now, now + timeout, key),
        )
        self.store.event("task_created", {"title": title, "device_id": device_id}, task_id)
        self.launch(task_id)
        return task_id

    def launch(self, task_id):
        if task_id not in self.workers or self.workers[task_id].done():
            self.workers[task_id] = asyncio.create_task(self.run(task_id))

    def set_state(self, task_id, status, context=None, error=None):
        if context is not None:
            self.store.execute(
                "UPDATE tasks SET context=?,updated=? WHERE id=?", (encode(context), time.time(), task_id)
            )
        self.store.execute(
            "UPDATE tasks SET status=?,error=?,updated=? WHERE id=?", (status, error, time.time(), task_id)
        )
        self.store.event("task_status", {"status": status, "message": error}, task_id)

    async def run(self, task_id):
        task = self.store.one("SELECT * FROM tasks WHERE id=?", (task_id,))
        if not task or task["status"] in TERMINAL:
            return
        context = json.loads(task["context"])
        try:
            self.set_state(task_id, "running")
            while True:
                current = self.store.one("SELECT status FROM tasks WHERE id=?", (task_id,))
                if current["status"] == "cancelled":
                    return
                if time.time() > task["deadline"]:
                    raise ToolError("deadline", "Venció el tiempo de la tarea. No se ejecutarán más pasos.")
                owner = self.store.one("SELECT revoked,expires FROM devices WHERE id=?", (task["owner"],))
                if not owner or owner["revoked"] or (owner["expires"] and owner["expires"] < time.time()):
                    raise ToolError(
                        "device_revoked",
                        "El dispositivo iniciador fue revocado o su sesión venció.",
                        "denied",
                    )
                if context["index"] < len(context["actions"]):
                    if context["index"] >= self.settings.max_steps:
                        raise ToolError("step_limit", "Se alcanzó el límite de pasos de la tarea.")
                    call = ToolCall.model_validate(context["actions"][context["index"]])
                    if task["device_id"] == "local":
                        self.tools.preflight(call, task["device_id"])
                    else:
                        self.remote.validate(call, task["device_id"])
                    if call.tool_name not in READ_ONLY:
                        if not self.security.consume(call.approval_id, task_id, task["device_id"], call):
                            aid = self.security.request_approval(task_id, task["device_id"], call)
                            context["actions"][context["index"]]["approval_id"] = aid
                            self.set_state(task_id, "awaiting_approval", context)
                            self.store.event(
                                "approval_required",
                                {
                                    "approval_id": aid,
                                    "tool": call.tool_name,
                                    "arguments": call.arguments,
                                    "expected_resource_version": call.expected_resource_version,
                                    "device_id": task["device_id"],
                                },
                                task_id,
                            )
                            return
                    step_id = uid()
                    self.store.execute(
                        "INSERT INTO steps VALUES(?,?,?,?,?,?,NULL)",
                        (
                            step_id,
                            task_id,
                            context["index"],
                            call.tool_name,
                            encode(call.arguments),
                            "running",
                        ),
                    )
                    result = (
                        await self.tools.run(call)
                        if task["device_id"] == "local"
                        else await self.remote.execute(task, call)
                    )
                    self.store.execute(
                        "UPDATE steps SET status=?,result=? WHERE id=?",
                        (result.status, result.model_dump_json(), step_id),
                    )
                    self.store.event(
                        "step_result", {"step": context["index"], "result": result.model_dump()}, task_id
                    )
                    context["index"] += 1
                    if context["chat"] and call.call_id:
                        context["chat"]["input"].append(
                            {
                                "type": "function_call_output",
                                "call_id": call.call_id,
                                "output": result.model_dump_json(),
                            }
                        )
                    self.set_state(task_id, "running", context)
                    if result.status != "completed":
                        self.set_state(
                            task_id,
                            result.status if result.status in TERMINAL else "failed",
                            context,
                            result.user_message,
                        )
                        return
                    continue
                if not context["chat"]:
                    self.set_state(task_id, "completed", context)
                    return
                if context["rounds"] >= self.settings.max_steps:
                    raise ToolError("step_limit", "Se alcanzó el límite de inferencias de la tarea.")
                self.set_state(task_id, "planning", context)
                response = await self.infer(task_id, context)
                context["rounds"] += 1
                context["chat"]["input"].extend(response["output"])
                if response["text"]:
                    self.store.execute(
                        "INSERT INTO messages VALUES(?,?,?,?,?)",
                        (
                            uid(),
                            context["chat"]["conversation_id"],
                            "assistant",
                            response["text"],
                            time.time(),
                        ),
                    )
                    self.store.event(
                        "message", {"text": response["text"], "model": response["model"]}, task_id
                    )
                calls = []
                for raw in response["calls"]:
                    data = json.loads(raw["arguments"])
                    calls.append(
                        ToolCall(
                            tool_name=raw["name"].replace("__", "."),
                            arguments=data["arguments"],
                            expected_resource_version=data.get("expected_resource_version"),
                            call_id=raw["call_id"],
                        )
                    )
                context["actions"].extend(c.model_dump() for c in calls)
                self.set_state(task_id, "running", context)
                if not calls:
                    self.set_state(task_id, "completed", context)
                    return
        except asyncio.CancelledError:
            # A dispatched external effect might finish; distinguish it from an undispatched cancellation.
            active = self.store.one("SELECT id FROM steps WHERE task_id=? AND status='running'", (task_id,))
            self.set_state(
                task_id,
                "uncertain" if active else "cancelled",
                context,
                "Detenido. Revisá efectos ya iniciados." if active else None,
            )
        except ToolError as error:
            self.store.event("error", error.result.model_dump(), task_id)
            self.set_state(
                task_id, "uncertain" if error.result.status == "uncertain" else "failed", context, str(error)
            )
        except Exception as error:
            # Exceptions from side-effecting executors cannot be blindly classified as retryable.
            active = self.store.one("SELECT id FROM steps WHERE task_id=? AND status='running'", (task_id,))
            self.store.event(
                "error",
                {"code": type(error).__name__, "message": "Fallo interno; consultá el diagnóstico."},
                task_id,
            )
            self.set_state(task_id, "uncertain" if active else "failed", context, type(error).__name__)

    async def infer(self, task_id, context):
        async def delta(text):
            self.store.event("text_delta", {"text": text}, task_id)

        async with self.budget_lock:
            now = time.time()
            today = now - now % 86400
            used = self.store.one(
                "SELECT COALESCE(SUM(tokens),0) AS total FROM usage WHERE created>=?", (today,)
            )["total"]
            # UTF-8 byte count deliberately overestimates tokenized input, including tool schemas.
            estimated_input = (
                len(
                    encode(
                        {
                            "input": context["chat"]["input"],
                            "tools": self.tools.schemas(),
                            "instructions": SYSTEM,
                        }
                    ).encode("utf-8")
                )
                + 512
            )
            reservation = estimated_input + self.settings.max_output
            if (
                used + reservation > self.settings.daily_tokens
                or context["tokens"] + reservation > self.settings.task_tokens
            ):
                raise ToolError(
                    "budget_limit", "La próxima solicitud superaría el presupuesto de tokens configurado."
                )
            # Reserve before contacting provider; keep an estimate if the stream is interrupted.
            usage_id = uid()
            self.store.execute(
                "INSERT INTO usage VALUES(?,?,?,?,?,?,?)",
                (
                    usage_id,
                    task_id,
                    self.settings.provider,
                    self.settings.effective_model,
                    reservation,
                    1,
                    now,
                ),
            )
            response = await self.provider.respond(context["chat"]["input"], self.tools.schemas(), delta)
            tokens = response["usage"].get("total_tokens")
            if tokens is not None:
                self.store.execute(
                    "UPDATE usage SET tokens=?,estimated=0,model=? WHERE id=?",
                    (tokens, response["model"], usage_id),
                )
            context["tokens"] += tokens if tokens is not None else reservation
            self.store.event(
                "usage",
                {"tokens": tokens or reservation, "estimated": tokens is None, "model": response["model"]},
                task_id,
            )
            return response

    def cancel(self, task_id):
        task = self.store.one("SELECT status FROM tasks WHERE id=?", (task_id,))
        if task and task["status"] not in TERMINAL:
            self.set_state(task_id, "cancelled")
            self.store.execute("UPDATE approvals SET used=1 WHERE task_id=?", (task_id,))
            worker = self.workers.get(task_id)
            if worker and not worker.done():
                worker.cancel()

    async def close(self):
        for worker in self.workers.values():
            if not worker.done():
                worker.cancel()
        await asyncio.gather(*self.workers.values(), return_exceptions=True)
