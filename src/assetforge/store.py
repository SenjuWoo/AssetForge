"""Project, asset and job storage.

One project is one folder with `assetforge.json`, `assets/` and `.assetforge/`.
Assets are folders with a small JSON manifest; binaries live beside it, never
inside the JSON. Jobs are append-only records that survive a crash.
"""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from .util import now_iso, read_json, safe_name, sha256_file, slugify, write_json

PROJECT_FILE = "assetforge.json"
PROJECT_SCHEMA = 1


class StoreError(RuntimeError):
    pass


def _media_type(path: Path) -> str:
    return {
        ".glb": "model/gltf-binary",
        ".gltf": "model/gltf+json",
        ".bin": "application/octet-stream",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".json": "application/json",
        ".md": "text/markdown",
    }.get(path.suffix.lower(), "application/octet-stream")


class Asset:
    def __init__(self, project: "Project", folder: Path):
        self.project = project
        self.folder = folder
        self.manifest_path = folder / "asset.json"
        if not self.manifest_path.exists():
            raise StoreError(f"asset manifest missing: {self.manifest_path}")
        self.manifest = read_json(self.manifest_path)

    @property
    def id(self) -> str:
        return self.manifest["id"]

    def path(self, *parts: str) -> Path:
        return self.folder.joinpath(*parts)

    def save(self) -> None:
        self.manifest["updated"] = now_iso()
        write_json(self.manifest_path, self.manifest)

    def _relative(self, path: Path) -> str:
        path = Path(path).resolve()
        try:
            return path.relative_to(self.project.root.resolve()).as_posix()
        except ValueError as exc:
            raise StoreError(f"path is outside the project: {path}") from exc

    def resolve_artifact(self, value) -> Path:
        """Resolve a manifest path, rejecting absolute paths, escapes and
        missing files. Every consumer of an artifact path goes through this."""
        raw = Path(str(value))
        if raw.is_absolute():
            raise StoreError(f"artifact path must be project-relative: {value}")
        target = (self.project.root / raw).resolve()
        try:
            target.relative_to(self.project.root.resolve())
        except ValueError as exc:
            raise StoreError(f"artifact path escapes the project: {value}") from exc
        if not target.is_file():
            raise StoreError(f"artifact is missing: {value}")
        return target

    def add_input(self, path: Path, kind: str = "file") -> dict:
        path = Path(path).resolve()
        if not path.is_file():
            raise StoreError(f"input is not a file: {path}")
        inputs_dir = self.folder / "inputs"
        inputs_dir.mkdir(parents=True, exist_ok=True)
        target = inputs_dir / path.name
        if target.exists() and sha256_file(target) != sha256_file(path):
            target = inputs_dir / f"{path.stem}-{uuid.uuid4().hex[:6]}{path.suffix}"
        if not target.exists():
            shutil.copy2(path, target)
        record = {
            "path": self._relative(target),
            "name": path.name,
            "kind": kind,
            "bytes": target.stat().st_size,
            "sha256": sha256_file(target),
        }
        self.manifest.setdefault("inputs", [])
        if not any(item.get("sha256") == record["sha256"] for item in self.manifest["inputs"]):
            self.manifest["inputs"].append(record)
        self.save()
        return record

    def add_artifact(self, path: Path, role: str, label: str | None = None) -> dict:
        path = Path(path).resolve()
        if not path.is_file():
            raise StoreError(f"artifact is not a file: {path}")
        record = {
            "path": self._relative(path),
            "role": role,
            "media_type": _media_type(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if label:
            record["label"] = label
        self.manifest.setdefault("artifacts", [])
        # Re-running a recipe in the same asset replaces the record for the same path.
        self.manifest["artifacts"] = [item for item in self.manifest["artifacts"] if item.get("path") != record["path"]]
        self.manifest["artifacts"].append(record)
        self.save()
        return record

    def set_primary(self, role: str, path: Path) -> None:
        """Record the intended deliverable explicitly instead of guessing from
        artifact order."""
        path = Path(path).resolve()
        if not path.is_file():
            raise StoreError(f"primary artifact is not a file: {path}")
        self.manifest.setdefault("primary", {})[role] = self._relative(path)
        self.save()

    def primary(self, role: str) -> Path | None:
        value = (self.manifest.get("primary") or {}).get(role)
        return self.resolve_artifact(value) if value else None

    def set_validation(self, checks: list[dict]) -> None:
        self.manifest["validation"] = checks
        self.save()

    def add_export(self, record: dict) -> None:
        self.manifest.setdefault("exports", [])
        self.manifest["exports"] = [item for item in self.manifest["exports"] if item.get("target") != record.get("target")]
        self.manifest["exports"].append(record)
        self.save()


class Project:
    def __init__(self, root: Path):
        self.root = Path(root).resolve()
        self.file = self.root / PROJECT_FILE
        if not self.file.exists():
            raise StoreError(f"no {PROJECT_FILE} in {self.root}; run `assetforge init` first")
        self.data = read_json(self.file)
        if self.data.get("schema") != PROJECT_SCHEMA:
            raise StoreError(f"unsupported project schema: {self.data.get('schema')}")

    @classmethod
    def find(cls, start: Path | None = None) -> "Project | None":
        here = Path(start or Path.cwd()).resolve()
        for folder in (here, *here.parents):
            if (folder / PROJECT_FILE).exists():
                return cls(folder)
        return None

    @classmethod
    def init(cls, root: Path, name: str | None = None) -> "Project":
        root = Path(root).resolve()
        root.mkdir(parents=True, exist_ok=True)
        file = root / PROJECT_FILE
        if file.exists():
            return cls(root)
        data = {
            "schema": PROJECT_SCHEMA,
            "name": name or root.name,
            "created": now_iso(),
            "integrations": {},
            "default_profile": "generic",
        }
        write_json(file, data)
        (root / "assets").mkdir(exist_ok=True)
        (root / ".assetforge" / "jobs").mkdir(parents=True, exist_ok=True)
        (root / "recipes").mkdir(exist_ok=True)
        return cls(root)

    def save(self) -> None:
        write_json(self.file, self.data)

    @property
    def assets_dir(self) -> Path:
        return self.root / "assets"

    @property
    def jobs_dir(self) -> Path:
        return self.root / ".assetforge" / "jobs"

    def asset_folder(self, asset_id: str) -> Path:
        return self.assets_dir / safe_name(asset_id)

    def create_asset(self, name: str, recipe: str | None = None, params: dict | None = None) -> Asset:
        stamp = now_iso().replace("-", "").replace(":", "").replace("+00:00", "Z")[:15]
        base = f"{slugify(name)}-{stamp}"
        folder = self.asset_folder(base)
        counter = 2
        while folder.exists():
            folder = self.asset_folder(f"{base}-{counter}")
            counter += 1
        (folder / "inputs").mkdir(parents=True, exist_ok=True)
        (folder / "outputs").mkdir(exist_ok=True)
        (folder / "previews").mkdir(exist_ok=True)
        manifest = {
            "schema": 1,
            "id": folder.name,
            "name": name,
            "created": now_iso(),
            "updated": now_iso(),
            "source": {"recipe": recipe, "params": params or {}},
            "inputs": [],
            "artifacts": [],
            "primary": {},
            "exports": [],
            "validation": [],
            "provenance": {
                "tool": "AssetForge",
                "version": _version(),
                "versions": {},
                "seed": (params or {}).get("seed"),
            },
            "license": {"mode": "user-supplied", "note": "AssetForge does not relicense inputs or outputs."},
        }
        write_json(folder / "asset.json", manifest)
        return Asset(self, folder)

    def asset(self, query: str) -> Asset:
        exact = self.asset_folder(query)
        if (exact / "asset.json").exists():
            return Asset(self, exact)
        matches = [folder for folder in self.assets_dir.glob(f"{query}*") if (folder / "asset.json").exists()]
        if len(matches) == 1:
            return Asset(self, matches[0])
        if not matches:
            raise StoreError(f"no asset matches {query!r}")
        raise StoreError(f"ambiguous asset id {query!r}; matches: {', '.join(item.name for item in matches[:5])}")

    def assets(self) -> list[Asset]:
        if not self.assets_dir.exists():
            return []
        return [Asset(self, folder) for folder in sorted(self.assets_dir.iterdir()) if (folder / "asset.json").exists()]


class Job:
    def __init__(self, project: Project, job_id: str, data: dict):
        self.project = project
        self.id = job_id
        self.data = data
        self.folder = project.jobs_dir / job_id

    @classmethod
    def create(cls, project: Project, recipe: str, params: dict, asset_id: str | None = None, sources: dict | None = None) -> "Job":
        stamp = now_iso().replace("-", "").replace(":", "").replace("+00:00", "Z")[:15]
        job_id = f"{stamp}-{uuid.uuid4().hex[:6]}"
        folder = project.jobs_dir / job_id
        folder.mkdir(parents=True, exist_ok=False)
        data = {
            "schema": 1,
            "id": job_id,
            "recipe": recipe,
            "status": "RUNNING",
            "started": now_iso(),
            "finished": None,
            "params": params,
            "asset": asset_id,
            "sources": sources or {},
            "steps": [],
            "error": None,
        }
        job = cls(project, job_id, data)
        job.save()
        return job

    @classmethod
    def load(cls, project: Project, job_id: str) -> "Job":
        folder = project.jobs_dir / job_id
        if not (folder / "job.json").exists():
            raise StoreError(f"no job {job_id!r}")
        return cls(project, job_id, read_json(folder / "job.json"))

    @classmethod
    def latest(cls, project: Project) -> "Job | None":
        if not project.jobs_dir.exists():
            return None
        folders = sorted((item for item in project.jobs_dir.iterdir() if (item / "job.json").exists()), reverse=True)
        return cls(project, folders[0].name, read_json(folders[0] / "job.json")) if folders else None

    def save(self) -> None:
        write_json(self.folder / "job.json", self.data)

    def log(self, line: str) -> None:
        with open(self.folder / "run.log", "a", encoding="utf-8") as fh:
            fh.write(f"{now_iso()} {line}\n")

    def step(self, name: str, status: str, detail: str = "", **extra) -> None:
        record = {"name": name, "status": status, "detail": detail, **extra}
        self.data["steps"].append(record)
        self.log(f"[{status}] {name}: {detail}")
        self.save()

    def finish(self, status: str, error: str | None = None) -> None:
        self.data["status"] = status
        self.data["finished"] = now_iso()
        self.data["error"] = error
        self.save()


def _version() -> str:
    from . import __version__

    return __version__
