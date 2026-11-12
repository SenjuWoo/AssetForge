"""Look at a file or folder before any project exists and say what to do with it.

`probe` is the routing step: it reads the source, reports the facts that decide
a pipeline (format, size, triangle count, rig, texture sizes) and names the
recipes that fit. It writes nothing and needs no project.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import exporters, images
from .adapters import CONVERTIBLE
from .glb import GlbError, inspect_glb, validate_glb
from .util import human_bytes

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tga"}
CHANNEL_WORDS = {
    "occlusion": ("ao", "occlusion", "ambientocclusion"),
    "roughness": ("rough", "roughness"),
    "metallic": ("metal", "metallic", "metalness"),
}
MAX_LISTED = 40
MAX_WALK = 5000


def classify(path: Path) -> str:
    if path.is_dir():
        return "directory"
    suffix = path.suffix.lower()
    if suffix == ".glb":
        return "glb"
    if suffix in CONVERTIBLE:
        return "mesh"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    return "unknown"


def _channel(name: str) -> str | None:
    words = set(re.split(r"[^a-z0-9]+", name.lower()))
    for channel, keys in CHANNEL_WORDS.items():
        if words & set(keys):
            return channel
    return None


def _quote(path: Path) -> str:
    return f'"{path}"'


def _step(recipe: str, reason: str, command: str) -> dict:
    return {"recipe": recipe, "reason": reason, "command": command}


def _budget_fit(stats: dict) -> list[dict]:
    """How the mesh sits against every export profile's budgets."""
    fits = []
    for name, profile in sorted(exporters.profiles().items()):
        budgets = profile.get("budgets") or {}
        over = []
        for key, value in (("triangles", stats["triangles"]), ("vertices", stats["vertices"]),
                           ("textures", stats["images"]), ("texture_size", stats["max_texture_size"])):
            limit = budgets.get(key)
            if limit and value > limit:
                over.append(f"{key} {value} > {limit}")
        fits.append({"target": name, "fits": not over, "over": over})
    return fits


def _probe_glb(path: Path) -> dict:
    try:
        stats = inspect_glb(path)
    except (GlbError, OSError) as exc:
        return {"facts": {}, "findings": [{"status": "FAIL", "detail": str(exc)}], "recommend": []}
    report = validate_glb(path)
    findings = [
        {"id": item["id"], "status": item["status"], "detail": item["detail"]}
        for item in report["checks"]
        if item["status"] in ("FAIL", "WARNING")
    ]
    fits = _budget_fit(stats)
    facts = {
        "bytes": stats["bytes"],
        "triangles": stats["triangles"],
        "vertices": stats["vertices"],
        "meshes": stats["meshes"],
        "materials": stats["materials"],
        "textures": stats["images"],
        "max_texture_size": stats["max_texture_size"],
        "uv_sets": stats["uv_sets"],
        "skins": stats["skins"],
        "max_joints": stats["rig"]["max_joints"],
        "animations": stats["animations"],
        "animation_seconds": stats["rig"]["animation_seconds"],
        "bbox_size": (stats["bbox"] or {}).get("size"),
        "validation": report["status"],
        "budget_fit": fits,
    }
    recommend = []
    game = next((item for item in fits if item["target"] == "roblox"), None) or fits[0]
    heavy = any("triangles" in entry or "texture_size" in entry for entry in game["over"])
    if heavy:
        reason = "over the game budget: " + ", ".join(game["over"])
        if stats["animations"]:
            reason += "; note that mesh-gameready does not carry animations over"
        recommend.append(_step("mesh-gameready", reason, f"assetforge run mesh-gameready --input {_quote(path)}"))
    else:
        recommend.append(_step("glb-optimize", "within budget; weld and prune without changing the look",
                               f"assetforge run glb-optimize --input {_quote(path)}"))
    recommend.append(_step("glb-inspect", "record the file as an asset with a validation report",
                           f"assetforge run glb-inspect --input {_quote(path)}"))
    return {"facts": facts, "findings": findings, "recommend": recommend}


def _probe_mesh(path: Path) -> dict:
    siblings = sorted(
        item.name for item in path.parent.iterdir()
        if item.is_file() and item != path and (item.stem == path.stem or item.suffix.lower() in IMAGE_SUFFIXES | {".mtl", ".bin"})
    )[:MAX_LISTED]
    facts = {"bytes": path.stat().st_size, "format": path.suffix.lower(), "beside_it": siblings}
    recommend = [_step(
        "mesh-convert",
        f"{path.suffix.lower()} is read through Blender; convert to GLB first, then probe the GLB",
        f"assetforge run mesh-convert --input {_quote(path)}",
    )]
    return {"facts": facts, "findings": [], "recommend": recommend}


