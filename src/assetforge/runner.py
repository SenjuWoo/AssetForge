"""Job runner: maps recipe steps to real operations and records evidence.

The runner writes one job folder per non-dry run. A step failure stops the
pipeline, marks the job FAILED and leaves the asset folder for inspection.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from . import adapters, gameready, images, official, providers
from .glb import GlbError, compare_glb, inspect_glb, validate_glb
from .recipes import RecipeError, asset_name
from .store import Asset, Job, Project, StoreError
from .util import human_bytes, now_iso, sha256_file, write_json

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tga"}
MESH_SUFFIXES = {".glb"}


class RunFailed(RuntimeError):
    pass


class ProviderMissing(RunFailed):
    pass


def _provider(ctx, provider_id: str) -> dict:
    item = providers.get(provider_id, ctx.project)
    if not item.get("available"):
        raise ProviderMissing(f"{provider_id} is unavailable: {item.get('reason') or 'not installed'}")
    return item


def _mark_failed(asset: Asset) -> None:
    try:
        asset.manifest["status"] = "FAILED"
        asset.save()
    except Exception:
        # A failed status write must not hide the original job failure.
        pass


class Context:
    def __init__(self, project: Project, asset: Asset, job: Job, recipe: dict, inputs: dict[str, Path], params: dict, copied: dict[str, Path] | None = None):
        self.project = project
        self.asset = asset
        self.job = job
        self.recipe = recipe
        self.inputs = inputs
        self.copied = copied if copied is not None else {}
        self.params = params
        self.outputs: dict = {}
        self.validation: list[dict] = []

    def input(self, name: str = "") -> Path:
        """Return a project-owned copy for files. Directories (an import
        source) stay external because there is nothing to copy into the asset."""
        if name:
            if name in self.copied:
                return self.copied[name]
            if name in self.inputs and self.inputs[name].is_dir():
                return self.inputs[name]
            raise RunFailed(f"input {name!r} has no project-owned copy")
        for key in ("image", "mesh", "source"):
            if key in self.copied:
                return self.copied[key]
            if key in self.inputs and self.inputs[key].is_dir():
                return self.inputs[key]
        if self.copied:
            return next(iter(self.copied.values()))
        raise RunFailed("recipe needs a project-owned input file but none was supplied")

    def image_input(self) -> Path:
        for path in self.copied.values():
            if path.suffix.lower() in IMAGE_SUFFIXES:
                return path
        raise RunFailed("recipe needs an image input")

    def mesh(self) -> Path:
        if "mesh" in self.outputs:
            return Path(self.outputs["mesh"])
        for path in self.copied.values():
            if path.suffix.lower() in MESH_SUFFIXES:
                return path
        raise RunFailed("recipe needs a .glb input")

    def artifact(self, path: Path, role: str, label: str = "") -> None:
        self.asset.add_artifact(path, role, label or None)

    def report(self, name: str, data: dict) -> Path:
        path = self.asset.path("outputs", name)
        write_json(path, data)
        self.artifact(path, "report", name)
        return path


def _image_inspect(ctx: Context) -> dict:
    source = ctx.image_input()
    info = images.inspect_image(source)
    ctx.outputs["image"] = source
    ctx.outputs["image_info"] = info
    warnings = []
    if info["width"] < 64 or info["height"] < 64:
        warnings.append("small image")
    if info["has_alpha"]:
        warnings.append("alpha present")
    status = "WARNING" if warnings else "PASS"
    return {"status": status, "detail": f"{info['format']} {info['width']}x{info['height']} {info['mode']}" + (f" ({', '.join(warnings)})" if warnings else "")}


def _image_convert(ctx: Context) -> dict:
    source = ctx.outputs.get("image") or ctx.image_input()
    fmt = ctx.params.get("format") or "png"
    suffix = ".jpg" if fmt in ("jpg", "jpeg") else f".{fmt}"
    target = ctx.asset.path("outputs", f"{Path(source).stem}{suffix}")
    result = images.convert_image(
        source,
        target,
        fmt=fmt,
        width=int(ctx.params.get("width") or 0),
        height=int(ctx.params.get("height") or 0),
        quality=int(ctx.params.get("quality") or 90),
    )
    ctx.outputs["image"] = target
    ctx.artifact(target, "image", "converted")
    ctx.asset.set_primary("image", target)
    detail = f"{result['format']} {result['width']}x{result['height']} {human_bytes(result['bytes'])}"
    if result["warnings"]:
        detail += f"; {'; '.join(result['warnings'])}"
    return {"status": "PASS", "detail": detail}


def _image_thumbnail(ctx: Context) -> dict:
    source = ctx.outputs.get("image") or ctx.image_input()
    target = ctx.asset.path("previews", f"{Path(source).stem}-thumb.png")
    result = images.thumbnail(source, target, size=int(ctx.params.get("thumbnail") or 256))
    ctx.artifact(target, "preview", "thumbnail")
    return {"status": "PASS", "detail": f"{result['width']}x{result['height']}"}


def _image_pack_orm(ctx: Context) -> dict:
    paths = [ctx.input(name) for name in ("occlusion", "roughness", "metallic")]
    target = ctx.asset.path("outputs", f"{ctx.asset.id}-orm.png")
    result = images.pack_orm(*paths, target, resize=bool(ctx.params.get("resize") or False))
    ctx.outputs["image"] = target
    ctx.artifact(target, "texture", "orm")
    ctx.asset.set_primary("image", target)
    detail = f"ORM {result['width']}x{result['height']} {human_bytes(result['bytes'])}"
    if result["warnings"]:
        detail += f"; {'; '.join(result['warnings'])}"
    return {"status": "WARNING" if result["warnings"] else "PASS", "detail": detail}


def _image_atlas(ctx: Context) -> dict:
    source = ctx.input("source")
    if not source.is_dir():
        raise RunFailed(f"atlas input is not a directory: {source}")
    files = sorted(
        path for path in source.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )
    if not files:
        raise RunFailed(f"atlas input has no images: {source}")
    if len(files) > images.ATLAS_MAX_FRAMES:
        raise RunFailed(
            f"atlas accepts at most {images.ATLAS_MAX_FRAMES} images, got {len(files)}; "
            "split the folder into smaller batches"
        )
    copied = []
    provenance = ctx.job.data.setdefault("sources", {}).setdefault("source_frames", [])
    for path in files:
        record = ctx.asset.add_input(path, "image")
        copied.append(ctx.project.root / record["path"])
        provenance.append({
            "name": path.name,
            "original": str(path.resolve()),
            "sha256": record["sha256"],
            "input": record["path"],
        })
    ctx.job.save()
    target = ctx.asset.path("outputs", "atlas.png")
    metadata = ctx.asset.path("outputs", "atlas.json")
    result = images.make_atlas(
        copied,
        target,
        metadata,
        columns=int(ctx.params.get("columns", 4)),
        padding=int(ctx.params.get("padding", 2)),
    )
    ctx.outputs["image"] = target
    ctx.artifact(target, "texture", "atlas")
    ctx.artifact(metadata, "report", "atlas-metadata")
    ctx.asset.set_primary("image", target)
    return {"status": "PASS", "detail": f"{len(files)} frames, {result['width']}x{result['height']}"}


def _glb_inspect(ctx: Context) -> dict:
    source = ctx.mesh()
    ctx.outputs["source_mesh"] = source
    ctx.artifact(source, "mesh", "converted" if "convert" in ctx.outputs else "source")
    if ctx.asset.primary("mesh") is None:
        ctx.asset.set_primary("mesh", source)
    stats = inspect_glb(source)
    ctx.outputs["stats"] = stats
    ctx.report(f"{source.stem}-inspect.json", stats)
    return {
        "status": "PASS",
        "detail": f"{stats['triangles']} tris, {stats['vertices']} verts, {stats['materials']} materials, {stats['bytes']} bytes",
    }


def _glb_validate(ctx: Context) -> dict:
    source = ctx.mesh()
    report = validate_glb(source)
    if official.available(ctx.project):
        report["checks"] = [
            official.check(ctx.project, source) if check["id"] == "GLB-014" else check
            for check in report["checks"]
        ]
        summary = {status: 0 for status in ("PASS", "WARNING", "FAIL", "NOT_TESTED")}
        for item in report["checks"]:
            summary[item["status"]] += 1
        report["summary"] = summary
        report["status"] = "FAIL" if summary["FAIL"] else ("WARNING" if summary["WARNING"] else "PASS")
    ctx.report(f"{source.stem}-validation.json", report)
    for check in report["checks"]:
        ctx.validation.append({"artifact": source.name, **check})
    return {"status": report["status"], "detail": ", ".join(f"{key}={value}" for key, value in report["summary"].items())}


def _glb_optimize(ctx: Context) -> dict:
    provider = _provider(ctx, "gltf-transform")
    source = ctx.mesh()
    target = ctx.asset.path("outputs", f"{source.stem}-optimized.glb")
    command = list(provider.get("command") or [provider["path"]]) + [
        "optimize",
        str(source),
        str(target),
        "--compress",
        "false",
        "--flatten",
        "false",
        "--instance",
        "false",
        "--join",
        "false",
        "--palette",
        "false",
        "--simplify",
        "false",
        "--texture-compress",
        "false",
        "--prune",
        "true",
        "--prune-solid-textures",
        "false",
        "--weld",
        "true",
    ]
    from .util import run

    result = run(command, timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root)
    ctx.job.log("gltf-transform: " + " ".join(command))
    if result.get("timed_out"):
        raise RunFailed("gltf-transform timed out")
    if result["returncode"] != 0:
        raise RunFailed(f"gltf-transform exited {result['returncode']}: {(result['stderr'] or result['stdout'])[-800:]}")
    stats = inspect_glb(target)
    ctx.outputs["mesh"] = target
    ctx.outputs["optimized_stats"] = stats
    ctx.artifact(target, "mesh", "optimized")
    ctx.asset.set_primary("mesh", target)
    return {"status": "PASS", "detail": f"{stats['triangles']} tris, {stats['bytes']} bytes"}


def _glb_compare(ctx: Context) -> dict:
    source = Path(ctx.outputs.get("source_mesh") or ctx.mesh())
    optimized = ctx.outputs.get("mesh")
    if not optimized or Path(optimized) == source:
        raise RunFailed("glb.compare needs an optimized mesh")
    report = compare_glb(source, optimized)
    ctx.report(f"{source.stem}-comparison.json", report)
    delta = report["delta"]
    return {
        "status": "PASS",
        "detail": f"bytes {delta['bytes']:+d}, triangles {delta['triangles']:+d}, vertices {delta['vertices']:+d}",
    }


def _blender_gameready(ctx: Context) -> dict:
    provider = _provider(ctx, "blender")
    source = ctx.mesh()
    ctx.outputs.setdefault("source_mesh", source)
    budget_name = str(ctx.params.get("budget") or "game")
    try:
        target_tris, texture_cap, hard_cap = gameready.resolve_budget(
            budget_name,
            int(ctx.params.get("tris") or 0),
            int(ctx.params.get("texture") or 0),
        )
    except ValueError as exc:
        raise RunFailed(str(exc)) from exc
    target = ctx.asset.path("outputs", f"{source.stem}-gameready.glb")
    result = adapters.blender_gameready(
        provider,
        source,
        target,
        target_tris,
        texture_cap,
        timeout=float(ctx.params.get("timeout") or 900),
    )
    stats = inspect_glb(target)
    before = int((ctx.outputs.get("stats") or {}).get("triangles") or 0)
    try:
        gameready.reject_over_cap(stats["triangles"], hard_cap, budget_name)
    except ValueError as exc:
        target.unlink(missing_ok=True)
        raise RunFailed(f"{exc} Source had {before}.") from exc
    ctx.outputs["mesh"] = target
    report = result.get("report") or {}
    report["triangle_cap"] = hard_cap
    report["triangles"] = stats["triangles"]
    ctx.outputs["gameready"] = report
    ctx.artifact(target, "mesh", "gameready")
    ctx.asset.set_primary("mesh", target)
    shrunk = [
        item for item in (report.get("textures") or [])
        if item.get("before") != item.get("after")
    ]
    dropped = int((ctx.outputs.get("stats") or {}).get("animations") or 0) - stats["animations"]
    detail = (
        f"{stats['triangles']} tris (cap {hard_cap}, asked {target_tris}); "
        f"texture cap {texture_cap}; {len(shrunk)} texture(s) resized"
    )
    if dropped > 0:
        # Collapsing a mesh under animation is not safe to automate; be loud about it.
        return {"status": "WARNING", "detail": detail + f"; {dropped} animation(s) were NOT carried over"}
    return {"status": "PASS", "detail": detail}


def _blender_convert(ctx: Context) -> dict:
    provider = _provider(ctx, "blender")
    name = (ctx.recipe.get("input") or {}).get("name") or "source"
    original = ctx.inputs.get(name) or next(iter(ctx.inputs.values()), None)
    if original is None or not Path(original).is_file():
        raise RunFailed("mesh-convert needs one mesh file as --input")
    original = Path(original)
    if original.suffix.lower() not in adapters.CONVERTIBLE:
        raise RunFailed(f"{original.suffix or 'this file'} is not a convertible mesh format; supported: {', '.join(adapters.CONVERTIBLE)}")
    target = ctx.asset.path("outputs", f"{original.stem}.glb")
    # Read the source where it lies: an .obj needs its .mtl, a .gltf its .bin
    # and textures. The project keeps a copy of the main file as provenance.
    result = adapters.blender_convert(
        provider, original, target,
        animations=bool(ctx.params.get("animations", True)),
        timeout=float(ctx.params.get("timeout") or 900),
    )
    report = result.get("report") or {}
    ctx.outputs["mesh"] = target
    ctx.outputs["convert"] = report
    ctx.report(f"{original.stem}-convert.json", {"source_format": original.suffix.lower(), **report})
    return {
        "status": "PASS",
        "detail": (f"{original.suffix.lower()} -> glb via {report.get('importer', 'Blender')}; "
                   f"{report.get('meshes', '?')} mesh(es), {report.get('armatures', 0)} armature(s), {report.get('actions', 0)} action(s)"),
    }


def _blender_sample(ctx: Context) -> dict:
    provider = _provider(ctx, "blender")
    target = ctx.asset.path("outputs", "blender-sample.glb")
    adapters.blender_build(provider, target, timeout=float(ctx.params.get("timeout") or 240))
    stats = inspect_glb(target)
    ctx.outputs["mesh"] = target
    ctx.artifact(target, "mesh", "blender-sample")
    ctx.asset.set_primary("mesh", target)
    return {"status": "PASS", "detail": f"Blender {provider.get('version')}; {stats['triangles']} tris"}


def _blender_skills(ctx: Context) -> tuple[dict, dict, Path]:
    skills = _provider(ctx, "blender-skills")
    blender = _provider(ctx, "blender")
    skills_dir = Path((skills.get("details") or {}).get("skills_dir") or "")
    if not skills_dir.is_dir():
        raise RunFailed(f"blender-skills catalog is missing: {skills_dir}")
    return skills, blender, skills_dir


def _blender_blend(ctx: Context) -> Path:
    blend = ctx.outputs.get("blend")
    if blend is None:
        blend = ctx.input("blend")
    blend = Path(blend)
    if not blend.is_file():
        raise RunFailed(f"Blender source file is missing: {blend}")
    return blend


def _blender_skills_build(ctx: Context) -> dict:
    skills, blender, _ = _blender_skills(ctx)
    script = Path(__file__).resolve().parent / "data" / "blender" / "procedural_crate.py"
    target = ctx.asset.path("outputs", "blender-asset.blend")
    data, _ = adapters.blender_skills_exec(
        skills, blender, script, ["--out", str(target)],
        timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root,
    )
    if not target.is_file() or target.stat().st_size < 1000:
        raise RunFailed("blender-skills build reported success but wrote no .blend")
    ctx.outputs["blend"] = target
    ctx.artifact(target, "source", "blend")
    return {"status": "PASS", "detail": f"{data.get('polygons', 0)} polygons; {target.name}"}


def _drop_save_backup(blend: Path) -> None:
    """Saving over an existing .blend makes Blender write `<name>.blend1`.
    That copy is the pre-step file, already kept as its own artifact, so it is
    removed instead of left unrecorded in the asset."""
    backup = blend.with_name(blend.name + "1")
    if backup.is_file():
        backup.unlink()


def _blender_skills_material(ctx: Context) -> dict:
    skills, blender, skills_dir = _blender_skills(ctx)
    built = _blender_blend(ctx)
    # Keep the build stage immutable: material edits get their own .blend so the
    # recorded hash for the build artifact never goes stale.
    blend = ctx.asset.path("outputs", "blender-asset-material.blend")
    shutil.copy2(built, blend)
    script = skills_dir / "blender-pbr-materials" / "scripts" / "build_pbr_material.py"
    preset = str(ctx.params.get("preset") or "wood")
    data, _ = adapters.blender_skills_exec(
        skills, blender, script,
        ["--name", "M_BlenderAsset", "--preset", preset, "--objects", "SM_Crate", "--save", str(blend)],
        blend=blend, timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root,
    )
    _drop_save_backup(blend)
    assigned = data.get("assigned") or []
    if "SM_Crate" not in assigned:
        raise RunFailed(f"blender-skills did not assign the material: {data}")
    ctx.outputs["blend"] = blend
    ctx.artifact(blend, "source", "blend-material")
    ctx.report("blender-material.json", data)
    return {"status": "PASS", "detail": f"{data.get('material')} preset={preset}"}


def _blender_qa_gate(data: dict, warning_note: str) -> tuple[bool, str]:
    """A QA pass is not a clean pass while warnings are unacknowledged."""
    objects = data.get("objects") or {}
    triangles = sum(int(item.get("tris") or 0) for item in objects.values() if isinstance(item, dict))
    errors = data.get("errors") or []
    warnings = data.get("warnings") or []
    accepted = bool(warnings and warning_note)
    passed = bool(data.get("pass")) and not errors and (not warnings or accepted)
    detail = f"{triangles} tris; ground_z={data.get('ground_z')}; {len(errors)} error(s), {len(warnings)} warning(s)"
    if warnings and not accepted:
        detail += "; warnings need a fix or --set warning_note=<reason>"
    return passed, detail


def _blender_visual_review(visual_review: str, approval_note: str) -> tuple[str, str]:
    if visual_review not in ("pending", "approved"):
        raise RunFailed("visual_review must be pending or approved")
    if visual_review == "approved":
        if not approval_note:
            raise RunFailed("visual_review=approved requires approval_note describing the inspection")
        return "PASS", f"visual review approved: {approval_note}"
    return "NOT_TESTED", "review sheets generated; visual inspection pending"


def _blender_skills_qa(ctx: Context) -> dict:
    skills, blender, skills_dir = _blender_skills(ctx)
    blend = _blender_blend(ctx)
    object_name = str(ctx.params.get("object") or "SM_Crate")
    warning_note = str(ctx.params.get("warning_note") or "").strip()
    visual_review = str(ctx.params.get("visual_review") or "pending")
    approval_note = str(ctx.params.get("approval_note") or "").strip()
    visual_status, visual_detail = _blender_visual_review(visual_review, approval_note)

    qa_script = skills_dir / "blender-asset-qa" / "scripts" / "qa_check.py"
    args = ["--profile", "game", "--objects", object_name]
    data, _ = adapters.blender_skills_exec(
        skills, blender, qa_script, args, blend=blend,
        timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root,
    )
    qa_report = ctx.report("blender-qa.json", data)
    passed, detail = _blender_qa_gate(data, warning_note)
    errors = data.get("errors") or []
    warnings = data.get("warnings") or []
    warnings_accepted = bool(warnings and warning_note)
    triangles = sum(int(item.get("tris") or 0) for item in (data.get("objects") or {}).values() if isinstance(item, dict))
    ctx.validation.append({
        "artifact": blend.name,
        "id": "BLENDER-QA",
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    })

    reviews = []
    review_script = skills_dir / "blender-asset-qa" / "scripts" / "review_shots.py"
    for mode in ("random", "wire"):
        target = ctx.asset.path("previews", f"blender-qa-{mode}.png")
        adapters.blender_skills_exec(
            skills, blender, review_script,
            ["--out", str(target), "--mode", mode, "--res", "512", "--objects", object_name],
            blend=blend, timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root,
        )
        if not target.is_file() or target.stat().st_size < 1000:
            raise RunFailed(f"blender-asset-qa wrote no {mode} review sheet")
        ctx.artifact(target, "preview", f"blender-qa-{mode}")
        reviews.append({"mode": mode, "path": ctx.asset.relative(target)})

    ctx.validation.append({
        "artifact": blend.name,
        "id": "BLENDER-QA-RENDER",
        "status": "PASS",
        "detail": "random and wire review sheets generated; rendering is not visual approval",
    })
    ctx.validation.append({
        "artifact": blend.name,
        "id": "BLENDER-QA-VISUAL",
        "status": visual_status,
        "detail": visual_detail,
    })

    details = skills.get("details") or {}
    ctx.asset.manifest.setdefault("provenance", {})["blender_skills"] = {
        "version": skills.get("version"),
        "revision": details.get("revision"),
        "skills": details.get("skills"),
        "qa": {
            "pass": passed,
            "triangles": triangles,
            "ground_z": data.get("ground_z"),
            "errors": errors,
            "warnings": warnings,
            "warnings_accepted": warnings_accepted,
            "warning_note": warning_note if warnings else "",
            "report": qa_report.name,
        },
        "visual_review": {
            "status": visual_review,
            "note": approval_note if visual_review == "approved" else "",
            "recorded": now_iso() if visual_review == "approved" else None,
        },
        "reviews": reviews,
    }
    ctx.asset.save()
    if errors:
        raise RunFailed(f"blender-asset-qa gate failed: {errors[0]}")
    if warnings and not warnings_accepted:
        raise RunFailed(
            f"blender-asset-qa reported {len(warnings)} warning(s); fix them or "
            "pass --set warning_note=<reason for accepting>"
        )
    if not passed:
        raise RunFailed("blender-asset-qa reported failure without error or warning details")
    return {
        "status": "PASS",
        "detail": f"{triangles} tris; QA {len(warnings)} warning(s); 2 review sheets; visual {visual_review}",
    }



def _param_float(ctx: Context, name: str, default: str) -> float:
    raw = ctx.params.get(name, default)
    try:
        return float(str(raw).strip())
    except ValueError as exc:
        raise RunFailed(f"{name} must be a number, got {raw!r}") from exc


def _res_margin_args(ctx: Context) -> list[str]:
    res = int(ctx.params.get("res") or 2048)
    margin = int(ctx.params.get("margin_px") or 8)
    if not 64 <= res <= 8192:
        raise RunFailed("res must be between 64 and 8192")
    if not 0 <= margin <= 256:
        raise RunFailed("margin_px must be between 0 and 256")
    return ["--res", str(res), "--margin-px", str(margin)]


def _blender_skills_run(ctx: Context) -> dict:
    skills, blender, skills_dir = _blender_skills(ctx)
    blend = _blender_blend(ctx)
    recipe_id = str(ctx.recipe.get("id") or "")
    operation = str(ctx.params.get("operation") or "").strip()
    # Keep the runner surface explicit: each whitelisted operation maps to one
    # upstream script and only its documented arguments.
    operations = {
        "blender-optimize": {
            "mesh-stats": ("blender-game-optimization", "mesh_stats.py", False),
            "make-lods": ("blender-game-optimization", "make_lods.py", True),
        },
        "blender-retopo-uv": {
            "auto-retopo": ("blender-retopology-uv", "auto_retopo.py", True),
            "uv-pack": ("blender-retopology-uv", "uv_pack.py", True),
            "texel-density": ("blender-retopology-uv", "texel_density.py", bool(str(ctx.params.get("target") or "").strip())),
        },
    }
    mapping = operations.get(recipe_id, {}).get(operation)
    if mapping is None:
        raise RunFailed(f"unsupported blender-skills operation for {recipe_id}: {operation}")
    skill, script_name, mutating = mapping
    script = skills_dir / skill / "scripts" / script_name
    args = []
    for item in str(ctx.params.get("objects") or "").split():
        args.append(item)
    if args:
        args = ["--objects", *args]
    if operation == "mesh-stats" and ctx.params.get("budget"):
        args += ["--budget", str(ctx.params["budget"])]
    result_blend = ctx.asset.path("outputs", f"blender-{operation}.blend") if mutating else None
    if operation == "make-lods":
        ratios = str(ctx.params.get("ratios") or "0.5 0.25").split()
        try:
            ratio_values = [float(item) for item in ratios]
        except ValueError as exc:
            raise RunFailed("ratios must be space-separated numbers between 0 and 1") from exc
        if not ratio_values or any(not 0.0 < item < 1.0 for item in ratio_values):
            raise RunFailed("ratios must be space-separated numbers between 0 and 1")
        args += ["--ratios", *(str(item) for item in ratio_values)]
        if ctx.params.get("symmetry"):
            args.append("--symmetry")
        if ctx.params.get("cleanup"):
            args.append("--cleanup")
        if ctx.params.get("rename"):
            args.append("--rename")
        if ctx.params.get("collection"):
            args += ["--collection", str(ctx.params["collection"])]
    elif operation == "auto-retopo":
        method = (str(ctx.params.get("method") or "").strip() or "decimate")
        if method not in {"quadriflow", "decimate", "planar"}:
            raise RunFailed("method must be one of quadriflow, decimate, planar")
        args += ["--method", method]
        tris = _param_float(ctx, "tris", "10000")
        if tris < 1:
            raise RunFailed("tris must be at least 1")
        args += ["--tris", str(int(tris))]
        if str(ctx.params.get("voxel") or "").strip():
            voxel = _param_float(ctx, "voxel", "0")
            if voxel < 0:
                raise RunFailed("voxel must be zero or positive")
            args += ["--voxel", str(voxel)]
        if ctx.params.get("symmetry"):
            args.append("--symmetry")
    elif operation == "uv-pack":
        method = (str(ctx.params.get("method") or "").strip() or "smart")
        if method not in {"smart", "seams", "min_stretch"}:
            raise RunFailed("method must be one of smart, seams, min_stretch")
        args += ["--method", method]
        args += ["--angle", str(_param_float(ctx, "angle", "66"))]
        if str(ctx.params.get("seams_from_sharp") or "").strip():
            args += ["--seams-from-sharp", str(_param_float(ctx, "seams_from_sharp", "60"))]
        args += _res_margin_args(ctx)
        if ctx.params.get("lightmap"):
            args.append("--lightmap")
        args += ["--shape", str(ctx.params.get("shape") or "AABB")]
    elif operation == "texel-density":
        args += _res_margin_args(ctx)
        if str(ctx.params.get("target") or "").strip():
            target = _param_float(ctx, "target", "512")
            if target <= 0:
                raise RunFailed("target must be at least 1 px/m")
            args += ["--set", str(target)]
    if result_blend is not None:
        args += ["--save", str(result_blend)]
    data, _ = adapters.blender_skills_exec(
        skills, blender, script, args, blend=blend,
        timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root,
    )
    report = ctx.report(f"blender-{operation}.json", data)
    if data.get("ok") is not True:
        raise RunFailed(f"blender-skills {operation} reported failure: {data}")
    ctx.validation.append({
        "artifact": result_blend.name if result_blend else blend.name,
        "id": "BLENDER-SKILL",
        "status": "PASS",
        "detail": f"{recipe_id} {operation}",
    })
    if result_blend is not None:
        _drop_save_backup(result_blend)
        if not result_blend.is_file() or result_blend.stat().st_size < 1000:
            raise RunFailed(f"blender-skills {operation} wrote no output .blend")
        ctx.outputs["blend"] = result_blend
        ctx.artifact(result_blend, "source", f"blender-{operation}")
    return {"status": "PASS", "detail": f"{operation}; report {report.name}"}


def _blender_skills_export(ctx: Context) -> dict:
    skills, blender, skills_dir = _blender_skills(ctx)
    blend = _blender_blend(ctx)
    target = ctx.asset.path("outputs", "blender-asset.glb")
    script = skills_dir / "blender-export-pipelines" / "scripts" / "export_asset.py"
    data, _ = adapters.blender_skills_exec(
        skills, blender, script,
        ["--preset", "gltf", "--objects", "SM_Crate", "--out", str(target)],
        blend=blend, timeout=float(ctx.params.get("timeout") or 300), cwd=ctx.project.root,
    )
    if not target.is_file() or target.stat().st_size < 100:
        raise RunFailed(f"blender-skills export wrote no GLB: {data}")
    stats = inspect_glb(target)
    ctx.outputs["mesh"] = target
    ctx.artifact(target, "mesh", "deliverable")
    ctx.asset.set_primary("mesh", target)
    return {"status": "PASS", "detail": f"{stats['triangles']} tris; {human_bytes(target.stat().st_size)}"}



def _comfykit_check(ctx: Context) -> dict:
    provider = _provider(ctx, "comfy-kit")
    details = provider.get("details") or {}
    return {"status": "PASS", "detail": f"comfy-kit {provider.get('version') or 'unknown'}; {details.get('presets', 0)} presets"}


def _comfykit_generate(ctx: Context) -> dict:
    provider = _provider(ctx, "comfy-kit")
    root = Path(provider["path"])
    out_dir = ctx.asset.path("outputs", "generated").resolve()
    try:
        out_dir.relative_to(ctx.project.root.resolve())
    except ValueError as exc:
        raise RunFailed("refusing to write comfy-kit output outside the project") from exc
    out_dir.mkdir(parents=True, exist_ok=True)
    result = adapters.comfykit_generate(root, ctx.params, out_dir, timeout=float(ctx.params.get("timeout") or 900))
    files = adapters.comfykit_images(out_dir)
    if not files:
        raise RunFailed("comfy-kit reported success but produced no images in the assigned output folder")
    for path in files:
        ctx.artifact(path, "image", "generated")
    ctx.outputs["images"] = files
    ctx.outputs["image"] = files[0]
    ctx.asset.set_primary("image", files[0])
    return {"status": "PASS", "detail": f"{len(files)} image(s); first {files[0].name}"}


def _comfykit_import(ctx: Context) -> dict:
    _provider(ctx, "comfy-kit")
    source_dir = Path(ctx.input("source"))
    if not source_dir.is_dir():
        raise RunFailed(f"not a directory: {source_dir}")
    files = sorted(
        (item for item in source_dir.iterdir() if item.suffix.lower() in IMAGE_SUFFIXES),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    limit = max(1, min(int(ctx.params.get("limit") or 1), 24))
    if not files:
        raise RunFailed(f"no images in {source_dir}")
    imported = []
    for path in files[:limit]:
        record = ctx.asset.add_input(path, "image")
        imported.append(record)
        ctx.artifact(Path(ctx.project.root) / record["path"], "image", "imported")
    ctx.outputs["images"] = [Path(ctx.project.root) / item["path"] for item in imported]
    ctx.outputs["image"] = ctx.outputs["images"][0]
    ctx.asset.set_primary("image", ctx.outputs["image"])
    return {"status": "PASS", "detail": f"imported {len(imported)} image(s) from comfy-kit output"}


def _img2threejs_probe(ctx: Context) -> dict:
    provider = _provider(ctx, "img2threejs")
    source = ctx.image_input()
    target = ctx.asset.path("outputs", "img2threejs-probe.json")
    data = adapters.img2threejs_probe(Path(provider["path"]), source, target)
    ctx.artifact(target, "report", "img2threejs-probe")
    suitability = data.get("technicalSuitability") or "unknown"
    status = "PASS" if suitability in ("suitable", "good") else "WARNING"
    return {"status": status, "detail": f"technicalSuitability={suitability}; {len(data.get('warnings') or [])} warning(s)"}


def _img2threejs_codegen(ctx: Context) -> dict:
    provider = _provider(ctx, "img2threejs")
    spec = ctx.input("spec")
    target = ctx.asset.path("outputs", f"{Path(spec).stem}.ts")
    adapters.img2threejs_codegen(Path(provider["path"]), spec, target, timeout=float(ctx.params.get("timeout") or 120))
    ctx.artifact(target, "source", "threejs-factory")
    return {"status": "PASS", "detail": f"generated {human_bytes(target.stat().st_size)} of TypeScript"}


# A teardown sim is a small code folder; these caps stop a mistaken input such
# as a whole drive or a node_modules tree from being copied into the project.
TEARDOWN_MAX_FILES = 2000
TEARDOWN_MAX_BYTES = 512 * 1024 * 1024
TEARDOWN_SKIP = {"node_modules", "teardown-out", "__pycache__"}
STILLS = re.compile(r"^(?:\d+(?:\.\d+)?(?:,\d+(?:\.\d+)?){0,23}|every:\d+(?:\.\d+)?)$")
SIZE = re.compile(r"^(\d{2,4})x(\d{2,4})$")
ENTRY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def _teardown_entry(ctx: Context, source: Path) -> str:
    """Which folder holds the page's main.js. Upstream's own layout keeps the
    page in `<machine>-live` and imports `../<machine>-shared`, so the whole
    input is copied and the entry is one folder inside it."""
    entry = str(ctx.params.get("entry") or "").strip()
    if entry:
        if not ENTRY.match(entry):
            raise RunFailed("entry must be the name of one folder directly inside the input")
        if not (source / entry / "main.js").is_file():
            raise RunFailed(f"no main.js in {source / entry}")
        return entry
    if (source / "main.js").is_file():
        return ""
    found = sorted(child.name for child in source.iterdir() if child.is_dir() and (child / "main.js").is_file())
    if len(found) == 1:
        return found[0]
    if not found:
        raise RunFailed(f"a teardown sim is a folder with main.js; none in {source} or its folders")
    raise RunFailed(f"{source} holds several sims ({', '.join(found)}); choose one with --set entry=NAME")


def _teardown_copy_sim(ctx: Context, source: Path) -> Path:
    """Copy the sim folder into the asset with its layout intact, so relative
    imports and bundled .glb files still resolve. Links are refused."""
    target = ctx.asset.path("inputs", source.name)
    files: list[Path] = []
    total = 0
    for folder, dirs, names in os.walk(source, followlinks=False):
        here = Path(folder)
        dirs[:] = sorted(name for name in dirs if name not in TEARDOWN_SKIP and not name.startswith("."))
        for name in dirs:
            if (here / name).is_symlink():
                raise RunFailed(f"teardown sim contains a link, which is not copied: {here / name}")
        for name in sorted(names):
            path = here / name
            if path.is_symlink():
                raise RunFailed(f"teardown sim contains a link, which is not copied: {path}")
            files.append(path)
            total += path.stat().st_size
            if len(files) > TEARDOWN_MAX_FILES or total > TEARDOWN_MAX_BYTES:
                raise RunFailed(
                    f"teardown sim is larger than {TEARDOWN_MAX_FILES} files or {human_bytes(TEARDOWN_MAX_BYTES)}; "
                    "pass the folder that holds main.js"
                )
    inputs = ctx.asset.manifest.setdefault("inputs", [])
    for path in files:
        relative = path.relative_to(source)
        copy = target / relative
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, copy)
        inputs.append({
            "path": ctx.asset.relative(copy),
            "name": f"{source.name}/{relative.as_posix()}",
            "kind": "teardown-sim",
            "bytes": copy.stat().st_size,
            "sha256": sha256_file(copy),
        })
    ctx.asset.save()
    ctx.job.data.setdefault("sources", {})["teardown_sim"] = {
        "original": str(source.resolve()),
        "files": len(files),
        "bytes": total,
        "input": ctx.asset.relative(target),
    }
    return target


def _teardown_build(ctx: Context) -> dict:
    provider = _provider(ctx, "teardown")
    node = _provider(ctx, "node")
    source = ctx.input("source")
    if not source.is_dir():
        raise RunFailed(f"teardown input is not a folder: {source}")
    entry = _teardown_entry(ctx, source)
    copied = _teardown_copy_sim(ctx, source)
    sim = copied / entry if entry else copied
    out = ctx.asset.path("outputs", "teardown")
    try:
        page, _ = adapters.teardown_build(
            Path(node["path"]), Path(provider["path"]), sim, out, timeout=float(ctx.params.get("timeout") or 300)
        )
    except adapters.AdapterError as exc:
        raise RunFailed(str(exc)) from exc
    # The page and anything the build placed beside it (external models,
    # decoders listed in <name>.assets.json) are the deliverable.
    for path in sorted((out / "dist").rglob("*")):
        if path.is_file():
            ctx.artifact(path, "page" if path == page else "page-asset", path.name)
    ctx.asset.set_primary("page", page)
    ctx.outputs.update({"page": page, "teardown_out": out, "teardown_name": sim.name})
    ctx.validation.append({
        "artifact": page.name, "id": "TEARDOWN-BUILD", "status": "PASS",
        "detail": f"{human_bytes(page.stat().st_size)} single-file page from {sim.name}/main.js",
    })
    ctx.validation.append({
        "artifact": page.name, "id": "TEARDOWN-RENDER", "status": "NOT_TESTED",
        "detail": "bundled, not opened in a browser; teardown-film renders it",
    })
    return {"status": "PASS", "detail": f"{page.name} {human_bytes(page.stat().st_size)}"}


def _teardown_capture_args(ctx: Context) -> tuple[list[str], str]:
    args: list[str] = []
    size = str(ctx.params.get("size") or "1080x1350").strip()
    match = SIZE.match(size)
    if not match or not all(16 <= int(value) <= 3840 for value in match.groups()):
        raise RunFailed("size must be WIDTHxHEIGHT with each side 16-3840 CSS px")
    args += ["--size", size]
    fps = int(ctx.params.get("fps") or 30)
    if not 1 <= fps <= 120:
        raise RunFailed("fps must be 1-120")
    args += ["--fps", str(fps)]
    end = str(ctx.params.get("to") or "").strip()
    if end:
        try:
            seconds = float(end)
        except ValueError as exc:
            raise RunFailed("to must be a number of seconds") from exc
        if not 0 < seconds <= 600:
            raise RunFailed("to must be more than 0 and at most 600 seconds")
        args += ["--to", end]
    stills = str(ctx.params.get("stills") or "").strip()
    if stills:
        if not STILLS.match(stills):
            raise RunFailed("stills must be a comma list of seconds (at most 24) or every:<step>")
        args += ["--stills", stills, "--cols", str(min(4, max(1, stills.count(",") + 1)))]
    return args, ("png" if stills else "mp4")


def _teardown_capture(ctx: Context) -> dict:
    provider = _provider(ctx, "teardown")
    node = _provider(ctx, "node")
    args, kind = _teardown_capture_args(ctx)
    ffmpeg = _provider(ctx, "ffmpeg")["path"] if kind == "mp4" else None
    page = ctx.outputs.get("page")
    if not page:
        raise RunFailed("teardown.capture needs teardown.build first")
    name = ctx.outputs["teardown_name"]
    target = ctx.asset.path("outputs", f"{name}-sheet.png" if kind == "png" else f"{name}.mp4")
    try:
        result = adapters.teardown_capture(
            Path(node["path"]), Path(provider["path"]), name, ctx.outputs["teardown_out"], target, args,
            ffmpeg=ffmpeg, timeout=float(ctx.params.get("timeout") or 1800),
        )
    except adapters.AdapterError as exc:
        raise RunFailed(str(exc)) from exc
    gpu = next((line.strip() for line in result["stdout"].splitlines() if line.startswith("gpu:")), "")
    role = "preview" if kind == "png" else "video"
    ctx.artifact(target, role, target.name)
    # A review sheet comes with its full-size frames in `<sheet>-frames/`.
    frames = target.with_name(target.stem + "-frames")
    if kind == "png" and frames.is_dir():
        for frame in sorted(frames.glob("*.png")):
            ctx.artifact(frame, "preview-frame", f"{frames.name}/{frame.name}")
    ctx.asset.set_primary(role, target)
    ctx.validation = [item for item in ctx.validation if item["id"] != "TEARDOWN-RENDER"]
    ctx.validation.append({
        "artifact": target.name, "id": "TEARDOWN-RENDER", "status": "PASS",
        "detail": f"rendered in headless Chromium to {target.name} ({human_bytes(target.stat().st_size)})"
                  + (f"; {gpu}" if gpu else ""),
    })
    ctx.validation.append({
        "artifact": target.name, "id": "TEARDOWN-VISUAL", "status": "NOT_TESTED",
        "detail": "frames were rendered, not reviewed; open the file before calling it finished",
    })
    return {"status": "PASS", "detail": f"{target.name} {human_bytes(target.stat().st_size)}"}


def _asset_record(ctx: Context) -> dict:
    ctx.asset.manifest["provenance"]["versions"] = providers.tool_versions(ctx.project)
    ctx.asset.manifest["provenance"]["seed"] = ctx.params.get("seed")
    ctx.asset.manifest["source"] = {"recipe": ctx.recipe["id"], "params": ctx.params, "finished": now_iso()}
    if ctx.validation:
        ctx.asset.set_validation(ctx.validation)
    ctx.asset.save()
    return {"status": "PASS", "detail": f"{len(ctx.asset.manifest.get('artifacts', []))} artifact(s)"}


HANDLERS = {
    "image.inspect": _image_inspect,
    "image.convert": _image_convert,
    "image.thumbnail": _image_thumbnail,
    "image.pack_orm": _image_pack_orm,
    "image.atlas": _image_atlas,
    "glb.inspect": _glb_inspect,
    "glb.validate": _glb_validate,
    "glb.optimize": _glb_optimize,
    "glb.compare": _glb_compare,
    "blender.sample": _blender_sample,
    "blender.gameready": _blender_gameready,
    "blender.convert": _blender_convert,
    "blender.skills.build": _blender_skills_build,
    "blender.skills.material": _blender_skills_material,
    "blender.skills.qa": _blender_skills_qa,
    "blender.skills.export": _blender_skills_export,
    "blender.skills.run": _blender_skills_run,
    "comfykit.detect": _comfykit_check,
    "comfykit.generate": _comfykit_generate,
    "comfykit.import": _comfykit_import,
    "img2threejs.probe": _img2threejs_probe,
    "img2threejs.codegen": _img2threejs_codegen,
    "teardown.build": _teardown_build,
    "teardown.capture": _teardown_capture,
    "asset.record": _asset_record,
}


def _check_inputs(recipe: dict, inputs: dict[str, Path]) -> None:
    spec = recipe.get("input") or {}
    if spec.get("required"):
        name = spec.get("name", "input")
        if name not in inputs:
            raise RecipeError(f"recipe {recipe['id']} requires --input {name}=<path>")
    for name, item in (recipe.get("inputs") or {}).items():
        if item.get("required") and name not in inputs:
            raise RecipeError(f"recipe {recipe['id']} requires --input {name}=<path>")
    for name, path in inputs.items():
        if not Path(path).exists():
            raise RecipeError(f"input {name!r} does not exist: {path}")


def plan(recipe: dict, inputs: dict[str, Path], params: dict, project: Project | None = None) -> dict:
    providers_now = {item["id"]: item for item in providers.detect(project)}
    needs = []
    for step in recipe["steps"]:
        if step == "glb.optimize":
            needs.append("gltf-transform")
        elif step in ("blender.sample", "blender.gameready", "blender.convert"):
            needs.append("blender")
        elif step.startswith("blender.skills."):
            needs.extend(["blender-skills", "blender"])
        elif step.startswith("comfykit."):
            needs.append("comfy-kit")
        elif step == "img2threejs.probe":
            needs.append("img2threejs")
        elif step == "img2threejs.codegen":
            needs.append("img2threejs")
    return {
        "recipe": recipe["id"],
        "asset": None,
        "inputs": {name: str(path) for name, path in inputs.items()},
        "params": params,
        "steps": recipe["steps"],
        "providers": {item: providers_now.get(item) for item in sorted(set(needs))},
        "dry_run": True,
    }


def execute(project: Project, recipe: dict, inputs: dict[str, Path], params: dict, name: str | None = None, dry_run: bool = False):
    _check_inputs(recipe, inputs)
    if dry_run:
        return plan(recipe, inputs, params, project), None, None

    # Name the asset after what went in, so a folder of results is readable.
    asset = project.create_asset(name or (asset_name(recipe, inputs) if inputs else recipe["id"]), recipe["id"], params)
    copied: dict[str, Path] = {}
    sources: dict[str, dict] = {}
    for input_name, path in inputs.items():
        kind = "directory" if Path(path).is_dir() else "image" if Path(path).suffix.lower() in IMAGE_SUFFIXES else "mesh" if Path(path).suffix.lower() in MESH_SUFFIXES else "file"
        sources[input_name] = {"original": str(Path(path).resolve()), "kind": kind}
    try:
        job = Job.create(project, recipe["id"], params, asset.id, sources)
    except Exception:
        # The folder was just created by this call; remove it rather than leave
        # an asset with no job.
        shutil.rmtree(asset.folder, ignore_errors=True)
        raise
    ctx = Context(project, asset, job, recipe, inputs, params, copied)
    try:
        for input_name, path in inputs.items():
            if sources[input_name]["kind"] == "directory":
                continue
            record = asset.add_input(path, sources[input_name]["kind"])
            copied[input_name] = project.root / record["path"]
        for step in recipe["steps"]:
            handler = HANDLERS.get(step)
            if handler is None:
                raise RunFailed(f"no handler for {step}")
            result = handler(ctx)
            status = result.get("status", "PASS")
            job.step(step, "OK" if status in ("PASS", "WARNING", "NOT_TESTED") else "FAIL", result.get("detail", ""), outcome=status)
            if status == "FAIL":
                raise RunFailed(f"{step} failed: {result.get('detail', '')}")
        asset.manifest["status"] = "COMPLETE"
        asset.save()
        job.finish("SUCCEEDED")
        return job, asset, ctx
    except (RunFailed, StoreError, RecipeError, images.ImageError, adapters.AdapterError, GlbError, OSError) as exc:
        message = str(exc) or type(exc).__name__
        _mark_failed(asset)
        job.step("failed", "FAIL", message)
        job.finish("FAILED", message)
        raise
    except Exception as exc:
        # External tools and parsers can raise ordinary exceptions; a job must
        # still finish FAILED with the real type and message instead of hanging
        # in RUNNING.
        message = f"unexpected {type(exc).__name__}: {exc}"
        _mark_failed(asset)
        job.step("failed", "FAIL", message)
        job.finish("FAILED", message)
        raise RunFailed(message) from exc
