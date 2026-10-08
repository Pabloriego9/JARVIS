import hashlib
import hmac
import json
import secrets
import time
from pathlib import Path
from urllib.parse import urlparse

from .contracts import ToolError
from .store import uid


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


class Security:
    def __init__(self, store, settings):
        self.store = store
        self.settings = settings

    def bootstrap(self):
        path = self.settings.data_dir / "admin.token"
        if path.exists():
            token = path.read_text().strip()
        else:
            token = secrets.token_urlsafe(48)
            with path.open("x", encoding="utf-8") as f:
                f.write(token)
            path.chmod(0o600)
        self.store.execute(
            "INSERT OR REPLACE INTO devices(id,name,token_hash,role,capabilities,expires,revoked) "
            "VALUES('local','Este servidor',?,'admin','[\"backend\"]',NULL,0)",
            (digest(token),),
        )

    def authenticate(self, token):
        device = self.store.one("SELECT * FROM devices WHERE token_hash=? AND revoked=0", (digest(token),))
        if not device or (device["expires"] and device["expires"] < time.time()):
            raise ToolError("unauthenticated", "Sesión vencida o dispositivo revocado.", "denied")
        return device

    def pairing(self):
        code = secrets.token_hex(5).upper()
        self.store.execute("INSERT INTO pairings VALUES(?,?,0)", (digest(code), time.time() + 180))
        return {"code": code, "expires_in": 180}

    def pair(self, code, name, capabilities):
        token, device_id = secrets.token_urlsafe(48), uid()
        with self.store.transaction() as db:
            c = db.execute(
                "DELETE FROM pairings WHERE code_hash=? AND expires>?", (digest(code.upper()), time.time())
            )
            if not c.rowcount:
                raise ToolError("pairing_invalid", "Código inválido, utilizado o vencido.", "denied")
            db.execute(
                "INSERT INTO devices VALUES(?,?,?,?,?,?,0)",
                (device_id, name, digest(token), "device", json.dumps(capabilities), time.time() + 86400),
            )
        return {"device_id": device_id, "token": token, "expires_in": 86400}

    def grant(self, body):
        resource = body.resource
        if body.kind == "folder":
            p = Path(resource).expanduser().resolve(strict=True)
            if not p.is_dir():
                raise ToolError("invalid_scope", "Seleccioná una carpeta existente.")
            resource = str(p)
        elif body.kind == "site":
            url = urlparse(resource)
            if url.scheme not in ("https", "http") or not url.hostname or url.username or url.password:
                raise ToolError("invalid_scope", "El permiso de sitio requiere un origen HTTP/HTTPS.")
            resource = f"{url.scheme}://{url.netloc}"
        grant_id = uid()
        self.store.execute(
            "INSERT INTO grants VALUES(?,?,?,?,?,?,0)",
            (grant_id, body.kind, resource, body.device_id, json.dumps(body.operations), body.mode),
        )
        self.store.event("grant_created", {"grant_id": grant_id, "kind": body.kind, "resource": resource})
        return self.store.one("SELECT * FROM grants WHERE id=?", (grant_id,))

    def folder(self, grant_id, relative, operation, device_id="local"):
        g = self.store.one("SELECT * FROM grants WHERE id=? AND revoked=0 AND kind='folder'", (grant_id,))
        if not g or g["device_id"] != device_id or operation not in json.loads(g["operations"]):
            raise ToolError(
                "permission_denied", "La carpeta no está autorizada para esta operación.", "denied"
            )
        if g["mode"] == "consult" and operation not in ("list", "read", "search", "document"):
            raise ToolError("consult_mode", "El modo consulta no permite modificar archivos.", "denied")
        root = Path(g["resource"]).resolve(strict=True)
        rel = Path(relative)
        if rel.is_absolute() or ".." in rel.parts:
            raise ToolError(
                "path_escape", "La ruta debe permanecer dentro de la carpeta autorizada.", "denied"
            )
        # Reject every symlink component, including a dangling link and the final component.
        p = root
        for component in rel.parts:
            p = p / component
            if p.is_symlink():
                raise ToolError(
                    "symlink_denied",
                    "Los enlaces requieren seleccionar la carpeta destino directamente.",
                    "denied",
                )
        resolved = p.resolve()
        if not resolved.is_relative_to(root):
            raise ToolError("path_escape", "La ruta sale del alcance autorizado.", "denied")
        # Internal backup/quarantine content is never part of the tool's file namespace.
        if any(part.startswith(".jarvis-") for part in rel.parts):
            raise ToolError("internal_path", "Ruta reservada para recuperación.", "denied")
        return resolved, g

    def approval_digest(self, task_id, device_id, call):
        data = {
            "task": task_id,
            "device": device_id,
            "tool": call.tool_name,
            "arguments": call.arguments,
            "version": call.expected_resource_version,
        }
        return digest(json.dumps(data, sort_keys=True, separators=(",", ":")))

    def request_approval(self, task_id, device_id, call):
        d = self.approval_digest(task_id, device_id, call)
        existing = self.store.one(
            "SELECT * FROM approvals WHERE task_id=? AND digest=? AND used=0 AND expires>?",
            (task_id, d, time.time()),
        )
        if existing:
            return existing["id"]
        aid = uid()
        self.store.execute(
            "INSERT INTO approvals VALUES(?,?,?,?,0,0,NULL)", (aid, task_id, d, time.time() + 300)
        )
        return aid

    def consume(self, approval_id, task_id, device_id, call):
        if not approval_id:
            return False
        d = self.approval_digest(task_id, device_id, call)
        with self.store.transaction() as db:
            row = db.execute(
                "SELECT * FROM approvals WHERE id=? AND task_id=? AND used=0 AND approved=1 AND expires>?",
                (approval_id, task_id, time.time()),
            ).fetchone()
            if not row or not hmac.compare_digest(d, row["digest"]):
                return False
            db.execute("UPDATE approvals SET used=1 WHERE id=?", (approval_id,))
            return True
