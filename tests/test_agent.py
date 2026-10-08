import json
import time

from fastapi.testclient import TestClient
from jarvis.app import create_app
from jarvis.config import Settings


class ToolProvider:
    def __init__(self):
        self.count = 0
        self.received = []

    async def respond(self, inputs, tools, on_delta):
        self.received.append(list(inputs))
        self.count += 1
        if self.count == 1:
            call = {
                "type": "function_call",
                "name": "memory__save",
                "call_id": "call_1",
                "arguments": json.dumps({"arguments": {"content": "Proyecto Egiverso3D", "kind": "project"}}),
            }
            return {
                "text": "",
                "calls": [call],
                "output": [call],
                "model": "gpt-6-astra",
                "usage": {"total_tokens": 25},
            }
        return {
            "text": "Guardé el proyecto.",
            "calls": [],
            "output": [{"role": "assistant", "content": "Guardé el proyecto."}],
            "model": "gpt-6-astra",
            "usage": {"total_tokens": 30},
        }

    async def close(self):
        pass


def wait(client, task, status):
    for _ in range(200):
        row = client.get("/v1/tasks/" + task).json()
        if row["status"] == status:
            return row
        time.sleep(0.01)
    raise AssertionError(row)


def test_agent_resumes_after_exact_approval_with_observation(tmp_path):
    provider = ToolProvider()
    app = create_app(Settings(data_dir=tmp_path), provider)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + (tmp_path / "admin.token").read_text()
        task = client.post(
            "/v1/chat", json={"message": "Recordá mi proyecto Egiverso3D", "idempotency_key": "agent-test-1"}
        ).json()["task_id"]
        row = wait(client, task, "awaiting_approval")
        assert client.get("/v1/memories").json() == []
        assert provider.count == 1
        client.post("/v1/approvals/" + row["actions"][0]["approval_id"])
        wait(client, task, "completed")
        assert client.get("/v1/memories").json()[0]["content"] == "Proyecto Egiverso3D"
        observations = [i for i in provider.received[1] if i.get("type") == "function_call_output"]
        assert json.loads(observations[0]["output"])["status"] == "completed"
        assert sum(r["tokens"] for r in client.get("/v1/usage").json()["records"]) == 55


def test_budget_stops_before_contacting_provider(tmp_path):
    provider = ToolProvider()
    app = create_app(Settings(data_dir=tmp_path, daily_tokens=100), provider)
    with TestClient(app) as client:
        client.headers["Authorization"] = "Bearer " + (tmp_path / "admin.token").read_text()
        task = client.post("/v1/chat", json={"message": "Hola", "idempotency_key": "budget-test"}).json()[
            "task_id"
        ]
        row = wait(client, task, "failed")
        assert "presupuesto" in row["error"]
        assert provider.count == 0


def test_cancel_multistep_keeps_completed_effect_and_blocks_next(client):
    task = client.post(
        "/v1/tasks",
        json={
            "title": "Dos recuerdos",
            "idempotency_key": "two-effects",
            "actions": [
                {"tool_name": "memory.save", "arguments": {"content": "primero", "kind": "fact"}},
                {"tool_name": "memory.save", "arguments": {"content": "segundo", "kind": "fact"}},
            ],
        },
    ).json()["task_id"]
    row = wait(client, task, "awaiting_approval")
    client.post("/v1/approvals/" + row["actions"][0]["approval_id"])
    for _ in range(200):
        row = client.get("/v1/tasks/" + task).json()
        if row["index"] == 1 and row["status"] == "awaiting_approval":
            break
        time.sleep(0.01)
    assert row["index"] == 1
    client.post("/v1/tasks/" + task + "/cancel")
    wait(client, task, "cancelled")
    assert [m["content"] for m in client.get("/v1/memories").json()] == ["primero"]
    assert client.post("/v1/approvals/" + row["actions"][1]["approval_id"]).status_code == 409