def _probe_image(path: Path) -> dict:
    try:
        info = images.inspect_image(path)
    except images.ImageError as exc:
        return {"facts": {"bytes": path.stat().st_size}, "findings": [{"status": "FAIL", "detail": str(exc)}], "recommend": []}
    facts = {key: info[key] for key in ("bytes", "format", "mode", "width", "height", "has_alpha", "frames")}
    findings = []
    power_of_two = all(value and value & (value - 1) == 0 for value in (info["width"], info["height"]))
    facts["power_of_two"] = power_of_two
    if not power_of_two:
        findings.append({"status": "WARNING", "detail": f"{info['width']}x{info['height']} is not a power of two; some engines resample or refuse mipmaps"})
    channel = _channel(path.stem)
    recommend = [_step("image-prep", "resize, re-encode and write a thumbnail",
                       f"assetforge run image-prep --input {_quote(path)}")]
    if channel:
        facts["looks_like"] = channel
        recommend.append(_step("texture-pack", f"the name reads as a {channel} map; pack it with the other two into one ORM texture",
                               "assetforge run texture-pack --input occlusion=<ao> --input roughness=<rough> --input metallic=<metal>"))
    return {"facts": facts, "findings": findings, "recommend": recommend}


def _probe_directory(path: Path) -> dict:
    counts: dict[str, int] = {}
    listed: dict[str, list[str]] = {"glb": [], "mesh": [], "image": []}
    channels: dict[str, str] = {}
    total = 0
    truncated = False
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        total += 1
        if total > MAX_WALK:
            truncated = True
            break
        kind = classify(item)
        counts[kind] = counts.get(kind, 0) + 1
        if kind in listed and len(listed[kind]) < MAX_LISTED:
            listed[kind].append(item.relative_to(path).as_posix())
        if kind == "image":
            channel = _channel(item.stem)
            if channel and channel not in channels:
                channels[channel] = str(item)
    top_images = [item for item in sorted(path.iterdir()) if item.is_file() and classify(item) == "image"]
    facts = {"files": total, "by_kind": counts, "listed": {key: value for key, value in listed.items() if value}}
    findings = []
    if truncated:
        findings.append({"status": "WARNING", "detail": f"stopped after {MAX_WALK} files; counts are a lower bound"})
    recommend = []
    for name in listed["glb"][:5]:
        recommend.append(_step("probe", "look at this GLB", f"assetforge probe {_quote(path / name)}"))
    for name in listed["mesh"][:5]:
        recommend.append(_step("mesh-convert", "convert to GLB", f"assetforge run mesh-convert --input {_quote(path / name)}"))
    if len(channels) == 3:
        args = " ".join(f"--input {key}={_quote(Path(value))}" for key, value in sorted(channels.items()))
        recommend.append(_step("texture-pack", "an occlusion, a roughness and a metallic map are all present",
                               f"assetforge run texture-pack {args}"))
    if 2 <= len(top_images) <= 64 and not channels:
        recommend.append(_step("sprite-atlas", f"{len(top_images)} images sit directly in this folder",
                               f"assetforge run sprite-atlas --input {_quote(path)}"))
    return {"facts": facts, "findings": findings, "recommend": recommend}


def probe(path: Path) -> dict:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(str(path))
    kind = classify(path)
    handler = {"glb": _probe_glb, "mesh": _probe_mesh, "image": _probe_image, "directory": _probe_directory}.get(kind)
    if handler is None:
        body = {
            "facts": {"bytes": path.stat().st_size},
            "findings": [{"status": "WARNING", "detail": f"{path.suffix or 'this file'} is not an image or a mesh format AssetForge reads"}],
            "recommend": [],
        }
    else:
        body = handler(path)
    return {"schema": 1, "path": str(path), "kind": kind, **body}


def render(report: dict) -> str:
    lines = [f"{report['kind']}  {report['path']}"]
    for key, value in report["facts"].items():
        if key == "budget_fit":
            for item in value:
                lines.append(f"  fits {item['target']:<8} {'yes' if item['fits'] else 'no: ' + ', '.join(item['over'])}")
        elif key == "bytes":
            lines.append(f"  size         {human_bytes(value)}")
        elif key == "listed":
            for kind, names in value.items():
                lines.append(f"  {kind:<12} " + ", ".join(names[:8]) + (" ..." if len(names) > 8 else ""))
        else:
            lines.append(f"  {key:<12} {value}")
    for item in report["findings"]:
        lines.append(f"  {item['status']:<8} {item.get('id', ''):<8} {item['detail']}")
    for item in report["recommend"]:
        lines.append(f"next: {item['command']}")
        lines.append(f"      {item['reason']}")
    return "\n".join(lines)
