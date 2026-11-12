"""Thin delegations to external owners. Each function builds an argument list,
runs it with a timeout, and verifies the output it claims to have produced.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

from .util import read_json, run


class AdapterError(RuntimeError):
    pass


def blender_gameready(provider: dict, source: Path, out_path: Path, tris: int, texture: int, timeout: float = 900) -> dict:
    """Collapse a GLB in Blender to a triangle budget and a texture cap.

    The script lives with the package. ASSETFORGE_SRC lets Blender import
    the same budget helper the tests use, so the limits are not copied.
    """
    script = Path(__file__).resolve().parent / "data" / "blender" / "gameready.py"
    src = str(Path(__file__).resolve().parent.parent)
    command = [
        provider["path"],
        "-b",
        "--factory-startup",
        "--python",
        str(script),
        "--",
        "--input",
        str(source),
        "--out",
        str(out_path),
        "--tris",
        str(int(tris)),
        "--texture",
        str(int(texture)),
    ]
    result = run(command, timeout=timeout, cwd=out_path.parent, env={"ASSETFORGE_SRC": src})
    result["command"] = command
    if result.get("timed_out"):
        raise AdapterError(f"Blender timed out after {timeout:g}s")
    payload = None
    for line in reversed((result.get("stdout") or "").splitlines()):
        if line.startswith("GAMEREADY "):
            try:
                payload = json.loads(line[len("GAMEREADY "):])
            except ValueError:
                payload = None
            break
    result["report"] = payload
    if result["returncode"] != 0:
        detail = ""
        if isinstance(payload, dict) and payload.get("error"):
            detail = str(payload["error"])
        else:
            detail = (result.get("stderr") or result.get("stdout") or "")[-800:]
        raise AdapterError(f"Blender exited {result['returncode']}: {detail}")
    if not out_path.exists() or out_path.stat().st_size < 20:
        raise AdapterError("Blender reported success but no GLB was written")
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise AdapterError(f"Blender game-ready failed: {payload.get('error')}")
    return result


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


def _json_tail(text: str) -> dict:
    """The upstream runner prints one JSON object; trim accidental banner noise."""
    text = (text or "").strip()
    if not text:
        raise AdapterError("blender-skills wrote no JSON result")
    try:
        data = json.loads(text)
    except ValueError:
        data = None
        for line in reversed(text.splitlines()):
            try:
                data = json.loads(line)
                break
            except ValueError:
                continue
        if data is None:
            raise AdapterError(f"blender-skills returned non-JSON output: {text[-500:]}")
    if not isinstance(data, dict):
        raise AdapterError("blender-skills returned a non-object JSON result")
    return data


def blender_skills_exec(provider: dict, blender: dict, script: Path, args: list[str],
                        blend: Path | None = None, timeout: float = 600,
                        cwd: Path | str | None = None) -> tuple[dict, dict]:
    """Run one upstream skill script through blender-core's headless launcher.

    The owner keeps the skill scripts and Blender discovery; AssetForge supplies
    the executable it already verified and parses the JSON contract.
    """
    script = Path(script)
    if not script.is_file():
        raise AdapterError(f"blender-skills script is missing: {script}")
    details = provider.get("details") or {}
    runner = Path(details.get("skills_dir") or "") / "blender-core" / "scripts" / "run_in_blender.py"
    if not runner.is_file():
        raise AdapterError(f"blender-skills headless runner is missing: {runner}")
    command = [sys.executable, str(runner)]
    if blend:
        command += ["--blend", str(blend)]
    command += [str(script), "--"] + [str(item) for item in args]
    result = run(command, timeout=timeout, cwd=cwd, env={"BLENDER_EXE": str(blender["path"])})
    result["command"] = command
    if result.get("timed_out"):
        raise AdapterError(f"blender-skills script timed out after {timeout:g}s")
    if result["returncode"] != 0:
        raise AdapterError(
            f"blender-skills script exited {result['returncode']}: "
            f"{(result['stderr'] or result['stdout'])[-800:]}"
        )
    data = _json_tail(result.get("stdout", ""))
    if data.get("ok") is False:
        raise AdapterError(f"blender-skills script failed: {data.get('error') or data}")
    return data, result
