import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from .contracts import ToolError, ToolResult
from .store import uid

MAX_FILE = 10 * 1024 * 1024


def file_hash(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def metadata(path, root):
    s = path.stat()
    return {
        "path": str(path.relative_to(root)),
        "name": path.name,
        "directory": path.is_dir(),
        "size": s.st_size,
        "modified": s.st_mtime,
        "version": file_hash(path) if path.is_file() and s.st_size <= MAX_FILE else None,
    }


class Files:
    def __init__(self, store, security):
        self.store, self.security = store, security

    def run(self, operation, args, version=None):
        path, grant = self.security.folder(args["grant_id"], args.get("path", "."), operation)
        root = Path(grant["resource"])
        if operation == "list":
            if not path.is_dir():
                raise ToolError("not_directory", "La ruta no es una carpeta.")
            rows = [
                metadata(p, root)
                for p in sorted(path.iterdir())
                if not p.is_symlink() and not p.name.startswith(".jarvis-")
            ][:500]
            return ToolResult(data=rows)
        if operation == "search":
            result, examined = [], 0
            for base, dirs, names in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs if not d.startswith(".jarvis-") and not (Path(base) / d).is_symlink()
                ]
                for name in names:
                    examined += 1
                    p = Path(base) / name
                    if p.is_symlink() or name.startswith(".jarvis-"):
                        continue
                    stat = p.stat()
                    if (
                        args.get("query", "").casefold() in name.casefold()
                        and stat.st_size >= args.get("min_size", 0)
                        and stat.st_size <= args.get("max_size", 2**63)
                    ):
                        if args.get("content"):
                            if stat.st_size > MAX_FILE:
                                continue
                            try:
                                if args["content"].casefold() not in p.read_text().casefold():
                                    continue
                            except (UnicodeError, OSError):
                                continue
                        result.append(metadata(p, root))
                    if len(result) >= 200 or examined >= 10000:
                        return ToolResult(data={"items": result, "partial": True, "examined": examined})
            return ToolResult(data={"items": result, "partial": False, "examined": examined})
        if operation in ("read", "document"):
            self.check_size(path)
            if operation == "document":
                return self.document(path)
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeError:
                raise ToolError(
                    "binary_file", "Este archivo no es texto UTF-8. Usá un extractor compatible."
                ) from None
            return ToolResult(
                data={"content": content, "path": args["path"]}, resource_version=file_hash(path)
            )
        if path == root:
            raise ToolError("root_protected", "No se puede modificar la carpeta raíz del permiso.", "denied")
        if operation == "mkdir":
            path.mkdir(exist_ok=False)
            return ToolResult(
                data={"path": args["path"]}, evidence=[{"exists": path.is_dir()}], side_effects=["created"]
            )
        if operation == "write":
            content = args["content"].encode("utf-8")
            if len(content) > MAX_FILE:
                raise ToolError("file_too_large", "Se supera el límite de edición de 10 MiB.")
            if path.suffix.lower() == ".json":
                json.loads(args["content"])
            if path.suffix.lower() == ".csv":
                list(csv.reader(io.StringIO(args["content"]), strict=True))
            backup = None
            if path.exists():
                self.check_version(path, version)
                backup = self.preserve(path, root, grant["id"], remove=False)
                self.check_version(path, version)
            elif version:
                raise ToolError("version_conflict", "El archivo original ya no existe.")
            self.atomic_write(path, content, replace=path.exists())
            return ToolResult(
                data={"path": args["path"], "backup_id": backup},
                resource_version=file_hash(path),
                evidence=[{"sha256": file_hash(path), "bytes": path.stat().st_size}],
                side_effects=["written"],
            )
        if operation in ("copy", "move"):
            self.check_size(path)
            self.check_version(path, version)
            target, _ = self.security.folder(
                args.get("destination_grant_id", args["grant_id"]), args["destination"], operation
            )
            if target.exists():
                raise ToolError("collision", "El destino ya existe. Elegí otro nombre o cancelá.")
            original_hash = file_hash(path)
            self.atomic_write(target, path.read_bytes(), replace=False)
            if file_hash(target) != original_hash:
                raise ToolError("integrity_error", "La copia no coincide con el original.")
            if operation == "move":
                # Revalidate source so that concurrent external changes cannot be silently deleted.
                self.check_version(path, original_hash)
                path.unlink()
            return ToolResult(
                data={"destination": args["destination"]},
                resource_version=original_hash,
                evidence=[{"sha256": original_hash, "destination_exists": target.exists()}],
                side_effects=[operation],
            )
        if operation == "trash":
            self.check_size(path)
            self.check_version(path, version)
            trash_id = self.preserve(path, root, grant["id"], remove=True)
            return ToolResult(
                data={"trash_id": trash_id},
                evidence=[{"original_exists": path.exists()}],
                side_effects=["quarantined"],
            )
        if operation == "restore":
            item = self.store.one(
                "SELECT * FROM trash WHERE id=? AND grant_id=?", (args["trash_id"], grant["id"])
            )
            if not item or str(path) != item["original"]:
                raise ToolError("trash_missing", "No existe una copia para esta ruta y permiso.")
            stored = Path(item["stored"])
            if path.exists():
                raise ToolError("collision", "El destino existe; no se sobrescribió.")
            if file_hash(stored) != item["hash"]:
                raise ToolError("integrity_error", "La copia recuperable no pasó la verificación.")
            self.atomic_write(path, stored.read_bytes(), replace=False)
            return ToolResult(
                data={"path": str(path)}, resource_version=file_hash(path), side_effects=["restored"]
            )
        raise ToolError("unsupported", "Operación no disponible.", "unsupported")

    @staticmethod
    def check_size(path):
        if not path.is_file():
            raise ToolError(
                "not_file", "Seleccioná un archivo. Las operaciones de carpetas completas son manuales."
            )
        if path.stat().st_size > MAX_FILE:
            raise ToolError("file_too_large", "Límite actual: 10 MiB por archivo.")

    @staticmethod
    def check_version(path, expected):
        if not expected or not path.is_file() or file_hash(path) != expected:
            raise ToolError(
                "version_conflict", "El archivo cambió o falta su hash. Revisá una nueva vista previa."
            )

    def preserve(self, path, root, grant_id, remove):
        folder = root / ".jarvis-recovery"
        if folder.is_symlink():
            raise ToolError("symlink_denied", "La carpeta de recuperación no puede ser un enlace.", "denied")
        folder.mkdir(mode=0o700, exist_ok=True)
        item = uid()
        target = folder / item
        sha = file_hash(path)
        shutil.copy2(path, target)
        if file_hash(target) != sha:
            raise ToolError("integrity_error", "No se pudo verificar la copia. Original conservado.")
        self.store.execute(
            "INSERT INTO trash VALUES(?,?,?,?,?,?)",
            (item, str(path), str(target), grant_id, sha, time.time()),
        )
        if remove:
            self.check_version(path, sha)
            path.unlink()
        return item

    @staticmethod
    def atomic_write(path, data, replace):
        fd, tmp = tempfile.mkstemp(prefix=".jarvis-write-", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())
            if replace:
                os.replace(tmp, path)
            else:
                # Link is exclusive: fail instead of clobbering a file created after the preview.
                os.link(tmp, path)
        finally:
            Path(tmp).unlink(missing_ok=True)

    def document(self, path):
        suffix = path.suffix.lower()
        chunks, partial = [], False
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(path)
            partial = len(reader.pages) > 50
            chunks = [
                {"location": f"página {i + 1}", "text": p.extract_text()[:20000]}
                for i, p in enumerate(reader.pages[:50])
            ]
        elif suffix == ".docx":
            from docx import Document

            paragraphs = Document(path).paragraphs
            partial = len(paragraphs) > 500
            chunks = [
                {"location": f"párrafo {i + 1}", "text": p.text[:10000]}
                for i, p in enumerate(paragraphs[:500])
            ]
        elif suffix in (".txt", ".md", ".json", ".csv", ".log", ".dart", ".py", ".cs", ".kt"):
            lines = path.read_text(encoding="utf-8").splitlines()
            partial = len(lines) > 1000
            chunks = [{"location": f"línea {i + 1}", "text": t[:4000]} for i, t in enumerate(lines[:1000])]
        else:
            raise ToolError(
                "format_unsupported", "Formato sin extractor. PDF, DOCX y texto disponibles.", "unsupported"
            )
        total, limited = 0, []
        for chunk in chunks:
            if total + len(chunk["text"]) > 60000:
                partial = True
                break
            limited.append(chunk)
            total += len(chunk["text"])
        return ToolResult(
            data={
                "file": path.name,
                "chunks": limited,
                "partial": partial,
                "source_trust": "untrusted_document",
            },
            resource_version=file_hash(path),
        )
