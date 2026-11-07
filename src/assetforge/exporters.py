"""Validation reports and engine export packaging.

Export means: copy the validated mesh or texture deliverables into a target
folder, write a machine-readable record and import notes. It never claims the
asset was imported into an engine; that check is always NOT_TESTED here.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from . import images, official
from .glb import inspect_glb, validate_glb
from .store import Asset, Project, StoreError
from .util import now_iso, read_json, sha256_file, write_json, write_text


class ExportError(RuntimeError):
    pass


def profile_dir() -> Path:
    return Path(__file__).resolve().parent / "data" / "profiles"


def load_profile(profile_id: str) -> dict:
    path = profile_dir() / f"{profile_id}.json"
    if not path.exists():
        raise ExportError(f"unknown export profile {profile_id!r}")
    return read_json(path)


def profiles() -> dict[str, dict]:
    return {path.stem: read_json(path) for path in sorted(profile_dir().glob("*.json"))}


def _primary_mesh(asset: Asset) -> tuple[Path, bool]:
    """Return the declared mesh deliverable. Falls back to a deterministic
    label order only for older manifests without a primary entry."""
    declared = (asset.manifest.get("primary") or {}).get("mesh")
    if declared:
        return asset.resolve_artifact(declared), True
    candidates = [item for item in asset.manifest.get("artifacts", []) if item.get("role") == "mesh"]
    for label in ("optimized", "deliverable", "source"):
        for item in candidates:
            if item.get("label") == label:
                return asset.resolve_artifact(item["path"]), False
    if candidates:
        return asset.resolve_artifact(candidates[0]["path"]), False
    raise ExportError("asset has no GLB artifact to export")


def _image_artifacts(asset: Asset) -> list[dict]:
    return [item for item in asset.manifest.get("artifacts", []) if item.get("media_type", "").startswith("image/")]


def _primary_image(asset: Asset) -> tuple[Path, bool]:
    """Return the declared texture deliverable, falling back to a deterministic
    label order only when no primary image is recorded."""
    declared = (asset.manifest.get("primary") or {}).get("image")
    if declared:
        return asset.resolve_artifact(declared), True
    candidates = _image_artifacts(asset)
    for label in ("orm", "atlas", "deliverable", "source"):
        for item in candidates:
            if item.get("label") == label:
                return asset.resolve_artifact(item["path"]), False
    if candidates:
        return asset.resolve_artifact(candidates[0]["path"]), False
    raise ExportError("asset has no image artifact to export")


def validate_asset(project: Project, asset: Asset) -> dict:
    checks: list[dict] = []
    meshes = [item for item in asset.manifest.get("artifacts", []) if item.get("role") == "mesh" or item.get("path", "").lower().endswith(".glb")]
    image_items = _image_artifacts(asset)
    if not meshes and not image_items:
        checks.append({
            "artifact": None,
            "id": "ASSET-001",
            "status": "FAIL",
            "detail": "asset has no mesh or image artifact; source-only artifacts such as Three.js TypeScript remain editable intermediates and are not exported",
        })
    for item in meshes:
        try:
            path = asset.resolve_artifact(item["path"])
        except Exception as exc:
            checks.append({"artifact": item.get("path"), "id": "ASSET-002", "status": "FAIL", "detail": str(exc)})
            continue
        report = validate_glb(path)
        for check in report["checks"]:
            if check["id"] == "GLB-014":
                check = official.check(project, path)
            checks.append({"artifact": item["path"], **check})

    for item in image_items:
        try:
            path = asset.resolve_artifact(item["path"])
            info = images.inspect_image(path)
            checks.append({
                "artifact": item["path"],
                "id": "IMG-001",
                "status": "PASS",
                "detail": f"{info['format']} {info['width']}x{info['height']} {info['mode']}",
            })
        except Exception as exc:
            checks.append({"artifact": item.get("path"), "id": "IMG-001", "status": "FAIL", "detail": str(exc)})

    summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
    for item in checks:
        summary[item["status"]] += 1
    overall = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")
    report = {"schema": 1, "asset": asset.id, "created": now_iso(), "checks": checks, "summary": summary, "status": overall}
    path = asset.path("outputs", "validation.json")
    write_json(path, report)
    asset.set_validation(checks)
    return report


def _budget(checks: list[dict], name: str, value, limit, unit: str = "") -> None:
    if not limit:
        checks.append({"id": f"BUDGET-{name.upper()}", "status": "NOT_TESTED", "detail": f"no {name} budget in this profile"})
        return
    status = "PASS" if value <= limit else "FAIL"
    checks.append({
        "id": f"BUDGET-{name.upper()}",
        "status": status,
        "detail": f"{value}{unit} / budget {limit}{unit}",
    })


def export(project: Project, asset: Asset, target: str, dry_run: bool = False) -> dict:
    profile = load_profile(target)
    validation = validate_asset(project, asset)
    if validation["status"] == "FAIL":
        failed = [item for item in validation["checks"] if item["status"] == "FAIL"]
        detail = "; ".join(item["detail"] for item in failed[:3])
        raise ExportError(f"export blocked by validation: {detail}")

    mesh_items = [item for item in asset.manifest.get("artifacts", []) if item.get("role") == "mesh" or item.get("path", "").lower().endswith(".glb")]
    image_items = _image_artifacts(asset)
    kind = "mesh" if mesh_items else "texture"
    budgets = profile.get("budgets") or {}

    if kind == "mesh":
        try:
            primary, declared = _primary_mesh(asset)
        except StoreError as exc:
            raise ExportError(f"cannot resolve the primary mesh: {exc}") from exc
        stats = inspect_glb(primary)
        checks = [
            {"id": "FORMAT-001", "status": "PASS", "detail": f"glTF binary, {stats['bytes']} bytes"},
            {
                "id": "PRIMARY-001",
                "status": "PASS" if declared else "WARNING",
                "detail": asset.manifest.get("primary", {}).get("mesh") or "manifest has no primary; deterministic label fallback used",
            },
        ]
        _budget(checks, "triangles", stats["triangles"], budgets.get("triangles"))
        _budget(checks, "vertices", stats["vertices"], budgets.get("vertices"))
        _budget(checks, "textures", stats["images"], budgets.get("textures"))
    else:
        try:
            primary, declared = _primary_image(asset)
        except StoreError as exc:
            raise ExportError(f"cannot resolve the primary image: {exc}") from exc
        info = images.inspect_image(primary)
        checks = [
            {"id": "FORMAT-002", "status": "PASS", "detail": f"{info['format']} image, {info['width']}x{info['height']}, {info['bytes']} bytes"},
            {
                "id": "PRIMARY-001",
                "status": "PASS" if declared else "WARNING",
                "detail": asset.manifest.get("primary", {}).get("image") or "manifest has no primary image; deterministic label fallback used",
            },
        ]
        for name in ("triangles", "vertices", "textures"):
            checks.append({"id": f"BUDGET-{name.upper()}", "status": "NOT_TESTED", "detail": "texture-only asset has no mesh budget"})

    texture_limit = int(budgets.get("texture_size") or 0)
    if not texture_limit:
        checks.append({"id": "BUDGET-TEXTURE_SIZE", "status": "NOT_TESTED", "detail": "no texture size budget"})
    elif not image_items:
        checks.append({"id": "BUDGET-TEXTURE_SIZE", "status": "NOT_TESTED", "detail": "textures are embedded; size not decoded"})
    else:
        oversize = []
        for item in image_items:
            try:
                info = images.inspect_image(asset.resolve_artifact(item["path"]))
                if max(info["width"], info["height"]) > texture_limit:
                    oversize.append(f"{Path(item['path']).name} {info['width']}x{info['height']}")
            except Exception:
                oversize.append(f"{Path(item['path']).name} unreadable")
        checks.append({
            "id": "BUDGET-TEXTURE_SIZE",
            "status": "FAIL" if oversize else "PASS",
            "detail": "; ".join(oversize) if oversize else f"all loose textures <= {texture_limit}px",
        })

    checks.append({
        "id": "ENGINE-IMPORT",
        "status": "NOT_TESTED",
        "detail": f"{profile['title']} was not launched; this is packaging and structural validation only",
    })
    summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
    for item in checks:
        summary[item["status"]] += 1
    overall = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")

    plan = {
        "target": target,
        "asset": asset.id,
        "kind": kind,
        "profile": profile,
        "source": str(primary),
        "checks": checks,
        "summary": summary,
        "status": overall,
        "engine_import": "NOT_TESTED",
        "validation": validation["summary"],
    }
    if dry_run:
        return plan
    if overall == "FAIL":
        raise ExportError("export blocked by a failed budget check: " + "; ".join(item["detail"] for item in checks if item["status"] == "FAIL"))

    out_dir = asset.path("exports", target)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = []
    if kind == "mesh":
        target_name = f"{asset.id}{primary.suffix.lower()}"
        mesh_target = out_dir / target_name
        shutil.copy2(primary, mesh_target)
        files.append({
            "path": mesh_target.name,
            "sha256": sha256_file(mesh_target),
            "bytes": mesh_target.stat().st_size,
        })
    texture_dir = out_dir / "textures"
    for item in image_items:
        source = asset.resolve_artifact(item["path"])
        texture_dir.mkdir(exist_ok=True)
        copy = texture_dir / source.name
        shutil.copy2(source, copy)
        files.append({"path": copy.relative_to(out_dir).as_posix(), "sha256": sha256_file(copy), "bytes": copy.stat().st_size})

    record = {
        "schema": 1,
        "target": target,
        "title": profile["title"],
        "asset": asset.id,
        "kind": kind,
        "created": now_iso(),
        "status": overall,
        "checks": checks,
        "files": files,
        "engine_import": "NOT_TESTED",
    }
    write_json(out_dir / "export.json", record)
    write_text(out_dir / "IMPORT.md", _import_notes(profile, record))
    asset.add_export({"target": target, "path": out_dir.relative_to(project.root).as_posix(), "created": record["created"], "status": overall})
    return {**plan, "out_dir": str(out_dir), "files": files}


def _import_notes(profile: dict, record: dict) -> str:
    lines = [
        f"# {profile['title']} import",
        "",
        f"Asset: `{record['asset']}`",
        f"Package status: **{record['status']}**",
        "",
        "## Files",
        "",
    ]
    for item in record["files"]:
        lines.append(f"- `{item['path']}`")
    lines += ["", "## Steps", ""]
    if record.get("kind") == "texture":
        if profile["id"] == "roblox":
            lines += [
                "1. Open the Roblox Creator Dashboard or Studio's Asset Manager.",
                "2. Upload each PNG in `textures/` as an image asset.",
                "3. Apply the image to a material or decal; no mesh is included in this package.",
            ]
        elif profile["id"] == "godot":
            lines += [
                "1. Copy the PNG files into the Godot project.",
                "2. Let the editor import them as textures.",
                "3. Assign them to a material; no `.glb` is included in this package.",
            ]
        else:
            lines += [
                "1. Load the PNG in an image viewer or material authoring tool.",
                "2. ORM maps are linear data, not sRGB color; base color stays separate.",
            ]
    elif profile["id"] == "roblox":
        lines += [
            "1. Open Roblox Studio and choose **File > Import**.",
            "2. Select the `.glb` file in this folder.",
            "3. Check scale and pivot in the import preview before confirming.",
        ]
    elif profile["id"] == "godot":
        lines += [
            "1. Copy the `.glb` into the Godot project.",
            "2. Let the editor finish importing, then open the generated scene.",
            "3. Check scale, materials and lightmap UVs in the editor.",
        ]
    else:
        lines += ["1. Load the `.glb` in any glTF 2.0 viewer or engine importer.", "2. Check scale and materials."]
    lines += [
        "",
        "## Evidence boundary",
        "",
        profile.get("notes", ""),
        "",
        "This package passed structural checks and any configured budgets. "
        "No editor or engine import was executed, so visual quality, pivots, "
        "scale, materials and runtime behavior remain **NOT_TESTED**.",
        "",
    ]
    return "\n".join(lines)
