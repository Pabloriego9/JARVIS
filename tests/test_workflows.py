import hashlib
import time

import pytest
from cryptography.fernet import InvalidToken
from jarvis.app import fire_reminders
from jarvis.backup import export_backup, restore_backup
from jarvis.contracts import ToolCall, ToolError
from jarvis.store import Store


def wait_task(client, task_id, expected=None):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        task = client.get(f"/v1/tasks/{task_id}").json()
        if expected and task["status"] == expected:
            return task
        if not expected and task["status"] in (
            "completed",
            "failed",
            "uncertain",
            "awaiting_approval",
            "cancelled",
        ):
            return task
        time.sleep(0.02)
    raise AssertionError(task)


def grant(client, folder):
    r = client.post(
        "/v1/grants",
        json={
            "resource": str(folder),
            "operations": [
                "list",
                "search",
                "read",
                "write",
                "mkdir",
                "copy",
                "move",
                "trash",
                "restore",
                "document",
            ],
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def task(client, name, arguments, version=None, key=None):
    r = client.post(
        "/v1/tasks",
        json={
            "title": name,
            "actions": [{"tool_name": name, "arguments": arguments, "expected_resource_version": version}],
            "idempotency_key": key or str(time.time_ns()),
        },
    )
    assert r.status_code == 200, r.text
    return r.json()["task_id"]


def approve(client, task_id):
    row = wait_task(client, task_id, "awaiting_approval")
    aid = row["actions"][row["index"]]["approval_id"]
    r = client.post(f"/v1/approvals/{aid}")
    assert r.status_code == 200, r.text
    return wait_task(client, task_id, "completed")


def test_auth_health_and_missing_credentials(client):
    assert client.get("/health").json()["status"] == "ok"
    assert client.get("/v1/memories", headers={"Authorization": ""}).status_code == 401
    result = client.post("/v1/chat", json={"message": "Hola", "idempotency_key": "first-chat"})
    row = wait_task(client, result.json()["task_id"])
    assert row["status"] == "failed"
    assert "JARVIS_OPENAI_API_KEY" in row["error"]
    assert client.get("/v1/status").json()["model"] == "gpt-6-astra"


def test_memory_restart_correction_forgetting_and_sync(client, app):
    m = client.post("/v1/memories", json={"content": "Mi proyecto es Egiverso3D", "kind": "project"}).json()
    second = Store(app.state.store.path)
    assert second.memories("Egiverso3D")[0]["id"] == m["id"]
    second.close()
    edited = client.put(
        f"/v1/memories/{m['id']}",
        json={"content": "Egiverso3D fabrica modelos", "kind": "project", "expected_revision": 1},
    )
    assert edited.json()["revision"] == 2
    conflict = client.put(
        f"/v1/memories/{m['id']}", json={"content": "versión vieja", "expected_revision": 1}
    )
    assert conflict.status_code == 409
    assert client.delete(f"/v1/memories/{m['id']}?revision=2").status_code == 200
    assert client.get("/v1/memories?q=Egiverso3D").json() == []
    tombstone = client.get("/v1/sync/memories").json()["changes"][0]
    assert tombstone["deleted"] and tombstone["content"] == ""
    assert (
        client.put(
            f"/v1/memories/{m['id']}", json={"content": "resurrección", "expected_revision": 3}
        ).status_code
        == 409
    )


def test_file_lifecycle_with_hash_and_recovery(client, tmp_path):
    folder = tmp_path / "files"
    folder.mkdir()
    gid = grant(client, folder)
    args = {"grant_id": gid, "path": "note.md", "content": "Hola Jarvis"}
    tid = task(client, "files.write", args)
    wait_task(client, tid, "awaiting_approval")
    assert not (folder / "note.md").exists()
    approve(client, tid)
    sha = hashlib.sha256(b"Hola Jarvis").hexdigest()
    tid = task(client, "files.copy", {"grant_id": gid, "path": "note.md", "destination": "copy.md"}, sha)
    approve(client, tid)
    assert (folder / "copy.md").read_text() == "Hola Jarvis"
    tid = task(client, "files.move", {"grant_id": gid, "path": "copy.md", "destination": "moved.md"}, sha)
    approve(client, tid)
    assert not (folder / "copy.md").exists()
    tid = task(client, "files.trash", {"grant_id": gid, "path": "moved.md"}, sha)
    approve(client, tid)
    assert not (folder / "moved.md").exists()
    import json

    result = json.loads(client.get(f"/v1/tasks/{tid}").json()["steps"][0]["result"])
    tid = task(
        client, "files.restore", {"grant_id": gid, "path": "moved.md", "trash_id": result["data"]["trash_id"]}
    )
    approve(client, tid)
    assert (folder / "moved.md").read_text() == "Hola Jarvis"


def test_change_after_preview_and_revoked_scope(client, tmp_path):
    folder = tmp_path / "files"
    folder.mkdir()
    path = folder / "a.txt"
    path.write_text("before")
    gid = grant(client, folder)
    tid = task(
        client,
        "files.write",
        {"grant_id": gid, "path": "a.txt", "content": "after"},
        hashlib.sha256(b"before").hexdigest(),
    )
    row = wait_task(client, tid, "awaiting_approval")
    path.write_text("external edit")
    client.post(f"/v1/approvals/{row['actions'][0]['approval_id']}")
    assert wait_task(client, tid, "failed")["status"] == "failed"
    assert path.read_text() == "external edit"
    client.delete(f"/v1/grants/{gid}")
    tid = task(client, "files.read", {"grant_id": gid, "path": "a.txt"})
    assert wait_task(client, tid)["status"] == "failed"


@pytest.mark.parametrize("path", ["../secret", "/etc/passwd", ".jarvis-recovery/id"])
def test_scope_escape_denied(client, tmp_path, path):
    gid = grant(client, tmp_path)
    tid = task(client, "files.read", {"grant_id": gid, "path": path})
    assert wait_task(client, tid)["status"] == "failed"


def test_symlink_and_collision_preserve_original(client, tmp_path):
    folder = tmp_path / "granted"
    folder.mkdir()
    outside = tmp_path / "outside"
    outside.write_text("private")
    (folder / "link").symlink_to(outside)
    gid = grant(client, folder)
    tid = task(client, "files.read", {"grant_id": gid, "path": "link"})
    assert wait_task(client, tid)["status"] == "failed"
    (folder / "source").write_text("source")
    (folder / "dest").write_text("dest")
    tid = task(
        client,
        "files.copy",
        {"grant_id": gid, "path": "source", "destination": "dest"},
        hashlib.sha256(b"source").hexdigest(),
    )
    row = wait_task(client, tid, "awaiting_approval")
    client.post(f"/v1/approvals/{row['actions'][0]['approval_id']}")
    assert wait_task(client, tid)["status"] == "failed"
    assert (folder / "dest").read_text() == "dest"


def test_idempotency_and_cancel_before_effect(client, tmp_path):
    gid = grant(client, tmp_path)
    args = {"grant_id": gid, "path": "no.txt", "content": "never"}
    first = task(client, "files.write", args, key="same-key-123")
    second = task(client, "files.write", args, key="same-key-123")
    assert first == second
    row = wait_task(client, first, "awaiting_approval")
    client.post(f"/v1/tasks/{first}/cancel")
    assert client.post(f"/v1/approvals/{row['actions'][0]['approval_id']}").status_code == 409
    assert not (tmp_path / "no.txt").exists()


def test_pairing_one_use_expiry_and_revocation(client, app):
    code = client.post("/v1/pairing").json()["code"]
    data = {"code": code, "name": "Android", "capabilities": ["files.saf"]}
    paired = client.post("/v1/pair", json=data).json()
    assert client.post("/v1/pair", json=data).status_code == 403
    headers = {"Authorization": f"Bearer {paired['token']}"}
    assert client.get("/v1/status", headers=headers).status_code == 200
    assert client.post("/v1/pairing", headers=headers).status_code == 403
    client.delete(f"/v1/devices/{paired['device_id']}")
    assert client.get("/v1/status", headers=headers).status_code == 401


def test_approval_is_bound_to_arguments_and_single_use(client, app):
    c = ToolCall(tool_name="memory.save", arguments={"content": "x", "kind": "fact"})
    tid = task(client, c.tool_name, c.arguments)
    row = wait_task(client, tid, "awaiting_approval")
    aid = row["actions"][0]["approval_id"]
    app.state.store.execute("UPDATE approvals SET approved=1 WHERE id=?", (aid,))
    changed = c.model_copy(update={"arguments": {"content": "changed", "kind": "fact"}})
    assert not app.state.security.consume(aid, tid, "local", changed)
    assert not app.state.security.consume(aid, tid, "other-device", c)
    assert app.state.security.consume(aid, tid, "local", c)
    assert not app.state.security.consume(aid, tid, "local", c)


def test_backup_restore_encryption_and_integrity(client, app, tmp_path):
    client.post("/v1/memories", json={"content": "persistente"})
    payload = export_backup(app.state.store, "una frase segura de prueba")
    assert b"persistente" not in payload
    with pytest.raises(InvalidToken):
        restore_backup(payload, "contraseña incorrecta", tmp_path / "bad.sqlite3")
    target = tmp_path / "restore.sqlite3"
    restore_backup(payload, "una frase segura de prueba", target)
    restored = Store(target)
    assert restored.memories()[0]["content"] == "persistente"
    assert restored.one("SELECT revoked FROM devices WHERE id='local'")["revoked"]
    restored.close()


def test_reminders_timezone_restart_and_dedup(client, app):
    body = {
        "title": "Revisar impresión",
        "due_at": "2026-10-07T15:00:00-03:00",
        "timezone": "America/Argentina/Buenos_Aires",
        "interval_seconds": 3600,
    }
    rid = client.post("/v1/reminders", json=body).json()["id"]
    due = app.state.store.one("SELECT due FROM reminders WHERE id=?", (rid,))["due"]
    fire_reminders(app.state.store, due + 1)
    fire_reminders(app.state.store, due + 2)
    rows = app.state.store.all("SELECT * FROM events WHERE kind='reminder'")
    assert len(rows) == 1
    assert app.state.store.one("SELECT due FROM reminders WHERE id=?", (rid,))["due"] == due + 3600


def test_recovery_marks_inflight_uncertain(client, app):
    tid = task(client, "memory.search", {})
    wait_task(client, tid, "completed")
    app.state.store.execute("UPDATE tasks SET status='running' WHERE id=?", (tid,))
    app.state.store.recover()
    assert client.get(f"/v1/tasks/{tid}").json()["status"] == "uncertain"


def test_browser_permission_rejects_script_and_foreign_url(client, app):
    g = client.post(
        "/v1/grants",
        json={
            "kind": "site",
            "resource": "https://example.com",
            "operations": ["new_page", "evaluate_script"],
        },
    ).json()["id"]
    for name, args in [
        ("new_page", {"url": "https://evil.example"}),
        ("evaluate_script", {"function": "alert(1)"}),
    ]:
        with pytest.raises(ToolError):
            app.state.tools.preflight(
                ToolCall(
                    tool_name="browser.call", arguments={"site_grant_id": g, "name": name, "arguments": args}
                ),
                "local",
            )
