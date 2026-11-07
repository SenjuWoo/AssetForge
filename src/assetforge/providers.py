"""External provider detection.

A provider is an optional tool that AssetForge delegates to. Detection is
read-only: nothing is installed, launched or configured here. Missing providers
are reported with a reason and a capability list, never silently replaced.
"""

from __future__ import annotations

import importlib.metadata
import os
import re
import shutil
import sys
from pathlib import Path

from .util import first_line, read_json, run

MARKERS = {
    "comfy-kit": ("TOOLS/image-stack.ps1", "presets/presets.json"),
    "img2threejs": ("SKILL.md", "forge/stage1_intake/probe_image.py"),
}


def _env_path(name: str):
    value = os.environ.get(name)
    return Path(value).expanduser() if value else None


def _declared_roots(project=None) -> list[Path]:
    roots: list[Path] = []
    for chunk in os.environ.get("ASSETFORGE_ROOTS", "").split(os.pathsep):
        if chunk.strip():
            roots.append(Path(chunk).expanduser())
    profile = Path.home() / ".uabs" / "profile" / "TOOL-ROOTS.txt"
    if profile.exists():
        try:
            for line in profile.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#"):
                    roots.append(Path(line).expanduser())
        except OSError:
            pass
    if project is not None:
        for value in (project.data.get("integrations") or {}).get("roots", []):
            roots.append(Path(value).expanduser())
    return [item for item in roots if item.exists()]


def _looks_like(path: Path, name: str) -> bool:
    return path.is_dir() and all((path / marker).exists() for marker in MARKERS[name])


def _breadth_first(roots: list[Path], name: str, depth: int = 3, limit: int = 400) -> Path | None:
    """Bounded search for an owner folder. Handles a moved checkout without
    walking an entire drive."""
    seen = 0
    level = list(roots)
    for _ in range(depth):
        nxt = []
        for parent in level:
            try:
                children = list(parent.iterdir())
            except OSError:
                continue
            for child in children:
                if not child.is_dir() or child.name.startswith("."):
                    continue
                seen += 1
                if seen > limit:
                    return None
                if _looks_like(child, name):
                    return child
                nxt.append(child)
        level = nxt
    return None


def find_owner(name: str, project=None, defaults: tuple[Path, ...] = (), env: str | None = None) -> Path | None:
    explicit = _env_path(env) if env else None
    if explicit and _looks_like(explicit, name):
        return explicit
    if project is not None:
        configured = (project.data.get("integrations") or {}).get(name.replace("-", "_"))
        if configured:
            candidate = Path(str(configured)).expanduser()
            if _looks_like(candidate, name):
                return candidate
    for candidate in defaults:
        if _looks_like(candidate, name):
            return candidate
    return _breadth_first(_declared_roots(project), name)


def _version_file(root: Path) -> str | None:
    path = root / "VERSION"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8").strip().splitlines()[0]
        except OSError:
            return None
    return None


def _tree_size_files(root: Path, limit: int = 5000) -> int:
    count = 0
    for _ in root.rglob("*"):
        count += 1
        if count >= limit:
            break
    return count


def _blender_version(path: Path) -> tuple[str | None, str]:
    result = run([path, "--version"], timeout=25)
    combined = f"{result.get('stdout', '')}\n{result.get('stderr', '')}"
    match = re.search(r"Blender\s+(\d+\.\d+(?:\.\d+)?)", combined)
    if not match:
        reason = result.get("error") or first_line(combined) or "probe did not identify Blender"
        return None, reason[:200]
    return match.group(1), ""


def _gltf_transform(project):
    roots = []
    if project is not None:
        roots.append(project.root)
    roots.append(Path(__file__).resolve().parents[2])
    node = shutil.which("node")
    for root in roots:
        cli = root / ".tools" / "node_modules" / "@gltf-transform" / "cli" / "bin" / "cli.js"
        if cli.exists() and node:
            command = [node, str(cli)]
            result = run(command + ["--version"], timeout=25)
            if result["returncode"] == 0:
                return command, first_line(result["stdout"] + result["stderr"]), str(cli)
    found = shutil.which("gltf-transform")
    if found and not str(found).lower().endswith((".cmd", ".bat")):
        result = run([found, "--version"], timeout=25)
        if result["returncode"] == 0:
            return [str(found)], first_line(result["stdout"] + result["stderr"]), str(found)
    return None, None, None


def _official_validator(project):
    node = shutil.which("node")
    wrapper = Path(__file__).resolve().parents[2] / "tools" / "validate_glb.mjs"
    roots = [Path(__file__).resolve().parents[2]]
    if project is not None:
        roots.append(project.root)
    for root in roots:
        module = root / ".tools" / "node_modules" / "gltf-validator" / "index.js"
        if node and wrapper.exists() and module.exists():
            return {"node": node, "wrapper": str(wrapper), "module": str(module)}
    return None


def _comfy_state():
    path = Path(os.environ.get("LOCALAPPDATA", "")) / "comfy-kit" / "anima-swarmui.json"
    if not path.exists():
        legacy = Path(os.environ.get("LOCALAPPDATA", "")) / "Ultimate-AI-Starter-Bundle" / "anima-swarmui.json"
        path = legacy if legacy.exists() else path
    if not path.exists():
        return {}
    try:
        data = read_json(path)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _pillow_version() -> str | None:
    try:
        return importlib.metadata.version("Pillow")
    except importlib.metadata.PackageNotFoundError:
        try:
            import PIL

            return getattr(PIL, "__version__", None)
        except ImportError:
            return None


