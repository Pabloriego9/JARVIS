import json
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .contracts import ToolError


def uid():
    return str(uuid.uuid4())


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


SCHEMA = """
CREATE TABLE IF NOT EXISTS migrations(version INTEGER PRIMARY KEY, applied_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS devices(id TEXT PRIMARY KEY, name TEXT NOT NULL, token_hash TEXT UNIQUE,
 role TEXT NOT NULL, capabilities TEXT NOT NULL DEFAULT '[]', expires REAL, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS pairings(code_hash TEXT PRIMARY KEY, expires REAL NOT NULL, attempts INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS memories(id TEXT PRIMARY KEY, content TEXT NOT NULL, kind TEXT NOT NULL,
 source TEXT NOT NULL, device_id TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
 deleted INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL);
CREATE INDEX IF NOT EXISTS memory_updated ON memories(updated);
CREATE TABLE IF NOT EXISTS conversations(id TEXT PRIMARY KEY, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
 role TEXT NOT NULL, content TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS grants(id TEXT PRIMARY KEY, kind TEXT NOT NULL, resource TEXT NOT NULL,
 device_id TEXT NOT NULL, operations TEXT NOT NULL, mode TEXT NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, title TEXT NOT NULL, device_id TEXT NOT NULL,
 owner TEXT NOT NULL, status TEXT NOT NULL, context TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
 deadline REAL NOT NULL, idempotency_key TEXT NOT NULL, error TEXT, UNIQUE(owner,idempotency_key));
CREATE TABLE IF NOT EXISTS steps(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
 position INTEGER NOT NULL, tool TEXT NOT NULL, arguments TEXT NOT NULL, status TEXT NOT NULL,
 result TEXT, UNIQUE(task_id,position));
CREATE TABLE IF NOT EXISTS approvals(id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(id),
 digest TEXT NOT NULL, expires REAL NOT NULL, approved INTEGER NOT NULL DEFAULT 0,
 used INTEGER NOT NULL DEFAULT 0, actor TEXT);
CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT, kind TEXT NOT NULL,
 data TEXT NOT NULL, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS usage(id TEXT PRIMARY KEY, task_id TEXT, provider TEXT NOT NULL,
 model TEXT NOT NULL, tokens INTEGER NOT NULL, estimated INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL);
CREATE TABLE IF NOT EXISTS reminders(id TEXT PRIMARY KEY, title TEXT NOT NULL, due REAL NOT NULL,
 timezone TEXT NOT NULL, interval_seconds INTEGER, last_fired REAL, enabled INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS integrations(id TEXT PRIMARY KEY, config TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS sync_revisions(id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, device_id TEXT NOT NULL,
 base_revision INTEGER NOT NULL, content TEXT NOT NULL, created REAL NOT NULL, resolved INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS trash(id TEXT PRIMARY KEY, original TEXT NOT NULL, stored TEXT NOT NULL,
 grant_id TEXT NOT NULL, hash TEXT NOT NULL, created REAL NOT NULL);
"""


class Store:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.db.execute("INSERT OR IGNORE INTO migrations VALUES(1,?)", (time.time(),))

    def close(self):
        self.db.close()

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def execute(self, sql, args=()):
        with self.lock:
            return self.db.execute(sql, args)

    def all(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def one(self, sql, args=()):
        with self.lock:
            row = self.db.execute(sql, args).fetchone()
            return dict(row) if row else None

    def event(self, kind, data, task_id=None):
        self.execute(
            "INSERT INTO events(task_id,kind,data,created) VALUES(?,?,?,?)",
            (task_id, kind, encode(data), time.time()),
        )

    def memories(self, query=""):
        return self.all(
            "SELECT * FROM memories WHERE deleted=0 AND instr(lower(content),lower(?))>0 "
            "ORDER BY updated DESC LIMIT 100",
            (query,),
        )

    def memory_write(self, content, kind, device_id, memory_id=None, revision=None):
        now = time.time()
        with self.transaction() as db:
            if memory_id:
                if revision is None:
                    raise ToolError("revision_required", "Falta la revisión de la memoria.", "denied")
                cursor = db.execute(
                    "UPDATE memories SET content=?,kind=?,revision=revision+1,updated=? "
                    "WHERE id=? AND revision=? AND deleted=0",
                    (content, kind, now, memory_id, revision),
                )
                if not cursor.rowcount:
                    raise ToolError(
                        "revision_conflict", "El recuerdo cambió o fue eliminado. Revisá la versión actual."
                    )
            else:
                memory_id = uid()
                db.execute(
                    "INSERT INTO memories VALUES(?,?,?,?,?,1,0,?,?)",
                    (memory_id, content, kind, "explicit", device_id, now, now),
                )
        return self.one("SELECT * FROM memories WHERE id=?", (memory_id,))

    def memory_delete(self, memory_id, revision):
        c = self.execute(
            "UPDATE memories SET content='',deleted=1,revision=revision+1,updated=? "
            "WHERE id=? AND revision=? AND deleted=0",
            (time.time(), memory_id, revision),
        )
        if not c.rowcount:
            raise ToolError("revision_conflict", "El recuerdo cambió o ya se eliminó.")
        # No retained memory content in active conflict copies after erasure.
        self.execute("DELETE FROM sync_revisions WHERE entity_id=?", (memory_id,))

    def backup(self, path):
        with self.lock, sqlite3.connect(path) as dest:
            self.db.backup(dest)

    def recover(self):
        # Never replay an effect whose outcome was not durably recorded.
        for row in self.all("SELECT id FROM tasks WHERE status IN ('running','planning')"):
            self.execute(
                "UPDATE tasks SET status='uncertain',error=?,updated=? WHERE id=?",
                (
                    "Proceso interrumpido. Inspeccioná los efectos antes de volver a ejecutar.",
                    time.time(),
                    row["id"],
                ),
            )
            self.event("recovery_required", {"status": "uncertain"}, row["id"])
