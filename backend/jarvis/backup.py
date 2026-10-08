import base64
import os
import sqlite3
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

MAGIC = b"JARVIS-BACKUP-1\n"


def cipher(password, salt):
    if len(password) < 12:
        raise ValueError("Usá una frase de al menos 12 caracteres.")
    key = Scrypt(salt=salt, length=32, n=2**15, r=8, p=1).derive(password.encode())
    return Fernet(base64.urlsafe_b64encode(key))


def export_backup(store, password):
    salt = os.urandom(16)
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp) / "backup.sqlite3"
        store.backup(path)
        payload = path.read_bytes()
    return MAGIC + salt + cipher(password, salt).encrypt(payload)


def restore_backup(payload, password, target):
    if not payload.startswith(MAGIC):
        raise ValueError("Formato de copia inválido.")
    salt = payload[len(MAGIC) : len(MAGIC) + 16]
    data = cipher(password, salt).decrypt(payload[len(MAGIC) + 16 :])
    target = Path(target)
    if target.exists():
        raise FileExistsError("Restaurá en un directorio nuevo; no se sobrescribe una base existente.")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=target.parent) as temp:
        test = Path(temp) / "restored.sqlite3"
        test.write_bytes(data)
        with sqlite3.connect(test) as db:
            if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("La base recuperada no pasó la comprobación de integridad.")
            db.execute("UPDATE devices SET revoked=1")
            db.execute("UPDATE approvals SET used=1")
            db.execute("DELETE FROM pairings")
            db.execute(
                "UPDATE tasks SET status='uncertain' WHERE status NOT IN ('completed','failed','cancelled','uncertain')"
            )
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        db.execute("PRAGMA journal_mode=DELETE")
        db.close()
        os.replace(test, target)
