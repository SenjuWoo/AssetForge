"""Thin delegations to external owners. Each function builds an argument list,
runs it with a timeout, and verifies the output it claims to have produced.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .util import read_json, run


class AdapterError(RuntimeError):
    pass


def blender_build(provider: dict, out_path: Path, timeout: float = 240) -> dict:
    script = Path(__file__).resolve().parent / "blender_sample.py"
    command = [
        provider["path"],
        "-b",
        "--factory-startup",
        "--python",
        str(script),
        "--",
        "--out",
        str(out_path),
    ]
    result = run(command, timeout=timeout, cwd=out_path.parent)
    result["command"] = command
    if result.get("timed_out"):
        raise AdapterError(f"Blender timed out after {timeout:g}s")
    if result["returncode"] != 0:
        raise AdapterError(f"Blender exited {result['returncode']}: {result['stderr'][-800:] or result['stdout'][-800:]}")
    if not out_path.exists() or out_path.stat().st_size < 20:
        raise AdapterError("Blender reported success but no GLB was written")
    return result


def comfykit_generate(root: Path, params: dict, out_dir: Path, timeout: float = 900) -> dict:
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        raise AdapterError("PowerShell is required to delegate to comfy-kit")
    prompt = str(params.get("prompt") or "").strip()
    if not prompt:
        raise AdapterError("prompt is required for comfy-kit generation")
    preset = str(params.get("preset") or "").strip()
    width = int(params.get("width") or 1024)
    height = int(params.get("height") or 1024)
    if width < 64 or height < 64:
        raise AdapterError("width and height must be at least 64")
    script = root / "TOOLS" / "image-stack.ps1"
    command = [
        powershell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script),
        "generate",
        "-Prompt",
        prompt,
        "-Width",
        str(width),
        "-Height",
        str(height),
        "-Seed",
        str(params.get("seed", -1)),
        "-Count",
        str(max(1, min(int(params.get("count") or 1), 24))),
        "-Out",
        str(out_dir),
    ]
    if preset:
        command.extend(["-Preset", preset])
    if params.get("model"):
        command.extend(["-Model", str(params["model"])])
    result = run(command, timeout=timeout, cwd=root)
    result["command"] = command
    if result.get("timed_out"):
        raise AdapterError(f"comfy-kit generate timed out after {timeout:g}s")
    if result["returncode"] != 0:
        raise AdapterError(f"comfy-kit generate exited {result['returncode']}: {(result['stderr'] or result['stdout'])[-800:]}")
    return result


def comfykit_images(out_dir: Path) -> list[Path]:
    if not out_dir.exists():
        return []
    files = [item for item in out_dir.iterdir() if item.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    return sorted(files, key=lambda item: (item.stat().st_mtime, item.name))


def img2threejs_probe(root: Path, image: Path, out_json: Path, timeout: float = 120) -> dict:
    script = root / "forge" / "stage1_intake" / "probe_image.py"
    command = [sys.executable, str(script), str(image), "--out", str(out_json)]
    result = run(command, timeout=timeout, cwd=root)
    result["command"] = command
    if result.get("timed_out"):
        raise AdapterError(f"img2threejs probe timed out after {timeout:g}s")
    if result["returncode"] != 0:
        raise AdapterError(f"img2threejs probe exited {result['returncode']}: {result['stderr'][-800:]}")
    if not out_json.exists():
        raise AdapterError("img2threejs probe wrote no JSON")
    try:
        data = read_json(out_json)
    except ValueError as exc:
        raise AdapterError(f"img2threejs probe output is not JSON: {exc}") from exc
    return data


def img2threejs_codegen(root: Path, spec: Path, out_path: Path, timeout: float = 120) -> dict:
    """Run the upstream deterministic spec-to-Three.js generator. This consumes
    an ObjectSculptSpec; it does not perform image reconstruction."""
    script = root / "forge" / "stage3_build" / "generate_threejs_factory.py"
    if not script.exists():
        raise AdapterError(f"img2threejs code generator is missing: {script}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, str(script), str(spec), "--out", str(out_path)]
    result = run(command, timeout=timeout, cwd=root)
    result["command"] = command
    if result.get("timed_out"):
        raise AdapterError(f"img2threejs codegen timed out after {timeout:g}s")
    if result["returncode"] != 0:
        raise AdapterError(f"img2threejs codegen exited {result['returncode']}: {(result['stderr'] or result['stdout'])[-800:]}")
    if not out_path.exists() or out_path.stat().st_size < 500:
        raise AdapterError("img2threejs codegen reported success but wrote no usable TypeScript")
    return result