def detect(project=None) -> list[dict]:
    home = Path.home()
    local = Path(os.environ.get("LOCALAPPDATA", ""))
    providers = []

    pillow = _pillow_version()
    providers.append({
        "id": "pillow",
        "title": "Pillow image processing",
        "kind": "python",
        "available": pillow is not None,
        "version": pillow,
        "path": None,
        "reason": "" if pillow else "Pillow is not installed for this Python",
        "capabilities": ["image.inspect", "image.resize", "image.convert", "image.thumbnail", "image.compare"],
    })

    node = shutil.which("node")
    node_version = None
    if node:
        result = run([node, "--version"], timeout=15)
        if result["returncode"] == 0:
            node_version = first_line(result["stdout"])
    providers.append({
        "id": "node",
        "title": "Node.js runtime",
        "kind": "runtime",
        "available": bool(node),
        "version": node_version,
        "path": node,
        "reason": "" if node else "Node.js is not on PATH",
        "capabilities": ["gltf-transform", "mcp"],
    })

    gtf, gtf_version, gtf_path = _gltf_transform(project)
    providers.append({
        "id": "gltf-transform",
        "title": "glTF-Transform CLI",
        "kind": "cli",
        "available": gtf is not None,
        "version": gtf_version,
        "path": gtf_path,
        "command": gtf,
        "reason": "" if gtf else "gltf-transform is not installed on PATH or in .tools",
        "capabilities": ["glb.optimize"],
    })

    validator = _official_validator(project)
    providers.append({
        "id": "gltf-validator",
        "title": "Khronos glTF Validator",
        "kind": "cli",
        "available": validator is not None,
        "version": None,
        "path": validator["wrapper"] if validator else None,
        "details": validator or {},
        "reason": "" if validator else "official validator package is not installed in .tools",
        "capabilities": ["glb.validate.official"],
    })

    blender = _env_path("BLENDER") or shutil.which("blender")
    blender_path = Path(blender) if blender else None
    if blender_path is None:
        for pattern in (
            Path("C:/Program Files/Blender Foundation").glob("Blender */blender.exe"),
            (local / "Programs" / "Blender Foundation").glob("Blender */blender.exe"),
        ):
            candidate = next(iter(pattern), None)
            if candidate:
                blender_path = candidate
                break
    blender_version = None
    blender_reason = "Blender is not installed or not on PATH"
    if blender_path:
        blender_version, blender_reason = _blender_version(blender_path)
        if blender_version is None:
            blender_path = None
    providers.append({
        "id": "blender",
        "title": "Blender (background)",
        "kind": "application",
        "available": blender_path is not None,
        "version": blender_version,
        "path": str(blender_path) if blender_path else None,
        "reason": "" if blender_path else blender_reason,
        "capabilities": ["blender.export_glb", "blender.headless"],
    })

    comfy = find_owner(
        "comfy-kit",
        project,
        defaults=(home / "comfy-kit", local / "comfy-kit"),
        env="COMFY_KIT_ROOT",
    )
    presets = 0
    comfy_version = _version_file(comfy) if comfy else None
    if comfy:
        try:
            presets = len(read_json(comfy / "presets" / "presets.json"))
        except (OSError, ValueError):
            presets = 0
    state = _comfy_state() if comfy else {}
    providers.append({
        "id": "comfy-kit",
        "title": "comfy-kit (image generation)",
        "kind": "owner",
        "available": comfy is not None,
        "version": comfy_version,
        "path": str(comfy) if comfy else None,
        "reason": "" if comfy else "comfy-kit was not found; set COMFY_KIT_ROOT or integrations.comfy_kit",
        "capabilities": ["image.generate.delegated", "image.presets"],
        "details": {"presets": presets, "swarmui": state.get("swarm_root") or state.get("swarmRoot")},
    })

    img2 = find_owner(
        "img2threejs",
        project,
        defaults=(
            home / ".hermes" / "skills" / "img2threejs",
            home / ".agents" / "skills" / "img2threejs",
            home / ".claude" / "skills" / "img2threejs",
            home / ".img2",
        ),
        env="IMG2THREEJS_ROOT",
    )
    providers.append({
        "id": "img2threejs",
        "title": "img2threejs skill",
        "kind": "skill",
        "available": img2 is not None,
        "version": _version_file(img2) if img2 else None,
        "path": str(img2) if img2 else None,
        "reason": "" if img2 else "img2threejs was not found; install it with npx or set IMG2THREEJS_ROOT",
        "capabilities": ["image.probe", "image.reconstruct.agent"],
    })

    return providers


def get(provider_id: str, project=None) -> dict:
    for item in detect(project):
        if item["id"] == provider_id:
            return item
    return {"id": provider_id, "title": provider_id, "available": False, "reason": "unknown provider"}


def tool_versions(project=None) -> dict:
    versions = {"python": sys.version.split()[0], "platform": sys.platform}
    for item in detect(project):
        if item["available"] and item.get("version"):
            versions[item["id"]] = item["version"]
    return versions
