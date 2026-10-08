import time

from jarvis.contracts import ToolResult


def test_remote_destination_dedup_and_revocation(client):
    code = client.post("/v1/pairing").json()["code"]
    phone = client.post(
        "/v1/pair", json={"code": code, "name": "Mi teléfono", "capabilities": ["files.saf"]}
    ).json()
    headers = {"Authorization": "Bearer " + phone["token"]}
    task = client.post(
        "/v1/tasks",
        json={
            "title": "Batería del teléfono",
            "device_id": phone["device_id"],
            "idempotency_key": "remote-metrics-1",
            "actions": [{"tool_name": "system.metrics", "arguments": {}}],
        },
    ).json()["task_id"]
    envelope = None
    for _ in range(50):
        requests = client.post("/v1/executor/poll", headers=headers).json()
        if requests:
            envelope = requests[0]
            break
        time.sleep(0.02)
    assert envelope and envelope["device_id"] == phone["device_id"]
    assert envelope["task_id"] == task and envelope["deadline"] > time.time()
    assert client.post("/v1/executor/poll", headers=headers).json() == []
    result = ToolResult(data={"battery_percent": 51}).model_dump()
    url = "/v1/executor/results/" + envelope["request_id"]
    assert client.post(url, json=result).status_code == 403  # wrong destination identity
    assert client.post(url, json=result, headers=headers).status_code == 200
    assert (
        client.post(url, json=result, headers=headers).status_code == 200
    )  # result retry only, no action replay
    changed = ToolResult(data={"battery_percent": 12}).model_dump()
    assert client.post(url, json=changed, headers=headers).status_code == 409
    for _ in range(50):
        row = client.get(f"/v1/tasks/{task}").json()
        if row["status"] == "completed":
            break
        time.sleep(0.02)
    assert row["status"] == "completed"
    client.delete("/v1/devices/" + phone["device_id"])
    assert client.post("/v1/executor/poll", headers=headers).status_code == 401
